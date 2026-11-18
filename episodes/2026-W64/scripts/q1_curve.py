"""Q1：一顿饭的血糖曲线（含标定过程）。

第一版参数（文献典型值）算出峰值 191 @ 72 min，偏高；
标定到 γ=0.026、p3=6e-5、kabs=0.020 后，峰值 149 @ 55 min。
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams

import bg

rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
rcParams["axes.unicode_minus"] = False

EP = Path(__file__).resolve().parents[1]
RES = EP / "results"
FIGS = RES / "figs"
FIGS.mkdir(parents=True, exist_ok=True)


def main() -> int:
    p0 = bg.Params()
    s0 = bg.summarize(bg.simulate(p=p0))

    p1, s1 = bg.calibrate()
    res = bg.simulate(p=p1)

    out = {
        "initial": {"gamma": p0.gamma, "p3": p0.p3, "kabs": p0.kabs,
                    "peak": round(s0["peak"], 1), "peak_tt": round(s0["peak_tt"], 1),
                    "back_tt": round(s0["back_tt"], 1)},
        "calibrated": {"gamma": p1.gamma, "p3": p1.p3, "kabs": p1.kabs,
                       "peak": round(s1["peak"], 1), "peak_tt": round(s1["peak_tt"], 1),
                       "back_tt": round(s1["back_tt"], 1)},
        "peak_mmol": round(s1["peak"] / bg.MG_PER_MMOL, 2),
        "base_mmol": round(p1.Gb / bg.MG_PER_MMOL, 2),
    }
    (RES / "q1_curve.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                       encoding="utf-8")

    fig, ax = plt.subplots(1, 2, figsize=(13.0, 4.7), dpi=160)

    ax[0].plot(res["t"], res["G"], color="#e8604a", lw=2.6, label="血糖")
    ax[0].axhline(p1.Gb, color="#888", ls="--", lw=1)
    ax[0].axvline(s1["peak_tt"], color="#569cd6", ls=":", lw=1.2)
    ax[0].scatter([s1["peak_tt"]], [s1["peak"]], color="#569cd6", zorder=5, s=55)
    ax[0].annotate(f"峰值 {s1['peak']:.0f} mg/dL\n@ {s1['peak_tt']:.0f} min",
                   (s1["peak_tt"], s1["peak"]), textcoords="offset points",
                   xytext=(12, -34), fontsize=11, color="#569cd6", fontweight="bold")
    ax[0].set_xlabel("时间（分钟）")
    ax[0].set_ylabel("血糖（mg/dL）")
    ax[0].set_title("标定后的单餐曲线（50 g 碳水）", fontsize=12)
    ax[0].grid(alpha=.25)

    i_ra = max(range(len(res["Ra"])), key=lambda i: res["Ra"][i])
    i_ins = max(range(len(res["I"])), key=lambda i: res["I"][i])
    lag = res["t"][i_ins] - res["t"][i_ra]
    out["ra_peak_tt"] = round(res["t"][i_ra], 1)
    out["ins_peak_tt"] = round(res["t"][i_ins], 1)
    out["ins_lag_min"] = round(lag, 1)
    out["ins_peak"] = round(res["I"][i_ins], 1)

    ax[1].plot(res["t"], res["Ra"], color="#7fb069", lw=2.4, label="吸收速度 $R_a$")
    ax[1].set_xlabel("时间（分钟）")
    ax[1].set_ylabel("吸收速度 $R_a$（mg/dL/min）", color="#7fb069")
    ax[1].tick_params(axis="y", labelcolor="#7fb069")
    ax2 = ax[1].twinx()
    ax2.plot(res["t"], res["I"], color="#c9a0ff", lw=2.4, label="胰岛素 I")
    ax2.set_ylabel("血胰岛素 I（μU/mL）", color="#9a6ad0")
    ax2.tick_params(axis="y", labelcolor="#9a6ad0")
    ax[1].axvline(res["t"][i_ra], color="#7fb069", ls=":", lw=1)
    ax2.axvline(res["t"][i_ins], color="#9a6ad0", ls=":", lw=1)
    ax[1].set_title(f"吸收先到（{res['t'][i_ra]:.0f} min），胰岛素后到（{res['t'][i_ins]:.0f} min）",
                    fontsize=12)
    ax[1].grid(alpha=.25)

    fig.tight_layout()
    fig.savefig(FIGS / "q1_curve.png")

    print(f"[初始] 峰值 {s0['peak']:.0f} mg/dL @ {s0['peak_tt']:.0f} min，回落 {s0['back_tt']:.0f}")
    print(f"[标定] 峰值 {s1['peak']:.0f} mg/dL @ {s1['peak_tt']:.0f} min，回落 {s1['back_tt']:.0f}")
    print(f"       基础 {p1.Gb/bg.MG_PER_MMOL:.1f} → 峰值 {out['peak_mmol']:.1f} mmol/L")
    print(f"[图] {FIGS / 'q1_curve.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
