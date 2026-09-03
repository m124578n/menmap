# menmap worker(API)

詳情 API。Hono on Cloudflare Workers,綁 D1。架構見 `../docs/architecture.md`。
已部署:Worker `menmap-api`,正式路由 `menmap.shunzz.com/api/*`,
備援 `https://menmap-api.m23568n.workers.dev`;D1 `menmap`(APAC)。

## 端點

- `GET /api/health` → `{ ok: true }`
- `GET /api/shop/:ftid` → 單店詳情:
  - `shop`(名稱、地址、電話、網站、封面照)
  - `latest`:最新成功快照(營業狀態、營業時間、價位、評分、評論數)
  - `history`:近 30 筆快照(評分/評論數/狀態趨勢)
  - `reviews`:最新一次抓到的評論(作者、星等、日期、全文、照片)
  - 找不到 → `404 { found: false }`

## 本地開發

```bash
npm install

# 從採集端 data/ramen.db 匯入本地 D1(開發用)
uv run python ../scripts/export_d1_seed.py   # 在專案根目錄跑亦可
npm run db:init      # 建 schema(本地 D1)
npm run db:seed      # 載入 seed.local.sql

npm run dev          # wrangler dev,http://localhost:8787
```

前端(`../web`)dev server 已設 `/api` proxy 到 `:8787`,兩邊都啟動即可。

## 部署

```bash
npm run deploy             # wrangler deploy(路由與 D1 綁定都在 wrangler.toml)
npm run db:schema:remote   # 遠端 D1 建 schema(只有 schema 變動時需要)
npm run db:publish         # 當天增量:scripts/publish_d1.py → publish.local.sql → 遠端 D1(每日排程用,冪等)
npm run db:push            # 整顆重灌:export_d1_seed.py → seed.local.sql(先 DELETE 再 INSERT,只在重建時用)
```

- `wrangler.toml` 的 `routes` 把 `menmap.shunzz.com/api/*` 指到這個 Worker,和 Pages 前端同源。
- 本機 `data/ramen.db` 是正本,D1 是複本。`db:publish` 的規則:shop 整列覆蓋、snapshot 依
  captured_at 先刪再插、review/post 比照採集端「某店某後端整批取代」。
  補推某天:`uv run python ../scripts/publish_d1.py --date 2026-09-02` 再手動 execute。

## 結構

```
src/index.ts     # Hono app + /api/shop/:ftid
schema.sql       # D1 schema(同 ramen/db.py)
wrangler.toml    # Worker 設定 + D1 綁定
```
