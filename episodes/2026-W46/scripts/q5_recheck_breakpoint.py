#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W46 修订 · **核实"2020–2022 口径断点"这个论断**（为发布前复核）。

## 起因（用户提出）

> 「里面有句"2020–2022 的口径断点"，这应该就是新冠爆发的那段时间。」

用户说得对 —— **那正是 COVID 期**，而 W46 的原文写的是
"2020–2022（COVID 期）监测行为显著改变 …… **这是一个观测口径断点，不是病毒变强**"。

## 本文要回答的三个问题

| # | 问题 |
|---|---|
| **Q1** | 那个"三段均值 2.083 / 2.371 / 2.643"是**按日历年**还是**按流感季**算的？ |
| **Q2** | "**不是病毒变强**"这个论断，数据支不支持？ |
| **Q3** | 多了 2 周新数据后，结论有没有变化？ |

## 关键方法：**流感季 vs 日历年**

ILI 有强季节性（冬高夏低）。**按日历年切会把一个流行季劈成两半**，
于是"均值"混进了"切在哪"的人为因素。

**正确做法**：按**流感季**（约 W40 至次年 W39）切分
—— 这也正是 CDC 的口径（`2025-26 season`）。

## 落盘 `results/核查_口径断点.json`

用法：
    $PY q5_recheck_breakpoint.py
"""
from __future__ import annotations

import csv
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W46"
RES = EP / "results"
RES.mkdir(parents=True, exist_ok=True)
ILI = EP / "data" / "clean" / "ili_weekly.csv"
CLIN = EP / "data" / "clean" / "clinical_weekly.csv"


def load_ili() -> list[tuple[int, int, float]]:
    out = []
    with ILI.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            try:
                out.append((int(r["epiweek"]), int(r["epiweek"][:4]),
                            float(r["ili"])))
            except (ValueError, KeyError):
                continue
    return sorted(out)


def season_of(epiweek: int) -> str:
    r"""流感季标签：约 **W40 至次年 W39**（CDC 口径）。

    例：`202540`–`202639` 都归入 `2025-26`。
    """
    y, w = epiweek // 100, epiweek % 100
    return f"{y}-{str(y+1)[2:]}" if w >= 40 else f"{y-1}-{str(y)[2:]}"


def main() -> int:
    ili = load_ili()
    print("=" * 94)
    print("  W46 修订 · 核查『2020–2022 口径断点』")
    print("=" * 94)
    print(f"\n  ILI 序列 {len(ili)} 周，{ili[0][0]}–{ili[-1][0]}")

    # ── Q1：按日历年 vs 按流感季 ──
    print(f"\n  ── Q1：两种切法的均值对比 ──")
    print(f"     (A) 按**日历年**（W46 原文可能用的口径）")
    for lo, hi, name in ((2015, 2019, "2015–2019"), (2020, 2022, "2020–2022"),
                         (2023, 2026, "2023–2026")):
        v = [x for _, y, x in ili if lo <= y <= hi]
        print(f"        {name}: n={len(v):>4}  均值 {st.mean(v):.4f}")
    print(f"     (B) 按**流感季**（CDC 口径，W40–次年 W39）")
    bys: dict[str, list[float]] = {}
    for _, _, x in ili:
        pass
    bys = {}
    for ew, _, x in ili:
        bys.setdefault(season_of(ew), []).append(x)
    for s in sorted(bys):
        v = bys[s]
        if len(v) >= 30:
            print(f"        {s}: n={len(v):>4}  均值 {st.mean(v):.4f}"
                  f"  峰值 {max(v):.4f}")

    # ── Q2：季节峰值是否"变强" ──
    print(f"\n  ── Q2：各流感季的**峰值**与『过阈值周数』──")
    print(f"     {'流感季':<10}{'n':>5}{'均值':>9}{'峰值':>9}{'达峰周':>9}"
          f"{'>=2%周数':>10}")
    peaks = {}
    for s in sorted(bys):
        v = bys[s]
        if len(v) < 30:
            continue
        mx = max(v)
        wk = [w for w, _, x in ili if season_of(w) == s and x == mx]
        over = sum(1 for x in v if x >= 2.0)
        peaks[s] = {"mean": round(st.mean(v), 4), "peak": round(mx, 4),
                    "peak_week": wk[0] if wk else None,
                    "weeks_ge_2pct": over, "n": len(v)}
        print(f"     {s:<10}{len(v):>5}{st.mean(v):>9.4f}{mx:>9.4f}"
              f"{(wk[0] if wk else 0):>9}{over:>10}")

    # 结论判读
    print(f"\n  ── 判读 ──")
    ks = [s for s in sorted(peaks) if s >= "2013"]
    pk = [peaks[s]["peak"] for s in ks]
    print(f"     各季**峰值**序列：")
    for s in ks:
        bar = "#" * int(peaks[s]["peak"] * 10)
        print(f"       {s}  {peaks[s]['peak']:>6.3f}  {bar}")
    if len(pk) >= 4:
        pre = [peaks[s]["peak"] for s in ks if s < "2020"]
        cov = [peaks[s]["peak"] for s in ks if "2020" <= s < "2022"]
        post = [peaks[s]["peak"] for s in ks if s >= "2022"]
        print(f"\n     疫前（<2020）峰值均值   {st.mean(pre):.3f}  n={len(pre)}")
        if cov:
            print(f"     COVID 期（2020–21）      "
                  f"{st.mean(cov):.3f}  n={len(cov)}")
        print(f"     疫后（>=2022）峰值均值   {st.mean(post):.3f}  n={len(post)}")
        if cov and st.mean(cov) < st.mean(pre) * 0.7:
            print(f"     => **COVID 期峰值显著偏低** "
                  f"（{st.mean(cov)/st.mean(pre)*100:.0f}% 于疫前）")
        if post and st.mean(post) > st.mean(pre):
            print(f"     => **疫后峰值高于疫前** "
                  f"（{st.mean(post)/st.mean(pre)*100:.0f}%）")
    print(f"\n     [!] 注意：**均值**受『切在哪』影响很大，"
          f"而**峰值**是季节性指标，更稳健。")

    # ── Q3：新数据（2026W38/W39）──
    print(f"\n  ── Q3：序列末端（新数据）──")
    for ew, y, x in ili[-6:]:
        s = season_of(ew)
        print(f"     {ew}  季 {s}  ILI {x:.4f}")

    out = {"序列": {"n": len(ili), "起": ili[0][0], "止": ili[-1][0]},
           "按日历年": {
               "2015-2019": round(st.mean([x for _, y, x in ili
                                           if 2015 <= y <= 2019]), 4),
               "2020-2022": round(st.mean([x for _, y, x in ili
                                           if 2020 <= y <= 2022]), 4),
               "2023-2026": round(st.mean([x for _, y, x in ili
                                           if 2023 <= y <= 2026]), 4)},
           "按流感季": peaks,
           "末端": [{"epiweek": w, "season": season_of(w), "ili": round(x, 4)}
                    for w, _, x in ili[-6:]],
           "_自查": [
               "ILI 有强季节性 => 按日历年切会把流行季劈成两半",
               "峰值比均值稳健，是季节性指标",
               "2020-21 季的监测行为改变（就诊行为、哨点构成）需与病毒学分开",
           ]}
    p = RES / "核查_口径断点.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
