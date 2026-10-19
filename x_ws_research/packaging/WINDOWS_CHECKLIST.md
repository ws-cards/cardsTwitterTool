# Windows 打包後驗證清單（實機）

> **本倉庫 CI／Linux VM 未在 Windows 實機執行下列檢查。**  
> 請在目標 Windows 機器依序勾選。

## 建置前

- [ ] Python 3.12+ 已安裝
- [ ] `pip install -r requirements.txt pyinstaller`
- [ ] 工作目錄為 `x_ws_research/`
- [ ] 確認本機沒有把 `browser_profile`、`*.sqlite`、個人圖片複製進 `packaging/`

## 建置

```bat
packaging\build_windows.bat
```

- [ ] 產出 `dist\x_ws_research\x_ws_research.exe`
- [ ] `dist` 內**沒有** `browser_profile`、使用者 DB、個人 `images`、cookies

## Playwright Chromium（與程式分離）

瀏覽器 binary **不**打進 onedir。建議：

```bat
set PLAYWRIGHT_BROWSERS_PATH=%LOCALAPPDATA%\x_ws_research\ms-playwright
python -m playwright install chromium
```

- [ ] Chromium 安裝成功
- [ ] 路徑在使用者目錄，非 `Program Files`

## 啟動與資料目錄

- [ ] 雙擊 `x_ws_research.exe` 可開主視窗
- [ ] 日誌顯示資料根目錄為 `%LOCALAPPDATA%\x_ws_research\`（或 `X_WS_DATA_ROOT`）
- [ ] 安裝目錄（`dist\...`）在執行後**沒有**新建 `browser_profile` / `db`（應寫入使用者目錄）

## 瀏覽器

- [ ] 「開啟瀏覽器」可啟動可見 Chromium
- [ ] 首次可手動登入（若需要）；程式日誌**無**密碼／cookie
- [ ] 「關閉瀏覽器」後工作管理員無殘留多餘 chromium 程序
- [ ] 結束主程式後無殘留 chromium／playwright 程序

## 任務與 UI

- [ ] JSON／CSV 匯入成功，貼文預覽更新
- [ ] 匯入進行中按「停止」可取消，按鈕恢復可點
- [ ] 執行辨識（啟發式）錯誤時 UI 不崩潰，錯誤出現在日誌／錯誤分頁
- [ ] 長時間操作後日誌分頁仍可用（有筆數上限）
- [ ] 匯出牌組 CSV 寫入 `%LOCALAPPDATA%\x_ws_research\exports\` 或使用者選擇路徑

## 合規

- [ ] 發布 zip **不含**登入狀態／profile／DB／個人圖
- [ ] 未使用日常 Chrome 使用者設定檔
