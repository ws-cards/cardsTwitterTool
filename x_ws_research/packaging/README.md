# 打包說明（PyInstaller onedir）

## 原則

| 項目 | 處理 |
|------|------|
| 執行檔 | `--onedir` → `dist/x_ws_research/` |
| DB／圖片／exports／logs | **使用者資料目錄**（Windows: `%LOCALAPPDATA%\x_ws_research`） |
| browser_profile | 同上；**禁止**打進發布物 |
| Playwright Chromium | 使用者快取另行 `playwright install`；**不**打包進 onedir |
| 認證／cookies | 從不寫入應用日誌；從不進入 git／dist |

## Windows（主要目標）

```bat
cd x_ws_research
packaging\build_windows.bat
```

驗證步驟見 [WINDOWS_CHECKLIST.md](WINDOWS_CHECKLIST.md)。

## Linux（可選煙測）

```bash
cd x_ws_research
bash packaging/build_linux.sh
```

Linux VM 可驗證「能產出 dist」；**可見 Chromium／Windows 實機行為以清單為準，本環境不宣稱已驗證。**

## 執行期環境變數

| 變數 | 用途 |
|------|------|
| `X_WS_DATA_ROOT` | 覆寫資料根目錄 |
| `X_WS_BROWSER_HEADLESS=1` | 無頭瀏覽器（測試） |
| `PLAYWRIGHT_BROWSERS_PATH` | Playwright 瀏覽器安裝位置（建議指向使用者目錄） |
