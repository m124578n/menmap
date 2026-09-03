"""把 seed + 最新快照匯出成前端用的 web/public/shops.json。

開發期用(P0):地圖載這顆檔案就能把 617 家點上去。之後 P2 改由家裡
publish 步驟產生同格式檔案上傳 R2。
    uv run python scripts/export_web_data.py
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "data" / "seed.json"
DB = ROOT / "data" / "ramen.db"
OUT = ROOT / "web" / "public" / "shops.json"

TAIPEI = ["中正", "大同", "中山", "松山", "大安", "萬華",
          "信義", "士林", "北投", "內湖", "南港", "文山"]
NEW_TAIPEI = [
    "板橋", "三重", "中和", "永和", "新莊", "新店", "樹林", "鶯歌", "三峽",
    "淡水", "汐止", "瑞芳", "土城", "蘆洲", "五股", "泰山", "林口", "深坑",
    "石碇", "坪林", "三芝", "石門", "八里", "平溪", "雙溪", "貢寮", "金山",
    "萬里", "烏來"]
TAIPEI_SET = set(TAIPEI)
# 3 字區名優先比對(避免「三重」誤配到含「三」的字串等,雖然目前無衝突)
ALL_DISTRICTS = sorted(TAIPEI + NEW_TAIPEI, key=len, reverse=True)


def city_district(addr: str | None) -> tuple[str | None, str | None]:
    a = addr or ""
    dist = None
    for d in ALL_DISTRICTS:
        if d + "區" in a:
            dist = d + "區"
            break
    if "新北市" in a:
        city = "新北市"
    elif "臺北市" in a or "台北市" in a:
        city = "台北市"
    elif dist:
        city = "台北市" if dist[:-1] in TAIPEI_SET else "新北市"
    else:
        city = None
    return city, dist


def latest_snapshots() -> dict[str, sqlite3.Row]:
    """每家店最近一次成功快照(不分後端,playwright 優先因較完整)。"""
    if not DB.exists():
        return {}
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT s.* FROM snapshot s
        JOIN (
            SELECT ftid, MAX(captured_at) mx FROM snapshot
            WHERE ok = 1 GROUP BY ftid
        ) t ON s.ftid = t.ftid AND s.captured_at = t.mx
        WHERE s.ok = 1
        """
    ).fetchall()
    out: dict[str, sqlite3.Row] = {}
    for r in rows:
        # 同 captured_at 可能兩後端都有,留 is_rich 或 user_rating_count 較全的
        prev = out.get(r["ftid"])
        if prev is None or (r["is_rich"] or 0) >= (prev["is_rich"] or 0):
            out[r["ftid"]] = r
    conn.close()
    return out


def build() -> dict:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    snaps = latest_snapshots()
    shops = []
    for s in seed:
        city, dist = city_district(s.get("address"))
        snap = snaps.get(s["ftid"])
        shops.append({
            "ftid": s["ftid"],
            "name": s.get("name"),
            "lat": s.get("lat"),
            "lng": s.get("lng"),
            "city": city,
            "district": dist,
            "types": s.get("types") or [],
            "status": snap["business_status"] if snap else None,
            "rating": snap["rating"] if snap else None,
            "rating_count": snap["user_rating_count"] if snap else None,
            "price": snap["price_text"] if snap else None,
            "cover": None,
            "maps_url": s.get("maps_url"),
        })
    return {"generated_at": None, "shops": shops}


def main() -> None:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    n = len(data["shops"])
    withgeo = sum(1 for s in data["shops"] if s["lat"] and s["lng"])
    print(f"匯出 {n} 家(有座標 {withgeo})→ {OUT}")


if __name__ == "__main__":
    main()
