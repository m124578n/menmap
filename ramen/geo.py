"""Geohash 編碼(店址沿革的位置 id 用),無外部依賴。"""

from __future__ import annotations

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def geohash(lat: float, lng: float, precision: int = 8) -> str:
    """標準 geohash。precision=8 約 ±19m,適合「同一店面位置」的歸戶。"""
    lat_rng = [-90.0, 90.0]
    lng_rng = [-180.0, 180.0]
    bits = 0
    bit_count = 0
    even = True  # 經度先
    out = []
    while len(out) < precision:
        if even:
            mid = (lng_rng[0] + lng_rng[1]) / 2
            if lng >= mid:
                bits = (bits << 1) | 1
                lng_rng[0] = mid
            else:
                bits <<= 1
                lng_rng[1] = mid
        else:
            mid = (lat_rng[0] + lat_rng[1]) / 2
            if lat >= mid:
                bits = (bits << 1) | 1
                lat_rng[0] = mid
            else:
                bits <<= 1
                lat_rng[1] = mid
        even = not even
        bit_count += 1
        if bit_count == 5:
            out.append(_BASE32[bits])
            bits = 0
            bit_count = 0
    return "".join(out)
