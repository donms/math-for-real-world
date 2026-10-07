#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W48 · 摸清讲稿里的"数字写法"现状（改单向转换前必做）。

## 背景：为什么要改单向

现状是**双向**的：

* `clean_caption(讲稿) -> 字幕`：汉字数词 -> 阿拉伯
* `to_tts(字幕) -> 口播`：阿拉伯 -> 汉字

**双向必然打架**：`一小部分` 里的"一"会被当成计数转成 `1`，
而 `ChR2` 里的 `2` 又会被"还原"规则改成 `两`。

**⇒ 改成单向**：讲稿**直接按字幕想显示的样子写**，
只保留 `to_tts`（阿拉伯 -> 汉字）一个方向。

## 本脚本要查清

1. 讲稿里**汉字数词**出现在哪（这些需要改写为阿拉伯）；
2. 讲稿里**已经是阿拉伯**的（这些不用动）；
3. 哪些汉字数词是**词汇化**的（`一小部分`/`第一`），**不该动**。

用法：
    $PY audit_script_numerals.py
"""
from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NARR = ROOT / "episodes" / "2026-W48" / "内容" / "讲稿.md"

# 词汇化的数词：**绝不改写**
FROZEN = (
    "一起", "一直", "一定", "一般", "一样", "一切", "一致", "一半",
    "一边", "一旦", "一面", "一并", "一同", "一向", "一味",
    "第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八",
    "第九", "第十", "这一", "那一", "哪一", "一次", "一条", "一种",
    "一小部分", "一部分", "一篇", "一屏", "一头", "一度", "一步",
    "两三个", "两件事", "两条", "两种", "两个", "两万",
)

CN_NUM = "零一二两三四五六七八九十百千万亿"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=40)
    args = ap.parse_args()

    s = NARR.read_text(encoding="utf-8")
    # 只取「口播」块的正文
    blocks = re.findall(r"\*\*口播\*\*\s*\n+(.*?)(?=\n\*\*|\n##|\Z)", s, re.S)
    txt = " ".join(blocks)
    print("=" * 84)
    print("  W48 讲稿数字写法现状")
    print("=" * 84)
    print(f"  口播正文 {len(txt)} 字（{len(blocks)} 屏）")

    # ① 已经是阿拉伯的
    ar = re.findall(r"[0-9]+(?:\.[0-9]+)?", txt)
    print(f"\n  ── 已是阿拉伯数字 {len(ar)} 处（不用动）──")
    print("     " + " ".join(sorted(set(ar), key=lambda x: (len(x), x))[:30]))

    # ② 汉字数词（候选改写）
    print("\n  ── 汉字数词出现的搭配（需判断是否该改写）──")
    c: Counter = Counter()
    for m in re.finditer(f"[{CN_NUM}]+", txt):
        w = m.group(0)
        a = max(0, m.start() - 4)
        b = min(len(txt), m.end() + 4)
        c[txt[a:b].replace("\n", "")] += 1
    for ctx, n in c.most_common(args.show):
        # 标出是否命中冻结表
        frozen = any(f in ctx for f in FROZEN)
        tag = "  [冻结]" if frozen else ""
        print(f"     x{n}  ...{ctx}...{tag}")

    # ③ 冻结表命中统计
    hit = sum(1 for f in FROZEN if f in txt)
    print(f"\n  ── 冻结词命中 {hit} / {len(FROZEN)} ──")
    print("     这些**不改写**（词汇化数词）")
    print("\n  ── 结论 ──")
    print("     改写目标是第 ② 类里**未命中冻结表**的搭配。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
