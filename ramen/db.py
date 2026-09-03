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
    first_seen  TEXT,
    last_seen   TEXT
);

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


def connect(db_path: str | Path) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_shop(conn: sqlite3.Connection, d: ShopDetail, now: str) -> None:
    conn.execute(
        """
        INSERT INTO shop (ftid, name, address, lat, lng, phone, website,
                          place_id, cover_photo, first_seen, last_seen)
        VALUES (:ftid, :name, :address, :lat, :lng, :phone, :website,
                :place_id, :cover_photo, :now, :now)
        ON CONFLICT(ftid) DO UPDATE SET
            name = COALESCE(excluded.name, shop.name),
            address = COALESCE(excluded.address, shop.address),
            lat = COALESCE(excluded.lat, shop.lat),
            lng = COALESCE(excluded.lng, shop.lng),
            phone = COALESCE(excluded.phone, shop.phone),
            website = COALESCE(excluded.website, shop.website),
            place_id = COALESCE(excluded.place_id, shop.place_id),
            cover_photo = COALESCE(excluded.cover_photo, shop.cover_photo),
            last_seen = excluded.last_seen
        """,
        {**{k: d.to_dict().get(k) for k in
            ("ftid", "name", "address", "lat", "lng", "phone", "website",
             "place_id", "cover_photo")}, "now": now},
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
