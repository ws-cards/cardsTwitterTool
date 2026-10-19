"""Resolve runtime data directories (user data preferred, project data/ fallback)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_data_root() -> Path:
    """Prefer a user-writable data root; fall back to project ``data/``."""
    override = os.environ.get("X_WS_DATA_ROOT")
    if override:
        return Path(override).expanduser().resolve()

    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return (base / "x_ws_research").resolve()

    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return (Path(xdg) / "x_ws_research").resolve()
    return (Path.home() / ".local" / "share" / "x_ws_research").resolve()


def get_browser_profile_dir() -> Path:
    """Persistent Chromium profile — never the user's daily Chrome profile."""
    return get_data_root() / "browser_profile"


def ensure_data_dirs() -> dict[str, Path]:
    root = get_data_root()
    dirs = {
        "root": root,
        "browser_profile": root / "browser_profile",
        "db": root / "db",
        "images": root / "images",
        "exports": root / "exports",
        "logs": root / "logs",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs
