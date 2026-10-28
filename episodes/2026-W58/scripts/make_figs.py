#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""2026-W58 论文级图表：五张 2D 图 + 3D 静帧（3D 动画见 make_3d.py）。"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
EP = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EP.parent.parent / "scripts"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle, Polygon
from matplotlib.gridspec import GridSpec

import w58_core as c
from w58_core import P0, equilibrium, resistance

try:
    from common import C, setup_cn_font, savefig, polish, STYLE
    setup_cn_font()
except Exception as e:      # 单独跑时兜底
    print("[warn] common.py 不可用：", e)
    C = dict(navy="#1F3B63", blue="#2E86C1", red="#C0392B", green="#1E8449",
             darkred="#922B21", grey="#7F8C8D", bg="#FBFBF9", grid="#E5E7E9")
    STYLE = dict(dpi=300, fs_title=16, fs_label=13, fs_tick=11, fig_w_single=8.0,
                 fig_h_single=5.0, fig_w_double=12.0, fig_h_double=5.0)

    def savefig(fig, path, dpi=None):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=dpi or 300, bbox_inches="tight", facecolor=C["bg"])
        print("[fig]", path)

    def polish(ax, xlabel="", ylabel="", title="", legend=True):
        ax.set_xlabel(xlabel, fontsize=STYLE["fs_label"])
        ax.set_ylabel(ylabel, fontsize=STYLE["fs_label"])
        if title:
            ax.set_title(title, fontsize=STYLE["fs_title"], color=C["navy"], pad=10)
        ax.grid(True, ls="--", alpha=0.6, color=C["grid"])
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        if legend:
            h, l = ax.get_legend_handles_labels()
            if h:
                ax.legend(frameon=False, fontsize=STYLE["fs_tick"])
        return ax

R = EP / "results"
FIGS = R / "figs"
FIGS.mkdir(parents=True, exist_ok=True)
V_CRUISE = 21.23
p = P0


def load(name):
    return json.loads((R / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 图 1
def fig1_principle():
    """两支撑受力 + 吃水/湿面积随速度。"""
    fig = plt.figure(figsize=(13.2, 5.2))
    gs = GridSpec(1, 2, width_ratios=[1.15, 1.0], wspace=0.28)
    ax = fig.add_subplot(gs[0])
    ax.set_xlim(-1.35, 1.35)
    ax.set_ylim(-0.55, 0.75)
    ax.axis("off")

    # 水线
    ax.axhline(0, color=C["blue"], lw=2.2, alpha=0.9)
    ax.fill_between([-1.35, 1.35], -0.55, 0, color=C["blue"], alpha=0.12)
    ax.text(-1.30, 0.03, "水面", color=C["blue"], fontsize=10)

    # 车体
    body = Polygon([(-0.95, 0.12), (0.75, 0.12), (0.98, 0.30), (0.62, 0.44),
                    (-0.42, 0.44), (-0.88, 0.30)], closed=True,
                   facecolor="#D5DBDB", edgecolor=C["navy"], lw=1.6, zorder=3)
    ax.add_patch(body)
    ax.text(-0.12, 0.33, "整机 198 kg", ha="center", fontsize=10, color=C["navy"])

    # 两个支撑（升力值取自模型）
    _eq = equilibrium(V_CRUISE, p)
    for x, h, lab, L in ((0.71, _eq["h_front"], "前板", _eq["l_front"]),
                         (-0.77, _eq["h_rear"], "后板", _eq["l_rear"])):
        ax.plot([x - 0.26, x + 0.24], [-h * 8, -h * 8 + 0.02], color=C["navy"], lw=5,
                solid_capstyle="round", zorder=4)
        ax.annotate("", xy=(x, 0.115), xytext=(x, -0.005),
                    arrowprops=dict(arrowstyle="-|>", color=C["red"], lw=2.2))
        ax.text(x + 0.04, -0.06, f"$L$={L:.0f} N（{L/1980*100:.0f}%）", color=C["red"],
                fontsize=9.5)
        ax.text(x, -0.19, lab, color=C["navy"], fontsize=10.5,
                ha="center")

    # 重心 / 推力 / 阻力
    ax.plot(0, 0.24, marker="o", ms=9, color=C["darkred"], zorder=6)
    ax.text(0.03, 0.25, "重心", color=C["darkred"], fontsize=10)
    ax.annotate("", xy=(-0.77, -0.02), xytext=(-1.15, -0.02),
                arrowprops=dict(arrowstyle="-|>", color=C["green"], lw=2.4))
    ax.text(-1.30, -0.09, "推力 $T$", color=C["green"], fontsize=10)
    ax.annotate("", xy=(0.80, 0.05), xytext=(1.12, 0.05),
                arrowprops=dict(arrowstyle="-|>", color=C["grey"], lw=2.4))
    ax.text(1.13, 0.09, "阻力 $D$", color=C["grey"], fontsize=10, ha="right")
    ax.set_title("(a) 两支撑滑行：整机重量由两块板的动升力分担",
                 fontsize=13, color=C["navy"], loc="left")

    # 右图：吃水/湿面积随速度
    ax2 = fig.add_subplot(gs[1])
    Vs = np.linspace(14, 32, 60)
    hf, hr, sw = [], [], []
    for V in Vs:
        eq = equilibrium(V, p)
        hf.append(eq["h_front"] * 100)
        hr.append(eq["h_rear"] * 100)
        res = resistance(V, p, eq, include_wheel_drag=False)
        sw.append(res["S_wet"] * 1e4)
    ax2.plot(Vs * 3.6, hf, color=C["navy"], lw=2.2, label="前板吃水")
    ax2.plot(Vs * 3.6, hr, color=C["red"], lw=2.2, label="后板吃水")
    ax2.axvline(V_CRUISE * 3.6, color=C["grey"], ls=":", lw=1.4)
    ax2.text(V_CRUISE * 3.6 + 0.8, max(hf) * 0.92, "76.4 km/h\n（本次纪录）",
             fontsize=9, color=C["grey"])
    ax2.set_ylim(0, None)
    polish(ax2, "航速 / (km/h)", "吃水深度 / cm",
           "(b) 速度越高，两块板浮得越高：吃水按 $V^{-2}$ 缩小")
    ax3 = ax2.twinx()
    ax3.plot(Vs * 3.6, sw, color=C["green"], lw=1.6, ls="--", label="总湿面积")
    ax3.set_ylabel("总湿面积 / cm²", fontsize=STYLE["fs_label"], color=C["green"])
    ax3.tick_params(axis="y", colors=C["green"])
    ax3.spines["top"].set_visible(False)
    h1, l1 = ax2.get_legend_handles_labels()
    h2, l2 = ax3.get_legend_handles_labels()
    ax2.legend(h1 + h2, l1 + l2, frameon=False, fontsize=9, loc="upper right")
    savefig(fig, FIGS / "fig1_principle.png")


# ---------------------------------------------------------------- 图 2
def fig2_drag():
    q2 = load("q2_校验.json")
    db = q2["drag_break"]
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13.0, 4.9))
    names = ["摩擦", "压力\n(升力分量)", "空气", "附体", "喷溅"]
    vals = [db["friction"], db["pressure"], db["air"], db["appendage"], db["spray"]]
    cols = [C["navy"], C["blue"], C["grey"], C["darkred"], C["green"]]
    bars = ax.bar(names, vals, color=cols, alpha=0.88, width=0.62)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 8, f"{v:.0f} N",
                ha="center", fontsize=10, color=C["navy"])
    ax.set_ylim(0, max(vals) * 1.28)
    ax.text(0.02, 0.93, f"合计 {db['total']:.0f} N  →  16.5 kW（轴功率 25.8 kW）",
            transform=ax.transAxes, fontsize=10.5, color=C["darkred"])
    polish(ax, "", "阻力 / N", "(a) 76.4 km/h 巡航时的阻力账（669 N）")

    # 功率-速度
    Vs = np.linspace(6, 34, 90)
    D, P = [], []
    for V in Vs:
        eq = equilibrium(V, p)
        r = resistance(V, p, eq, include_wheel_drag=False)["total"]
        D.append(r)
        P.append(r * V / p.eta_drive / 1000)
    ax2.plot(Vs * 3.6, D, color=C["navy"], lw=2.2, label="总阻力 $D(V)$")
    ax2.set_ylim(0, 3000)
    polish(ax2, "航速 / (km/h)", "阻力 / N", "(b) 阻力与所需功率：功率按 $V^3$ 涨")
    ax4 = ax2.twinx()
    ax4.plot(Vs * 3.6, P, color=C["red"], lw=2.2, ls="--", label="所需功率")
    ax4.axhline(p.p_max_kw, color=C["darkred"], lw=1.2, ls=":")
    ax4.text(8, p.p_max_kw + 2, f"额定 {p.p_max_kw:.1f} kW", color=C["darkred"], fontsize=9)
    ax4.set_ylabel("功率 / kW", fontsize=STYLE["fs_label"], color=C["red"])
    ax4.tick_params(axis="y", colors=C["red"])
    ax4.set_ylim(0, 120)
    ax4.spines["top"].set_visible(False)
    h1, l1 = ax2.get_legend_handles_labels()
    h3, l3 = ax4.get_legend_handles_labels()
    ax2.legend(h1 + h3, l1 + l3, frameon=False, fontsize=9, loc="upper left")
    savefig(fig, FIGS / "fig2_drag_power.png")


# ---------------------------------------------------------------- 图 3
def fig3_vmax():
    q3 = load("q3_极速.json")
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13.0, 4.9))
    Vs = np.linspace(12, 36, 90)
    Tmax, Drag = [], []
    for V in Vs:
        eq = equilibrium(V, p)
        hw = c.wheel_immersion(eq, p)
        T = max(c.thrust_at(V, hw, p, g, 1.0)[0] for g in (6.5, 7.5, 8.5, 9.5))
        Tmax.append(T)
        Drag.append(resistance(V, p, eq, include_wheel_drag=False)["total"])
    ax.plot(Vs * 3.6, Tmax, color=C["green"], lw=2.4, label="桨轮可用推力（全油门）")
    ax.plot(Vs * 3.6, Drag, color=C["navy"], lw=2.4, label="阻力 $D(V)$")
    # 无滑差的理论推力（= 功率/速度）
    Tideal = [p.p_max_kw * 1000 * p.eta_drive / V for V in Vs]
    ax.plot(Vs * 3.6, Tideal, color=C["grey"], lw=1.6, ls="--",
            label="若推进效率 100%")
    vmax = q3["base_kmh"]
    ax.axvline(vmax, color=C["red"], lw=1.2, ls=":")
    ax.text(vmax - 1.2, 260, f"模型极速\n{vmax:.1f}", color=C["red"],
            ha="right", fontsize=10)
    ax.set_ylim(0, 1800)
    ax.set_xlim(40, 130)
    polish(ax, "航速 / (km/h)", "力 / N",
           "(a) 极速 = 推力曲线与阻力曲线的交点")

    # 功率扫描
    ps = q3["power_sweep"]
    kw = [s["kw"] for s in ps]
    vm = [s["vmax_kmh"] for s in ps]
    ideal = [s["ideal_kmh"] for s in ps]
    ax2.plot(kw, ideal, "o--", color=C["grey"], lw=1.6, ms=5, label="理想（无滑差）")
    ax2.plot(kw, vm, "o-", color=C["red"], lw=2.4, ms=6, label="模型（含桨轮滑差）")
    ax2.axvline(p.p_max_kw, color=C["navy"], ls=":", lw=1.2)
    ax2.text(p.p_max_kw + 1, min(vm) + 2, "现役 60+ hp", color=C["navy"], fontsize=9)
    polish(ax2, "额定功率 / kW", "极速 / (km/h)",
           "(b) 加马力有效，但在 45 kW 附近每 10 kW 只换约 6 km/h")
    savefig(fig, FIGS / "fig3_vmax.png")


# ---------------------------------------------------------------- 图 4
def fig4_sea():
    q4 = load("q4_波浪.json")
    cases = q4["cases"]
    fig = plt.figure(figsize=(13.2, 5.0))
    gs = GridSpec(1, 2, width_ratios=[1.0, 1.0], wspace=0.30)

    ax = fig.add_subplot(gs[0])
    Hs = [x["Hs"] for x in cases]
    wo = [x["wheel_out"] * 100 for x in cases]
    air = [x["air_frac"] * 100 for x in cases]
    ax.plot(Hs, wo, "o-", color=C["red"], lw=2.2, ms=6, label="后轮脱水时间占比")
    ax.plot(Hs, air, "s--", color=C["blue"], lw=1.8, ms=5, label="整机离水时间占比")
    ax.set_ylim(0, 100)
    ax.axhline(50, color=C["grey"], ls=":", lw=1)
    ax.text(1.35, 52, "一半时间", fontsize=9, color=C["grey"])
    polish(ax, "有效波高 $H_s$ / m", "时间占比 / %",
           "(a) 浪一大，桨轮就够不着水")

    ax2 = fig.add_subplot(gs[1])
    env = q4["envelope"]
    ax2.plot([e["Hs"] for e in env], [e["V_hold_kmh"] for e in env],
             "o-", color=C["navy"], lw=2.4, ms=7, label="能维持的最高速度")
    ax2.axhline(v := 40.74 / 32 * 60, color=C["red"], ls=":", lw=1.3)
    ax2.text(0.25, v + 2.2, "本次纪录的平均速度 76.4 km/h", color=C["red"], fontsize=9)
    for e in env:
        ax2.annotate(f"{e['V_hold_kmh']:.0f}", (e["Hs"], e["V_hold_kmh"]),
                     textcoords="offset points", xytext=(6, 6), fontsize=9,
                     color=C["navy"])
    ax2.set_ylim(0, 95)
    polish(ax2, "有效波高 $H_s$ / m", "可维持航速 / (km/h)",
           "(b) 海况包线：浪高每加 0.5 m，速度掉一大截")
    savefig(fig, FIGS / "fig4_sea_envelope.png")


# ---------------------------------------------------------------- 图 5
def fig5_pareto():
    q5 = load("q5_设计.json")
    recs = q5["recs"]
    par = q5["pareto"]
    base = q5["baseline"]
    fig, ax = plt.subplots(figsize=(9.6, 6.2))
    xs = [r["vmax_kmh"] for r in recs]
    ys = [r["az_p95_g"] for r in recs]
    cs = [r["wheel_out"] for r in recs]
    sc = ax.scatter(xs, ys, c=cs, cmap="viridis_r", s=34, alpha=0.75,
                    edgecolor="none", label="设计样本（160 组）")
    cb = fig.colorbar(sc, ax=ax, pad=0.02)
    cb.set_label("后轮脱水时间占比", fontsize=10)
    px = [r["vmax_kmh"] for r in par]
    py = [r["az_p95_g"] for r in par]
    ax.scatter(px, py, s=90, facecolor="none", edgecolor=C["red"], lw=1.8,
               label="Pareto 前沿", zorder=5)
    ax.scatter([base["vmax_kmh"]], [base["az_p95_g"]], marker="*", s=320,
               color=C["red"], label="现役方案（标称参数）", zorder=6)
    # 推荐点
    rec = min(par, key=lambda r: (r["az_p95_g"] + 0.9 * (110 - r["vmax_kmh"])))
    ax.annotate(f"极速优先端点\n{rec['vmax_kmh']:.0f} km/h / {rec['az_p95_g']:.2f} g",
                (rec["vmax_kmh"], rec["az_p95_g"]),
                textcoords="offset points", xytext=(-108, 26), fontsize=9.5,
                color=C["darkred"],
                arrowprops=dict(arrowstyle="->", color=C["darkred"], lw=1.2))
    polish(ax, "极速 / (km/h)", "砰击加速度 95 分位 / g",
           "前后板几何的多目标权衡：更快 与 更稳，不可兼得")
    savefig(fig, FIGS / "fig5_pareto.png")
    return rec


if __name__ == "__main__":
    fig1_principle()
    fig2_drag()
    fig3_vmax()
    fig4_sea()
    rec = fig5_pareto()
    print("[recommend]", rec)
