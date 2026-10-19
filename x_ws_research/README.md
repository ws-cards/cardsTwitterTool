# X 貼文蒐集 × Weiss Schwarz 牌組工具

個人研究用途的桌面應用：蒐集 X 貼文、篩選關鍵字、辨識 Weiss Schwarz 牌組圖片並匯出。

**目前進度：Phase 1（骨架）** — UI、可見 Chromium、任務狀態、日誌、PostSource 介面。

## 需求

- Python 3.12+
- PySide6、Playwright、Pydantic、SQLAlchemy
- Playwright Chromium（`playwright install chromium`）

## 安裝

```bash
cd x_ws_research
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## 啟動

```bash
cd x_ws_research
PYTHONPATH=. python -m app.main
```

Linux 無顯示環境可使用：

```bash
xvfb-run -a PYTHONPATH=. python -m app.main
```

無頭瀏覽器煙測（可選）：

```bash
X_WS_BROWSER_HEADLESS=1 PYTHONPATH=. python -m app.main
```

資料目錄預設為使用者資料夾（Linux: `~/.local/share/x_ws_research/`），可用環境變數 `X_WS_DATA_ROOT` 覆寫。瀏覽器 profile 獨立存放，**不會**使用日常 Chrome 設定檔。

## 測試

```bash
cd x_ws_research
PYTHONPATH=. pytest -q
```

GUI 測試在無顯示環境：

```bash
xvfb-run -a PYTHONPATH=. pytest -q
```

測試**不依賴**真實 X 帳號或網路擷取。

## 目錄

```
x_ws_research/
  app/          # PySide6 UI、QThread
  crawler/      # BrowserManager、PostSource
  services/     # 路徑、日誌緩衝
  schemas/      # Pydantic / TaskState
  storage/      # SQLite 骨架
  vision/       # 辨識介面 stub
  tests/
  data/         # 本機執行資料（gitignore）
```

## 階段規劃

| Phase | 內容 |
|-------|------|
| 1 | UI 骨架、可見 Chromium、狀態、日誌、匯入介面 |
| 2 | JSON/CSV 匯入、篩選、SQLite、去重、預覽 |
| 3 | 影像辨識介面與校正匯出 |
| 4 | 整合、測試、PyInstaller、手冊 |

## 合規

- 禁止 X 網頁自動化擷取、反偵測、CAPTCHA 破解
- 首次由使用者在可見瀏覽器中自行登入
- 日誌不寫入認證資料
