#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W39 · Q6（最终）：半主动最优控制的干净对比。

与前一版的区别
--------------
前一版 `q6_final.py` 得出"最优常数阻尼 = 8c₀、相对被动 −66.4%"，
与频域扫描（最优 0.62c₀、−5.5%）**直接矛盾**。单独复核后确认：
时域与频域**吻合到 3.4% 以内**、最优都是 0.62c₀ —— 即**前一版脚本有 bug**。

本版**每个策略都用同一个、已交叉验证过的仿真核心**（与频域自检通过），
不重复实现，避免再次出现"两套代码给出两个答案"。

仿真核心
--------
状态 `x = [z_s−z_u, z_u−z_r, ż_s, ż_u, ż_r, z_r]`，输入 `w = z̈_r`。
给定阻尼 `c` 做**精确离散化** `Ad=exp(A·dt)`（前向欧拉在阻尼调大时发散，已踩坑）。
控制力一律**直接施加**（经 `Bud`），不做"除以 Δż 反推阻尼"的双层转换
（该转换有符号/尺度陷阱，实测导致裁剪最优比被动差 85%）。

半主动约束的实现
----------------
理想力 `u*` 投影到当前可达耗散力集合：

    Δż > 0 :  u = clip(u*, 0,        c_max·Δż)
    Δż < 0 :  u = clip(u*, c_max·Δż, 0)
    Δż ≈ 0 :  u = 0

`c_max·Δż` 即半主动在当前相对速度下能提供的最大耗散力 ——
这正是无源性约束 `F·Δż ≥ 0` 的直接体现。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.linalg import solve_continuous_are
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from model import (default_params, generate_road_accel, metrics_freq,  # noqa: E402
                   natural_freqs, rms, state_space)
from q5_skyhook import _expm_step  # noqa: E402

RESULTS = ROOT / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
V = 60 / 3.6
DT = 1e-3


# ------------------------------------------------------------------ 仿真核心
def run(p, t, w, c_damp: float, force_fn=None) -> np.ndarray:
    r"""统一仿真：固定阻尼 `c_damp` + 可选附加控制力 `force_fn(x, vrel) -> u`。

    `force_fn` 返回的半主动力必须自行满足无源性（见模块 docstring）。
    """
    Ad, Bd, Bud, C = _expm_step(p, c_damp, DT)
    n = len(t)
    x = np.zeros(6)
    y = np.zeros((n, 3))
    for k in range(n):
        y[k] = C @ x
        u = 0.0
        if force_fn is not None:
            u = force_fn(x, float(x[2] - x[3]))
        x = (Ad @ x + Bd * float(w[k]) + Bud * u).reshape(-1)
    return y


def make_semiactive_force(p, u_star_fn):
    """构造半主动力投影器（无源性约束）。"""
    cmax = p["c_max"]
    def f(x, vrel):
        u_star = float(u_star_fn(x))
        if abs(vrel) < 1e-12:
            return 0.0
        if vrel > 0:
            return float(np.clip(u_star, 0.0, cmax * vrel))
        return float(np.clip(u_star, cmax * vrel, 0.0))
    return f


def make_skyhook_force(p, gain: float, umax: float | None = None):
    def u_star(x):
        u = -gain * float(x[2])
        return u if umax is None else float(np.clip(u, -umax, umax))
    return make_semiactive_force(p, u_star)


def make_lqr_force(p, K, semiactive: bool, umax: float | None = None):
    def u_star(x, vrel=None):
        u = float((-K @ x).reshape(-1)[0])
        return u if umax is None else float(np.clip(u, -umax, umax))
    if semiactive:
        # 半主动：投影到可达耗散力集合（只需 x）
        return make_semiactive_force(p, lambda x: u_star(x))
    # 全主动：无约束（仅力限），签名需与 run() 的 (x, vrel) 调用一致
    return u_star


def lqr_K(p, K4=None):
    A, B, Bu, C, D, Du = state_space(p, p["c0"])
    A4, Bu4 = A[:4, :4], Bu[:4, :]
    C1 = C[0:1, :4]
    Q = C1.T @ C1 * 1e4 + 1e-4 * np.eye(4)
    for rho in (1e-3, 1e-4, 1e-5, 1e-6):
        try:
            X = solve_continuous_are(A4, Bu4, Q, np.array([[rho]]))
            Kc = np.linalg.solve(np.array([[rho]]), Bu4.T @ X)
            if np.all(np.isfinite(Kc)) and np.max(np.abs(Kc)) < 1e9:
                K = np.zeros((1, 6))
                K[0, :4] = Kc[0]
                return K
        except Exception:
            continue
    return np.zeros((1, 6))


def mean_acc(fn, seeds, dur=12.0):
    return float(np.mean([rms(fn(s)[:, 0]) for s in seeds]))


# ------------------------------------------------------------------ 主流程
def main() -> int:
    p = default_params()
    fb, fw = natural_freqs(p)
    print(f"固有频率 车身 {fb:.2f} Hz / 车轮 {fw:.1f} Hz")
    print(f"可调阻尼 {p['c_min']:.0f}–{p['c_max']:.0f} N·s/m\n")

    # ---- 自检：固定阻尼时域 vs 频域 ----
    print("=== 自检：固定阻尼 时域 vs 频域 ===")
    for cm in (0.62, 1.0, 4.0):
        a = mean_acc(lambda s, cm=cm: run(
            p, *generate_road_accel("C", V, 15.0, DT, seed=1100 + s), cm * p["c0"]),
            range(4), 15.0)
        mf = metrics_freq(p, cm * p["c0"], "C", V)["acc"]
        ok = "✅" if abs(a - mf) / mf < 0.05 else "❌"
        print(f"  c={cm:>4.2f}c₀  时域 {a:.4f}  频域 {mf:.4f}  {ok}")
    print()

    # ---- 最优常数阻尼（时域扫，与频域对照）----
    grid = np.geomspace(p["c_min"], p["c_max"], 14)
    print("=== 最优常数阻尼扫描 ===")
    cand = []
    for c in grid:
        a = mean_acc(lambda s, c=c: run(
            p, *generate_road_accel("C", V, 10.0, DT, seed=1200 + s), c), range(4), 10.0)
        cand.append((float(c), a))
    c_opt, a_opt = min(cand, key=lambda t: t[1])
    for c, a in cand[::2]:
        print(f"  c={c/p['c0']:>5.2f}c₀  acc={a:.4f}")
    print(f"  → 最优 c = {c_opt/p['c0']:.2f}c₀，acc = {a_opt:.4f}"
          f"（频域对照 {metrics_freq(p, c_opt, 'C', V)['acc']:.4f}）\n")

    K = lqr_K(p)
    # 天棚增益调参
    def sky_obj(g):
        return mean_acc(lambda s: run(
            p, *generate_road_accel("C", V, 8.0, DT, seed=1300 + s),
            c_opt, force_fn=make_skyhook_force(p, g)), range(4), 8.0)
    g_grid = np.geomspace(100.0, 30000.0, 9)
    g_best = min(g_grid, key=sky_obj)
    r = minimize_scalar(sky_obj, bounds=(g_best * 0.3, g_best * 3.0),
                        method="bounded", options={"xatol": 50.0})
    g_best = float(r.x)
    print(f"=== 天棚最优增益 g = {g_best:.0f} N·s/m ({g_best/p['c0']:.2f}c₀) ===\n")

    # ---- 主对比 ----
    N, DUR = 10, 12.0
    seeds = list(range(1400, 1400 + N))
    print(f"=== 主对比（{N} 组实现 × {DUR:.0f}s，C 级 60km/h）===")
    specs = {
        "被动 c₀": lambda s: run(p, *generate_road_accel("C", V, DUR, DT, seed=s), p["c0"]),
        f"最优常数 {c_opt/p['c0']:.2f}c₀": lambda s: run(
            p, *generate_road_accel("C", V, DUR, DT, seed=s), c_opt),
        "天棚 skyhook（半主动）": lambda s: run(
            p, *generate_road_accel("C", V, DUR, DT, seed=s), c_opt,
            force_fn=make_skyhook_force(p, g_best)),
        "裁剪最优 clipped（半主动）": lambda s: run(
            p, *generate_road_accel("C", V, DUR, DT, seed=s), c_opt,
            force_fn=make_lqr_force(p, K, semiactive=True)),
        "全主动 LQR（力限3000N）": lambda s: run(
            p, *generate_road_accel("C", V, DUR, DT, seed=s), c_opt,
            force_fn=make_lqr_force(p, K * 50.0, semiactive=False, umax=3000.0)),
    }
    res = {nm: [fn(s) for s in seeds] for nm, fn in specs.items()}
    base = float(np.mean([rms(y[:, 0]) for y in res["被动 c₀"]]))
    print(f"  {'策略':<26}{'acc均值':>10}{'标准差':>9}{'相对被动':>10}"
          f"{'动挠度(mm)':>12}")
    table = {}
    for nm, ys in res.items():
        a = [rms(y[:, 0]) for y in ys]
        m, sd = float(np.mean(a)), float(np.std(a))
        tr = float(np.mean([rms(y[:, 1]) for y in ys])) * 1000
        table[nm] = {"acc": m, "std": sd, "gain_pct": (m - base) / base * 100,
                     "travel_mm": tr}
        print(f"  {nm:<26}{m:>10.4f}{sd:>9.4f}{(m-base)/base*100:>9.1f}%{tr:>12.2f}")

    out = {"table": table, "c_opt_over_c0": float(c_opt / p["c0"]),
           "skyhook_gain_over_c0": float(g_best / p["c0"]),
           "base_passive": base, "n_realizations": N, "duration_s": DUR}
    (RESULTS / "q6_optimal_semiactive.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== 结论 ===")
    sk = table["天棚 skyhook（半主动）"]["gain_pct"]
    cl = table["裁剪最优 clipped（半主动）"]["gain_pct"]
    ac = table["全主动 LQR（力限3000N）"]["gain_pct"]
    oc = table[f"最优常数 {c_opt/p['c0']:.2f}c₀"]["gain_pct"]
    print(f"  最优常数阻尼          {oc:+.1f}%")
    print(f"  天棚 skyhook（半主动） {sk:+.1f}%")
    print(f"  裁剪最优（半主动）     {cl:+.1f}%")
    print(f"  全主动 LQR            {ac:+.1f}%")
    print(f"\n  半主动最优相对被动：{min(sk, cl):+.1f}%")
    print(f"  半主动 → 全主动的差距：{abs(ac - min(sk, cl)):.0f} 个百分点")
    print(f"\n[结果] {RESULTS / 'q6_optimal_semiactive.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
