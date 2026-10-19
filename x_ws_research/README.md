# X 貼文蒐集 × Weiss Schwarz 牌組工具

個人研究用途的桌面應用：合規匯入貼文與本機圖片、關鍵字篩選、啟發式牌組辨識、校正與 CSV 匯出。

**目前進度：Phase 4（整合與打包）**

## 需求

- Python 3.12+
- PySide6、Playwright、Pydantic、SQLAlchemy、Pillow、OpenCV（headless）
- Playwright Chromium（`playwright install chromium`）

## 安裝與啟動

```bash
cd x_ws_research
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
PYTHONPATH=. python3 -m app.main
```

文件：

- 使用者手冊：[docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- 開發指引：[docs/DEVELOPER.md](docs/DEVELOPER.md)
- Windows 打包：[packaging/README.md](packaging/README.md) · [驗證清單](packaging/WINDOWS_CHECKLIST.md)

## 資料目錄

執行時資料寫入**使用者目錄**（非安裝目錄）：

- Windows：`%LOCALAPPDATA%\x_ws_research\`
- Linux：`~/.local/share/x_ws_research\`
- 覆寫：`X_WS_DATA_ROOT`

含 `db/`、`images/`、`browser_profile/`、`exports/`、`logs/`、`crops/`。圖片以 SHA-256 落盤，不寫入 SQLite BLOB。

## 功能摘要

| 階段 | 內容 |
|------|------|
| 1 | UI、可見 Chromium、任務狀態、日誌 |
| 2 | JSON/CSV 匯入、關鍵字、SQLite、去重、預覽 |
| 3 | 可替換辨識管線、卡表、校正、CSV 匯出 |
| 4 | 清理強化、打包規格、手冊與驗證清單 |

辨識為啟發式／可替換引擎，**不宣稱** YOLO 已達標。

## 測試

```bash
cd x_ws_research
xvfb-run -a env PYTHONPATH=. QT_QPA_PLATFORM=offscreen pytest -q
```

測試**不依賴**真實 X 帳號。

## 打包（Windows onedir）

```bat
cd x_ws_research
packaging\build_windows.bat
```

發布物**不得**含 `browser_profile`、登入狀態、個人 DB／圖片。Playwright Chromium 另行安裝到使用者快取。詳見 `packaging/WINDOWS_CHECKLIST.md`（需 Windows 實機勾選）。

## 合規

- 禁止 X 網頁自動化擷取、反偵測、CAPTCHA 破解
- 日誌不寫入認證資料
- 不使用日常 Chrome 個人設定檔
