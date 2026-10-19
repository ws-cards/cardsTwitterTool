"""Bottom status bar."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QStatusBar


class AppStatusBar(QStatusBar):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._task = QLabel("任務: IDLE")
        self._browser = QLabel("瀏覽器: CLOSED")
        self._hint = QLabel("就緒")
        self.addWidget(self._task, 1)
        self.addPermanentWidget(self._browser)
        self.addPermanentWidget(self._hint)

    def set_task_state(self, state: str) -> None:
        self._task.setText(f"任務: {state}")

    def set_browser_status(self, status: str) -> None:
        self._browser.setText(f"瀏覽器: {status}")

    def set_hint(self, text: str) -> None:
        self._hint.setText(text)
