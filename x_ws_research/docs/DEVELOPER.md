# 開發指引

## 結構

```
x_ws_research/
  app/           # PySide6 UI、QThread
  crawler/       # BrowserManager、PostSource
  services/      # 匯入、辨識、卡表、路徑、日誌
  vision/        # 可替換辨識介面與啟發式實作
  storage/       # SQLAlchemy / SQLite
  schemas/       # Pydantic、TaskState
  packaging/     # PyInstaller
  tests/
  docs/
```

## 技術鎖定

Python 3.12+、PySide6、Playwright Async、asyncio、QThread、SQLite／SQLAlchemy、Pydantic、Pillow、OpenCV。勿擅自換 UI／瀏覽器框架。

## 執行與測試

```bash
cd x_ws_research
pip install -r requirements.txt
playwright install chromium
PYTHONPATH=. python -m app.main

# 測試（無真實 X）
xvfb-run -a env PYTHONPATH=. QT_QPA_PLATFORM=offscreen pytest -q
```

## 不變式

- UI **不直接寫** DB；長任務走 `TaskWorker` + Signals
- 執行資料在 `get_data_root()`（使用者目錄），打包後亦然
- `browser_profile` 永不進 git／dist
- 禁止 X 自動化擷取、反偵測、CAPTCHA 破解
- 辨識引擎可替換；測試用 Mock／合成圖／sidecar

## 階段

| Phase | 內容 |
|-------|------|
| 1 | UI／Chromium／狀態／日誌 |
| 2 | 匯入／篩選／SQLite／去重 |
| 3 | 辨識介面／校正／匯出 |
| 4 | 整合／測試／打包／手冊 |
