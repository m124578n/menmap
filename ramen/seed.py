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

KEYWORDS = ["拉麵 台北市", "拉麵 新北市", "ラーメン 台北"]
MAX_TOTAL = 300
PAGE_SIZE = 20
MAX_PAGES = 6  # 每關鍵字最多翻幾頁(20×6=120)

# 過濾:名稱含這些字、或不含任何拉麵相關字樣的,視為非拉麵店
NAME_BLOCKLIST = ["百貨", "美食街", "商場", "夜市", "outlet", "Mall", "廣場", "市場"]
RAMEN_HINTS = ["拉麵", "ラーメン", "ramen", "らーめん", "つけ麺", "沾麵", "油そば"]
TYPE_ALLOW = ["拉麵店", "麵店", "日本餐廳", "日式", "拉麵", "餐廳", "ramen"]


def _looks_like_ramen(d: ShopDetail) -> bool:
    name = (d.name or "")
    if any(b.lower() in name.lower() for b in NAME_BLOCKLIST):
        return False
    if any(h.lower() in name.lower() for h in RAMEN_HINTS):
        return True
    # 名稱看不出來時,靠類別;類別含「拉麵店」最可靠
    types = " ".join(d.types).lower()
    if "拉麵" in types or "ramen" in types or "麵店" in types:
        return True
    # 純日式餐廳但名稱/類別都沒拉麵字樣 → 保守排除(驗證期寧缺勿濫)
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
