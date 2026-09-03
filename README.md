# ramap — 雙北拉麵地圖資料採集(可行性驗證)

在正式開發拉麵地圖前,先驗證「能不能每天穩定、零成本地採集雙北拉麵店基本資料」。
這個階段**不做前端、不做地圖**,只做資料採集 pipeline 並連跑數天觀察結果。

## 這版用什麼方法

原本規劃用 Google Places API (New),但每日快照需要的欄位(營業時間、評分、
電話)全屬 **Enterprise SKU,免費額度僅 1,000 次/月**,無法零成本長跑
(seed 約 150 家的話 6~10 天就開始收費,一個月約 US$70~90)。

因此改為**直接抓 Google 地圖的內部資料端點**,並實作兩個後端做對比:

| 後端 | 方式 | 特性 |
|---|---|---|
| `static` | `requests` 直打 `/search?tbm=map` 與 `/maps/preview/place` 內部 XHR | 快、輕量;精簡欄位穩定,但「完整版」(評論數、整週營業時間、評論)會在同一 IP 大量請求後被**軟性降級** |
| `playwright` | 無頭 Chromium 開真實地圖頁,攔截頁面自發的 place XHR | 較慢;瀏覽器帶完整 session,**穩定拿到完整版**資料 |

兩後端輸出同一組欄位(`ramen/parser.py` 是唯一的欄位定義),`compare` 指令
每天量測兩者的覆蓋率與成功率——這就是「哪個方法比較可靠」的證據。

完整版回應還帶**最新約 5~8 則評論**(作者、星等、日期、全文、每則照片連結)與
**封面照**,存進 SQLite 的 `review` 表與 `shop.cover_photo`;每次抓到完整版就整批
取代該店評論(精簡版沒帶評論時保留舊的)。photos 連結即店家/菜色照片,可直接下載。

> ⚠️ **合規與風險**:直接抓 Google 地圖違反其服務條款,實務風險是**被封鎖**
> (CAPTCHA / 空回應 / 降級),不是帳單。程式已加 sleep、退避與禮貌性節流,
> 但這條路能否長期穩定正是本次要驗證的事。FB/IG 粉專不在範圍內。

## 專案結構

```
ramen/
  __main__.py        # CLI:seed / snapshot / compare
  parser.py          # Google Maps 內部 JSON 解析(欄位索引集中在此)
  static_backend.py  # requests 後端 + URL 模板參數化
  dynamic_backend.py # Playwright 後端
  templates.py       # 實錄的 XHR URL 模板(由 scripts/capture_templates.py 產生)
  net.py             # session / headers / sleep / 指數退避
  seed.py  snapshot.py  diff.py  compare.py  db.py  storage.py  schema.py
scripts/
  run_daily.ps1        # 每日:兩後端快照 + compare + git commit
  register_task.ps1    # 註冊 Windows 工作排程(每天 06:00)
  capture_templates.py # Google 改版導致 static 失效時,重錄 URL 模板
data/
  seed.json  ramen.db  raw/{date}/{backend}/  diff/  compare/
```

## 本機執行

需求:Python 3.14、[uv](https://docs.astral.sh/uv/)。

```bash
uv sync                          # 安裝依賴(requests + playwright)
uv run playwright install chromium

# 1) 建立 seed(只跑一次;之後人工維護)
uv run python -m ramen seed              # 產出 data/seed.json(雙北拉麵店)

# 2) 每日快照(兩個後端各跑一次)
uv run python -m ramen snapshot --backend static
uv run python -m ramen snapshot --backend playwright

# 3) 兩後端對比報告
uv run python -m ramen compare
```

Windows 終端若 log 出現亂碼,設 `$env:PYTHONUTF8=1`(排程腳本已內建)。

用量控制:`--limit N` 或環境變數 `SNAPSHOT_LIMIT=N` 只抓 seed 前 N 家,
驗證期建議設小(例如 60)以縮短時間、減少被降級機率。

### 節流(避免爬太快被擋)

每次請求後隨機延遲,並每隔幾家插入一段長休息,打散節奏。全部可用環境變數調整:

| 變數 | 預設 | 說明 |
|---|---|---|
| `RAMEN_SLEEP_MIN` / `RAMEN_SLEEP_MAX` | 2.5 / 5.0 | 每次請求後的隨機延遲(秒) |
| `RAMEN_LONG_PAUSE_EVERY` | 15 | 每處理幾家店插入一次長休息(0 = 關閉) |
| `RAMEN_LONG_PAUSE_MIN` / `RAMEN_LONG_PAUSE_MAX` | 20 / 45 | 長休息秒數範圍 |
| `RAMEN_LITE_RETRIES` | 2 | playwright 拿到精簡版時的重試次數(每次多等讓完整版 render) |

預設值下抓 60 家約需 5~10 分鐘。**若開始出現失敗或大量精簡版,把延遲調更長**、
或降低單日抓取家數。static 後端每店只發 1 次請求;playwright 每店 1 次(精簡版才重試)。

不用 uv 的環境:`pip install -r requirements.txt` 亦可(但仍需 `playwright install chromium`)。

## 排程(Windows 工作排程器)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1   # 註冊,每天 06:00
Start-ScheduledTask -TaskName RamenDailySnapshot                     # 立即測試一次
Unregister-ScheduledTask -TaskName RamenDailySnapshot -Confirm:$false # 移除
```

`run_daily.ps1` 會依序跑 static / playwright 快照、compare,然後以 `ramen-bot`
身分 `git commit` 整個 `data/`(快照、diff、compare、原始 JSON 都留在 git),
最後 `git push`。log 寫在 `data/logs/`(此目錄不進 git)。

> 選這條路是為了避開 GitHub Actions 的資料中心 IP——Google 對那類 IP 特別容易
> 觸發降級/封鎖。本機住宅 IP 穩定得多,代價是電腦要開著。

## 驗證期間要觀察什麼

連跑數天後,每天看這幾件事:

1. **每日成功率**:`snapshot` 最後一行 `{ok}/{total} ok, {failed} failed`,以及
   `data/diff/{date}-{backend}.md` 的「本次失敗」清單。失敗率飆高 = 開始被擋。
2. **有沒有被降級 / 擋**:翻 `data/raw/{date}/` 的原始 JSON;正常是大檔(數十~上百 KB),
   若普遍變成 1~3 KB 小檔、或出現 consent/captcha 字樣,代表被降級或擋了。
3. **完整版比例**:`data/compare/{date}.md` 的 `is_rich` 列。static 若長期偏低、
   playwright 也開始下降,表示這條路的穩定性有疑慮。
4. **diff 是否合理**:`data/diff/` 裡 business_status / 營業時間 / 評分變動,對照真實
   情況看有沒有假變動或漏抓。特別留意標記 ⚠️ 的 `CLOSED_TEMPORARILY / CLOSED_PERMANENTLY`。
5. **零成本確認**:這版**完全沒用付費 API,也不需要任何 API key**,不會有帳單。
   (若日後改回 Places API,才需要下面的 GCP 設定。)

## 若日後改用 Places API (New)(本版未使用)

保留給對照:要走官方 API 時,在 GCP 的步驟——

1. **啟用 API**:GCP Console → APIs & Services → 啟用 **Places API (New)**(不是 legacy Places API)。
2. **建立並限制 API key**:Credentials → 建立 API key → 編輯 →
   **API restrictions** 選「Restrict key」只勾 **Places API (New)**;
   **Application restrictions** 依用途設 IP 限制。
3. **設每日 quota 上限防帳單暴衝**:APIs & Services → Places API (New) → Quotas,
   把每日請求上限設為 **500 次/天**(擋暴衝,不保證零成本)。
4. key 從環境變數 `GOOGLE_PLACES_API_KEY` 讀,`.env` 已在 `.gitignore`。

## 維護

- Google 改版導致 `static` 整批失敗時,重錄 URL 模板:
  `uv run python scripts/capture_templates.py`
- 欄位索引都在 `ramen/parser.py` 最上方的 `IDX_*` 常數,對照 `data/raw/` 的實際
  回應調整即可。
