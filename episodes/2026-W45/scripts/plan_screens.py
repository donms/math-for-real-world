#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W45 · 计算分屏边界建议（供 `make_storyboard.py` 的 `SCREEN_BOUNDS` 定稿）。

## 为什么要算而不是拍

W44 的教训：**屏是按段区间切的、版式是按叙事节拍设计的，两套切法天生不对齐**。
⇒ 正确做法是**按版式/叙事单元设计分屏**，即先看清"每个自然单元在哪几段"，
   再定边界。本脚本把节边界、段长、累积字数一次打印出来，
   让边界定在**语义单元**上（而不是凑字数）。

用法：
    $PY plan_screens.py
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
MD = ROOT / "内容" / "讲稿.md"


def load():
    lines = MD.read_text(encoding="utf-8").splitlines()
    sec, out = 0, []
    for ln in lines:
        s = ln.strip()
        if s.startswith("## "):
            sec += 1
            continue
        if not s or s.startswith("#") or s.startswith(">"):
            continue
        if s in ("---", "***", "___") or set(s) <= {"-", "*", "_"}:
            continue
        out.append((sec, s))
    return out


def main() -> int:
    paras = load()
    n = len(paras)
    print("=" * 92)
    print(f"  W45 · 讲稿段表（共 {n} 段）")
    print("=" * 92)
    print(f"\n  {'段':>4}{'节':>4}{'字':>5}{'累计':>6}  文本")
    cum = 0
    for i, (sec, t) in enumerate(paras):
        cum += len(t)
        mark = ""
        if i + 1 < n and paras[i + 1][0] != sec:
            mark = "   <-- 节末"
        print(f"  {i:>4}{sec:>4}{len(t):>5}{cum:>6}  {t[:52]}{mark}")

    # 节汇总
    print(f"\n  ── 分节汇总 ──")
    from collections import defaultdict
    secs = defaultdict(list)
    for i, (sec, t) in enumerate(paras):
        secs[sec].append((i, len(t)))
    print(f"  {'节':>4}{'段区间':>12}{'段数':>6}{'字数':>7}")
    for sec in sorted(secs):
        items = secs[sec]
        lo, hi = items[0][0], items[-1][0] + 1
        print(f"  {sec:>4}{f'{lo}-{hi}':>12}{hi-lo:>6}"
              f"{sum(c for _, c in items):>7}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
