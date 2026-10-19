"""Right-hand monitor: browser status, logs, post preview."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.log_buffer import LogBuffer
from storage.repository import PostPreview


class MonitorPanel(QWidget):
    open_browser_requested = Signal()
    close_browser_requested = Signal()
    open_output_requested = Signal()

    def __init__(self, log_buffer: LogBuffer | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log_buffer = log_buffer or LogBuffer(max_entries=500)
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)

        summary = QHBoxLayout()
        self.lbl_browser = QLabel("瀏覽器: CLOSED")
        self.lbl_task = QLabel("任務: IDLE")
        self.lbl_account = QLabel("處理中帳號: —")
        self.lbl_counts = QLabel("貼文 0｜圖片 0｜辨識 0｜錯誤 0")
        for w in (self.lbl_browser, self.lbl_task, self.lbl_account, self.lbl_counts):
            summary.addWidget(w)
        summary.addStretch(1)
        root.addLayout(summary)

        browser_row = QHBoxLayout()
        self.btn_open_browser = QPushButton("開啟瀏覽器")
        self.btn_close_browser = QPushButton("關閉瀏覽器")
        self.btn_open_output = QPushButton("開啟輸出資料夾")
        self.btn_close_browser.setEnabled(False)
        self.btn_open_browser.clicked.connect(self.open_browser_requested.emit)
        self.btn_close_browser.clicked.connect(self.close_browser_requested.emit)
        self.btn_open_output.clicked.connect(self.open_output_requested.emit)
        browser_row.addWidget(self.btn_open_browser)
        browser_row.addWidget(self.btn_close_browser)
        browser_row.addWidget(self.btn_open_output)
        browser_row.addStretch(1)
        root.addLayout(browser_row)

        self.tabs = QTabWidget()
        self.browser_status_view = QPlainTextEdit()
        self.browser_status_view.setReadOnly(True)
        self.browser_status_view.setPlainText(
            "Playwright Chromium（可見視窗，與主程式分離）。\n"
            "首次請在瀏覽器中自行登入；本程式不會記錄認證資料。\n"
            "貼文資料請使用合規 JSON/CSV／本機圖片匯入（Phase 2）。"
        )
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)

        self.posts_tree = QTreeWidget()
        self.posts_tree.setHeaderLabels(
            ["來源 ID", "帳號", "文字預覽", "圖片數", "時間", "網址"]
        )
        self.posts_tree.setColumnWidth(0, 100)
        self.posts_tree.setColumnWidth(1, 100)
        self.posts_tree.setColumnWidth(2, 320)
        self.posts_tree.setRootIsDecorated(True)

        # Keep plain-text alias for older tests / fallback
        self.posts_view = QPlainTextEdit()
        self.posts_view.setReadOnly(True)
        self.posts_view.setPlaceholderText("貼文結果文字預覽")

        posts_tab = QWidget()
        posts_layout = QVBoxLayout(posts_tab)
        posts_layout.setContentsMargins(0, 0, 0, 0)
        posts_layout.addWidget(self.posts_tree, stretch=3)
        posts_layout.addWidget(self.posts_view, stretch=1)

        self.vision_view = QPlainTextEdit()
        self.vision_view.setReadOnly(True)
        self.vision_view.setPlaceholderText("圖片辨識結果（Phase 3）")
        self.errors_view = QPlainTextEdit()
        self.errors_view.setReadOnly(True)
        self.errors_view.setPlaceholderText("錯誤紀錄")

        self.tabs.addTab(self.browser_status_view, "瀏覽器狀態")
        self.tabs.addTab(self.log_view, "執行日誌")
        self.tabs.addTab(posts_tab, "貼文結果")
        self.tabs.addTab(self.vision_view, "圖片辨識結果")
        self.tabs.addTab(self.errors_view, "錯誤紀錄")
        root.addWidget(self.tabs, stretch=1)

    def set_browser_status(self, status: str) -> None:
        self.lbl_browser.setText(f"瀏覽器: {status}")
        ready = status == "READY"
        starting = status == "STARTING"
        closing = status == "CLOSING"
        self.btn_open_browser.setEnabled(not ready and not starting and not closing)
        self.btn_close_browser.setEnabled(ready or status == "ERROR")
        self.browser_status_view.appendPlainText(f"狀態 → {status}")

    def set_task_state(self, state: str) -> None:
        self.lbl_task.setText(f"任務: {state}")

    def set_counts(self, posts: int = 0, images: int = 0, vision: int = 0, errors: int = 0) -> None:
        self.lbl_counts.setText(f"貼文 {posts}｜圖片 {images}｜辨識 {vision}｜錯誤 {errors}")

    def append_log(self, message: str, level: str = "INFO") -> None:
        entry = self.log_buffer.append(message, level=level)
        self.log_view.setPlainText("\n".join(self.log_buffer.lines()))
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())
        if level.upper() == "ERROR":
            self.errors_view.appendPlainText(entry.format())

    def show_post_previews(self, previews: list[PostPreview]) -> None:
        self.posts_tree.clear()
        lines: list[str] = []
        for preview in previews:
            text_preview = preview.text.replace("\n", " ")
            if len(text_preview) > 80:
                text_preview = text_preview[:77] + "…"
            created = preview.created_at.isoformat() if preview.created_at else ""
            item = QTreeWidgetItem(
                [
                    preview.source_id,
                    f"@{preview.author_handle}",
                    text_preview,
                    str(preview.image_count),
                    created,
                    preview.url or "",
                ]
            )
            for path in preview.image_paths:
                child = QTreeWidgetItem(["", "", path, "", "", ""])
                item.addChild(child)
            self.posts_tree.addTopLevelItem(item)
            lines.append(
                f"[{preview.source_id}] @{preview.author_handle} "
                f"({preview.image_count} img)\n{preview.text}\n"
            )
        self.posts_view.setPlainText("\n".join(lines) if lines else "（尚無貼文）")
        self.tabs.setCurrentIndex(2)
