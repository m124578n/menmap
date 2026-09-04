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


def _json_list(raw: str | None) -> list:
    try:
        v = json.loads(raw) if raw else []
        return v if isinstance(v, list) else []
    except (ValueError, TypeError):
        return []


def shop_master() -> dict[str, sqlite3.Row]:
    """shop 主檔(每日快照 upsert,改名/搬家會反映在這;seed 只有每週更新)。"""
    if not DB.exists():
        return {}
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = {r["ftid"]: r for r in conn.execute(
        "SELECT ftid, name, address, lat, lng, categories_json, beginner_friendly FROM shop")}
    conn.close()
    return rows


def build() -> dict:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    snaps = latest_snapshots()
    master = shop_master()

    # 新店判定:相對於「初始收錄批次」——初始整批不算新,之後 seed 更新
    # 加入且 30 天內的才標 NEW
    added_dates = sorted({(s.get("added_at") or "")[:10] for s in seed if s.get("added_at")})
    baseline = added_dates[0] if added_dates else ""
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    shops = []
    for s in seed:
        # 名稱/地址/座標優先用 shop 主檔(天天更新),沒有才退回 seed
        m = master.get(s["ftid"])
        name = (m["name"] if m and m["name"] else None) or s.get("name")
        address = (m["address"] if m and m["address"] else None) or s.get("address")
        lat = m["lat"] if m and m["lat"] is not None else s.get("lat")
        lng = m["lng"] if m and m["lng"] is not None else s.get("lng")
        city, dist = city_district(address)
        snap = snaps.get(s["ftid"])
        hours = None
        if snap and snap["opening_hours_json"]:
            try:
                hours = json.loads(snap["opening_hours_json"])
            except (ValueError, TypeError):
                pass
        added = (s.get("added_at") or "")[:10]
        shops.append({
            "ftid": s["ftid"],
            "name": name,
            "lat": lat,
            "lng": lng,
            "city": city,
            "district": dist,
            "types": s.get("types") or [],
            "status": snap["business_status"] if snap else None,
            "rating": snap["rating"] if snap else None,
            "rating_count": snap["user_rating_count"] if snap else None,
            "price": snap["price_text"] if snap else None,
            "hours": hours,
            "added_at": added or None,
            "is_new": bool(added and added > baseline and added >= cutoff),
            "cover": None,
            "maps_url": s.get("maps_url"),
            # LLM 分類(scripts/classify_types.py);沒跑過就是 []/None
            "categories": _json_list(m["categories_json"]) if m else [],
            "beginner": (None if not m or m["beginner_friendly"] is None else bool(m["beginner_friendly"])),
        })
    return {"generated_at": None, "shops": shops}


# ---------------------------------------------------------------------------
# 麵榜 / 本週動態(discover.json):全部從現有資料算,零使用者也有內容
# ---------------------------------------------------------------------------
DISCOVER_OUT = ROOT / "web" / "public" / "discover.json"
WINDOW_DAYS = 7
BAYES_M = 300         # 貝氏平均的「先驗評論數」:評論數少於這個量的高分會被拉回全體平均
HOT_N, RISING_N, STARTER_N = 20, 10, 15


def _price_max(price: str | None) -> int | None:
    if not price:
        return None
    nums = re.findall(r"\d+", price.replace(",", ""))
    return max(map(int, nums)) if nums else None


def build_discover(shops: list[dict], seed: list[dict], baseline: str) -> dict:
    from datetime import datetime, timedelta
    now = datetime.now()
    since = (now - timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%d")
    by_ftid = {s["ftid"]: s for s in shops}

    alive = [s for s in shops if s["status"] != "CLOSED_PERMANENTLY"]
    rated = [s for s in alive if s["rating"] and s["rating_count"]]
    C = sum(s["rating"] for s in rated) / len(rated) if rated else 0.0

    def bayes(s: dict) -> float:
        v, R = s["rating_count"], s["rating"]
        return (v / (v + BAYES_M)) * R + (BAYES_M / (v + BAYES_M)) * C

    hot = [{"ftid": s["ftid"], "score": round(bayes(s), 3)}
           for s in sorted(rated, key=bayes, reverse=True)[:HOT_N]]

    # 入門友善:大眾接受度高(評論多、評分穩)、價格親民、目前營業
    starter = [s for s in rated
               if s["rating"] >= 4.3 and s["rating_count"] >= 800
               and (_price_max(s["price"]) or 0) <= 400 and s["status"] == "OPERATIONAL"]
    starter = [{"ftid": s["ftid"]} for s in sorted(starter, key=lambda s: -s["rating_count"])[:STARTER_N]]

    # 近 7 天視窗:每家店「視窗內最早 vs 最新」的成功快照
    first: dict[str, sqlite3.Row] = {}
    last: dict[str, sqlite3.Row] = {}
    dates: set[str] = set()
    if DB.exists():
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT ftid, captured_at, business_status, rating, user_rating_count,
                      opening_hours_json FROM snapshot
               WHERE ok = 1 AND captured_at >= ? ORDER BY captured_at""", (since,)).fetchall()
        for r in rows:
            dates.add(r["captured_at"][:10])
            first.setdefault(r["ftid"], r)
            last[r["ftid"]] = r
        try:
            renames = [{"ftid": r["ftid"], "field": r["field"], "old": r["old"], "new": r["new"]}
                       for r in conn.execute(
                           "SELECT ftid, field, old, new FROM shop_change WHERE captured_at >= ? ORDER BY id",
                           (since,)) if r["ftid"] in by_ftid]
        except sqlite3.OperationalError:  # 表由採集端 db.connect 建;第一次快照前還沒有
            renames = []
        conn.close()
    else:
        renames = []

    rising, status_changes, rating_jumps, hours_changes = [], [], [], []
    for ftid, a in first.items():
        b = last[ftid]
        if ftid not in by_ftid or a is b or a["captured_at"][:10] == b["captured_at"][:10]:
            continue
        days = max(1, (datetime.fromisoformat(b["captured_at"][:10]) -
                       datetime.fromisoformat(a["captured_at"][:10])).days)
        if a["user_rating_count"] is not None and b["user_rating_count"] is not None:
            delta = b["user_rating_count"] - a["user_rating_count"]
            if delta >= 3:
                rising.append({"ftid": ftid, "delta": delta, "days": days})
        if a["business_status"] != b["business_status"]:
            status_changes.append({"ftid": ftid, "from": a["business_status"],
                                   "to": b["business_status"], "at": b["captured_at"][:10]})
        if a["rating"] is not None and b["rating"] is not None and abs(b["rating"] - a["rating"]) >= 0.1:
            rating_jumps.append({"ftid": ftid, "from": a["rating"], "to": b["rating"]})
        if a["opening_hours_json"] and b["opening_hours_json"] \
                and a["opening_hours_json"] != b["opening_hours_json"]:
            hours_changes.append({"ftid": ftid})
    rising.sort(key=lambda x: (-x["delta"] / x["days"], -x["delta"]))
    rating_jumps.sort(key=lambda x: -(x["to"] - x["from"]))

    new_shops = [{"ftid": s["ftid"], "added_at": (s.get("added_at") or "")[:10]}
                 for s in seed if s["ftid"] in by_ftid
                 and (s.get("added_at") or "")[:10] > baseline and (s.get("added_at") or "")[:10] >= since]
    new_shops.sort(key=lambda x: x["added_at"], reverse=True)

    return {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "window": {"from": since, "to": now.strftime("%Y-%m-%d"), "days": len(dates)},
        "hot": hot,
        "rising": rising[:RISING_N],
        "starter": starter,
        "weekly": {
            "new_shops": new_shops,
            "status_changes": status_changes,
            "rating_jumps": rating_jumps[:20],
            "hours_changes": hours_changes,
            "renames": renames,
        },
    }


def main() -> None:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    n = len(data["shops"])
    withgeo = sum(1 for s in data["shops"] if s["lat"] and s["lng"])
    print(f"匯出 {n} 家(有座標 {withgeo})→ {OUT}")

    seed = json.loads(SEED.read_text(encoding="utf-8"))
    added_dates = sorted({(s.get("added_at") or "")[:10] for s in seed if s.get("added_at")})
    disc = build_discover(data["shops"], seed, added_dates[0] if added_dates else "")
    DISCOVER_OUT.write_text(json.dumps(disc, ensure_ascii=False), encoding="utf-8")
    w = disc["weekly"]
    print(f"麵榜 → {DISCOVER_OUT}:熱門 {len(disc['hot'])}、竄紅 {len(disc['rising'])}、入門 {len(disc['starter'])};"
          f"本週(快照 {disc['window']['days']} 天):新店 {len(w['new_shops'])}、狀態 {len(w['status_changes'])}、"
          f"評分 {len(w['rating_jumps'])}、時間 {len(w['hours_changes'])}、改名/搬家 {len(w['renames'])}")


if __name__ == "__main__":
    main()
