# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller --onedir spec for x_ws_research (Windows primary).

NEVER bundle:
  - browser_profile / cookies / credentials
  - user SQLite databases
  - personal images / exports
  - Playwright browser binaries (install separately into user cache)

Build (from x_ws_research/):
  pyinstaller packaging/x_ws_research.spec
"""

from __future__ import annotations

import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH).resolve().parent  # x_ws_research/

a = Analysis(
    [str(ROOT / "run_app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "PySide6",
        "sqlalchemy",
        "pydantic",
        "playwright",
        "playwright.async_api",
        "PIL",
        "cv2",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Keep release slim; optional heavy stacks not required at runtime for Phase 4
        "tkinter",
        "matplotlib",
        "numpy.tests",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Explicitly drop any accidental data that looks like user runtime dirs
a.datas = [
    d
    for d in a.datas
    if not any(
        part in str(d[0]).replace("\\", "/").lower()
        for part in (
            "browser_profile",
            "/db/",
            "\\db\\",
            "/images/",
            "\\images\\",
            "credentials",
            "cookie",
        )
    )
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="x_ws_research",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="x_ws_research",
)
