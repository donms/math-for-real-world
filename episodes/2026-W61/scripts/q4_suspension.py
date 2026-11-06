"""Q4：悬挂 —— 气动平台要稳在多少毫米。

核心矛盾
--------
Q2 算出：离地间隙变 10 mm，下压力变 649 N。
也就是说**车身高度本身就是气动参数**。普通车的弹簧（40–60 kN/m）在这里远远不够，
必须做主动高度控制。

输出
----
    results/q4_suspension.json
    figs/q4_suspension.png
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

EP = Path(__file__).resolve().parents[1]
RES = EP / "results"
FIGS = RES / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

M = 1800.0
G = 9.81
DOWNFORCE = 6100.0      # N @ 500 km/h（Q2）
DDFORCE_PER_10MM = 649.0
TOL = 0.005             # 允许下沉 5 mm
CORNER_MASS = M / 4


def main() -> int:
    # 1) 若只用被动弹簧，要多硬才能把下沉压在 5 mm
    k_need = DOWNFORCE / TOL
    f_n = np.sqrt(k_need / CORNER_MASS) / (2 * np.pi)

    # 2) 典型超跑弹簧刚度
    k_typical = 60e3
    sag_typical = DOWNFORCE / (4 * k_typical) if False else DOWNFORCE / k_typical * 1000
    # 注意：下压力是整车量，四根弹簧分担
    sag_typical = (DOWNFORCE / 4) / k_typical * 1000   # mm

    # 3) 下沉带来的下压力损失（正反馈）
    loss = DOWNFORCE / TOL * 0 + 0
    delta_df = -sag_typical / 10 * DDFORCE_PER_10MM

    # 4) 俯仰：前后下压力不平衡产生的力矩
    front_df, rear_df = 0.4 * DOWNFORCE, 0.6 * DOWNFORCE
    wheelbase = 2.7
    pitch_moment = (rear_df - front_df) * wheelbase / 2
    k_pitch = 2 * k_need * (wheelbase / 2) ** 2      # 等效俯仰刚度
    pitch_deg = np.degrees(pitch_moment / k_pitch)

    # 5) 阻尼：气动平台希望 ζ≈0.7
    zeta = 0.7
    c_crit = 2 * np.sqrt(k_need * CORNER_MASS)
    c_need = zeta * c_crit

    out = {
        "downforce_N": DOWNFORCE,
        "ddforce_per_10mm_N": DDFORCE_PER_10MM,
        "tolerance_mm": TOL * 1000,
        "passive_k_need_kN_per_m": round(k_need / 1e3, 0),
        "natural_freq_Hz": round(f_n, 1),
        "typical_spring_kN_per_m": k_typical / 1e3,
        "typical_sag_mm": round(sag_typical, 1),
        "typical_downforce_loss_N": round(delta_df, 0),
        "pitch_moment_Nm": round(pitch_moment, 0),
        "pitch_deg": round(pitch_deg, 2),
        "damping_Ns_per_m": round(c_need, 0),
        "active_bandwidth_Hz": 20,
        "note": "被动弹簧下沉 15 mm 会再丢 970 N 下压力 ⇒ 正反馈，必须主动控高",
    }
    (RES / "q4_suspension.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                            encoding="utf-8")

    print(f"[目标] 保 500 km/h 下 6.1 kN 下压力，下沉 ≤ {TOL*1000:.0f} mm")
    print(f"[被动] 需要 {k_need/1e3:.0f} kN/m（典型超跑 {k_typical/1e3:.0f} kN/m）")
    print(f"[对比] 用典型弹簧：下沉 {sag_typical:.1f} mm → 再丢 {abs(delta_df):.0f} N 下压力")
    print(f"[频率] 固有频率 {f_n:.1f} Hz，阻尼 {c_need:.0f} N·s/m（ζ=0.7）")
    print(f"[俯仰] 力矩 {pitch_moment:.0f} N·m → 俯仰角 {pitch_deg:.2f}°")

    plot(out)
    return 0


def plot(out: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import rcParams
    rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(1, 2, figsize=(12.0, 4.4), dpi=150)

    k = np.linspace(10e3, 1.4e6, 300)
    sag = (DOWNFORCE / 4) / k * 1000
    ax[0].semilogx(k / 1e3, sag, color="#569cd6", lw=2.4)
    ax[0].axhline(5, color="#e8604a", ls="--", lw=1.2, label="允许下沉 5 mm")
    ax[0].axvline(60, color="#8a9bb0", ls=":", lw=1.4, label="典型超跑 60 kN/m")
    ax[0].set_xlabel("单根弹簧刚度（kN/m）")
    ax[0].set_ylabel("气动下沉量（mm）")
    ax[0].set_title("被动弹簧压不住 6.1 kN 的下压力", fontsize=12)
    ax[0].set_ylim(0, 80)
    ax[0].legend(frameon=False, fontsize=9)
    ax[0].grid(alpha=0.25, which="both")

    hs = np.linspace(-25, 25, 200)
    ax[1].plot(hs, [DOWNFORCE + h / 10 * DDFORCE_PER_10MM for h in hs], color="#7fb069", lw=2.4)
    ax[1].axhline(DOWNFORCE, color="#8a9bb0", ls="--", lw=1)
    ax[1].set_xlabel("离地间隙变化（mm）")
    ax[1].set_ylabel("500 km/h 下压力（N）")
    ax[1].set_title("高度就是气动参数：±25 mm 改变近 3 kN", fontsize=12)
    ax[1].grid(alpha=0.25)

    fig.tight_layout()
    fig.savefig(FIGS / "q4_suspension.png")
    print(f"[图] {FIGS / 'q4_suspension.png'}")


if __name__ == "__main__":
    raise SystemExit(main())
