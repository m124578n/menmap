"""把 data/raw/{date}/{backend}/ 的原始回應重新解析,更新 shop / review / post。

parser 加新欄位後,已抓過的店不用重爬——raw 有落地,重解析即可。
    uv run python scripts/reparse_raw.py [date=today] [backend=playwright]
不動 snapshot 表(那是當時的快照事實)。
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ramen import db, storage  # noqa: E402
from ramen.parser import EmptyPlaceResponse, parse_place_response  # noqa: E402


def main() -> None:
    date = sys.argv[1] if len(sys.argv) > 1 else storage.today_str()
    backend = sys.argv[2] if len(sys.argv) > 2 else "playwright"
    files = glob.glob(str(storage.RAW_DIR / date / backend / "*.json"))
    if not files:
        print(f"沒有 raw 檔:{storage.RAW_DIR / date / backend}")
        return
    conn = db.connect(storage.DB_FILE)
    now = storage.now_iso()
    ok = skip = 0
    for f in files:
        try:
            d = parse_place_response(Path(f).read_text(encoding="utf-8"))
        except (EmptyPlaceResponse, ValueError):
            skip += 1
            continue
        db.upsert_shop(conn, d, now)
        db.replace_reviews(conn, d.ftid, backend, now, d.reviews)
        db.replace_posts(conn, d.ftid, backend, now, d.posts)
        ok += 1
    conn.commit()
    conn.close()
    print(f"重解析 {backend} {date}:{ok} 家更新,{skip} 略過")


if __name__ == "__main__":
    main()
