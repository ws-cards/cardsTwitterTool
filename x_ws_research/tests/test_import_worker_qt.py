"""Background import via TaskWorker signals — no live X."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from app.threads.task_thread import TaskWorker
from schemas.models import KeywordConfig
from schemas.task_state import TaskState
from services.import_service import ImportRequest
from storage.repository import PostPreview


def _png(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (4, 4), (10, 20, 30)).save(path)
    return path


def test_import_worker_emits_preview(qtbot, data_root, tmp_path):
    img = _png(tmp_path / "i.png")
    posts = tmp_path / "posts.json"
    posts.write_text(
        json.dumps(
            {
                "posts": [
                    {
                        "source_id": "w1",
                        "author_handle": "worker",
                        "text": "Weiss import via worker",
                        "image_paths": [img.name],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    worker = TaskWorker(
        db_path=data_root / "db" / "worker.sqlite",
        images_root=data_root / "images",
    )
    worker.set_import_request(
        ImportRequest(
            path=posts,
            keywords=KeywordConfig(keywords=["weiss"]),
            db_path=data_root / "db" / "worker.sqlite",
            images_root=data_root / "images",
        )
    )

    states: list[str] = []
    previews: list[PostPreview] = []
    worker.state_changed.connect(states.append)

    def _capture(obj):
        if isinstance(obj, list):
            previews.clear()
            previews.extend(p for p in obj if isinstance(p, PostPreview))

    worker.preview_ready.connect(_capture)

    with qtbot.waitSignal(worker.finished_ok, timeout=10_000):
        worker.run_import_task()

    assert TaskState.COMPLETED.value in states
    assert TaskState.RUNNING.value in states
    assert len(previews) >= 1
    assert previews[0].source_id == "w1"
    assert previews[0].image_count == 1
