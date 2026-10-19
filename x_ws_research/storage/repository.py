"""Repository helpers for posts / images / tasks (no UI coupling)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from storage.models import PostImageRow, PostRow, TaskLogRow, TaskRow, utcnow


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
