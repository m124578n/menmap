"""把本地 data/ramen.db 的 shop/snapshot/review 匯出成 worker/seed.local.sql,
供本地 D1 載入(開發用)。P2 起改由家裡 publish 步驟直接寫 D1,不再需要這步。

    uv run python scripts/export_d1_seed.py
    cd worker && npm run db:init && npm run db:seed
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "ramen.db"
OUT = ROOT / "worker" / "seed.local.sql"

TABLES = {
    "shop": ["ftid", "name", "address", "lat", "lng", "phone", "website",
             "place_id", "cover_photo", "fan_page", "location_id", "closed_at",
             "menu_photos_json", "first_seen", "last_seen",
             "categories_json", "beginner_friendly", "classified_at", "classify_model", "llm_is_ramen"],
    "snapshot": ["ftid", "backend", "captured_at", "ok", "error",
                 "business_status", "opening_hours_json", "price_text", "rating",
                 "user_rating_count", "phone", "website", "is_rich",
                 "review_count_scraped"],
    "review": ["ftid", "backend", "captured_at", "seq", "author", "stars",
               "date_rel", "text", "photos_json"],
    "post": ["ftid", "backend", "captured_at", "seq", "text", "ts", "link", "photo"],
}


def lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def main() -> None:
    if not DB.exists():
        raise SystemExit("data/ramen.db 不存在,先跑 snapshot 產生資料")
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    lines: list[str] = ["-- 由 scripts/export_d1_seed.py 產生;本地 D1 開發用",
                        "DELETE FROM post; DELETE FROM review; "
                        "DELETE FROM snapshot; DELETE FROM shop;"]
    counts = {}
    for table, cols in TABLES.items():
        rows = conn.execute(f"SELECT {', '.join(cols)} FROM {table}").fetchall()
        counts[table] = len(rows)
        for r in rows:
            vals = ", ".join(lit(r[c]) for c in cols)
            lines.append(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({vals});")
    conn.close()
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"匯出 → {OUT}")
    print("  ", {k: counts[k] for k in TABLES})


if __name__ == "__main__":
    main()
