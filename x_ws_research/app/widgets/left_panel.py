"""Left settings panel — keywords & import controls for Phase 2."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from schemas.models import KeywordConfig
from services.keyword_filter import parse_keyword_list


class LeftSettingsPanel(QWidget):
    """Account / keyword / filter / task / settings management."""

    start_requested = Signal()
    stop_requested = Signal()
    refresh_requested = Signal()
    import_requested = Signal(str)
    catalog_import_requested = Signal()
    recognize_requested = Signal()
    export_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)

        accounts = QGroupBox("帳號管理")
        acc_layout = QVBoxLayout(accounts)
        self.account_list = QListWidget()
        self.account_list.addItem("@example_user  (stub)")
        acc_btns = QHBoxLayout()
        self.btn_add_account = QPushButton("新增")
        self.btn_edit_account = QPushButton("編輯")
        self.btn_remove_account = QPushButton("移除")
        for b in (self.btn_add_account, self.btn_edit_account, self.btn_remove_account):
            b.setEnabled(False)
            acc_btns.addWidget(b)
        self.chk_account_enabled = QCheckBox("啟用選取帳號")
        self.chk_account_enabled.setChecked(True)
        acc_layout.addWidget(self.account_list)
        acc_layout.addLayout(acc_btns)
        acc_layout.addWidget(self.chk_account_enabled)
        root.addWidget(accounts)

        keywords = QGroupBox("關鍵字設定")
        kw_form = QFormLayout(keywords)
        self.keyword_edit = QLineEdit()
        self.keyword_edit.setPlaceholderText("逗號分隔，例如：Weiss, デッキ")
        self.match_mode = QComboBox()
        self.match_mode.addItem("任一符合 (OR / any)", "any")
        self.match_mode.addItem("全部符合 (AND / all)", "all")
        self.chk_case = QCheckBox("區分大小寫")
        self.chk_normalize_ws = QCheckBox("正規化空白")
        self.chk_normalize_ws.setChecked(True)
        kw_form.addRow("關鍵字", self.keyword_edit)
        kw_form.addRow("符合模式", self.match_mode)
        kw_form.addRow(self.chk_case)
        kw_form.addRow(self.chk_normalize_ws)
        root.addWidget(keywords)

        filters = QGroupBox("貼文篩選")
        f_form = QFormLayout(filters)
        self.date_from = QLineEdit()
        self.date_from.setPlaceholderText("YYYY-MM-DD")
        self.date_to = QLineEdit()
        self.date_to.setPlaceholderText("YYYY-MM-DD")
        self.filter_processed = QComboBox()
        self.filter_processed.addItems(["全部", "未處理", "已處理"])
        self.filter_images = QComboBox()
        self.filter_images.addItems(["全部", "僅含圖片", "不含圖片"])
        self.filter_recognition = QComboBox()
        self.filter_recognition.addItems(["全部", "未辨識", "已辨識", "失敗"])
        f_form.addRow("日期起", self.date_from)
        f_form.addRow("日期迄", self.date_to)
        f_form.addRow("處理狀態", self.filter_processed)
        f_form.addRow("圖片", self.filter_images)
        f_form.addRow("辨識狀態", self.filter_recognition)
        root.addWidget(filters)

        task = QGroupBox("任務設定")
        t_form = QFormLayout(task)
        self.max_posts = QSpinBox()
        self.max_posts.setRange(1, 10_000)
        self.max_posts.setValue(500)
        self.chk_download_images = QCheckBox("下載遠端圖片")
        self.chk_download_images.setChecked(False)
        self.chk_download_images.setEnabled(False)  # Phase 2: local images only
        self.chk_recognition = QCheckBox("辨識任務就緒（啟發式／可替換）")
        self.chk_recognition.setChecked(True)
        self.output_dir = QLineEdit("data/exports")
        t_form.addRow("最大筆數", self.max_posts)
        t_form.addRow(self.chk_download_images)
        t_form.addRow(self.chk_recognition)
        t_form.addRow("輸出資料夾", self.output_dir)

        task_btns = QHBoxLayout()
        self.btn_start = QPushButton("開始匯入")
        self.btn_stop = QPushButton("停止")
        self.btn_refresh = QPushButton("重新整理")
        self.btn_recognize = QPushButton("執行辨識")
        self.btn_stop.setEnabled(False)
        self.btn_start.clicked.connect(self.start_requested.emit)
        self.btn_stop.clicked.connect(self.stop_requested.emit)
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        self.btn_recognize.clicked.connect(self.recognize_requested.emit)
        task_btns.addWidget(self.btn_start)
        task_btns.addWidget(self.btn_stop)
        task_btns.addWidget(self.btn_refresh)
        t_form.addRow(task_btns)
        t_form.addRow(self.btn_recognize)
        root.addWidget(task)

        settings = QGroupBox("設定／匯入匯出")
        s_layout = QHBoxLayout(settings)
        self.btn_save_settings = QPushButton("儲存")
        self.btn_load_settings = QPushButton("載入")
        self.btn_reset_settings = QPushButton("恢復預設")
        self.btn_import = QPushButton("貼文 JSON/CSV…")
        self.btn_catalog = QPushButton("卡表…")
        self.btn_export = QPushButton("匯出牌組 CSV…")
        for b in (self.btn_save_settings, self.btn_load_settings, self.btn_reset_settings):
            b.setEnabled(False)
            s_layout.addWidget(b)
        self.btn_import.clicked.connect(lambda: self.import_requested.emit(""))
        self.btn_catalog.clicked.connect(self.catalog_import_requested.emit)
        self.btn_export.clicked.connect(self.export_requested.emit)
        s_layout.addWidget(self.btn_import)
        s_layout.addWidget(self.btn_catalog)
        s_layout.addWidget(self.btn_export)
        root.addWidget(settings)

        root.addWidget(QLabel("Phase 3：啟發式辨識、卡表、人工校正與 CSV 匯出。"))
        root.addStretch(1)

    def keyword_config(self) -> KeywordConfig:
        mode = self.match_mode.currentData()
        if mode not in {"any", "all"}:
            mode = "any"
        return KeywordConfig(
            keywords=parse_keyword_list(self.keyword_edit.text()),
            match_mode=mode,
            case_sensitive=self.chk_case.isChecked(),
            normalize_whitespace=self.chk_normalize_ws.isChecked(),
        )

    def apply_task_state(self, state_name: str) -> None:
        from schemas.task_state import TaskState

        state = TaskState(state_name)
        self.btn_start.setEnabled(state.can_start)
        self.btn_stop.setEnabled(state.can_stop)
        self.btn_refresh.setEnabled(not state.is_busy)
        self.btn_import.setEnabled(state.can_start)
        self.btn_catalog.setEnabled(state.can_start)
        self.btn_export.setEnabled(state.can_start)
        self.btn_recognize.setEnabled(state.can_start and self.chk_recognition.isChecked())
