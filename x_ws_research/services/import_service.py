"""Post import pipeline: PostSource → keyword filter → SQLite + local images."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from crawler.post_source import create_import_source, load_posts_sync
from schemas.models import KeywordConfig, PostRecord
from services.image_store import resolve_image_path, store_local_image
from services.keyword_filter import filter_posts
from storage.database import Database
from storage.repository import ImportStats, PostRepository, TaskRepository


LogFn = Callable[[str, str], None]
ProgressFn = Callable[[int, int], None]
StopFn = Callable[[], bool]


@dataclass
class ImportRequest:
    path: Path
    keywords: KeywordConfig
    max_posts: int = 10_000
    db_path: Path | None = None
    images_root: Path | None = None


def run_import(
    request: ImportRequest,
    *,
    log: LogFn | None = None,
    progress: ProgressFn | None = None,
    should_stop: StopFn | None = None,
) -> ImportStats:
    """Synchronous import entry (safe to call from a QThread worker)."""

    def _log(msg: str, level: str = "INFO") -> None:
        if log:
            log(msg, level)

    def _stopped() -> bool:
        return bool(should_stop and should_stop())

    stats = ImportStats()
    db = Database(db_path=request.db_path)
    db.create_schema()

    source = create_import_source(request.path)
    posts = load_posts_sync(source)
    _log(f"Loaded {len(posts)} post(s) from {request.path.name}", "INFO")

    filtered = filter_posts(posts, request.keywords)
    stats.filtered_out = len(posts) - len(filtered)
    if stats.filtered_out:
        _log(f"Keyword filter excluded {stats.filtered_out} post(s)", "INFO")

    if request.max_posts > 0:
        filtered = filtered[: request.max_posts]

    base_dir = request.path.parent
    total = len(filtered)

    with db.session() as session:
        tasks = TaskRepository(session)
        posts_repo = PostRepository(session)
        task = tasks.create_task(kind="import", source_path=str(request.path))
        stats.task_id = task.id
        task.state = "RUNNING"
        session.commit()

        for index, post in enumerate(filtered, start=1):
            if _stopped():
                task.state = "CANCELLED"
                tasks.add_log(task.id, "Import cancelled by user", "WARN")
                tasks.finish(task, state="CANCELLED", stats=stats, note="cancelled")
                session.commit()
                _log("Import cancelled.", "WARN")
                return stats

            if progress:
                progress(index, total)

            try:
                _import_one(
                    posts_repo,
                    post,
                    base_dir=base_dir,
                    images_root=request.images_root,
                    stats=stats,
                    log=_log,
                )
                session.commit()
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                stats.errors += 1
                tasks.add_log(task.id, f"Error on {post.source_id}: {exc}", "ERROR")
                session.commit()
                _log(f"Error importing {post.source_id}: {exc}", "ERROR")

        tasks.finish(task, state="COMPLETED", stats=stats, note="ok")
        session.commit()

    _log(
        f"Import done: +{stats.inserted} posts, "
        f"{stats.skipped_duplicate} dupes, "
        f"{stats.images_linked} images linked "
        f"({stats.images_reused} reused), "
        f"{stats.errors} errors",
        "INFO",
    )
    return stats


def _import_one(
    repo: PostRepository,
    post: PostRecord,
    *,
    base_dir: Path,
    images_root: Path | None,
    stats: ImportStats,
    log: LogFn,
) -> None:
    existing = repo.get_by_source_id(post.source_id)
    if existing is not None:
        stats.skipped_duplicate += 1
        log(f"Skip duplicate source_id={post.source_id}", "INFO")
        # Still try to attach any new local images not yet linked
        _link_images(
            repo,
            existing,
            post,
            base_dir=base_dir,
            images_root=images_root,
            stats=stats,
            log=log,
        )
        return

    row = repo.insert_post(
        source_id=post.source_id,
        author_handle=post.author_handle,
        text=post.text,  # original text preserved
        created_at=post.created_at,
        url=post.url,
        raw=post.raw,
    )
    stats.inserted += 1
    log(f"Inserted post source_id={post.source_id}", "INFO")
    _link_images(
        repo,
        row,
        post,
        base_dir=base_dir,
        images_root=images_root,
        stats=stats,
        log=log,
    )


def _link_images(
    repo: PostRepository,
    row,
    post: PostRecord,
    *,
    base_dir: Path,
    images_root: Path | None,
    stats: ImportStats,
    log: LogFn,
) -> None:
    # Local paths only in Phase 2 (no remote download / no X)
    for order, raw_path in enumerate(post.image_paths):
        try:
            resolved = resolve_image_path(raw_path, base_dir=base_dir)
            stored = store_local_image(resolved, images_root=images_root)
            # Detect content already known in DB before linking
            known = repo.get_image_by_sha(stored.sha256) is not None
            _, newly = repo.ensure_image_link(
                post=row,
                sha256=stored.sha256,
                file_path=stored.file_path,
                original_name=stored.original_name,
                sort_order=order,
            )
            if newly:
                stats.images_linked += 1
            if stored.reused or known:
                stats.images_reused += 1
            log(
                f"Image {stored.original_name} sha={stored.sha256[:12]}… "
                f"{'reused' if (stored.reused or known) else 'stored'}",
                "INFO",
            )
        except FileNotFoundError as exc:
            stats.errors += 1
            log(str(exc), "ERROR")
        except Exception as exc:  # noqa: BLE001
            stats.errors += 1
            log(f"Image error ({raw_path}): {exc}", "ERROR")

    # Record remote URLs as metadata-only placeholders (no download)
    for order, url in enumerate(post.image_urls):
        if not url or url.startswith("file:"):
            continue
        # Skip URL-only images for binary storage; log for preview awareness
        log(f"Image URL noted (no download in Phase 2): {url}", "INFO")
