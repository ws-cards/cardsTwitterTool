"""Replaceable PostSource interface + JSON/CSV import stubs (Phase 1).

No live X scraping. Import adapters establish the architecture for Phase 2.
"""

from __future__ import annotations

import csv
import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Iterable

from schemas.models import PostRecord


class PostSource(ABC):
    """Contract for every post data source (import, API adapter, …)."""

    @abstractmethod
    async def initialize(self) -> None:
        """Prepare resources (open files, validate paths, etc.)."""

    @abstractmethod
    def fetch_posts(self) -> AsyncIterator[PostRecord]:
        """Yield normalized posts. Implementations must not hit live X in Phase 1."""
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Release resources."""


class _FileImportSource(PostSource):
    """Shared helpers for file-based import stubs."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._opened = False

    async def initialize(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(f"Import file not found: {self.path}")
        if not self.path.is_file():
            raise ValueError(f"Import path is not a file: {self.path}")
        self._opened = True

    async def close(self) -> None:
        self._opened = False

    def _ensure_open(self) -> None:
        if not self._opened:
            raise RuntimeError("PostSource is not initialized; call initialize() first")


class JsonImportSource(_FileImportSource):
    """Stub JSON importer.

    Expected shapes (Phase 2 will harden parsing):
    - ``{"posts": [ {...}, ... ]}``
    - or a top-level list of post objects
    """

    async def fetch_posts(self) -> AsyncIterator[PostRecord]:
        self._ensure_open()
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        items = raw["posts"] if isinstance(raw, dict) and "posts" in raw else raw
        if not isinstance(items, list):
            raise ValueError("JSON import expects a list or {\"posts\": [...]}")
        for item in items:
            yield _coerce_post(item)


class CsvImportSource(_FileImportSource):
    """Stub CSV importer.

    Expected columns (flexible): source_id, author_handle, text, created_at, url, image_urls
    """

    async def fetch_posts(self) -> AsyncIterator[PostRecord]:
        self._ensure_open()
        with self.path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                yield _coerce_post(row)


def create_import_source(path: Path | str) -> PostSource:
    """Factory: choose JSON or CSV stub from file suffix."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".json":
        return JsonImportSource(path)
    if suffix == ".csv":
        return CsvImportSource(path)
    raise ValueError(f"Unsupported import format: {suffix} (use .json or .csv)")


def _coerce_post(item: dict[str, Any] | Any) -> PostRecord:
    if not isinstance(item, dict):
        raise TypeError(f"Post item must be a mapping, got {type(item)!r}")
    created = item.get("created_at")
    if isinstance(created, str) and created:
        try:
            created_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError:
            created_at = None
    elif isinstance(created, datetime):
        created_at = created
    else:
        created_at = None

    image_urls = item.get("image_urls") or item.get("images") or []
    if isinstance(image_urls, str):
        image_urls = [u.strip() for u in image_urls.split("|") if u.strip()]

    source_id = str(item.get("source_id") or item.get("id") or "")
    author = str(item.get("author_handle") or item.get("author") or item.get("handle") or "")
    if not source_id:
        raise ValueError("post requires source_id (or id)")
    if not author:
        raise ValueError("post requires author_handle (or author/handle)")

    return PostRecord(
        source_id=source_id,
        author_handle=author.lstrip("@"),
        text=str(item.get("text") or item.get("content") or ""),
        created_at=created_at,
        url=item.get("url"),
        image_urls=list(image_urls),
        raw=dict(item),
    )


async def collect_posts(source: PostSource) -> list[PostRecord]:
    """Utility for tests: initialize → fetch all → close."""
    await source.initialize()
    try:
        posts: list[PostRecord] = []
        async for post in source.fetch_posts():
            posts.append(post)
        return posts
    finally:
        await source.close()


def filter_by_keywords(
    posts: Iterable[PostRecord],
    keywords: list[str],
    *,
    match_mode: str = "any",
    case_sensitive: bool = False,
) -> list[PostRecord]:
    """Simple keyword filter scaffold (full pipeline in Phase 2)."""
    if not keywords:
        return list(posts)
    prepared = keywords if case_sensitive else [k.lower() for k in keywords]
    out: list[PostRecord] = []
    for post in posts:
        text = post.text if case_sensitive else post.text.lower()
        hits = [k in text for k in prepared]
        ok = all(hits) if match_mode == "all" else any(hits)
        if ok:
            out.append(post)
    return out
