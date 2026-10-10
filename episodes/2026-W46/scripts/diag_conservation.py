#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · Q1 守恒失败的点态诊断（**逐步定位，不靠猜**）。

## 为什么要单独写这个

12 维版跑出来总量从 1.00000000 掉到 0.00001357 —— **全体人口消失**，
说明某个仓室的流**只出不进**。
上一版我用"跑完再比总量"的办法只能知道"错了"，
**不知道错在哪一项**。

## 本脚本

1. **点态检查**：随机取若干 $(t,y)$，检查 $\sum_i \dot y_i = 0$。
   若有残差，逐个转移到出；
2. **逐位查表**：把每个 $k$ 的
   恢复去向 $k\oplus1,k\oplus2$、衰减去向 $k\ominus1,k\ominus2$
   全部打印出来，人工核对是否构成闭环；
3. **定位**：找出"有出无进"的那些项。

用法：
    $PY diag_conservation.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import q1_model as M                                        # noqa: E402


def main() -> int:
    print("=" * 88)
    print("  W46 · Q1 守恒点态诊断")
    print("=" * 88)

    # ---- 1) 转移表 ----
    print("\n  ── 1) 转移去向表（人工核对闭环）──")
    print(f"  {'k':>3} {'(e1,e2)':>9}  {'恢复株1→':>9} {'恢复株2→':>9}  "
          f"{'衰减e1→':>8} {'衰减e2→':>8}  可被株1感染 可被株2感染")
    for k in M.K:
        k1 = k | 1
        k2 = k | 2
        kw1 = k & ~1
        kw2 = k & ~2
        print(f"  {k:>3} {str((M.E1[k], M.E2[k])):>9}  {k1:>9} {k2:>9}  "
              f"{kw1:>8} {kw2:>8}  "
              f"{'是' if M.E1[k]==0 else '否':>10} "
              f"{'是' if M.E2[k]==0 else '否':>10}")

    # ---- 2) 点态守恒 ----
    print("\n  ── 2) 点态检查：Σ dy_i 是否恒为 0 ──")
    pr = M.unpack({"beta0": 1.15, "phi": 1.18, "eps": 0.40, "theta": 4.0,
                   "gamma": 1.0 / 1.8, "omega": 1.0 / 100.0,
                   "rho": 3.0, "seed": 1e-4})
    rng = np.random.default_rng(0)
    worst = 0.0
    worst_y = None
    worst_t = None
    for _ in range(200):
        y = rng.dirichlet(np.ones(M.NVAR))
        t = float(rng.uniform(0, 520))
        d = M.rhs(t, y, pr)
        s = float(d.sum())
        if abs(s) > abs(worst):
            worst, worst_y, worst_t = s, y.copy(), t
    print(f"     200 个随机状态下 max |Σ dy| = {abs(worst):.3e}"
          f"   {'[OK]' if abs(worst) < 1e-12 else '[X] 不守恒'}")

    if abs(worst) >= 1e-12:
        # ---- 3) 逐项归因：把每类的贡献拆开 ----
        print(f"\n  ── 3) 归因（在残差最大的那个状态，t={worst_t:.1f}）──")
        y = worst_y
        d = M.rhs(worst_t, y, pr)
        print(f"     各仓室 dy：")
        for k in M.K:
            print(f"       S{k}={d[M.IDX_S[k]]:+.6f}  "
                  f"I{k}={d[M.IDX_I[k]]:+.6f}  J{k}={d[M.IDX_J[k]]:+.6f}")
        # 逐类核算：本类的"总变化"（S+I+J）
        print(f"\n     逐类总变化（S_k+I_k+J_k 的导数）：")
        tot = 0.0
        for k in M.K:
            c = (d[M.IDX_S[k]] + d[M.IDX_I[k]] + d[M.IDX_J[k]])
            tot += c
            print(f"       类 {k} (e1={M.E1[k]},e2={M.E2[k]}): {c:+.6f}")
        print(f"     合计 {tot:+.6f}")
        # 归类：感染项、恢复项、衰减项
        print(f"\n     分项核对（应各自为零）：")
        seas = max(1.0 + pr["eps"] * np.cos(
            2 * np.pi * (worst_t - pr["theta"]) / 52.0), 0.05)
        S = {k: y[M.IDX_S[k]] for k in M.K}
        I = {k: y[M.IDX_I[k]] for k in M.K}
        J = {k: y[M.IDX_J[k]] for k in M.K}
        i1 = sum(I[k] for k in M.K if M.E1[k] == 0)
        i2 = sum(J[k] for k in M.K if M.E2[k] == 0)
        b, g, w = pr["beta0"], pr["gamma"], pr["omega"]
        # 衰减净流量
        wan = 0.0
        for k in M.K:
            kw1, kw2 = k & ~1, k & ~2
            out = (w * S[k] if kw1 != k else 0) + (w * S[k] if kw2 != k else 0)
            inn = (w * S[kw1] if kw1 != k else 0) + (w * S[kw2] if kw2 != k else 0)
            wan += inn - out
        print(f"       衰减净流量        {wan:+.6f}")
        # 恢复净流量
        rec = 0.0
        for k in M.K:
            k1, k2 = k | 1, k | 2
            out = (g * I[k] if M.E1[k] == 0 else 0) + (g * J[k] if M.E2[k] == 0 else 0)
            inn = (g * I[k1] if k1 == k else 0) + (g * J[k2] if k2 == k else 0)
            rec += inn - out
        print(f"       恢复净流量        {rec:+.6f}")
        # 感染净流量（应恒为 0）
        inf = 0.0
        for k in M.K:
            l1 = b * seas * S[k] * i1 if M.E1[k] == 0 else 0.0
            l2 = b * pr["phi"] * seas * S[k] * i2 if M.E2[k] == 0 else 0.0
            inf += -(l1 + l2) + l1 + l2
        print(f"       感染净流量        {inf:+.6f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
