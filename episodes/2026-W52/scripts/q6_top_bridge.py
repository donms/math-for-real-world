#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W52 题 A · 深挖**最大的那一对桥梁**：它到底是什么？

## 为什么查这个

903 条跨科跨族边高度集中在少数族对上（Top-12 占 87%）。
**最大的那一对**是：

    Combinatorics/SumProduct  <->  Geometry/NilpotentCharts   263 条

**它是不是真桥梁？** 三种可能，含义完全不同：

| 可能 | 表现 | 对结论的影响 |
|---|---|---|
| **同一篇论文的两条腿** | 两边在 `preprints/` 里指向**同一篇** | 不算跨领域合作，**结论更强** |
| **两篇论文互相依赖** | 指向**两篇不同**论文 | 真桥梁 |
| **共享基础设施** | 被引模块名是 `Basic`/`Defs` | 不算 |

## 做法

1. 在 `CONTENTS.md`（377 个结果族）里**定位**这两个族；
2. 取出它们关联的**手稿链接**；
3. 判断是同一篇还是两篇不同；
4. 落在 `results/q6_最大桥梁.json`。

用法：
    $PY q6_top_bridge.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from net_resolve import open_url                                   # noqa: E402

OUT = ROOT / "episodes" / "2026-W52" / "results" / "q6_最大桥梁.json"

# 最大的一对（来自 q5）
PAIR = ("SumProduct", "NilpotentCharts")


def main() -> int:
    print("=" * 96)
    print("  W52 题 A · 最大桥梁解剖：SumProduct <-> NilpotentCharts")
    print("=" * 96)

    c = open_url("https://raw.githubusercontent.com/openai/math/main/"
                 "CONTENTS.md", timeout=180,
                 tries=3).read().decode("utf-8", "ignore")
    print(f"\n  CONTENTS.md {len(c)} 字符")

    # 结果族条目：**NNN. 标题.**
    results = re.findall(r"\*\*(\d{3})\.\s*(.+?)\*\*", c)
    print(f"  结果族 {len(results)}")

    for key in PAIR:
        print(f"\n  == 查找「{key}」==")
        # ① 在结果族标题里找
        hit_r = [(n, t) for n, t in results
                 if re.search(key.replace("Charts", "chart"), t, re.I)]
        for n, t in hit_r[:5]:
            print(f"     [族 {n}] {t[:110]}")
        # ② 在手稿链接里找
        papers = re.findall(r"\[([^\]]+)\]\((preprints/[^\)]+)\)", c)
        hit_p = [(t, p) for t, p in papers
                 if re.search(key.replace("Charts", "chart"), t, re.I)
                 or re.search(key.replace("Charts", "chart"), p, re.I)]
        print(f"     手稿链接命中 {len(hit_p)}")
        for t, p in hit_p[:6]:
            print(f"       · {t[:70]}")
            print(f"         {p[:96]}")
        if not hit_r and not hit_p:
            # ③ 退一步：拆词
            for w in re.findall(r"[A-Z][a-z]+", key):
                hh = [t for t, _p in papers if w.lower() in t.lower()]
                print(f"     拆词「{w}」命中 {len(hh)}：{[x[:56] for x in hh[:3]]}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "pair": list(PAIR),
        "note": "见控制台输出；用于判断这一对是同一篇论文还是两篇"
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
