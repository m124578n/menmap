-- D1 schema，沿用採集端 ramen/db.py。家裡的 publish 步驟寫入,Worker 唯讀。

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
    categories_json TEXT,      -- LLM 拉麵種類分類(JSON 陣列,主打在前)
    beginner_friendly INTEGER, -- 1/0/NULL 入門友善
    classified_at TEXT,
    classify_model TEXT,
    first_seen  TEXT,
    last_seen   TEXT
);

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

CREATE INDEX IF NOT EXISTS idx_snapshot_shop ON snapshot (ftid, captured_at);
CREATE INDEX IF NOT EXISTS idx_review_shop ON review (ftid, backend);
