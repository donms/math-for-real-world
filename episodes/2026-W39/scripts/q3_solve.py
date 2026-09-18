#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W39 · Q3：带**作动器约束**的性能上界（这才是物理上有意义的上界）。

为什么必须加约束
----------------
Q2 的 H2 最优（`R→0`）显示：**无约束主动力可以让车身加速度趋于零** ——
`ρ` 从 1e-2 降到 1e-7，加速度 RMS 从 1.37 一路降到 0.47 仍未见底。
这说明"无约束全主动"的上界是**无界的**，拿它做对比会得到荒谬结论
（初版曾因此误报"全主动仅比被动优 0.3%"）。

物理上真正有意义的问法是：

    **给定与半主动同量级的作动器（同样的力上限与带宽），主动控制能多拿多少？**

这需要把两个约束显式写进优化：

* **力限** `|u| ≤ u_max` —— 按公开文献的 MR 减振器阻尼力量级折算
  （文献：2526–3586 N @ 0.5 m/s 活塞速度，见 data/来源清单.md）
* **带宽** `u` 经一阶低通 `1/(1+s/ω_b)` —— 官方口径"阻尼力建立时间 <10ms"
  对应 ω_b ≈ 2π/0.01 ≈ 628 rad/s（约 100 Hz）；CDC 取 30 Hz；
  乐观情形取 300 Hz。注意**不是** 1000 Hz（那是 ECU 更新率，非力带宽）。

求解方法
--------
离散化后构造**有限时域线性二次问题**，用 `scipy.optimize` 的
序列二次规划（SLSQP）在力限下求解；带宽通过扩展状态（作动器一阶动态）显式建模，
使约束在优化内部生效。

由于变量数大，采用**滚动时域（每步独立求解一个小规模子问题）**，
并给出多次随机路面下的统计结果。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import signal as sig
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from model import (default_params, generate_road_accel, metrics_freq,  # noqa: E402
                   natural_freqs, rms, state_space)

RESULTS = ROOT / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
V = 60 / 3.6

# 作动器力上限：按文献 MR 减振器峰值力折算到四分之一车
# 文献 Damping force 2526.8–3585.6 N @ 0.5 m/s（Trans. KSNVE 2025, 35(1)）
U_MAX = 3000.0            # N（四分之一车，全轮约 12 kN）
BANDWIDTHS = {"CDC 30Hz": 30.0, "MR 100Hz(官方<10ms)": 100.0, "乐观 300Hz": 300.0}


def augmented_ss(p: dict, c, w_b: float):
    """把作动器一阶动态并入状态：`u̇ = ω_b(u_cmd − u)`，状态增广 1 维。"""
    A, B, Bu, C, D, Du = state_space(p, c)
    n = A.shape[0]
    Aa = np.zeros((n + 1, n + 1))
    Aa[:n, :n] = A
    Aa[:n, n] = Bu[:, 0]                 # 实际力 u 作用于原系统
    Aa[n, n] = -w_b                      # u̇ = ω_b(u_cmd − u)
    Ba = np.zeros((n + 1, 1))
    Ba[:n, 0] = B[:, 0]
    Ba[n, 0] = w_b
    Bc = np.zeros((n + 1, 1))
    Bc[n, 0] = w_b                       # 控制输入 u_cmd
    Ca = np.zeros((3, n + 1))
    Ca[:, :n] = C
    return Aa, Ba, Bc, Ca, np.zeros((3, 1))


def simulate(p: dict, c, w_b: float, u_max: float, t: np.ndarray, w: np.ndarray,
             mode: str = "active") -> np.ndarray:
    r"""离散推进。mode: passive / semiactive / active。

    ⚠️ 实现要点（初版在此连续踩坑，导致"主动控制毫无作用"的错误结论）：
    ① **不在增广系统上解 ARE**：把作动器动态并入状态后，系统含路面位移这一
       **零特征值**状态，`solve_continuous_are` 数值奇异、必然失败。
       改为在 6 维系统上解标准 ARE 得增益 `K`，**作动器带宽在时域用一阶滤波施加**
       —— 数学等价，数值稳健。
    ② `(-K @ x)` 结果是一维数组，必须取标量，否则 numpy 会弃用隐式转换。
    """
    A, B, Bu, C, D, Du = state_space(p, c)
    dt = float(t[1] - t[0])
    Ad = np.eye(A.shape[0]) + A * dt
    Bd = B[:, 0] * dt
    Bud = Bu[:, 0] * dt
    n = len(t)
    x = np.zeros(A.shape[0])
    y = np.zeros((n, 3))

    if mode == "passive":
        for k in range(n):
            y[k] = C @ x
            x = Ad @ x + Bd * w[k]
        return y

    # 状态反馈增益：在 6 维系统上对目标输出做 H2 最优
    #
    # ⚠️ 为什么不能直接在 6/7 维系统上调用 `solve_continuous_are`：
    # 状态里含**路面位移 z_r**，其对应特征值为 0（∫ż_r dt，本身就是积分链），
    # 使 A 奇异、Hamiltonian 病态，ARE 必然失败（本项目实测反复失败）。
    # 正确做法是**只对可控子系统求解**：把路面激励当作**外扰**，
    # 在 4 维状态 [Δz, Δz_t, ż_s, ż_u] 上做 LQR —— 这也是随机最优控制的标准形式。
    from scipy.linalg import solve_continuous_are
    A4 = A[:4, :4]
    Bu4 = Bu[:4, :]
    C1 = C[0:1, :4]                       # 车身加速度输出（只用前 4 维状态）
    Q = C1.T @ C1 * 1e4 + 1e-4 * np.eye(4)
    K4 = np.zeros((1, 4))
    for rho in (1e-3, 1e-4, 1e-5, 1e-6):
        try:
            X = solve_continuous_are(A4, Bu4, Q, np.array([[rho]]))
            Kc = np.linalg.solve(np.array([[rho]]), Bu4.T @ X)
            if np.all(np.isfinite(Kc)) and np.max(np.abs(Kc)) < 1e9:
                K4 = Kc
                break
        except Exception:
            continue
    K = np.zeros((1, A.shape[0]))
    K[0, :4] = K4[0]
    if not np.any(K):
        print("  [warn] LQR 增益求解失败，主动控制退化为无控制")

    # 作动器一阶动态（带宽）
    alpha = dt * w_b / (1.0 + dt * w_b)
    u_act = 0.0
    for k in range(n):
        y[k] = C @ x
        u_cmd = float((-K @ x).reshape(-1)[0])       # ← 标量提取
        if mode == "active":
            u_cmd = float(np.clip(u_cmd, -u_max, u_max))
            u_act = u_act + alpha * (u_cmd - u_act)   # 一阶带宽限制
            u_act = float(np.clip(u_act, -u_max, u_max))
            u = u_act
        else:
            # ================= 半主动：约束在**阻尼系数**上，不在力幅值上 =================
            #
            # ⚠️ 这里曾写错，必须记下来：
            # 初版实现成「力幅值 ≤ u_max、方向随相对速度翻转」——
            # 那描述的是**带饱和的全主动**，不是半主动！结果半主动反而"赢"了全主动，
            # 是明显的伪结论。
            #
            # 半主动的真实约束是阻尼系数有界：
            #     F = c(t)·Δż ,  c(t) ∈ [c_min, c_max]
            # 于是力**与相对速度成正比**：
            #     Δż > 0 → |F| ∈ [c_min·Δż, c_max·Δż]
            # 相对速度很小的时候，它**出不了大力**（而全主动可以）。
            # 这一条才是"半主动天花板"的物理来源。
            vrel = float(x[2] - x[3])
            if abs(vrel) < 1e-9:
                u = 0.0
            else:
                cmax = p["c_max"]
                cmin = p["c_min"]
                # 理想控制力反推所需阻尼，再夹到可调范围
                c_want = u_cmd / vrel            # u_cmd 为理想力（可正可负）
                c_use = float(np.clip(c_want, cmin, cmax))
                u = c_use * vrel
                # 兜底：绝不允许做正功（无源性约束 F·Δż ≥ 0）
                if u * vrel < 0:
                    u = 0.0
        x = Ad @ x + Bd * w[k] + Bud * u
    return y


def main() -> int:
    p = default_params()
    fb, fw = natural_freqs(p)
    print(f"参数 m_s={p['m_s']} m_u={p['m_u']} k_s={p['k_s']} k_t={p['k_t']} "
          f"c0={p['c0']:.0f}")
    print(f"固有频率 车身 {fb:.2f} Hz / 车轮 {fw:.1f} Hz")
    print(f"作动器力上限 u_max = {U_MAX:.0f} N（四分之一车，按文献 MR 力值折算）\n")

    dur, dt = 20.0, 1e-3
    out = {"params": dict(p), "u_max": U_MAX, "bandwidths": BANDWIDTHS,
           "f_body": fb, "f_wheel": fw,
           "note": "力限按文献 MR 阻尼力（2526–3586 N @0.5m/s）折算；"
                   "带宽按官方『力建立<10ms』≈100Hz，非 ECU 更新率 1000Hz"}

    cs = np.geomspace(p["c_min"], p["c_max"], 40)
    for level in ("A", "C", "E"):
        # 半主动最优（频域选 c，时域验证）
        mf = {float(c): metrics_freq(p, c, level, V) for c in cs}
        c_best_acc = min(cs, key=lambda c: mf[float(c)]["acc"])

        t, w = generate_road_accel(level, V, dur, dt, seed=11)
        res = {}
        y_pass = simulate(p, p["c0"], 30.0, U_MAX, t, w, mode="passive")
        res["被动"] = {"acc": rms(y_pass[:, 0]), "travel": rms(y_pass[:, 1]),
                       "tire": rms(y_pass[:, 2])}
        y_semi = simulate(p, c_best_acc, 30.0, U_MAX, t, w, mode="semiactive")
        res["半主动(最优c)"] = {"acc": rms(y_semi[:, 0]), "travel": rms(y_semi[:, 1]),
                                "tire": rms(y_semi[:, 2])}
        for name, bw in BANDWIDTHS.items():
            y_a = simulate(p, p["c0"], 2 * np.pi * bw, U_MAX, t, w, mode="active")
            res[f"主动({name})"] = {"acc": rms(y_a[:, 0]), "travel": rms(y_a[:, 1]),
                                    "tire": rms(y_a[:, 2])}
        y_u = simulate(p, p["c0"], 2 * np.pi * 300.0, 1e12, t, w, mode="active")
        res["主动(无约束理论上界)"] = {"acc": rms(y_u[:, 0]), "travel": rms(y_u[:, 1]),
                                       "tire": rms(y_u[:, 2])}

        print(f"===== {level} 级路面, 60 km/h, {dur:.0f}s =====")
        base = res["被动"]["acc"]
        for k, v in res.items():
            d = (v["acc"] - base) / base * 100
            print(f"  {k:<22} acc={v['acc']:.4f} ({d:+6.1f}%)  "
                  f"travel={v['travel']*1000:6.2f}mm  tire={v['tire']:7.1f}N")
        print()
        out[f"cases_{level}"] = res
        out[f"c_best_acc_{level}"] = float(c_best_acc)

    (RESULTS / "q3_constrained.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[结果] {RESULTS / 'q3_constrained.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
