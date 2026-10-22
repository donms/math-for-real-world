#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W53 问 2 · **真正的效应在哪**：工作日 vs 周末，含季节分层。

## 背景（问 1 的结论）

* **周一 vs 周二 = 0**：中位差 −0.052 mph（−0.16%），
  区间 [−0.205, +0.103] 跨 0，p = 0.104，逐周符号 6:8 对半；
* 但周内形态显示 **工作日 ≈ 32.2–34.5 mph vs 周末 ≈ 40.8–44.6 mph**。

## 本问做两件事

1. **量化这个效应**（配对 + 效应量 + 区间 + 显著性）；
2. ★ **按季节分层**，确认它不是"某个时期特有"的假象。

## ★ 为什么必须做季节分层

取数区间 **2026-05-11 … 2026-09-13** 横跨三个时期：

| 时期 | 周 | 学校状态 |
|---|---|---|
| **暑假前** | 05-11 … 06-15 | 学期中 |
| **暑假中** | 06-22 … 08-31 | 放假 |
| **暑假后** | 09-07 … | 已开学 |

不分层时，一个只存在于某一时期的效应会被"平均"成看起来普遍的现象。

## 配对方式

同一 (ISO周, link, 小时) 上，
取"A 组各日的均值"与"B 组各日的均值"作差 ⇒ 抵消路段与季节。

用法：
    $PY q2_weekend.py
"""
from __future__ import annotations

import json
import math
import random
import statistics as st
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import w53_data as W                                              # noqa: E402

EP = ROOT / "episodes" / "2026-W53"
OUT = EP / "results" / "q2_工作日与周末.json"

PEAK = (7, 8, 9)
WD = ("Mon", "Tue", "Wed", "Thu", "Fri")
WE = ("Sat", "Sun")
MID = ("Tue", "Wed", "Thu")

SEASONS = [("暑假前（学期中）", date(2026, 5, 11), date(2026, 6, 15)),
           ("暑假中", date(2026, 6, 22), date(2026, 8, 31)),
           ("暑假后（已开学）", date(2026, 9, 7), date(2026, 9, 30))]


def wilcoxon_p(diffs):
    nz = [x for x in diffs if x != 0]
    n = len(nz)
    if n < 10:
        return 1.0
    order = sorted(range(n), key=lambda i: abs(nz[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(nz[order[j + 1]]) == abs(nz[order[i]]):
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    wp = sum(ranks[i] for i in range(n) if nz[i] > 0)
    mu = n * (n + 1) / 4
    sd = math.sqrt(n * (n + 1) * (2 * n + 1) / 24)
    z = (wp - mu) / sd if sd else 0.0
    return 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))


def boot_ci(by_link, n_boot=400, seed=20261013):
    links = list(by_link)
    if not links:
        return (0.0, 0.0)
    rng = random.Random(seed)
    meds = []
    for _ in range(n_boot):
        pick = [links[rng.randrange(len(links))] for _ in range(len(links))]
        v = [x for lk in pick for x in by_link[lk]]
        if v:
            meds.append(st.median(v))
    meds.sort()
    return (meds[int(0.025 * len(meds))], meds[int(0.975 * len(meds)) - 1])


def paired(cells, sel_a, sel_b, keep=None):
    A: dict[tuple, list] = defaultdict(list)
    B: dict[tuple, list] = defaultdict(list)
    for (ds, dw, lk, h), v in cells.items():
        d = date.fromisoformat(ds)
        if keep and not keep(d):
            continue
        key = (d.isocalendar()[:2], lk, h)
        if dw in sel_a:
            A[key].append(v)
        elif dw in sel_b:
            B[key].append(v)
    am = {k: st.mean(v) for k, v in A.items()}
    bm = {k: st.mean(v) for k, v in B.items()}
    com = sorted(set(am) & set(bm))
    diffs = [am[k] - bm[k] for k in com]
    by_link = defaultdict(list)
    for k in com:
        by_link[str(k[1])].append(am[k] - bm[k])
    return am, bm, com, diffs, by_link


def report(title, am, bm, com, diffs, by_link):
    print(f"\n  == {title} ==")
    if not diffs:
        print("     [!] 无配对样本")
        return None
    ma = st.mean([am[k] for k in com])
    mb = st.mean([bm[k] for k in com])
    med = st.median(diffs)
    lo, hi = boot_ci(by_link)
    p = wilcoxon_p(diffs)
    rel = med / mb * 100 if mb else 0.0
    print(f"     配对单元 {len(com):,}（{len(by_link)} 条 link）")
    print(f"     A 组均速 {ma:.2f} ｜ B 组均速 {mb:.2f}")
    print(f"     **中位配对差** {med:+.3f} mph = **{rel:+.2f}%**")
    print(f"     bootstrap 95% 区间 [{lo:+.3f}, {hi:+.3f}]   p={p:.3e}")
    sig = "显著" if (lo > 0 or hi < 0) else "**不显著（区间跨 0）**"
    print(f"     ==> {sig}")
    return {"n": len(com), "links": len(by_link),
            "mean_a": round(ma, 3), "mean_b": round(mb, 3),
            "median_diff": round(med, 4), "rel_pct": round(rel, 2),
            "ci": [round(lo, 4), round(hi, 4)], "p": p}


def main() -> int:
    print("=" * 96)
    print("  W53 问 2 · 真正的效应：工作日 vs 周末（含季节分层）")
    print("=" * 96)
    print(f"\n  {W.QUALITY_NOTE}")
    cells = W.load_speed(peak_only=True, hours=PEAK)
    days = sorted({k[0] for k in cells})
    print(f"  早高峰单元 {len(cells):,} ｜ 覆盖 {len(days)} 天："
          f"{days[0]} … {days[-1]}")

    # ---------- ① 周内形态 ----------
    print(f"\n  == ① 周内形态（早高峰）==")
    by_dow = defaultdict(list)
    for k, v in cells.items():
        by_dow[k[1]].append(v)
    order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    spd = {}
    print(f"     {'星期':<6}{'均速':>8}{'中位':>8}{'n':>9}")
    for dw in order:
        v = by_dow.get(dw, [])
        if v:
            spd[dw] = round(st.mean(v), 2)
            print(f"     {dw:<6}{st.mean(v):>8.2f}{st.median(v):>8.2f}"
                  f"{len(v):>9,}")
    wd_m = st.mean([spd[d] for d in WD if d in spd])
    we_m = st.mean([spd[d] for d in WE if d in spd])
    print(f"\n     工作日均值 {wd_m:.2f} ｜ 周末均值 {we_m:.2f}"
          f"  ==> 周末快 **{(we_m/wd_m-1)*100:.2f}%**")
    sun, mon = spd.get("Sun"), spd.get("Mon")
    if sun and mon:
        print(f"     ★ 相邻日最大落差：周日 {sun:.2f} -> 周一 {mon:.2f}"
              f"  = **+{(sun/mon-1)*100:.1f}%**")

    # ---------- ② 整体配对 ----------
    res_all = report("② 工作日 vs 周末（全区间配对）",
                     *paired(cells, WD, WE))

    # ---------- ③ ★ 季节分层 ----------
    print(f"\n  == ③ ★ 季节分层（确认不是某一时期特有）==")
    seas = {}
    for nm, a, b in SEASONS:
        keep = (lambda aa, bb: (lambda d: aa <= d <= bb))(a, b)
        r = report(f"{nm}（{a} … {b}）",
                   *paired(cells, WD, WE, keep=keep))
        if r:
            seas[nm] = r

    # ---------- ④ 周一 / 周五 相对周中 ----------
    print(f"\n  == ④ 周一 与 周五 各自相对「周二至周四」==")
    r_mon = report("周一 vs 周二至周四", *paired(cells, ("Mon",), MID))
    r_fri = report("周五 vs 周二至周四", *paired(cells, ("Fri",), MID))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "quality": W.summary(), "peak": list(PEAK),
        "days": len(days), "by_dow": spd,
        "weekday_mean": round(wd_m, 3), "weekend_mean": round(we_m, 3),
        "weekend_advantage_pct": round((we_m / wd_m - 1) * 100, 2),
        "sun_minus_mon_pct": round((spd["Sun"] / spd["Mon"] - 1) * 100, 2)
                             if "Sun" in spd and "Mon" in spd else None,
        "wd_vs_we_all": res_all, "by_season": seas,
        "mon_vs_mid": r_mon, "fri_vs_mid": r_fri,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
