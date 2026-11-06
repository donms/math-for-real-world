"""Q6：质量预算 —— 1 800 kg 是乐观还是保守，减重的代价是什么。

用户质疑：比实车轻 26%，代价是多少？能不能实现？
本问回答三件事：
  1. 一份逐部件的质量预算（自下而上）
  2. 电池的能力边界（能量、C 率）
  3. 减重的真实代价：稳定性裕度、轮胎载荷、气动敏感性
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

EP = Path(__file__).resolve().parents[1]
RES = EP / "results"
FIGS = RES / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

RHO, G = 1.15, 9.81
CDA, CLA, P = 0.521, 0.55, 1000e3
MU, CRR = 1.0, 0.010
DT = 0.002


def accel(v: float, m: float) -> float:
    fz = m * G + 0.5 * RHO * CLA * v ** 2
    f_drive = min(P / max(v, 1.0), MU * fz) if v > 1.0 else MU * fz
    f_drag = 0.5 * RHO * CDA * v ** 2
    return (f_drive - f_drag - CRR * m * G) / m


def run(m: float) -> dict:
    v = s = t = 0.0
    energy = 0.0          # 驱动能量 J
    heat = 0.0            # 阻力耗散 J
    t500 = s500 = None
    while t < 80:
        a = accel(v, m)
        fz = m * G + 0.5 * RHO * CLA * v ** 2
        f_drive = min(P / max(v, 1.0), MU * fz) if v > 1.0 else MU * fz
        if t500 is None:
            energy += f_drive * v * DT
            heat += (0.5 * RHO * CDA * v ** 2) * v * DT
        if t500 is None and v * 3.6 >= 500:
            t500, s500 = t, s
        if abs(a) < 1e-4 and t > 5:
            break
        v += a * DT
        s += v * DT
        t += DT
    return {"t500": t500, "s500": s500, "energy_kWh": energy / 3.6e6,
            "heat_kWh": heat / 3.6e6, "vmax": v * 3.6}


def main() -> int:
    base = run(1800.0)

    # ---------- 1) 自下而上的质量预算
    budget = {
        "碳纤维单体壳 + 车身": 210,
        "四个电机（250 kW/个）": 160,
        "逆变器与高压线束": 60,
        "电池包（含壳体、BMS、冷却）": 330,
        "悬挂、转向、制动": 140,
        "轮辋与轮胎（4 套）": 88,
        "热管理（电池/电机/轮胎风冷）": 55,
        "气动套件（尾翼、扩散器、底板）": 45,
        "座椅、安全带、灭火、数据采集": 40,
        "车手": 80,
    }
    total = sum(budget.values())

    # ---------- 2) 电池能力
    # 一次记录跑需要的驱动能量；按 80% 放电深度与 30% 余量取容量
    e_run = base["energy_kWh"]
    # ★ 一次跑只用几 kWh，但要输出 1000 kW，容量必须按 C 率定
    c_max = 30.0                     # 30C 赛道级电芯（②实车同类）
    e_power = (P / 1e3) / c_max      # 为满足功率所需的最小容量
    e_need = max(e_run * 1.3 / 0.8, e_power)
    c_rate = (P / 1e3) / e_need
    c_rate_energy_only = (P / 1e3) / max(e_run * 1.3 / 0.8, 1e-6)
    pack_mass = budget["电池包（含壳体、BMS、冷却）"]
    cell_wh_kg = (e_need * 1000) / (pack_mass * 0.72)   # 壳体等占 28%

    # ---------- 3) 减重的代价
    def downforce_ratio(m):
        return (0.5 * RHO * CLA * (500 / 3.6) ** 2) / (m * G)

    def gust_lateral(m):
        # 横风 5 m/s 造成的等效侧向加速度（用侧向力系数 0.3 粗估）
        return 0.5 * RHO * 0.3 * 2.0 * (500 / 3.6) ** 2 / (m * G)

    out = {
        "mass_budget_kg": budget,
        "mass_total_kg": total,
        "design_mass_kg": 1800,
        "margin_kg": 1800 - total,
        "energy_run_kWh": round(e_run, 2),
        "energy_need_kWh": round(e_need, 2),
        "c_rate": round(c_rate, 1),
        "c_rate_if_sized_by_energy": round(c_rate_energy_only, 1),
        "capacity_for_power_kWh": round(e_power, 1),
        "cell_specific_energy_Wh_kg": round(cell_wh_kg, 0),
        "downforce_ratio": {str(m): round(downforce_ratio(m), 3)
                            for m in (1500, 1800, 2100, 2470)},
        "gust_lateral_g": {str(m): round(gust_lateral(m), 4)
                           for m in (1500, 1800, 2100, 2470)},
        "sens_mass": {},
    }
    for dm in (-10, 0, 10, 20):
        m = 1800 * (1 + dm / 100)
        r = run(m)
        out["sens_mass"][f"{dm:+d}%"] = {
            "mass_kg": round(m), "t500": round(r["t500"], 1) if r["t500"] else None,
            "s500_m": round(r["s500"], 0) if r["s500"] else None,
            "energy_kWh": round(r["energy_kWh"], 2)}

    (RES / "q6_mass.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                      encoding="utf-8")

    print("[质量预算] 自下而上")
    for k, v in budget.items():
        print(f"   {k:28s} {v:5.0f} kg")
    print(f"   {'合计':28s} {total:5.0f} kg（设计值 1800，余量 {1800-total:+.0f}）")
    print(f"\n[能量] 一次 0→500 驱动能 {e_run:.2f} kWh")
    print(f"[关键] 若只按能量配电池（{e_run*1.3/0.8:.1f} kWh），需要 {c_rate_energy_only:.0f}C —— 不可行")
    print(f"[定容] 按 30C 反推：容量至少 {e_power:.1f} kWh（1000 kW ÷ 30C）")
    print(f"       实际取 {e_need:.1f} kWh，工作点 {c_rate:.1f}C")
    print(f"[电芯] 需要的比能量约 {cell_wh_kg:.0f} Wh/kg（成组 72% 效率）")
    print(f"\n[减重代价] 下压力/重量比：", out["downforce_ratio"])
    print(f"[横风敏感性] 等效侧向加速度：", out["gust_lateral_g"])
    print("\n[质量敏感性]")
    for k, v in out["sens_mass"].items():
        print(f"   {k}: {v['mass_kg']} kg → 0-500 用 {v['t500']} s，{v['s500_m']:.0f} m，"
              f"能耗 {v['energy_kWh']} kWh")

    plot(out, base)
    return 0


def plot(out: dict, base: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import rcParams
    rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(1, 2, figsize=(13.0, 4.4), dpi=150)

    # (a) 质量预算饼图
    labels = list(out["mass_budget_kg"])
    vals = [out["mass_budget_kg"][k] for k in labels]
    ax[0].pie(vals, labels=[f"{l}\n{v} kg" for l, v in zip(labels, vals)],
              autopct="", startangle=90, textprops={"fontsize": 7})
    ax[0].set_title(f"质量预算合计 {out['mass_total_kg']} kg（设计 1 800）", fontsize=12)

    # (b) 质量 vs 0-500 时间
    ms = np.linspace(1400, 2600, 13)
    ts = []
    for m in ms:
        r = run(m)
        ts.append(r["t500"] if r["t500"] else np.nan)
    ax[1].plot(ms, ts, "-o", ms=3, color="#569cd6", lw=2.2)
    ax[1].axvline(1800, color="#7fb069", ls=":", lw=1.6, label="本文设计 1 800 kg")
    ax[1].axvline(2470, color="#e8604a", ls="--", lw=1.4, label="实车约 2 470 kg")
    ax[1].set_xlabel("整备质量（kg）")
    ax[1].set_ylabel("0→500 km/h 时间（s）")
    ax[1].set_title("轻 26% 换来的是时间，不是极速", fontsize=12)
    ax[1].legend(frameon=False, fontsize=9)
    ax[1].grid(alpha=0.25)

    fig.tight_layout()
    fig.savefig(FIGS / "q6_mass.png")
    print(f"[图] {FIGS / 'q6_mass.png'}")


if __name__ == "__main__":
    raise SystemExit(main())
