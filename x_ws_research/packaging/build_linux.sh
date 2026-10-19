#!/usr/bin/env bash
# Optional Linux onedir smoke (primary target is Windows).
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m pip install -r requirements.txt pyinstaller
rm -rf dist build
python3 -m PyInstaller packaging/x_ws_research.spec --noconfirm
echo "Build complete: dist/x_ws_research/"
echo "Note: GUI + Chromium still need a display / playwright browsers."
