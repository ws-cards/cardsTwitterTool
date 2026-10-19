# X 貼文蒐集 × Weiss Schwarz 牌組工具

個人研究用途的桌面應用：蒐集 X 貼文、篩選關鍵字、辨識 Weiss Schwarz 牌組圖片並匯出。

**目前進度：Phase 2（資料匯入）** — JSON/CSV 匯入、關鍵字篩選、SQLite、去重、預覽。

## 需求

- Python 3.12+
- PySide6、Playwright、Pydantic、SQLAlchemy、Pillow
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
PYTHONPATH=. python3 -m app.main
```

Linux 無顯示環境：

```bash
xvfb-run -a PYTHONPATH=. python3 -m app.main
```

資料目錄預設為 `~/.local/share/x_ws_research/`（可用 `X_WS_DATA_ROOT` 覆寫）。圖片以 SHA-256 存於 `images/`，**不會**把二進位寫入 SQLite。

## 匯入格式（Phase 2）

JSON 範例：

```json
{
  "posts": [
    {
      "source_id": "123",
      "author_handle": "alice",
      "text": "Weiss Schwarz deck",
      "created_at": "2024-01-01T12:00:00+00:00",
      "image_paths": ["relative/or/absolute.png"],
      "image_urls": ["https://example.com/optional-url.jpg"]
    }
  ]
}
```

CSV 欄位：`source_id,author_handle,text,created_at,url,image_urls,image_paths`（多值以 `|` 分隔）。遠端 URL 僅記錄、不下載。

## 測試

```bash
cd x_ws_research
xvfb-run -a env PYTHONPATH=. QT_QPA_PLATFORM=offscreen pytest -q
```

測試**不依賴**真實 X 帳號。

## 目錄

```
x_ws_research/
  app/          # PySide6 UI、QThread
  crawler/      # BrowserManager、PostSource
  services/     # 匯入、關鍵字、圖片、路徑、日誌
  schemas/      # Pydantic / TaskState
  storage/      # SQLite / SQLAlchemy
  vision/       # 辨識介面 stub（Phase 3）
  tests/
  data/         # 本機執行資料（gitignore）
```

## 階段規劃

| Phase | 內容 |
|-------|------|
| 1 | UI 骨架、可見 Chromium、狀態、日誌 |
| 2 | JSON/CSV 匯入、篩選、SQLite、去重、預覽 |
| 3 | 影像辨識介面與校正匯出 |
| 4 | 整合、測試、PyInstaller、手冊 |

## 合規

- 禁止 X 網頁自動化擷取、反偵測、CAPTCHA 破解
- 合規匯入為 Phase 2 資料來源
- 日誌不寫入認證資料
