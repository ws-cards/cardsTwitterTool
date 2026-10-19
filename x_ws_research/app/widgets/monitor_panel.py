"""Right-hand monitor: browser, logs, posts, recognition + correction."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.log_buffer import LogBuffer
from storage.repository import DeckPreview, PostPreview, RecognitionPreview


class MonitorPanel(QWidget):
    open_browser_requested = Signal()
    close_browser_requested = Signal()
    open_output_requested = Signal()
    correction_requested = Signal(object)  # dict payload

    def __init__(self, log_buffer: LogBuffer | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log_buffer = log_buffer or LogBuffer(max_entries=500)
        self._selected_deck_card_id: int | None = None
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
            "Phase 3 使用啟發式／可替換辨識管線；不宣稱 YOLO 已達標。"
        )
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)

        self.posts_tree = QTreeWidget()
        self.posts_tree.setHeaderLabels(
            ["來源 ID", "帳號", "文字預覽", "圖片數", "時間", "網址"]
        )
        self.posts_tree.setColumnWidth(2, 320)
        self.posts_view = QPlainTextEdit()
        self.posts_view.setReadOnly(True)
        posts_tab = QWidget()
        posts_layout = QVBoxLayout(posts_tab)
        posts_layout.setContentsMargins(0, 0, 0, 0)
        posts_layout.addWidget(self.posts_tree, stretch=3)
        posts_layout.addWidget(self.posts_view, stretch=1)

        # Recognition + correction tab
        vision_tab = QWidget()
        vision_layout = QVBoxLayout(vision_tab)
        self.decks_tree = QTreeWidget()
        self.decks_tree.setHeaderLabels(
            ["牌組 / 卡號", "數量", "名稱", "確認", "deck_card_id"]
        )
        self.decks_tree.setColumnHidden(4, True)
        self.decks_tree.itemSelectionChanged.connect(self._on_deck_selection)
        vision_layout.addWidget(self.decks_tree, stretch=3)

        correct = QFormLayout()
        self.edit_card_number = QLineEdit()
        self.edit_card_number.setPlaceholderText("例如 ABC/S123-001")
        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 99)
        self.chk_confirmed = QCheckBox("已確認")
        self.edit_note = QLineEdit()
        self.edit_note.setPlaceholderText("修正備註（寫入 correction_log）")
        self.btn_apply_correction = QPushButton("套用校正")
        self.btn_apply_correction.clicked.connect(self._emit_correction)
        correct.addRow("卡號", self.edit_card_number)
        correct.addRow("數量", self.spin_qty)
        correct.addRow(self.chk_confirmed)
        correct.addRow("備註", self.edit_note)
        correct.addRow(self.btn_apply_correction)
        vision_layout.addLayout(correct)

        self.vision_view = QPlainTextEdit()
        self.vision_view.setReadOnly(True)
        self.vision_view.setPlaceholderText("辨識明細")
        vision_layout.addWidget(self.vision_view, stretch=1)

        self.errors_view = QPlainTextEdit()
        self.errors_view.setReadOnly(True)

        self.tabs.addTab(self.browser_status_view, "瀏覽器狀態")
        self.tabs.addTab(self.log_view, "執行日誌")
        self.tabs.addTab(posts_tab, "貼文結果")
        self.tabs.addTab(vision_tab, "圖片辨識結果")
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
                item.addChild(QTreeWidgetItem(["", "", path, "", "", ""]))
            self.posts_tree.addTopLevelItem(item)
            lines.append(
                f"[{preview.source_id}] @{preview.author_handle} "
                f"({preview.image_count} img)\n{preview.text}\n"
            )
        self.posts_view.setPlainText("\n".join(lines) if lines else "（尚無貼文）")

    def show_decks(self, decks: list[DeckPreview]) -> None:
        self.decks_tree.clear()
        for deck in decks:
            parent = QTreeWidgetItem(
                [
                    f"#{deck.id} {deck.name}",
                    "",
                    deck.source_key,
                    deck.status,
                    "",
                ]
            )
            for card in deck.cards:
                child = QTreeWidgetItem(
                    [
                        card.card_number or "(未知)",
                        str(card.quantity),
                        card.card_name or "",
                        "Y" if card.confirmed else "N",
                        str(card.id),
                    ]
                )
                parent.addChild(child)
            parent.setExpanded(True)
            self.decks_tree.addTopLevelItem(parent)
        self.tabs.setCurrentIndex(3)

    def show_recognitions(self, items: list[RecognitionPreview]) -> None:
        lines = []
        for r in items[:200]:
            lines.append(
                f"#{r.id} img={r.post_image_id} deck={r.deck_id} "
                f"[{r.status}] {r.card_number or '-'} conf={r.confidence or '-'} "
                f"confirmed={r.confirmed}\n  {r.crop_path or ''}"
            )
        self.vision_view.setPlainText("\n".join(lines) if lines else "（尚無辨識結果）")

    def _on_deck_selection(self) -> None:
        items = self.decks_tree.selectedItems()
        if not items:
            self._selected_deck_card_id = None
            return
        item = items[0]
        raw_id = item.text(4)
        if not raw_id:
            self._selected_deck_card_id = None
            return
        self._selected_deck_card_id = int(raw_id)
        self.edit_card_number.setText(item.text(0) if item.text(0) != "(未知)" else "")
        try:
            self.spin_qty.setValue(int(item.text(1) or "1"))
        except ValueError:
            self.spin_qty.setValue(1)
        self.chk_confirmed.setChecked(item.text(3) == "Y")

    def _emit_correction(self) -> None:
        if self._selected_deck_card_id is None:
            return
        self.correction_requested.emit(
            {
                "deck_card_id": self._selected_deck_card_id,
                "card_number": self.edit_card_number.text().strip() or None,
                "quantity": self.spin_qty.value(),
                "confirmed": self.chk_confirmed.isChecked(),
                "note": self.edit_note.text().strip(),
            }
        )
