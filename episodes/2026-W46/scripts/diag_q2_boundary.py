#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · Q2 诊断：**后验是否被边界截断** + 加宽窗口重估。

## 为什么要单独做这个

`q2_changepoint.py` 首次运行给出"变点众数 = 第 35 周"，
但 $n=18$ 时我限制了 $\tau\le n-3=15$ ⇒ **第 35 周正好是上边界**。
后验直方图也显示它在右端**单调升到最高**，没有回落。

**这是边界伪影（boundary artifact），不是估计值。**
⇒ 必须诊断并修正，否则会把"窗口开得太短"当成"起爆点在第 35 周"。

## 本脚本做三件事

1. **边界诊断**：看 $\tau$ 后验在两端是否堆在边界上
   （判据：边界处的后验是否 > 内部最大值）；
2. **加宽窗口**：把窗口从"第 20–38 周"扩到"第 1–38 周"甚至跨年，
   看众数是否移到内部；
3. **报告"变点不可辨识"这一可能结论** —— 若加宽后后验仍然右偏，
   就如实说"起爆点晚于观测末端，数据不能定出它"。

用法：
    $PY diag_q2_boundary.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from q2_changepoint import (deseason_A, deseason_B, flat_week,  # noqa: E402
                            hdi, load_ili, logmarg_const)

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"


def post_const(x: np.ndarray, prior: str = "uniform", margin: int = 3):
    n = len(x)
    taus = np.arange(margin, n - margin + 1)
    lp = np.array([logmarg_const(x, int(t)) for t in taus])
    if prior == "edge":
        c = (taus - taus.mean()) / max(taus.std(), 1e-9)
        lp = lp + 0.5 * c ** 2
    lp -= lp.max()
    p = np.exp(lp)
    return taus, p / max(p.sum(), 1e-300)


def main() -> int:
    print("=" * 94)
    print("  W46 · Q2 边界诊断（后验是否被截断）")
    print("=" * 94)
    wk, y = load_ili()
    rA, _, _ = deseason_A(wk, y)
    ok = np.isfinite(rA) & (rA > 0)
    rep: dict = {}

    windows = [
        ("2026 W20–38（原窗口）", (wk // 100 == 2026) & (wk % 100 >= 20)
         & (wk % 100 <= 38)),
        ("2026 W1–38", (wk // 100 == 2026) & (wk % 100 >= 1)
         & (wk % 100 <= 38)),
        ("2025W40–2026W38（跨年）", ((wk // 100 == 2025) & (wk % 100 >= 40))
         | ((wk // 100 == 2026) & (wk % 100 <= 38))),
        ("2024W40–2026W38（两季）", ((wk // 100 == 2024) & (wk % 100 >= 40))
         | (wk // 100 == 2025)
         | ((wk // 100 == 2026) & (wk % 100 <= 38))),
    ]

    print(f"\n  {'窗口':<26}{'n':>5}{'众数':>10}{'95% HDI':>16}"
          f"{'左边界后验':>12}{'右边界后验':>12}  判定")
    for name, sel in windows:
        idx = np.where(sel & ok)[0]
        if len(idx) < 12:
            print(f"  {name:<26}{len(idx):>5}   点太少，跳过")
            continue
        x = np.log(rA[idx])
        wsel = wk[idx]
        taus, p = post_const(x)
        pk = int(taus[np.argmax(p)])
        lo, hi = hdi(taus, p)
        pL, pR = float(p[0]), float(p[-1])
        p_int = float(p[1:-1].max()) if len(p) > 2 else 0.0
        # 判据：边界后验 > 内部最大值 ⇒ 被截断
        trunc = (pR >= p_int) or (pL >= p_int)
        side = ("右" if pR >= p_int else "") + ("左" if pL >= p_int else "")
        print(f"  {name:<26}{len(idx):>5}{int(wsel[pk]) % 100:>10}"
              f"{str((int(wsel[lo]) % 100, int(wsel[hi]) % 100)):>16}"
              f"{pL:>12.3f}{pR:>12.3f}  "
              f"{'**边界截断('+side+')**' if trunc else '内部极值 [OK]'}")
        rep[name] = {"n": len(idx), "mode_week": int(wsel[pk]) % 100,
                     "hdi": [int(wsel[lo]) % 100, int(wsel[hi]) % 100],
                     "p_left": pL, "p_right": pR, "p_interior": p_int,
                     "boundary_truncated": bool(trunc)}

    print(f"\n{'='*94}")
    print("  ── 结论 ──")
    any_int = any(not v.get("boundary_truncated", True) for v in rep.values())
    if any_int:
        print("     加宽窗口后**存在内部极值**的窗口 ⇒ 变点可辨识，见上表 [OK] 行")
    else:
        print("     所有窗口的后验都堆在边界 ⇒ **起爆点在本数据上不可辨识**")
    print()
    print("     ⚠️ 方法学教训（写进论文『模型失败』一节）：")
    print("        变点检测的**允许范围**必须显式检查，否则")
    print("        『众数落在边界』会被误当成估计值。")
    print("        判据：**边界处后验 > 内部最大值 ⇒ 报告『不可辨识』**，")
    print("        而不是报告那个边界位置。")

    (RES / "q2_边界诊断.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {RES/'q2_边界诊断.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
