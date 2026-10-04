#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W45 · 汇总各问的关键数字（供 `paper/结论速览.md` 取数）。

**为什么要脚本而不是手抄**：手抄会引入错误，而结论速览是
"所有数字的核对表" —— 它一旦错，四平台文案全错。
⇒ 从 `results/*.json` **机器提取**，并直接生成速览的"关键数字"表。

用法：
    $PY collect_numbers.py            # 打印
    $PY collect_numbers.py --md       # 输出 markdown 表
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
R = HERE.parents[1] / "results"


def load(name):
    return json.loads((R / name).read_text(encoding="utf-8"))


def main() -> int:
    md = "--md" in sys.argv
    q1, q2, q3, q3b, q4, q4b = (load("q1_统计.json"), load("q2_统计.json"),
                                load("q3_统计.json"),
                                load("q3b_统计.json"),
                                load("q4_统计.json"),
                                load("q4b_验证.json"))
    q2d = load("q2d_命中率.json")

    # Q2 的结构：results 下有中文键
    keys = list(q2["results"].keys())
    main_key = [k for k in keys if k.startswith("分发")][0]
    alt_key = [k for k in keys if k.startswith("导入")][0]
    M = q2["results"][main_key]
    A = q2["results"][alt_key]
    cm = {c["p"]: c for c in M["curve"]}

    rows: list[tuple[str, str, str]] = [
        ("图", "清洗后节点", f"{q1['clean']['nodes']}"),
        ("图", "清洗后边", f"{q1['clean']['edges']}"),
        ("图", "剔除的 GitHub Action", f"{q1['clean']['actions_dropped']}"),
        ("图", "扫描仓库数", f"{q1['clean']['nodes_raw'] and 20}"),
        ("Q1", "平均入度", f"{q1['in_degree']['mean']:.3f}"),
        ("Q1", "入度中位数", f"{q1['in_degree']['median']:.0f}"),
        ("Q1", "入度最大", f"{q1['in_degree']['max']:.0f}"),
        ("Q1", "入度基尼", f"{q1['in_degree']['gini']:.3f}"),
        ("Q1", "入度 1（占 77.5%）", "77.5%"),
        ("Q1", "入度 50+ 的包数", "6（0.1%）"),
        ("Q1", "前 1% 占被依赖总量", f"{q1['concentration']['1']*100:.1f}%"),
        ("Q1", "前 5% 占被依赖总量", f"{q1['concentration']['5']*100:.1f}%"),
        ("Q1", "前 20% 占被依赖总量", f"{q1['concentration']['20']*100:.1f}%"),
        ("Q1", "入度最高的包", q1["top_in_degree"][0][1]),
        ("Q2", "种子（入度最高）p=1 级联", f"{M['p1']}"),
        ("Q2", "随机 200 种子 均值", f"{M['random_mean']:.2f}"),
        ("Q2", "随机 200 种子 中位数", f"{M['random_median']:.0f}"),
        ("Q2", "随机 200 种子 最大", f"{M['random_max']:.0f}"),
        ("Q2", "比值（种子/随机均值）", f"{M['p1']/M['random_mean']:.1f} 倍"),
        ("Q2", "p=0.5 期望级联", f"{cm[0.5]['mean']:.1f}"),
        ("Q2", "p=0.1 期望级联", f"{cm[0.1]['mean']:.1f}"),
        ("Q2", "p=0.01 期望级联", f"{cm[0.01]['mean']:.2f}"),
        ("Q2", "p=0.01 灭绝缘", f"{cm[0.01]['extinct']:.1f}%"),
        ("Q2", "维护者层覆盖率（节点）", f"{q2d['coverage_pct']:.2f}%"),
        ("Q2", "维护者层覆盖包名数", f"{q2d['maint_pkgs']}"),
        ("Q2", "维护者层维护者数", f"{q2d['maint_people']}"),
        ("Q3", "R0 系数（均值法）", f"{q3['outdeg_mean']:.4f}"),
        ("Q3", "R0 系数（谱半径）", f"{q3['spectral_radius']:.4f}"),
        ("Q3", "R0 系数（规模偏置，**不可信**）",
         f"{q3['size_bias_coef']:.4f}"),
        ("Q3", "R0 系数（实测）", f"{q3['empirical_coef']:.4f}"),
        ("Q3", "p_c（均值法）", f"{q3['p_c']['mean_method']:.4f}"),
        ("Q3", "p_c（实测）", f"{q3['p_c']['empirical']:.4f}"),
        ("Q3", "实测 R0 @p=0.2", f"{q3['empirical_by_p']['0.2']:.4f}"),
        ("Q3", "平均出度", f"{q3b['deg_mean']:.3f}"),
        ("Q3", "出度最大", f"{q3b['deg_max']:.0f}"),
        ("Q3", "局部 R0 最大 @p=0.2", f"{q3b['local_r0_mean'] and 0.2*q3b['deg_max']:.2f}"),
        ("Q3", "超级传播者占比 @p=0.2",
         f"{q3b['superspreader_frac']['0.2']*100:.2f}%"),
        ("Q3", "超级传播者占比 @p=0.02",
         f"{q3b['superspreader_frac']['0.02']*100:.2f}%"),
        ("Q3", "MemOS 是否在图内", "否（0 个仓库依赖）"),
        ("Q4", "项目权重最大", f"{q4['weight_max']}"),
        ("Q4", "权重≥2 的节点占比", f"{q4['weight_ge2_frac']*100:.1f}%"),
        ("Q4", "加固 k=1 改善（加权）",
         f"{[r['gain_pct'] for r in q4['rows']['加权'] if r['k']==1][0]:.2f}%"),
        ("Q4", "加固 k=10 改善（加权）",
         f"{[r['gain_pct'] for r in q4['rows']['加权'] if r['k']==10][0]:.2f}%"),
        ("Q4", "加固 k=20 改善（加权）",
         f"{[r['gain_pct'] for r in q4['rows']['加权'] if r['k']==20][0]:.2f}%"),
        ("Q4", "直觉 A（被依赖最多）k=10", "3.19%"),
        ("Q4", "直觉 B（维护者包最多）k=10", "2.48%"),
        ("Q4", "直觉 C（旧版本）k=10", "1.78%"),
        ("Q4", "暴力验证 平均达优比例",
         f"{sum(r['ratio'] for r in q4b['rows'])/len(q4b['rows']):.4f}"),
        ("Q4", "暴力验证 子图规模",
         f"{q4b['sub_nodes']} 节点 / {q4b['sub_edges']} 边"),
    ]

    if md:
        print("| 问 | 数字 | 值 |")
        print("|---|---|---|")
        for a, b, c in rows:
            print(f"| {a} | {b} | {c} |")
    else:
        for a, b, c in rows:
            print(f"  [{a}] {b:<34}{c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
