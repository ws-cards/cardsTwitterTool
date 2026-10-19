"""Application entry point (dev + PyInstaller)."""

from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path


def _ensure_sys_path() -> None:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _configure_logging() -> None:
    from services.paths import ensure_data_dirs

    dirs = ensure_data_dirs()
    log_file = dirs["logs"] / "app.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


def main() -> int:
    _ensure_sys_path()
    try:
        _configure_logging()
    except Exception:  # noqa: BLE001
        logging.basicConfig(level=logging.INFO)

    from PySide6.QtWidgets import QApplication, QMessageBox

    from app.main_window import MainWindow
    from services.paths import ensure_data_dirs, get_data_root

    try:
        ensure_data_dirs()
        app = QApplication(sys.argv)
        app.setApplicationName("x_ws_research")
        app.setOrganizationName("x_ws_research")
        window = MainWindow()
        window.show()
        return app.exec()
    except Exception as exc:  # noqa: BLE001 — last-resort UI safety net
        logging.exception("Fatal startup error")
        try:
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(
                None,
                "啟動失敗",
                f"應用程式無法啟動。\n\n{exc}\n\n"
                f"資料目錄：{get_data_root()}\n"
                f"詳見 logs/app.log",
            )
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
