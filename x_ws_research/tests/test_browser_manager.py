"""BrowserManager tests — use headless Chromium; no X network required."""

from __future__ import annotations

import pytest

from crawler.browser_manager import BrowserManager, BrowserStatus


@pytest.mark.asyncio
async def test_browser_start_stop(data_root, tmp_path):
    profile = data_root / "browser_profile"
    manager = BrowserManager(profile_dir=profile, headless=True)
    assert manager.status == BrowserStatus.CLOSED
    try:
        await manager.start()
        assert manager.status == BrowserStatus.READY
        assert manager.is_open
        assert profile.is_dir()
        # about:blank — no external network dependency on X
        await manager.navigate("about:blank")
    finally:
        await manager.stop()
    assert manager.status == BrowserStatus.CLOSED
    assert not manager.is_open


@pytest.mark.asyncio
async def test_browser_double_start_is_safe(data_root):
    manager = BrowserManager(profile_dir=data_root / "browser_profile", headless=True)
    try:
        await manager.start()
        await manager.start()  # idempotent
        assert manager.status == BrowserStatus.READY
    finally:
        await manager.stop()
