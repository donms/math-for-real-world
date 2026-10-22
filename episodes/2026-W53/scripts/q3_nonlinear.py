#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W53 问 3 · **非线性检验**：延误随需求是线性还是超线性？

## 题面的直觉命题

> "平时半个小时路程，周一一个小时都不够"

若成立，意味着**延误对需求的响应是超线性的**
（需求涨一点，时间涨很多）—— 这正是排队系统的特征。

## 但本数据**没有流量**

⇒ 必须用**代理量**，且**必须声明它的局限**。本脚本用**两个**代理并对比：

| 代理 | 定义 | 局限 |
|---|---|---|
| **A. 时段代理** | 该 (日, 小时) 属于"高峰/非高峰" | 太粗，几乎循环论证 |
| **B. 跨路段代理** | 同一时刻**全网速度的中位数** | ★ 它本身就是结果，存在**内生性** |

⇒ 诚实的做法是：**用 B 做形状描述，用 A 做分段检验**，
并**明确写出内生性**，不给因果解释。

## 检验什么

1. **延误 vs 拥堵程度**的散点形状（是否凸）；
2. **分段斜率**：低拥堵段 vs 高拥堵段的斜率比；
3. **拐点**：用分段线性拟合的最小 SSE 搜索拐点位置；
4. **附加**：速度的**方差随拥堵程度上升**（相变的统计指纹，角度 2 的侧证）。

用法：
    $PY q3_nonlinear.py
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
EP = ROOT / "episodes" / "2026-W53"
RAW = EP / "data" / "raw"
OUT = EP / "results" / "q3_非线性.json"

HOLIDAYS = {date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3),
            date(2026, 9, 7)}


def load_cells():
    r"""{(iso_date, hour): [speeds]}（剔 0、剔假日，全部 24 小时）。"""
    acc: dict[tuple[str, int], list[float]] = defaultdict(list)
    for p in sorted(RAW.glob("speed_*.jsonl")):
        with p.open(encoding="utf-8") as f:
            for ln in f:
                try:
                    r = json.loads(ln)
                except Exception:                                    # noqa: BLE001
                    continue
                ts = r.get("data_as_of") or ""
                if not ts.startswith("2026"):
                    continue
                try:
                    d = date.fromisoformat(ts[:10])
                    h = int(ts[11:13])
                except ValueError:
                    continue
                if d in HOLIDAYS:
                    continue
                sv = r.get("speed")
                if sv in (None, ""):
                    continue
                try:
                    v = float(sv)
                except ValueError:
                    continue
                if v > 0:
                    acc[(ts[:10], h)].append(v)
    return acc


def seg_fit(xs: list[float], ys: list[float], cp: float):
    r"""给定拐点 cp，拟合两段线性，返回 (SSE, k1, b1, k2, b2)。"""
    def lin(x, y):
        n = len(x)
        if n < 3:
            return (0.0, st.mean(y) if y else 0.0)
        mx, my = st.mean(x), st.mean(y)
        d = sum((a - mx) ** 2 for a in x)
        k = sum((a - mx) * (b - my) for a, b in zip(x, y)) / d if d else 0.0
        return (k, my - k * mx)
    L = [(x, y) for x, y in zip(xs, ys) if x <= cp]
    R = [(x, y) for x, y in zip(xs, ys) if x > cp]
    k1, b1 = lin([p[0] for p in L], [p[1] for p in L])
    k2, b2 = lin([p[0] for p in R], [p[1] for p in R])
    sse = 0.0
    for x, y in xs and zip(xs, ys):
        pred = k1 * x + b1 if x <= cp else k2 * x + b2
        sse += (y - pred) ** 2
    return (sse, k1, b1, k2, b2)


def main() -> int:
    W.require_raw()          # 缺原始数据时给可操作提示
    print("=" * 96)
    print("  W53 问 3 · 非线性检验（延误 vs 需求代理）")
    print("=" * 96)
    cells = load_cells()
    print(f"\n  (日 x 小时) 单元 {len(cells):,}")

    # 每个单元：均速 + 样本数 + 方差
    pts = []
    for (ds, h), v in sorted(cells.items()):
        if len(v) < 20:
            continue
        m = st.mean(v)
        pts.append({"d": ds, "h": h, "mean": m, "n": len(v),
                    "sd": st.pstdev(v) if len(v) > 1 else 0.0,
                    "cv": (st.pstdev(v) / m if m > 0 else 0.0)})
    print(f"  有效单元 {len(pts):,}")

    # ---------- ① 用"全网中位速度"作拥堵代理 ----------
    #     注意：这是**内生**代理，只用来看形状
    med_all = st.median([p["mean"] for p in pts])
    print(f"\n  == ① 形状：延误 vs 拥堵程度 ==")
    print(f"     全网 (日x小时) 均速中位 = {med_all:.2f} mph"
          f"  ⇒ 以此为界分「畅/堵」")

    # 以"拥堵程度" = 100/速度（越小越堵）为 x，延误 = 100/速度 本身
    # ⇒ 换个更有解释力的口径：**相对延误** = 自由流速度 / 实际速度 - 1
    #    自由流速度取每个时段的 **P95 速度**（近似畅通）
    free = {}
    for h in range(24):
        vals = [p["mean"] for p in pts if p["h"] == h]
        if vals:
            vals.sort()
            free[h] = vals[int(0.95 * (len(vals) - 1))]
    print(f"\n     自由流参考（每小时 P95 速度）：")
    for h in range(24):
        if h in free:
            print(f"       {h:>2}时  {free[h]:>6.2f} mph")

    # 相对延误
    for p in pts:
        f = free.get(p["h"], med_all)
        p["delay"] = (f / p["mean"] - 1) if p["mean"] > 0 else 0.0
    # 拥堵强度 x = 1/速度
    for p in pts:
        p["inten"] = 1.0 / p["mean"] if p["mean"] > 0 else 0.0

    xs = [p["inten"] for p in pts]
    ys = [p["delay"] for p in pts]
    sse1, k1, b1, _k2, _b2 = seg_fit(xs, ys, max(xs) * 2)   # 单段（等于整体线性）
    print(f"\n  == ② 整体线性拟合 ==")
    print(f"     斜率 k = {k1:.4f}  截距 b = {b1:.4f}  SSE = {sse1:.2f}")

    # ---------- ② 分段：搜索拐点 ----------
    print(f"\n  == ③ 分段线性（搜索拐点）==")
    lo, hi = sorted(xs)[int(0.1 * len(xs))], sorted(xs)[int(0.9 * len(xs))]
    best = None
    step = (hi - lo) / 60
    for i in range(61):
        cp = lo + i * step
        sse, a1, _c1, a2, _c2 = seg_fit(xs, ys, cp)
        if best is None or sse < best[0]:
            best = (sse, cp, a1, a2)
    sse2, cp, a1, a2 = best
    print(f"     拐点 x* = {cp:.5f}  （对应速度 ≈ {1/cp:.2f} mph）")
    print(f"     低拥堵段斜率 k1 = {a1:.4f}")
    print(f"     高拥堵段斜率 k2 = {a2:.4f}")
    print(f"     斜率比 k2/k1 = {a2/a1 if a1 else float('nan'):.2f}")
    print(f"     SSE: 单段 {sse1:.2f} → 两段 {sse2:.2f}"
          f"  （降低 {(1-sse2/sse1)*100:.1f}%）")
    if a1 and a2 / a1 > 1.2:
        print(f"     ⇒ **存在超线性区间**（高拥堵段斜率更大）")
    elif a1 and a2 / a1 < 0.8:
        print(f"     ⇒ 高拥堵段斜率**更小**（次线性）")
    else:
        print(f"     ⇒ 两段斜率接近 ⇒ **看不出明显分段**")

    # ---------- ③ 方差随拥堵上升（相变指纹）----------
    print(f"\n  == ④ 附加：速度离散度随拥堵程度的变化（相变指纹）==")
    sorted_pts = sorted(pts, key=lambda p: p["mean"])
    K = 10
    step_n = max(1, len(sorted_pts) // K)
    print(f"     {'速度分位段':<16}{'均速':>8}{'段内速度 sd':>13}"
          f"{'段内 CV':>9}")
    for i in range(0, len(sorted_pts), step_n):
        chunk = sorted_pts[i:i + step_n]
        if len(chunk) < 20:
            continue
        mm = st.mean([c["mean"] for c in chunk])
        sd = st.mean([c["sd"] for c in chunk])
        cv = st.mean([c["cv"] for c in chunk])
        lo_, hi_ = chunk[0]["mean"], chunk[-1]["mean"]
        print(f"     {lo_:>6.1f}–{hi_:<7.1f}{mm:>8.2f}{sd:>13.3f}{cv:>9.3f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "cells": len(pts), "median_speed": round(med_all, 3),
        "free_flow_p95": {str(k): round(v, 3) for k, v in free.items()},
        "linear_fit": {"k": round(k1, 5), "b": round(b1, 5),
                       "sse": round(sse1, 3)},
        "piecewise": {"breakpoint": round(cp, 6),
                      "speed_at_bp": round(1 / cp, 3),
                      "k_low": round(a1, 5), "k_high": round(a2, 5),
                      "ratio": round(a2 / a1, 3) if a1 else None,
                      "sse": round(sse2, 3),
                      "sse_reduction_pct": round((1 - sse2 / sse1) * 100, 2)},
        "_代理局限": ("本数据无真实流量。'拥堵强度'用 1/速度 代理，"
                      "'延误'用 每小时P95速度/实际速度-1 代理。"
                      "**两者都含内生性**（速度既是原因也是结果）⇒ "
                      "只作形状描述，不作因果解释。"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
