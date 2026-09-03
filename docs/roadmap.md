# menmap Roadmap

現況與待辦。階段代號沿用 `architecture.md`(P0 前端、P1 詳情 API、P2 部署、P3 收尾)。

## 現況(2026-09)

- ✅ 採集 pipeline(家裡):static / playwright 雙後端,617 家 seed(雙北、已過濾台式雜訊)
- ✅ P0 前端:MapLibre 地圖 + 篩選 + 詳情面板,和風設計,深色模式
- ✅ P1 詳情 API:Worker(Hono)+ D1,`/api/shop/:ftid` 回營業時間/評論/照片/趨勢
- 🔜 資料覆蓋:D1 目前約 30 家有完整詳情;static 全抽(617)進行中,補齊營業狀態與基本資料

## 待辦

### 拉麵種類分類(雞白湯/豚骨/醬油/家系…)— 延後用 LLM 處理

**決策**:等評論資料齊了,用 **LLM 一次性分類**(名稱 + 評論文字 → 主湯頭標籤,多標籤)。

**為什麼不用其他方法**(2026-09 實測,免得之後重查):

- **名稱關鍵字**:只有 **11%(66/617)** 能從店名分出來——多數店叫「麵屋武藏」「凪 Nagi」
  「一風堂」,不把湯頭寫在名字。精準但覆蓋太低。
- **Google 編輯描述(description 欄位)**:❌ 走不通。實測 place/search 回應的描述大多是
  None,有值也只是「供應拉麵和日式料理的當代餐廳」「早午餐」「可帶狗入住」這種籠統標籤,
  **從不提湯頭**。不值得為它加採集欄位。
- **評論關鍵字(naive)**:有評論的店 **100%** 命中,但**過度貼標**——一家店常被貼 5~6 種
  (評論會提到各種湯頭、客人比較),精準度差。
- ✅ **評論 + LLM**:評論提供原料(豚骨/雞白湯/湯頭…實測神山評論明確寫「魚介和豚骨雙湯頭」),
  LLM 判斷「這家主打什麼」並濾掉比較性雜訊,精準度最高。

**前置條件**:先讓 Playwright 把評論抓到足夠覆蓋(目前僅 ~30 家有評論;要靠每日排程或分批
補到大部分 617 家)。

**實作草案**:
1. 一次性腳本 `scripts/classify_types.py`:讀 D1/ramen.db 的 shop.name + review.text,
   對每家店呼叫 Claude(單次 batch,便宜),輸出多標籤 categories。
2. 分類結果寫回 shop 表(新增 `categories` 欄位,JSON 陣列)。
3. `export_web_data.py` 把 categories 帶進 `shops.json`。
4. 前端加「類型」篩選 chip(多選,多標籤;一家店可同時是豚骨+家系)。
5. 之後新店或評論更新時再增量重跑。

**備選**:LLM 之前想先有東西,可先上「名稱關鍵字 + 知名連鎖對照表(一風堂/屯京/一蘭→豚骨、
一幻→蝦、Nagi→煮干…)」的精準子集,標好明確的、其餘「未分類」,LLM 版上線後取代。

### P2 — 部署上 Cloudflare(家裡 publish 自動化)

- `wrangler d1 create menmap` → 遠端 D1;schema 上遠端
- 家裡 `run_daily.ps1` 加 publish 步驟:`shops.json` → R2、變動列 → ingest Worker 寫遠端 D1、
  新店封面照 → R2(scoped token,全 outbound)
- 前端 Pages、API Workers 部署

### P3 — 收尾

- 地圖底圖換自架 **Protomaps pmtiles**(存 R2,去除 CARTO 外部依賴)
- **照片快取進 R2**:googleusercontent 熱連結會間歇失效(目前破圖自動隱藏、顯示時放大解析度),
  改成採集時下載封面/評論照存 R2,穩定且可控
- 評分/營業狀態的歷史趨勢視覺化強化

### P4 — 使用者功能(登入 / 最愛 / 造訪紀錄 / 等候回報)

把 app 從唯讀變成有帳號、有寫入的產品。需要認證、per-user 資料、群眾共享資料,
以及寫入端的濫用防護。全部仍可 Cloudflare-native、零成本。

#### 4.0 認證(前置,其餘功能都依賴)

- **做法**:Worker 自己處理 OAuth(建議 **LINE Login**——台灣用戶普及;或 Google),
  callback 驗證後簽發 **HttpOnly 簽章 session cookie(JWT,Worker secret 簽)**,
  不靠外部 auth 服務,維持零成本。
- D1 `user` 表:`id, provider, provider_id, display_name, avatar_url, created_at`。
- 所有寫入端點驗 session;加基本 rate limit 與濫用防護。
- **備選**:Clerk / Supabase Auth(程式少但外部依賴、可能超出免費圈)——與零成本原則衝突,
  預設自建。
- **待定**:登入提供者(LINE / Google / 兩者)。

#### 4.1 我的最愛

- D1 `favorite(user_id, ftid, created_at)`。
- API:`POST/DELETE /api/favorites/:ftid`、`GET /api/favorites`。
- 前端:卡片/詳情的愛心 toggle;「我的最愛」篩選或分頁。

#### 4.2 造訪紀錄 → 歷史回顧

- D1 `visit(id, user_id, ftid, visited_at, note?, my_rating?)`——「我某天在這吃過」。
- API:`POST /api/visits`、`GET /api/visits`(本人時間軸)。
- 前端:詳情「記錄造訪」;「歷史回顧」頁——時間軸 + 造訪過的店標在地圖 +
  統計(吃過幾家、最常去的區、每月次數、口袋清單完成度)。

#### 4.3 排隊人數 / 等候時間回報(群眾共享)

- D1 `wait_report(id, ftid, user_id, queue_count, est_wait_min, reported_at)`。
- **目前估計**:取近 30~60 分鐘的回報,依新鮮度加權;沒有近期回報就不顯示(過時資料無用)。
- 前端:詳情「回報排隊」(人數 / 預估分鐘);卡片/詳情顯示「目前約 15 分 · 5 分前回報」。
- **難點**:冷啟動稀疏(多數店沒人回報)、可信度/濫用、時效性。
- **關鍵補強**:Google 地圖有「**目前繁忙程度 / 熱門時段(popular times / live busyness)**」,
  採集時**很可能抓得到**(place 回應內),可當作**零使用者也有的基準**,群眾回報疊上去校正。
  → 先驗證採集端能否穩定拿到 popular times;能的話它就是等候功能的底層資料,回報是加值。
- 需登入才能回報(可課責、減少灌水)。

#### 資料架構影響

- D1 從「只有家裡 publish 寫」變成「家裡 publish + 使用者寫」;user 表與 shop/snapshot 併存。
- 讀寫分離仍成立:地圖/列表走 `shops.json`(靜態、快),使用者資料與等候估計走 Worker + D1。
- 這正是 P0 選 hybrid 架構的原因,現在把 D1 的寫入面補上。

### 地區擴充(雙北 → 台中 → 高雄 → 全台 → 日本)

分階段擴大涵蓋範圍。採集端與前端大致 region-agnostic,主要工作是關鍵字/地區設定與**規模**。

**階段**:
1. 雙北(現況)
2. 台中、高雄(各大都會)
3. 全台
4. 日本(全台穩定後)

**每階段要做的**:
- seed 關鍵字擴充(各縣市/行政區,如 `拉麵 台中西區`);把 `ramen/seed.py` 的
  `_in_twin_cities` 地區守門改成**可設定的地區清單**(config-driven,不再寫死雙北)。
- 過濾規則沿用(台式雜訊過濾對全台同樣適用;日本則幾乎沒有此問題)。

**關鍵架構轉折(規模)**:
- 現在 617 家整包成一顆 `shops.json` 前端載入、client 端篩選——這在數千家內都還行
  (幾 MB)。
- **到全台(上萬家)/ 日本(數萬~數十萬家)會撐不住**:單一 JSON 過大、初次載入慢。
  屆時改為 **viewport 載入**——前端只向 Worker 要「目前地圖範圍內」的店(D1 空間查詢 +
  bbox 索引 / 或分區塊的靜態檔),不再一次載全部。這是擴充到一定規模必然要做的調整,
  越早把資料存取抽象成「依範圍取店」介面越好。
- 採集量同步暴增:住宅 IP 的請求量與被擋風險上升,需**分區、分日排程**慢慢鋪,
  而非一次抓完;每日排程改成輪流跑不同地區。
- 分類(P4 LLM 種類)、等候(popular times)等功能對日本資料同樣適用,且日本 Google
  資料通常更完整。

### 其他點子(未排期)

- 「營業中(依現在時間)」精準判斷(用 opening_hours 對當下時刻,而非只看 business_status)
- 依地圖範圍排序、距離排序
- 分享單店連結(deep link 到某家店)
