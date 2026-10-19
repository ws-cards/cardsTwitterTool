"""QThread worker that drives BrowserManager via asyncio."""

from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot


class BrowserWorker(QObject):
    """Runs Playwright async API off the UI thread."""

    started_ok = Signal()
    stopped_ok = Signal()
    failed = Signal(str)
    status_changed = Signal(str)
    log_message = Signal(str, str)  # message, level

    def __init__(self, profile_dir: Path | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._profile_dir = profile_dir
        self._loop: asyncio.AbstractEventLoop | None = None
        self._manager = None
        self._headless = False

    def set_headless(self, headless: bool) -> None:
        self._headless = headless

    @Slot()
    def open_browser(self) -> None:
        self._run_coro(self._open())

    @Slot()
    def close_browser(self) -> None:
        self._run_coro(self._close())

    @Slot()
    def cleanup(self) -> None:
        self._run_coro(self._close(silent=True))

    def _run_coro(self, coro) -> None:
        try:
            if self._loop is None or self._loop.is_closed():
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(coro)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            self.log_message.emit(f"Browser error: {exc}", "ERROR")

    async def _ensure_manager(self):
        if self._manager is None:
            from crawler.browser_manager import BrowserManager

            self._manager = BrowserManager(
                profile_dir=self._profile_dir,
                headless=self._headless,
            )
        return self._manager

    async def _open(self) -> None:
        self.status_changed.emit("STARTING")
        self.log_message.emit("Starting Chromium…", "INFO")
        manager = await self._ensure_manager()
        manager.headless = self._headless
        await manager.start()
        self.status_changed.emit(manager.status.value)
        self.started_ok.emit()
        self.log_message.emit("Chromium ready (persistent profile).", "INFO")

    async def _close(self, silent: bool = False) -> None:
        if self._manager is None:
            self.status_changed.emit("CLOSED")
            self.stopped_ok.emit()
            return
        self.status_changed.emit("CLOSING")
        if not silent:
            self.log_message.emit("Closing Chromium…", "INFO")
        await self._manager.stop()
        self.status_changed.emit(self._manager.status.value)
        self.stopped_ok.emit()
        if not silent:
            self.log_message.emit("Chromium closed.", "INFO")


class BrowserThread(QThread):
    """Dedicated thread owning a BrowserWorker event loop affinity."""

    def __init__(self, profile_dir: Path | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.worker = BrowserWorker(profile_dir=profile_dir)
        self.worker.moveToThread(self)
