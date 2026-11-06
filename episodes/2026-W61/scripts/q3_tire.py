"""Q3：轮胎 —— 500 km/h 时胎面在承受什么。

四个量
------
1. 转速与胎面离心加速度      ω = v/r，a = v²/r
2. 带束层环向应力            σ = ρ·v²（薄环）
3. 胎面径向增长              Δr ≈ σ·r/E
4. 生热功率                  P = Crr·Fz·v

结论会指向一件事：**橡胶本身撑不住，必须靠纤维/钢丝带束层把离心力接走。**
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

EP = Path(__file__).resolve().parents[1]
RES = EP / "results"
FIGS = RES / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

R = 0.34                 # 滚动半径 m（③）
V = 500 / 3.6            # m/s
M = 1800.0
G = 9.81
DOWNFORCE = 6100.0       # N，来自 Q2
CRR = 0.010              # 高速滚动阻力系数（③，取值偏小，见限制）

MATERIALS = {
    "橡胶（无带束）": {"rho": 1100, "E": 10e6},
    "芳纶带束": {"rho": 1440, "E": 80e9},
    "钢丝带束": {"rho": 7800, "E": 200e9},
}


def main() -> int:
    omega = V / R
    rpm = omega * 60 / (2 * np.pi)
    a_cent = V ** 2 / R
    g_cent = a_cent / G

    out = {
        "radius_m": R, "speed_kmh": 500,
        "omega_rad_s": round(omega, 1), "rpm": round(rpm, 0),
        "centripetal_m_s2": round(a_cent, 0), "centripetal_g": round(g_cent, 0),
        "materials": {},
    }

    # 环向应力与径向增长
    for name, mat in MATERIALS.items():
        sigma = mat["rho"] * V ** 2          # Pa
        growth_mm = sigma * R / mat["E"] * 1000
        out["materials"][name] = {
            "hoop_stress_MPa": round(sigma / 1e6, 1),
            "radial_growth_mm": round(growth_mm, 2),
        }

    # 每只轮胎的载荷与生热
    static = M * G / 4
    extra = DOWNFORCE / 4
    fz = static + extra
    p_heat = CRR * fz * V
    out["load"] = {
        "static_N": round(static, 0), "with_downforce_N": round(fz, 0),
        "heat_per_tire_kW": round(p_heat / 1e3, 1),
        "heat_total_kW": round(4 * p_heat / 1e3, 1),
    }

    # 速度对增长的放大（σ ∝ v²）
    curve = []
    for v_kmh in (200, 300, 400, 450, 500, 520):
        v = v_kmh / 3.6
        sigma = MATERIALS["钢丝带束"]["rho"] * v ** 2
        curve.append({"v_kmh": v_kmh,
                      "g": round(v ** 2 / R / G, 0),
                      "growth_mm_belt": round(sigma * R / MATERIALS["钢丝带束"]["E"] * 1000, 2),
                      "rubber_growth_mm": round(sigma * R / MATERIALS["橡胶（无带束）"]["E"] * 1000, 0)})
    out["speed_curve"] = curve

    (RES / "q3_tire.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                      encoding="utf-8")

    print(f"[转速] {omega:.0f} rad/s = {rpm:.0f} rpm")
    print(f"[离心] 胎面 {a_cent:,.0f} m/s² = {g_cent:,.0f} g")
    print("\n[材料对比] 环向应力 / 径向增长")
    for k, v in out["materials"].items():
        print(f"   {k:12s} σ={v['hoop_stress_MPa']:7.1f} MPa，Δr={v['radial_growth_mm']:8.2f} mm")
    print(f"\n[载荷] 静载 {static:.0f} N → 加下压力 {fz:.0f} N")
    print(f"[生热] 每只 {p_heat/1e3:.1f} kW，四只合计 {4*p_heat/1e3:.1f} kW")
    print("\n[随速度]")
    for c in curve:
        print(f"   {c['v_kmh']:3d} km/h: {c['g']:5.0f} g，钢丝带束增长 {c['growth_mm_belt']:5.2f} mm，"
              f"纯橡胶 {c['rubber_growth_mm']:6.0f} mm（远超半径 ⇒ 失效）")

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

    # (a) 离心加速度 vs 速度
    v = np.linspace(100, 550, 200)
    ax[0].plot(v, (v / 3.6) ** 2 / R / G, color="#e8604a", lw=2.4)
    ax[0].axvline(500, color="#8a9bb0", ls="--", lw=1.2)
    ax[0].set_xlabel("车速（km/h）")
    ax[0].set_ylabel("胎面离心加速度（g）")
    ax[0].set_title("胎面在 500 km/h 承受约 5 800 g", fontsize=12)
    ax[0].grid(alpha=0.25)

    # (b) 径向增长
    for name, mat, col in (("纯橡胶", MATERIALS["橡胶（无带束）"], "#deac5c"),
                           ("钢丝带束", MATERIALS["钢丝带束"], "#569cd6")):
        sig = mat["rho"] * (v / 3.6) ** 2
        ax[1].plot(v, sig * R / mat["E"] * 1000, color=col, lw=2.4, label=name)
    ax[1].set_yscale("log")
    ax[1].set_ylim(1e-2, 60)
    ax[1].axvline(500, color="#8a9bb0", ls="--", lw=1.2)
    ax[1].axhline(2.0, color="#7fb069", ls=":", lw=1.4, label="可接受增长 2 mm")
    ax[1].set_xlabel("车速（km/h）")
    ax[1].set_ylabel("径向增长（mm，对数）")
    ax[1].set_title("没有带束层，橡胶会被离心力甩散", fontsize=12)
    ax[1].annotate("纯橡胶远超半径\n（模型已失效）", xy=(430, 30), fontsize=9, color="#c0392b")
    ax[1].legend(frameon=False, fontsize=9)
    ax[1].grid(alpha=0.25, which="both")

    # (c) 生热
    fz_static = M * G / 4
    vv = np.linspace(100, 550, 200)
    heat = CRR * (fz_static + DOWNFORCE / 4) * (vv / 3.6) / 1e3
    ax[2].plot(vv, heat, color="#7fb069", lw=2.4)
    ax[2].axvline(500, color="#8a9bb0", ls="--", lw=1.2)
    ax[2].set_xlabel("车速（km/h）")
    ax[2].set_ylabel("单胎生热（kW）")
    ax[2].set_title("500 km/h 时每只轮胎 9 kW 的摩擦热", fontsize=12)
    ax[2].grid(alpha=0.25)

    fig.tight_layout()
    fig.savefig(FIGS / "q3_tire.png")
    print(f"[图] {FIGS / 'q3_tire.png'}")


if __name__ == "__main__":
    raise SystemExit(main())
