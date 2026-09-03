"""Google Maps 內部 JSON(位置型陣列)解析。

兩個來源共用同一套「place array」結構:
- 詳情 XHR(/maps/preview/place)回應的 data[6]
- 搜尋 XHR(/search?tbm=map)回應的 data[64][i][1]

索引以 2026-09 實際抓取的回應為準(見 README 維護章節);Google 改版時
只需要修這個檔案。
"""

from __future__ import annotations

import json
import re
from typing import Any

from .schema import ShopDetail

# --- place array 欄位索引(集中管理,斷了好修) ---
IDX_NAME = 11
IDX_FTID = 10
IDX_ADDRESS = 39          # 全形完整地址字串
IDX_COORDS = 9            # [_, _, lat, lng]
IDX_RATING_BLOCK = 4      # [.., [3]=reviews url block, [7]=rating, [8]=count]
IDX_WEBSITE = 7           # [url, display, ...]
IDX_PHONE = 178           # [[formatted, .., .., raw digits], ...]
IDX_HOURS = 203           # [[[day, num, [y,m,d], [[range,..]], ..], ...], ...]
IDX_TYPES = 13            # ["拉麵店", ...]
IDX_REVIEWS = 175         # [9][0][0] = 評論列表
IDX_COVER = 72            # [[[..., [url,...]]]] 封面照
IDX_GID = 89              # "/g/..." 知識圖譜 id
IDX_S6 = (181, 5)         # 詳情請求 pb 需要的店家識別碼
IDX_S7 = (181, 6)
IDX_POSTS = 122           # [1] = 商家貼文列表
MENU_BLOCKS = (105, 171)  # 「菜單」相片分類可能出現的區塊(巢狀位置會浮動)

_PLACE_ID_RE = re.compile(r"placeid=(ChIJ[\w-]+)")
_WEEK_ORDER = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def sort_week(hours: list) -> list:
    """把 [[星期名, spans], ...] 固定排成星期一~星期日;認不得的名稱排最後、維持原順序。"""
    def rank(item):
        try:
            return _WEEK_ORDER.index(item[0])
        except ValueError:
            return 99
    return sorted(hours, key=rank)  # sorted 是穩定排序
_PRICE_RE = re.compile(r"^\$[\d$]*(?:[–\-][\d,]+)?$")


def _get(node: Any, *path: int) -> Any:
    """安全取巢狀索引,任何一層不存在就回 None。"""
    for i in path:
        if not isinstance(node, list) or i >= len(node):
            return None
        node = node[i]
    return node


def parse_place_array(p: list, *, raw_text: str | None = None) -> ShopDetail:
    """把一個 place array 解析成 ShopDetail。缺欄位一律 None,不丟例外。"""
    ftid = _get(p, IDX_FTID) or ""
    d = ShopDetail(ftid=ftid)
    d.name = _get(p, IDX_NAME)
    d.address = _get(p, IDX_ADDRESS)
    d.lat = _get(p, IDX_COORDS, 2)
    d.lng = _get(p, IDX_COORDS, 3)
    d.rating = _get(p, IDX_RATING_BLOCK, 7)
    d.user_rating_count = _get(p, IDX_RATING_BLOCK, 8)
    if d.user_rating_count is None:
        # 有些回應 [4][8] 是 null,但 [4][3][1] 有 "13,467 篇評論" 字串
        txt = _get(p, IDX_RATING_BLOCK, 3, 1)
        if isinstance(txt, str):
            m = re.search(r"([\d,]+)", txt)
            if m:
                d.user_rating_count = int(m.group(1).replace(",", ""))
    d.website = _get(p, IDX_WEBSITE, 0)
    d.phone = _get(p, IDX_PHONE, 0, 0)
    types = _get(p, IDX_TYPES)
    d.types = [t for t in types if isinstance(t, str)] if isinstance(types, list) else []

    # place_id 藏在評論連結 querystring 裡
    reviews_url = _get(p, IDX_RATING_BLOCK, 3, 0)
    if isinstance(reviews_url, str):
        m = _PLACE_ID_RE.search(reviews_url)
        if m:
            d.place_id = m.group(1)

    # 營業時間:[[day_name, day_num, [y,m,d], [["11:00–04:00", ...]], ...], ...]
    hours_block = _get(p, IDX_HOURS, 0)
    if isinstance(hours_block, list):
        parsed = []
        for entry in hours_block:
            day = _get(entry, 0)
            ranges = entry[3] if isinstance(_get(entry, 3), list) else []
            spans = [r[0] for r in ranges if isinstance(r, list) and r and isinstance(r[0], str)]
            if isinstance(day, str):
                parsed.append([day, spans])
        if parsed:
            # Google 回傳是從「抓取當天」開始排的一週;固定成星期一~星期日,入庫才一致
            d.opening_hours = sort_week(parsed)

    # 營業狀態:正常時沒有明確欄位,關店時整包 JSON 會出現標記字串
    scan = raw_text if raw_text is not None else json.dumps(p, ensure_ascii=False)
    if "永久停業" in scan:
        d.business_status = "CLOSED_PERMANENTLY"
    elif "暫停營業" in scan:
        d.business_status = "CLOSED_TEMPORARILY"
    else:
        d.business_status = "OPERATIONAL"

    # 價位:沒有固定淺層索引,掃字串找 "$100–200"/"$$" 形式
    for s in _iter_strings(p, max_depth=4):
        if _PRICE_RE.match(s):
            d.price_text = s
            break

    # 封面照
    cover = _get(p, IDX_COVER, 0, 0, 6, 0)
    if isinstance(cover, str) and cover.startswith("http"):
        d.cover_photo = cover

    # 評論(完整版回應才有,最新約 5 則)
    entries = _get(p, IDX_REVIEWS, 9, 0, 0)
    if isinstance(entries, list):
        for e in entries:
            rv = {
                "author": _get(e, 0, 1, 4, 5, 0),
                "date_rel": _get(e, 0, 1, 6),
                "stars": _get(e, 0, 2, 0, 0),
                "text": _get(e, 0, 2, 15, 0, 0),
                "photos": [
                    s for s in _iter_strings(_get(e, 0, 2, 2), max_depth=12)
                    if s.startswith("https://lh") and "googleusercontent" in s
                ][:10],
            }
            if rv["author"] or rv["text"]:
                d.reviews.append(rv)

    # 粉專:website 是 FB/IG 時另存(店家把粉專當官網登記)
    if d.website and re.search(r"facebook\.com|instagram\.com", d.website):
        d.fan_page = d.website

    # 位置 id(店址沿革歸戶)
    if isinstance(d.lat, float) and isinstance(d.lng, float):
        from .geo import geohash
        d.location_id = geohash(d.lat, d.lng, precision=8)

    # 商家貼文(完整版才有)
    d.posts = _extract_posts(p)

    # 菜單照片(完整版才有,且店家要有「菜單」相片分類)
    d.menu_photos = _extract_menu_photos(p)

    # 完整版判定:有評論數且營業時間含整週
    d.is_rich = d.user_rating_count is not None and len(d.opening_hours or []) >= 7
    return d


def _extract_posts(p: list) -> list[dict]:
    """商家「最新動態」貼文:p[122][1] 每則 [_, [[..segments]], [ts, ts2], _, [_, link], [[photo]]]"""
    entries = _get(p, IDX_POSTS, 1)
    out: list[dict] = []
    if not isinstance(entries, list):
        return out
    for e in entries:
        segs = _get(e, 1, 0)
        text = None
        if isinstance(segs, list):
            parts = [s[0] for s in segs
                     if isinstance(s, list) and s and isinstance(s[0], str)]
            text = "".join(parts).strip() or None
        if not text:
            continue
        link = _get(e, 4, 1)
        photo = _get(e, 5, 0, 0)
        ts = _get(e, 2, 0)
        out.append({
            "text": text,
            "ts": ts if isinstance(ts, (int, float)) else None,
            "link": link if isinstance(link, str) and link.startswith("http") else None,
            "photo": photo if isinstance(photo, str) and photo.startswith("http") else None,
        })
    return out[:10]


def _extract_menu_photos(p: list, cap: int = 8) -> list[str]:
    """「菜單」相片分類的照片 URL。

    分類節點的巢狀位置會隨店家浮動,採防禦性做法:在 MENU_BLOCKS 區塊內
    找到值為「菜單」的節點,收集其父層子樹內的 googleusercontent 圖片 URL。
    """
    urls: list[str] = []

    def collect(node: Any, depth: int = 0) -> None:
        if len(urls) >= cap or depth > 10:
            return
        if isinstance(node, str):
            if node.startswith("https://lh") and "googleusercontent" in node and node not in urls:
                urls.append(node)
        elif isinstance(node, list):
            for c in node:
                collect(c, depth + 1)

    def walk(node: Any, parent: list | None) -> None:
        if isinstance(node, list):
            for c in node:
                walk(c, node)
        elif node in ("菜單", "Menu") and parent is not None:
            collect(parent)

    for idx in MENU_BLOCKS:
        blk = _get(p, idx)
        if isinstance(blk, list):
            walk(blk, None)
    return urls[:cap]


def _iter_strings(node: Any, max_depth: int, _depth: int = 0):
    if _depth > max_depth:
        return
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for c in node:
            yield from _iter_strings(c, max_depth, _depth + 1)


def strip_xssi(text: str) -> Any:
    """移除 )]}' 前綴並解析 JSON。"""
    t = text.strip()
    if t.startswith(")]}'"):
        t = t[4:]
    return json.loads(t)


class EmptyPlaceResponse(ValueError):
    """回應合法但沒有店家資料(ftid 錯誤、被擋、或格式改版)。"""


def parse_place_response(text: str) -> ShopDetail:
    """/maps/preview/place 回應 → ShopDetail。"""
    data = strip_xssi(text)
    p = data[6]
    if not isinstance(p, list):
        raise ValueError("place array (data[6]) missing in response")
    d = parse_place_array(p, raw_text=text)
    if not d.name and not d.address:
        raise EmptyPlaceResponse(
            f"回應無店家資料({len(text)}b)— ftid 可能失效或被降級")
    return d


def parse_search_response(text: str) -> tuple[list[ShopDetail], str | None]:
    """/search?tbm=map 回應 → (結果列表, event token)。

    token(data[7])綁定這次搜尋;下一個詳情請求帶上它才能拿到完整版回應。
    每筆結果附帶 req_ids(gid/s6/s7),組完整詳情請求時要用。
    """
    data = strip_xssi(text)
    token = data[7] if isinstance(_get(data, 7), str) else None
    results = data[64] if len(data) > 64 else None
    out: list[ShopDetail] = []
    if not isinstance(results, list):
        return out, token
    for item in results:
        p = _get(item, 1)
        if isinstance(p, list) and _get(p, IDX_FTID):
            d = parse_place_array(p)
            d.req_ids = {
                "gid": _get(p, IDX_GID),
                "s6": _get(p, *IDX_S6),
                "s7": _get(p, *IDX_S7),
            }
            out.append(d)
    return out, token
