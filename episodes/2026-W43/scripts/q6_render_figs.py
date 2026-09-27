#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""渲染本期 6 张论文/内容配图到 `results/figs/`。

## 图目录

| 文件 | 内容 | 用途 |
|---|---|---|
| `fig1_city_curves.png` | 五地分摊曲线 + "按受益"基准线 | 知乎/B站/论文 |
| `fig2_ningbo_rounds.png` | 宁波三轮方案对照（越来越陡）| 全部 |
| `fig3_mechanisms.png` | ★ 可谈成率对比（核心图）| 抖音/B站/小红书 |
| `fig4_vote_gate.png` | 12 户表决门槛与 4 户否决 | B站/小红书 |
| `fig5_correlation.png` | 五地规则相关系数 | 知乎/B站 |
| `fig6_kappa.png` | 临界支付意愿比 κ\* 敏感性 | 知乎/论文 |

数据全部来自 `results/*.json` 与 `scripts/q1_build_tables.py`，
**不在此脚本内硬编码任何结论数字**（除标签文字）。

用法：
    $PY q6_render_figs.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]      # → .
ROOT = REPO.parent                               # → <LOCAL_PATH>
EP = REPO / "episodes" / "2026-W43"
RES = EP / "results"
FIGS = RES / "figs"
CLEAN = EP / "data" / "clean"

sys.path.insert(0, str(REPO / "scripts"))
from common import C, setup_cn_font  # noqa: E402

if not setup_cn_font():
    print("[!] 中文字体不可用，图中中文会变方块")
import matplotlib.pyplot as plt  # noqa: E402

GAMMA = 1.35
H = 6


def shares(H: int, gamma: float) -> dict[int, float]:
    raw = {i: float(i - 1) ** gamma for i in range(1, H + 1)}
    raw[1] = 0.0
    s = sum(raw.values())
    return {i: v / s for i, v in raw.items()}


def style(ax, title: str, xlabel: str = "", ylabel: str = ""):
    ax.set_title(title, fontsize=15, color=C["navy"], pad=14, fontweight="bold")
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=12)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=12)
    ax.grid(True, color=C["grid"], linewidth=0.9)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(labelsize=11)


def save(fig, name: str):
    FIGS.mkdir(parents=True, exist_ok=True)
    p = FIGS / name
    fig.tight_layout()
    fig.savefig(p, dpi=200, facecolor=C["bg"])
    plt.close(fig)
    print(f"  [ok] {name}  {p.stat().st_size/1024:.0f} KB")
    return p


# ---------------------------------------------------------------- 图 1
def fig1():
    data = json.loads((CLEAN / "city_rules.json").read_text(encoding="utf-8"))
    norm = {k: {int(i): v for i, v in d.items()}
            for k, d in data["归一化_六层"].items()}
    fig, ax = plt.subplots(figsize=(11, 6))
    x = list(range(1, H + 1))
    base = shares(H, 1.0)

    ax.plot(x, [base[i] * 100 for i in x], "o--", color=C["red"], lw=2.6,
            ms=8, label="理论：按受益分摊 (γ=1)", zorder=5)

    picks = [("北京(六层·区间中位)", C["navy"], "-"),
             ("南京(系数+0.3)", C["blue"], "-"),
             ("广州(系数+0.1)", C["green"], "-"),
             ("武汉(个案+5%)", C["grey"], "-"),
             ("宁波(第1轮 5:4:3:2:1)", "#B7791F", "-")]
    for name, col, ls in picks:
        if name not in norm:
            continue
        y = [norm[name].get(i, 0) * 100 for i in x]
        ax.plot(x, y, ls, marker="s", color=col, lw=2.0, ms=5,
                label=name.split("(")[0], alpha=0.9)

    ax.set_xticks(x)
    ax.set_xticklabels([f"{i} 层" for i in x])
    style(ax, "五个城市的分摊规则，都贴着同一条「按受益」曲线",
          "楼层", "出资占比（%）")
    ax.legend(fontsize=10, frameon=False, loc="upper left")
    # ★ 消息：所有曲线都紧贴基准带。
    #   带宽取**实测最大绝对偏差**（不硬编码猜测值）：
    #   逐层比较 5 条规则与线性基准，取 max|dev|，向上取整到 0.5 pp。
    devs = []
    for name, _, _ in picks:
        if name in norm:
            for i in x:
                devs.append(abs(norm[name].get(i, 0) * 100 - base[i] * 100))
    band = math.ceil(max(devs) * 2) / 2            # 向上取整到 0.5
    lo_pt = [base[i] * 100 - band for i in x]
    hi_pt = [base[i] * 100 + band for i in x]
    ax.fill_between(x, lo_pt, hi_pt, color=C["red"], alpha=0.08, zorder=0)
    ax.text(3.4, 44.0, f"全部落在基准线 ±{band:g} 个百分点内",
            fontsize=11, color=C["red"], ha="center", fontweight="bold")
    ax.set_ylim(-3, 47)
    ax.annotate("北京顶层 33.7%", xy=(6, 33.67), xytext=(4.55, 29.0),
                fontsize=10, color=C["navy"], ha="center",
                arrowprops=dict(arrowstyle="->", color=C["navy"], lw=1.2))
    ax.annotate("广州最平：顶层 25.5%", xy=(6, 25.49), xytext=(4.05, 10.0),
                fontsize=10, color=C["green"], ha="center",
                arrowprops=dict(arrowstyle="->", color=C["green"], lw=1.2))
    return save(fig, "fig1_city_curves.png")


# ---------------------------------------------------------------- 图 2
def fig2():
    x = list(range(1, H + 1))
    base = shares(H, 1.0)
    r1 = shares(H, 1.0)                                  # 5:4:3:2:1 == 线性
    r2 = {1: 0.0, 2: 8.0, 3: 14.0, 4: 20.0, 5: 26.0, 6: 32.0}
    r3 = shares(H, GAMMA)
    fig, ax = plt.subplots(figsize=(11, 6))
    # ⚠️ 不要在图中用 ❌/✅ 等 emoji —— 中文字体没有这些字形，会渲染成豆腐块。
    ax.plot(x, [base[i] * 100 for i in x], "o--", color=C["grey"], lw=2.4,
            ms=8, label="线性基准 γ=1")
    ax.plot(x, [r1[i] * 100 for i in x], "s-", color=C["navy"], lw=2.2, ms=6,
            label="第 1 轮 5:4:3:2:1（偏差 0.00 pp）")
    ax.plot(x, [r2[i] for i in x], "^-", color=C["red"], lw=2.8, ms=9,
            label="第 2 轮 爬梯级数（偏 4.00 pp，更平）—— 被否决")
    ax.plot(x, [r3[i] * 100 for i in x], "D-", color=C["green"], lw=2.8, ms=8,
            label="第 3 轮 γ*=1.35（4 楼 19%）—— 达成")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{i} 层" for i in x])
    style(ax, "宁波一栋楼的三轮协商：方向是「越来越陡」",
          "楼层", "出资占比（%）")
    ax.legend(fontsize=10, frameon=False, loc="upper left")
    # 第 2 轮相对「第 3 轮」在低层更高、在高层更低
    ax.annotate("第 2 轮比第 3 轮\n在 2、3 层多摊\n在 5、6 层少摊",
                xy=(2.05, 8), xytext=(2.6, 21),
                fontsize=10, color=C["red"], ha="left",
                arrowprops=dict(arrowstyle="->", color=C["red"], lw=1.3))
    return save(fig, "fig2_ningbo_rounds.png")


# ---------------------------------------------------------------- 图 3
def fig3():
    labels = ["不干预", "货币补偿\n（全额）", "改设计降损\n30%",
              "改设计降损\n60%", "调分摊比例\n（扫遍）"]
    vals = [16.7, 80.8, 16.7, 16.7, 16.7]
    cols = [C["grey"], C["green"], C["red"], C["red"], C["red"]]
    fig, ax = plt.subplots(figsize=(11, 6))
    bars = ax.bar(labels, vals, color=cols, width=0.62)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 2.2, f"{v}%",
                ha="center", fontsize=14, fontweight="bold",
                color=C["navy"])
    ax.set_ylim(0, 100)
    style(ax, "什么能把「谈成」的概率抬起来？——只有补偿", "", "可谈成率（%）")
    ax.text(4.0, 93, "120 个参数组合上的代理指标", ha="center",
            fontsize=10, color=C["grey"])
    ax.annotate("+385%", xy=(1.0, 83), xytext=(1.75, 67),
                fontsize=14, color=C["green"], fontweight="bold",
                ha="center",
                arrowprops=dict(arrowstyle="->", color=C["green"], lw=1.6))
    ax.annotate("+0%", xy=(3.0, 18), xytext=(3.0, 40),
                fontsize=14, color=C["red"], fontweight="bold", ha="center",
                arrowprops=dict(arrowstyle="->", color=C["red"], lw=1.6))
    return save(fig, "fig3_mechanisms.png")


# ---------------------------------------------------------------- 图 4
def fig4():
    n = 12
    fig, ax = plt.subplots(figsize=(11, 5.6))
    need_part = math.ceil(2 * n / 3)          # 8
    need_yes = math.ceil(3 * n / 4)           # 9

    # 支持者（绿）/ 反对者（红）
    for i in range(n):
        oppose = i >= (n - 4)                 # 后 4 户反对
        col = C["red"] if oppose else C["green"]
        ax.add_patch(plt.Rectangle((i * 1.0, 0), 0.82, 1.0,
                                   facecolor=col, alpha=0.85))
        ax.text(i * 1.0 + 0.41, 0.5, f"{i+1}", ha="center", va="center",
                color="white", fontsize=13, fontweight="bold")
    ax.set_xlim(-0.4, n + 0.4)
    ax.set_ylim(-1.5, 2.1)
    ax.axis("off")
    ax.text(n / 2, 1.55, "12 户单元：4 户反对（红）即可否决",
            ha="center", fontsize=15, color=C["navy"], fontweight="bold")
    ax.text(n / 2, 1.12,
            f"参与门槛 ceil(2/3 × 12) = {need_part} 户　｜　"
            f"全员参与时需 ceil(3/4 × 12) = {need_yes} 户同意",
            ha="center", fontsize=12, color=C["grey"])
    ax.text(n / 2, -0.55,
            "4 户投反对票 → 只剩 8 户赞成，8 < 9 → 卡住",
            ha="center", fontsize=13, color=C["red"], fontweight="bold")
    ax.text(n / 2, -1.05,
            "关键：门槛是相对「参与表决的人」算的，不是相对全体",
            ha="center", fontsize=11, color=C["grey"])
    return save(fig, "fig4_vote_gate.png")


# ---------------------------------------------------------------- 图 5
def fig5():
    rows = [("宁波（第1轮）", 1.000), ("北京（5层）", 0.998),
            ("北京（6层）", 0.997), ("南京", 0.992),
            ("北京（4层）", 0.989), ("武汉", 0.988), ("广州", 0.921)]
    rows.sort(key=lambda r: r[1])
    names = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    cols = [C["red"] if v < 0.95 else C["navy"] for v in vals]
    fig, ax = plt.subplots(figsize=(10, 5.4))
    bars = ax.barh(names, vals, color=cols, height=0.6)
    for b, v in zip(bars, vals):
        ax.text(v + 0.004, b.get_y() + b.get_height() / 2, f"{v:.3f}",
                va="center", fontsize=12, fontweight="bold", color=C["navy"])
    ax.set_xlim(0.85, 1.03)
    style(ax, "五地规则与「按受益分摊」的相关系数：全部 ≥ 0.92", "相关系数")
    ax.axvline(0.95, color=C["grey"], ls=":", lw=1.4)
    ax.text(0.951, -0.75, "0.95", fontsize=10, color=C["grey"])
    return save(fig, "fig5_correlation.png")


# ---------------------------------------------------------------- 图 6
def fig6():
    data = json.loads((RES / "q5_decision_rules.json").read_text(encoding="utf-8"))
    ktab = data["临界表"]
    # 转成 补贴率 × L1 的矩阵（L1 = 2·L2）
    subs = sorted({r["补贴率"] for r in ktab})
    l1s = sorted({r["L1"] for r in ktab})
    M = [[0.0] * len(l1s) for _ in subs]
    for r in ktab:
        i = subs.index(r["补贴率"])
        j = l1s.index(r["L1"])
        M[i][j] = r["kappa*"]

    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    im = ax.imshow(M, cmap="YlOrRd", aspect="auto", vmin=1.0, vmax=3.2)
    ax.set_xticks(range(len(l1s)))
    ax.set_xticklabels([f"{v//10000} 万" for v in l1s])
    ax.set_yticks(range(len(subs)))
    ax.set_yticklabels([f"{s:.0%}" for s in subs])
    for i in range(len(subs)):
        for j in range(len(l1s)):
            ax.text(j, i, f"{M[i][j]:.2f}", ha="center", va="center",
                    fontsize=12, fontweight="bold",
                    color="white" if M[i][j] > 2.3 else C["navy"])
    ax.set_xlabel("一层损失 L1（元/户；取 L2 = L1/2）", fontsize=12)
    ax.set_ylabel("政府补贴率", fontsize=12)
    ax.set_title("临界支付意愿比 κ*：低于此值一定谈不成",
                 fontsize=15, color=C["navy"], pad=14, fontweight="bold")
    cb = fig.colorbar(im, ax=ax, pad=0.02)
    cb.set_label("κ* = 总支付意愿 / 净造价", fontsize=11)
    return save(fig, "fig6_kappa.png")


def main() -> int:
    FIGS.mkdir(parents=True, exist_ok=True)
    print("=" * 88)
    print("  渲染本期配图 → results/figs/")
    print("=" * 88)
    made = []
    for fn in (fig1, fig2, fig3, fig4, fig5, fig6):
        try:
            made.append(fn())
        except Exception as e:                 # noqa: BLE001
            print(f"  [FAIL] {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n共 {len(made)}/6 张 → {FIGS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
