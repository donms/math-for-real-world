#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · Q1 双亚型季节性传播模型（**12 维完整多株 SIR**，严格守恒）。

## 为什么是 12 维（**两个失败版本换来的**）

我先后试过两种"紧凑"写法，都不守恒：

| 版本 | 写法 | 结果 |
|---|---|---|
| v1（6 维）| 累计感染 $\Lambda_i$ + $e^{-\Lambda_j/N}$ 交叉免疫因子 | 累计量不随免疫衰减回收 ⇒ 总量从 0.9015 漂到 **1.6975** |
| v2（9 维）| 显式免疫仓室，但**按易感池比例分摊**恢复者去向 | 分摊系数按**易感池**算，恢复者却来自**感染池**，两池形状不同 ⇒ 漂移 **1.07** |

**根因**：只要"某类人的去向"需要**事后按比例猜测**，守恒就保不住。

⇒ **正确做法：把免疫史完全展开，让每一个转移都有唯一确定的源与汇。**

## 模型定义

用二元组 $(e_1,e_2)\in\{0,1\}^2$ 表示"是否**曾**感染过第 $i$ 株"，
$e_i=1$ 表示**完全免疫**（不再感染第 $i$ 株）。共 **4 个免疫类**：

| 类 | $(e_1,e_2)$ | 含义 |
|---|---|---|
| 0 | $(0,0)$ | 从未感染 |
| 1 | $(1,0)$ | 只感染过株 1 |
| 2 | $(0,1)$ | 只感染过株 2 |
| 3 | $(1,1)$ | 两株都感染过 |

每个免疫类再分：易感 $S_k$、正感染株 1（$I_k$）、正感染株 2（$J_k$）。
**共 12 个仓室，且 $\sum(S_k+I_k+J_k)=1$ 恒成立。**

### 转移规则（**每个转移源汇唯一**）

* **感染**（株 $i$，仅当 $e_i=0$）：
  $S_k \to I_k$（株 1）或 $S_k \to J_k$（株 2）
* **恢复**（速率 $\gamma$）：$I_k \to S_{k\oplus 1}$（把 $e_1$ 置 1），
  $J_k \to S_{k\oplus 2}$（把 $e_2$ 置 1）
  —— $\oplus$ 是"按位或"
* **免疫衰减**（速率 $\omega$）：$S_k \to S_{k\ominus 1}$（清掉 $e_1$），
  或 $S_k \to S_{k\ominus 2}$（清掉 $e_2$）
  —— 每个位独立以 $\omega$ 衰减

> 12 维里**没有任何"按比例分摊"**：每条边都是确定的 $k\to k'$。

### 传播与观测

$$\lambda_{i,k}=\beta_0\,\phi_i\,\Sigma(t)\,S_k\,I_{i,\text{tot}},
\qquad \Sigma(t)=1+\epsilon\cos\tfrac{2\pi(t-\theta)}{52}$$

* 株 1 的总感染 $I_1^{\text{tot}}=\sum_k I_k$（只感染 $e_1=0$ 的类，即 $k\in\{0,2\}$）
* 株 2 的总感染 $I_2^{\text{tot}}=\sum_k J_k$（$k\in\{0,1\}$）
* 观测：$y_t=\rho(I_1^{\text{tot}}+I_2^{\text{tot}})\cdot100+\varepsilon$；
  份额 $z_t=I_1^{\text{tot}}/(I_1^{\text{tot}}+I_2^{\text{tot}})$
* $\phi_1=1,\;\phi_2=\phi$（**适应度比**，Q1 要反演的核心量）

用法：
    $PY q1_model.py --sim
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402
from scipy.integrate import solve_ivp    # noqa: E402

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
RES = ROOT / "results"
FIGS = RES / "figs"
RES.mkdir(parents=True, exist_ok=True)
FIGS.mkdir(parents=True, exist_ok=True)

# ---- 免疫类与索引 ----
# 类 k 的位表示：bit0 = 曾感染株1，bit1 = 曾感染株2
K = [0, 1, 2, 3]                 # (0,0) (1,0) (0,1) (1,1)
E1 = {k: (k & 1) for k in K}     # 对株1 免疫？
E2 = {k: (k >> 1) & 1 for k in K}
# 索引布局：S_0..S_3, I_0..I_3（株1）, J_0..J_3（株2）
IDX_S = {k: k for k in K}
IDX_I = {k: 4 + k for k in K}
IDX_J = {k: 8 + k for k in K}
NVAR = 12

PNAMES = ["beta0", "phi", "eps", "theta", "gamma", "omega", "rho", "seed"]


def unpack(p: dict) -> dict:
    return {k: float(p[k]) for k in PNAMES}


def rhs(t, y, pr, N=1.0):
    r"""12 维右端。**每个转移都有唯一的源与汇** ⇒ 总量严格守恒。"""
    y = np.maximum(y, 0.0)
    seas = max(1.0 + pr["eps"] * np.cos(2 * np.pi * (t - pr["theta"]) / 52.0),
               0.05)
    b, g, w = pr["beta0"], pr["gamma"], pr["omega"]

    S = {k: y[IDX_S[k]] for k in K}
    I = {k: y[IDX_I[k]] for k in K}
    J = {k: y[IDX_J[k]] for k in K}
    I1tot = sum(I[k] for k in K if E1[k] == 0)
    I2tot = sum(J[k] for k in K if E2[k] == 0)

    d = np.zeros(NVAR)
    # ---- ① 出流：感染（S_k→I_k/J_k）、衰退（每位独立 ω）、恢复（I_k→、J_k→）----
    for k in K:
        # 该类的力感染（只有尚未免疫该株的类会被感染）
        lam1 = b * seas * S[k] * I1tot / N if E1[k] == 0 else 0.0
        lam2 = b * pr["phi"] * seas * S[k] * I2tot / N if E2[k] == 0 else 0.0
        d[IDX_S[k]] += -(lam1 + lam2)
        d[IDX_I[k]] += lam1 - g * I[k]
        d[IDX_J[k]] += lam2 - g * J[k]
        # 免疫衰减：**每个"已免疫"的位独立**以 ω 清零（流出）
        d[IDX_S[k]] += -w * S[k] * (E1[k] + E2[k])

    # ---- ② 入流：**从定义出发推导，不试错** ----
    #
    # ★★★ W46：守恒在这里错了**四次**，最后靠"按定义写"才通过。
    #
    # **推导规则**（目标类 $k$，免疫位 $b\in\{1,2\}$）：
    #
    # * **恢复入流**：感染株 $b$ 的是 $E_b{=}0$ 的类，恢复后 $E_b$ 置 1。
    #   ⇒ 目标 $k$ 必须 $E_b(k){=}1$，且**来源**是把该位改回 0、另一株位不变的类
    #   ⇒ 来源 $= k\ominus b$，即 **`k & ~b`**。
    # * **衰减入流**：免疫位从 1 衰减到 0。
    #   ⇒ 目标 $k$ 必须 $E_b(k){=}0$，**来源** $= k\oplus b$，即 **`k | b`**。
    #
    # ⚠️ 两个方向**恰好相反**（恢复 `& ~b`、衰减 `| b`）。
    #    写反不会发散，只会"少一截"，很容易被忽略 ——
    #    实测残差分解：感染净 0、衰减净 0、**恢复净 −0.4974 / −0.0941**
    #    （换了两种错写法都还剩一截）。
    for k in K:
        # 衰减入流（位 1→0，来源是 k|b）
        if E1[k] == 0:
            d[IDX_S[k]] += w * S[k | 1]
        if E2[k] == 0:
            d[IDX_S[k]] += w * S[k | 2]
        # 恢复入流（目标该位必须为 1；来源是该位为 0、另一株位相同的类）
        if E1[k] == 1:
            d[IDX_S[k]] += g * I[k & ~1]
        if E2[k] == 1:
            d[IDX_S[k]] += g * J[k & ~2]
    return d


def simulate(pr: dict, tmax: float = 26 * 52, y0=None, n_out: int = 4000,
             max_step: float = 0.5):
    if y0 is None:
        y0 = np.zeros(NVAR)
        y0[IDX_S[0]] = 1.0 - 2 * pr["seed"]
        y0[IDX_I[0]] = pr["seed"]        # 株1 种子（类 0 对株1 不免疫）
        y0[IDX_J[0]] = pr["seed"]        # 株2 种子
    t_eval = np.linspace(0, tmax, n_out)
    # `rhs` 签名 (t, y, pr)：args 只给 pr。
    sol = solve_ivp(rhs, (0, tmax), y0, args=(pr,), t_eval=t_eval,
                    method="LSODA", rtol=1e-8, atol=1e-11, max_step=0.5)
    return sol.t, sol.y


def totals(y: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """返回 (总感染, 株1 总感染, 株2 总感染)。"""
    i1 = sum(y[IDX_I[k]] for k in K if E1[k] == 0)
    i2 = sum(y[IDX_J[k]] for k in K if E2[k] == 0)
    return i1 + i2, i1, i2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--tmax", type=float, default=12 * 52)
    args = ap.parse_args()

    # 默认参数：R0(A)=beta0/gamma≈2.2，株2 略强，年周期，免疫约 2 年
    pr = unpack({"beta0": 1.15, "phi": 1.18, "eps": 0.40, "theta": 4.0,
                 "gamma": 1.0 / 1.8, "omega": 1.0 / 100.0,
                 "rho": 3.0, "seed": 1e-4})
    t, y = simulate(pr, tmax=args.tmax)
    It, I1, I2 = totals(y)
    tot = y.sum(axis=0)
    drift = float(np.abs(tot - tot[0]).max())
    sh = I1 / np.maximum(It, 1e-12)

    print("=" * 92)
    print("  W46 · Q1 双亚型季节性模型（12 维，严格守恒）")
    print("=" * 92)
    print(f"  R0(株1) = beta0/gamma = {pr['beta0']/pr['gamma']:.3f}")
    print(f"  R0(株2) = beta0*phi/gamma = {pr['beta0']*pr['phi']/pr['gamma']:.3f}")
    print(f"  免疫衰减特征时间 1/omega = {1/pr['omega']:.0f} 周")
    print(f"\n  积分 {t[0]:.0f}–{t[-1]:.0f} 周（{t[-1]/52:.0f} 年）")
    print(f"  守恒：总量 {tot[0]:.8f} → {tot[-1]:.8f}  最大漂移 {drift:.2e}  "
          f"{'[OK]' if drift < 1e-8 else '[X] 不守恒'}")
    print(f"  非负：最小值 {y.min():.3e}  "
          f"{'[OK]' if y.min() > -1e-9 else '[X] 有负值'}")
    print(f"  I_total：max {It.max():.4f}  min {It.min():.2e}")
    print(f"  株1 份额：{sh.min():.3f} ~ {sh.max():.3f}")
    if It.std() > 1e-12:
        ac = float(np.corrcoef(It[:-52], It[52:])[0, 1])
        print(f"  lag-52 自相关 {ac:+.3f}"
              f"{'（有年周期）' if abs(ac) > 0.3 else '（周期不明显）'}")

    fig, ax = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    ax[0].plot(t / 52, It * 100, color="#c0392b", lw=1.0)
    ax[0].set_ylabel("总感染占比 (%)")
    ax[0].set_title("双亚型季节性模型（12 维，默认参数）", fontsize=13)
    ax[0].grid(alpha=0.3)
    ax[1].plot(t / 52, I1 * 100, label="株1 (A)", color="#2c6fbb", lw=1.0)
    ax[1].plot(t / 52, I2 * 100, label="株2 (B)", color="#e67e22", lw=1.0)
    ax[1].set_ylabel("各株感染占比 (%)")
    ax[1].legend(fontsize=9)
    ax[1].grid(alpha=0.3)
    ax[2].plot(t / 52, sh, color="#27ae60", lw=1.0)
    ax[2].axhline(0.5, ls="--", color="k", lw=0.8)
    ax[2].set_ylabel("株1 份额")
    ax[2].set_xlabel("年")
    ax[2].grid(alpha=0.3)
    fig.tight_layout()
    f = FIGS / "q1_正演.png"
    fig.savefig(f, dpi=150)
    plt.close(fig)
    print(f"\n  -> {f}")

    (RES / "q1_正演.json").write_text(json.dumps({
        "params": pr, "weeks": float(t[-1]), "conservation_drift": drift,
        "I_max": float(It.max()), "share_range": [float(sh.min()),
                                                  float(sh.max())],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
