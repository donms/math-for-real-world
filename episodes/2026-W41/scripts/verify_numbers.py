#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""核对论文里的关键数字能否在 results/ 找到出处。

## 为什么需要

skill 硬规矩：**每个数字都要能溯源** —— 论文里的数字必须能在
`results/` 找到落盘出处。手写论文时最容易出现"数字抄错"或
"改了模型忘了改论文"，而这个错误**不会报错**，只会让结论失真。

本脚本列出一组**关键数字**，逐个到 results/*.json 里查找，
报告命中/未命中。未命中不等于错（可能来自参数集或文献），
但必须人工确认。

用法：
    $PY verify_numbers.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
PAPER = ROOT / "paper" / "论文.md"

# 论文中的关键数字 → 期望的落盘出处（子串匹配）
KEY = [
    ("1.0098", "q1_bottleneck.json", "每闸次载货中位"),
    ("3.35", "q1_bottleneck.json", "年能力上界"),
    ("2.72", "q1_bottleneck.json", "年能力保守"),
    ("2.24", "q0_params.json", "2025 实际"),
    ("66.7", "q1_bottleneck.json", "利用率上界"),
    ("82.3", "q1_bottleneck.json", "利用率保守"),
    ("-0.461", "q1_bottleneck.json", "装载率与流量相关"),
    ("0.078", "q1_bottleneck.json", "排除检修后相关"),
    ("-0.605", "q1_bottleneck.json", "闸次与待闸相关"),
    ("0.59", "q2_diversion.json", "等待时间均值"),
    ("22.37", "q2_diversion.json", "口径B反推"),
    ("16.8", "q2_diversion.json", "口径A低值"),
    ("44.8", "q2_diversion.json", "口径A高值"),
    ("31.80", "q2_diversion.json", "成本差"),
    ("53.6", "q2_diversion.json", "加权平均分流率"),
    ("2.281", "q3_locks.json", "通道年能力"),
    ("21.2", "q3_locks.json", "临界等待天数"),
    ("52.5", "q3_locks.json", "新通道利用率"),
    ("18000", "q3_locks.json", "单闸次通过量"),
    ("40", "q4_sensitivity.json", "转换摩擦临界值"),
]


def load_all() -> dict:
    out = {}
    for p in RES.glob("*.json"):
        out[p.name] = p.read_text(encoding="utf-8")
    return out


def main() -> int:
    files = load_all()
    print(f"  results/ 共 {len(files)} 个 json")
    print(f"  论文 {PAPER.name}："
          f"{'存在' if PAPER.exists() else '❌ 缺失'}\n")
    paper = PAPER.read_text(encoding="utf-8") if PAPER.exists() else ""

    print(f"  {'数字':<10}{'期望出处':<26}{'在论文中':>9}{'在结果中':>9}  说明")
    print("  " + "-" * 78)
    miss_paper, miss_res = 0, 0
    for num, src, desc in KEY:
        in_paper = num in paper
        in_res = num in files.get(src, "")
        if not in_paper:
            miss_paper += 1
        if not in_res:
            miss_res += 1
        flag_p = "✅" if in_paper else "—"
        flag_r = "✅" if in_res else "⚠️"
        print(f"  {num:<10}{src:<26}{flag_p:>9}{flag_r:>9}  {desc}")

    print()
    print(f"  论文中未出现：{miss_paper} 个（可能表述不同，需人工确认）")
    print(f"  期望出处未命中：{miss_res} 个（可能来自参数集/文献，需确认）")

    # 论文与解读的结构检查
    print(f"\n  结构检查：")
    for f, name in ((PAPER, "论文"), (ROOT / "paper" / "论文解读.md", "解读"),
                    (ROOT / "paper" / "结论速览.md", "结论速览")):
        if not f.exists():
            print(f"    ❌ {name} 缺失")
            continue
        t = f.read_text(encoding="utf-8")
        h2 = len(re.findall(r"^## ", t, re.M))
        n = len(re.sub(r"\s", "", t))
        print(f"    {name:<6} {n:>6} 字  {h2:>2} 个一级小节")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
