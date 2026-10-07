#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W48 · 问题 3：门控动力学 —— **该用几个状态**。

## ★★ 本问的核心不是"解 ODE"，而是**模型选择**

### 实验事实（题面 §2.4b，来源 Kuhne 等 *PNAS* 2019，作者含 Hegemann）

| 事实 | 含义 |
|---|---|
| 暗适应态**只有** all-trans, C=N-**anti** 一种构象 | 起点单一 |
| 光照后**分支**为 13-cis, C=N-**anti** 或 13-cis, C=N-**syn** | **两条并行循环** |
| anti 循环：晚期 M 样态依次导通 H+ 与 Na+ | 混合阳离子电导 |
| syn 异构体 = **长寿命 P480**，是**闭合通道态** | **P480 不是晚期中间体，而是"第二暗态"** |
| **P480 可被光再次激发** | 进入 syn 循环，开放态**电导小、质子选择性高** |
| 连续光照下的失活与选择性改变 | 来自**两条循环的相对布居变化** |

### 本脚本要证明的两件事

**（A）教科书四态线性链在原理上做不出"峰-稳态落差"**

四态线性链（$C\to O\to D\to C$）在恒定光照下，
所有状态趋近**唯一稳态**，光电流 $I\propto O(t)$ **单调上升**后稳定
（或单调下降到稳定），**不会出现"先冲到峰值再大幅回落"**。

> ⚠️ 严谨地说：若把"快速激发态"也算进去，线性链在启动瞬间
> 会有个**极短的尖峰**（激发态快速充放）。但它**不是一个"慢"过程**，
> 而实验观察到的失活发生在**数百毫秒到秒**的尺度上。
> **本脚本用数值求解把这一点定量化。**

**（B）必须"分支 + 可光激发的长寿命态"才能复现实验**

最小结构：
* **分支点**：$A\to O_1$（anti 循环）或 $A\to P$（syn 循环）；
* **长寿命态 $P$（P480）**：既热弛豫回 $A$（慢），又可被光激发进 $O_2$；
* **两个开放态** $O_1,O_2$，电导与离子选择性不同。

## 两个模型

### 模型 L（线性四态）

$$
\dot O=k_1\Phi(1-O-D)-k_2O,\qquad
\dot D=k_3O-k_4D
$$

### 模型 B（分支 + 光可激发长寿命态）

$$
\begin{aligned}
\dot A &= -k_{\text{anti}}\Phi A - k_{\text{syn}}\Phi A
        + k_{1}O_1 + k_{2}O_2 + k_{r}P\\
\dot O_1 &= k_{\text{anti}}\Phi A - k_{1}O_1\\
\dot P &= k_{\text{syn}}\Phi A - k_{r}P - k_{p}\Phi P\\
\dot O_2 &= k_{p}\Phi P - k_{2}O_2
\end{aligned}
$$

（$A+O_1+P+O_2=1$ 守恒，已做自检）

**光电流**：$I(t)=g_1O_1(t)+g_2O_2(t)$，
按实验取 $g_2/g_1\approx0.3$（syn 开放态**电导小**）。

## 输出

* 两个模型的 $I(t)$ 曲线（恒定光照）对比；
* **峰-稳态比** $I_{\text{peak}}/I_{\text{ss}}$ 与**失活时间尺度**；
* 与实验量级（失活发生在数百 ms 到 s）对照；
* **离子选择性转变**的定性解释（连续光照下 $O_2$ 占比上升）。

用法：
    $PY q3_gating.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[3]
RES = ROOT / "episodes" / "2026-W48" / "results"
RES.mkdir(parents=True, exist_ok=True)

# ── 速率常数（量级取自题面 §2.4a 与文献范围，单位 ms^-1）──
PAR = {
    "k1": 1.0,        # O1 -> A（关闭，tau ~1 ms）
    "k2": 0.05,       # O2 -> A（tau ~20 ms）
    "k_anti": 1.0,    # A --光--> O1
    "k_syn": 0.02,    # A --光--> P（分支比小，syn 是次要通路）
    "k_r": 0.002,     # P -> A 热弛豫（**慢**，tau ~500 ms）
    "k_p": 0.5,       # P --光--> O2（P480 可被光再次激发）
    "g2_over_g1": 0.3 # syn 开放态电导小
}
# 线性链参数（把"开放"对应到 O，把 D 当作脱敏）
PAR_L = {
    "k1": 1.0,        # C --光--> O
    "k2": 0.05,       # O -> D
    "k3": 0.002,      # D -> C（慢恢复）
}


def model_L(t: float, y: np.ndarray, Phi: float, p: dict) -> list[float]:
    r"""线性四态：C --Phi k1--> O --k2--> D --k3--> C。

    设 O 为开放态；C = 1 - O - D。
    """
    O, D = y
    C = 1.0 - O - D
    dO = p["k1"] * Phi * C - p["k2"] * O
    dD = p["k2"] * O - p["k3"] * D
    return [dO, dD]


def model_B(t: float, y: np.ndarray, Phi: float, p: dict) -> list[float]:
    r"""分支 + 光可激发长寿命态：A -> O1（anti）/ P（syn）；P 可光激发 -> O2。"""
    A, O1, P, O2 = y
    dA = (-p["k_anti"] * Phi * A - p["k_syn"] * Phi * A
          + p["k1"] * O1 + p["k2"] * O2 + p["k_r"] * P)
    dO1 = p["k_anti"] * Phi * A - p["k1"] * O1
    dP = p["k_syn"] * Phi * A - p["k_r"] * P - p["k_p"] * Phi * P
    dO2 = p["k_p"] * Phi * P - p["k2"] * O2
    return [dA, dO1, dP, dO2]


def current(y: np.ndarray, which: str, p: dict) -> float:
    if which == "L":
        return float(y[0])                         # O
    return float(y[1] + p["g2_over_g1"] * y[3])    # O1 + (g2/g1) O2


def simulate(which: str, Phi: float, t_end_ms: float,
             n: int = 4000) -> dict:
    """恒定光照下的光电流 I(t)。"""
    t_eval = np.linspace(0.0, t_end_ms, n)
    if which == "L":
        y0 = [0.0, 0.0]
        f, p = model_L, PAR_L
    else:
        y0 = [1.0, 0.0, 0.0, 0.0]
        f, p = model_B, PAR
    sol = solve_ivp(f, (0.0, t_end_ms), y0, t_eval=t_eval, args=(Phi, p),
                    rtol=1e-9, atol=1e-12, method="LSODA")
    I = np.array([current(sol.y[:, i], which, p)
                  for i in range(sol.y.shape[1])])
    # 守恒自检
    cons = float(np.abs(sol.y.sum(axis=0) - 1.0).max())
    # 峰-稳态
    iPk = int(np.argmax(I))
    Ipk = float(I[iPk])
    Iss = float(I[-1])
    ratio = Ipk / Iss if Iss > 1e-12 else np.inf
    # 失活时间尺度：从峰值降到 (Ipk+Iss)/2 的时刻 - 峰值时刻
    half = 0.5 * (Ipk + Iss)
    after = I[iPk:]
    idx = np.where(after <= half)[0]
    tau_ms = float(t_eval[iPk + idx[0]] - t_eval[iPk]) if idx.size else np.nan
    return {"t_ms": sol.t, "I": I, "I_peak": Ipk, "I_ss": Iss,
            "peak_over_ss": ratio, "inactivation_tau_ms": tau_ms,
            "mass_error": cons, "success": bool(sol.success)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phi", type=float, default=1.0)
    ap.add_argument("--t-end-ms", type=float, default=2000.0)
    args = ap.parse_args()

    print("=" * 94)
    print("  W48 · 问题 3：门控动力学 —— 该用几个状态")
    print("=" * 94)
    print(f"\n  恒定光照 Phi = {args.phi}（相对单位），时长 {args.t_end_ms:.0f} ms")
    print(f"  速率常数（ms^-1）：")
    print(f"     线性链  k1={PAR_L['k1']} k2={PAR_L['k2']} k3={PAR_L['k3']}")
    print(f"     分支模型 k_anti={PAR['k_anti']} k_syn={PAR['k_syn']} "
          f"k1={PAR['k1']} k2={PAR['k2']} k_r={PAR['k_r']} k_p={PAR['k_p']} "
          f"g2/g1={PAR['g2_over_g1']}")

    resL = simulate("L", args.phi, args.t_end_ms)
    resB = simulate("B", args.phi, args.t_end_ms)

    print(f"\n  -- 两个模型的 I(t) 关键量 --")
    print(f"     {'模型':<22}{'I_peak':>11}{'I_ss':>11}"
          f"{'峰/稳态':>10}{'失活tau(ms)':>13}{'守恒误差':>11}")
    print(f"     {'L 线性四态':<22}{resL['I_peak']:>11.5f}"
          f"{resL['I_ss']:>11.5f}{resL['peak_over_ss']:>10.3f}"
          f"{resL['inactivation_tau_ms']:>13.1f}{resL['mass_error']:>11.1e}")
    print(f"     {'B 分支+光可激发':<22}{resB['I_peak']:>11.5f}"
          f"{resB['I_ss']:>11.5f}{resB['peak_over_ss']:>10.3f}"
          f"{resB['inactivation_tau_ms']:>13.1f}{resB['mass_error']:>11.1e}")

    # ── I(t) 抽样表 ──
    print(f"\n  -- I(t) 抽样（每模型 12 点）--")
    print(f"     {'t(ms)':>9}{'I_线性':>12}{'I_分支':>12}")
    for tq in np.linspace(0, args.t_end_ms, 12):
        iL = int(np.argmin(np.abs(resL["t_ms"] - tq)))
        iB = int(np.argmin(np.abs(resB["t_ms"] - tq)))
        print(f"     {tq:>9.1f}{resL['I'][iL]:>12.5f}{resB['I'][iB]:>12.5f}")

    # ── 结论判定 ──
    print(f"\n  {'='*94}")
    print("  ★ 结论判定：四态线性链能否复现『峰-稳态落差』？")
    rL, rB = resL["peak_over_ss"], resB["peak_over_ss"]
    print(f"     线性链峰/稳态 = {rL:.3f}"
          + ("  => **无落差**（峰即稳态）" if rL < 1.05
             else f"  => 有 {rL:.2f} 倍落差"))
    print(f"     分支模型峰/稳态 = {rB:.3f}"
          + ("  => **有显著落差**" if rB >= 1.05 else "  => 无落差"))
    print(f"\n     线性链失活时间尺度 = {resL['inactivation_tau_ms']:.1f} ms")
    print(f"     分支模型失活时间尺度 = {resB['inactivation_tau_ms']:.1f} ms")

    # ── 离子选择性 ──
    print(f"\n  -- 连续光照下两条循环的布居（分支模型）--")
    print("     （syn 开放态电导小、质子选择性高 => 其占比上升即选择性转变）")
    print(f"     {'t(ms)':>9}{'O1(anti)':>12}{'O2(syn)':>12}{'O2/(O1+O2)':>13}")
    t_eval = np.linspace(0, args.t_end_ms, 800)
    sol = solve_ivp(model_B, (0.0, args.t_end_ms), [1.0, 0, 0, 0],
                    t_eval=t_eval, args=(args.phi, PAR), rtol=1e-9, atol=1e-12,
                    method="LSODA")
    O1, O2 = sol.y[1], sol.y[3]
    for tq in (1, 50, 200, 500, 1000, 2000):
        i = int(np.argmin(np.abs(sol.t - tq)))
        tot = O1[i] + O2[i]
        frac = O2[i] / tot if tot > 1e-15 else 0.0
        print(f"     {tq:>9}{O1[i]:>12.5f}{O2[i]:>12.5f}{frac:>13.3f}")

    out = {
        "参数": {"线性链": PAR_L, "分支模型": PAR},
        "Phi": args.phi, "t_end_ms": args.t_end_ms,
        "线性四态": {"I_peak": resL["I_peak"], "I_ss": resL["I_ss"],
                     "峰稳态比": rL,
                     "失活tau_ms": resL["inactivation_tau_ms"],
                     "守恒误差": resL["mass_error"]},
        "分支模型": {"I_peak": resB["I_peak"], "I_ss": resB["I_ss"],
                     "峰稳态比": rB,
                     "失活tau_ms": resB["inactivation_tau_ms"],
                     "守恒误差": resB["mass_error"]},
        "I_t_抽样": {"t_ms": np.linspace(0, args.t_end_ms, 200).tolist(),
                     "I_线性": np.interp(np.linspace(0, args.t_end_ms, 200),
                                         resL["t_ms"], resL["I"]).tolist(),
                     "I_分支": np.interp(np.linspace(0, args.t_end_ms, 200),
                                         resB["t_ms"], resB["I"]).tolist()},
        "选择性转变": {"t_ms": [1, 50, 200, 500, 1000, 2000],
                       "O2_占比": [float(O2[int(np.argmin(np.abs(sol.t - tq)))]
                                        / max(O1[int(np.argmin(np.abs(sol.t - tq)))]
                                              + O2[int(np.argmin(np.abs(sol.t - tq)))],
                                              1e-15))
                                   for tq in (1, 50, 200, 500, 1000, 2000)]},
    }
    p = RES / "q3_门控.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
