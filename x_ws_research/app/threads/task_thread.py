"""Background task worker — import pipeline + optional demo lifecycle."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from schemas.models import KeywordConfig
from schemas.task_state import TaskState
from services.import_service import ImportRequest, run_import
from storage.database import Database
from storage.repository import PostPreview, PostRepository


class TaskWorker(QObject):
    """Runs import (and demo) work off the UI thread. UI never writes the DB."""

    state_changed = Signal(str)
    log_message = Signal(str, str)
    progress = Signal(int, int)  # current, total
    counts_changed = Signal(int, int, int, int)  # posts, images, vision, errors
    preview_ready = Signal(object)  # list[PostPreview]
    finished_ok = Signal()
    failed = Signal(str)

    def __init__(
        self,
        db_path: Path | None = None,
        images_root: Path | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._stop_requested = False
        self._db_path = db_path
        self._images_root = images_root
        self._pending_import: ImportRequest | None = None

    def configure_paths(self, db_path: Path | None, images_root: Path | None) -> None:
        self._db_path = db_path
        self._images_root = images_root

    def set_import_request(self, request: ImportRequest) -> None:
        self._pending_import = request

    @Slot()
    def request_stop(self) -> None:
        self._stop_requested = True
        self.log_message.emit("Stop requested…", "WARN")

    @Slot()
    def run_demo_task(self) -> None:
        """Legacy Phase 1 demo — still useful for button/state wiring tests."""
        self._stop_requested = False
        try:
            self._set_state(TaskState.INITIALIZING)
            self.log_message.emit("Initializing task (demo, no network)…", "INFO")
            time.sleep(0.15)
            if self._stop_requested:
                self._set_state(TaskState.CANCELLED)
                return

            self._set_state(TaskState.RUNNING)
            total = 5
            for i in range(1, total + 1):
                if self._stop_requested:
                    self._set_state(TaskState.STOPPING)
                    self.log_message.emit("Stopping task…", "WARN")
                    time.sleep(0.05)
                    self._set_state(TaskState.CANCELLED)
                    self.log_message.emit("Task cancelled.", "WARN")
                    return
                self.progress.emit(i, total)
                self.log_message.emit(f"Demo step {i}/{total}", "INFO")
                time.sleep(0.1)

            self._set_state(TaskState.COMPLETED)
            self.log_message.emit("Demo task completed.", "INFO")
            self.finished_ok.emit()
        except Exception as exc:  # noqa: BLE001
            self._set_state(TaskState.FAILED)
            self.failed.emit(str(exc))
            self.log_message.emit(f"Task failed: {exc}", "ERROR")

    @Slot()
    def run_import_task(self) -> None:
        """Execute pending ImportRequest; emits logs/progress/preview via signals."""
        self._stop_requested = False
        request = self._pending_import
        if request is None:
            self.failed.emit("No import request configured")
            return

        if self._db_path is not None:
            request.db_path = self._db_path
        if self._images_root is not None:
            request.images_root = self._images_root

        try:
            self._set_state(TaskState.INITIALIZING)
            self.log_message.emit(f"Starting import: {request.path}", "INFO")

            def _log(msg: str, level: str) -> None:
                self.log_message.emit(msg, level)

            def _progress(cur: int, total: int) -> None:
                self.progress.emit(cur, total)

            def _stop() -> bool:
                return self._stop_requested

            self._set_state(TaskState.RUNNING)
            stats = run_import(
                request,
                log=_log,
                progress=_progress,
                should_stop=_stop,
            )

            if self._stop_requested:
                self._set_state(TaskState.CANCELLED)
            else:
                self._set_state(TaskState.COMPLETED)

            self._emit_db_snapshot(error_count=stats.errors)
            if self._stop_requested:
                return
            self.finished_ok.emit()
        except Exception as exc:  # noqa: BLE001
            self._set_state(TaskState.FAILED)
            self.failed.emit(str(exc))
            self.log_message.emit(f"Import failed: {exc}", "ERROR")

    @Slot()
    def refresh_preview(self) -> None:
        try:
            self._emit_db_snapshot()
            self.log_message.emit("Preview refreshed from database.", "INFO")
        except Exception as exc:  # noqa: BLE001
            self.log_message.emit(f"Refresh failed: {exc}", "ERROR")
            self.failed.emit(str(exc))

    def _emit_db_snapshot(self, error_count: int = 0) -> None:
        db = Database(db_path=self._db_path)
        db.create_schema()
        with db.session() as session:
            repo = PostRepository(session)
            previews = repo.list_posts(limit=200)
            posts = repo.count_posts()
            images = repo.count_images()
        self.counts_changed.emit(posts, images, 0, error_count)
        self.preview_ready.emit(previews)

    def _set_state(self, state: TaskState) -> None:
        self.state_changed.emit(state.value)


class TaskThread(QThread):
    def __init__(
        self,
        db_path: Path | None = None,
        images_root: Path | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.worker = TaskWorker(db_path=db_path, images_root=images_root)
        self.worker.moveToThread(self)
