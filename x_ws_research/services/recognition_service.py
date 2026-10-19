"""Background-safe recognition pipeline (heuristic / replaceable engines)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from services.catalog_import import load_catalog_map
from services.paths import ensure_data_dirs, get_data_root
from storage.database import Database
from storage.models import PostImageRow, PostRow
from storage.repository import ImportStats, RecognitionRepository, TaskRepository
from vision.card_number import normalize_card_number
from vision.heuristic import (
    CatalogCardMatcher,
    HeuristicCardNumberOCR,
    HeuristicDeckDetector,
    MergeDeckBuilder,
    PillowCardCropper,
)
from vision.interfaces import (
    CardCropper,
    CardMatcher,
    CardNumberOCR,
    CardRegion,
    DeckBuilder,
    DeckDetector,
)


LogFn = Callable[[str, str], None]
ProgressFn = Callable[[int, int], None]
StopFn = Callable[[], bool]


@dataclass
class RecognitionStats:
    images_processed: int = 0
    decks_created: int = 0
    cards_detected: int = 0
    empty_ocr: int = 0
    errors: int = 0
    task_id: int | None = None
    deck_ids: list[int] = field(default_factory=list)


@dataclass
class RecognitionRequest:
    db_path: Path | None = None
    crops_root: Path | None = None
    image_ids: list[int] | None = None  # None = all
    detector: DeckDetector | None = None
    cropper: CardCropper | None = None
    ocr: CardNumberOCR | None = None
    matcher: CardMatcher | None = None
    builder: DeckBuilder | None = None


def run_recognition(
    request: RecognitionRequest | None = None,
    *,
    log: LogFn | None = None,
    progress: ProgressFn | None = None,
    should_stop: StopFn | None = None,
) -> RecognitionStats:
    request = request or RecognitionRequest()

    def _log(msg: str, level: str = "INFO") -> None:
        if log:
            log(msg, level)

    def _stopped() -> bool:
        return bool(should_stop and should_stop())

    stats = RecognitionStats()
    db = Database(db_path=request.db_path)
    db.create_schema()
    ensure_data_dirs()
    crops_root = Path(request.crops_root or (get_data_root() / "crops"))
    crops_root.mkdir(parents=True, exist_ok=True)

    catalog = load_catalog_map(request.db_path)
    detector = request.detector or HeuristicDeckDetector()
    cropper = request.cropper or PillowCardCropper()
    ocr = request.ocr or HeuristicCardNumberOCR()
    matcher = request.matcher or CatalogCardMatcher(catalog)
    builder = request.builder or MergeDeckBuilder()

    with db.session() as session:
        tasks = TaskRepository(session)
        repo = RecognitionRepository(session)
        task = tasks.create_task(kind="recognition", source_path=None)
        stats.task_id = task.id
        task.state = "RUNNING"
        session.commit()

        images = repo.list_post_images()
        if request.image_ids is not None:
            allow = set(request.image_ids)
            images = [i for i in images if i.id in allow]

        total = max(1, len(images))
        _log(f"Recognition start: {len(images)} image(s), catalog={len(catalog)}", "INFO")

        for index, image in enumerate(images, start=1):
            if _stopped():
                task.state = "CANCELLED"
                tasks.add_log(task.id, "Recognition cancelled", "WARN")
                # Reuse ImportStats shape for finish counters loosely
                _finish_task(tasks, task, stats, state="CANCELLED")
                session.commit()
                return stats

            if progress:
                progress(index, total)

            try:
                deck_id = _recognize_one(
                    session,
                    repo,
                    image,
                    detector=detector,
                    cropper=cropper,
                    ocr=ocr,
                    matcher=matcher,
                    builder=builder,
                    crops_root=crops_root,
                    stats=stats,
                    log=_log,
                )
                if deck_id is not None:
                    stats.deck_ids.append(deck_id)
                    stats.decks_created += 1
                stats.images_processed += 1
                session.commit()
            except Exception as exc:  # noqa: BLE001 — never crash the host
                session.rollback()
                stats.errors += 1
                tasks.add_log(task.id, f"Image {image.id} failed: {exc}", "ERROR")
                session.commit()
                _log(f"Recognition error on image {image.id}: {exc}", "ERROR")

        _finish_task(tasks, task, stats, state="COMPLETED")
        session.commit()

    _log(
        f"Recognition done: images={stats.images_processed}, "
        f"decks={stats.decks_created}, cards={stats.cards_detected}, "
        f"empty_ocr={stats.empty_ocr}, errors={stats.errors}",
        "INFO",
    )
    return stats


def _finish_task(tasks: TaskRepository, task, stats: RecognitionStats, *, state: str) -> None:
    # Map into ImportStats fields for TaskRepository.finish reuse
    mapped = ImportStats(
        inserted=stats.decks_created,
        skipped_duplicate=0,
        filtered_out=stats.empty_ocr,
        images_linked=stats.images_processed,
        errors=stats.errors,
        task_id=stats.task_id,
    )
    tasks.finish(task, state=state, stats=mapped, note="recognition")


def _recognize_one(
    session,
    repo: RecognitionRepository,
    image: PostImageRow,
    *,
    detector: DeckDetector,
    cropper: CardCropper,
    ocr: CardNumberOCR,
    matcher: CardMatcher,
    builder: DeckBuilder,
    crops_root: Path,
    stats: RecognitionStats,
    log: LogFn,
) -> int | None:
    path = Path(image.file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Image file missing: {path}")

    post: PostRow | None = session.get(PostRow, image.post_id)
    source_key = f"post:{image.post_id}:image:{image.id}"
    out_dir = crops_root / f"img_{image.id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    regions = detector.detect(path)
    log(f"Image {image.id}: {len(regions)} region(s)", "INFO")
    crop_paths = cropper.crop(path, regions, out_dir=out_dir)

    card_entries: list[dict[str, Any]] = []
    recognition_ids: list[int] = []
    for region, crop_path in zip(regions, crop_paths, strict=False):
        status = "pending"
        number: str | None = None
        name: str | None = None
        confidence = 0.0
        detail: dict[str, Any] = {"region": region.as_dict()}
        try:
            raw_ocr = ocr.read_number(crop_path, region=region)
            if raw_ocr is None or str(raw_ocr).strip() == "":
                status = "empty"
                stats.empty_ocr += 1
            else:
                match = matcher.match(crop_path, ocr_hint=raw_ocr)
                if match is None or (match.matched_by == "none" and not match.card_number):
                    status = "empty"
                    stats.empty_ocr += 1
                else:
                    number = normalize_card_number(match.card_number)
                    name = match.name
                    confidence = match.confidence
                    status = "matched" if number else "empty"
                    detail["match"] = {
                        "matched_by": match.matched_by,
                        "confidence": match.confidence,
                        "raw": match.raw,
                    }
                    if number:
                        card_entries.append(
                            {
                                "card_number": number,
                                "name": name,
                                "quantity": 1,
                                "crop_path": str(crop_path),
                            }
                        )
                        stats.cards_detected += 1
                    else:
                        stats.empty_ocr += 1
        except Exception as exc:  # noqa: BLE001
            status = "failed"
            detail["error"] = str(exc)
            stats.errors += 1
            log(f"OCR/match failed for {crop_path.name}: {exc}", "ERROR")

        row = repo.add_recognition(
            post_image_id=image.id,
            deck_id=None,
            crop_path=str(crop_path),
            status=status,
            card_number=number,
            card_name=name,
            confidence=confidence,
            detail=detail,
        )
        recognition_ids.append(row.id)

    deck_list = builder.build(card_entries, source_key=source_key)
    deck_name = f"@{post.author_handle}" if post else f"image-{image.id}"
    deck_name = f"{deck_name} / img#{image.id}"
    deck = repo.create_deck(
        name=deck_name,
        post_id=image.post_id,
        post_image_id=image.id,
        source_key=source_key,
        cards=deck_list.cards,
    )

    from storage.models import RecognitionResultRow

    for rid in recognition_ids:
        rr = session.get(RecognitionResultRow, rid)
        if rr is not None:
            rr.deck_id = deck.id

    if post is not None:
        post.recognition_status = "done" if deck_list.cards else "empty"
        post.processed = True

    return deck.id


def apply_card_correction(
    *,
    db_path: Path | None,
    deck_card_id: int,
    card_number: str | None = None,
    quantity: int | None = None,
    confirmed: bool | None = None,
    note: str = "",
) -> dict[str, Any]:
    db = Database(db_path=db_path)
    db.create_schema()
    with db.session() as session:
        repo = RecognitionRepository(session)
        card = repo.correct_deck_card(
            deck_card_id,
            card_number=normalize_card_number(card_number) if card_number else card_number,
            quantity=quantity,
            confirmed=confirmed,
            note=note,
        )
        session.commit()
        return {
            "id": card.id,
            "card_number": card.card_number,
            "quantity": card.quantity,
            "confirmed": card.confirmed,
            "correction_log": card.correction_log,
        }
