"""Repository helpers for posts / images / tasks (no UI coupling)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from storage.models import (
    DeckCardRow,
    DeckRow,
    PostImageRow,
    PostRow,
    RecognitionResultRow,
    TaskLogRow,
    TaskRow,
    utcnow,
)


@dataclass
class ImportStats:
    inserted: int = 0
    skipped_duplicate: int = 0
    filtered_out: int = 0
    images_linked: int = 0
    images_reused: int = 0
    errors: int = 0
    task_id: int | None = None


@dataclass
class PostPreview:
    id: int
    source_id: str
    author_handle: str
    text: str
    created_at: datetime | None
    url: str | None
    image_count: int
    image_paths: list[str] = field(default_factory=list)


class PostRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_source_id(self, source_id: str) -> PostRow | None:
        return self.session.scalar(
            select(PostRow)
            .options(selectinload(PostRow.images))
            .where(PostRow.source_id == source_id)
        )

    def get_image_by_sha(self, sha256: str) -> PostImageRow | None:
        """Return any existing image row with this content hash (for path reuse)."""
        return self.session.scalar(select(PostImageRow).where(PostImageRow.sha256 == sha256))

    def insert_post(
        self,
        *,
        source_id: str,
        author_handle: str,
        text: str,
        created_at: datetime | None,
        url: str | None,
        raw: dict[str, Any] | None = None,
    ) -> PostRow:
        row = PostRow(
            source_id=source_id,
            author_handle=author_handle,
            text=text,
            created_at=created_at,
            url=url,
            raw_json=json.dumps(raw, ensure_ascii=False, default=str) if raw else None,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def ensure_image_link(
        self,
        *,
        post: PostRow,
        sha256: str,
        file_path: Path,
        source_url: str | None = None,
        original_name: str | None = None,
        sort_order: int = 0,
    ) -> tuple[PostImageRow, bool]:
        """Attach image to post; reuse stored path if SHA already known.

        Returns (row, newly_linked_to_this_post).
        """
        for img in post.images:
            if img.sha256 == sha256:
                return img, False

        canonical = self.get_image_by_sha(sha256)
        stored_path = Path(canonical.file_path) if canonical is not None else file_path
        reused = canonical is not None

        row = PostImageRow(
            post_id=post.id,
            sha256=sha256,
            file_path=str(stored_path),
            source_url=source_url or (canonical.source_url if canonical else None),
            original_name=original_name or (canonical.original_name if canonical else None),
            sort_order=sort_order,
        )
        self.session.add(row)
        self.session.flush()
        _ = reused  # file-path reuse tracked by caller via store_local_image
        return row, True

    def list_posts(self, *, limit: int = 200) -> list[PostPreview]:
        stmt = (
            select(PostRow)
            .options(selectinload(PostRow.images))
            .order_by(PostRow.id.desc())
            .limit(limit)
        )
        rows = list(self.session.scalars(stmt))
        previews: list[PostPreview] = []
        for row in rows:
            paths = [img.file_path for img in sorted(row.images, key=lambda i: i.sort_order)]
            previews.append(
                PostPreview(
                    id=row.id,
                    source_id=row.source_id,
                    author_handle=row.author_handle,
                    text=row.text,
                    created_at=row.created_at,
                    url=row.url,
                    image_count=len(row.images),
                    image_paths=paths,
                )
            )
        return previews

    def count_posts(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(PostRow)) or 0)

    def count_images(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(PostImageRow)) or 0)


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_task(self, *, kind: str, source_path: str | None = None) -> TaskRow:
        row = TaskRow(kind=kind, state="INITIALIZING", source_path=source_path)
        self.session.add(row)
        self.session.flush()
        return row

    def add_log(self, task_id: int | None, message: str, level: str = "INFO") -> TaskLogRow:
        row = TaskLogRow(task_id=task_id, message=message, level=level.upper())
        self.session.add(row)
        return row

    def finish(
        self,
        task: TaskRow,
        *,
        state: str,
        stats: ImportStats,
        note: str = "",
    ) -> None:
        task.state = state
        task.finished_at = utcnow()
        task.posts_inserted = stats.inserted
        task.posts_skipped = stats.skipped_duplicate + stats.filtered_out
        task.images_linked = stats.images_linked
        task.error_count = stats.errors
        task.note = note


@dataclass
class DeckCardPreview:
    id: int
    card_number: str | None
    card_name: str | None
    quantity: int
    confirmed: bool
    correction_log: str | None = None


@dataclass
class DeckPreview:
    id: int
    name: str
    post_id: int | None
    post_image_id: int | None
    source_key: str
    status: str
    cards: list[DeckCardPreview] = field(default_factory=list)


@dataclass
class RecognitionPreview:
    id: int
    post_image_id: int | None
    deck_id: int | None
    crop_path: str | None
    status: str
    card_number: str | None
    card_name: str | None
    confidence: str | None
    confirmed: bool


class RecognitionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_post_images(self, *, limit: int = 500) -> list[PostImageRow]:
        stmt = (
            select(PostImageRow)
            .order_by(PostImageRow.id.asc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def count_recognition(self) -> int:
        return int(
            self.session.scalar(select(func.count()).select_from(RecognitionResultRow)) or 0
        )

    def create_deck(
        self,
        *,
        name: str,
        post_id: int | None,
        post_image_id: int | None,
        source_key: str,
        cards: list[dict[str, Any]],
    ) -> DeckRow:
        deck = DeckRow(
            name=name,
            post_id=post_id,
            post_image_id=post_image_id,
            source_key=source_key,
            status="draft",
        )
        self.session.add(deck)
        self.session.flush()
        for card in cards:
            self.session.add(
                DeckCardRow(
                    deck_id=deck.id,
                    card_number=card.get("card_number"),
                    card_name=card.get("name") or card.get("card_name"),
                    quantity=int(card.get("quantity") or 1),
                    confirmed=bool(card.get("confirmed", False)),
                    correction_log=None,
                )
            )
        self.session.flush()
        return deck

    def add_recognition(
        self,
        *,
        post_image_id: int | None,
        deck_id: int | None,
        crop_path: str | None,
        status: str,
        card_number: str | None,
        card_name: str | None,
        confidence: float | None,
        detail: dict[str, Any] | None = None,
    ) -> RecognitionResultRow:
        row = RecognitionResultRow(
            post_image_id=post_image_id,
            deck_id=deck_id,
            crop_path=crop_path,
            status=status,
            card_number=card_number,
            card_name=card_name,
            confidence=None if confidence is None else f"{confidence:.3f}",
            confirmed=False,
            detail_json=json.dumps(detail or {}, ensure_ascii=False, default=str),
        )
        self.session.add(row)
        self.session.flush()
        return row

    def list_decks(self, *, limit: int = 200) -> list[DeckPreview]:
        stmt = (
            select(DeckRow)
            .options(selectinload(DeckRow.cards))
            .order_by(DeckRow.id.desc())
            .limit(limit)
        )
        previews: list[DeckPreview] = []
        for deck in self.session.scalars(stmt):
            previews.append(
                DeckPreview(
                    id=deck.id,
                    name=deck.name,
                    post_id=deck.post_id,
                    post_image_id=deck.post_image_id,
                    source_key=deck.source_key,
                    status=deck.status,
                    cards=[
                        DeckCardPreview(
                            id=c.id,
                            card_number=c.card_number,
                            card_name=c.card_name,
                            quantity=c.quantity,
                            confirmed=c.confirmed,
                            correction_log=c.correction_log,
                        )
                        for c in sorted(
                            deck.cards,
                            key=lambda x: (x.card_number is None, x.card_number or ""),
                        )
                    ],
                )
            )
        return previews

    def list_recognitions(self, *, limit: int = 500) -> list[RecognitionPreview]:
        stmt = (
            select(RecognitionResultRow)
            .order_by(RecognitionResultRow.id.desc())
            .limit(limit)
        )
        return [
            RecognitionPreview(
                id=r.id,
                post_image_id=r.post_image_id,
                deck_id=r.deck_id,
                crop_path=r.crop_path,
                status=r.status,
                card_number=r.card_number,
                card_name=r.card_name,
                confidence=r.confidence,
                confirmed=r.confirmed,
            )
            for r in self.session.scalars(stmt)
        ]

    def correct_deck_card(
        self,
        deck_card_id: int,
        *,
        card_number: str | None = None,
        quantity: int | None = None,
        confirmed: bool | None = None,
        note: str = "",
    ) -> DeckCardRow:
        card = self.session.get(DeckCardRow, deck_card_id)
        if card is None:
            raise KeyError(f"deck_card {deck_card_id} not found")
        history: list[dict[str, Any]] = []
        if card.correction_log:
            try:
                history = json.loads(card.correction_log)
            except json.JSONDecodeError:
                history = [{"raw": card.correction_log}]
        before = {
            "card_number": card.card_number,
            "quantity": card.quantity,
            "confirmed": card.confirmed,
        }
        if card_number is not None:
            card.card_number = card_number
        if quantity is not None:
            card.quantity = int(quantity)
        if confirmed is not None:
            card.confirmed = bool(confirmed)
        history.append(
            {
                "at": utcnow().isoformat(),
                "before": before,
                "after": {
                    "card_number": card.card_number,
                    "quantity": card.quantity,
                    "confirmed": card.confirmed,
                },
                "note": note,
            }
        )
        card.correction_log = json.dumps(history, ensure_ascii=False)
        self.session.flush()
        return card

    def correct_recognition(
        self,
        recognition_id: int,
        *,
        card_number: str | None = None,
        confirmed: bool | None = None,
        note: str = "",
    ) -> RecognitionResultRow:
        row = self.session.get(RecognitionResultRow, recognition_id)
        if row is None:
            raise KeyError(f"recognition {recognition_id} not found")
        detail: dict[str, Any] = {}
        if row.detail_json:
            try:
                detail = json.loads(row.detail_json)
            except json.JSONDecodeError:
                detail = {}
        history = list(detail.get("corrections") or [])
        before = {"card_number": row.card_number, "confirmed": row.confirmed, "status": row.status}
        if card_number is not None:
            row.card_number = card_number
            row.status = "corrected"
        if confirmed is not None:
            row.confirmed = bool(confirmed)
        history.append(
            {
                "at": utcnow().isoformat(),
                "before": before,
                "after": {
                    "card_number": row.card_number,
                    "confirmed": row.confirmed,
                    "status": row.status,
                },
                "note": note,
            }
        )
        detail["corrections"] = history
        row.detail_json = json.dumps(detail, ensure_ascii=False)
        self.session.flush()
        return row
