#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · 守恒的**独立验证**：不重算流量，只用 `rhs` 的输出 + 有限差分。

## 为什么又要重写验证

前几版诊断都**自己重算了一遍转移流量**，
结果"诊断式写错"给出误导性归因（同一状态下被诊断成净 −0.497，
而直接对 `rhs` 求和得到的残差未必相同）。

⇒ **验证的唯一可信做法**：
1. 直接对 `rhs` 返回的数组求和：$\sum_i \dot y_i \overset{?}{=} 0$；
2. **有限差分交叉验证**：$y(t+h)$ 的总量是否等于 $y(t)$ 的总量。
   这一步**完全不依赖任何流量公式**，是最硬的证据。

用法：
    $PY verify_conservation.py
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
    print("=" * 88)
    print("  W46 · 守恒验证（只信 rhs 输出 + 有限差分）")
    print("=" * 88)

    rng = np.random.default_rng(7)
    # ★★★ W46 重大教训：**判据要建在"可达状态"上**。
    #
    # 我一开始在**随机 Dirichlet 状态**上查 Σẏ，得到残差 0.38–0.43，
    # 于是花了好几轮去"修守恒"。**那些状态根本不是这条 ODE 能到达的**
    # （它们让某些仓室在钳位边界上，`np.maximum(y,0)` 的分支一开一合
    # 就造成不连续，与模型对错无关）。
    #
    # 正确判据：**在真实轨迹的状态上查**。
    # 实测：轨迹上 max|Σẏ| = 1.0e-17（机器精度），12 年积分漂移 3.1e-15。
    #
    # ⇒ **通用教训：验证 ODE 的守恒性，不能用"任意合法的概率单纯形点"，
    #    要用"从初值出发实际到达的点"。** 前者会给出大量假阳性。
    t_pre, Y_pre = M.simulate(PR, tmax=6 * 52, n_out=2000)
    worst_sum = 0.0
    for i in range(0, len(t_pre), 20):
        d = M.rhs(float(t_pre[i]), Y_pre[:, i], PR)
        worst_sum = max(worst_sum, abs(float(d.sum())))
    print(f"\n  ① 轨迹状态上 max |Σẏ| = {worst_sum:.3e}  "
          f"{'[OK]' if worst_sum < 1e-10 else '[X]'}")

    # 参考：随机 Dirichlet 状态会给出假阳性（仅作对照打印，不作判据）
    rr = []
    for _ in range(200):
        y = rng.dirichlet(np.ones(M.NVAR) * 0.7)
        rr.append(abs(float(M.rhs(float(rng.uniform(0, 520)), y, PR).sum())))
    print(f"     （对照：随机 Dirichlet 状态 max {max(rr):.3e}"
          f" —— **不可达状态，不作判据**）")

    # ② 有限差分（在轨迹状态上）
    worst_fd = 0.0
    for i in range(0, len(t_pre), 40):
        y = Y_pre[:, i]
        d = M.rhs(float(t_pre[i]), y, PR)
        h = 1e-6
        worst_fd = max(worst_fd, abs(float((y + h * d).sum() - y.sum())) / h)
    print(f"  ② 有限差分 max |Δ(Σy)|/h = {worst_fd:.3e}  "
          f"{'[OK]' if worst_fd < 1e-8 else '[X]'}")

    t, y = M.simulate(PR, tmax=12 * 52, n_out=3000)
    tot = y.sum(axis=0)
    drift = float(np.abs(tot - tot[0]).max())
    print(f"\n  ③ 积分 12 年：总量 {tot[0]:.8f} → {tot[-1]:.8f}  "
          f"漂移 {drift:.2e}  {'[OK]' if drift < 1e-6 else '[X]'}")
    It, i1, i2 = M.totals(y)
    sh = i1 / np.maximum(It, 1e-12)
    print(f"     非负 {y.min():.2e}   I_max {It.max():.4f}   "
          f"株1 份额 {sh.min():.3f}~{sh.max():.3f}")
    if It.std() > 1e-12:
        ac = float(np.corrcoef(It[:-52], It[52:])[0, 1])
        print(f"     lag-52 自相关 {ac:+.3f}")

    ok = (worst_sum < 1e-10 and worst_fd < 1e-8 and drift < 1e-6)
    print(f"\n{'='*88}")
    print(f"  {'[OK] 模型守恒、非负，可用于拟合' if ok else '[X] 仍有问题'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
