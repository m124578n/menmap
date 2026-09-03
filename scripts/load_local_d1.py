"""把 data/ramen.db 直接灌進本地 D1 的 sqlite(開發用,繞過 wrangler execute 的大檔限制)。

本地 D1(miniflare)底層就是一個 sqlite 檔;直接用 Python 複製資料,
比 wrangler d1 execute --file 快且不受 body timeout / 換行切割問題影響。
只適用本地開發;遠端 D1(P2)改走 ingest Worker。

    uv run python scripts/load_local_d1.py
"""

from __future__ import annotations

import glob
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "ramen.db"

TABLES = {
    "shop": ["ftid", "name", "address", "lat", "lng", "phone", "website",
             "place_id", "cover_photo", "fan_page", "location_id", "closed_at",
             "menu_photos_json", "first_seen", "last_seen"],
    "snapshot": ["ftid", "backend", "captured_at", "ok", "error",
                 "business_status", "opening_hours_json", "price_text", "rating",
                 "user_rating_count", "phone", "website", "is_rich",
                 "review_count_scraped"],
    "review": ["ftid", "backend", "captured_at", "seq", "author", "stars",
               "date_rel", "text", "photos_json"],
    "post": ["ftid", "backend", "captured_at", "seq", "text", "ts", "link", "photo"],
}


def find_d1_file() -> Path:
    hits = glob.glob(str(ROOT / "worker" / ".wrangler" / "state" / "v3" / "d1"
                         / "miniflare-D1DatabaseObject" / "*.sqlite"))
    if not hits:
        raise SystemExit("找不到本地 D1 sqlite;先跑一次 `cd worker && npm run db:init`")
    if len(hits) > 1:
        # 取最近修改的
        hits.sort(key=lambda p: Path(p).stat().st_mtime, reverse=True)
    return Path(hits[0])


def main() -> None:
    dst_path = find_d1_file()
    src = sqlite3.connect(SRC)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(dst_path)
    total = {}
    for table, cols in TABLES.items():
        dst.execute(f"DELETE FROM {table}")
        rows = src.execute(f"SELECT {', '.join(cols)} FROM {table}").fetchall()
        ph = ", ".join("?" for _ in cols)
        dst.executemany(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({ph})",
            [tuple(r[c] for c in cols) for r in rows],
        )
        total[table] = len(rows)
    dst.commit()
    dst.close()
    src.close()
    print(f"載入本地 D1({dst_path.name[:12]}…):{total}")


if __name__ == "__main__":
    main()
