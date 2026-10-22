#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W53 取数 · **NYC 车速（5 分钟）+ 逐小时流量**，按周切片、断点续跑。

## 数据源（探针实测）

| 数据 | 域 / ID | 粒度 |
|---|---|---|
| NYC DOT Traffic Speeds | `data.cityofnewyork.us` / `i4gi-tjb9` | 5 分钟 |
| MTA 桥梁隧道逐小时过车 | `data.ny.gov` / `ebfx-2m7v` | 逐小时 |

## ★★ 三条来自探针的硬约束（决定本脚本怎么写）

1. **全表 `$group` 会超时**（1.1 亿行）
   ⇒ **必须先用 `$where` 卡时间窗**，本脚本**按周切片**；
2. **服务端不能对 `speed` 做数值聚合**（它是**文本列**，
   `cast` / `::double` / `to_number` 全失败）
   ⇒ **取原始行、本地聚合**（顺带能算分位数）；
3. **`min_data_as_of = 1930-12-09`**（脏记录）
   ⇒ 每个时间窗都显式卡上下界。

## 断点续跑

每周一个 JSONL 文件落在 `data/raw/`；
**已存在且行数合理的周会跳过** —— 这样网络中断后不用从头再来。

用法：
    $PY fetch_traffic.py                 # 取默认区间
    $PY fetch_traffic.py --weeks 8       # 取最近 8 周
    $PY fetch_traffic.py --verify        # 只查已取到的数据
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

EP = ROOT / "episodes" / "2026-W53"
RAW = EP / "data" / "raw"

SPEED = "https://data.cityofnewyork.us/resource/i4gi-tjb9.json"
MTA = "https://data.ny.gov/resource/ebfx-2m7v.json"

# 单页上限：Socrata 允许 50000，但一次要 8 秒 / 3.6 MB
PAGE = 50000
# 锚点：2026-09-07 是周一
ANCHOR_MON = date(2026, 9, 7)


def fetch(url: str, params: str, timeout: int = 240, tries: int = 3):
    r"""取 JSON。

    [!] **不要对 URL 做整体 quote**：SoQL 的 `$` `=` `&` `'` `(` `)` `,`
        都是**语法字符**，编码它们会让 Socrata 报
        `Unrecognized arguments []`（探针第 10 轮踩过）。
        真正需要编码的只有**空格**与中文 —— 用 `quote(safe=...)` 且
        **把语法字符全放进 safe**。
    """
    from urllib.parse import quote
    from net_resolve import open_url
    SAFE = ":/?&=%$,()'*.-_[]{}<>~+"
    u = quote(f"{url}?{params}", safe=SAFE)
    return json.loads(open_url(u, timeout=timeout, tries=tries)
                      .read().decode("utf-8", "ignore"))


def week_bounds(mon: date) -> tuple[str, str]:
    return (f"{mon.isoformat()}T00:00:00",
            f"{(mon + timedelta(days=7)).isoformat()}T00:00:00")


def fetch_speed_week(mon: date) -> list[dict]:
    r"""取一周的**原始**车速行（逐页 `$offset`）。"""
    t0s, t1s = week_bounds(mon)
    out: list[dict] = []
    off = 0
    while True:
        p = ("$select=data_as_of,speed,travel_time,link_id,borough,link_name"
             f"&$where=data_as_of>'{t0s}' AND data_as_of<'{t1s}'"
             f"&$order=data_as_of,link_id&$limit={PAGE}&$offset={off}")
        d = fetch(SPEED, p)
        out.extend(d)
        if len(d) < PAGE:
            break
        off += PAGE
        time.sleep(0.3)
    return out


def fetch_mta_week(mon: date) -> list[dict]:
    r"""取一周的 MTA 逐小时过车。"""
    t0s, t1s = week_bounds(mon)
    out: list[dict] = []
    off = 0
    while True:
        p = ("$select=date,hour,facility,facility_id,direction,"
             "payment_method,vehicle_class,traffic_count"
             f"&$where=date>='{mon.isoformat()}'"
             f" AND date<'{ (mon + timedelta(days=7)).isoformat() }'"
             f"&$order=date,hour&$limit={PAGE}&$offset={off}")
        d = fetch(MTA, p)
        out.extend(d)
        if len(d) < PAGE:
            break
        off += PAGE
        time.sleep(0.3)
    return out


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=int, default=8,
                    help="从锚点周往前的周数（默认 8）")
    ap.add_argument("--verify", action="store_true", help="只统计已取到的数据")
    ap.add_argument("--anchor", default=ANCHOR_MON.isoformat())
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    anchor = date.fromisoformat(args.anchor)
    mons = [anchor - timedelta(weeks=i) for i in range(args.weeks)]

    print("=" * 96)
    print(f"  W53 取数 · {len(mons)} 周")
    print("=" * 96)
    print(f"  区间: {mons[-1]} … {mons[0] + timedelta(days=6)}")
    print(f"  落盘: {RAW.relative_to(ROOT)}\n")

    if args.verify:
        tot_s = tot_m = 0
        for mon in mons:
            fs = RAW / f"speed_{mon.isoformat()}.jsonl"
            fm = RAW / f"mta_{mon.isoformat()}.jsonl"
            ns = sum(1 for _ in fs.open(encoding="utf-8")) if fs.exists() else 0
            nm = sum(1 for _ in fm.open(encoding="utf-8")) if fm.exists() else 0
            tot_s += ns
            tot_m += nm
            print(f"  {mon}  speed {ns:>7,}  mta {nm:>6,}")
        print(f"\n  合计 speed {tot_s:,} / mta {tot_m:,}")
        return 0

    for i, mon in enumerate(mons, 1):
        fs = RAW / f"speed_{mon.isoformat()}.jsonl"
        fm = RAW / f"mta_{mon.isoformat()}.jsonl"
        print(f"  [{i}/{len(mons)}] 周 {mon} …")
        # 车速
        if fs.exists() and fs.stat().st_size > 1000:
            n = sum(1 for _ in fs.open(encoding="utf-8"))
            print(f"      speed 已存在（{n:,} 行）⇒ 跳过")
        else:
            try:
                t0 = time.time()
                rows = fetch_speed_week(mon)
                write_jsonl(fs, rows)
                print(f"      speed {len(rows):,} 行  "
                      f"({time.time()-t0:.0f}s, "
                      f"{fs.stat().st_size/2**20:.1f} MB)")
            except Exception as e:                                   # noqa: BLE001
                print(f"      speed [!] {type(e).__name__}: {str(e)[:70]}")
        # MTA
        if fm.exists() and fm.stat().st_size > 1000:
            n = sum(1 for _ in fm.open(encoding="utf-8"))
            print(f"      mta   已存在（{n:,} 行）⇒ 跳过")
        else:
            try:
                t0 = time.time()
                rows = fetch_mta_week(mon)
                write_jsonl(fm, rows)
                print(f"      mta   {len(rows):,} 行  ({time.time()-t0:.0f}s)")
            except Exception as e:                                   # noqa: BLE001
                print(f"      mta   [!] {type(e).__name__}: {str(e)[:70]}")

    print("\n  取数完成。用 --verify 核对。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
