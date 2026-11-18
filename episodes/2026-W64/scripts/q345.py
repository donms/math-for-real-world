"""Q3–Q5：CGM 延迟、HbA1c 换算、个体差异。

Q3：间质液一阶滞后，τ 从 3 到 20 分钟，看峰值时刻右移与峰值削低
Q4：ADAG 换算 + "同平均不同峰值"
Q5：参数扫描（p3 / kabs / γ），看峰值与峰值时刻的分布
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import rcParams

import bg

rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
rcParams["axes.unicode_minus"] = False

EP = Path(__file__).resolve().parents[1]
RES = EP / "results"
FIGS = RES / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

P_CAL, _ = bg.calibrate()


# ---------------------------------------------------------------- Q3
def q3() -> dict:
    rows = []
    for tau in (0.5, 3.0, 8.0, 15.0, 25.0):
        p = replace(P_CAL, tau=tau)
        r = bg.simulate(p=p)
        isf = r["G_isf"]
        i_isf = max(range(len(isf)), key=lambda i: isf[i])
        i_true = max(range(len(r["G"])), key=lambda i: r["G"][i])
        rows.append({"tau": tau, "peak_isf": round(isf[i_isf], 1),
                     "peak_tt_isf": round(r["t"][i_isf], 1),
                     "peak_true": round(r["G"][i_true], 1),
                     "peak_tt_true": round(r["t"][i_true], 1),
                     "delay_min": round(r["t"][i_isf] - r["t"][i_true], 1),
                     "peak_drop": round(r["G"][i_true] - isf[i_isf], 1)})

    fig, ax = plt.subplots(figsize=(9.6, 4.6), dpi=160)
    p = replace(P_CAL, tau=15.0)
    r = bg.simulate(p=p)
    ax.plot(r["t"], r["G"], color="#e8604a", lw=2.6, label="血浆（真值）")
    ax.plot(r["t"], r["G_isf"], color="#569cd6", lw=2.6, ls="--", label="组织间液（CGM 读到）")
    ax.set_xlim(0, 180)
    ax.set_xlabel("时间（分钟）")
    ax.set_ylabel("血糖（mg/dL）")
    ax.set_title("CGM 测的是组织间液：曲线右移、峰值被削低", fontsize=12)
    ax.legend(frameon=False, fontsize=10)
    ax.grid(alpha=.25)
    fig.tight_layout()
    fig.savefig(FIGS / "q3_cgm.png")

    return {"rows": rows, "example_tau": 15.0}


# ---------------------------------------------------------------- Q4
def q4() -> dict:
    conv = {a: round(28.7 * a - 46.7, 1) for a in (5.0, 5.7, 6.5, 7.0, 8.0, 9.0)}

    # 两条"平均相同"的曲线：平稳 vs 尖峰
    t = np.linspace(0, 240, 481)
    steady = np.full_like(t, 140.0)
    spiky = 140.0 + 55 * np.exp(-((t - 60) ** 2) / (2 * 18 ** 2)) \
        + 30 * np.exp(-((t - 160) ** 2) / (2 * 18 ** 2))
    spiky = spiky - (spiky.mean() - 140.0)          # 拉回同一均值

    fig, ax = plt.subplots(1, 2, figsize=(12.6, 4.5), dpi=160)
    a1c = np.linspace(5.0, 9.0, 100)
    ax[0].plot(a1c, 28.7 * a1c - 46.7, color="#e8604a", lw=2.6)
    for a in (5.7, 6.5, 7.0):
        ax[0].scatter([a], [28.7 * a - 46.7], color="#333", zorder=5, s=45)
        ax[0].annotate(f"{a}% → {28.7*a-46.7:.0f}", (a, 28.7 * a - 46.7),
                       textcoords="offset points", xytext=(8, -14), fontsize=10)
    ax[0].set_xlabel("糖化血红蛋白 HbA1c（%）")
    ax[0].set_ylabel("估算平均血糖（mg/dL）")
    ax[0].set_title("ADAG 换算：6.5% 对应 140 mg/dL", fontsize=12)
    ax[0].grid(alpha=.25)

    ax[1].plot(t, steady, color="#8a9bb8", lw=2.4, label="平稳型（均值 140）")
    ax[1].plot(t, spiky, color="#e8604a", lw=2.4, label="尖峰型（均值也是 140）")
    ax[1].axhline(140, color="#333", ls=":", lw=1.2)
    ax[1].set_xlabel("时间（分钟）")
    ax[1].set_ylabel("血糖（mg/dL）")
    ax[1].set_title("同一个平均值，两条完全不同的曲线", fontsize=12)
    ax[1].legend(frameon=False, fontsize=10)
    ax[1].grid(alpha=.25)

    fig.tight_layout()
    fig.savefig(FIGS / "q4_a1c.png")

    return {"a1c_to_eag": conv,
            "steady": {"mean": 140, "sd": 0.0},
            "spiky": {"mean": round(float(spiky.mean()), 1), "sd": round(float(spiky.std()), 1),
                      "max": round(float(spiky.max()), 1)}}


# ---------------------------------------------------------------- Q5
def q5() -> dict:
    rows = []
    for f_p3 in (0.3, 1.0, 3.0, 10.0):
        for f_k in (0.7, 1.0, 1.4):
            p = replace(P_CAL, p3=P_CAL.p3 * f_p3, kabs=P_CAL.kabs * f_k)
            s = bg.summarize(bg.simulate(p=p))
            rows.append({"p3_x": f_p3, "kabs_x": f_k, "peak": round(s["peak"], 1),
                         "peak_tt": round(s["peak_tt"], 1)})

    peaks = [r["peak"] for r in rows]
    tts = [r["peak_tt"] for r in rows]

    # 每种参数单独扫（其余固定）
    solo = {}
    for key, vals in (("p3", (0.3, 1, 3, 10)), ("kabs", (0.7, 1, 1.4, 2.0)),
                      ("gamma", (0.5, 1, 2, 4))):
        ps = []
        for v in vals:
            kw = {key: (getattr(P_CAL, key) * v)}
            p = replace(P_CAL, **kw)
            s = bg.summarize(bg.simulate(p=p))
            ps.append({"x": v, "peak": round(s["peak"], 1), "peak_tt": round(s["peak_tt"], 1)})
        solo[key] = ps

    fig, ax = plt.subplots(1, 2, figsize=(12.6, 4.6), dpi=160)

    for f_k, color in ((0.7, "#7fb069"), (1.0, "#569cd6"), (1.4, "#e8604a")):
        sub = [r for r in rows if r["kabs_x"] == f_k]
        ax[0].plot([r["p3_x"] for r in sub], [r["peak"] for r in sub],
                   "o-", color=color, lw=2.2, label=f"kabs ×{f_k}")
    ax[0].set_xscale("log")
    ax[0].set_xlabel("胰岛素敏感性 $p_3$（相对倍数）")
    ax[0].set_ylabel("峰值（mg/dL）")
    ax[0].set_title("标定后：敏感性 ×10，峰值从 167 掉到 114", fontsize=12)
    ax[0].legend(frameon=False, fontsize=9)
    ax[0].grid(alpha=.25, which="both")

    for f_k, color in ((0.7, "#7fb069"), (1.0, "#569cd6"), (1.4, "#e8604a")):
        sub = [r for r in rows if r["kabs_x"] == f_k]
        ax[1].plot([r["p3_x"] for r in sub], [r["peak_tt"] for r in sub],
                   "o-", color=color, lw=2.2, label=f"kabs ×{f_k}")
    ax[1].set_xscale("log")
    ax[1].set_xlabel("胰岛素敏感性 $p_3$（相对倍数）")
    ax[1].set_ylabel("峰值时刻（分钟）")
    ax[1].set_title("同时峰值时刻从 71 提前到 28 分钟", fontsize=12)
    ax[1].legend(frameon=False, fontsize=9)
    ax[1].grid(alpha=.25, which="both")

    fig.tight_layout()
    fig.savefig(FIGS / "q5_variation.png")

    return {"grid": rows, "peak_range": [min(peaks), max(peaks)],
            "tt_range": [min(tts), max(tts)], "solo": solo}


def main() -> int:
    r3, r4, r5 = q3(), q4(), q5()
    (RES / "q3_cgm.json").write_text(json.dumps(r3, ensure_ascii=False, indent=2), encoding="utf-8")
    (RES / "q4_a1c.json").write_text(json.dumps(r4, ensure_ascii=False, indent=2), encoding="utf-8")
    (RES / "q5_variation.json").write_text(json.dumps(r5, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[Q3 CGM 延迟]")
    for row in r3["rows"]:
        print(f"   τ={row['tau']:5.1f} min  峰值时刻右移 {row['delay_min']:5.1f} min"
              f"  峰值削低 {row['peak_drop']:5.1f} mg/dL")
    print(f"[Q4] HbA1c 6.5% → {r4['a1c_to_eag'][6.5]} mg/dL；"
          f"两条曲线均值都 140，尖峰型 SD={r4['spiky']['sd']}")
    print(f"[Q5] 峰值 {r5['peak_range'][0]:.0f}–{r5['peak_range'][1]:.0f} mg/dL，"
          f"峰值时刻 {r5['tt_range'][0]:.0f}–{r5['tt_range'][1]:.0f} min")
    for k, v in r5["solo"].items():
        print(f"   仅扫 {k}: 峰值 {v[0]['peak']:.0f}→{v[-1]['peak']:.0f}，"
              f"时刻 {v[0]['peak_tt']:.0f}→{v[-1]['peak_tt']:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
