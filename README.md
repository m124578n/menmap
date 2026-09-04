# menmap — 雙北拉麵地圖 🍜

雙北 **591 家拉麵店**的互動地圖:營業狀態、營業時間、評分評論、菜單照片、店家公告,
外加一顆「今天吃哪間」的拉麵骰子。資料每日自動採集,前後端部署 Cloudflare,
爬蟲跑在家裡。

> **正式站:<https://menmap.shunzz.com>**(Pages + Workers + D1,2026-09-03 上線)。
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
- 🏆 **麵榜**:熱門(評分 × 評論數貝氏平均)、竄紅(近 7 天評論數增幅)、入門友善
  (評論多、評分穩、價格親民)三個榜 + **本週動態**(新收錄、歇業/恢復、評分變動、
  營業時間調整、改名搬家);資料每天由 `export_web_data.py` 產成 `discover.json`
- 🖼️ **圖片燈箱**、💲 **價格篩選**、ⓘ **關於本站**(資料來源與免責)

## 架構(摘要)

```
[家裡 Windows,每天 20:00]                 [Cloudflare]                      [使用者]
爬蟲 static + playwright ─▶ SQLite(正本)   menmap.shunzz.com
        │                                   ├─ Pages   前端 + shops.json  ◀── 地圖/列表
        ├─ publish_d1.py 當天增量 ─────────▶ D1       shop/snapshot/review/post
        └─ export_web_data.py + deploy ───▶ Pages     └─ /api/* ─▶ Worker(Hono)◀── 單店詳情
```

- **爬蟲留在家**是刻意決策:住宅 IP,避開資料中心 IP 被 Google 降級/封鎖
- **本機 SQLite 是正本,雲端是複本**:每天排程尾端把當天變動推上去(見「部署」)
- 讀寫分離:地圖/列表走靜態 `shops.json`(隨 Pages 部署),單店詳情走同網域 `/api/*` → Worker + D1
- 不用付費 API、不需任何金鑰,Cloudflare 免費方案內,月費 $0

細節見 [docs/architecture.md](docs/architecture.md)、設計規格 [docs/design.md](docs/design.md)。

## Monorepo 佈局

```
ramen/       採集(Python):雙後端爬蟲、parser、SQLite、diff
web/         前端(Vite + React + MapLibre)→ Pages     [web/README.md]
worker/      詳情 API(Hono + D1)→ Workers            [worker/README.md]
scripts/     每日排程(run_daily/register_task)、publish(publish_d1/export_web_data)、
             本地 D1 seed、模板重錄、raw 重解析
docs/        architecture / design / roadmap
data/        seed.json、ramen.db、每日 raw/diff/compare(進 git 保留歷史);logs/ 不進 git
```

## 快速開始

需求:Python 3.14 + [uv](https://docs.astral.sh/uv/)、Node 20+。

```bash
# 1) 採集端
uv sync && uv run playwright install chromium
uv run python -m ramen seed                        # 建 seed(只跑一次,已入庫可跳過)
uv run python -m ramen seed --refresh              # 重新搜尋並合併(新店/改名/搬家;排程每週日跑)
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
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1   # 註冊,每天 20:00
Start-ScheduledTask -TaskName RamenDailySnapshot                     # 立即測試
```

`run_daily.ps1`:**兩後端同時**快照(static 全抓 591 家、playwright 每天輪 100 家)→ compare
→ **publish 上線**(D1 當天增量 + Pages 重新部署)→ git commit/push `data/` 與 `shops.json`。
log 在 `data/logs/`(不進 git):`{date}.log` 主流程、`{date}-static.log` /
`{date}-playwright.log` 各後端逐店輸出。跑的期間會擋住閒置睡眠,結束後解除。

- 實測 static 每家約 6 秒(全抓約 50 分鐘)、playwright 每家約 8 秒(100 家約 15 分鐘),
  含請求間 2.5~5 秒隨機延遲、每 15 家長休 8~15 秒;兩後端各自節流、並行跑,
  整趟約 50 分鐘(排程上限 4 小時)。DB 走 WAL + 逐店 commit,所以能同時寫。
- 用量用環境變數調:`SNAPSHOT_LIMIT_STATIC`(預設空 = 全抓)、`SNAPSHOT_LIMIT_PLAYWRIGHT`
  (預設 100)。設了 N 就會**輪替**:優先抓從沒被該後端抓過的店,其次最久沒抓的,
  每天跑同樣的數字會自動輪完整個 seed(100 家約 6 天一輪)。被降級/失敗變多時調小。
- diff 是每家店跟**自己上一次**成功快照比(不是跟上一個批次比),輪抓時才有東西可比。
  也會列出**改名/搬家**(主檔覆蓋前偵測,記在 `shop_change` 表)。
- **新店與更替**:每週日快照前跑 `ramen seed --refresh`,重新搜尋所有關鍵字並**合併**進 seed:
  新 ftid 追加並記 `added_at`(前端「新店雷達」30 天內標 NEW)、既有店更新名稱/地址/座標、
  搜不到的不刪只累計 `missed`;不符現行過濾規則的(含既有)會移除並列在報告。
  報告在 `data/diff/{date}-seed.md`。`$env:SEED_REFRESH="1"` 可當天強制跑;搜尋命中不到
  seed 一半時視為被擋,不動 seed。永久停業的店留在 seed,由每日快照的狀態反映。
- 過濾規則(`ramen/seed.py` 的 `looks_like_ramen`):類別是「拉麵店」就收;否則名稱要有
  拉麵訊號且不是咖哩/丼飯/烏龍麵等副品項店;只有「日本餐廳」類別的不收(會混進定食、壽司連鎖)。
  Google 搜尋結果每次都會浮動(實測同關鍵字前後兩天差 40~50 家),所以 seed 要靠累積。

## 部署(Cloudflare)

| 元件 | 位置 | 指令 |
|---|---|---|
| 前端 | Pages 專案 `menmap` → `menmap.shunzz.com`(備援 `menmap.pages.dev`),**已接 GitHub** | `git push` 到 main 自動建置(root `web`、`npm run build`、`dist`;只在 `web/**` 變動時建);`cd web && npm run deploy` 為手動備援 |
| API | Worker `menmap-api`,路由 `menmap.shunzz.com/api/*`(備援 `menmap-api.m23568n.workers.dev`) | `cd worker && npm run deploy` |
| 資料 | D1 `menmap`(APAC) | `cd worker && npm run db:publish`(當天增量);`db:push` 整顆重灌(只在 schema 重建時用) |

- 前端與 API 同源,不需要 CORS 或 `VITE_API_BASE`;本機開發仍走 Vite proxy。
- **線上資料每天自動更新**:`run_daily.ps1` 抓完、compare 完後跑 publish——
  `scripts/publish_d1.py` 只匯出當天新增/取代的列(冪等,同天重跑不會重複)推到 D1,
  再 `export_web_data.py` 重產 shops.json,連同 data/ commit、push;Pages 收到 push 自己建置。
  手動測試不想推 D1 時設 `$env:PUBLISH="0"`。
- Web Analytics 已在 Pages 專案啟用(Dashboard → menmap → Metrics),beacon 由 Pages 自動注入。
- Pages 建置設定(API 設過,Dashboard 也看得到):只在 `web/*` 變動時建、不做 preview 分支、
  build caching 開啟、建置環境變數 `PYTHON_VERSION=3.13.3`(build image 會讀根目錄的
  `.python-version` 3.14 而從原始碼編 Python,指到預裝版本省 2 分鐘)。首次建置約 10 分鐘,
  之後有 cache 應該快很多。
- publish 只推「當天日期」的列;某天沒跑或推失敗,要手動補:
  `uv run python scripts/publish_d1.py --date YYYY-MM-DD`,再到 `worker/` 執行
  `npx wrangler d1 execute menmap --remote --file=./publish.local.sql -y`。
- 自訂網域的 DNS(CNAME `menmap` → `menmap.pages.dev`)在 Dashboard 管理;
  wrangler 用 `npx wrangler login` 登入的帳號要有 Pages/Workers/D1 權限(採集機已登入)。

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
