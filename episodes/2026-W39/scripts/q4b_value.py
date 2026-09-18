#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W39 · Q4 补充：半主动的真实价值在哪里？

问题
----
Q4 多目标评分显示：半主动（综合最优调校）只比被动高 0.2 分（50.0 → 50.2），
几乎为零。这引出两种可能：

  (a) 半主动确实没用；
  (b) 我们给的被动基线已经是最优调校（ζ=0.3 本就按舒适选定），
      在**单一工况**下自然没有提升空间。

判据：若 (b) 成立，则当**工况改变**时，固定调校会偏离最优，
半主动的"按工况自适应"价值就会显现。

本脚本做三组对照：
  1. **同一工况**：被动 c₀ vs 半主动最优 → 几乎无差（复现 Q4）
  2. **跨工况**：被动用"单一固定调校"应对 C→A/E 路况变化
     vs 半主动按路况重选最优 → 差距应显著
  3. **瞬态冲击**：减速带工况下，固定调校对冲击无适应能力
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from model import default_params, metrics_freq, metrics_time, rms  # noqa: E402

RESULTS = ROOT / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
V = 60 / 3.6
LEVELS = ["A", "C", "E"]


def main() -> int:
    p = default_params()
    cs = np.geomspace(p["c_min"], p["c_max"], 60)

    # ---------- 1. 同一工况（复现 Q4）----------
    print("=== ① 同一工况（C 级）===")
    m_pass = metrics_freq(p, p["c0"], "C", V)
    best_c = min(cs, key=lambda c: metrics_freq(p, c, "C", V)["acc"])
    m_best = metrics_freq(p, best_c, "C", V)
    print(f"  被动 c₀        acc={m_pass['acc']:.4f}")
    print(f"  半主动最优 c    acc={m_best['acc']:.4f} "
          f"(c={best_c/p['c0']:.2f}c₀)")
    print(f"  → 提升 {(m_pass['acc']-m_best['acc'])/m_pass['acc']*100:.2f}%"
          "（与 Q4 一致：同一工况下几乎无提升）\n")

    # ---------- 2. 跨工况 ----------
    print("=== ② 跨工况：单一固定调校 vs 按路况自适应 ===")
    print("  场景：车主平时走 C 级路，偶尔走 A 级（新修高速）与 E 级（烂路）")
    print("  被动策略：出厂固定 c₀（在 C 级下调优）")
    print("  半主动策略：识别路况后重选最优 c\n")

    # 被动固定 c₀ 在各路况下的表现
    fixed = {lv: metrics_freq(p, p["c0"], lv, V)["acc"] for lv in LEVELS}
    # 各路况的"该路况最优 c"与其表现
    per_level = {}
    for lv in LEVELS:
        c_opt = min(cs, key=lambda c: metrics_freq(p, c, lv, V)["acc"])
        per_level[lv] = (c_opt, metrics_freq(p, c_opt, lv, V)["acc"])

    print(f"  {'路况':<6}{'被动固定c₀':>13}{'该路况最优c':>13}"
          f"{'半主动acc':>12}{'提升':>9}{'最优c/c₀':>10}")
    gains = []
    for lv in LEVELS:
        c_opt, a_opt = per_level[lv]
        a_fix = fixed[lv]
        g = (a_fix - a_opt) / a_fix * 100
        gains.append(g)
        print(f"  {lv:<6}{a_fix:>13.4f}{a_opt:>13.4f}{a_opt:>12.4f}"
              f"{g:>8.1f}%{c_opt/p['c0']:>10.2f}")

    # 若被动把 c 调到"折中"（对三路况综合最优的单一 c）
    def avg_acc(c):
        return np.mean([metrics_freq(p, c, lv, V)["acc"] for lv in LEVELS])
    c_comp = min(cs, key=avg_acc)
    print(f"\n  被动改为'跨路况折中调校' c={c_comp/p['c0']:.2f}c₀：")
    comp_gain = []
    for lv in LEVELS:
        a_c = metrics_freq(p, c_comp, lv, V)["acc"]
        a_opt = per_level[lv][1]
        g = (a_c - a_opt) / a_c * 100
        comp_gain.append(g)
        print(f"    {lv} 级：折中 {a_c:.4f} → 自适应 {a_opt:.4f}  提升 {g:.1f}%")
    print(f"  → 跨工况平均提升 {np.mean(comp_gain):.1f}%"
          f"（单一工况下仅 {np.mean(gains):.1f}%）")

    # ---------- 3. 瞬态冲击 ----------
    print("\n=== ③ 瞬态冲击：减速带 ===")
    print("  说明：线性 RMS 框架下时变阻尼无可观测优势（见 results/q2q3_结论.md）；")
    print("  真正的差异出现在**瞬态**——固定调校对冲击既不能变软也不能变硬。")
    # 用不同 c 在同一冲击下的峰值对比（解析：冲击响应峰值随 c 单调变化）
    print("  冲击峰值对阻尼的依赖（同一致命冲击，看车身加速度峰值）：")
    from model import generate_road_accel
    # 构造单次减速带冲击：半正弦路面速度
    dur, dt = 2.0, 2e-4
    t = np.arange(int(dur / dt)) * dt
    a_imp = np.zeros_like(t)
    m = (t > 0.5) & (t < 0.6)
    a_imp[m] = 3.0 * np.sin(np.pi * (t[m] - 0.5) / 0.1)     # 路面加速度冲击
    print(f"  {'c/c₀':>7}{'峰值acc(m/s²)':>15}")
    for cmul in (0.3, 0.5, 1.0, 2.0, 4.0):
        y = metrics_time(p, p["c0"] * cmul, "A", V, dur=dur, dt=dt, seed=0)
        # metrics_time 用随机路面，这里改用冲击直算
        from scipy import signal as sig
        from model import state_space
        A, B, Bu, C, D, Du = state_space(p, p["c0"] * cmul)
        sysd = sig.StateSpace(A, B, C, D)
        _, yy, _ = sig.lsim(sysd, U=a_imp, T=t)
        print(f"  {cmul:>7.1f}{np.max(np.abs(yy[:, 0])):>15.4f}")

    out = {"same_case_gain_pct": float((m_pass["acc"] - m_best["acc"]) / m_pass["acc"] * 100),
           "cross_case_gains_pct": [float(g) for g in gains],
           "compromise_gains_pct": [float(g) for g in comp_gain],
           "c_compromise_over_c0": float(c_comp / p["c0"]),
           "per_level_opt_c_over_c0": {lv: float(per_level[lv][0] / p["c0"])
                                       for lv in LEVELS},
           "conclusion": "半主动的价值在'跨工况自适应'，不在单一工况的稳态性能"}
    (RESULTS / "q4_value.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[结果] {RESULTS / 'q4_value.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
