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

### 其他點子(未排期)

- 「營業中(依現在時間)」精準判斷(用 opening_hours 對當下時刻,而非只看 business_status)
- 收藏 / 我的清單(需使用者功能,會用到 D1 的 data/users 或登入)
- 依地圖範圍排序、距離排序
- 等候時間(原始需求之一,這階段刻意排除)
