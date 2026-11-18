"""Q2：峰值为什么在 1 小时——吸收与清除的赛跑。

dG/dt = 0  ⟺  Ra/(Vg·BW) = (p1+X)·G - p1·Gb
左边是"进来的"，右边是"出去的"。交点就是峰值。
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
    p, _ = bg.calibrate()
    res = bg.simulate(p=p)

    # 进项 / 出项
    inflow = [ra for ra in res["Ra"]]
    outflow = [(p.p1 + x) * g - p.p1 * p.Gb for g, x in zip(res["G"], res["X"])]

    # 找交点（最近的一对）
    cross = None
    for i in range(1, len(inflow)):
        if inflow[i - 1] >= outflow[i - 1] and inflow[i] < outflow[i]:
            cross = res["t"][i]
            break
    peak_tt = max(range(len(res["G"])), key=lambda i: res["G"][i])
    peak_t = res["t"][peak_tt]

    out = {"cross_tt": round(cross, 1) if cross else None,
           "peak_tt": round(peak_t, 1),
           "inflow_peak_tt": round(res["t"][max(range(len(inflow)), key=lambda i: inflow[i])], 1),
           "outflow_peak_tt": round(res["t"][max(range(len(outflow)), key=lambda i: outflow[i])], 1),
           "max_inflow": round(max(inflow), 3), "max_outflow": round(max(outflow), 3)}
    (RES / "q2_race.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                      encoding="utf-8")

    fig, ax = plt.subplots(1, 2, figsize=(13.0, 4.7), dpi=160)

    # 左：两个速率
    ax[0].plot(res["t"], inflow, color="#7fb069", lw=2.6, label="进来：$R_a$")
    ax[0].plot(res["t"], outflow, color="#e8604a", lw=2.6, label="出去：$(p_1+X)G-p_1G_b$")
    if cross:
        ax[0].axvline(cross, color="#333", ls="--", lw=1.2)
        ax[0].annotate(f"交点 {cross:.0f} min\n= 血糖峰值",
                       (cross, max(inflow) * 0.55), textcoords="offset points",
                       xytext=(14, 0), fontsize=11, color="#333", fontweight="bold")
    ax[0].set_xlim(0, 200)
    ax[0].set_xlabel("时间（分钟）")
    ax[0].set_ylabel("速率（mg/dL/min）")
    ax[0].set_title("吸收先冲上去，清除随后追上", fontsize=12)
    ax[0].legend(frameon=False, fontsize=10)
    ax[0].grid(alpha=.25)

    # 右：净变化率
    net = [i - o for i, o in zip(inflow, outflow)]
    ax[1].plot(res["t"], net, color="#569cd6", lw=2.4)
    ax[1].axhline(0, color="#333", lw=1)
    ax[1].axvline(peak_t, color="#333", ls="--", lw=1.2)
    ax[1].fill_between(res["t"], net, 0, where=[n > 0 for n in net],
                       color="#7fb069", alpha=.18)
    ax[1].fill_between(res["t"], net, 0, where=[n <= 0 for n in net],
                       color="#e8604a", alpha=.18)
    ax[1].set_xlim(0, 200)
    ax[1].set_xlabel("时间（分钟）")
    ax[1].set_ylabel("净变化率 dG/dt（mg/dL/min）")
    ax[1].set_title(f"净变化率过零，就是峰值（{peak_t:.0f} min）", fontsize=12)
    ax[1].grid(alpha=.25)

    fig.tight_layout()
    fig.savefig(FIGS / "q2_race.png")

    print(f"[吸收峰] {out['inflow_peak_tt']:.0f} min　[清除峰] {out['outflow_peak_tt']:.0f} min")
    print(f"[交点] {cross:.0f} min　[血糖峰值] {peak_t:.0f} min")
    print(f"[净变化率] 过零点与曲线峰值一致 ✓" if cross and abs(cross - peak_t) < 2
          else f"[警告] 交点与峰值差 {abs(cross - peak_t):.1f} min")
    print(f"[图] {FIGS / 'q2_race.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
