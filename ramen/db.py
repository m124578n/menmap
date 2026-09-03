"""SQLite 存取:shop(店家主檔)與 snapshot(每日快照)。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .schema import ShopDetail

SCHEMA = """
CREATE TABLE IF NOT EXISTS shop (
    ftid        TEXT PRIMARY KEY,
    name        TEXT,
    address     TEXT,
    lat         REAL,
    lng         REAL,
    phone       TEXT,
    website     TEXT,
    place_id    TEXT,
    cover_photo TEXT,
    fan_page    TEXT,
    location_id TEXT,
    closed_at   TEXT,
    menu_photos_json TEXT,
    first_seen  TEXT,
    last_seen   TEXT
);

-- 商家「最新動態」貼文(每次抓到完整版就整批取代,同 review)
CREATE TABLE IF NOT EXISTS post (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ftid        TEXT NOT NULL,
    backend     TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    seq         INTEGER,
    text        TEXT,
    ts          INTEGER,
    link        TEXT,
    photo       TEXT
);

CREATE INDEX IF NOT EXISTS idx_post_shop ON post (ftid, backend);

-- 每家店「最新一次抓到的」評論(每次成功抓到完整版就整批取代;
-- 精簡版沒帶評論時保留舊的,不清空)
CREATE TABLE IF NOT EXISTS review (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ftid        TEXT NOT NULL,
    backend     TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    seq         INTEGER,
    author      TEXT,
    stars       INTEGER,
    date_rel    TEXT,
    text        TEXT,
    photos_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_review_shop ON review (ftid, backend);

CREATE TABLE IF NOT EXISTS snapshot (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    ftid               TEXT NOT NULL,
    backend            TEXT NOT NULL,
    captured_at        TEXT NOT NULL,
    ok                 INTEGER NOT NULL,
    error              TEXT,
    business_status    TEXT,
    opening_hours_json TEXT,
    price_text         TEXT,
    rating             REAL,
    user_rating_count  INTEGER,
    phone              TEXT,
    website            TEXT,
    is_rich            INTEGER,
    review_count_scraped INTEGER
);

CREATE INDEX IF NOT EXISTS idx_snapshot_backend_time
    ON snapshot (backend, captured_at);
"""


# 既有 db 補欄位用(CREATE TABLE IF NOT EXISTS 不會加新欄)
_SHOP_MIGRATIONS = ["fan_page", "location_id", "closed_at", "menu_photos_json"]


def connect(db_path: str | Path) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    # static 與 playwright 兩個快照程序會同時寫這顆 DB:
    # WAL 讓讀寫不互擋;busy timeout 讓另一方在寫入時等待而不是直接「database is locked」。
    conn = sqlite3.connect(str(db_path), timeout=60)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        pass  # 別的連線正持有鎖時切不過去,維持現有模式即可
    conn.execute("PRAGMA busy_timeout=60000")
    conn.executescript(SCHEMA)
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(shop)")}
    for col in _SHOP_MIGRATIONS:
        if col not in existing:
            conn.execute(f"ALTER TABLE shop ADD COLUMN {col} TEXT")
    return conn


def upsert_shop(conn: sqlite3.Connection, d: ShopDetail, now: str) -> None:
    dd = d.to_dict()
    menu_json = (json.dumps(d.menu_photos, ensure_ascii=False)
                 if d.menu_photos else None)
    conn.execute(
        """
        INSERT INTO shop (ftid, name, address, lat, lng, phone, website,
                          place_id, cover_photo, fan_page, location_id,
                          menu_photos_json, first_seen, last_seen)
        VALUES (:ftid, :name, :address, :lat, :lng, :phone, :website,
                :place_id, :cover_photo, :fan_page, :location_id,
                :menu_photos_json, :now, :now)
        ON CONFLICT(ftid) DO UPDATE SET
            name = COALESCE(excluded.name, shop.name),
            address = COALESCE(excluded.address, shop.address),
            lat = COALESCE(excluded.lat, shop.lat),
            lng = COALESCE(excluded.lng, shop.lng),
            phone = COALESCE(excluded.phone, shop.phone),
            website = COALESCE(excluded.website, shop.website),
            place_id = COALESCE(excluded.place_id, shop.place_id),
            cover_photo = COALESCE(excluded.cover_photo, shop.cover_photo),
            fan_page = COALESCE(excluded.fan_page, shop.fan_page),
            location_id = COALESCE(excluded.location_id, shop.location_id),
            menu_photos_json = COALESCE(excluded.menu_photos_json, shop.menu_photos_json),
            last_seen = excluded.last_seen
        """,
        {**{k: dd.get(k) for k in
            ("ftid", "name", "address", "lat", "lng", "phone", "website",
             "place_id", "cover_photo", "fan_page", "location_id")},
         "menu_photos_json": menu_json, "now": now},
    )
    # 店址沿革:偵測永久停業記 closed_at;重新營業則清除
    if d.business_status == "CLOSED_PERMANENTLY":
        conn.execute(
            "UPDATE shop SET closed_at = COALESCE(closed_at, ?) WHERE ftid = ?",
            (now, d.ftid))
    elif d.business_status == "OPERATIONAL":
        conn.execute(
            "UPDATE shop SET closed_at = NULL WHERE ftid = ? AND closed_at IS NOT NULL",
            (d.ftid,))


def replace_posts(conn: sqlite3.Connection, ftid: str, backend: str,
                  captured_at: str, posts: list[dict]) -> None:
    """整批取代某店的商家貼文。posts 為空(精簡版/沒發文)時不動舊資料。"""
    if not posts:
        return
    conn.execute("DELETE FROM post WHERE ftid = ? AND backend = ?", (ftid, backend))
    for seq, p in enumerate(posts):
        conn.execute(
            """
            INSERT INTO post (ftid, backend, captured_at, seq, text, ts, link, photo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ftid, backend, captured_at, seq, p.get("text"), p.get("ts"),
             p.get("link"), p.get("photo")),
        )


def replace_reviews(conn: sqlite3.Connection, ftid: str, backend: str,
                    captured_at: str, reviews: list[dict]) -> None:
    """整批取代某店某後端的評論。reviews 為空(精簡版)時不動舊資料。"""
    if not reviews:
        return
    conn.execute("DELETE FROM review WHERE ftid = ? AND backend = ?", (ftid, backend))
    for seq, r in enumerate(reviews):
        conn.execute(
            """
            INSERT INTO review (ftid, backend, captured_at, seq,
                author, stars, date_rel, text, photos_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ftid, backend, captured_at, seq, r.get("author"), r.get("stars"),
             r.get("date_rel"), r.get("text"),
             json.dumps(r.get("photos") or [], ensure_ascii=False)),
        )


def insert_snapshot(conn: sqlite3.Connection, ftid: str, backend: str,
                    captured_at: str, *, ok: bool, error: str | None = None,
                    detail: ShopDetail | None = None) -> None:
    row = {
        "ftid": ftid, "backend": backend, "captured_at": captured_at,
        "ok": 1 if ok else 0, "error": error,
        "business_status": None, "opening_hours_json": None, "price_text": None,
        "rating": None, "user_rating_count": None, "phone": None,
        "website": None, "is_rich": None, "review_count_scraped": None,
    }
    if detail is not None:
        row.update({
            "business_status": detail.business_status,
            "opening_hours_json": detail.hours_json(),
            "price_text": detail.price_text,
            "rating": detail.rating,
            "user_rating_count": detail.user_rating_count,
            "phone": detail.phone,
            "website": detail.website,
            "is_rich": 1 if detail.is_rich else 0,
            "review_count_scraped": len(detail.reviews),
        })
    conn.execute(
        """
        INSERT INTO snapshot (ftid, backend, captured_at, ok, error,
            business_status, opening_hours_json, price_text, rating,
            user_rating_count, phone, website, is_rich, review_count_scraped)
        VALUES (:ftid, :backend, :captured_at, :ok, :error,
            :business_status, :opening_hours_json, :price_text, :rating,
            :user_rating_count, :phone, :website, :is_rich, :review_count_scraped)
        """,
        row,
    )


def previous_snapshot_time(conn: sqlite3.Connection, backend: str,
                           before: str) -> str | None:
    """同後端、早於 before 的最近一次成功批次的 captured_at。"""
    cur = conn.execute(
        """
        SELECT captured_at FROM snapshot
        WHERE backend = ? AND captured_at < ? AND ok = 1
        ORDER BY captured_at DESC LIMIT 1
        """,
        (backend, before),
    )
    row = cur.fetchone()
    return row["captured_at"] if row else None


def last_ok_capture_per_shop(conn: sqlite3.Connection,
                             backend: str) -> dict[str, str]:
    """同後端每家店最近一次成功快照的 captured_at(從沒成功過的店不在裡面)。"""
    cur = conn.execute(
        """
        SELECT ftid, MAX(captured_at) AS at FROM snapshot
        WHERE backend = ? AND ok = 1
        GROUP BY ftid
        """,
        (backend,),
    )
    return {r["ftid"]: r["at"] for r in cur.fetchall()}


def previous_snapshots_per_shop(conn: sqlite3.Connection, backend: str,
                                before: str) -> dict[str, sqlite3.Row]:
    """同後端、早於 before,每家店各自最近一次成功快照(不限同一批次)。

    每日輪抓一部分店時,上一批次和本批次的店幾乎不重疊,所以 diff 要對「該店自己
    上一次」比,而不是對「上一個批次」比。
    """
    cur = conn.execute(
        """
        SELECT s.* FROM snapshot s
        JOIN (
            SELECT ftid, MAX(captured_at) AS at FROM snapshot
            WHERE backend = ? AND ok = 1 AND captured_at < ?
            GROUP BY ftid
        ) m ON m.ftid = s.ftid AND m.at = s.captured_at
        WHERE s.backend = ? AND s.ok = 1
        """,
        (backend, before, backend),
    )
    return {r["ftid"]: r for r in cur.fetchall()}


def snapshots_at(conn: sqlite3.Connection, backend: str,
                 captured_at: str) -> dict[str, sqlite3.Row]:
    """某次批次(以 captured_at 前綴日期比對)每個 ftid 的快照。"""
    cur = conn.execute(
        "SELECT * FROM snapshot WHERE backend = ? AND captured_at = ?",
        (backend, captured_at),
    )
    return {r["ftid"]: r for r in cur.fetchall()}


def latest_snapshot_per_shop(conn: sqlite3.Connection, backend: str,
                             at: str) -> dict[str, sqlite3.Row]:
    cur = conn.execute(
        "SELECT * FROM snapshot WHERE backend = ? AND captured_at = ?",
        (backend, at),
    )
    return {r["ftid"]: r for r in cur.fetchall()}
