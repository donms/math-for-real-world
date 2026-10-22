#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W53 问 1 · **周一效应检验**（定稿口径，全部经 `w53_data` 门槛）。

## 数据口径（`w53_data.py`）

* 剔除 `speed <= 0`（占 **29.76%**，视为无读数）；
* 剔除归一化覆盖率 < **75%** 的日子（**分母 = 当天实际 link 数 x 288**）；
* 只用**全程出现的 101 条 link**（消除 6 月由 101 增至 125 条的组成变化）；
* 剔除 5 个联邦假日。

## 三条纪律（题面已写明）

1. **先检验、后下结论** —— 不预设"周一最堵"；
2. **必须报效应量** —— 配对单元数千、底层观测数百万，
   p 值几乎必然极小，只报 p 值等于没回答问题；
3. **逐周重复** —— 要看**分布**而非单点。

## 配对设计

同一 `link_id` × 同一 `hour` × **同一 ISO 周** 的周一与参照日。
路段间速度差异极大（有的常年 40 mph，有的常年 12 mph），
不配对会被路段构成淹没。

## 统计方法

| 量 | 方法 |
|---|---|
| 配对差 | $v_{周一} - v_{参照}$（同周同 link 同时段）|
| 检验 | **Wilcoxon 符号秩**（正态近似，不假设分布）|
| 效应量 | **中位配对差** + **Hodges-Lehmann** + 相对差 |
| 区间 | **bootstrap**（**按 link 重抽**，保留路段内相关性）|

用法：
    $PY q1_monday.py
"""
from __future__ import annotations

import json
import math
import random
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import w53_data as W                                              # noqa: E402

EP = ROOT / "episodes" / "2026-W53"
OUT = EP / "results" / "q1_周一效应.json"

PEAK = (7, 8, 9)
REF_DAYS = ("Tue",)
ROBUST_REF = ("Tue", "Wed", "Thu", "Fri")


def wilcoxon_p(diffs):
    r"""配对 Wilcoxon 符号秩（正态近似，双侧）。"""
    nz = [x for x in diffs if x != 0]
    n = len(nz)
    if n < 10:
        return (0.0, 1.0)
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
    return (wp, 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2)))))


def hl_estimate(diffs):
    r"""Hodges-Lehmann：所有配对差两两均值的**中位数**。

    样本大时（> 4000）改用 20000 次随机抽样的中位数 —— **抽样近似**，
    已在结论中声明。
    """
    if not diffs:
        return 0.0
    if len(diffs) <= 4000:
        return st.median([(diffs[i] + diffs[j]) / 2
                          for i in range(len(diffs))
                          for j in range(i, len(diffs))])
    rng = random.Random(20261013)
    return st.median([st.mean(rng.sample(diffs, 2)) for _ in range(20000)])


def boot_ci(by_link, n_boot=400, seed=20261013):
    r"""按 **link** 重抽的 bootstrap 区间。"""
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


def pkey(k):
    r"""配对键 = (ISO周, link, 小时) —— **不含星期**（星期是分组变量）。

    [!] 本项目第一版写成 `k[1:]`，而键是 `(日, 星期, link, 小时)`，
        于是切掉的是**星期**、留下 `(星期, link, 小时)`
        ⇒ 周一键与周二键**永远不可能相等**，配对数恒为 0 且**不报错**。
    """
    import datetime as _dt
    d = _dt.date.fromisoformat(k[0])
    return (d.isocalendar()[:2], k[2], k[3])


def paired(cells, sel_a, sel_b):
    A: dict[tuple, list] = defaultdict(list)
    B: dict[tuple, list] = defaultdict(list)
    for k, v in cells.items():
        kk = pkey(k)
        if k[1] in sel_a:
            A[kk].append(v)
        elif k[1] in sel_b:
            B[kk].append(v)
    am = {k: st.mean(v) for k, v in A.items()}
    bm = {k: st.mean(v) for k, v in B.items()}
    com = sorted(set(am) & set(bm))
    diffs = [am[k] - bm[k] for k in com]
    by_link = defaultdict(list)
    for k in com:
        by_link[str(k[1])].append(am[k] - bm[k])
    return am, bm, com, diffs, by_link


def main() -> int:
    print("=" * 96)
    print("  W53 问 1 · 周一效应检验（定稿口径）")
    print("=" * 96)
    print(f"\n  {W.QUALITY_NOTE}")
    s = W.summary()
    print(f"  天数 {s['days_total']} -> {s['days_after_cov_filter']}"
          f"（门槛 {W.MIN_DAY_COV:.0%}，归一化分母）"
          f" ｜ 共用 link {s['common_links']}")

    cells = W.load_speed(peak_only=True, hours=PEAK)
    print(f"\n  早高峰单元（日 x 星期 x link x 小时）: {len(cells):,}")
    days = sorted({k[0] for k in cells})
    print(f"  覆盖 {len(days)} 天：{days[0]} … {days[-1]}")

    # ---------- ① 周内形态 ----------
    print(f"\n  == ① 周内形态（早高峰均速）==")
    by_dow = defaultdict(list)
    for k, v in cells.items():
        by_dow[k[1]].append(v)
    order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    stats = {}
    print(f"     {'星期':<6}{'均速':>8}{'中位':>8}{'n':>9}")
    for dw in order:
        v = by_dow.get(dw, [])
        if v:
            stats[dw] = {"mean": round(st.mean(v), 2),
                         "median": round(st.median(v), 2), "n": len(v)}
            print(f"     {dw:<6}{st.mean(v):>8.2f}{st.median(v):>8.2f}"
                  f"{len(v):>9,}")

    # ---------- ② 配对：周一 vs 周二 ----------
    print(f"\n  == ② 配对检验：周一 vs 周二（同周 x 同 link x 同时段）==")
    am, bm, com, diffs, by_link = paired(cells, ("Mon",), REF_DAYS)
    print(f"     配对单元数 {len(com):,}（{len(by_link)} 条 link）")
    if not diffs:
        print("     [!] 无配对样本")
        return 1
    med, hl = st.median(diffs), hl_estimate(diffs)
    lo, hi = boot_ci(by_link)
    w, p = wilcoxon_p(diffs)
    m_ref = st.mean([bm[k] for k in com])
    rel = med / m_ref * 100
    print(f"     参照（周二）均速        : {m_ref:.2f} mph")
    print(f"     **中位配对差（周一-周二）**: {med:+.3f} mph  = {rel:+.2f}%")
    print(f"     Hodges-Lehmann 估计     : {hl:+.3f} mph")
    print(f"     bootstrap 95% 区间      : [{lo:+.3f}, {hi:+.3f}]（按 link 重抽）")
    print(f"     Wilcoxon 符号秩         : W={w:.0f}  p={p:.4f}")
    sig = "显著" if (lo > 0 or hi < 0) else "**不显著（区间跨 0）**"
    print(f"     ==> {sig}，效应量 {abs(rel):.2f}%")
    # 换算成通勤时间
    if m_ref > 0:
        print(f"     ★ 换算：半小时路程（30.0 分钟）"
              f"⇒ {30.0/(1+med/m_ref):.2f} 分钟，"
              f"即 **{30.0/(1+med/m_ref)-30.0:+.1f} 分钟**"
              f"（{abs(30.0/(1+med/m_ref)-30.0)*60:.0f} 秒）")

    # ---------- ③ 逐周稳健性 ----------
    print(f"\n  == ③ 逐周稳健性（各周的 中位配对差）==")
    per_week = {}
    for k in com:
        if k[0] not in per_week:
            per_week[k[0]] = []
    for k in com:
        per_week[k[0]].append(am[k] - bm[k])
    rows = {f"{y}-W{w:02d}": round(st.median(v), 3)
            for (y, w), v in per_week.items() if len(v) >= 50}
    for k in sorted(rows):
        v = rows[k]
        print(f"     {k}  {v:+7.3f}  {'-' if v < 0 else '+'}"
              f"{'#' * min(40, int(abs(v) * 8))}")
    neg = sum(1 for v in rows.values() if v < 0)
    print(f"\n     {len(rows)} 周：周一更慢 {neg} 周 / 周一更快 "
          f"{len(rows)-neg} 周")
    print(f"     ★ 若「周一效应」真实存在，应绝大多数为负")

    # ---------- ④ 稳健性：参照改为周二至周五 ----------
    print(f"\n  == ④ 稳健性：参照改为周二至周五 ==")
    _, bm4, com4, d4, bl4 = paired(cells, ("Mon",), ROBUST_REF)
    m4 = st.mean([bm4[k] for k in com4])
    lo4, hi4 = boot_ci(bl4)
    p4 = wilcoxon_p(d4)[1]
    print(f"     配对单元 {len(com4):,}  参照均速 {m4:.2f} mph")
    print(f"     中位配对差 {st.median(d4):+.3f} mph = "
          f"{st.median(d4)/m4*100:+.2f}%")
    print(f"     bootstrap 95% 区间 [{lo4:+.3f}, {hi4:+.3f}]  p={p4:.4f}")
    print(f"     ==> "
          + ("**不显著（区间跨 0）**" if lo4 <= 0 <= hi4
             else "区间不含 0 ⇒ 显著"))
    print(f"     ★ 注意：本项把参照扩到「周二至周五」，"
          f"而**周五本身更快**（见问 2）⇒ 该差里含周五的贡献，"
          f"**不能读作「周一 vs 周中」**。")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "quality": s, "peak_hours": list(PEAK),
        "days": len(days), "range": [days[0], days[-1]],
        "by_dow": stats,
        "paired_tue": {"n": len(com), "links": len(by_link),
                       "ref_mean": round(m_ref, 3),
                       "median_diff": round(med, 4), "hl": round(hl, 4),
                       "ci": [round(lo, 4), round(hi, 4)],
                       "rel_pct": round(rel, 2),
                       "wilcoxon_W": round(w, 1), "p": p},
        "per_week": rows, "n_weeks_neg": neg, "n_weeks": len(rows),
        "robust_ref4": {"n": len(com4), "ref_mean": round(m4, 3),
                        "median_diff": round(st.median(d4), 4),
                        "rel_pct": round(st.median(d4) / m4 * 100, 2),
                        "ci": [round(lo4, 4), round(hi4, 4)],
                        "p": p4,
                        "_注": "参照含周五；周五本身更快，故该差含周五贡献，"
                               "不能读作「周一 vs 周中」"},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
