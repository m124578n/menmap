# menmap 架構

雙北拉麵地圖。資料採集在家跑(住宅 IP),前後端全部部署到 Cloudflare 免費方案。

## 全貌

```
   [家裡 Windows]                         [Cloudflare 邊緣]              [使用者]

  Task Scheduler ─每天 06:00
      │
      ▼
  ramen 爬蟲 (Playwright/requests)
  → 本地 SQLite (data/ramen.db)
      │
      │  publish 步驟(outbound HTTPS,scoped token;家裡不開任何 port)
      ▼
  ┌──────────────────────────────────────────────┐
  │  R2   ← shops.json / 店家照片 / 地圖圖磚 pmtiles │
  │  D1   ← shop / snapshot / review(供詳情與趨勢) │
  └──────────────────────────────────────────────┘
      ▲                                   │
      │ 讀 shops.json                     │ 查單店詳情/歷史
  ┌───────────────┐                ┌───────────────┐
  │ Pages (前端)  │ ── /api/... ─▶ │ Workers (Hono)│
  │ MapLibre 地圖 │ ◀── JSON ───── │  綁 D1 + R2   │
  └───────────────┘                └───────────────┘
      ▲
      └────────── 瀏覽器載入 ──────────────────────────────  使用者
```

## 為什麼爬蟲留在家

Cloudflare 有 Browser Rendering(雲端 Puppeteer)可跑爬蟲,但它是**資料中心 IP**——正是
會被 Google Maps 降級/擋的來源(見採集階段驗證)。住宅 IP 留在家是刻意的架構決策,
不是限制。家裡對雲端**只做 outbound push**,不暴露任何 inbound endpoint。

## 元件與職責

| 元件 | 技術 | 職責 | 免費額度 |
|---|---|---|---|
| 前端 | Cloudflare **Pages** + Vite + React + MapLibre | 地圖、篩選、詳情面板 | 靜態請求無限 |
| 地圖圖磚 | **Protomaps `.pmtiles` 存 R2** + MapLibre | 向量地圖,零每次載入費 | R2 免費 |
| 列表資料 | **R2** 上的 `shops.json` | 617 家精簡欄位,前端載一次做 client 端篩選 | R2 免費 |
| API | Cloudflare **Workers** + Hono | `/api/shop/:ftid` 回詳情+評論+歷史 | 10 萬 req/天 |
| 資料庫 | **D1**(SQLite) | shop / snapshot / review;沿用採集端 schema | 5GB、讀 500 萬列/天 |
| 照片 | **R2** | 封面/菜色圖 | 10GB、零 egress |
| 採集 | 家裡 Python(現有) | 每日快照 → publish | — |

規模(617 家、每日更新、讀多寫少)全部落在免費額度內,預期月費 **$0**。

## 資料分層(hybrid)

- **地圖與列表**走 `shops.json`(靜態、client 端篩選)——617 家約 1~2MB,瀏覽器載一次就够,
  地圖上的點不打後端。
- **單店詳情/評論/歷史趨勢**走 D1——點進單店才呼叫 `/api/shop/:ftid`,回完整欄位、最新評論、
  近期 rating/營業狀態變化。
- 使用者端全**唯讀**,無登入。D1 只有家裡的 publish 在寫。

### `shops.json` 欄位(前端契約)

```jsonc
{
  "generated_at": "2026-09-03T06:12:00+08:00",
  "shops": [
    {
      "ftid": "0x...:0x...",
      "name": "麵屋武藏-神山",
      "lat": 25.05, "lng": 121.53,
      "city": "台北市", "district": "中山區",
      "types": ["拉麵店", "日本餐廳"],
      "status": "OPERATIONAL",        // 最新快照;無資料為 null
      "rating": 4.3,
      "rating_count": 4724,
      "price": "$200–400",
      "cover": "https://.../cover.jpg" // R2 或原始連結;可為 null
    }
  ]
}
```

### D1 serving schema

沿用採集端 `ramen/db.py` 的 `shop` / `snapshot` / `review` 三表。API 讀取:

- `GET /api/shop/:ftid` → `shop` 一列 + 最新 `snapshot` + 最近 N 筆 `snapshot`(畫趨勢)
  + `review` 全部(最新一次抓到的評論)。

## 家裡 → 雲的 publish(接縫)

`scripts/run_daily.ps1` 爬完後新增 publish 步驟(全 outbound):

1. 從本地 SQLite 算當前狀態 → 產 `shops.json` → **R2 put**
2. 當天有變動的 shop/snapshot/review 列 → POST 到 **ingest Worker**(帶 bearer secret,
   Worker 端寫 D1)。用 ingest Worker 而非直接發 D1 REST:家裡只拿一把 secret、
   碰不到 D1 結構,權限更收斂。
3. 新店封面照下載 → **R2 put**

寫入量:617 ×(1 shop + 1 snapshot + ~5 review)≈ 4k 列/天,遠低於 D1 免費 10 萬列/天。

Token:R2:Edit(限單一 bucket)、ingest Worker bearer secret,存在家裡 `.env`(已 gitignore)。

## Repo 佈局(monorepo)

```
menmap/
  ramen/     scripts/          # 採集(家裡)+ 匯出/發布腳本
  web/                         # 前端 → Pages(Vite + React + MapLibre)
    public/shops.json          #（開發期)由 scripts/export_web_data.py 產生
  worker/                      # API → Workers(Hono,綁 D1 + R2)
  docs/architecture.md
```

## 建置階段

| 階段 | 內容 | 部署 |
|---|---|---|
| **P0** | `web/` 地圖 SPA,MapLibre + OpenFreeMap 免費圖磚,載入本地匯出的 `shops.json`,617 家點上地圖 + 篩選/搜尋/詳情面板 | 本地 dev(先不部署) |
| **P1** ✅ | `worker/` Hono + D1;本地 D1 匯入 SQLite;`/api/shop/:ftid` 回營業時間/評論/照片/歷史,詳情面板接上 | 本地 wrangler dev |
| **P2** | 家裡 publish 步驟(R2 + ingest Worker)每日自動 | 上 Cloudflare |
| **P3** | 圖磚換自架 pmtiles(擺脫外部依賴);照片進 R2 | 上 Cloudflare |

目前進度:**P0 + P1 本地開發完成,尚未部署。**
本地開發需同時啟動兩個服務:`cd worker && npm run dev`(API,:8787)與
`cd web && npm run dev`(前端,:5173,已設 `/api` proxy 到 :8787)。
本地 D1 資料由 `scripts/export_d1_seed.py` + `worker` 的 `npm run db:init && db:seed` 從
`data/ramen.db` 匯入。

## 技術選型備註

- **前端框架 Vite + React**:MapLibre 生態成熟、範例多。
- **地圖 MapLibre + 開源圖磚**:避開 Google Maps JS 的按載入計費,維持零成本;
  P0 先用 OpenFreeMap(免 key),P3 換成自架 pmtiles 去除外部依賴。
- **API 用 Hono**:Cloudflare Workers 上最輕量慣用的路由框架。
- **D1 = SQLite**:採集端就是 SQLite,schema 幾乎直接搬,無需 ORM 轉換。
