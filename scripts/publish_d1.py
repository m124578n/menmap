"""把本機 data/ramen.db「某一天新增的列」匯出成增量 SQL,供推到遠端 D1(每日 publish 用)。

    uv run python scripts/publish_d1.py [--date YYYY-MM-DD] [--out worker/publish.local.sql]
    cd worker && npx wrangler d1 execute menmap --remote --file=./publish.local.sql -y
    (兩步合起來就是 worker 的 `npm run db:publish`)

本機 SQLite 是正本,遠端 D1 是複本;這支只搬「當天」的變動,不整顆重灌:
- shop:當天有被抓到(last_seen)或當天被 LLM 分類(classified_at)的店,整列覆蓋(INSERT OR REPLACE)
- snapshot:當天的列;先刪遠端同 captured_at 的列再插,同一天重跑不會重複
- review / post:比照 ramen/db.py 的 replace_*:某店某後端當天有新資料,就整批取代
產生的 SQL 可重複執行(冪等)。
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "ramen.db"
DEFAULT_OUT = ROOT / "worker" / "publish.local.sql"
TZ_TAIPEI = timezone(timedelta(hours=8))  # 同 ramen/storage.py;Windows 沒 tzdata 不用 zoneinfo

SHOP_COLS = ["ftid", "name", "address", "lat", "lng", "phone", "website",
             "place_id", "cover_photo", "fan_page", "location_id", "closed_at",
             "menu_photos_json", "first_seen", "last_seen",
             "categories_json", "beginner_friendly", "classified_at", "classify_model"]
SNAPSHOT_COLS = ["ftid", "backend", "captured_at", "ok", "error",
                 "business_status", "opening_hours_json", "price_text", "rating",
                 "user_rating_count", "phone", "website", "is_rich",
                 "review_count_scraped"]
REVIEW_COLS = ["ftid", "backend", "captured_at", "seq", "author", "stars",
               "date_rel", "text", "photos_json"]
POST_COLS = ["ftid", "backend", "captured_at", "seq", "text", "ts", "link", "photo"]


def lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def _insert(table: str, cols: list[str], row: sqlite3.Row, *, replace: bool = False) -> str:
    verb = "INSERT OR REPLACE" if replace else "INSERT"
    vals = ", ".join(lit(row[c]) for c in cols)
    return f"{verb} INTO {table} ({', '.join(cols)}) VALUES ({vals});"


def build_sql(conn: sqlite3.Connection, date: str) -> tuple[list[str], dict[str, int]]:
    """回傳 (SQL 行, 各表列數)。date 是 YYYY-MM-DD,比對 captured_at / last_seen 前綴。"""
    like = f"{date}%"
    lines = [f"-- 由 scripts/publish_d1.py 產生:{date} 增量;可重複執行"]
    counts: dict[str, int] = {}

    # 當天有快照(last_seen)或當天有被 LLM 分類(classified_at)的店,整列覆蓋
    shops = conn.execute(
        f"SELECT {', '.join(SHOP_COLS)} FROM shop WHERE last_seen LIKE ? OR classified_at LIKE ?",
        (like, like)).fetchall()
    lines += [_insert("shop", SHOP_COLS, r, replace=True) for r in shops]
    counts["shop"] = len(shops)

    snaps = conn.execute(
        f"SELECT {', '.join(SNAPSHOT_COLS)} FROM snapshot WHERE captured_at LIKE ? "
        "ORDER BY id", (like,)).fetchall()
    stamps = sorted({r["captured_at"] for r in snaps})
    if stamps:
        lines.append("DELETE FROM snapshot WHERE captured_at IN ("
                     + ", ".join(lit(s) for s in stamps) + ");")
    lines += [_insert("snapshot", SNAPSHOT_COLS, r) for r in snaps]
    counts["snapshot"] = len(snaps)

    for table, cols in (("review", REVIEW_COLS), ("post", POST_COLS)):
        keys = conn.execute(
            f"SELECT DISTINCT ftid, backend FROM {table} WHERE captured_at LIKE ?",
            (like,)).fetchall()
        n = 0
        for k in keys:
            lines.append(f"DELETE FROM {table} WHERE ftid = {lit(k['ftid'])} "
                         f"AND backend = {lit(k['backend'])};")
            rows = conn.execute(
                f"SELECT {', '.join(cols)} FROM {table} WHERE ftid = ? AND backend = ? "
                "ORDER BY seq", (k["ftid"], k["backend"])).fetchall()
            lines += [_insert(table, cols, r) for r in rows]
            n += len(rows)
        counts[table] = n
    return lines, counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", default=datetime.now(TZ_TAIPEI).strftime("%Y-%m-%d"))
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--db", type=Path, default=DB)
    a = ap.parse_args()
    if not a.db.exists():
        raise SystemExit(f"{a.db} 不存在")
    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    lines, counts = build_sql(conn, a.date)
    conn.close()
    a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{a.date} 增量 → {a.out}")
    print("  ", counts)
    if not any(counts.values()):
        print("   (當天沒有任何變動;SQL 只有註解,推上去也無害)")


if __name__ == "__main__":
    main()
