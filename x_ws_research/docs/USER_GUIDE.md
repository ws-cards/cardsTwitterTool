# 使用者操作手冊

## 這是什麼

個人研究用桌面工具：以**合規匯入**（JSON／CSV／本機圖片）整理 X 貼文與 Weiss Schwarz 牌組辨識結果，並可校正、匯出 CSV。

**不會**自動登入或擷取 X 網頁；可見瀏覽器僅供你自行操作／登入（若需要）。

## 安裝（開發／原始碼）

1. 安裝 Python 3.12+
2. `cd x_ws_research && pip install -r requirements.txt`
3. `playwright install chromium`
4. `PYTHONPATH=. python -m app.main`

Windows 打包版見 `packaging/WINDOWS_CHECKLIST.md`。

## 資料存在哪

預設（請勿依賴安裝目錄可寫）：

- Windows：`%LOCALAPPDATA%\x_ws_research\`
- Linux：`~/.local/share/x_ws_research\`

可用環境變數 `X_WS_DATA_ROOT` 覆寫。內含 `db/`、`images/`、`browser_profile/`、`exports/`、`logs/`、`crops/`。

## 建議流程

1. **匯入卡表**（選用）：CSV／JSON，欄位含 `card_number`、`name`
2. **匯入貼文**：JSON／CSV；本機圖片用 `image_paths`（相對匯入檔路徑）
3. 左側可設**關鍵字**（OR／AND）再匯入
4. **執行辨識**：啟發式裁切／OCR stub（可替換；不保證辨識率）
5. 在「圖片辨識結果」分頁**校正**卡號／數量並確認
6. **匯出牌組 CSV**

## 貼文 JSON 範例

```json
{
  "posts": [
    {
      "source_id": "123",
      "author_handle": "alice",
      "text": "Weiss deck",
      "image_paths": ["photos/deck1.png"]
    }
  ]
}
```

可選 sidecar：`deck1.png.cards.json` 描述裁切區域與 `hint_text` 卡號（測試／輔助用）。

## 注意

- 日誌不會記錄密碼或 cookie
- 辨識為可替換管線；未宣稱 YOLO／商業 OCR 已達標
- 發布資料夾不應含你的登入狀態或個人 DB
