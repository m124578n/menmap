"""用 LLM 把每家店分類成拉麵種類(豚骨/雞白湯/醬油…多標籤),寫回 data/ramen.db 的 shop 表。

    uv run python scripts/classify_types.py --limit 5        # 試跑 5 家(只印結果,不寫入)
    uv run python scripts/classify_types.py --limit 5 --write
    uv run python scripts/classify_types.py --write                 # 每日排程用:沒分類過的 + 之前資料不足(其他)但有新評論的
    uv run python scripts/classify_types.py --write --mode stale    # 也重跑「分類後評論有更新」的店
    uv run python scripts/classify_types.py --write --mode all      # 全部重跑

金鑰從專案根目錄 .env 讀(已 gitignore):
- Foundry:ANTHROPIC_FOUNDRY_API_KEY + ANTHROPIC_FOUNDRY_RESOURCE(資源名或整段 endpoint)
- 或第一方:ANTHROPIC_API_KEY
- ANTHROPIC_MODEL(預設 claude-opus-5)

輸入:店名、Google 類別、價格帶、商家貼文(≤3)、最新評論(≤10)。
輸出:is_ramen(是否日式拉麵店;false 會從地圖與 seed 移除)、categories(1~3 個,主打在前)、
beginner_friendly(入門友善 bool|null)、reason(短句)。
用 tool 強制 JSON 結構;Foundry 的 strict 是 beta,失敗就退回非 strict。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "ramen.db"
ENV = ROOT / ".env"
TZ = timezone(timedelta(hours=8))

# 標籤清單(前端篩選用;改這裡要同步改 web 的 CATEGORY 對照)
CATEGORIES = [
    "豚骨", "雞白湯", "醬油", "鹽味", "味噌", "魚介煮干", "蝦", "家系", "二郎系",
    "沾麵", "油拌麵", "擔擔麵", "辣味", "蔬食", "其他",
]

SYSTEM = f"""你是台灣拉麵店的分類專家。我會給你一家雙北拉麵店在 Google 地圖上的資料:店名、類別、價格帶、商家貼文、最新評論。

任務:先判斷這家店是不是「日式拉麵店」,再判斷「主打」的拉麵種類,以及是否對拉麵新手友善。

是否日式拉麵店(is_ramen):主力品項是日式拉麵(含沾麵、油拌麵)才算 true。以下一律 false:
台式牛肉麵/羊肉麵/魚麵/羹麵、泡麵自助店或無人泡麵店、韓式拉麵、以煎餃/丼飯/咖哩/定食為主而拉麵只是副品項、
烏龍麵/蕎麥麵店。資料太少無法判斷時給 true(寧可保留)。

分類規則:
- 只能用這些標籤:{"、".join(CATEGORIES)}
- 給 1~3 個,最主要的放第一個。多數店 1~2 個就夠,第 3 個只在真的並列主打時才給,不要為了湊滿而加。只標「店家實際供應的主力品項」;評論裡拿別家比較、或只是順口提到的湯頭不算。
- 標籤定義:豚骨(含博多/久留米等豬骨白湯)、雞白湯(雞骨白湯)、醬油(清湯醬油/東京系/淡麗系)、鹽味(塩ラーメン)、味噌(含北海道味噌)、魚介煮干(魚介/小魚乾/鯛魚/雞魚雙湯以魚介為主)、蝦(蝦湯頭,如一幻)、家系(横浜家系豚骨醬油)、二郎系(蒜山、大份量)、沾麵(つけ麺為主打)、油拌麵(油そば/まぜそば/乾拌)、擔擔麵(日式擔擔)、辣味(以辣為主打)、蔬食(素食/植物性湯頭)、其他(拉麵但資料無法歸到上述任一)。
- 資料太少無法判斷時 categories 給 ["其他"],reason 說明資料不足。

入門友善(beginner_friendly):口味大眾、點餐直覺、不需特殊儀式或長時間排隊、環境友善;資料不足就 null。

不要編造資料裡沒有的東西。reason 用繁體中文一句話(不超過 40 字)說明判斷依據。"""

TOOL = {
    "name": "classify_ramen_shop",
    "description": "回報這家拉麵店的分類結果",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_ramen": {"type": "boolean", "description": "主力品項是日式拉麵才 true;台式麵、泡麵店、韓式、煎餃/丼飯為主等給 false"},
            "categories": {
                "type": "array",
                "items": {"type": "string", "enum": CATEGORIES},
                "description": "主打種類 1~3 個,最主要的在前(strict 模式不吃 minItems/maxItems,程式端再截)",
            },
            "beginner_friendly": {
                "type": ["boolean", "null"],
                "description": "是否對拉麵新手友善;資料不足給 null",
            },
            "reason": {"type": "string", "description": "一句話說明判斷依據(≤40 字)"},
        },
        "required": ["is_ramen", "categories", "beginner_friendly", "reason"],
        "additionalProperties": False,
    },
}


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k.startswith("ANTHROPIC_")})
    return env


def make_client(env: dict[str, str]):
    import anthropic

    if env.get("ANTHROPIC_FOUNDRY_API_KEY"):
        res = env.get("ANTHROPIC_FOUNDRY_RESOURCE", "")
        if res.startswith("http"):
            # 使用者可能貼整段 endpoint:https://<resource>.services.ai.azure.com/anthropic/
            base = res.rstrip("/")
            if not base.endswith("/anthropic"):
                base = base + "/anthropic"
            return anthropic.AnthropicFoundry(api_key=env["ANTHROPIC_FOUNDRY_API_KEY"], base_url=base, max_retries=6), "foundry"
        if not res:
            sys.exit("ANTHROPIC_FOUNDRY_RESOURCE 沒填(資源名或 endpoint)")
        return anthropic.AnthropicFoundry(api_key=env["ANTHROPIC_FOUNDRY_API_KEY"], resource=res, max_retries=6), "foundry"
    if env.get("ANTHROPIC_API_KEY"):
        return anthropic.Anthropic(api_key=env["ANTHROPIC_API_KEY"], max_retries=6), "anthropic"
    sys.exit("找不到金鑰:在 .env 填 ANTHROPIC_FOUNDRY_API_KEY(+RESOURCE)或 ANTHROPIC_API_KEY")


# ---------------------------------------------------------------------------
# 資料
# ---------------------------------------------------------------------------
def _short(t: str | None, n: int) -> str:
    t = re.sub(r"\s+", " ", (t or "")).strip()
    return t if len(t) <= n else t[:n] + "…"


def load_shops(conn: sqlite3.Connection, *, mode: str, limit: int | None,
               ftids: list[str] | None) -> list[dict]:
    """mode: unclassified(沒分類過的 + 之前資料不足標「其他」但現在有新評論的)/ stale(加上評論有更新的)/ all(全部)。"""
    seed = json.loads((ROOT / "data" / "seed.json").read_text(encoding="utf-8"))
    seed_ids = [e["ftid"] for e in seed]
    types_by = {e["ftid"]: e.get("types") or [] for e in seed}
    out = []
    for ftid in seed_ids:
        if ftids and ftid not in ftids:
            continue
        shop = conn.execute("SELECT * FROM shop WHERE ftid = ?", (ftid,)).fetchone()
        if not shop:
            continue
        reviews = conn.execute(
            """SELECT author, stars, date_rel, text, captured_at FROM review
               WHERE ftid = ? AND text IS NOT NULL AND text != ''
               ORDER BY captured_at DESC, seq ASC LIMIT 10""", (ftid,)).fetchall()
        if shop["classified_at"] and mode == "other":
            if shop["categories_json"] != '["其他"]':
                continue  # other 模式:只重跑目前標「其他」的店(補 is_ramen 旗標用)
        elif shop["classified_at"] and mode != "all":
            newest_review = max((r["captured_at"] for r in reviews), default="")
            if newest_review <= shop["classified_at"]:
                continue  # 分類後沒有新評論,重跑也不會變
            if mode == "unclassified" and shop["categories_json"] != '["其他"]':
                continue  # unclassified 模式只補「當時資料不足被標其他、現在有新評論」的店
        posts = conn.execute(
            "SELECT text FROM post WHERE ftid = ? AND text IS NOT NULL ORDER BY ts DESC LIMIT 3",
            (ftid,)).fetchall()
        snap = conn.execute(
            """SELECT price_text FROM snapshot WHERE ftid = ? AND ok = 1 AND price_text IS NOT NULL
               ORDER BY captured_at DESC LIMIT 1""", (ftid,)).fetchone()
        out.append({
            "ftid": ftid,
            "name": shop["name"],
            "types": types_by.get(ftid, []),
            "price": snap["price_text"] if snap else None,
            "posts": [_short(p["text"], 200) for p in posts],
            "reviews": [{"stars": r["stars"], "when": r["date_rel"], "text": _short(r["text"], 300)}
                        for r in reviews],
        })
        if limit and len(out) >= limit:
            break
    return out


def user_prompt(s: dict) -> str:
    L = [f"店名:{s['name']}", f"Google 類別:{'、'.join(s['types']) or '(無)'}",
         f"價格帶:{s['price'] or '(無)'}"]
    if s["posts"]:
        L.append("商家貼文:")
        L += [f"- {p}" for p in s["posts"]]
    if s["reviews"]:
        L.append(f"最新評論({len(s['reviews'])} 則):")
        L += [f"- [{r['stars']}★ {r['when'] or ''}] {r['text']}" for r in s["reviews"]]
    else:
        L.append("最新評論:(尚未抓到)")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# 呼叫
# ---------------------------------------------------------------------------
def classify_one(client, model: str, s: dict, *, strict: bool) -> tuple[dict, dict]:
    tool = dict(TOOL)
    if strict:
        tool["strict"] = True
    resp = client.messages.create(
        model=model,
        max_tokens=512,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=[tool],
        tool_choice={"type": "tool", "name": TOOL["name"]},
        messages=[{"role": "user", "content": user_prompt(s)}],
    )
    result = None
    for block in resp.content:
        if block.type == "tool_use" and block.name == TOOL["name"]:
            result = block.input if isinstance(block.input, dict) else json.loads(block.input)
    if result is None:
        text = "".join(b.text for b in resp.content if b.type == "text")
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise RuntimeError(f"沒有拿到結構化結果:{text[:200]}")
        result = json.loads(m.group(0))
    cats = [c for c in result.get("categories", []) if c in CATEGORIES][:3] or ["其他"]
    result["categories"] = cats
    result["is_ramen"] = bool(result.get("is_ramen", True))
    u = resp.usage
    usage = {"in": u.input_tokens, "out": u.output_tokens,
             "cache_r": getattr(u, "cache_read_input_tokens", 0) or 0,
             "cache_w": getattr(u, "cache_creation_input_tokens", 0) or 0}
    return result, usage


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--write", action="store_true", help="寫回 shop 表(預設只印)")
    ap.add_argument("--mode", choices=["unclassified", "stale", "other", "all"], default="unclassified",
                    help="unclassified=只跑沒分類過的(預設);stale=加上評論有更新的;all=全部重跑")
    ap.add_argument("--ftid", action="append", help="只跑指定店(可重複)")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    env = load_env()
    client, provider = make_client(env)
    model = env.get("ANTHROPIC_MODEL") or "claude-opus-5"
    print(f"provider={provider} model={model}")

    sys.path.insert(0, str(ROOT))
    from ramen import db as rdb  # 用採集端的 connect:會補 shop 表的新欄位
    conn = rdb.connect(DB)
    shops = load_shops(conn, mode=a.mode, limit=a.limit, ftids=a.ftid)
    print(f"待分類 {len(shops)} 家(mode={a.mode})")
    if not shops:
        return

    # 先單獨跑第一家,確認 strict 在這個平台可用;不行就退回非 strict
    strict = True
    try:
        classify_one(client, model, shops[0], strict=True)
    except Exception as e:  # noqa: BLE001
        print(f"strict 模式失敗({type(e).__name__}: {str(e)[:120]}),改用非 strict")
        strict = False

    total = {"in": 0, "out": 0, "cache_r": 0, "cache_w": 0}
    done = failed = 0
    now = datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S%z")
    t0 = time.time()

    def work(s):
        return s, classify_one(client, model, s, strict=strict)

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(work, s) for s in shops]
        for f in as_completed(futs):
            try:
                s, (r, u) = f.result()
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(f"!! 失敗:{type(e).__name__}: {str(e)[:160]}")
                continue
            done += 1
            for k in total:
                total[k] += u[k]
            bf = {True: "入門友善", False: "非入門", None: "?"}[r.get("beginner_friendly")]
            flag = "" if r["is_ramen"] else " ⚠️非日式拉麵"
            print(f"[{done}/{len(shops)}] {s['name']} → {'/'.join(r['categories'])} | {bf}{flag} | {r.get('reason','')}")
            if a.write:
                conn.execute(
                    """UPDATE shop SET categories_json = ?, beginner_friendly = ?, llm_is_ramen = ?,
                       classified_at = ?, classify_model = ? WHERE ftid = ?""",
                    (json.dumps(r["categories"], ensure_ascii=False),
                     None if r.get("beginner_friendly") is None else int(bool(r["beginner_friendly"])),
                     int(r["is_ramen"]), now, model, s["ftid"]))
                conn.commit()

    dt = time.time() - t0
    print(f"\n完成 {done} 家、失敗 {failed};{dt:.0f} 秒")
    print(f"token:input {total['in']:,}(cache 讀 {total['cache_r']:,} / 寫 {total['cache_w']:,})、output {total['out']:,}")
    if not a.write:
        print("(試跑,未寫入;加 --write 才會寫回 shop 表)")


if __name__ == "__main__":
    main()
