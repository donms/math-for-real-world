#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""Q1 求解：CPI 加权贡献度分解。

模型：$c_i = w_i r_i / 100$，$\sum_i c_i = R$

关键数据
--------
统计局 2026-02-11 **首次公布** 2025 年基期 CPI 八大类权数（合计 100.0%）。
因此本问可以直接用官方权数做精确分解，无需代理变量。

用法
----
    $env:PYTHONUTF8=1
    $PY = "python"
    $PY episodes\\2026-W38\\scripts\\q1_solve.py [--month 2026-08]

产出
----
    results/q1_contribution.csv     分项贡献度分解表
    results/q1_panel.csv            2026-02…2026-08 贡献度面板
    results/q1_result.txt           结论摘要
    results/q1_crosscheck.txt       与官方影响值的交叉验证
    results/figs/q1_waterfall.png   贡献度瀑布图
    results/figs/q1_rank.png        贡献度 vs 涨跌幅 对比图（揭示"涨得多≠影响大"）
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

EP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EP.parent.parent / "scripts"))
from common import C, STYLE, banner, polish, savefig, setup_cn_font, write_text  # noqa: E402

CLEAN = EP / "data" / "clean"
RES = EP / "results"
FIGS = RES / "figs"

# ---------------------------------------------------------------- 官方数据
# 国家统计局 2026-02-11 首次公布：2025 年基期 CPI 八大类权数（%），合计 100.0
WEIGHTS = {
    "一、食品烟酒及在外餐饮": 29.5,
    "二、衣着": 5.4,
    "三、居住": 22.1,
    "四、生活用品及服务": 5.5,
    "五、交通通信": 14.3,
    "六、教育文化娱乐": 11.4,
    "七、医疗保健": 8.9,
    "八、其他用品及服务": 2.9,
}
SHORT = {
    "一、食品烟酒及在外餐饮": "食品烟酒及在外餐饮",
    "二、衣着": "衣着",
    "三、居住": "居住",
    "四、生活用品及服务": "生活用品及服务",
    "五、交通通信": "交通通信",
    "六、教育文化娱乐": "教育文化娱乐",
    "七、医疗保健": "医疗保健",
    "八、其他用品及服务": "其他用品及服务",
}

# 2026-08 发布稿正文中明确给出的"影响（百分点）"——用于交叉验证
OFFICIAL_IMPACT = {
    "畜肉类": (-0.21, -5.1),
    "鲜菜": (-0.05, -2.8),
    "蛋类": (+0.07, +15.0),
    "奶类": (-0.01, -1.4),
    "水产品": (-0.01, -0.6),
    "一、食品烟酒及在外餐饮": (-0.21, -0.7),
}
HEADLINE = 0.8


def read_wide(name: str) -> tuple[list[str], dict[str, dict[str, float]]]:
    """读宽表 → (月份列表, {period: {item: value}})。"""
    p = CLEAN / name
    if not p.exists():
        raise SystemExit(f"[!] 缺少 {p}，先跑 clean_data.py")
    with p.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    months = [r["period"] for r in rows]
    data: dict[str, dict[str, float]] = {}
    for r in rows:
        per = r.pop("period")
        r.pop("regime", None)
        data[per] = {k: (float(v) if v not in ("", None) else None) for k, v in r.items()}
    return months, data


def decompose(month: str, yoy: dict[str, float]) -> list[dict]:
    """对给定月份做八大类贡献度分解。"""
    out = []
    for item, w in WEIGHTS.items():
        r = yoy.get(item)
        if r is None:
            continue
        c = w / 100.0 * r
        out.append({"类别": SHORT[item], "权数%": w, "同比%": r,
                    "贡献pp": round(c, 4),
                    "类型": "推高" if c > 0 else "拖累"})
    out.sort(key=lambda x: -x["贡献pp"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Q1 CPI 贡献度分解")
    ap.add_argument("--month", default="2026-08")
    args = ap.parse_args()

    banner(f"Q1 求解 · CPI 加权贡献度分解 · {args.month}")
    months, yoy_all = read_wide("cpi_wide_yoy.csv")
    if args.month not in yoy_all:
        raise SystemExit(f"[!] 数据里没有 {args.month}")
    yoy = yoy_all[args.month]
    RES.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)

    rows = decompose(args.month, yoy)
    total_w = sum(r["权数%"] for r in rows)
    total_c = sum(r["贡献pp"] for r in rows)

    # ---------- 落盘 ----------
    with (RES / "q1_contribution.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["类别", "权数%", "同比%", "贡献pp", "类型"])
        w.writeheader()
        w.writerows(rows)
    print(f"[csv ] results/q1_contribution.csv")

    # ---------- 多期面板 ----------
    sub_months = [m for m in months if m >= "2026-02"]
    panel = [["period", "item", "weight", "yoy", "contrib_pp"]]
    for m in sub_months:
        for it, ww in WEIGHTS.items():
            r = yoy_all[m].get(it)
            if r is None:
                continue
            panel.append([m, SHORT[it], ww, r, round(ww / 100 * r, 4)])
    with (RES / "q1_panel.csv").open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(panel)
    print(f"[csv ] results/q1_panel.csv（{len(sub_months)} 个月）")

    # ---------- 交叉验证：反推权数 vs 官方公布权数 ----------
    lines = ["Q1 交叉验证：用发布稿‘影响（百分点）’反推权数，与官方公布权数比对",
             "=" * 74, "",
             f"{'指标':<24}{'官方影响':>10}{'同比%':>9}{'反推权数%':>12}{'公布权数%':>12}{'一致':>8}",
             "-" * 74]
    for name, (imp, r) in OFFICIAL_IMPACT.items():
        implied = imp / r * 100 if r else float("nan")
        pub = WEIGHTS.get(name)
        pub_s = f"{pub:.1f}" if pub else "—"
        ok = ""
        if pub:
            ok = "✅" if abs(implied - pub) / pub < 0.35 else "⚠️"
        lines.append(f"{name:<24}{imp:>10.2f}{r:>9.1f}{implied:>12.2f}{pub_s:>12}{ok:>8}")
    lines += ["",
              "判读：",
              "  · 对【聚合类别】（如食品烟酒及在外餐饮）反推值与公布值吻合良好。",
              "  · 对【细项】（鲜菜、蛋类、奶类）反推值偏离较大，原因是发布稿的影响值",
              "    为两位小数四舍五入后的结果，除以个位数涨跌幅会显著放大舍入误差",
              "    （如蛋类 0.07/15.0 → 0.47%，与常识量级不符）。",
              "  · 因此：**细项权数不能由影响值可靠反推**，聚合层面可以。",
              "  · 这也解释了为什么本文直接用官方公布的八大类权数做分解。"]
    write_text("\n".join(lines), RES / "q1_crosscheck.txt")

    # ---------- 结论摘要 ----------
    push = [r for r in rows if r["贡献pp"] > 0]
    drag = [r for r in rows if r["贡献pp"] < 0]
    biggest_yoy = max(rows, key=lambda x: x["同比%"])          # 涨幅最大
    top_push = max(rows, key=lambda x: x["贡献pp"])             # 贡献最大
    top_drag = min(rows, key=lambda x: x["贡献pp"])             # 拖累最大
    summary = [
        f"Q1 结论摘要 · {args.month}",
        "=" * 62,
        f"CPI 同比：官方公布 {HEADLINE}%   分解合计 {total_c:+.3f} pp   "
        f"残差 {HEADLINE - total_c:+.4f} pp（四舍五入）",
        f"权数合计：{total_w:.1f}%",
        "",
        "【推高项】按贡献排序",
    ]
    for i, r in enumerate(push, 1):
        summary.append(f"  {i}. {r['类别']:<18} 权数 {r['权数%']:>5.1f}%  "
                       f"同比 {r['同比%']:>+6.1f}%  →  贡献 {r['贡献pp']:>+7.3f} pp")
    summary += ["", "【拖累项】按拖累幅度排序"]
    for i, r in enumerate(drag, 1):
        summary.append(f"  {i}. {r['类别']:<18} 权数 {r['权数%']:>5.1f}%  "
                       f"同比 {r['同比%']:>+6.1f}%  →  贡献 {r['贡献pp']:>+7.3f} pp")
    summary += ["",
                f"推高项合计 {sum(r['贡献pp'] for r in push):+.3f} pp；"
                f"拖累项合计 {sum(r['贡献pp'] for r in drag):+.3f} pp",
                "",
                "【核心洞察】涨得多 ≠ 影响大：",
                f"  · 涨幅最大的是 {biggest_yoy['类别']}"
                f"（{biggest_yoy['同比%']:+.1f}%），"
                f"但只贡献 {biggest_yoy['贡献pp']:+.3f} pp；",
                f"  · 第一推高项是 {top_push['类别']}（贡献 {top_push['贡献pp']:+.3f} pp，"
                f"占总涨幅约 {top_push['贡献pp'] / total_c * 100:.0f}%）；",
                f"  · 最大拖累项是 {top_drag['类别']}（{top_drag['贡献pp']:+.3f} pp），"
                f"其权数高达 {top_drag['权数%']:.1f}%。",
                ]
    write_text("\n".join(summary), RES / "q1_result.txt")
    print("\n".join(summary))

    # ---------- 图表 ----------
    make_figs(rows, args.month, total_c)
    make_trend_fig(months, yoy_all)
    return 0


def make_trend_fig(months: list[str], yoy_all: dict[str, dict[str, float]],
                   standalone: bool = True) -> None:
    r"""CPI 同比 28 个月走势（标出基期轮换断点与各月数值）。

    standalone=True  → 自带标题（论文插图用）
    standalone=False → 不画标题/来源（供"16:9 面板"复用，面板已有标题条）
    """
    if not setup_cn_font():
        return
    import matplotlib.pyplot as plt
    import numpy as np

    ms = list(months)
    vals = [yoy_all[m].get("居民消费价格") for m in ms]
    if all(v is None for v in vals):
        print("[!] 走势图：无 CPI 数据，跳过")
        return
    x = np.arange(len(ms))
    vals_f = [float("nan") if v is None else v for v in vals]
    arr = np.array(vals_f, dtype=float)
    lo_v = float(np.nanmin(arr)) if np.isfinite(arr).any() else -1.0

    fig, ax = plt.subplots(figsize=(12.5, 5.6))
    # 断点前后用不同颜色，直观体现"基期轮换，序列不可直接拼接"
    bi = ms.index("2026-01") if "2026-01" in ms else None
    if bi is not None:
        ax.plot(x[:bi + 1], vals_f[:bi + 1], color=C["blue"], lw=2.6, marker="o",
                ms=5, label="2020 年基期")
        ax.plot(x[bi:], vals_f[bi:], color=C["navy"], lw=2.6, marker="o",
                ms=5, label="2025 年基期（2026-01 起）")
        ax.axvline(bi - 0.5, color=C["green"], ls=":", lw=2.2)
        # 标注放在左下空白区，避免与曲线/标题重叠
        ax.annotate("基期轮换：跨 2026-01 的序列不可直接拼接",
                    xy=(bi - 0.5, lo_v * 0.72), xytext=(max(1.0, bi - 11.5), lo_v * 0.90),
                    fontsize=11, color=C["green"],
                    arrowprops=dict(arrowstyle="->", color=C["green"], lw=1.6))
    else:
        ax.plot(x, vals_f, color=C["navy"], lw=2.6, marker="o", ms=5, label="CPI 同比")

    # 标注最高/最低点（峰值标签放在点下方，避免顶到标题）
    if np.isfinite(arr).any():
        hi = int(np.nanargmax(arr)); lo = int(np.nanargmin(arr))
        ax.annotate(f"最高 {arr[hi]:+.1f}%", xy=(hi, arr[hi]),
                    xytext=(hi, arr[hi] - 0.30), fontsize=11.5,
                    color=C["red"], fontweight="bold", ha="center",
                    arrowprops=dict(arrowstyle="->", color=C["red"], lw=1.3))
        ax.annotate(f"最低 {arr[lo]:+.1f}%", xy=(lo, arr[lo]),
                    xytext=(lo + 1.2, arr[lo] - 0.22), fontsize=11.5,
                    color=C["grey"], fontweight="bold", ha="left",
                    arrowprops=dict(arrowstyle="->", color=C["grey"], lw=1.3))
    ax.axhline(0, color=C["grey"], ls="--", lw=1.2)
    # 8 月数值单独强调
    if ms[-1] == "2026-08":
        ax.annotate(f"8月 {arr[-1]:+.1f}%", xy=(len(ms) - 1, arr[-1]),
                    xytext=(len(ms) - 3.4, arr[-1] + 0.30), fontsize=12.5,
                    color=C["red"], fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color=C["red"], lw=1.6))
    ax.set_xticks(x[::2])
    ax.set_xticklabels([ms[i] for i in range(0, len(ms), 2)], rotation=45,
                       ha="right", fontsize=9.5)
    ax.set_ylim(lo_v - 0.30, float(np.nanmax(arr)) + 0.55)
    title = (f"CPI 同比走势：{ms[0]} — {ms[-1]}（共 {len(ms)} 个月）"
             if standalone else "")
    polish(ax, "", "CPI 同比（%）", title)
    savefig(fig, FIGS / "ppl_trend.png")
    plt.close(fig)


def make_figs(rows: list[dict], month: str, total_c: float) -> None:
    if not setup_cn_font():
        print("[!] 中文字体不可用，跳过绘图")
        return
    import matplotlib.pyplot as plt
    import numpy as np

    labels = [r["类别"] for r in rows]
    contrib = [r["贡献pp"] for r in rows]

    # --- 瀑布图 ---
    fig, ax = plt.subplots(figsize=(11, 5.6))
    order = sorted(rows, key=lambda x: x["贡献pp"])       # 负 → 正
    start = 0.0
    for i, r in enumerate(order):
        c = r["贡献pp"]
        col = C["red"] if c < 0 else C["blue"]
        ax.bar(i, c, bottom=start, color=col, width=0.62,
               edgecolor="white", linewidth=0.8)
        va = "bottom" if c > 0 else "top"
        off = 0.012 if c > 0 else -0.012
        ax.text(i, start + c + off, f"{c:+.3f}", ha="center", va=va,
                fontsize=9.5, color=C["navy"], fontweight="bold")
        start += c
    ax.bar(len(order), total_c, color=C["navy"], width=0.62)
    ax.text(len(order), total_c + 0.012, f"{total_c:+.3f}", ha="center",
            va="bottom", fontsize=10.5, color=C["navy"], fontweight="bold")
    ax.axhline(0, color=C["grey"], lw=1.0)
    ax.axhline(0.8, color=C["green"], ls="--", lw=1.4)
    ax.text(len(order) - 0.1, 0.813, "官方公布 0.800%", ha="right",
            fontsize=10, color=C["green"])
    ax.set_xticks(range(len(order) + 1))
    ax.set_xticklabels([r["类别"] for r in order] + ["合计"], rotation=22, ha="right",
                       fontsize=10)
    polish(ax, "", "对 CPI 的贡献（百分点）",
           f"{month} CPI 贡献度瀑布图：谁在推高、谁在拖累", legend=False)
    savefig(fig, FIGS / "q1_waterfall.png")
    plt.close(fig)

    # --- 涨跌幅 vs 贡献度（揭示"涨得多≠影响大"）---
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
    order2 = sorted(rows, key=lambda x: -x["同比%"])
    y = np.arange(len(order2))
    axes[0].barh(y, [r["同比%"] for r in order2], color=C["blue"], height=0.6)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels([r["类别"] for r in order2], fontsize=10)
    axes[0].invert_yaxis()
    polish(axes[0], "同比涨跌幅（%）", "", "① 谁涨得多？", legend=False)
    for i, r in enumerate(order2):
        axes[0].text(r["同比%"] + (0.15 if r["同比%"] >= 0 else -0.15), i,
                     f"{r['同比%']:+.1f}%", va="center",
                     ha="left" if r["同比%"] >= 0 else "right", fontsize=9.5)

    order3 = sorted(rows, key=lambda x: -x["贡献pp"])
    y3 = np.arange(len(order3))
    cols = [C["red"] if r["贡献pp"] < 0 else C["navy"] for r in order3]
    axes[1].barh(y3, [r["贡献pp"] for r in order3], color=cols, height=0.6)
    axes[1].set_yticks(y3)
    axes[1].set_yticklabels([r["类别"] for r in order3], fontsize=10)
    axes[1].invert_yaxis()
    axes[1].axvline(0, color=C["grey"], lw=1.0)
    polish(axes[1], "对 CPI 的贡献（百分点）", "", "② 谁影响大？", legend=False)
    for i, r in enumerate(order3):
        axes[1].text(r["贡献pp"] + (0.012 if r["贡献pp"] >= 0 else -0.012), i,
                     f"{r['贡献pp']:+.3f}", va="center",
                     ha="left" if r["贡献pp"] >= 0 else "right", fontsize=9.5)

    fig.suptitle("涨得多 ≠ 影响大：涨跌幅排名与贡献度排名完全不同",
                 fontsize=14, color=C["navy"], y=1.02)
    savefig(fig, FIGS / "q1_rank.png")
    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
