"""Local image storage: SHA-256 dedup, files on disk (never blobs in SQLite)."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from services.paths import ensure_data_dirs, get_data_root

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


@dataclass(frozen=True)
class StoredImage:
    sha256: str
    file_path: Path
    original_name: str
    reused: bool


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def get_images_root() -> Path:
    ensure_data_dirs()
    root = get_data_root() / "images"
    root.mkdir(parents=True, exist_ok=True)
    return root


def store_local_image(source: Path, *, images_root: Path | None = None) -> StoredImage:
    """Copy ``source`` into the images tree keyed by content hash.

    If an identical file already exists, reuse it (no second copy).
    """
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(f"Image not found: {source}")

    digest = sha256_file(source)
    root = images_root or get_images_root()
    suffix = source.suffix.lower() if source.suffix else ".bin"
    dest_dir = root / digest[:2]
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{digest}{suffix}"

    reused = dest.exists()
    if not reused:
        shutil.copy2(source, dest)

    return StoredImage(
        sha256=digest,
        file_path=dest,
        original_name=source.name,
        reused=reused,
    )


def resolve_image_path(raw: str | Path, *, base_dir: Path | None = None) -> Path:
    path = Path(raw)
    if path.is_file():
        return path.resolve()
    if base_dir is not None:
        candidate = (base_dir / path).resolve()
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Cannot resolve image path: {raw}")
