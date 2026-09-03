# menmap web(前端)

雙北拉麵地圖前端。Vite + React + MapLibre。設計見 `../docs/design.md`,
架構見 `../docs/architecture.md`。目前為 **P0**(本地開發,尚未部署)。

## 開發

```bash
# 先從採集端資料匯出前端用的 shops.json(在專案根目錄)
uv run python scripts/export_web_data.py

cd web
npm install
npm run dev        # http://localhost:5173
```

`web/public/shops.json` 由 `scripts/export_web_data.py` 從 `data/ramen.db` + `data/seed.json`
產生(617 家的座標/區域/評分/狀態)。P2 起改由家裡 publish 步驟上傳 R2。

## 目前功能(P0)

- 全螢幕 MapLibre 地圖(CARTO positron/dark 底圖),617 家聚合標記,依營業狀態上色
- 名稱搜尋、區域(多選)/營業中/評分篩選
- 桌機左側列表抽屜、手機底部 sheet;列表隨地圖可視範圍同步
- 點選單店 → 詳情面板(基本資料 + Google Maps 連結)
- 深/淺色主題(記憶於 localStorage)

詳情面板的營業時間、評論、照片、評分趨勢來自 `worker`(P1,`/api/shop/:ftid`)。
開發時需**同時啟動** worker:`cd ../worker && npm run dev`(:8787);本前端已設
`/api` proxy 過去。worker 未啟動時,詳情面板會優雅顯示「詳情 API 無法連線」並保留
基本資料。

## 部署(Cloudflare Pages)

- 正式站 **<https://menmap.shunzz.com>**(Pages 專案 `menmap`,備援 `menmap.pages.dev`)。
- `npm run deploy`:`npm run build` 後用 wrangler(裝在 `../worker`)直接上傳 `dist`。
  上傳前記得先 `uv run python ../scripts/export_web_data.py` 更新 `public/shops.json`。
- API 走同網域的 `/api/*` 路由到 Worker(見 `../worker/wrangler.toml`),所以正式建置
  **不設** `VITE_API_BASE`。只有在別的網域(例如直接開 `menmap.pages.dev`)才需要設成
  Worker 網址 `https://menmap-api.m23568n.workers.dev`。本機開發留空走 Vite proxy。
- `index.html` 的 canonical / og:url / og:image 已是 `https://menmap.shunzz.com`;換網域要改。
- `public/_headers`:Pages 的快取規則(`/assets/*` 長快取、`shops.json` 5~10 分鐘)。
- SEO/分享資產都在 `public/`:`favicon.svg`、`apple-touch-icon.png`、`og.png`(1200×630)、
  `manifest.webmanifest`、`robots.txt`。
- 限制:單頁 hash 路由(`#ftid`),搜尋引擎只會索引首頁;單店 OG 分享卡(per-shop
  og:image / 標題)要另做預渲染或 Worker 動態產生,見 roadmap。

## 待辦

- **P3**:地圖底圖換自架 Protomaps pmtiles;評論/封面照快取進 R2(googleusercontent
  熱連結會間歇失效,目前破圖自動隱藏)

## 結構

```
src/
  App.tsx                 # 狀態整合(搜尋/篩選/選取/主題)
  components/
    MapView.tsx           # MapLibre + 聚合 + 狀態上色 + 選取高亮
    FilterChips.tsx  ShopList.tsx  DetailPanel.tsx  StatusBadge.tsx
  hooks/  useShops.ts  useTheme.ts
  lib/  format.ts         # 狀態標籤/顏色、星等、數字格式
  styles/  tokens.css  app.css   # 和風設計 tokens
```
