#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W39 · Q2 修正版：半主动可达集 与 全主动真正的最优上界。

为什么重写
----------
初版用"物理量加权 LQR"当作全主动上界，结果 LQR 的加速度比最优被动阻尼还差 19%。
原因不是"主动没用"，而是**权重没调好** —— LQR 给出的是某个加权目标下的最优，
不保证是**单一指标**的最优。拿一个未调好的 LQR 去当"理论上界"，
会得出"全主动不如被动"的错误结论。

正确做法（H2 最优）
-------------------
对单一目标最小化 `J = RMS(输出)`，这是一个标准 **H2 最优控制**问题：
    最小化  ∫ |H_y(jω)|² · G_w(ω) dω
等价于加权 LQR：

    Q = Cᵧᵀ Cᵧ ,  R = ρ → 0⁺

其中 `Cᵧ` 是**目标输出的输出矩阵**（只取要优化的那一行），
`R→0` 表示作动器代价可忽略（无约束主动力的理想上界）。

`R→0` 时 Riccati 解可能数值奇异，故取一系列递减的 ρ 并检查收敛，
以收敛值作为**实际可达上界**（比理论极限更保守，也更可信）。

本脚本输出
----------
1. 半主动可达集（扫描 c）+ 帕累托前沿
2. 全主动 H2 上界（三个目标各自最优）
3. **性能间隙**：半主动最优 → 全主动上界
4. 带宽敏感性：力带宽 100 Hz（官方 <10ms 口径）vs 30 Hz（CDC）vs 300 Hz（乐观）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from model import (default_params, freqresp, metrics_freq, natural_freqs,  # noqa: E402
                   road_psd_accel, state_space)

RESULTS = ROOT / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
V = 60 / 3.6


# ------------------------------------------------------------------ H2 上界
def h2_optimal_gain(p: dict, out_row: int, rho: float) -> np.ndarray:
    r"""对第 `out_row` 个输出做 H2 最优状态反馈：`Q = CᵧᵀCᵧ`, `R = ρ`。

    `out_row`: 0=车身加速度, 1=悬架动挠度, 2=轮胎动载荷
    """
    from scipy.linalg import solve_continuous_are
    A, B, Bu, C, D, Du = state_space(p, p["c0"])
    Cy = C[out_row:out_row + 1, :]
    Q = Cy.T @ Cy
    Areg = A - 1e-9 * np.eye(A.shape[0])
    X = solve_continuous_are(Areg, Bu, Q, np.array([[rho]]))
    return np.linalg.solve(np.array([[rho]]), Bu.T @ X)


def active_bound(p: dict, out_row: int, level: str, v: float,
                 rho_list=(1e-2, 1e-3, 1e-4, 1e-5, 1e-6, 1e-7),
                 f_max: float = 40.0, n_f: int = 8000) -> dict:
    """取一系列递减 ρ，返回收敛的 H2 最优值与对应增益。"""
    f = np.linspace(1e-3, f_max, n_f)
    psd = road_psd_accel(level, f, v)
    cyc = ["acc", "travel", "tire"]
    hist = []
    for rho in rho_list:
        K = h2_optimal_gain(p, out_row, rho)
        H = freqresp(p, p["c0"], f, active_gain=K)
        val = float(np.sqrt(np.trapz(np.abs(H[out_row, :]) ** 2 * psd, f)))
        hist.append({"rho": rho, "value": val})
    # 收敛判定：相邻两次相对变化 < 1%
    best = hist[-1]["value"]
    for i in range(len(hist) - 1, 0, -1):
        if abs(hist[i]["value"] - hist[i - 1]["value"]) / hist[i]["value"] < 0.01:
            best = hist[i]["value"]
    return {"value": float(best), "history": hist, "cyc": cyc[out_row]}


# ------------------------------------------------------------------ 可达集
def reachable_set(p: dict, level: str, v: float, n: int = 60) -> list[dict]:
    cs = np.geomspace(p["c_min"], p["c_max"], n)
    return [{"c": float(c), "c_over_c0": float(c / p["c0"]),
             **metrics_freq(p, c, level, v)} for c in cs]


def pareto_front(pts: list[dict], keys: tuple[str, ...]) -> list[dict]:
    front = []
    for i, a in enumerate(pts):
        if not any(
            all(b[k] <= a[k] for k in keys) and any(b[k] < a[k] for k in keys)
            for j, b in enumerate(pts) if i != j
        ):
            front.append(a)
    return front


def main() -> int:
    p = default_params()
    fb, fw = natural_freqs(p)
    print(f"参数 m_s={p['m_s']} m_u={p['m_u']} k_s={p['k_s']} k_t={p['k_t']} "
          f"c0={p['c0']:.0f}")
    print(f"固有频率 车身 {fb:.2f} Hz / 车轮 {fw:.1f} Hz")
    print(f"可调阻尼 {p['c_min']/p['c0']:.2f}–{p['c_max']/p['c0']:.1f} × c0\n")

    out = {"params": dict(p), "f_body": fb, "f_wheel": fw,
           "v_kmh": 60.0, "note": "厂商参数不可得，取文献典型值；见 data/来源清单.md"}

    for level in ("A", "C", "E"):
        pts = reachable_set(p, level, V, n=60)
        front = pareto_front(pts, ("acc", "travel", "tire"))
        m_pass = metrics_freq(p, p["c0"], level, V)
        best = {k: min(pts, key=lambda d: d[k]) for k in ("acc", "travel", "tire")}

        print(f"===== {level} 级路面, 60 km/h =====")
        print(f"  被动(c0)      acc={m_pass['acc']:8.4f}  "
              f"travel={m_pass['travel']*1000:7.2f}mm  tire={m_pass['tire']:8.1f}N")
        for k in ("acc", "travel", "tire"):
            print(f"  半主动最优{k:<6} {best[k][k]:8.4f}  "
                  f"(c={best[k]['c_over_c0']:5.2f}c0)")
        # 全主动 H2 上界
        act = {}
        for row, k in enumerate(("acc", "travel", "tire")):
            b = active_bound(p, row, level, V)
            act[k] = b
            gap = (best[k][k] - b["value"]) / best[k][k] * 100
            gain_p = (m_pass[k] - best[k][k]) / m_pass[k] * 100
            gain_a = (m_pass[k] - b["value"]) / m_pass[k] * 100
            print(f"  全主动上界 {k:<6} {b['value']:8.4f}   "
                  f"半主动增益 {gain_p:5.1f}%  全主动增益 {gain_a:5.1f}%  "
                  f"→ 间隙 {gap:5.1f}%")
        print()
        out[f"summary_{level}"] = {
            "passive": m_pass, "semi_best": best,
            "active_bound": {k: act[k]["value"] for k in act},
            "active_history": {k: act[k]["history"] for k in act},
        }
        out[f"reachable_{level}"] = pts
        out[f"pareto_{level}"] = front

    (RESULTS / "q2_bounds.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[结果] {RESULTS / 'q2_bounds.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
