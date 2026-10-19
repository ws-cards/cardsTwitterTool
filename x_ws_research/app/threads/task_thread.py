"""Background task worker — Phase 1 simulates lifecycle without X scraping."""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QThread, Signal, Slot

from schemas.task_state import TaskState


class TaskWorker(QObject):
    """Emits task state transitions and log lines for UI wiring tests."""

    state_changed = Signal(str)
    log_message = Signal(str, str)
    progress = Signal(int, int)  # current, total
    finished_ok = Signal()
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._stop_requested = False

    @Slot()
    def request_stop(self) -> None:
        self._stop_requested = True
        self.log_message.emit("Stop requested…", "WARN")

    @Slot()
    def run_demo_task(self) -> None:
        """Phase 1 stub: walk through states without touching X."""
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

    def _set_state(self, state: TaskState) -> None:
        self.state_changed.emit(state.value)


class TaskThread(QThread):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.worker = TaskWorker()
        self.worker.moveToThread(self)
