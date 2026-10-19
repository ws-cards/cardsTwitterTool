"""Phase 2 import / dedup / multi-image tests — no live X."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
from sqlalchemy import func, select

from schemas.models import KeywordConfig
from services.image_store import sha256_file
from services.import_service import ImportRequest, run_import
from storage.database import Database
from storage.models import PostImageRow, PostRow
from storage.repository import PostRepository


def _write_png(path: Path, color: tuple[int, int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), color).save(path)
    return path


def _sample_bundle(tmp_path: Path) -> tuple[Path, Path, Path]:
    img_dir = tmp_path / "imgs"
    a = _write_png(img_dir / "a.png", (255, 0, 0))
    b = _write_png(img_dir / "b.png", (0, 255, 0))
    # identical content to a → same SHA
    a_copy = _write_png(img_dir / "a_copy.png", (255, 0, 0))

    posts_json = tmp_path / "posts.json"
    posts_json.write_text(
        json.dumps(
            {
                "posts": [
                    {
                        "source_id": "p1",
                        "author_handle": "alice",
                        "text": "Weiss Schwarz デッキ ABC/S123-001",
                        "created_at": "2024-01-01T12:00:00+00:00",
                        "image_paths": ["imgs/a.png", "imgs/b.png"],
                    },
                    {
                        "source_id": "p2",
                        "author_handle": "bob",
                        "text": "unrelated cooking recipe",
                        "image_paths": ["imgs/a_copy.png"],
                    },
                    {
                        "source_id": "p3",
                        "author_handle": "carol",
                        "text": "Another WEISS post",
                        "image_paths": [],
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return posts_json, a, b


def test_json_import_with_keyword_or_and_images(data_root, tmp_path):
    posts_json, img_a, img_b = _sample_bundle(tmp_path)
    db_path = data_root / "db" / "import.sqlite"
    images_root = data_root / "images"

    stats = run_import(
        ImportRequest(
            path=posts_json,
            keywords=KeywordConfig(keywords=["weiss"], match_mode="any"),
            db_path=db_path,
            images_root=images_root,
        )
    )
    # p1 + p3 match; p2 filtered
    assert stats.inserted == 2
    assert stats.filtered_out == 1
    assert stats.images_linked == 2  # a.png + b.png on p1
    assert stats.errors == 0

    db = Database(db_path)
    with db.session() as session:
        repo = PostRepository(session)
        assert repo.count_posts() == 2
        p1 = repo.get_by_source_id("p1")
        assert p1 is not None
        assert "ABC/S123-001" in p1.text
        assert len(p1.images) == 2
        assert sha256_file(img_a) in {i.sha256 for i in p1.images}
        assert sha256_file(img_b) in {i.sha256 for i in p1.images}
        # binaries stored on disk, not in DB columns as blobs
        for img in p1.images:
            stored = Path(img.file_path)
            assert stored.is_file()
            assert str(images_root.resolve()) in str(stored.resolve())


def test_duplicate_import_skips_same_source_id(data_root, tmp_path):
    posts_json, _, _ = _sample_bundle(tmp_path)
    db_path = data_root / "db" / "dedup.sqlite"
    images_root = data_root / "images"
    kw = KeywordConfig(keywords=[], match_mode="any")

    first = run_import(
        ImportRequest(path=posts_json, keywords=kw, db_path=db_path, images_root=images_root)
    )
    second = run_import(
        ImportRequest(path=posts_json, keywords=kw, db_path=db_path, images_root=images_root)
    )
    assert first.inserted == 3
    assert second.inserted == 0
    assert second.skipped_duplicate == 3

    db = Database(db_path)
    with db.session() as session:
        count = session.scalar(select(func.count()).select_from(PostRow))
        assert count == 3


def test_image_sha_dedup_reuses_file(data_root, tmp_path):
    img_dir = tmp_path / "imgs"
    a = _write_png(img_dir / "a.png", (1, 2, 3))
    twin = _write_png(img_dir / "twin.png", (1, 2, 3))
    assert sha256_file(a) == sha256_file(twin)

    posts_json = tmp_path / "multi.json"
    posts_json.write_text(
        json.dumps(
            {
                "posts": [
                    {
                        "source_id": "x1",
                        "author_handle": "a",
                        "text": "one",
                        "image_paths": ["imgs/a.png"],
                    },
                    {
                        "source_id": "x2",
                        "author_handle": "b",
                        "text": "two",
                        "image_paths": ["imgs/twin.png"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    db_path = data_root / "db" / "sha.sqlite"
    images_root = data_root / "images"
    stats = run_import(
        ImportRequest(
            path=posts_json,
            keywords=KeywordConfig(),
            db_path=db_path,
            images_root=images_root,
        )
    )
    assert stats.inserted == 2
    assert stats.images_linked == 2
    assert stats.images_reused >= 1

    # Only one physical file under images_root for that hash
    digest = sha256_file(a)
    stored = list(images_root.rglob(f"{digest}.*"))
    assert len(stored) == 1

    db = Database(db_path)
    with db.session() as session:
        rows = list(session.scalars(select(PostImageRow)))
        assert len(rows) == 2
        assert {r.sha256 for r in rows} == {digest}
        assert rows[0].file_path == rows[1].file_path


def test_keyword_and_mode(data_root, tmp_path):
    posts_json, _, _ = _sample_bundle(tmp_path)
    stats = run_import(
        ImportRequest(
            path=posts_json,
            keywords=KeywordConfig(
                keywords=["weiss", "デッキ"],
                match_mode="all",
                case_sensitive=False,
            ),
            db_path=data_root / "db" / "and.sqlite",
            images_root=data_root / "images",
        )
    )
    # Only p1 has both weiss and デッキ
    assert stats.inserted == 1
    assert stats.filtered_out == 2


def test_csv_import(data_root, tmp_path):
    img = _write_png(tmp_path / "c.png", (9, 9, 9))
    csv_path = tmp_path / "posts.csv"
    csv_path.write_text(
        "source_id,author_handle,text,created_at,url,image_urls,image_paths\n"
        "c1,dave,Hello Weiss,2024-03-01T00:00:00Z,https://example.com/c1,,"
        f"{img.name}\n",
        encoding="utf-8",
    )
    stats = run_import(
        ImportRequest(
            path=csv_path,
            keywords=KeywordConfig(keywords=["weiss"]),
            db_path=data_root / "db" / "csv.sqlite",
            images_root=data_root / "images",
        )
    )
    assert stats.inserted == 1
    assert stats.images_linked == 1
