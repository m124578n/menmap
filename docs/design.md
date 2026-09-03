# menmap 前端設計規格

雙北拉麵地圖。**地圖優先的搜尋型工具**(map-first directory/finder),不是行銷落地頁。
全螢幕地圖 + 浮在其上的和風面板。**日系美學**:留白(間 ma)、細硬邊框(hairline)、
生成奶白紙感、墨黑文字、藍染靛與朱紅點綴。收斂、精緻、職人感,支援深色模式,
桌機與手機都好用。

> 設計來源:ui-ux-pro-max 設計系統(見 `design-system/menmap/MASTER.md`),
> 版型採「Directory / Listing + Map」;視覺調性刻意往和風走,少玻璃擬態、多紙感留白。

## 配色 tokens

和風色:生成(kinari)奶白底、墨(sumi)黑字、藍染(ai)靛為主色、朱(shu)紅點綴。
主色用沉穩靛藍(如暖簾/地圖),朱紅只在品牌標記與選中處少量出現(避免與停業紅衝突)。

### Light
| Token | 值 | 用途 |
|---|---|---|
| `--bg` | `#F6F1E7` | 頁面底(生成奶白/紙感) |
| `--surface` | `rgba(250,247,240,0.86)` | 面板(紙感,微透) |
| `--surface-solid` | `#FBF8F2` | 卡片實底 |
| `--fg` | `#1F1B16` | 主文字(墨) |
| `--fg-muted` | `#6E655A` | 次要文字(灰茶) |
| `--primary` | `#22405F` | 主色(藍染靛:按鈕、選中 chip、focus) |
| `--on-primary` | `#F6F1E7` | |
| `--accent` | `#C1352B` | 朱紅點綴(品牌標記、選中 pin、重點) |
| `--border` | `#E3DBCC` | hairline 邊框 |
| `--open` | `#3F7A5B` | 營業中(松葉綠) |
| `--closed-temp` | `#C98A1E` | 暫停營業(山吹) |
| `--closed-perm` | `#B23A2E` | 永久停業(弁柄) |

### Dark
| Token | 值 |
|---|---|
| `--bg` | `#15130F`(墨黑,暖調) |
| `--surface` | `rgba(30,27,22,0.86)` |
| `--surface-solid` | `#1E1B16` |
| `--fg` | `#F2ECE0`(生成) |
| `--fg-muted` | `#A99E8E` |
| `--primary` | `#6E93C9`(深色下的藍染,加亮) |
| `--accent` | `#E05A4E`(朱紅加亮) |
| `--border` | `rgba(242,236,224,0.12)` |
| `--open` | `#5A9E78` · `--closed-temp` `#D9A441` · `--closed-perm` `#D8574A` |

對比一律 ≥ 4.5:1。

## 字體

- **Noto Serif JP**(店名標題、品牌字 — 帶明體/職人氣質,和風核心)
- **Noto Sans TC**(UI/內文,台灣繁體)+ **Noto Sans JP**(假名 fallback)
- base 16px、line-height 1.6(和風偏鬆);店名標題 20–26px serif、字距略收。
- 載入:Google Fonts(P3 可自架)。

## 和風視覺語彙

- **紙感留白**:大量負空間(間),面板用生成紙色實底 + 1px hairline 邊框(`--border`),
  取代重玻璃模糊;陰影極淡。
- **細線分隔**:清單、區塊用 1px hairline 分隔,不用粗重卡片陰影。
- **暖簾(noren)點綴**:面板頂部或標題可加一道 `--accent` 朱紅細線/短飾條。
- **圓角克制**:8–10px(比一般 App 小),偏俐落;標記/印章元素可用正圓(判子感)。
- **朱印標記**:品牌/選中 pin 走朱紅圓印(hanko)意象。

## 版型

### 桌機(≥1024px)
```
┌───────────────────────────────────────────────────────┐
│ [🔍 搜尋店名]              浮動玻璃 · 左上         [☰][🌙]│
│ [中山區][大安區…] [營業中] [★4.0+]  篩選 chips          │
│ ┌─────────────┐                                         │
│ │ 店家列表     │            全螢幕 MapLibre 地圖         │
│ │ (可收合抽屜) │            標記依狀態上色 · 低 zoom 聚合 │
│ │ ShopCard×N   │                                         │
│ │ ...          │        選店 → DetailPanel 覆蓋於列表上  │
│ └─────────────┘                                         │
└───────────────────────────────────────────────────────┘
```
列表抽屜寬 ~380px,可收合。選取單店時 DetailPanel 從左側滑入蓋住列表。

### 手機(<768px)
- 全螢幕地圖 + 頂部搜尋列。
- 底部 **bottom sheet**(拖曳把手,3 段:peek 露出把手+筆數 / half / full)承載列表。
- 選店 → bottom sheet 切成詳情內容(full)。
- 篩選 chips 橫向可捲。

## 元件

| 元件 | 內容 |
|---|---|
| `SearchBar` | 名稱即時搜尋(debounce 200ms),清除鈕 |
| `FilterChips` | 區域(多選)、營業中(toggle)、最低評分(★4.0/4.5) |
| `MapView` | MapLibre;GeoJSON source + cluster;標記依 status 上色;選中放大;點擊選店;地圖移動時列表同步可見範圍 |
| `ShopList` | 虛擬化列表(617 筆);依目前篩選+地圖範圍 |
| `ShopCard` | 店名、區域、★評分(評論數)、狀態點、價位、類別 tag |
| `DetailPanel` | 店名(serif)、營業狀態徽章、營業時間(可展開)、評分+評論數、價位、評論(作者/星等/日期/內文/照片)、封面照、Google Maps 連結 |
| `ThemeToggle` | 明/暗切換,記憶於 localStorage |
| `StatusDot` / `StatusBadge` | 綠=營業中、琥珀=暫停、紅=永久停業、灰=未知 |

## 風格與互動

- **紙感面板**:生成紙色實底 + 1px hairline 邊框 + 極淡陰影;非重玻璃模糊(和風收斂)。
- **標記**:朱印(hanko)意象圓標,依狀態上色;聚合泡泡用 `--primary` 靛藍顯示筆數;
  選中 pin 放大 + 朱紅環 + 輕彈跳(back.out)。
- **動效**:150–300ms;列表載入輕微 stagger;`prefers-reduced-motion` 全部關閉。
- **icon**:Lucide(SVG),不用 emoji。
- **觸控**:目標 ≥44×44px、間距 ≥8px;所有可點元素 `cursor-pointer` + hover 過渡。
- **地圖底圖**:P0 用 CARTO positron(light)/dark-matter(dark),低彩度不搶標記;
  P3 換自架 pmtiles 並套和風配色。
- 響應斷點:375 / 768 / 1024 / 1440。

## 資料來源(P0)

`web/public/shops.json`(由 `scripts/export_web_data.py` 產生)。單店詳情/評論/歷史在 P1
接上 Worker + D1 的 `/api/shop/:ftid`;P0 先用 shops.json 內的欄位撐詳情面板骨架。
