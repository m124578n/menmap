"""重錄 ramen/templates.py 的 URL 模板。

Google 改版導致 static 後端整批失敗時執行:
    uv run python scripts/capture_templates.py

它用 Playwright 開一次搜尋、點第一個結果,攔截頁面實際發出的
/search?tbm=map 與 /maps/preview/place 兩個 XHR,寫回 ramen/templates.py。
"""

from __future__ import annotations

import pathlib
import re
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")


def capture() -> tuple[str, str, str]:
    search_url = place_url = None
    template_ftid_enc = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(locale="zh-TW", user_agent=UA,
                                  viewport={"width": 1400, "height": 900})
        ctx.add_cookies([
            {"name": "SOCS", "value": "CAISHagB", "domain": ".google.com", "path": "/"},
            {"name": "CONSENT", "value": "YES+", "domain": ".google.com", "path": "/"},
        ])
        page = ctx.new_page()
        seen = {}

        def on_request(req):
            if "/search?tbm=map" in req.url and "search" not in seen:
                seen["search"] = req.url
            elif "/maps/preview/place" in req.url and "place" not in seen:
                seen["place"] = req.url

        page.on("request", on_request)
        page.goto("https://www.google.com/maps/search/拉麵+台北市?hl=zh-TW", timeout=60000)
        page.wait_for_timeout(6000)
        first = page.locator('div[role="feed"] a[href*="/maps/place/"]').first
        href = first.get_attribute("href")
        m = re.search(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)", href or "")
        template_ftid_enc = (m.group(1).replace(":", "%3A")) if m else None
        first.click()
        page.wait_for_timeout(6000)
        browser.close()

    if "search" not in seen or "place" not in seen:
        print("!! 未能同時攔截到兩個 XHR,重試或檢查是否被擋", file=sys.stderr)
        sys.exit(1)
    return seen["search"], seen["place"], template_ftid_enc


def main() -> None:
    search_url, place_url, ftid_enc = capture()
    content = f'''"""Google Maps 內部 XHR 的 URL 模板(由 scripts/capture_templates.py 實錄)。

pb 參數是 protobuf 的 URL 表示法,欄位有長度前綴,不要手動增刪段落;
參數化一律用 build_* 的正則「等長替換值」方式。模板失效時重跑
scripts/capture_templates.py 重錄。
"""

# /search?tbm=map:q= 與 pb 內 !1z(query 的 base64url)需替換
SEARCH_URL_TEMPLATE = "{search_url}"

# /maps/preview/place:!1s(ftid)、!4s(gid)、!5s(place_id)、!6s/!7s、!39z(店名 b64)、!14m2!1s(token)需替換
PLACE_URL_TEMPLATE = "{place_url}"

# 模板中原本的店家值(替換時作為定位錨點)
TPL_FTID_ENC = "{ftid_enc}"
'''
    out = ROOT / "ramen" / "templates.py"
    out.write_text(content, encoding="utf-8")
    print(f"已更新 {out}")
    print(f"  search template: {len(search_url)} 字元")
    print(f"  place template : {len(place_url)} 字元")


if __name__ == "__main__":
    main()
