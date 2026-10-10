#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · 点态守恒残差的**逐类手算核对**（解决"点态 −0.497 vs 积分 1e-15"的矛盾）。

## 矛盾

* 点态：随机非负状态下 $\sum\dot y=-0.497$（看起来漏了 0.5 的质量）
* 积分：12 年总量漂移仅 **1.33e-15**（机器精度）

**两者不可能同时为真** —— 若真有系统性漏项，积分必然漂移。

## 排查思路

逐类手算「$S_k$ 的入流 + 出流」，
与 `rhs` 返回的 $dS_k$ 对照。
**重点查我的掩码条件**：`(k|1)!=k` 用来判"该位为 0"，
但 `k` 取值是 $\{0,1,2,3\}$，`k|1` 对 $k=1,3$ 等于 $k$ —— 这没问题。
要查的是**入流项是否重复计入**（例如同时加了 `w*S[k|1]` 和 `g*I[k&~1]`）。

用法：
    $PY diag_pointwise.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import q1_model as M                                        # noqa: E402

PR = M.unpack({"beta0": 1.15, "phi": 1.18, "eps": 0.40, "theta": 4.0,
               "gamma": 1.0 / 1.8, "omega": 1.0 / 100.0,
               "rho": 3.0, "seed": 1e-4})


def main() -> int:
    rng = np.random.default_rng(1)
    # 复现出残差最大的那个状态
    worst, wy, wt = 0.0, None, None
    for _ in range(500):
        y = rng.dirichlet(np.ones(M.NVAR) * 0.7)
        t = float(rng.uniform(0, 520))
        s = float(M.rhs(t, y, PR).sum())
        if abs(s) > abs(worst):
            worst, wy, wt = s, y.copy(), t
    y, t = wy, wt
    print("=" * 88)
    print(f"  W46 · 点态残差逐类核对（t={t:.2f}, Σẏ={worst:+.6f}）")
    print("=" * 88)

    d = M.rhs(t, y, PR)
    seas = max(1.0 + PR["eps"] * np.cos(2 * np.pi * (t - PR["theta"]) / 52.0),
               0.05)
    b, g, w = PR["beta0"], PR["gamma"], PR["omega"]
    S = {k: max(y[M.IDX_S[k]], 0.0) for k in M.K}
    I = {k: max(y[M.IDX_I[k]], 0.0) for k in M.K}
    J = {k: max(y[M.IDX_J[k]], 0.0) for k in M.K}
    i1 = sum(I[k] for k in M.K if M.E1[k] == 0)
    i2 = sum(J[k] for k in M.K if M.E2[k] == 0)

    # ---- 手算每个 dS_k，与 rhs 对照 ----
    print(f"\n  {'k':>2} {'手算 dS_k':>12} {'rhs dS_k':>12} {'差':>12}"
          f"   {'出流(感+衰)':>12} {'入流(衰)':>10} {'入流(复)':>10}")
    tot_manual = 0.0
    tot_rhs = 0.0
    for k in M.K:
        lam1 = b * seas * S[k] * i1 if M.E1[k] == 0 else 0.0
        lam2 = b * PR["phi"] * seas * S[k] * i2 if M.E2[k] == 0 else 0.0
        out = lam1 + lam2 + w * S[k] * (M.E1[k] + M.E2[k])
        win = (w * S[k | 1] if (k | 1) != k else 0.0) \
            + (w * S[k | 2] if (k | 2) != k else 0.0)
        rin = (g * I[k & ~1] if (k | 1) != k else 0.0) \
            + (g * J[k & ~2] if (k | 2) != k else 0.0)
        manual = -out + win + rin
        rhs = d[M.IDX_S[k]]
        tot_manual += manual
        tot_rhs += rhs
        print(f"  {k:>2} {manual:>12.6f} {rhs:>12.6f} {rhs-manual:>12.2e}"
              f"   {out:>12.6f} {win:>10.6f} {rin:>10.6f}")

    # ---- 全部 12 个仓室的 rhs 与手算之差 ----
    print(f"\n  Σ dS_k 手算 {tot_manual:+.6f}   rhs {tot_rhs:+.6f}")
    print(f"  Σ dI_k rhs {sum(d[M.IDX_I[k]] for k in M.K):+.6f}"
          f"   （手算应为 {-g*sum(I.values()):+.6f}）")
    print(f"  Σ dJ_k rhs {sum(d[M.IDX_J[k]] for k in M.K):+.6f}"
          f"   （手算应为 {-g*sum(J.values()):+.6f}）")
    print(f"\n  分解 rhs 的 Σẏ：")
    sS = sum(d[M.IDX_S[k]] for k in M.K)
    sI = sum(d[M.IDX_I[k]] for k in M.K)
    sJ = sum(d[M.IDX_J[k]] for k in M.K)
    print(f"     Σ dS = {sS:+.6f}   Σ dI = {sI:+.6f}   Σ dJ = {sJ:+.6f}")
    print(f"     合计 = {sS+sI+sJ:+.6f}")
    # 分项汇总（**先算再打印** —— f-string 里塞复杂表达式会触发语法错误）
    inf_out = sum(
        (b * seas * S[k] * i1 if M.E1[k] == 0 else 0.0)
        + (b * PR["phi"] * seas * S[k] * i2 if M.E2[k] == 0 else 0.0)
        for k in M.K)
    inf_in = i1 * sum(b * seas * S[k] for k in M.K if M.E1[k] == 0) \
        + i2 * sum(b * PR["phi"] * seas * S[k]
                   for k in M.K if M.E2[k] == 0)
    wan_out = sum(w * S[k] * (M.E1[k] + M.E2[k]) for k in M.K)
    wan_in = sum(
        (w * S[k | 1] if (k | 1) != k else 0.0)
        + (w * S[k | 2] if (k | 2) != k else 0.0)
        for k in M.K)
    rec_out = g * (sum(I.values()) + sum(J.values()))
    rec_in = sum(
        (g * I[k & ~1] if (k | 1) != k else 0.0)
        + (g * J[k & ~2] if (k | 2) != k else 0.0)
        for k in M.K)

    print("\n     分项（流入 − 流出 应为 0）：")
    for nm, a, bb in (("感染", inf_in, inf_out), ("衰减", wan_in, wan_out),
                      ("恢复", rec_in, rec_out)):
        print(f"       {nm}: 流入 {a:+.6f}  流出 {bb:+.6f}  "
              f"净 {a-bb:+.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
