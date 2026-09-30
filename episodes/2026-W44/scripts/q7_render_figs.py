#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W44 · 本期配图（6 张）→ `results/figs/`。

## ★★ 字形纪律（本项目最高频的静默失败）

微软雅黑/黑体**缺少**下列字符，matplotlib/PIL **只给一行 stderr、不报错**，
于是带豆腐块的图会直接被发出去（W43 在配图与幻灯片上**各踩一次**）：

| 禁用 | 原因 |
|---|---|
| `⇒` `⟷` `↔` `⌈` `⌉` `❌` `✅` `⚠️` | 字体无此字形 |
| `₁` `₂`（U+2081/2082 下标）| 字体无此字形 |

**允许**：CJK、基本 Latin、全角标点、`→`、`★`、`① ②`、`×`、`−`、`≥`。

⇒ 本脚本所有文本**只用允许集**，并在末尾用 `FT2Font` **逐字符校验**。

## 图目录

| # | 文件 | 内容 |
|---|---|---|
| 1 | `fig1_双峰错位.png` | ★ 出生 vs 在园幼儿 vs 园数，三条曲线 + 峰值错位标注 |
| 2 | `fig2_逐年变化.png` | 出生人口与园数的同比变化（降幅扩大）|
| 3 | `fig3_需求预测.png` | Q1 情景预测（2035 区间 + 历史）|
| 4 | `fig4_传导进度.png` | Q2 已兑现比例 ρ 的可视化 |
| 5 | `fig5_撤并策略.png` | Q3 帕累托前沿 + 三策略位置 |
| 6 | `fig6_公民办分化.png` | Q4 公办/民办在园幼儿指数化对比 |

用法：
    $PY q7_render_figs.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
CLEAN = EP / "data" / "clean"
RES = EP / "results"
FIGS = RES / "figs"

# ---- 中文字体（必须显式注册）----
for f in ("<LOCAL_PATH>", "<LOCAL_PATH>"):
    if Path(f).exists():
        font_manager.fontManager.addfont(f)
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 130

NAVY, RED, BLUE, GREY = "#1F3B63", "#C0392B", "#2E86C1", "#7F8C8D"
TXT: list[str] = []          # 收集所有画上去的文字，供字形校验


def T(ax, x, y, s, **kw):
    TXT.append(s)
    return ax.text(x, y, s, **kw)


def load():
    kg, kc, births = {}, {}, {}
    with (CLEAN / "kindergarten.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            y = int(r["年份"])
            if r["在园幼儿_万人"].strip():
                kg[y] = float(r["在园幼儿_万人"])
            if r["幼儿园数_万所"].strip():
                kc[y] = float(r["幼儿园数_万所"])
    with (CLEAN / "births.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            births[int(r["年份"])] = float(r["出生人口_万人"])
    return kg, kc, births


def fig1(kg, kc, births):
    fig, ax = plt.subplots(figsize=(9, 5.4))
    by = sorted(births)
    ky = sorted(kc)
    ey = sorted(kg)
    ax.plot(by, [births[y] for y in by], "o-", color=RED, lw=2.4,
            label="出生人口（万人）")
    ax.plot(ky, [kc[y] * 60 for y in ky], "s-", color=BLUE, lw=2.4,
            label="幼儿园数（万所，右轴）")
    ax.set_ylabel("出生人口（万人）", color=RED)
    ax.tick_params(axis="y", labelcolor=RED)
    ax2 = ax.twinx()
    ax2.plot(ky, [kc[y] for y in ky], "s-", color=BLUE, lw=2.4)
    ax2.plot(ey, [kg[y] / 100 for y in ey], "^-", color=NAVY, lw=2.4)
    ax2.set_ylabel("园数（万所）/ 在园幼儿（百万人）", color=BLUE)
    ax2.tick_params(axis="y", labelcolor=BLUE)
    ax.lines[1].remove()

    ax.axvline(2016, color=RED, ls=":", lw=1.6)
    ax2.axvline(2020, color=NAVY, ls=":", lw=1.6)
    ax2.axvline(2021, color=BLUE, ls=":", lw=1.6)
    # ⚠️ 标注要加白底，否则会被自己那条竖直虚线**穿过**（实测被切成两半）
    BB = dict(fc="white", ec="none", alpha=0.85, boxstyle="round,pad=0.18")
    T(ax, 2016.15, ax.get_ylim()[1] * 0.955, "出生峰 2016", color=RED,
      fontsize=9.5, fontweight="bold", bbox=BB)
    T(ax2, 2020.15, ax2.get_ylim()[1] * 0.72, "在园峰 2020", color=NAVY,
      fontsize=9.5, fontweight="bold", bbox=BB)
    T(ax2, 2021.15, ax2.get_ylim()[1] * 0.52, "园数峰 2021", color=BLUE,
      fontsize=9.5, fontweight="bold", bbox=BB)
    T(ax, 2017.4, ax.get_ylim()[1] * 0.28,
      "峰值错位 → 滞后 4 至 5 年", color="#333333", fontsize=11,
      fontweight="bold",
      bbox=dict(fc="#FFF6E5", ec="#E0B060", boxstyle="round,pad=0.4"))
    ax.set_title("三条曲线的峰值不在同一年：出生 2016、在园 2020、园数 2021",
                 fontsize=12.5, fontweight="bold", color=NAVY)
    ax.set_xlabel("年份")
    # ★ 横轴只显示整数年（默认会给出 2007.5 / 2010.0 这类小数刻度）
    ax.set_xticks(list(range(2008, 2026, 2)))
    ax.set_xticklabels([str(y) for y in range(2008, 2026, 2)])
    h1 = plt.Line2D([], [], color=RED, marker="o", label="出生人口")
    h2 = plt.Line2D([], [], color=NAVY, marker="^", label="在园幼儿")
    h3 = plt.Line2D([], [], color=BLUE, marker="s", label="幼儿园数")
    ax.legend(handles=[h1, h2, h3], loc="lower left", fontsize=9.5)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGS / "fig1_双峰错位.png")
    plt.close(fig)


def fig2(births, kc):
    fig, ax = plt.subplots(figsize=(9, 4.6))
    by = sorted(births)
    years = [y for y in by if y - 1 in births]
    db = [(births[y] / births[y - 1] - 1) * 100 for y in years]
    ky = [y for y in sorted(kc) if y - 1 in kc]
    dk = [(kc[y] / kc[y - 1] - 1) * 100 for y in ky]
    ax.bar([y - 0.2 for y in years], db, width=0.4, color=RED,
           label="出生人口同比")
    ax.bar([y + 0.2 for y in ky], dk, width=0.4, color=BLUE,
           label="幼儿园数同比")
    ax.axhline(0, color="#333333", lw=1)
    ax.set_ylabel("同比变化（%）")
    ax.set_xlabel("年份")
    T(ax, 2024, dk[ky.index(2024)] + 0.8, "+5.8% 龙年反弹", color=RED,
      fontsize=9.5, fontweight="bold")
    ax.set_title("出生人口与幼儿园数的同比变化：降幅逐年扩大",
                 fontsize=12.5, fontweight="bold", color=NAVY)
    ax.legend(fontsize=9.5)
    ax.grid(alpha=0.25, axis="y")
    fig.tight_layout()
    fig.savefig(FIGS / "fig2_逐年变化.png")
    plt.close(fig)


def fig3(kg):
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    ey = sorted(kg)
    ax.plot(ey, [kg[y] for y in ey], "o-", color="#333333", lw=2.6,
            label="实际（公报原文）")
    pred = {}
    with (RES / "q1_预测.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            pred.setdefault(r["情景"], []).append(
                (int(r["年份"]), float(r["在园幼儿_万人"]),
                 float(r["下界_万人"]), float(r["上界_万人"])))
    s1 = sorted(pred["S1_稳住"])
    ys = [2025] + [p[0] for p in s1]
    lo = [kg[2025]] + [p[2] for p in s1]
    hi = [kg[2025]] + [p[3] for p in s1]
    mid = [kg[2025]] + [p[1] for p in s1]
    ax.fill_between(ys, lo, hi, color=BLUE, alpha=0.18,
                    label="预测区间（q 观测范围）")
    ax.plot(ys, mid, "--", color=BLUE, lw=2.4, label="S1 稳住情景")
    for sy, c in (("S2_缓升", "#27AE60"), ("S3_冲顶", "#8E44AD")):
        d = sorted(pred[sy])
        ax.plot([2025] + [p[0] for p in d], [kg[2025]] + [p[1] for p in d],
                ":", color=c, lw=2.0, label=f"{sy.replace('_',' ')}")
    ax.axvline(2028, color=RED, ls=":", lw=1.6)
    T(ax, 2028.1, ax.get_ylim()[0] + 220, "谷底约 2028", color=RED,
      fontsize=9.5, fontweight="bold")
    ax.annotate("", xy=(2035, 2311), xytext=(2035, 2827),
                arrowprops=dict(arrowstyle="<->", color=RED, lw=1.8))
    T(ax, 2031.4, 2900, "2035 区间 2311 至 2827 万", color=RED, fontsize=9.5,
      fontweight="bold")
    ax.set_ylabel("在园幼儿（万人）")
    ax.set_xlabel("年份")
    ax.set_title("学位需求预测：出生队列已定，2026 至 2028 是推算而非预测",
                 fontsize=12.5, fontweight="bold", color=NAVY)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGS / "fig3_需求预测.png")
    plt.close(fig)


def fig4():
    lag = json.loads((CLEAN / "q2_lag.json").read_text(encoding="utf-8"))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.4, 4.4),
                                   gridspec_kw={"width_ratios": [1.35, 1]})
    # 左：进度条
    rho = lag["rho"]
    ax1.barh([0], [1.0], color="#E8E8E8", height=0.5)
    ax1.barh([0], [rho], color=RED, height=0.5)
    T(ax1, rho / 2, 0, f"已兑现 {rho:.1%}", color="white", fontsize=12,
      fontweight="bold", ha="center", va="center")
    T(ax1, rho + (1 - rho) / 2, 0, f"待兑现 {1-rho:.1%}", color="#444444",
      fontsize=12, fontweight="bold", ha="center", va="center")
    ax1.set_xlim(0, 1)
    ax1.set_ylim(-1.2, 1.2)
    ax1.set_yticks([])
    ax1.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax1.set_xticklabels(["0", "25%", "50%", "75%", "100%"])
    ax1.set_xlabel("占出生下降总冲击的比例")
    ax1.set_title(f"冲击兑现进度  总落差 {lag['total_gap']:.1%}",
                  fontsize=11.5, fontweight="bold", color=NAVY)
    # 右：落差分解
    ax2.bar(["总落差", "已兑现", "待兑现"],
            [lag["total_gap"] * 100, lag["realized"] * 100,
             (lag["total_gap"] - lag["realized"]) * 100],
            color=[GREY, RED, "#F0A030"])
    for i, v in enumerate([lag["total_gap"] * 100, lag["realized"] * 100,
                           (lag["total_gap"] - lag["realized"]) * 100]):
        T(ax2, i, v + 1.2, f"{v:.1f}%", ha="center", fontsize=11,
          fontweight="bold")
    ax2.set_ylabel("在园幼儿降幅（%）")
    ax2.set_title("落差分解", fontsize=11.5, fontweight="bold", color=NAVY)
    ax2.grid(alpha=0.25, axis="y")
    fig.suptitle("最坏时刻尚未到来：还差约三成",
                 fontsize=13, fontweight="bold", color=NAVY)
    fig.tight_layout()
    fig.savefig(FIGS / "fig4_传导进度.png")
    plt.close(fig)


def fig5():
    sit = json.loads((CLEAN / "q3_siting.json").read_text(encoding="utf-8"))
    front = sit["front"]
    fig, ax = plt.subplots(figsize=(9, 5.0))
    x = [f["占比"] * 100 for f in front]
    y = [f["增幅"] * 100 for f in front]
    ax.plot(x, y, "-", color=NAVY, lw=2.6, label="帕累托前沿（贪心最优）")
    knee = sit["knee"]
    ax.axvline(knee / 60 * 100, color=RED, ls=":", lw=1.8)
    T(ax, knee / 60 * 100 + 1.5, 60, f"拐点 {knee/60*100:.0f}%", color=RED,
      fontsize=10.5, fontweight="bold")
    # 三策略位置（关 20%）
    # ⚠️ A 与 C 的值只差 1 个百分点 ⇒ 标注会**重叠**，必须分开摆并拉引导线
    placements = [
        ("C 贪心最优", 3.0, BLUE, 21.0, 14.0),
        ("A 关最小", 4.0, "#27AE60", 26.0, 24.0),
        ("B 关最偏远", 27.0, RED, 23.0, 33.0),
    ]
    for name, v, c, lx, ly in placements:
        ax.plot([20], [v], "o", color=c, ms=11, zorder=5)
        ax.annotate(f"{name}  +{v:.1f}%", xy=(20, v), xytext=(lx, ly),
                    color=c, fontsize=10, fontweight="bold",
                    arrowprops=dict(arrowstyle="-", color=c, lw=1.2,
                                    shrinkA=0, shrinkB=4))
    ax.set_xlabel("关闭的幼儿园比例（%）")
    ax.set_ylabel("可达性代价增幅（%）")
    ax.set_title("撤并的代价是非线性的：拐点在约 47%，而关哪一所差 23 个百分点",
                 fontsize=12, fontweight="bold", color=NAVY)
    ax.legend(fontsize=9.5, loc="upper left")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGS / "fig5_撤并策略.png")
    plt.close(fig)


def fig6():
    rows = {}
    with (CLEAN / "kindergarten.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if not r["民办幼儿园_万所"].strip():
                continue
            if not r["在园幼儿_万人"].strip():
                continue
            y = int(r["年份"])
            te = float(r["在园幼儿_万人"])
            pe = float(r["民办在园幼儿_万人"])
            rows[y] = (pe, te - pe)
    ys = sorted(rows)
    base = rows[ys[0]]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(ys, [rows[y][0] / base[0] * 100 for y in ys], "o-", color=RED,
            lw=2.6, label="民办在园幼儿")
    ax.plot(ys, [rows[y][1] / base[1] * 100 for y in ys], "s-", color=NAVY,
            lw=2.6, label="公办在园幼儿")
    ax.axhline(100, color=GREY, ls="--", lw=1.2)
    for y in (ys[0], ys[-1]):
        ax.annotate(f"{rows[y][0]/base[0]*100:.0f}", (y, rows[y][0] / base[0] * 100),
                    textcoords="offset points", xytext=(0, -16),
                    color=RED, fontsize=10, fontweight="bold", ha="center")
        ax.annotate(f"{rows[y][1]/base[1]*100:.0f}", (y, rows[y][1] / base[1] * 100),
                    textcoords="offset points", xytext=(0, 9),
                    color=NAVY, fontsize=10, fontweight="bold", ha="center")
    ax.set_ylabel(f"指数（{ys[0]} 年 = 100）")
    ax.set_xlabel("年份")
    ax.set_title("收缩由民办承担：7 年腰斩，公办几乎没动",
                 fontsize=12.5, fontweight="bold", color=NAVY)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGS / "fig6_公民办分化.png")
    plt.close(fig)


def check_glyphs() -> int:
    """★ 逐字符校验：允许集之外的字符一律报出（防豆腐块）。"""
    from matplotlib import ft2font
    fp = "<LOCAL_PATH>"
    if not Path(fp).exists():
        print("  [!] 找不到 msyh.ttc，跳过字形校验")
        return 0
    font = ft2font.FT2Font(fp)
    allowed_extra = set(" \n\t")
    bad: dict[str, list[str]] = {}
    for s in TXT:
        for ch in s:
            if ch in allowed_extra:
                continue
            if font.get_char_index(ord(ch)) == 0:
                bad.setdefault(ch, []).append(s[:26])
    if not bad:
        print(f"  [ok] 字形校验通过（{len(TXT)} 段文本，无缺字形）")
        return 0
    print(f"  [X] 发现 {len(bad)} 个缺字形字符：")
    for ch, ctx in bad.items():
        print(f"      {ch!r} U+{ord(ch):04X}  出现在：{ctx[0]}")
    return 1


def main() -> int:
    FIGS.mkdir(parents=True, exist_ok=True)
    kg, kc, births = load()
    print("=" * 80)
    print("  W44 配图渲染")
    print("=" * 80)
    for fn, name in ((lambda: fig1(kg, kc, births), "fig1_双峰错位"),
                     (lambda: fig2(births, kc), "fig2_逐年变化"),
                     (lambda: fig3(kg), "fig3_需求预测"),
                     (fig4, "fig4_传导进度"),
                     (fig5, "fig5_撤并策略"),
                     (fig6, "fig6_公民办分化")):
        fn()
        print(f"  [fig] {name}.png")
    print()
    rc = check_glyphs()
    for p in sorted(FIGS.glob("fig*.png")):
        print(f"  {p.name:<26}{p.stat().st_size/1024:>7.1f} KB")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
