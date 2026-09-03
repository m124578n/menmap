"""快照差異比對:與同後端上一次成功快照比,產出 Markdown 報告。"""

from __future__ import annotations

import json
import sqlite3

from . import db, storage

CLOSED = {"CLOSED_TEMPORARILY", "CLOSED_PERMANENTLY"}


def _hours_readable(raw: str | None) -> str:
    if not raw:
        return "—"
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return raw
    return "；".join(f"{d}: {'/'.join(spans) or '休'}" for d, spans in data)


def build_diff(conn: sqlite3.Connection, backend: str, date: str,
               current_at: str, seed: list[dict]) -> tuple[str, int]:
    """回傳 (markdown, 變動數)。current_at 是本次批次的 captured_at。"""
    prev_at = db.previous_snapshot_time(conn, backend, current_at)
    cur = db.snapshots_at(conn, backend, current_at)
    name_by_ftid = {s["ftid"]: s.get("name") for s in seed}

    lines = [f"# 快照差異報告 — {backend} — {date}", ""]
    lines.append(f"- 本次批次:`{current_at}`")
    lines.append(f"- 對比批次:`{prev_at or '(無,首次快照)'}`")
    lines.append("")

    # 失敗清單
    failed = [(f, s) for f, s in cur.items() if not s["ok"]]
    lines.append(f"## 本次失敗({len(failed)})")
    if failed:
        for f, s in failed:
            lines.append(f"- {name_by_ftid.get(f, f)}(`{f}`):{s['error']}")
    else:
        lines.append("- 無")
    lines.append("")

    if prev_at is None:
        lines.append("## 變動")
        lines.append("- 首次快照,無對比基準。")
        return "\n".join(lines) + "\n", 0

    prev = db.snapshots_at(conn, backend, prev_at)
    changes = 0
    status_lines, hours_lines, rating_lines = [], [], []

    for ftid, c in cur.items():
        if not c["ok"]:
            continue
        p = prev.get(ftid)
        if p is None or not p["ok"]:
            continue
        nm = name_by_ftid.get(ftid, ftid)

        if c["business_status"] != p["business_status"]:
            flag = " ⚠️" if c["business_status"] in CLOSED else ""
            status_lines.append(
                f"- {nm}:`{p['business_status']}` → `{c['business_status']}`{flag}")
            changes += 1

        if c["opening_hours_json"] != p["opening_hours_json"]:
            hours_lines.append(
                f"- {nm}\n    - 舊:{_hours_readable(p['opening_hours_json'])}"
                f"\n    - 新:{_hours_readable(c['opening_hours_json'])}")
            changes += 1

        if (c["rating"] != p["rating"]
                or c["user_rating_count"] != p["user_rating_count"]):
            rating_lines.append(
                f"- {nm}:評分 {p['rating']}→{c['rating']}、"
                f"評論數 {p['user_rating_count']}→{c['user_rating_count']}")
            changes += 1

    lines.append(f"## 營業狀態變動({len(status_lines)})")
    lines += status_lines or ["- 無"]
    lines.append("")
    lines.append(f"## 營業時間變動({len(hours_lines)})")
    lines += hours_lines or ["- 無"]
    lines.append("")
    lines.append(f"## 評分/評論數變動({len(rating_lines)})")
    lines += rating_lines or ["- 無"]
    lines.append("")
    return "\n".join(lines) + "\n", changes


def write_diff(conn: sqlite3.Connection, backend: str, date: str,
               current_at: str, seed: list[dict]) -> tuple[str, int]:
    md, changes = build_diff(conn, backend, date, current_at, seed)
    storage.DIFF_DIR.mkdir(parents=True, exist_ok=True)
    out = storage.DIFF_DIR / f"{date}-{backend}.md"
    out.write_text(md, encoding="utf-8")
    return str(out), changes
