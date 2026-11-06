"""Q2：下压力 —— 要多少才稳，代价是几 km/h。

关键关系
--------
    下压力 L = ½·ρ·ClA·v²
    气动件阻力 D = L / (L/D)_wing
    ⇒ ΔCdA = ClA / (L/D)

于是阻力预算变成一条很硬的约束：

    CdA_body + ClA/(L/D) ≤ 0.55

**下压力不是免费加的，它是用 CdA 换来的。**
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

EP = Path(__file__).resolve().parents[1]
RES = EP / "results"
FIGS = RES / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

RHO = 1.15
M = 1800.0
G = 9.81
AREA = 1.95
V500 = 500 / 3.6
V520 = 520 / 3.6
P_BUDGET = 1000e3

CDA_BODY = 0.429            # Cd 0.22 × 1.95（光体，无大件）
CDA_LIMIT = 0.55            # Q1 给的预算上限
LD_WING = 6.0               # 气动件升阻比（③ 量级）


def top_speed(cda: float, power: float = P_BUDGET) -> float:
    lo, hi = 10.0, 300.0
    for _ in range(200):
        mid = (lo + hi) / 2
        p = 0.5 * RHO * cda * mid ** 3 + M * G * 0.012 * mid
        lo, hi = (mid, hi) if p < power else (lo, mid)
    return (lo + hi) / 2


def downforce(cla: float, v: float) -> float:
    return 0.5 * RHO * cla * v ** 2


def main() -> int:
    out = {"cda_body": CDA_BODY, "cda_limit": CDA_LIMIT, "ld_wing": LD_WING}

    # 1) 预算允许的最大 ClA_add
    cla_max = (CDA_LIMIT - CDA_BODY) * LD_WING
    out["max_cla_within_budget"] = round(cla_max, 3)

    # 2) 前沿：ClA → 总 CdA / 极速 / 500 km/h 下压力
    rows = []
    for cla in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2):
        dcda = cla / LD_WING
        cda = CDA_BODY + dcda
        df = downforce(cla, V500)
        rows.append({"cla": cla, "dcda": round(dcda, 3), "cda": round(cda, 3),
                     "downforce_kN": round(df / 1e3, 2),
                     "downforce_g": round(df / (M * G), 2),
                     "vmax_kmh": round(top_speed(cda) * 3.6, 1)})
    out["frontier"] = rows

    # 3) 稳定性判据
    #    前轴静载 45%，要保留转向权限：前轴下压力 ≥ 前轴静载的 20%
    FRONT_SHARE = 0.45
    front_static = M * G * FRONT_SHARE
    need_front = 0.20 * front_static
    need_total = 0.15 * M * G
    out["stability"] = {
        "front_static_kN": round(front_static / 1e3, 2),
        "need_front_downforce_kN": round(need_front / 1e3, 2),
        "need_total_downforce_kN": round(need_total / 1e3, 2),
        "cla_for_front_at_500": round(need_front / (0.5 * RHO * V500 ** 2 * FRONT_SHARE), 3),
    }

    # 4) 选择：ClA = 0.55（前 0.22 / 后 0.33）
    cla_pick = 0.55
    dcda = cla_pick / LD_WING
    cda_pick = CDA_BODY + dcda
    out["design"] = {
        "cla": cla_pick, "cla_front": 0.22, "cla_rear": 0.33,
        "cda": round(cda_pick, 3),
        "downforce_500_kN": round(downforce(cla_pick, V500) / 1e3, 2),
        "downforce_520_kN": round(downforce(cla_pick, V520) / 1e3, 2),
        "vmax_kmh": round(top_speed(cda_pick) * 3.6, 1),
        "cost_kmh": round((top_speed(CDA_BODY) - top_speed(cda_pick)) * 3.6, 1),
    }

    # 5) 俯仰敏感性：离地间隙 10 mm → ΔCl ≈ 0.03（③ 量级）
    dcl_per_10mm = 0.03
    cl_pick = cla_pick / AREA
    df_change = 0.5 * RHO * (dcl_per_10mm * AREA) * V500 ** 2
    out["pitch_sensitivity"] = {
        "dcl_per_10mm": dcl_per_10mm,
        "cl_at_pick": round(cl_pick, 3),
        "delta_downforce_N_per_10mm": round(df_change, 0),
        "note": "10 mm 的高度变化足以改变数百牛的升力 ⇒ 必须主动控高",
    }

    (RES / "q2_downforce.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                          encoding="utf-8")

    print(f"[预算] 光体 CdA {CDA_BODY}，上限 {CDA_LIMIT} ⇒ 可换 ClA ≤ {cla_max:.2f}"
          f"（L/D={LD_WING}）")
    print("\n[前沿] ClA → 总 CdA / 500 km/h 下压力 / 极速")
    for r in rows:
        print(f"   ClA {r['cla']:.1f} → CdA {r['cda']:.3f}，"
              f"下压力 {r['downforce_kN']:5.2f} kN（{r['downforce_g']:.2f} g），"
              f"极速 {r['vmax_kmh']:.0f} km/h")
    d = out["design"]
    print(f"\n[选型] ClA {d['cla']}（前 0.22 / 后 0.33）→ CdA {d['cda']}，"
          f"500 km/h 下压力 {d['downforce_500_kN']} kN，极速 {d['vmax_kmh']} km/h，"
          f"代价 {d['cost_kmh']} km/h")
    print(f"[俯仰] 离地间隙每变 10 mm ⇒ 下压力变化 {df_change:.0f} N")

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
    cla = np.linspace(0, 1.2, 120)

    # (a) 下压力
    ax[0].plot(cla, [downforce(c, V500) / 1e3 for c in cla], color="#569cd6", lw=2.4)
    ax[0].axhline(M * G / 1e3, color="#e8604a", ls="--", lw=1.2, label="整车重量 17.7 kN")
    ax[0].axvline(0.55, color="#7fb069", ls=":", lw=1.4, label="本文选型 ClA=0.55")
    ax[0].set_xlabel("ClA（升力面积，m²）")
    ax[0].set_ylabel("500 km/h 下压力（kN）")
    ax[0].set_title("下压力随 ClA 线性增长", fontsize=12)
    ax[0].legend(frameon=False, fontsize=9)
    ax[0].grid(alpha=0.25)

    # (b) 极速代价
    ax[1].plot(cla, [top_speed(CDA_BODY + c / LD_WING) * 3.6 for c in cla],
               color="#e8604a", lw=2.4)
    ax[1].axhline(520, color="#8a9bb0", ls="--", lw=1.2, label="目标 520 km/h")
    ax[1].axvline(0.55, color="#7fb069", ls=":", lw=1.4)
    ax[1].set_xlabel("ClA（m²）")
    ax[1].set_ylabel("1 000 kW 下极速（km/h）")
    ax[1].set_title("每加一点下压力，极速就掉一点", fontsize=12)
    ax[1].legend(frameon=False, fontsize=9)
    ax[1].grid(alpha=0.25)

    # (c) 预算条
    ax[2].barh(["光体", "气动件", "合计", "预算上限"],
               [CDA_BODY, 0.55 / LD_WING, CDA_BODY + 0.55 / LD_WING, CDA_LIMIT],
               color=["#8a9bb0", "#deac5c", "#569cd6", "#e8604a"], height=0.55)
    for i, v in enumerate([CDA_BODY, 0.55 / LD_WING, CDA_BODY + 0.55 / LD_WING, CDA_LIMIT]):
        ax[2].text(v + 0.005, i, f"{v:.3f}", va="center", fontsize=10)
    ax[2].set_xlabel("CdA（m²）")
    ax[2].set_title("CdA 预算怎么花掉的", fontsize=12)
    ax[2].set_xlim(0, 0.65)
    ax[2].grid(alpha=0.25, axis="x")

    fig.tight_layout()
    fig.savefig(FIGS / "q2_downforce.png")
    print(f"[图] {FIGS / 'q2_downforce.png'}")


if __name__ == "__main__":
    raise SystemExit(main())
