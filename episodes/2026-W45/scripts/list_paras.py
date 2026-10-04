#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""列出讲稿的**段落编号**，用于手工设计分屏边界。

为什么要看这个：分屏表用 `paras: [起, 止)` 指向讲稿段落。
**均匀分组（每屏 4 段）会得到 8 个"过短"屏** —— 必须按语义手工切。
本脚本把带编号的段落打出来，便于直接圈定区间。

用法：
    $PY list_paras.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
SPEED = 4.77

p = EP / "内容" / "讲稿.md"
lines = p.read_text(encoding="utf-8").splitlines()
sec = 0
paras: list[tuple[int, str]] = []
for ln in lines:
    s = ln.strip()
    if s.startswith("## "):
        sec += 1
        continue
    if not s or s.startswith("#") or s.startswith(">"):
        continue
    # ⚠️ 跳过 Markdown 分隔线（`---` / `***` / `___`）—— 它们不是口播内容，
    #    若计入段号，分屏表的 `paras` 区间就会整体错位。
    if s in ("---", "***", "___") or set(s) <= {"-", "*", "_"}:
        continue
    paras.append((sec, s))

print(f"{'段':>3}{'节':>3}{'字':>5}  内容")
for i, (s, t) in enumerate(paras):
    print(f"{i:>3}{s:>3}{len(t):>5}  {t[:66]}")
print(f"\n共 {len(paras)} 段，总 {sum(len(t) for _, t in paras)} 字，"
      f"{sum(len(t) for _, t in paras)/SPEED/60:.2f} 分钟")
