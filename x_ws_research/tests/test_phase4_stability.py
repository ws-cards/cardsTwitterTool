"""Phase 4: cleanup, cancel, paths, log cap — no live X."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from crawler.browser_manager import BrowserManager, BrowserStatus
from schemas.models import KeywordConfig
from services.import_service import ImportRequest, run_import
from services.log_buffer import LogBuffer
from services.paths import (
    assert_not_install_dir,
    ensure_data_dirs,
    get_browser_profile_dir,
    get_data_root,
    is_frozen,
)
from services.recognition_service import RecognitionRequest, run_recognition
from storage.database import Database
from storage.repository import PostRepository
from services.image_store import store_local_image


def test_log_buffer_hard_cap():
    buf = LogBuffer(max_entries=50)
    for i in range(5000):
        buf.append(f"line-{i}")
    assert len(buf) == 50
    assert "line-4999" in buf.lines()[-1]


def test_user_data_dirs_not_project_install(data_root, monkeypatch):
    monkeypatch.setenv("X_WS_DATA_ROOT", str(data_root))
    dirs = ensure_data_dirs()
    assert dirs["root"] == data_root.resolve()
    assert dirs["db"].is_dir()
    assert dirs["crops"].is_dir()
    assert get_browser_profile_dir() == data_root.resolve() / "browser_profile"
    # Default helper agrees
    assert get_data_root() == data_root.resolve()
    assert is_frozen() is False
    assert_not_install_dir(dirs["db"])  # no-op when not frozen


@pytest.mark.asyncio
async def test_browser_stop_idempotent(data_root):
    mgr = BrowserManager(profile_dir=data_root / "browser_profile", headless=True)
    await mgr.start()
    assert mgr.status == BrowserStatus.READY
    await mgr.stop()
    assert mgr.status == BrowserStatus.CLOSED
    await mgr.stop()  # second stop must not raise
    assert mgr.status == BrowserStatus.CLOSED


def test_import_cancel_cooperative(data_root, tmp_path):
    posts = tmp_path / "many.json"
    items = [
        {
            "source_id": f"id-{i}",
            "author_handle": "u",
            "text": f"Weiss {i}",
        }
        for i in range(40)
    ]
    posts.write_text(json.dumps({"posts": items}), encoding="utf-8")

    stop_after = {"n": 0}

    def should_stop() -> bool:
        stop_after["n"] += 1
        return stop_after["n"] > 5

    stats = run_import(
        ImportRequest(
            path=posts,
            keywords=KeywordConfig(keywords=["weiss"]),
            db_path=data_root / "db" / "cancel.sqlite",
            images_root=data_root / "images",
        ),
        should_stop=should_stop,
    )
    # Cancelled mid-way: fewer than all inserted
    assert stats.inserted < 40
    assert stats.task_id is not None


def test_recognition_cancel(data_root, tmp_path):
    db_path = data_root / "db" / "rcancel.sqlite"
    images_root = data_root / "images"
    # Seed two images
    db = Database(db_path)
    db.create_schema()
    with db.session() as session:
        repo = PostRepository(session)
        for i, color in enumerate([(1, 0, 0), (0, 1, 0), (0, 0, 1)]):
            raw = tmp_path / f"i{i}.png"
            Image.new("RGB", (40, 40), color).save(raw)
            stored = store_local_image(raw, images_root=images_root)
            post = repo.insert_post(
                source_id=f"s{i}",
                author_handle="u",
                text="x",
                created_at=None,
                url=None,
            )
            repo.ensure_image_link(
                post=post, sha256=stored.sha256, file_path=stored.file_path
            )
        session.commit()

    calls = {"n": 0}

    def should_stop() -> bool:
        calls["n"] += 1
        return calls["n"] > 1

    stats = run_recognition(
        RecognitionRequest(db_path=db_path, crops_root=data_root / "crops"),
        should_stop=should_stop,
    )
    assert stats.images_processed < 3
