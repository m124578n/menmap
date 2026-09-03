"""靜態後端:requests 直接打 Google Maps 內部 XHR。

流程(完整詳情必須這樣拿):
1. 搜尋 XHR → 每筆結果的 req_ids(gid/s6/s7)+ 綁定這次搜尋的 event token
2. 詳情 XHR 帶上「該店全部 id + token」→ 完整版回應(評論數、整週營業時間、評論)
   任一 id 或 token 不對,只會拿到精簡版(今日營業時間、無評論數)。
   一個 token 只換得到一次完整回應,所以每家店都要重新搜尋一次。
"""

from __future__ import annotations

import base64
import logging
import re
import struct
import urllib.parse

import requests

from . import net
from .parser import parse_place_response, parse_search_response
from .schema import ShopDetail
from .templates import PLACE_URL_TEMPLATE, SEARCH_URL_TEMPLATE, TPL_FTID_ENC

log = logging.getLogger(__name__)


def ftid_to_place_id(ftid: str) -> str:
    """ftid "0x..:0x.." → ChIJ... place_id(兩個 fixed64 的 protobuf + base64url)。"""
    hi, lo = (int(x, 16) for x in ftid.split(":"))
    payload = b"\x09" + struct.pack("<Q", hi) + b"\x11" + struct.pack("<Q", lo)
    msg = b"\x0a" + bytes([len(payload)]) + payload
    return base64.urlsafe_b64encode(msg).decode().rstrip("=")


def _b64_urlsafe(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def build_search_url(query: str, offset: int = 0) -> str:
    q = urllib.parse.quote_plus(query)
    url = re.sub(r"q=[^&]*", "q=" + q, SEARCH_URL_TEMPLATE, count=1)
    # pb 內的 !1z 是 query 的 base64url(模板整段是 URL-encoded,所以是 %211z)
    url = re.sub(r"%211z[^%]*%217i", "%211z" + _b64_urlsafe(query) + "%217i", url, count=1)
    if offset:
        # !7i20 後注入 !8i{offset} 換頁(每頁 20 筆)
        url = re.sub(r"(%217i20)", r"\g<1>%218i" + str(offset), url, count=1)
    return url


def build_place_url(ftid: str, name: str, *, gid: str | None,
                    s6: str | None, s7: str | None, token: str | None) -> str:
    url = PLACE_URL_TEMPLATE.replace(TPL_FTID_ENC, ftid.replace(":", "%3A"))
    url = re.sub(r"&q=[^&]*$", "", url)
    url = re.sub(r"!39z[^!]+", "!39z" + _b64_urlsafe(name), url)
    url = re.sub(r"!4s[^!]+", "!4s" + urllib.parse.quote(gid or "", safe=""), url)
    url = re.sub(r"!5sChIJ[^!]+", "!5s" + ftid_to_place_id(ftid), url)
    url = re.sub(r"!6s\d[^!]*", "!6s" + (s6 or ""), url)
    url = re.sub(r"!7s\d[^!]*", "!7s" + (s7 or ""), url)
    if token:
        url = re.sub(r"!14m2!1s[^!]+!7e81", "!14m2!1s" + token + "!7e81", url)
    return url


class StaticBackend:
    name = "static"

    def __init__(self) -> None:
        self.session = net.make_session()

    def search(self, query: str, offset: int = 0) -> tuple[list[ShopDetail], str | None, str]:
        """搜尋 → (結果, token, 原始回應文字)。"""
        resp = net.fetch(self.session, build_search_url(query, offset))
        if not resp.text.startswith(")]}'"):
            raise RuntimeError(
                f"search response not JSON (HTTP {resp.status_code}, "
                f"{len(resp.text)}b) — 可能被擋或格式改版")
        results, token = parse_search_response(resp.text)
        return results, token, resp.text

    def fetch_details(self, ftid: str, name: str,
                      fallback_ids: dict | None = None) -> tuple[ShopDetail, str]:
        """抓單店詳情。直接用 seed 存的 id 打一次(每店僅 1 次請求)。

        註:靜態後端的完整版(評論數/整週營業時間)需要「搜尋當下綁定的
        one-time token」,而搜尋店名只會回單一匹配(拿不到多筆結果與可用
        token),故這裡不再做每店搜尋——省一半請求量、降低被擋機率,拿到的
        是精簡版(核心欄位齊全)。完整版交給 playwright 後端。
        回傳 (ShopDetail, 詳情原始回應文字)。
        """
        ids = fallback_ids or {}
        url = build_place_url(ftid, name, gid=ids.get("gid"),
                              s6=ids.get("s6"), s7=ids.get("s7"), token=None)
        resp = net.fetch(self.session, url)
        if not resp.text.startswith(")]}'"):
            raise RuntimeError(
                f"place response not JSON (HTTP {resp.status_code}) — 可能被擋或格式改版")
        detail = parse_place_response(resp.text)
        detail.req_ids = ids
        return detail, resp.text
