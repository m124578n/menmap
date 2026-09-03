"""HTTP 工具:requests session、瀏覽器 headers、sleep、指數退避重試。"""

from __future__ import annotations

import logging
import os
import random
import time

import requests

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
}
# 沒有這兩個 cookie 時,部分地區會被導去 consent 頁
COOKIES = {"CONSENT": "YES+", "SOCS": "CAISHagB"}

MAX_RETRIES = 3

# --- 節流:避免爬太快被 Google 降級/封鎖。全部可用環境變數覆蓋 ---
# 每次請求後的基本等待:在 [MIN, MAX] 間均勻隨機(秒)
SLEEP_MIN = float(os.environ.get("RAMEN_SLEEP_MIN", "2.5"))
SLEEP_MAX = float(os.environ.get("RAMEN_SLEEP_MAX", "5.0"))
# 每處理 LONG_PAUSE_EVERY 家店,插入一次較長休息([LONG_MIN, LONG_MAX] 秒),
# 打散請求節奏,模擬真人瀏覽
LONG_PAUSE_EVERY = int(os.environ.get("RAMEN_LONG_PAUSE_EVERY", "15"))
# (2026-09 實測全抽 617 家 0 失敗後,從 20~45 秒縮短;若失敗/精簡版變多再調回去)
LONG_PAUSE_MIN = float(os.environ.get("RAMEN_LONG_PAUSE_MIN", "8"))
LONG_PAUSE_MAX = float(os.environ.get("RAMEN_LONG_PAUSE_MAX", "15"))

_request_count = 0


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def polite_sleep(base: float | None = None) -> None:
    """請求間節流:隨機延遲,並每隔數次插入一段長休息。

    base 給定時,延遲為 [base, 2*base];否則用 [SLEEP_MIN, SLEEP_MAX]。
    """
    global _request_count
    _request_count += 1
    if base is not None:
        time.sleep(random.uniform(base, base * 2))
    else:
        time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))
    if LONG_PAUSE_EVERY > 0 and _request_count % LONG_PAUSE_EVERY == 0:
        pause = random.uniform(LONG_PAUSE_MIN, LONG_PAUSE_MAX)
        log.info("已處理 %d 次,長休息 %.0f 秒(降低被擋機率)",
                 _request_count, pause)
        time.sleep(pause)


def fetch(session: requests.Session, url: str, *, timeout: int = 30) -> requests.Response:
    """GET,對 429/5xx 指數退避重試最多 MAX_RETRIES 次;其餘直接回傳。"""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, cookies=COOKIES, timeout=timeout)
        except requests.RequestException as e:
            last_exc = e
            log.warning("request error (attempt %d): %s", attempt + 1, e)
        else:
            if resp.status_code == 429 or resp.status_code >= 500:
                log.warning("HTTP %d (attempt %d) for %s",
                            resp.status_code, attempt + 1, url[:100])
                last_exc = RuntimeError(f"HTTP {resp.status_code}")
            else:
                return resp
        time.sleep(2 ** attempt + random.uniform(0, 1))
    raise RuntimeError(f"fetch failed after {MAX_RETRIES} retries: {last_exc}")
