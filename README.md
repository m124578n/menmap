# menmap — 雙北拉麵地圖 🍜

雙北 **591 家拉麵店**的互動地圖:營業狀態、營業時間、評分評論、菜單照片、店家公告,
外加一顆「今天吃哪間」的拉麵骰子。資料每日自動採集,前後端部署 Cloudflare(規劃中),
爬蟲跑在家裡。

> 目前狀態:本地開發完成(P0 前端 + P1 詳情 API),尚未部署。
> 進度與計畫見 [docs/roadmap.md](docs/roadmap.md)。

## 功能

- 🗺️ **全螢幕地圖**(MapLibre):標記依營業狀態上色、低 zoom 聚合;和風設計、深色模式
- 🔍 **搜尋與篩選**:店名搜尋;區域(縣市/行政區兩層)、**現在營業中**(對當下時刻
  精準判斷,含跨午夜時段)、**深夜營業**、評分門檻;列表隨地圖範圍同步
- 🎲 **拉麵骰子**:從目前篩選結果隨機選一間(選了區域就從該區骰,不選就全部)
- 📋 **店家詳情**:營業時間(今日標記)、評分與評論數、電話/網站/**粉專**、
  **店家公告與活動貼文**、**菜單照片**、最新評論(全文+照片)、評分趨勢
- 🆕 **新店雷達**:seed 新收錄 30 天內標 NEW(初始批次不標)
- 🔗 **分享連結**:`#ftid` deep link 直達單店

## 架構(摘要)

```
[家裡 Windows]                    [Cloudflare(規劃)]         [使用者]
爬蟲(每日排程)                    R2  shops.json/照片/圖磚
 static + playwright  ─publish──▶  D1  shop/snapshot/review/post
 → SQLite                          ▲              │
                                   Pages(前端) ─▶ Workers(Hono API)
```

- **爬蟲留在家**是刻意決策:住宅 IP,避開資料中心 IP 被 Google 降級/封鎖
- 讀寫分離:地圖/列表走靜態 `shops.json`(現階段過渡),單店詳情走 Worker + D1
- 不用付費 API、不需任何金鑰,預期月費 $0

細節見 [docs/architecture.md](docs/architecture.md)、設計規格 [docs/design.md](docs/design.md)。

## Monorepo 佈局

```
ramen/       採集(Python):雙後端爬蟲、parser、SQLite、diff
web/         前端(Vite + React + MapLibre)→ Pages     [web/README.md]
worker/      詳情 API(Hono + D1)→ Workers            [worker/README.md]
scripts/     seed/快照匯出、每日排程、模板重錄
docs/        architecture / design / roadmap
data/        seed.json、ramen.db、每日 raw/diff/compare(進 git 保留歷史)
```

## 快速開始

需求:Python 3.14 + [uv](https://docs.astral.sh/uv/)、Node 20+。

```bash
# 1) 採集端
uv sync && uv run playwright install chromium
uv run python -m ramen seed                        # 建 seed(只跑一次,已入庫可跳過)
uv run python -m ramen snapshot --backend static   # 每日快照(--limit N 可限量)
uv run python -m ramen snapshot --backend playwright
uv run python -m ramen compare                     # 兩後端對比報告

# 2) 匯出前端資料 + 本地 D1
uv run python scripts/export_web_data.py           # → web/public/shops.json
cd worker && npm install && npm run db:init && npm run db:seed

# 3) 啟動(兩個都要開)
cd worker && npm run dev     # API  http://localhost:8787
cd web && npm install && npm run dev   # 前端 http://localhost:5173(/api 已 proxy)
```

Windows 終端 log 亂碼:`$env:PYTHONUTF8=1`。

## 每日排程(Windows,採集機)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1   # 註冊,每天 06:00
Start-ScheduledTask -TaskName RamenDailySnapshot                     # 立即測試
```

`run_daily.ps1`:兩後端快照 → compare → git commit/push `data/`。log 在 `data/logs/`(不進 git)。

## 採集端備忘

| 後端 | 方式 | 特性 |
|---|---|---|
| `static` | requests 直打 Google Maps 內部 XHR | 快;精簡欄位穩定(狀態/當日時間/評分),完整版會被同 IP 大量請求**軟性降級** |
| `playwright` | 無頭 Chromium 攔截頁面自發 XHR | 較慢;穩定拿**完整版**(評論數/整週時間/評論/菜單照/貼文) |

- 兩後端共用 `ramen/parser.py`(欄位索引集中於 `IDX_*`,Google 改版對照 `data/raw/` 修)
- 節流:請求間隨機延遲 + 定期長休息,`RAMEN_SLEEP_MIN/MAX`、`RAMEN_LONG_PAUSE_*`、
  `RAMEN_LITE_RETRIES` 環境變數可調;出現失敗/大量精簡版就調慢
- static 的 URL 模板失效時重錄:`uv run python scripts/capture_templates.py`
- parser 加新欄位後不用重爬:`uv run python scripts/reparse_raw.py [date] [backend]`

> ⚠️ **合規與風險**:直接抓 Google 地圖違反其 ToS,實務風險是被降級/封鎖(非帳單)。
> 已加節流與退避;長期穩定性靠每日排程持續驗證。FB/IG 粉專**只記連結、不爬內容**
> (見 roadmap)。

## 觀察清單(驗證期)

1. 每日成功率:snapshot 摘要行 + `data/diff/{date}-{backend}.md` 失敗清單
2. 被降級/擋:`data/raw/` 檔案大小(正常數十~數百 KB;普遍 1~3KB = 被降級)
3. 完整版比例:`data/compare/{date}.md` 的 `is_rich` 列
4. diff 變動合理性:特別留意 ⚠️ `CLOSED_*`

## 若日後改用 Places API (New)(本版未使用)

啟用 Places API (New)(非 legacy)→ API key 限制只能用該 API → Quotas 設每日上限
(如 500/天)防暴衝 → key 走環境變數 `GOOGLE_PLACES_API_KEY`(`.env` 已 gitignore)。
注意:每日快照欄位屬 Enterprise SKU(免費 1,000 次/月),無法零成本長跑——
這正是本專案改走爬蟲的原因。
