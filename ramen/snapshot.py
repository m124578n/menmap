"""每日快照:對 seed 每家店抓詳情、存 SQLite、比 diff、印摘要。"""

from __future__ import annotations

import logging

from . import db, diff, net, storage
from .dynamic_backend import DynamicBackend, place_url_for
from .schema import ShopDetail
from .static_backend import StaticBackend

log = logging.getLogger(__name__)


def _pick_entries(conn, seed: list[dict], backend: str,
                  limit: int | None) -> list[dict]:
    """決定本次要抓哪些店。

    沒有 limit:全抓。有 limit:輪替——優先抓「從沒被該後端成功抓過」的店,
    其次「最久沒抓」的店,取前 N 家。這樣每天跑同一個 limit 就會自動輪完整個 seed,
    新加進 seed 的店也會自動排到最前面。
    """
    if not limit or limit >= len(seed):
        return list(seed)
    last = db.last_ok_capture_per_shop(conn, backend)
    # sorted 是穩定排序:同一天抓過的店維持 seed 原順序
    ordered = sorted(seed, key=lambda s: last.get(s["ftid"], ""))
    return ordered[:limit]


def _snapshot_static(seed: list[dict], date: str, limit: int | None):
    backend = StaticBackend()
    conn = db.connect(storage.DB_FILE)
    now = storage.now_iso()
    entries = _pick_entries(conn, seed, "static", limit)
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
            db.replace_posts(conn, ftid, "static", now, detail.posts)
            ok += 1
            log.info("[%d/%d] %s rich=%s", i, len(entries), name, detail.is_rich)
        except Exception as e:  # noqa: BLE001
            db.insert_snapshot(conn, ftid, "static", now, ok=False, error=str(e))
            fail += 1
            log.warning("[%d/%d] %s 失敗:%s", i, len(entries), name, e)
        conn.commit()  # 逐店 commit:不長時間鎖 DB(另一後端同時在寫),中途掛掉也保留進度
        net.polite_sleep()
    return conn, now, ok, fail


def _snapshot_playwright(seed: list[dict], date: str, limit: int | None):
    conn = db.connect(storage.DB_FILE)
    now = storage.now_iso()
    entries = _pick_entries(conn, seed, "playwright", limit)
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
                db.replace_posts(conn, ftid, "playwright", now, detail.posts)
                ok += 1
                log.info("[%d/%d] %s rich=%s", i, len(entries), name, detail.is_rich)
            except Exception as e:  # noqa: BLE001
                db.insert_snapshot(conn, ftid, "playwright", now, ok=False, error=str(e))
                fail += 1
                log.warning("[%d/%d] %s 失敗:%s", i, len(entries), name, e)
            conn.commit()  # 逐店 commit,理由同 static
            backend.polite_sleep()
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
