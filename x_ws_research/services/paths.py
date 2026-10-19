"""Resolve runtime data directories — always user-writable, never install dir."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """True when running from PyInstaller (or similar) bundle."""
    return bool(getattr(sys, "frozen", False)) or hasattr(sys, "_MEIPASS")


def get_bundle_root() -> Path:
    """Read-only resources root (PyInstaller ``_MEIPASS`` or project root)."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


def get_project_root() -> Path:
    """Source tree root when developing; bundle dir when frozen."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def get_data_root() -> Path:
    """User-writable data root — never assume the install directory is writable."""
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
    """Persistent Chromium profile under user data — never daily Chrome profile."""
    return get_data_root() / "browser_profile"


def get_crops_dir() -> Path:
    return get_data_root() / "crops"


def ensure_data_dirs() -> dict[str, Path]:
    root = get_data_root()
    dirs = {
        "root": root,
        "browser_profile": root / "browser_profile",
        "db": root / "db",
        "images": root / "images",
        "exports": root / "exports",
        "logs": root / "logs",
        "crops": root / "crops",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def assert_not_install_dir(path: Path) -> None:
    """Raise if a writable path would land inside a frozen install tree."""
    if not is_frozen():
        return
    install = Path(sys.executable).resolve().parent
    resolved = path.resolve()
    try:
        resolved.relative_to(install)
    except ValueError:
        return
    # Allow only if explicitly overridden (tests)
    if os.environ.get("X_WS_ALLOW_INSTALL_WRITE") == "1":
        return
    raise RuntimeError(
        f"Refusing to use install directory for writable data: {resolved}. "
        "Set X_WS_DATA_ROOT or use the default user data folder."
    )
