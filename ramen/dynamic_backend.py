"""動態後端:Playwright 開真實地圖頁,攔截 /maps/preview/place XHR。

比靜態後端穩健:瀏覽器自己帶完整 session、cookie、token,通常直接拿到
完整版回應(評論數、整週營業時間、評論)。我們不解析 DOM,而是攔截頁面
自己發出的 place XHR,交給同一套 parser——欄位定義兩後端共用一份。
"""

from __future__ import annotations

import logging
import os
import time
import urllib.parse

from . import net
from .parser import parse_place_response, parse_search_response
from .schema import ShopDetail

log = logging.getLogger(__name__)

# 拿到精簡版(非完整版)時的重試次數;每次重試等更久讓頁面 render 完整
LITE_RETRIES = int(os.environ.get("RAMEN_LITE_RETRIES", "2"))

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")


def place_url_for(ftid: str, name: str, *, lat: float | None = None,
                  lng: float | None = None, gid: str | None = None,
                  place_id: str | None = None) -> str:
    """組出帶 data= 的地圖店家永久連結。

    lat/lng/gid/place_id 有值時填入(定位更精準),缺了也能運作——
    Google 會靠 !1s{ftid} 解析。這個 URL 也適合存進 seed。
    """
    q = urllib.parse.quote(name)
    parts = ["!4m6", "!3m5", f"!1s{ftid}"]
    if lat is not None and lng is not None:
        parts.append(f"!8m2!3d{lat}!4d{lng}")
    if gid:
        parts.append(f"!16s{urllib.parse.quote(gid, safe='')}")
    if place_id:
        parts.append(f"!19s{place_id}")
    return f"https://www.google.com/maps/place/{q}/data={''.join(parts)}?hl=zh-TW"


class DynamicBackend:
    name = "playwright"

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self._pw = None
        self._browser = None
        self._ctx = None

    def __enter__(self) -> "DynamicBackend":
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        self._ctx = self._browser.new_context(
            locale="zh-TW",
            viewport={"width": 1400, "height": 900},
            user_agent=UA,
        )
        # 首次進站設 consent cookie,避免被導去同意頁
        self._ctx.add_cookies([
            {"name": "SOCS", "value": "CAISHagB", "domain": ".google.com", "path": "/"},
            {"name": "CONSENT", "value": "YES+", "domain": ".google.com", "path": "/"},
        ])
        return self

    def __exit__(self, *exc) -> None:
        try:
            if self._browser:
                self._browser.close()
        finally:
            if self._pw:
                self._pw.stop()

    def _capture(self, url: str, url_marker: str, timeout_ms: int = 45000,
                 settle_ms: int = 0) -> str:
        """開頁,回傳第一個符合 url_marker 的 XHR 回應原始文字。

        settle_ms:抓到 XHR 後額外多等的時間,讓頁面把完整版資料 render/載入完
        (減少拿到精簡版的機率)。
        """
        page = self._ctx.new_page()
        captured: list[str] = []

        def on_response(resp):
            if url_marker in resp.url:
                try:
                    captured.append(resp.text())
                except Exception:
                    pass

        page.on("response", on_response)
        try:
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            deadline = time.time() + timeout_ms / 1000
            while not captured and time.time() < deadline:
                page.wait_for_timeout(500)
            if captured and settle_ms:
                page.wait_for_timeout(settle_ms)  # 等頁面補發更完整的 XHR
        finally:
            page.close()
        if not captured:
            raise RuntimeError(f"no XHR matching {url_marker!r} captured for {url[:80]}")
        # 頁面可能發多次同型 XHR,取最長(最完整)那個
        return max(captured, key=len)

    def search(self, query: str) -> tuple[list[ShopDetail], str | None]:
        q = urllib.parse.quote(query)
        url = f"https://www.google.com/maps/search/{q}?hl=zh-TW"
        text = self._capture(url, "/search?tbm=map")
        results, token = parse_search_response(text)
        return results, token

    def fetch_details(self, ftid: str, name: str,
                      maps_url: str | None = None) -> tuple[ShopDetail, str]:
        """開店家頁,攔截頁面自發的 place XHR。maps_url 優先(seed 存的永久連結)。

        拿到精簡版時重試(每次多等一點讓完整版 render 完),最多 LITE_RETRIES 次。
        """
        url = maps_url or place_url_for(ftid, name)
        best: tuple[ShopDetail, str] | None = None
        for attempt in range(LITE_RETRIES + 1):
            settle = 1500 + attempt * 2500  # 首次等 1.5s,重試逐次加長
            text = self._capture(url, "/maps/preview/place", settle_ms=settle)
            detail = parse_place_response(text)
            if detail.is_rich:
                return detail, text
            if best is None or len(text) > len(best[1]):
                best = (detail, text)
            if attempt < LITE_RETRIES:
                log.info("  %s 拿到精簡版,重試(%d/%d)", name, attempt + 1, LITE_RETRIES)
                self.polite_sleep()
        return best  # 幾次都精簡版,回傳最完整的一次

    def polite_sleep(self, base: float | None = None) -> None:
        net.polite_sleep(base)
