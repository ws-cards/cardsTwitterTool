"""Main application window — Phase 2 import + preview."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QToolBar,
)

from app.threads.browser_thread import BrowserThread
from app.threads.task_thread import TaskThread
from app.widgets.left_panel import LeftSettingsPanel
from app.widgets.monitor_panel import MonitorPanel
from app.widgets.status_bar import AppStatusBar
from schemas.task_state import TaskState
from services.import_service import ImportRequest
from services.log_buffer import LogBuffer
from services.paths import ensure_data_dirs, get_browser_profile_dir, get_data_root
from storage.database import Database
from storage.repository import PostPreview


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("X 貼文蒐集 × Weiss Schwarz 牌組工具 — Phase 2")
        self.resize(1200, 760)

        self._dirs = ensure_data_dirs()
        self._db_path = get_data_root() / "db" / "app.sqlite"
        self._images_root = self._dirs["images"]
        Database(self._db_path).create_schema()

        self._log_buffer = LogBuffer(max_entries=500)
        self._task_state = TaskState.IDLE
        self._browser_status = "CLOSED"

        self._build_toolbar()
        self._build_central()
        self._status = AppStatusBar(self)
        self.setStatusBar(self._status)

        self._browser_thread = BrowserThread(profile_dir=get_browser_profile_dir())
        self._task_thread = TaskThread(
            db_path=self._db_path,
            images_root=self._images_root,
        )
        self._wire_threads()
        self._browser_thread.start()
        self._task_thread.start()

        self._apply_task_state(TaskState.IDLE)
        self.monitor.append_log("Application started (Phase 2 import).", "INFO")
        self.monitor.append_log(f"Data root: {self._dirs['root']}", "INFO")
        self.monitor.append_log(f"Database: {self._db_path}", "INFO")
        self._request_refresh()

    def _build_toolbar(self) -> None:
        tb = QToolBar("主工具列")
        tb.setMovable(False)
        self.addToolBar(tb)

        self.act_open_browser = QAction("開啟瀏覽器", self)
        self.act_close_browser = QAction("關閉瀏覽器", self)
        self.act_start = QAction("開始任務", self)
        self.act_stop = QAction("停止任務", self)
        self.act_import = QAction("匯入…", self)
        self.act_about = QAction("關於", self)

        self.act_close_browser.setEnabled(False)
        self.act_stop.setEnabled(False)

        tb.addAction(self.act_open_browser)
        tb.addAction(self.act_close_browser)
        tb.addSeparator()
        tb.addAction(self.act_start)
        tb.addAction(self.act_stop)
        tb.addSeparator()
        tb.addAction(self.act_import)
        tb.addAction(self.act_about)

        self.act_open_browser.triggered.connect(self._on_open_browser)
        self.act_close_browser.triggered.connect(self._on_close_browser)
        self.act_start.triggered.connect(self._on_start_task)
        self.act_stop.triggered.connect(self._on_stop_task)
        self.act_import.triggered.connect(self._on_import)
        self.act_about.triggered.connect(self._on_about)

    def _build_central(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.left = LeftSettingsPanel()
        self.monitor = MonitorPanel(log_buffer=self._log_buffer)
        splitter.addWidget(self.left)
        splitter.addWidget(self.monitor)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([380, 820])
        self.setCentralWidget(splitter)

        self.left.start_requested.connect(self._on_start_task)
        self.left.stop_requested.connect(self._on_stop_task)
        self.left.refresh_requested.connect(self._on_refresh)
        self.left.import_requested.connect(lambda _: self._on_import())
        self.monitor.open_browser_requested.connect(self._on_open_browser)
        self.monitor.close_browser_requested.connect(self._on_close_browser)
        self.monitor.open_output_requested.connect(self._on_open_output)

    def _wire_threads(self) -> None:
        bw = self._browser_thread.worker
        tw = self._task_thread.worker

        if os.environ.get("X_WS_BROWSER_HEADLESS", "").lower() in {"1", "true", "yes"}:
            bw.set_headless(True)

        bw.started_ok.connect(self._on_browser_started)
        bw.stopped_ok.connect(self._on_browser_stopped)
        bw.failed.connect(self._on_browser_failed)
        bw.status_changed.connect(self._on_browser_status)
        bw.log_message.connect(self.monitor.append_log)

        tw.state_changed.connect(self._on_task_state_str)
        tw.log_message.connect(self.monitor.append_log)
        tw.progress.connect(self._on_task_progress)
        tw.counts_changed.connect(self._on_counts)
        tw.preview_ready.connect(self._on_preview_ready)
        tw.finished_ok.connect(lambda: self._status.set_hint("任務完成"))
        tw.failed.connect(self._on_task_failed)

    def _invoke_worker(self, method_name: str) -> None:
        from PySide6.QtCore import QMetaObject, Qt as QtCoreQt

        QMetaObject.invokeMethod(
            self._task_thread.worker,
            method_name,
            QtCoreQt.ConnectionType.QueuedConnection,
        )

    def _invoke_browser(self, method_name: str) -> None:
        from PySide6.QtCore import QMetaObject, Qt as QtCoreQt

        QMetaObject.invokeMethod(
            self._browser_thread.worker,
            method_name,
            QtCoreQt.ConnectionType.QueuedConnection,
        )

    # --- Browser ---

    @Slot()
    def _on_open_browser(self) -> None:
        self._status.set_hint("正在啟動瀏覽器…")
        self.act_open_browser.setEnabled(False)
        self.monitor.btn_open_browser.setEnabled(False)
        self._invoke_browser("open_browser")

    @Slot()
    def _on_close_browser(self) -> None:
        self._status.set_hint("正在關閉瀏覽器…")
        self._invoke_browser("close_browser")

    @Slot()
    def _on_browser_started(self) -> None:
        self._status.set_hint("瀏覽器已就緒")

    @Slot()
    def _on_browser_stopped(self) -> None:
        self._status.set_hint("瀏覽器已關閉")

    @Slot(str)
    def _on_browser_failed(self, message: str) -> None:
        self.monitor.append_log(message, "ERROR")
        self._status.set_hint("瀏覽器錯誤")
        QMessageBox.warning(
            self,
            "瀏覽器啟動失敗",
            f"無法啟動 Chromium，應用程式將繼續執行。\n\n{message}",
        )
        self.act_open_browser.setEnabled(True)
        self.monitor.btn_open_browser.setEnabled(True)

    @Slot(str)
    def _on_browser_status(self, status: str) -> None:
        self._browser_status = status
        self.monitor.set_browser_status(status)
        self._status.set_browser_status(status)
        self.act_open_browser.setEnabled(status in {"CLOSED", "ERROR"})
        self.act_close_browser.setEnabled(status in {"READY", "ERROR"})

    # --- Task / import ---

    @Slot()
    def _on_start_task(self) -> None:
        """Phase 2: Start opens the import dialog (primary data path)."""
        if not self._task_state.can_start:
            return
        # Avoid nested modal when already choosing a file via 匯入…
        self._on_import()

    @Slot()
    def _on_stop_task(self) -> None:
        if not self._task_state.can_stop:
            return
        self._invoke_worker("request_stop")

    @Slot()
    def _on_refresh(self) -> None:
        self._request_refresh()

    def _request_refresh(self) -> None:
        self._invoke_worker("refresh_preview")

    @Slot(str)
    def _on_task_state_str(self, state_name: str) -> None:
        self._apply_task_state(TaskState(state_name))

    def _apply_task_state(self, state: TaskState) -> None:
        self._task_state = state
        self.left.apply_task_state(state.value)
        self.monitor.set_task_state(state.value)
        self._status.set_task_state(state.value)
        self.act_start.setEnabled(state.can_start)
        self.act_stop.setEnabled(state.can_stop)
        self.act_import.setEnabled(state.can_start)

    @Slot(int, int)
    def _on_task_progress(self, current: int, total: int) -> None:
        self._status.set_hint(f"進度 {current}/{total}")

    @Slot(int, int, int, int)
    def _on_counts(self, posts: int, images: int, vision: int, errors: int) -> None:
        self.monitor.set_counts(posts=posts, images=images, vision=vision, errors=errors)

    @Slot(object)
    def _on_preview_ready(self, previews: object) -> None:
        if isinstance(previews, list):
            typed = [p for p in previews if isinstance(p, PostPreview)]
            self.monitor.show_post_previews(typed)

    @Slot(str)
    def _on_task_failed(self, message: str) -> None:
        QMessageBox.warning(self, "任務失敗", message)

    @Slot()
    def _on_import(self) -> None:
        if not self._task_state.can_start:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "匯入貼文（JSON / CSV）",
            str(Path.cwd()),
            "Import (*.json *.csv)",
        )
        if not path:
            return

        request = ImportRequest(
            path=Path(path),
            keywords=self.left.keyword_config(),
            max_posts=self.left.max_posts.value(),
            db_path=self._db_path,
            images_root=self._images_root,
        )
        self._task_thread.worker.set_import_request(request)
        self.monitor.append_log(f"Queued import: {path}", "INFO")
        self._status.set_hint("匯入中…")
        self._invoke_worker("run_import_task")

    @Slot()
    def _on_open_output(self) -> None:
        out = self._dirs["exports"]
        out.mkdir(parents=True, exist_ok=True)
        self.monitor.append_log(f"Output folder: {out}", "INFO")
        self._status.set_hint(str(out))

    @Slot()
    def _on_about(self) -> None:
        QMessageBox.information(
            self,
            "關於",
            "X 貼文蒐集與 Weiss Schwarz 牌組辨識工具\n"
            "Phase 2：JSON/CSV 匯入、關鍵字篩選、SQLite、去重、預覽。\n"
            "不含 X 網頁自動化擷取。",
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        self.monitor.append_log("Shutting down…", "INFO")
        from PySide6.QtCore import QEventLoop, QMetaObject, QTimer, Qt as QtCoreQt

        loop = QEventLoop(self)
        self._browser_thread.worker.stopped_ok.connect(loop.quit)
        self._browser_thread.worker.failed.connect(loop.quit)
        QMetaObject.invokeMethod(
            self._browser_thread.worker,
            "cleanup",
            QtCoreQt.ConnectionType.QueuedConnection,
        )
        QTimer.singleShot(8000, loop.quit)
        if self._browser_status in {"READY", "STARTING"}:
            loop.exec()

        self._browser_thread.quit()
        self._task_thread.quit()
        self._browser_thread.wait(3000)
        self._task_thread.wait(3000)
        event.accept()
