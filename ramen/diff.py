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


def hours_changed(a_raw: str | None, b_raw: str | None) -> bool:
    """兩份 opening_hours_json 是否真的不同:只比「兩邊都有的星期」。

    static 後端每天只回當天那一天(星期四那天只有星期四、星期五只有星期五),playwright 才回整週;
    直接比字串會把每家店天天標成變動。沒有共同星期 → 無法比 → 視為沒變。
    """
    if not a_raw or not b_raw:
        return False
    try:
        a = {str(d): list(spans) for d, spans in json.loads(a_raw)}
        b = {str(d): list(spans) for d, spans in json.loads(b_raw)}
    except (ValueError, TypeError):
        return a_raw != b_raw
    common = a.keys() & b.keys()
    return any(a[d] != b[d] for d in common)


def build_diff(conn: sqlite3.Connection, backend: str, date: str,
               current_at: str, seed: list[dict]) -> tuple[str, int]:
    """回傳 (markdown, 變動數)。current_at 是本次批次的 captured_at。"""
    cur = db.snapshots_at(conn, backend, current_at)
    # 每家店對「自己上一次成功快照」比(不限同批次):輪抓時批次間店家不重疊
    prev = db.previous_snapshots_per_shop(conn, backend, current_at)
    name_by_ftid = {s["ftid"]: s.get("name") for s in seed}
    compared = sum(1 for f, c in cur.items() if c["ok"] and f in prev)

    lines = [f"# 快照差異報告 — {backend} — {date}", ""]
    lines.append(f"- 本次批次:`{current_at}`(共 {len(cur)} 家)")
    lines.append(f"- 對比基準:各店自己上一次成功快照;本次有基準可比 {compared} 家")
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

    # 名稱/地址變動(upsert_shop 覆蓋主檔前偵測到的;不需要對比基準)
    shop_changes = db.shop_changes_at(conn, current_at)
    field_label = {"name": "名稱", "address": "地址"}
    lines.append(f"## 名稱/地址變動({len(shop_changes)})")
    lines += [f"- {name_by_ftid.get(r['ftid'], r['ftid'])}:{field_label.get(r['field'], r['field'])}"
              f" `{r['old']}` → `{r['new']}`" for r in shop_changes] or ["- 無"]
    lines.append("")

    if compared == 0:
        lines.append("## 變動")
        lines.append("- 本次店家皆為首次快照,無對比基準。")
        return "\n".join(lines) + "\n", len(shop_changes)

    changes = len(shop_changes)
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

        if hours_changed(p["opening_hours_json"], c["opening_hours_json"]):
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
