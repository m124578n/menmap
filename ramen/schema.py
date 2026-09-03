"""共通資料結構:兩個後端都輸出同一組欄位。"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field


@dataclass
class ShopDetail:
    """單一店家一次抓取的正規化結果。"""

    ftid: str                      # "0x...:0x..." feature id,主鍵
    name: str | None = None
    place_id: str | None = None    # ChIJ...,從評論連結抽出,供未來對接官方 API
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    rating: float | None = None
    user_rating_count: int | None = None
    phone: str | None = None
    website: str | None = None
    price_text: str | None = None  # "$100–200" 之類,Google 顯示什麼存什麼
    business_status: str | None = None  # OPERATIONAL / CLOSED_TEMPORARILY / CLOSED_PERMANENTLY
    opening_hours: list | None = None   # [[星期名, [區間...]], ...] 依 Google 回傳順序
    types: list[str] = field(default_factory=list)
    reviews: list = field(default_factory=list)      # [{author, stars, date_rel, text, photos}]
    cover_photo: str | None = None
    is_rich: bool = False              # 這次回應是否為完整版(有評論數+整週營業時間)
    req_ids: dict = field(default_factory=dict)      # {gid, s6, s7}:組完整詳情請求所需
    posts: list = field(default_factory=list)        # 商家貼文 [{text, ts, link, photo}]
    menu_photos: list[str] = field(default_factory=list)  # 「菜單」分類照片 URL
    fan_page: str | None = None        # website 為 FB/IG 時的粉專連結
    location_id: str | None = None     # geohash(店址沿革歸戶用)

    def hours_json(self) -> str | None:
        if self.opening_hours is None:
            return None
        return json.dumps(self.opening_hours, ensure_ascii=False, sort_keys=True)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass
class SeedEntry:
    ftid: str
    name: str
    address: str | None
    lat: float | None
    lng: float | None
    maps_url: str | None
    added_at: str


def safe_ftid(ftid: str) -> str:
    """ftid 轉成可當 Windows 檔名的形式(冒號不合法)。"""
    return ftid.replace(":", "-")
