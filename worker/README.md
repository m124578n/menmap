# menmap worker(API)

詳情 API。Hono on Cloudflare Workers,綁 D1。架構見 `../docs/architecture.md`。
目前為 **P1**(本地 wrangler dev,尚未部署)。

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

## 部署前(P2)

1. `wrangler d1 create menmap` → 把回傳的 `database_id` 填進 `wrangler.toml`
2. `wrangler d1 execute menmap --remote --file=./schema.sql` 建遠端 schema
3. 資料改由家裡的 publish 步驟寫入(ingest Worker,見架構文件),不再用 `seed.local.sql`
4. `npm run deploy`

## 結構

```
src/index.ts     # Hono app + /api/shop/:ftid
schema.sql       # D1 schema(同 ramen/db.py)
wrangler.toml    # Worker 設定 + D1 綁定
```
