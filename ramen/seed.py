"""Seed 建立:搜尋雙北拉麵店、過濾、去重,產出 data/seed.json。

只跑一次;之後 seed 由人工維護。用靜態後端(快、分頁方便)。
"""

from __future__ import annotations

import logging

from . import net, storage
from .dynamic_backend import place_url_for
from .schema import ShopDetail
from .static_backend import StaticBackend

log = logging.getLogger(__name__)

# 大範圍關鍵字 + 外圍行政區補強(內湖/士林/北投等在大範圍搜尋中被低估)
KEYWORDS = [
    "拉麵 台北市", "拉麵 新北市", "ラーメン 台北", "つけ麺 台北",
    # 台北外圍區
    "拉麵 內湖", "拉麵 士林", "拉麵 北投", "拉麵 文山", "拉麵 南港",
    # 新北各區
    "拉麵 板橋", "拉麵 中和", "拉麵 永和", "拉麵 新莊", "拉麵 三重",
    "拉麵 新店", "拉麵 汐止", "拉麵 樹林", "拉麵 土城", "拉麵 蘆洲",
    "拉麵 淡水", "拉麵 三峽",
]
MAX_TOTAL = 1000  # 實務上會在關鍵字自然枯竭前遠低於此
PAGE_SIZE = 20
MAX_PAGES = 6  # 每關鍵字最多翻幾頁(20×6=120)

# --- 過濾 ---
# 非餐廳的整體場域
NAME_BLOCKLIST = ["百貨", "美食街", "商場", "outlet", "Mall", "廣場", "夜市"]
# 名稱含這些字 → 台式/中式麵食,非日式拉麵,直接排除
NOISE_NAME = ["刀削麵", "刀切麵", "刀削", "牛肉麵", "牛肉拉麵", "蘭州",
              "湯餃", "水餃", "牛大娘", "腸粉", "木須", "清燉牛", "麵館"]
# 判定為日式的訊號
RAMEN_HINTS = ["拉麵", "ラーメン", "ramen", "らーめん", "らあめん",
               "つけ麺", "つけめん", "沾麵", "油そば", "麺", "家系", "豚骨"]
# 類別:日式拉麵一定帶「拉麵店」,常伴「日本餐廳」
JP_TYPES = ["拉麵店", "日本餐廳", "日式"]
# 類別:台式/中式訊號,出現即排除(日式拉麵店不會帶這些)
CN_TYPES = ["中式麵食店", "中菜館", "台灣餐廳"]

# 雙北地區守門:關鍵字帶「台北」時 Google 會摻入外縣市結果
TAIPEI_DISTRICTS = ["中正", "大同", "中山", "松山", "大安", "萬華",
                    "信義", "士林", "北投", "內湖", "南港", "文山"]
NEW_TAIPEI_DISTRICTS = [
    "板橋", "三重", "中和", "永和", "新莊", "新店", "樹林", "鶯歌", "三峽",
    "淡水", "汐止", "瑞芳", "土城", "蘆洲", "五股", "泰山", "林口", "深坑",
    "石碇", "坪林", "三芝", "石門", "八里", "平溪", "雙溪", "貢寮", "金山",
    "萬里", "烏來"]
TWIN_DISTRICTS = [d + "區" for d in TAIPEI_DISTRICTS + NEW_TAIPEI_DISTRICTS]
# 明確排除的其他縣市(避免同名行政區誤收,例如基隆也有中山區)
OTHER_CITIES = ["基隆市", "桃園市", "新竹", "苗栗", "台中市", "臺中市", "彰化",
                "南投", "雲林", "嘉義", "台南市", "臺南市", "高雄市", "屏東",
                "宜蘭", "花蓮", "台東", "臺東", "澎湖", "金門", "連江"]


def _in_twin_cities(address: str | None) -> bool:
    a = address or ""
    if any(c in a for c in OTHER_CITIES):
        return False
    if "臺北市" in a or "台北市" in a or "新北市" in a:
        return True
    # 地址偶爾只寫「台灣內湖區/淡水區」不帶市名,靠雙北行政區名補認
    return any(d in a for d in TWIN_DISTRICTS)


def _looks_like_ramen(d: ShopDetail) -> bool:
    name = (d.name or "")
    joined = " ".join(d.types or [])

    # 1) 明確排除:場域、台式名稱
    if any(b.lower() in name.lower() for b in NAME_BLOCKLIST):
        return False
    if any(n in name for n in NOISE_NAME):
        return False
    # 2) 類別帶台式/中式訊號 → 排除(即使同時掛了「拉麵店」也是台式店)
    if any(c in joined for c in CN_TYPES):
        return False
    # 3) 接受:類別是日式拉麵店,或名稱有日式拉麵字樣
    if any(t in joined for t in JP_TYPES):
        return True
    if any(h.lower() in name.lower() for h in RAMEN_HINTS):
        return True
    return False


def build_seed() -> list[dict]:
    backend = StaticBackend()
    seen: dict[str, ShopDetail] = {}
    for kw in KEYWORDS:
        log.info("搜尋關鍵字:%s", kw)
        for page in range(MAX_PAGES):
            if len(seen) >= MAX_TOTAL:
                break
            offset = page * PAGE_SIZE
            try:
                results, _, _ = backend.search(kw, offset=offset)
            except Exception as e:  # noqa: BLE001
                log.warning("  第 %d 頁失敗:%s", page + 1, e)
                break
            new = 0
            for r in results:
                if r.ftid in seen:
                    continue
                if not _looks_like_ramen(r):
                    continue
                if not _in_twin_cities(r.address):
                    continue
                seen[r.ftid] = r
                new += 1
            log.info("  第 %d 頁:%d 筆結果,新增 %d(累計 %d)",
                     page + 1, len(results), new, len(seen))
            if not results:
                break
            net.polite_sleep()
        if len(seen) >= MAX_TOTAL:
            break

    added_at = storage.now_iso()
    entries = []
    for d in seen.values():
        entries.append({
            "ftid": d.ftid,
            "name": d.name,
            "address": d.address,
            "lat": d.lat,
            "lng": d.lng,
            "types": d.types,
            "place_id": d.place_id,
            "gid": d.req_ids.get("gid"),
            "maps_url": place_url_for(d.ftid, d.name or "", lat=d.lat, lng=d.lng,
                                      gid=d.req_ids.get("gid"), place_id=d.place_id),
            "added_at": added_at,
        })
    return entries


def run_seed(force: bool = False) -> int:
    existing = storage.load_seed()
    if existing and not force:
        log.warning("seed.json 已存在(%d 筆);要覆蓋請加 --force", len(existing))
        print(f"seed.json 已有 {len(existing)} 筆,未變更(--force 可覆蓋)")
        return len(existing)
    entries = build_seed()
    storage.save_seed(entries)
    print(f"seed 完成:{len(entries)} 家拉麵店 → {storage.SEED_FILE}")
    return len(entries)
