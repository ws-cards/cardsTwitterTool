"""Replaceable PostSource interface + working JSON/CSV importers.

No live X scraping. Local files only.
"""

from __future__ import annotations

import csv
import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Iterable

from schemas.models import PostRecord
from services.keyword_filter import filter_posts as _filter_posts


class PostSource(ABC):
    """Contract for every post data source (import, API adapter, …)."""

    @abstractmethod
    async def initialize(self) -> None:
        """Prepare resources (open files, validate paths, etc.)."""

    @abstractmethod
    def fetch_posts(self) -> AsyncIterator[PostRecord]:
        """Yield normalized posts. Must not hit live X."""
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Release resources."""


class _FileImportSource(PostSource):
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
    """JSON importer.

    Accepted shapes:
    - ``{"posts": [ {...}, ... ]}``
    - top-level list of post objects

    Optional per-post keys: ``image_paths`` (local files), ``image_urls``.
    """

    async def fetch_posts(self) -> AsyncIterator[PostRecord]:
        self._ensure_open()
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        items = raw["posts"] if isinstance(raw, dict) and "posts" in raw else raw
        if not isinstance(items, list):
            raise ValueError('JSON import expects a list or {"posts": [...]}')
        for item in items:
            yield coerce_post(item, base_dir=self.path.parent)


class CsvImportSource(_FileImportSource):
    """CSV importer.

    Columns: source_id, author_handle, text, created_at, url, image_urls, image_paths
    Multi-value fields use ``|`` as separator.
    """

    async def fetch_posts(self) -> AsyncIterator[PostRecord]:
        self._ensure_open()
        with self.path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                yield coerce_post(row, base_dir=self.path.parent)


def create_import_source(path: Path | str) -> PostSource:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".json":
        return JsonImportSource(path)
    if suffix == ".csv":
        return CsvImportSource(path)
    raise ValueError(f"Unsupported import format: {suffix} (use .json or .csv)")


def coerce_post(item: dict[str, Any] | Any, *, base_dir: Path | None = None) -> PostRecord:
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

    image_urls = _as_str_list(item.get("image_urls") or item.get("images") or [])
    image_paths_raw = _as_str_list(item.get("image_paths") or item.get("local_images") or [])
    image_paths = [_resolve_optional(p, base_dir) for p in image_paths_raw]

    source_id = str(item.get("source_id") or item.get("id") or "").strip()
    author = str(
        item.get("author_handle") or item.get("author") or item.get("handle") or ""
    ).strip()
    if not source_id:
        raise ValueError("post requires source_id (or id)")
    if not author:
        raise ValueError("post requires author_handle (or author/handle)")

    # Preserve original text exactly as provided
    text = item.get("text")
    if text is None:
        text = item.get("content")
    text = "" if text is None else str(text)

    return PostRecord(
        source_id=source_id,
        author_handle=author.lstrip("@"),
        text=text,
        created_at=created_at,
        url=item.get("url"),
        image_urls=image_urls,
        image_paths=image_paths,
        raw={k: v for k, v in item.items() if k != "raw"},
    )


def _as_str_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [u.strip() for u in value.split("|") if u.strip()]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if item is None:
                continue
            s = str(item).strip()
            if s:
                out.append(s)
        return out
    return [str(value)]


def _resolve_optional(raw: str, base_dir: Path | None) -> Path:
    path = Path(raw)
    if path.is_file():
        return path.resolve()
    if base_dir is not None:
        candidate = (base_dir / path).resolve()
        if candidate.is_file():
            return candidate
    # Keep unresolved path; import service will report FileNotFoundError
    return path if path.is_absolute() else ((base_dir / path) if base_dir else path)


async def collect_posts(source: PostSource) -> list[PostRecord]:
    await source.initialize()
    try:
        posts: list[PostRecord] = []
        async for post in source.fetch_posts():
            posts.append(post)
        return posts
    finally:
        await source.close()


def load_posts_sync(source: PostSource) -> list[PostRecord]:
    """Blocking helper for QThread / CLI (avoids nested asyncio.run issues)."""
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(collect_posts(source))

    # Already inside an event loop (e.g. pytest-asyncio): run in a fresh loop/thread
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(collect_posts(source))).result()


def filter_by_keywords(
    posts: Iterable[PostRecord],
    keywords: list[str],
    *,
    match_mode: str = "any",
    case_sensitive: bool = False,
    normalize_whitespace: bool = True,
) -> list[PostRecord]:
    """Back-compat wrapper — prefer ``services.keyword_filter.filter_posts``."""
    return _filter_posts(
        posts,
        keywords=keywords,
        match_mode=match_mode,
        case_sensitive=case_sensitive,
        normalize_whitespace=normalize_whitespace,
    )
