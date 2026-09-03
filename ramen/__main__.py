"""CLI 入口:seed / snapshot / compare。

用法:
    python -m ramen seed [--backend static] [--force]
    python -m ramen snapshot --backend static|playwright [--limit N]
    python -m ramen compare
"""

from __future__ import annotations

import argparse
import logging
import os
import sys


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    _setup_logging()
    parser = argparse.ArgumentParser(prog="ramen", description="雙北拉麵地圖資料採集")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_seed = sub.add_parser("seed", help="建立 seed(只跑一次);--refresh 合併更新(每週排程)")
    p_seed.add_argument("--backend", default="static", choices=["static"],
                        help="seed 目前只支援 static(快、可分頁)")
    p_seed.add_argument("--force", action="store_true", help="覆蓋既有 seed.json")
    p_seed.add_argument("--refresh", action="store_true",
                        help="重新搜尋並合併:新店追加、既有更新、搜不到的不刪;報告在 data/diff/{date}-seed.md")

    p_snap = sub.add_parser("snapshot", help="每日快照")
    p_snap.add_argument("--backend", required=True, choices=["static", "playwright"])
    p_snap.add_argument("--limit", type=int, default=None,
                        help="只抓 seed 前 N 家(預設全抓;也可用環境變數 SNAPSHOT_LIMIT)")

    sub.add_parser("compare", help="兩後端當日快照對比報告")

    args = parser.parse_args(argv)

    if args.cmd == "seed":
        if args.refresh:
            from .seed import refresh_seed
            return refresh_seed()
        from .seed import run_seed
        return run_seed(force=args.force)
    if args.cmd == "snapshot":
        limit = args.limit
        if limit is None and os.environ.get("SNAPSHOT_LIMIT"):
            limit = int(os.environ["SNAPSHOT_LIMIT"])
        from .snapshot import run_snapshot
        return run_snapshot(args.backend, limit=limit)
    if args.cmd == "compare":
        from .compare import run_compare
        return run_compare()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
