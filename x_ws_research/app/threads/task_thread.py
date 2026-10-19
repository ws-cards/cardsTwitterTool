"""Background task worker — import, recognition, corrections, export."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

from schemas.task_state import TaskState
from services.catalog_import import import_card_catalog
from services.deck_export import export_decks_csv
from services.import_service import ImportRequest, run_import
from services.recognition_service import (
    RecognitionRequest,
    apply_card_correction,
    run_recognition,
)
from storage.database import Database
from storage.repository import PostRepository, RecognitionRepository


class TaskWorker(QObject):
    """Runs long work off the UI thread. UI never writes the DB."""

    state_changed = Signal(str)
    log_message = Signal(str, str)
    progress = Signal(int, int)
    counts_changed = Signal(int, int, int, int)  # posts, images, vision, errors
    preview_ready = Signal(object)  # list[PostPreview]
    decks_ready = Signal(object)  # list[DeckPreview]
    recognitions_ready = Signal(object)
    finished_ok = Signal()
    failed = Signal(str)
    correction_applied = Signal(object)

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
        self._pending_catalog: Path | None = None
        self._pending_export: Path | None = None
        self._pending_correction: dict[str, Any] | None = None
        self._recognition_request: RecognitionRequest | None = None

    def configure_paths(self, db_path: Path | None, images_root: Path | None) -> None:
        self._db_path = db_path
        self._images_root = images_root

    def set_import_request(self, request: ImportRequest) -> None:
        self._pending_import = request

    def set_catalog_path(self, path: Path) -> None:
        self._pending_catalog = Path(path)

    def set_export_path(self, path: Path) -> None:
        self._pending_export = Path(path)

    def set_recognition_request(self, request: RecognitionRequest | None = None) -> None:
        self._recognition_request = request or RecognitionRequest(db_path=self._db_path)

    def set_correction(self, payload: dict[str, Any]) -> None:
        self._pending_correction = dict(payload)

    @Slot()
    def request_stop(self) -> None:
        self._stop_requested = True
        self.log_message.emit("Stop requested…", "WARN")

    @Slot()
    def run_demo_task(self) -> None:
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
            self._set_state(TaskState.RUNNING)
            stats = run_import(
                request,
                log=lambda m, l: self.log_message.emit(m, l),
                progress=lambda c, t: self.progress.emit(c, t),
                should_stop=lambda: self._stop_requested,
            )
            self._set_state(TaskState.CANCELLED if self._stop_requested else TaskState.COMPLETED)
            self._emit_db_snapshot(error_count=stats.errors)
            if not self._stop_requested:
                self.finished_ok.emit()
        except Exception as exc:  # noqa: BLE001
            self._set_state(TaskState.FAILED)
            self.failed.emit(str(exc))
            self.log_message.emit(f"Import failed: {exc}", "ERROR")

    @Slot()
    def run_catalog_import(self) -> None:
        self._stop_requested = False
        path = self._pending_catalog
        if path is None:
            self.failed.emit("No catalog path configured")
            return
        try:
            self._set_state(TaskState.INITIALIZING)
            self.log_message.emit(f"Importing catalog: {path}", "INFO")
            self._set_state(TaskState.RUNNING)
            stats = import_card_catalog(path, db_path=self._db_path)
            self.log_message.emit(
                f"Catalog: +{stats.inserted} / ~{stats.updated} / skip {stats.skipped} / err {stats.errors}",
                "INFO",
            )
            self._set_state(TaskState.COMPLETED)
            self._emit_db_snapshot(error_count=stats.errors)
            self.finished_ok.emit()
        except Exception as exc:  # noqa: BLE001
            self._set_state(TaskState.FAILED)
            self.failed.emit(str(exc))
            self.log_message.emit(f"Catalog import failed: {exc}", "ERROR")

    @Slot()
    def run_recognition_task(self) -> None:
        self._stop_requested = False
        req = self._recognition_request or RecognitionRequest(db_path=self._db_path)
        req.db_path = self._db_path
        try:
            self._set_state(TaskState.INITIALIZING)
            self.log_message.emit("Starting recognition…", "INFO")
            self._set_state(TaskState.RUNNING)
            stats = run_recognition(
                req,
                log=lambda m, l: self.log_message.emit(m, l),
                progress=lambda c, t: self.progress.emit(c, t),
                should_stop=lambda: self._stop_requested,
            )
            self._set_state(TaskState.CANCELLED if self._stop_requested else TaskState.COMPLETED)
            self._emit_db_snapshot(error_count=stats.errors, vision=stats.cards_detected)
            if not self._stop_requested:
                self.finished_ok.emit()
        except Exception as exc:  # noqa: BLE001
            self._set_state(TaskState.FAILED)
            self.failed.emit(str(exc))
            self.log_message.emit(f"Recognition failed: {exc}", "ERROR")

    @Slot()
    def run_export_task(self) -> None:
        path = self._pending_export
        if path is None:
            self.failed.emit("No export path configured")
            return
        try:
            self._set_state(TaskState.RUNNING)
            out = export_decks_csv(path, db_path=self._db_path)
            self.log_message.emit(f"Exported decks CSV: {out}", "INFO")
            self._set_state(TaskState.COMPLETED)
            self.finished_ok.emit()
        except Exception as exc:  # noqa: BLE001
            self._set_state(TaskState.FAILED)
            self.failed.emit(str(exc))
            self.log_message.emit(f"Export failed: {exc}", "ERROR")

    @Slot()
    def run_correction_task(self) -> None:
        payload = self._pending_correction
        if not payload:
            self.failed.emit("No correction payload")
            return
        try:
            result = apply_card_correction(
                db_path=self._db_path,
                deck_card_id=int(payload["deck_card_id"]),
                card_number=payload.get("card_number"),
                quantity=payload.get("quantity"),
                confirmed=payload.get("confirmed"),
                note=str(payload.get("note") or ""),
            )
            self.log_message.emit(
                f"Corrected deck_card#{result['id']} → {result['card_number']} x{result['quantity']}",
                "INFO",
            )
            self.correction_applied.emit(result)
            self._emit_db_snapshot()
            self.finished_ok.emit()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            self.log_message.emit(f"Correction failed: {exc}", "ERROR")

    @Slot()
    def refresh_preview(self) -> None:
        try:
            self._emit_db_snapshot()
            self.log_message.emit("Preview refreshed from database.", "INFO")
        except Exception as exc:  # noqa: BLE001
            self.log_message.emit(f"Refresh failed: {exc}", "ERROR")
            self.failed.emit(str(exc))

    def _emit_db_snapshot(self, error_count: int = 0, vision: int | None = None) -> None:
        db = Database(db_path=self._db_path)
        db.create_schema()
        with db.session() as session:
            posts_repo = PostRepository(session)
            recog_repo = RecognitionRepository(session)
            previews = posts_repo.list_posts(limit=200)
            posts = posts_repo.count_posts()
            images = posts_repo.count_images()
            vision_count = recog_repo.count_recognition() if vision is None else vision
            decks = recog_repo.list_decks(limit=200)
            recogs = recog_repo.list_recognitions(limit=500)
        self.counts_changed.emit(posts, images, vision_count, error_count)
        self.preview_ready.emit(previews)
        self.decks_ready.emit(decks)
        self.recognitions_ready.emit(recogs)

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
