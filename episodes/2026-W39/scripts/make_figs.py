#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W39 论文插图生成。

产出（results/figs/）：
  fig01_transmissibility.png   频域传递率曲线族（控制权限的可视化）
  fig02_force_bandwidth.png    力域 × 带宽二维扫描（核心发现）
  fig03_reachable.png          半主动可达集与帕累托前沿
  fig04_tradeoff.png           三目标最优阻尼冲突（设计点折中）
  fig05_band.png               分频段优势
  fig06_sensitivity.png        灵敏度分析（排序稳健性）
  fig07_control_layers.png     控制权限层级与性能阶梯
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from model import (ARCHS, default_params, freqresp, metrics_freq,  # noqa: E402
                   natural_freqs, road_psd_accel)

RESULTS = ROOT / "results"
FIGS = RESULTS / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

# 中文字体（Windows 常见路径，逐个尝试）
for _f in ("Microsoft YaHei", "SimHei", "SimSun"):
    try:
        matplotlib.rcParams["font.sans-serif"] = [_f]
        break
    except Exception:
        continue
matplotlib.rcParams["axes.unicode_minus"] = False
plt.rcParams.update({"figure.dpi": 130, "savefig.dpi": 130,
                     "font.size": 11, "axes.grid": True,
                     "grid.alpha": 0.3, "axes.axisbelow": True})

C_BLUE, C_RED, C_NAVY, C_GREEN = "#2C6BB0", "#C0392B", "#1F3B63", "#1E8449"


def save(fig, name: str):
    p = FIGS / name
    fig.tight_layout()
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    print(f"  [fig] {name}")


def main() -> int:
    p = default_params()
    fb, fw = natural_freqs(p)

    # ---------- 图 1：传递率曲线族 ----------
    f = np.logspace(np.log10(0.1), np.log10(30), 600)
    cs = np.geomspace(p["c_min"], p["c_max"], 12)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    for ax, row, lab, yl in ((axes[0], 0, "车身加速度", r"$|\ddot z_s/\ddot z_r|$"),
                             (axes[1], 1, "悬架动挠度", r"$|(z_s-z_u)/\ddot z_r|$")):
        for c in cs:
            H = freqresp(p, float(c), f)
            ax.loglog(f, np.abs(H[row, :]), lw=1.2, alpha=0.75,
                      color=plt.cm.viridis(np.log(c / p["c_min"]) / np.log(p["c_max"] / p["c_min"])))
        ax.axvline(fb, color=C_RED, ls="--", lw=1.4, label=f"车身固有频率 {fb:.2f} Hz")
        ax.axvline(fw, color=C_GREEN, ls=":", lw=1.4, label=f"车轮固有频率 {fw:.1f} Hz")
        ax.set_xlabel("频率 (Hz)")
        ax.set_ylabel(yl)
        ax.set_title(lab + "传递率（阻尼 0.15-8 c0 扫描）")
        ax.legend(fontsize=9)
    fig.suptitle("图 1  可调阻尼带来的传递率可实现区间：自由度集中在固有频率附近", y=1.03)
    save(fig, "fig01_transmissibility.png")

    # ---------- 图 2：力域 × 带宽 ----------
    umax = [300, 600, 1200, 3000, 10000]
    bw = ["30 Hz", "100 Hz", "300 Hz", "无约束"]
    # 数据来自 q2q3 结论中的二维扫描（硬编码已核验数值，并标注来源）
    data = np.array([[1.1470, 1.1238, 1.1215, 0.5196],
                     [0.9596, 0.9455, 0.9453, 0.5196],
                     [0.7551, 0.7477, 0.7478, 0.5196],
                     [0.5335, 0.5317, 0.5329, 0.5196],
                     [0.5175, 0.5180, 0.5196, 0.5196]])
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    ax = axes[0]
    x = np.arange(len(bw))
    for i, u in enumerate(umax):
        ax.plot(x, data[i], "o-", lw=1.8, label=f"力上限 {u} N")
    ax.set_xticks(x); ax.set_xticklabels(bw)
    ax.set_xlabel("作动器带宽")
    ax.set_ylabel(r"车身加速度 RMS (m/s²)")
    ax.set_title("带宽影响很小（同一曲线近乎水平）")
    ax.legend(fontsize=9)
    ax = axes[1]
    for j, b in enumerate(bw[:-1]):
        ax.semilogx(umax, data[:, j], "s-", lw=1.8, label=f"带宽 {b}")
    ax.semilogx(umax, data[:, 3], "k--", lw=1.6, label="无约束（理论上界）")
    ax.set_xlabel("作动器力上限 (N)")
    ax.set_ylabel(r"车身加速度 RMS (m/s²)")
    ax.set_title("力影响极大（曲线随力陡降）")
    ax.legend(fontsize=9)
    fig.suptitle("图 2  决定性能的是力域而非响应速度：带宽提高 10 倍仅改善约 2%，力提高 10 倍改善一倍以上", y=1.03)
    save(fig, "fig02_force_bandwidth.png")

    # ---------- 图 3：可达集与帕累托前沿 ----------
    q2 = json.loads((RESULTS / "q2_bounds.json").read_text(encoding="utf-8"))
    pts = q2["reachable_C"]
    front = q2["pareto_C"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    ax = axes[0]
    ax.scatter([d["acc"] for d in pts], [d["travel"] * 1000 for d in pts],
               c=[d["c_over_c0"] for d in pts], cmap="viridis", s=34, zorder=3)
    ax.plot([d["acc"] for d in front], [d["travel"] * 1000 for d in front],
            "r--", lw=1.6, label="帕累托前沿")
    ax.scatter([1.3674], [9.55], marker="*", s=260, color=C_RED,
               zorder=5, label="被动 c0")
    cb = plt.colorbar(ax.collections[0], ax=ax)
    cb.set_label("阻尼 c / c0")
    ax.set_xlabel(r"车身加速度 RMS (m/s²)")
    ax.set_ylabel("悬架动挠度 RMS (mm)")
    ax.set_title("舒适–姿态 的可达集与前沿")
    ax.legend(fontsize=9)
    ax = axes[1]
    ax.scatter([d["acc"] for d in pts], [d["tire"] for d in pts],
               c=[d["c_over_c0"] for d in pts], cmap="viridis", s=34, zorder=3)
    ax.plot([d["acc"] for d in front], [d["tire"] for d in front],
            "r--", lw=1.6, label="帕累托前沿")
    ax.scatter([1.3674], [690.4], marker="*", s=260, color=C_RED,
               zorder=5, label="被动 c0")
    ax.set_xlabel(r"车身加速度 RMS (m/s²)")
    ax.set_ylabel("轮胎动载荷 RMS (N)")
    ax.set_title("舒适–操稳 的可达集")
    ax.legend(fontsize=9)
    fig.suptitle("图 3  半主动的可达性能集合：三个目标无法同时最优，必须折中", y=1.03)
    save(fig, "fig03_reachable.png")

    # ---------- 图 4：三目标最优阻尼冲突 ----------
    cs2 = np.geomspace(p["c_min"], p["c_max"], 60)
    ms = [(float(c), metrics_freq(p, float(c), "C", 60 / 3.6)) for c in cs2]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax2 = ax.twinx()
    ax.plot([c / p["c0"] for c, _ in ms], [m["acc"] for _, m in ms],
            lw=2, color=C_BLUE, label="车身加速度 RMS（舒适）")
    ax2.plot([c / p["c0"] for c, _ in ms], [m["travel"] * 1000 for _, m in ms],
             lw=2, color=C_RED, label="悬架动挠度 RMS（姿态）")
    for v, lab, col, a in ((0.62, "舒适最优 0.62c0", C_BLUE, ax),
                           (1.39, "操稳最优 1.39c0", C_GREEN, ax)):
        a.axvline(v, color=col, ls="--", lw=1.3)
        a.text(v, a.get_ylim()[1] * 0.96, lab, color=col, fontsize=9, rotation=90,
               va="top")
    ax2.axvline(8.0, color=C_RED, ls="--", lw=1.3)
    ax2.text(8.0, ax2.get_ylim()[1] * 0.96, "姿态最优 8.0c0（顶到上限）",
             color=C_RED, fontsize=9, rotation=90, va="top", ha="right")
    ax.set_xscale("log")
    ax.set_xlabel("阻尼系数 c / c0")
    ax.set_ylabel("车身加速度 RMS (m/s²)", color=C_BLUE)
    ax2.set_ylabel("悬架动挠度 RMS (mm)", color=C_RED)
    ax.set_title("图 4  三个目标的最优阻尼互不相同（相差 13 倍）——被动悬架只能折中")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper center", fontsize=9)
    save(fig, "fig04_tradeoff.png")

    # ---------- 图 5：分频段优势 ----------
    q4 = json.loads((RESULTS / "q4_results.json").read_text(encoding="utf-8"))
    rows = q4["band_metrics"]
    keys = q4["band_keys"]
    names = list(rows.keys())
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    xx = np.arange(len(keys))
    w = 0.36
    for i, nm in enumerate(names):
        vals = [rows[nm][k]["acc"] for k in keys]
        ax.bar(xx + (i - 0.5) * w, vals, w, label=nm,
               color=[C_NAVY, C_RED][i], alpha=0.88)
    ax.set_xticks(xx)
    ax.set_xticklabels([f"{k}\n{hz}" for k, hz in zip(
        keys, ["车身浮动", "车身共振", "过渡段", "车轮跳动"])], fontsize=9)
    ax.set_ylabel(r"车身加速度 RMS (m/s²)")
    ax.set_title("图 5  分频段优势：半主动的优势集中在 2.5 Hz 以上")
    ax.legend(fontsize=9)
    save(fig, "fig05_band.png")

    # ---------- 图 6：灵敏度 ----------
    sens = q4["sensitivity"]
    labels = [f"{r['参数']}\n{r['扰动']}" for r in sens]
    gains = [r["提升%"] for r in sens]
    fig, ax = plt.subplots(figsize=(11, 4.4))
    colors = [C_GREEN if g > 0 else C_RED for g in gains]
    ax.bar(range(len(gains)), gains, color=colors, alpha=0.88)
    ax.axhline(np.median(gains), color=C_NAVY, ls="--", lw=1.5,
               label=f"中位 {np.median(gains):.2f}%")
    ax.set_xticks(range(len(gains)))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("半主动相对被动的提升 (%)")
    ax.set_title("图 6  灵敏度分析：10 组 ±20% 扰动下排序翻转 0 次（全部为正），\n"
                 "但幅度在 1.67%–10.89% 间波动 —— 结论给排序，不给单点数值")
    ax.legend(fontsize=9)
    save(fig, "fig06_sensitivity.png")

    # ---------- 图 7：控制权限层级与性能阶梯 ----------
    q6 = json.loads((RESULTS / "q6_optimal_semiactive.json").read_text(encoding="utf-8"))
    t = q6["table"]
    keys7 = ["被动 c0", f"最优常数 {q6['c_opt_over_c0']:.2f}c0",
             "天棚 skyhook（半主动）", "裁剪最优 clipped（半主动）", "全主动 LQR（力限3000N）"]
    vals = [t[k]["gain_pct"] for k in keys7 if k in t]
    labs = ["被动\n（无自由度）", "最优常数\n（离线标定）", "半主动天棚\n（只能耗散）",
            "半主动裁剪\n（只能耗散）", "全主动\n（可注入能量）"]
    fig, ax = plt.subplots(figsize=(11, 4.8))
    cols = [C_NAVY, C_BLUE, C_GREEN, C_GREEN, C_RED]
    bars = ax.bar(range(len(vals)), vals, color=cols, alpha=0.9)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + (2 if v > 0 else -5),
                f"{v:+.1f}%", ha="center", fontsize=10, fontweight="bold")
    ax.axhline(0, color="k", lw=1)
    ax.set_xticks(range(len(labs)))
    ax.set_xticklabels(labs, fontsize=9)
    ax.set_ylabel("相对被动悬架的性能变化 (%)")
    ax.set_title("图 7  控制权限层级与性能阶梯：半主动（−5%）与全主动（−67%）相差一个数量级\n"
                 "（负值表示加速度降低，即更优）")
    save(fig, "fig07_control_layers.png")

    print(f"\n[完成] 共 {len(list(FIGS.glob('*.png')))} 张图 → {FIGS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
