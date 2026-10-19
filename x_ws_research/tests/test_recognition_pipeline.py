"""End-to-end recognition with synthetic images — no live X."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
from sqlalchemy import select

from services.catalog_import import import_card_catalog
from services.deck_export import export_decks_csv
from services.image_store import store_local_image
from services.recognition_service import (
    RecognitionRequest,
    apply_card_correction,
    run_recognition,
)
from storage.database import Database
from storage.models import DeckCardRow, DeckRow, PostImageRow, PostRow, RecognitionResultRow
from storage.repository import PostRepository, RecognitionRepository
from vision.heuristic import RaisingOCR


def _png(path: Path, color=(20, 30, 40)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (120, 80), color).save(path)
    return path


def _seed_post_with_image(db_path: Path, images_root: Path, tmp_path: Path, *, source_id: str, color):
    raw = _png(tmp_path / f"{source_id}.png", color)
    sidecar = raw.with_suffix(raw.suffix + ".cards.json")
    # Two regions same card + one other → merge qty 2 + 1 within image
    sidecar.write_text(
        json.dumps(
            {
                "regions": [
                    {"x": 0, "y": 0, "width": 60, "height": 80, "hint_text": "ABC/S100-001"},
                    {"x": 60, "y": 0, "width": 60, "height": 80, "hint_text": "ABC/S100-001"},
                    {"x": 0, "y": 0, "width": 40, "height": 40, "hint_text": "BD/W10-002"},
                ]
            }
        ),
        encoding="utf-8",
    )
    # Also copy sidecar next to stored image path after store
    stored = store_local_image(raw, images_root=images_root)
    stored_sidecar = Path(stored.file_path).with_suffix(
        Path(stored.file_path).suffix + ".cards.json"
    )
    stored_sidecar.write_text(sidecar.read_text(encoding="utf-8"), encoding="utf-8")

    db = Database(db_path)
    db.create_schema()
    with db.session() as session:
        repo = PostRepository(session)
        post = repo.insert_post(
            source_id=source_id,
            author_handle="tester",
            text="deck shot",
            created_at=None,
            url=None,
        )
        img, _ = repo.ensure_image_link(
            post=post,
            sha256=stored.sha256,
            file_path=stored.file_path,
            original_name=stored.original_name,
        )
        session.commit()
        return post.id, img.id


def test_quantity_merge_and_separate_decks(data_root, tmp_path):
    db_path = data_root / "db" / "recog.sqlite"
    images_root = data_root / "images"

    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "cards": [
                    {"card_number": "ABC/S100-001", "name": "Card A"},
                    {"card_number": "BD/W10-002", "name": "Card B"},
                ]
            }
        ),
        encoding="utf-8",
    )
    import_card_catalog(catalog, db_path=db_path)

    _seed_post_with_image(db_path, images_root, tmp_path / "p1", source_id="p1", color=(1, 2, 3))
    _seed_post_with_image(db_path, images_root, tmp_path / "p2", source_id="p2", color=(9, 8, 7))

    stats = run_recognition(RecognitionRequest(db_path=db_path, crops_root=data_root / "crops"))
    assert stats.images_processed == 2
    assert stats.decks_created == 2
    assert stats.errors == 0

    db = Database(db_path)
    with db.session() as session:
        decks = list(session.scalars(select(DeckRow)))
        assert len(decks) == 2
        # Each deck independently has ABC qty 2 (not 4 across posts)
        for deck in decks:
            cards = {
                c.card_number: c.quantity
                for c in session.scalars(
                    select(DeckCardRow).where(DeckCardRow.deck_id == deck.id)
                )
            }
            assert cards["ABC/S100-001"] == 2
            assert cards["BD/W10-002"] == 1

        recogs = list(session.scalars(select(RecognitionResultRow)))
        assert len(recogs) == 6  # 3 regions × 2 images
        assert any(r.status == "matched" for r in recogs)


def test_ocr_failure_does_not_crash(data_root, tmp_path):
    db_path = data_root / "db" / "fail.sqlite"
    images_root = data_root / "images"
    _seed_post_with_image(db_path, images_root, tmp_path, source_id="fx", color=(5, 5, 5))

    stats = run_recognition(
        RecognitionRequest(
            db_path=db_path,
            crops_root=data_root / "crops",
            ocr=RaisingOCR(),
        )
    )
    # Pipeline completes; per-region OCR errors counted, UI host not crashed
    assert stats.images_processed == 1
    assert stats.decks_created == 1
    assert stats.errors >= 1

    db = Database(db_path)
    with db.session() as session:
        statuses = [r.status for r in session.scalars(select(RecognitionResultRow))]
        assert "failed" in statuses


def test_correction_keeps_history(data_root, tmp_path):
    db_path = data_root / "db" / "corr.sqlite"
    images_root = data_root / "images"
    catalog = tmp_path / "c.csv"
    catalog.write_text(
        "card_number,name,set_code\nABC/S100-001,Card A,ABC\n",
        encoding="utf-8",
    )
    import_card_catalog(catalog, db_path=db_path)
    _seed_post_with_image(db_path, images_root, tmp_path, source_id="c1", color=(2, 2, 2))
    run_recognition(RecognitionRequest(db_path=db_path, crops_root=data_root / "crops"))

    db = Database(db_path)
    with db.session() as session:
        card = session.scalars(select(DeckCardRow)).first()
        assert card is not None
        card_id = card.id

    result = apply_card_correction(
        db_path=db_path,
        deck_card_id=card_id,
        card_number="ABC/S100-099",
        quantity=4,
        confirmed=True,
        note="manual fix",
    )
    assert result["card_number"] == "ABC/S100-099"
    assert result["quantity"] == 4
    assert result["confirmed"] is True
    assert "manual fix" in (result["correction_log"] or "")


def test_export_csv(data_root, tmp_path):
    db_path = data_root / "db" / "exp.sqlite"
    images_root = data_root / "images"
    _seed_post_with_image(db_path, images_root, tmp_path, source_id="e1", color=(3, 3, 3))
    run_recognition(RecognitionRequest(db_path=db_path, crops_root=data_root / "crops"))
    out = export_decks_csv(data_root / "exports" / "decks.csv", db_path=db_path)
    text = out.read_text(encoding="utf-8")
    assert "card_number" in text
    assert "ABC/S100-001" in text
