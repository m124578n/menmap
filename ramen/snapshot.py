"""每日快照:對 seed 每家店抓詳情、存 SQLite、比 diff、印摘要。"""

from __future__ import annotations

import logging

from . import db, diff, net, storage
from .dynamic_backend import DynamicBackend, place_url_for
from .schema import ShopDetail
from .static_backend import StaticBackend

log = logging.getLogger(__name__)


def _snapshot_static(seed: list[dict], date: str, limit: int | None):
    backend = StaticBackend()
    conn = db.connect(storage.DB_FILE)
    now = storage.now_iso()
    entries = seed[:limit] if limit else seed
    ok = fail = 0
    for i, s in enumerate(entries, 1):
        ftid, name = s["ftid"], s.get("name") or ""
        fallback = {"gid": s.get("gid"), "s6": None, "s7": None}
        try:
            detail, raw = backend.fetch_details(ftid, name, fallback_ids=fallback)
            storage.write_raw(date, "static", _safe(ftid), raw, "json")
            db.upsert_shop(conn, detail, now)
            db.insert_snapshot(conn, ftid, "static", now, ok=True, detail=detail)
            db.replace_reviews(conn, ftid, "static", now, detail.reviews)
            ok += 1
            log.info("[%d/%d] %s rich=%s", i, len(entries), name, detail.is_rich)
        except Exception as e:  # noqa: BLE001
            db.insert_snapshot(conn, ftid, "static", now, ok=False, error=str(e))
            fail += 1
            log.warning("[%d/%d] %s 失敗:%s", i, len(entries), name, e)
        net.polite_sleep()
    conn.commit()
    return conn, now, ok, fail


def _snapshot_playwright(seed: list[dict], date: str, limit: int | None):
    conn = db.connect(storage.DB_FILE)
    now = storage.now_iso()
    entries = seed[:limit] if limit else seed
    ok = fail = 0
    with DynamicBackend(headless=True) as backend:
        for i, s in enumerate(entries, 1):
            ftid, name = s["ftid"], s.get("name") or ""
            maps_url = s.get("maps_url") or place_url_for(
                ftid, name, lat=s.get("lat"), lng=s.get("lng"),
                gid=s.get("gid"), place_id=s.get("place_id"))
            try:
                detail, raw = backend.fetch_details(ftid, name, maps_url=maps_url)
                storage.write_raw(date, "playwright", _safe(ftid), raw, "json")
                db.upsert_shop(conn, detail, now)
                db.insert_snapshot(conn, ftid, "playwright", now, ok=True, detail=detail)
                db.replace_reviews(conn, ftid, "playwright", now, detail.reviews)
                ok += 1
                log.info("[%d/%d] %s rich=%s", i, len(entries), name, detail.is_rich)
            except Exception as e:  # noqa: BLE001
                db.insert_snapshot(conn, ftid, "playwright", now, ok=False, error=str(e))
                fail += 1
                log.warning("[%d/%d] %s 失敗:%s", i, len(entries), name, e)
            backend.polite_sleep()
    conn.commit()
    return conn, now, ok, fail


def _safe(ftid: str) -> str:
    return ftid.replace(":", "-")


def run_snapshot(backend_name: str, limit: int | None = None) -> int:
    seed = storage.load_seed()
    if not seed:
        print("seed.json 不存在或為空,請先執行 `python -m ramen seed`")
        return 1
    date = storage.today_str()
    log.info("開始快照:backend=%s,seed=%d 家,limit=%s", backend_name, len(seed), limit)

    if backend_name == "static":
        conn, now, ok, fail = _snapshot_static(seed, date, limit)
    elif backend_name == "playwright":
        conn, now, ok, fail = _snapshot_playwright(seed, date, limit)
    else:
        print(f"未知 backend:{backend_name}(可用:static / playwright)")
        return 2

    diff_path, changes = diff.write_diff(conn, backend_name, date, now, seed)
    conn.close()
    total = ok + fail
    print(f"{ok}/{total} ok, {fail} failed, {changes} changed")
    print(f"diff → {diff_path}")
    return 0
