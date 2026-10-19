"""Application entry point."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_sys_path() -> None:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def main() -> int:
    _ensure_sys_path()

    from PySide6.QtWidgets import QApplication

    from app.main_window import MainWindow
    from services.paths import ensure_data_dirs

    ensure_data_dirs()
    app = QApplication(sys.argv)
    app.setApplicationName("x_ws_research")
    app.setOrganizationName("x_ws_research")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
