#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W54 · 工具：**定位**源码里"字符串未闭合"的真凶（只报告，不改）。

## 为什么不能用"引号两侧是不是中文"来判

我写过一个自动修器（`fix_cjk_quotes2.py`），它把
`r["收缴率"]` 里的引号也当成了"中文引号" ⇒ **破坏了合法的字典索引**。

**⇒ 判据必须是"语法层面的"**：逐行去掉注释与字符串后，
看 **ASCII 引号是否为偶数**；或者更直接 ——
**用 `ast` 报的 `lineno` 逐行看**。

## 本脚本的判据（三条，互补）

| # | 判据 | 抓什么 |
|---|---|---|
| **1** | 整文件 `ast.parse` 失败 ⇒ 输出 `SyntaxError.lineno` 上下文 | 主线索 |
| **2** | 逐行统计 **ASCII 双引号个数为奇数**（跳过纯注释行）| 未闭合的 f-string |
| **3** | 逐行找出"**ASCII 引号两侧都是中文**"的位置 | 中文里误打的英文引号 |

**⇒ 三者取并集输出，人工按行改**（最稳的改法：**把外层引号换成 `'`**）。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path


def cjk(c: str) -> bool:
    o = ord(c)
    return (0x4E00 <= o <= 0x9FFF or 0x3000 <= o <= 0x303F
            or 0xFF00 <= o <= 0xFFEF or 0x2018 <= o <= 0x201F
            or o in (0x2014, 0x2026))


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("用法: find_unclosed_strings.py <文件...>")
        return 2
    for a in args:
        p = Path(a)
        src = p.read_text(encoding="utf-8")
        print("=" * 88)
        print(f"  {p.name}")
        print("=" * 88)

        # 判据 1：ast 的 lineno
        try:
            ast.parse(src)
            print("  [i] ast.parse 通过 ⇒ 无需修")
            continue
        except SyntaxError as e:
            print(f"  [判据1] ast.parse 失败：L{e.lineno}  {e.msg}")
            L = src.split("\n")
            for i in range(max(0, e.lineno - 3), min(len(L), e.lineno + 2)):
                mark = ">>>" if i == e.lineno - 1 else "   "
                print(f"     {mark} L{i+1}: {L[i].rstrip()[:100]}")

        # 判据 2 / 3
        print("\n  [判据2] ASCII 双引号为奇数的行：")
        print("  [判据3] ASCII 引号两侧都是中文的位置：")
        n2 = n3 = 0
        for i, ln in enumerate(src.split("\n"), 1):
            if ln.lstrip().startswith("#"):
                continue
            k = ln.count('"')
            if k % 2 == 1:
                n2 += 1
                print(f"     L{i}（{k} 个）: {ln.strip()[:96]}")
            for j in range(1, len(ln) - 1):
                if ln[j] == '"' and cjk(ln[j - 1]) and cjk(ln[j + 1]):
                    n3 += 1
                    print(f"     L{i} 第 {j+1} 列: …{ln[max(0,j-16):j+16]}…")
        if n2 == 0:
            print("     （无）")
        if n3 == 0:
            print("     （无）")
        print(f"\n  ⇒ 判据2 命中 {n2} 行；判据3 命中 {n3} 处")
        print("  ★ 最稳的修法：**把外层引号换成 '**（Python 允许），"
              "内层中文引号不动")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
