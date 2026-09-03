"""兩後端當日快照對比:欄位覆蓋率、成功率、值不一致清單。

這是「哪個後端比較完整、穩定」的每日證據。
"""

from __future__ import annotations

import sqlite3

from . import db, storage

FIELDS = ["business_status", "opening_hours_json", "rating",
          "user_rating_count", "phone", "website", "price_text"]


def _latest_batch_at(conn: sqlite3.Connection, backend: str, date: str) -> str | None:
    cur = conn.execute(
        "SELECT captured_at FROM snapshot WHERE backend = ? "
        "AND captured_at LIKE ? ORDER BY captured_at DESC LIMIT 1",
        (backend, f"{date}%"),
    )
    row = cur.fetchone()
    return row["captured_at"] if row else None


def _coverage(rows: dict) -> dict:
    """各欄位非空比例(只計成功的快照)。"""
    ok_rows = [r for r in rows.values() if r["ok"]]
    n = len(ok_rows) or 1
    cov = {}
    for f in FIELDS:
        filled = sum(1 for r in ok_rows if r[f] not in (None, ""))
        cov[f] = filled / n
    rich = sum(1 for r in ok_rows if r["is_rich"]) / n
    return {"coverage": cov, "rich_rate": rich, "ok_count": len(ok_rows)}


def build_compare(conn: sqlite3.Connection, date: str, seed: list[dict]) -> str:
    name_by = {s["ftid"]: s.get("name") for s in seed}
    s_at = _latest_batch_at(conn, "static", date)
    p_at = _latest_batch_at(conn, "playwright", date)

    lines = [f"# 後端對比報告 — {date}", ""]
    if not s_at and not p_at:
        lines.append("- 今日尚無任何後端的快照。")
        return "\n".join(lines) + "\n"

    s_rows = db.snapshots_at(conn, "static", s_at) if s_at else {}
    p_rows = db.snapshots_at(conn, "playwright", p_at) if p_at else {}
    s_stat = _coverage(s_rows) if s_rows else None
    p_stat = _coverage(p_rows) if p_rows else None

    # 成功率
    lines.append("## 成功率")
    for label, rows in [("static", s_rows), ("playwright", p_rows)]:
        if not rows:
            lines.append(f"- {label}:今日無快照")
            continue
        ok = sum(1 for r in rows.values() if r["ok"])
        lines.append(f"- {label}:{ok}/{len(rows)} 成功")
    lines.append("")

    # 欄位覆蓋率表
    lines.append("## 欄位覆蓋率(成功快照中非空比例)")
    lines.append("")
    lines.append("| 欄位 | static | playwright |")
    lines.append("|---|---|---|")
    for f in FIELDS:
        sv = f"{s_stat['coverage'][f]:.0%}" if s_stat else "—"
        pv = f"{p_stat['coverage'][f]:.0%}" if p_stat else "—"
        lines.append(f"| {f} | {sv} | {pv} |")
    sr = f"{s_stat['rich_rate']:.0%}" if s_stat else "—"
    pr = f"{p_stat['rich_rate']:.0%}" if p_stat else "—"
    lines.append(f"| **完整版(is_rich)** | {sr} | {pr} |")
    lines.append("")

    # 值不一致清單(兩邊都成功的店)
    if s_rows and p_rows:
        common = set(s_rows) & set(p_rows)
        diffs = []
        for ftid in common:
            sr_, pr_ = s_rows[ftid], p_rows[ftid]
            if not (sr_["ok"] and pr_["ok"]):
                continue
            fld_diffs = []
            for f in ["business_status", "rating", "user_rating_count"]:
                if sr_[f] != pr_[f]:
                    fld_diffs.append(f"{f}: static={sr_[f]} / pw={pr_[f]}")
            if fld_diffs:
                diffs.append(f"- {name_by.get(ftid, ftid)}:" + "；".join(fld_diffs))
        lines.append(f"## 兩後端值不一致({len(diffs)})")
        lines += diffs or ["- 無(兩邊成功的店家關鍵欄位一致)"]
        lines.append("")

    return "\n".join(lines) + "\n"


def run_compare() -> int:
    seed = storage.load_seed()
    date = storage.today_str()
    conn = db.connect(storage.DB_FILE)
    md = build_compare(conn, date, seed)
    conn.close()
    storage.COMPARE_DIR.mkdir(parents=True, exist_ok=True)
    out = storage.COMPARE_DIR / f"{date}.md"
    out.write_text(md, encoding="utf-8")
    print(f"compare → {out}")
    return 0
