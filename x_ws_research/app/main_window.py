"""Main application window — Phase 1 shell."""

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
    QWidget,
)

from app.threads.browser_thread import BrowserThread
from app.threads.task_thread import TaskThread
from app.widgets.left_panel import LeftSettingsPanel
from app.widgets.monitor_panel import MonitorPanel
from app.widgets.status_bar import AppStatusBar
from schemas.task_state import TaskState
from services.log_buffer import LogBuffer
from services.paths import ensure_data_dirs, get_browser_profile_dir


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("X 貼文蒐集 × Weiss Schwarz 牌組工具 — Phase 1")
        self.resize(1200, 760)

        self._dirs = ensure_data_dirs()
        self._log_buffer = LogBuffer(max_entries=500)
        self._task_state = TaskState.IDLE
        self._browser_status = "CLOSED"

        self._build_toolbar()
        self._build_central()
        self._status = AppStatusBar(self)
        self.setStatusBar(self._status)

        self._browser_thread = BrowserThread(profile_dir=get_browser_profile_dir())
        self._task_thread = TaskThread()
        self._wire_threads()
        self._browser_thread.start()
        self._task_thread.start()

        self._apply_task_state(TaskState.IDLE)
        self.monitor.append_log("Application started (Phase 1 skeleton).", "INFO")
        self.monitor.append_log(f"Data root: {self._dirs['root']}", "INFO")
        self.monitor.append_log(f"Browser profile: {get_browser_profile_dir()}", "INFO")

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

        # Optional headless for CI / no-display smoke (visible by default)
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
        tw.finished_ok.connect(lambda: self._status.set_hint("任務完成"))
        tw.failed.connect(self._on_task_failed)

        # Queued slot invocations onto worker threads
        self._sig_open_browser = bw.open_browser
        self._sig_close_browser = bw.close_browser
        self._sig_cleanup_browser = bw.cleanup
        self._sig_run_task = tw.run_demo_task
        self._sig_stop_task = tw.request_stop

    # --- Browser ---

    @Slot()
    def _on_open_browser(self) -> None:
        self._status.set_hint("正在啟動瀏覽器…")
        self.act_open_browser.setEnabled(False)
        self.monitor.btn_open_browser.setEnabled(False)
        # Invoke on browser thread
        from PySide6.QtCore import QMetaObject, Qt as QtCoreQt

        QMetaObject.invokeMethod(
            self._browser_thread.worker,
            "open_browser",
            QtCoreQt.ConnectionType.QueuedConnection,
        )

    @Slot()
    def _on_close_browser(self) -> None:
        self._status.set_hint("正在關閉瀏覽器…")
        from PySide6.QtCore import QMetaObject, Qt as QtCoreQt

        QMetaObject.invokeMethod(
            self._browser_thread.worker,
            "close_browser",
            QtCoreQt.ConnectionType.QueuedConnection,
        )

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
        ready = status == "READY"
        self.act_open_browser.setEnabled(status in {"CLOSED", "ERROR"})
        self.act_close_browser.setEnabled(ready or status == "ERROR")

    # --- Task ---

    @Slot()
    def _on_start_task(self) -> None:
        if not self._task_state.can_start:
            return
        from PySide6.QtCore import QMetaObject, Qt as QtCoreQt

        QMetaObject.invokeMethod(
            self._task_thread.worker,
            "run_demo_task",
            QtCoreQt.ConnectionType.QueuedConnection,
        )

    @Slot()
    def _on_stop_task(self) -> None:
        if not self._task_state.can_stop:
            return
        from PySide6.QtCore import QMetaObject, Qt as QtCoreQt

        QMetaObject.invokeMethod(
            self._task_thread.worker,
            "request_stop",
            QtCoreQt.ConnectionType.QueuedConnection,
        )

    @Slot()
    def _on_refresh(self) -> None:
        self.monitor.append_log("Refresh requested (stub).", "INFO")
        self._status.set_hint("已重新整理（骨架）")

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

    @Slot(int, int)
    def _on_task_progress(self, current: int, total: int) -> None:
        self.monitor.set_counts(posts=current)
        self._status.set_hint(f"進度 {current}/{total}")

    @Slot(str)
    def _on_task_failed(self, message: str) -> None:
        QMessageBox.warning(self, "任務失敗", message)

    # --- Misc ---

    @Slot()
    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "匯入貼文（JSON / CSV stub）",
            str(Path.cwd()),
            "Import (*.json *.csv)",
        )
        if not path:
            return
        self.monitor.append_log(f"Import selected: {path} (architecture stub)", "INFO")
        try:
            from crawler.post_source import create_import_source

            source = create_import_source(path)
            self.monitor.append_log(
                f"PostSource ready: {type(source).__name__} — full import in Phase 2",
                "INFO",
            )
            self.monitor.posts_view.setPlainText(
                f"已選擇匯入來源：{path}\n"
                f"介面：{type(source).__name__}\n"
                "Phase 1 僅建立架構；實際批次寫入 DB 於 Phase 2。"
            )
        except Exception as exc:  # noqa: BLE001
            self.monitor.append_log(f"Import stub error: {exc}", "ERROR")
            QMessageBox.warning(self, "匯入失敗", str(exc))

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
            "Phase 1：UI 骨架、可見 Chromium、任務狀態與日誌。\n"
            "不含 X 網頁自動化擷取。",
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        """Ensure Chromium is torn down on exit."""
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
        if self._browser_status == "READY" or self._browser_status == "STARTING":
            loop.exec()

        self._browser_thread.quit()
        self._task_thread.quit()
        self._browser_thread.wait(3000)
        self._task_thread.wait(3000)
        event.accept()
