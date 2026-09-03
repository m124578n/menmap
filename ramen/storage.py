"""檔案路徑與 data/ 目錄結構。"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 專案根目錄的 data/(相對於本檔)
DATA = Path(__file__).resolve().parent.parent / "data"
SEED_FILE = DATA / "seed.json"
DB_FILE = DATA / "ramen.db"
RAW_DIR = DATA / "raw"
DIFF_DIR = DATA / "diff"
COMPARE_DIR = DATA / "compare"

TZ_TAIPEI = timezone(timedelta(hours=8))


def today_str() -> str:
    return datetime.now(TZ_TAIPEI).strftime("%Y-%m-%d")


def now_iso() -> str:
    return datetime.now(TZ_TAIPEI).strftime("%Y-%m-%dT%H:%M:%S%z")


def raw_path(date: str, backend: str, safe_id: str, ext: str) -> Path:
    p = RAW_DIR / date / backend
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{safe_id}.{ext}"


def write_raw(date: str, backend: str, safe_id: str, text: str, ext: str = "json") -> None:
    raw_path(date, backend, safe_id, ext).write_text(text, encoding="utf-8")


def load_seed() -> list[dict]:
    if not SEED_FILE.exists():
        return []
    return json.loads(SEED_FILE.read_text(encoding="utf-8"))


def save_seed(entries: list[dict]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    SEED_FILE.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
