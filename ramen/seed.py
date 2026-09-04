"""Seed 建立與更新:搜尋雙北拉麵店、過濾、去重,產出 data/seed.json。

- `run_seed`:第一次建(整份寫入)。
- `refresh_seed`:合併更新(每週排程跑):新店追加並記 added_at(新店雷達用)、
  既有店更新名稱/地址/座標、搜不到的不刪只累計 missed 次數,並產出報告。
用靜態後端(快、可分頁)。
"""

from __future__ import annotations

import logging

from . import net, storage
from .dynamic_backend import place_url_for
from .schema import ShopDetail
from .static_backend import StaticBackend

log = logging.getLogger(__name__)

# 大範圍關鍵字 + 外圍行政區補強(內湖/士林/北投等在大範圍搜尋中被低估)
KEYWORDS = [
    "拉麵 台北市", "拉麵 新北市", "ラーメン 台北", "つけ麺 台北",
    # 台北外圍區
    "拉麵 內湖", "拉麵 士林", "拉麵 北投", "拉麵 文山", "拉麵 南港",
    # 新北各區
    "拉麵 板橋", "拉麵 中和", "拉麵 永和", "拉麵 新莊", "拉麵 三重",
    "拉麵 新店", "拉麵 汐止", "拉麵 樹林", "拉麵 土城", "拉麵 蘆洲",
    "拉麵 淡水", "拉麵 三峽",
]
MAX_TOTAL = 1000  # 實務上會在關鍵字自然枯竭前遠低於此
PAGE_SIZE = 20
MAX_PAGES = 6  # 每關鍵字最多翻幾頁(20×6=120)

# --- 過濾 ---
# 非餐廳的整體場域
NAME_BLOCKLIST = ["百貨", "美食街", "商場", "outlet", "Mall", "廣場", "夜市"]
# 名稱含這些字 → 台式/中式麵食,無論類別一律排除
NOISE_NAME = ["刀削麵", "刀切麵", "刀削", "牛肉麵", "牛肉拉麵", "蘭州",
              "湯餃", "水餃", "牛大娘", "腸粉", "木須", "清燉牛", "麵館", "麵線", "麺線"]
# 類別:台式/中式訊號,出現即排除(日式拉麵店不會帶這些)
CN_TYPES = ["中式麵食店", "中菜館", "台灣餐廳"]
# 類別明確是拉麵店 → 直接接受(名稱帶定食/丼飯也是拉麵店,例:十三川日本拉麵定食)
RAMEN_TYPES = ["拉麵店", "ラーメン屋"]
# 類別不明確時,靠名稱的日式拉麵訊號;「麺」單字太弱(麺線)不算
RAMEN_HINTS = ["拉麵", "ラーメン", "ramen", "らーめん", "らあめん", "中華そば",
               "つけ麺", "つけめん", "沾麵", "油そば", "家系", "豚骨", "麵屋", "麺屋"]
# 類別不明確、只靠名稱時,名稱同時帶這些副品項就不收(咖哩店順便賣拉麵之類)
SIDE_ITEMS = ["咖哩", "丼飯", "蓋飯", "蛋包飯", "壽司", "燒肉", "居酒屋", "串燒",
              "烏龍麵", "烏冬", "讚岐", "定食", "彌生軒", "火鍋"]
# 註:只有「日本餐廳/日式」類別、名稱又沒拉麵訊號的一律不收——那是壽司/定食/居酒屋
# (2026-09-04 refresh 實測:光靠「日本餐廳」會混進彌生軒、丸亀製麵、大戶屋)

# 雙北地區守門:關鍵字帶「台北」時 Google 會摻入外縣市結果
TAIPEI_DISTRICTS = ["中正", "大同", "中山", "松山", "大安", "萬華",
                    "信義", "士林", "北投", "內湖", "南港", "文山"]
NEW_TAIPEI_DISTRICTS = [
    "板橋", "三重", "中和", "永和", "新莊", "新店", "樹林", "鶯歌", "三峽",
    "淡水", "汐止", "瑞芳", "土城", "蘆洲", "五股", "泰山", "林口", "深坑",
    "石碇", "坪林", "三芝", "石門", "八里", "平溪", "雙溪", "貢寮", "金山",
    "萬里", "烏來"]
TWIN_DISTRICTS = [d + "區" for d in TAIPEI_DISTRICTS + NEW_TAIPEI_DISTRICTS]
# 明確排除的其他縣市(避免同名行政區誤收,例如基隆也有中山區)
OTHER_CITIES = ["基隆市", "桃園市", "新竹", "苗栗", "台中市", "臺中市", "彰化",
                "南投", "雲林", "嘉義", "台南市", "臺南市", "高雄市", "屏東",
                "宜蘭", "花蓮", "台東", "臺東", "澎湖", "金門", "連江"]


def _in_twin_cities(address: str | None) -> bool:
    a = address or ""
    if any(c in a for c in OTHER_CITIES):
        return False
    if "臺北市" in a or "台北市" in a or "新北市" in a:
        return True
    # 地址偶爾只寫「台灣內湖區/淡水區」不帶市名,靠雙北行政區名補認
    return any(d in a for d in TWIN_DISTRICTS)


def looks_like_ramen(name: str | None, types: list[str] | None) -> bool:
    """過濾規則(seed 建立與每週 refresh 共用;既有 seed 也用它清雜訊)。"""
    name = name or ""
    joined = " ".join(types or [])

    # 1) 明確排除:場域、台式麵食(名稱或類別),即使掛了「拉麵店」也是台式店
    if any(b.lower() in name.lower() for b in NAME_BLOCKLIST):
        return False
    if any(n in name for n in NOISE_NAME):
        return False
    if any(c in joined for c in CN_TYPES):
        return False
    # 2) 類別明確是拉麵店 → 收
    if any(t in joined for t in RAMEN_TYPES):
        return True
    # 3) 類別不明確:名稱要有拉麵訊號,且不是「副品項店順便賣拉麵」
    if any(h.lower() in name.lower() for h in RAMEN_HINTS):
        return not any(s in name for s in SIDE_ITEMS)
    return False


def _looks_like_ramen(d: ShopDetail) -> bool:
    return looks_like_ramen(d.name, d.types)


def search_all() -> dict[str, ShopDetail]:
    """跑完所有關鍵字搜尋,回傳通過過濾的店(ftid → 搜尋結果)。"""
    backend = StaticBackend()
    seen: dict[str, ShopDetail] = {}
    for kw in KEYWORDS:
        log.info("搜尋關鍵字:%s", kw)
        for page in range(MAX_PAGES):
            if len(seen) >= MAX_TOTAL:
                break
            offset = page * PAGE_SIZE
            try:
                results, _, _ = backend.search(kw, offset=offset)
            except Exception as e:  # noqa: BLE001
                log.warning("  第 %d 頁失敗:%s", page + 1, e)
                break
            new = 0
            for r in results:
                if r.ftid in seen:
                    continue
                if not _looks_like_ramen(r):
                    continue
                if not _in_twin_cities(r.address):
                    continue
                seen[r.ftid] = r
                new += 1
            log.info("  第 %d 頁:%d 筆結果,新增 %d(累計 %d)",
                     page + 1, len(results), new, len(seen))
            if not results:
                break
            net.polite_sleep()
        if len(seen) >= MAX_TOTAL:
            break
    return seen


def _entry(d: ShopDetail, added_at: str) -> dict:
    return {
        "ftid": d.ftid,
        "name": d.name,
        "address": d.address,
        "lat": d.lat,
        "lng": d.lng,
        "types": d.types,
        "place_id": d.place_id,
        "gid": d.req_ids.get("gid"),
        "maps_url": place_url_for(d.ftid, d.name or "", lat=d.lat, lng=d.lng,
                                  gid=d.req_ids.get("gid"), place_id=d.place_id),
        "added_at": added_at,
    }


def build_seed() -> list[dict]:
    added_at = storage.now_iso()
    return [_entry(d, added_at) for d in search_all().values()]


# 既有店家會被搜尋結果更新的欄位(added_at 不動,新店雷達才準)
_UPDATABLE = ("name", "address", "lat", "lng", "types", "place_id", "gid", "maps_url")


def merge_seed(existing: list[dict], found: dict[str, ShopDetail],
               now: str, not_ramen: set[str] | None = None) -> tuple[list[dict], dict]:
    """把搜尋結果合併進既有 seed。回傳 (新 seed, 報告資料)。純函式,方便測試。

    - 新 ftid:追加(排在最後),added_at = now
    - 既有:更新 _UPDATABLE 欄位(搜尋結果為空的欄位不覆蓋),missed 歸零
    - 這次沒搜到:保留,missed += 1(不刪:搜尋排名浮動,不代表倒了;
      倒了會由每日快照的 CLOSED_PERMANENTLY 反映)
    """
    by = {e["ftid"]: dict(e) for e in existing}
    new, renamed, moved = [], [], []
    for ftid, d in found.items():
        e = _entry(d, now)
        old = by.get(ftid)
        if old is None:
            by[ftid] = e
            new.append(e)
            continue
        if d.name and old.get("name") and d.name != old["name"]:
            renamed.append((old["name"], d.name, ftid))
        if d.address and old.get("address") and d.address != old["address"]:
            moved.append((d.name or old["name"], old["address"], d.address, ftid))
        for k in _UPDATABLE:
            if e.get(k) not in (None, "", []):
                old[k] = e[k]
        old["missed"] = 0
    missing = []
    for ftid, old in by.items():
        if ftid not in found:
            old["missed"] = int(old.get("missed") or 0) + 1
            missing.append(old)
    # 過濾規則會演進:不符現行規則的(含既有的)一律移除並列在報告,seed 在 git 可回溯
    pruned = [e for e in by.values() if not looks_like_ramen(e.get("name"), e.get("types"))]
    # LLM 分類判定「非日式拉麵店」(台式麵/泡麵店/韓式/煎餃為主…)的也移除(scripts/classify_types.py 的 is_ramen)
    pruned += [e for e in by.values() if e["ftid"] in (not_ramen or set())
               and looks_like_ramen(e.get("name"), e.get("types"))]
    for e in pruned:
        by.pop(e["ftid"])
    new = [e for e in new if e["ftid"] in by]
    missing = [e for e in missing if e["ftid"] in by]
    report = {"found": len(found), "new": new, "renamed": renamed,
              "moved": moved, "missing": missing, "pruned": pruned, "total": len(by)}
    return list(by.values()), report


def _refresh_report(date: str, now: str, r: dict) -> str:
    L = [f"# Seed 更新報告 — {date}", "",
         f"- 執行:`{now}`;搜尋命中 {r['found']} 家;seed 共 {r['total']} 家", ""]
    L.append(f"## 新收錄({len(r['new'])})")
    L += [f"- {e['name']}({e.get('address') or '?'})<{e['maps_url']}>" for e in r["new"]] or ["- 無"]
    L.append("")
    L.append(f"## 改名({len(r['renamed'])})")
    L += [f"- `{a}` → `{b}`(`{f}`)" for a, b, f in r["renamed"]] or ["- 無"]
    L.append("")
    L.append(f"## 地址變動({len(r['moved'])})")
    L += [f"- {n}:`{a}` → `{b}`(`{f}`)" for n, a, b, f in r["moved"]] or ["- 無"]
    L.append("")
    stale = sorted((e for e in r["missing"] if e.get("missed", 0) >= 3),
                   key=lambda e: -e["missed"])
    L.append(f"## 本次搜尋未出現({len(r['missing'])};連續 ≥3 次者列出 {len(stale)})")
    L += [f"- {e['name']}(連續 {e['missed']} 次)" for e in stale] or ["- 無"]
    L.append("")
    L.append(f"## 移除:不符過濾規則或 LLM 判定非日式拉麵({len(r['pruned'])})")
    L += [f"- {e['name']} | {'、'.join(e.get('types') or [])}" for e in r["pruned"]] or ["- 無"]
    L.append("")
    return "\n".join(L) + "\n"


def _llm_not_ramen() -> set[str]:
    """shop 表裡被 LLM 分類判定為非日式拉麵店的 ftid(llm_is_ramen = 0)。"""
    import sqlite3
    if not storage.DB_FILE.exists():
        return set()
    conn = sqlite3.connect(storage.DB_FILE)
    try:
        return {r[0] for r in conn.execute("SELECT ftid FROM shop WHERE llm_is_ramen = 0")}
    except sqlite3.OperationalError:
        return set()
    finally:
        conn.close()


def refresh_seed() -> int:
    existing = storage.load_seed()
    if not existing:
        raise SystemExit("seed.json 不存在,先跑 `ramen seed` 建立")
    now = storage.now_iso()
    date = now[:10]
    found = search_all()
    if len(found) < len(existing) * 0.5:
        # 搜尋大面積失敗(被擋/改版)時不要把整份 seed 的 missed 全灌上去
        log.error("搜尋只命中 %d 家(seed 有 %d),疑似被擋或格式改版;seed 不變更",
                  len(found), len(existing))
        print(f"seed refresh 中止:只搜到 {len(found)} 家(seed {len(existing)})")
        return 1
    not_ramen = _llm_not_ramen()
    merged, report = merge_seed(existing, found, now, not_ramen)
    storage.save_seed(merged)
    storage.DIFF_DIR.mkdir(parents=True, exist_ok=True)
    out = storage.DIFF_DIR / f"{date}-seed.md"
    out.write_text(_refresh_report(date, now, report), encoding="utf-8")
    print(f"seed refresh:搜到 {report['found']} 家;新收錄 {len(report['new'])}、"
          f"改名 {len(report['renamed'])}、地址變動 {len(report['moved'])}、"
          f"未出現 {len(report['missing'])}、移除 {len(report['pruned'])};"
          f"seed 共 {report['total']} 家")
    print(f"報告 → {out}")
    return 0


def run_seed(force: bool = False) -> int:
    existing = storage.load_seed()
    if existing and not force:
        log.warning("seed.json 已存在(%d 筆);要覆蓋請加 --force", len(existing))
        print(f"seed.json 已有 {len(existing)} 筆,未變更(--force 可覆蓋)")
        return len(existing)
    entries = build_seed()
    storage.save_seed(entries)
    print(f"seed 完成:{len(entries)} 家拉麵店 → {storage.SEED_FILE}")
    return len(entries)
