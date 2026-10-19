"""Playwright Chromium lifecycle manager (visible browser, persistent profile).

Phase 1: open / close / status / cleanup only.
No X automation, no anti-detection, no credential logging.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from services.paths import ensure_data_dirs, get_browser_profile_dir

logger = logging.getLogger(__name__)


class BrowserStatus(str, Enum):
    CLOSED = "CLOSED"
    STARTING = "STARTING"
    READY = "READY"
    ERROR = "ERROR"
    CLOSING = "CLOSING"


@dataclass
class BrowserManager:
    """Owns Playwright async Chromium with a dedicated persistent profile."""

    profile_dir: Path | None = None
    headless: bool = False
    status: BrowserStatus = BrowserStatus.CLOSED
    last_error: str | None = None
    _playwright: Any = field(default=None, repr=False)
    _context: Any = field(default=None, repr=False)
    _page: Any = field(default=None, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    def __post_init__(self) -> None:
        if self.profile_dir is None:
            ensure_data_dirs()
            self.profile_dir = get_browser_profile_dir()
        else:
            self.profile_dir = Path(self.profile_dir)
        self.profile_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_open(self) -> bool:
        return self.status == BrowserStatus.READY and self._context is not None

    @property
    def page(self) -> Any:
        return self._page

    async def start(self) -> None:
        """Launch visible Chromium with a persistent user-data directory."""
        async with self._lock:
            if self.is_open:
                return
            self.status = BrowserStatus.STARTING
            self.last_error = None
            try:
                from playwright.async_api import async_playwright

                self._playwright = await async_playwright().start()
                self._context = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_dir),
                    headless=self.headless,
                    viewport={"width": 1280, "height": 800},
                    args=["--disable-dev-shm-usage"],
                )
                if self._context.pages:
                    self._page = self._context.pages[0]
                else:
                    self._page = await self._context.new_page()
                self.status = BrowserStatus.READY
                logger.info("Chromium started (profile=%s)", self.profile_dir)
            except Exception as exc:  # noqa: BLE001 — surface to UI, never crash host
                self.last_error = str(exc)
                self.status = BrowserStatus.ERROR
                logger.exception("Failed to start Chromium")
                await self._force_cleanup()
                raise

    async def stop(self) -> None:
        """Close browser and release Playwright resources."""
        async with self._lock:
            if self.status == BrowserStatus.CLOSED:
                return
            self.status = BrowserStatus.CLOSING
            await self._force_cleanup()
            self.status = BrowserStatus.CLOSED
            self.last_error = None
            logger.info("Chromium stopped")

    async def _force_cleanup(self) -> None:
        """Best-effort cleanup; swallow secondary errors."""
        for name, closer in (
            ("_context", self._safe_close_context),
            ("_playwright", self._safe_stop_playwright),
        ):
            try:
                await closer()
            except Exception:  # noqa: BLE001
                logger.exception("Cleanup error on %s", name)
            finally:
                setattr(self, name if name != "_playwright" else "_playwright", None)
        self._page = None
        self._context = None
        self._playwright = None

    async def _safe_close_context(self) -> None:
        if self._context is not None:
            await self._context.close()

    async def _safe_stop_playwright(self) -> None:
        if self._playwright is not None:
            await self._playwright.stop()

    async def navigate(self, url: str) -> None:
        """Optional helper for smoke checks — not used for X scraping in Phase 1."""
        if not self.is_open or self._page is None:
            raise RuntimeError("Browser is not ready")
        await self._page.goto(url, wait_until="domcontentloaded")
