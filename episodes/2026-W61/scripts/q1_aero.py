"""Q1：外形与功率预算 —— 520 km/h 需要多小的 CdA。

物理
----
    P = ½·ρ·CdA·v³ + m·g·f_r·v
极速时驱动力＝阻力，所以功率随速度**三次方**增长。

输出
----
    results/q1_aero.json
    figs/q1_aero.png
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

EP = Path(__file__).resolve().parents[1]
RES = EP / "results"
FIGS = RES / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

RHO_HOT = 1.15      # kg/m³，阿布扎比 40 ℃ 左右（③ 假设）
RHO_STD = 1.225     # 标准海平面
M = 1800.0          # kg（含车手）
G = 9.81
FR = 0.012          # 滚动阻力系数（③）

V_TARGET = 520 / 3.6      # m/s
V_RECORD = 503.17 / 3.6
P_BUDGET = 1000e3         # W


def drag_power(v: float, cda: float, rho: float = RHO_HOT) -> float:
    return 0.5 * rho * cda * v ** 3


def roll_power(v: float) -> float:
    return M * G * FR * v


def total_power(v: float, cda: float, rho: float = RHO_HOT) -> float:
    return drag_power(v, cda, rho) + roll_power(v)


def max_cda_for(power: float, v: float, rho: float = RHO_HOT) -> float:
    """给定功率与目标速度，允许的最大 CdA。"""
    return 2 * (power - roll_power(v)) / (rho * v ** 3)


def v_max(cda: float, power: float, rho: float = RHO_HOT) -> float:
    """给定功率与 CdA，解出的极速（m/s）。"""
    lo, hi = 10.0, 250.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if total_power(mid, cda, rho) < power:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def main() -> int:
    out = {"rho": RHO_HOT, "mass_kg": M, "fr": FR, "p_budget_kw": P_BUDGET / 1e3}

    # 1) 520 km/h 在 1000 kW 下允许的最大 CdA
    cda_allow = max_cda_for(P_BUDGET, V_TARGET)
    out["max_cda_for_520_at_1000kw"] = round(cda_allow, 3)

    # 2) 我们的设计：CdA 0.55
    cda = 0.55
    p520 = total_power(V_TARGET, cda)
    out["design"] = {"cda": cda,
                     "power_at_520_kw": round(p520 / 1e3, 1),
                     "vmax_at_1000kw_kmh": round(v_max(cda, P_BUDGET) * 3.6, 1)}

    # 3) 反推 U9X：503.17 km/h 需要的功率，随 CdA 变化
    implied = {}
    for c in (0.60, 0.70, 0.80, 0.90, 1.00):
        implied[f"{c:.2f}"] = round(total_power(V_RECORD, c) / 1e3, 0)
    out["u9x_implied_power_kw"] = implied
    out["u9x_peak_kw"] = 2220

    # 4) 边际成本：每 +1 km/h 需要多少 kW
    marginal = {}
    for v_kmh in (300, 400, 450, 500, 520):
        v = v_kmh / 3.6
        dpdv = 1.5 * RHO_HOT * cda * v ** 2      # W per (m/s)
        marginal[str(v_kmh)] = round(dpdv / 3.6 / 1000, 2)   # kW per km/h
    out["marginal_kw_per_kmh"] = marginal

    # 5) Cd 敏感性（A 固定 1.95 m²）
    area = 1.95
    sens = {}
    for cd in (0.20, 0.25, 0.30, 0.35, 0.40):
        c2 = cd * area
        sens[f"Cd={cd:.2f}"] = {
            "cda": round(c2, 3),
            "power_520_kw": round(total_power(V_TARGET, c2) / 1e3, 0),
            "vmax_1000kw_kmh": round(v_max(c2, P_BUDGET) * 3.6, 0),
        }
    out["cd_sensitivity"] = sens

    # 6) 空气密度（高温）影响
    out["rho_effect"] = {
        f"rho={r:.3f}": round(total_power(V_TARGET, cda, r) / 1e3, 0)
        for r in (1.10, 1.15, 1.225)
    }

    (RES / "q1_aero.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                      encoding="utf-8")

    print(f"[预算] 520 km/h 时：CdA = {cda:.2f} → {p520/1e3:.0f} kW"
          f"（其中滚动 {roll_power(V_TARGET)/1e3:.0f} kW）")
    print(f"[上限] 1000 kW 预算下，520 km/h 允许的最大 CdA = {cda_allow:.3f}")
    print(f"[反推] 若 U9X 的 CdA 是 0.8，503.17 km/h 只需 "
          f"{implied['0.80']:.0f} kW（峰值 2220 kW）")
    print("[边际] 每 +1 km/h 的功率代价：")
    for k, v in marginal.items():
        print(f"   {k} km/h → +{v} kW")
    print("[Cd 敏感性]")
    for k, v in sens.items():
        print(f"   {k}: CdA {v['cda']} → 520 需 {v['power_520_kw']} kW，"
              f"1000 kW 下极速 {v['vmax_1000kw_kmh']} km/h")
    print(f"[密度] {out['rho_effect']}")

    plot(out)
    return 0


def plot(out: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import rcParams
    rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(1, 3, figsize=(15.6, 4.4), dpi=150)

    # (a) 功率-速度（多条 CdA）
    v = np.linspace(200, 560, 200) / 3.6
    for c, col in ((0.35, "#7fb069"), (0.55, "#569cd6"), (0.80, "#deac5c"), (1.10, "#e8604a")):
        ax[0].plot(v * 3.6, total_power(v, c) / 1e3, color=col, lw=2.2, label=f"CdA={c}")
    ax[0].axhline(1000, color="#333", ls="--", lw=1.2, label="功率预算 1 000 kW")
    ax[0].axvline(520, color="#8a9bb0", ls=":", lw=1.2)
    ax[0].set_xlabel("车速（km/h）")
    ax[0].set_ylabel("所需功率（kW）")
    ax[0].set_title("阻力功率随速度三次方增长", fontsize=12)
    ax[0].legend(frameon=False, fontsize=8)
    ax[0].grid(alpha=0.25)
    ax[0].set_ylim(0, 2600)

    # (b) 边际成本
    vv = np.linspace(250, 540, 150)
    ax[1].plot(vv, 1.5 * RHO_HOT * 0.55 * (vv / 3.6) ** 2 / 3.6 / 1000, color="#e8604a", lw=2.4)
    ax[1].set_xlabel("车速（km/h）")
    ax[1].set_ylabel("每 +1 km/h 需要的功率（kW）")
    ax[1].set_title("越往后越贵：CdA=0.55 下的边际功率", fontsize=12)
    ax[1].grid(alpha=0.25)
    for x in (500, 520):
        y = 1.5 * RHO_HOT * 0.55 * (x / 3.6) ** 2 / 3.6 / 1000
        ax[1].plot([x], [y], "o", color="#333")
        ax[1].annotate(f"{x}: {y:.1f} kW", (x, y), textcoords="offset points",
                       xytext=(-70, 10), fontsize=9)

    # (c) Cd → 极速
    cds = np.linspace(0.18, 0.45, 100)
    ax[2].plot(cds, [v_max(cd * 1.95, 1000e3) * 3.6 for cd in cds], color="#569cd6", lw=2.4)
    ax[2].axhline(520, color="#e8604a", ls="--", lw=1.2, label="目标 520 km/h")
    ax[2].axvline(0.28, color="#7fb069", ls=":", lw=1.4, label="本文设计 Cd=0.28")
    ax[2].set_xlabel("风阻系数 Cd（迎风面积 1.95 m²）")
    ax[2].set_ylabel("1 000 kW 下的极速（km/h）")
    ax[2].set_title("Cd 每降 0.05，极速涨多少", fontsize=12)
    ax[2].grid(alpha=0.25)
    ax[2].legend(frameon=False, fontsize=9)

    fig.tight_layout()
    fig.savefig(FIGS / "q1_aero.png")
    print(f"[图] {FIGS / 'q1_aero.png'}")


if __name__ == "__main__":
    raise SystemExit(main())
