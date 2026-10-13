#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W52 问 4 · **真正的桥梁在哪**：跨学科边与跨族边的逐条解剖。

## 前四问的结论回顾

| 问 | 结论 |
|---|---|
| 1 | 内部边里 **99.55% 同学科**；**98.3% 的结果族只用 1 个学科** |
| 2 | 剔除 mathlib 后可达学科数**一个都没少** ⇒ **mathlib 是共享底座，不是桥梁** |
| 3 | 跨学科率比「按学科规模应有的水平」**低约 185 倍** |

## 于是剩下的问题

**那 909 条跨学科边是什么？它们是真桥梁，还是组织上的偶然？**

本脚本逐条解剖这 909 条边，并按**信息量**排序：

| 判据 | 含义 |
|---|---|
| **跨族性** | 两端是否属于**不同结果族** —— 跨族才是真"桥梁" |
| **对称性** | 是单向依赖还是互引（互引更像"共用工具"）|
| **集中度** | 是否集中在少数几对学科（若是，则不是普遍现象）|

## 还要回答：**费马大定理式的桥梁**在本批结果里有没有

费马大定理的桥梁形态是：
**一个领域（椭圆曲线）的核心问题，靠另一个领域（模形式）的工具解决**。

在本数据里的可观测代理：
* 边的两端**学科不同** 且 **族也不同** ⇒ 才是"借用外域工具"；
* 若两端同学科、跨族 ⇒ 是**同领域内的分工**，不算桥梁。

用法：
    $PY q4_real_bridges.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from load_imports import find_imports                           # noqa: E402

SRC = find_imports(ROOT)
OUTJ = ROOT / "episodes" / "2026-W52" / "results" / "q4_桥梁解剖.json"
OUTM = ROOT / "episodes" / "2026-W52" / "results" / "q4_桥梁解剖.md"


def parse(mod: str):
    m = re.sub(r"^lean\.", "", mod)
    if not m.startswith("OAI."):
        return None
    p = m.split(".")
    return (p[1], p[2]) if len(p) >= 3 else None


def main() -> int:
    print("=" * 96)
    print("  W52 问 4 · 真正的桥梁在哪：909 条跨学科边的逐条解剖")
    print("=" * 96)

    mod2dc: dict[str, tuple[str, str]] = {}
    deps: dict[str, list[str]] = {}
    with SRC.open(encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            mod = re.sub(r"^lean\.", "", d.get("mod", ""))
            p = parse(mod)
            if not p:
                continue
            mod2dc[mod] = p
            deps[mod] = [re.sub(r"^lean\.", "", str(x))
                         for x in (d.get("deps") or [])]

    # ---- 分类所有内部边 ----
    cats = Counter()
    cross_edges = []
    cross_fam_edges = []
    for m, ds in deps.items():
        d1, f1 = mod2dc[m]
        for dp in ds:
            if dp not in mod2dc:
                continue
            d2, f2 = mod2dc[dp]
            same_d = (d1 == d2)
            same_f = (f1 == f2)
            key = ("同科同族" if same_d and same_f else
                   "同科跨族" if same_d else
                   "跨科同族" if same_f else "跨科跨族")
            cats[key] += 1
            if not same_d:
                cross_edges.append((m, dp, d1, d2, f1, f2, key))
            if not same_d and not same_f:
                cross_fam_edges.append((m, dp, d1, d2, f1, f2))

    tot = sum(cats.values())
    print(f"\n  == 内部边四种形态（共 {tot}）==")
    for k in ("同科同族", "同科跨族", "跨科同族", "跨科跨族"):
        print(f"     {k:<12}{cats[k]:>8}  ({cats[k]/tot*100:>5.2f}%)")

    print(f"\n  == ★ 什么才算「桥梁」==")
    print(f"     跨学科边: {len(cross_edges)}")
    print(f"     其中**跨科且跨族**: {len(cross_fam_edges)}"
          f"  ← 这才是「借用外域工具」")
    print(f"     跨科但同族: {len(cross_edges)-len(cross_fam_edges)}"
          f"  ← 同一族内部的分工，不算桥梁")

    # ---- 集中度：跨科跨族边落在多少对学科上 ----
    pair_c = Counter(tuple(sorted((a[2], a[3]))) for a in cross_fam_edges)
    print(f"\n  == 跨科跨族边的学科对集中度 ==")
    print(f"     涉及学科对 {len(pair_c)} 种")
    for (a, b), v in pair_c.most_common(12):
        print(f"     {a:<22} <-> {b:<22} {v:>5}")
    if pair_c:
        top = sum(v for _k, v in pair_c.most_common(3))
        print(f"\n     Top-3 学科对占 {top}/{len(cross_fam_edges)} = "
              f"{top/max(1,len(cross_fam_edges))*100:.0f}%")

    # ---- 方向性：单向 vs 双向 ----
    directed = Counter()
    for m, dp, d1, d2, _f1, _f2 in cross_fam_edges:
        directed[(d1, d2)] += 1
    mutual = 0
    for (a, b), v in directed.items():
        if (b, a) in directed:
            mutual += 1
    print(f"\n  == 方向性 ==")
    print(f"     有向学科对 {len(directed)} 种")
    print(f"     其中**互引**（a->b 且 b->a）: {mutual // 2} 对"
          f"  ← 互引更像「共用工具」而非「桥梁」")

    # ---- 结果族层面的跨族依赖（不以学科为界）----
    fam_deps: Counter = Counter()
    for m, ds in deps.items():
        f1 = mod2dc[m][1]
        for dp in ds:
            if dp in mod2dc and mod2dc[dp][1] != f1:
                fam_deps[(f1, mod2dc[dp][1])] += 1
    print(f"\n  == 结果族之间的依赖（不按学科切）==")
    print(f"     跨族依赖边 {sum(fam_deps.values())} 条"
          f"，涉及 {len(fam_deps)} 个有序族对")
    print(f"     有跨族依赖的族: "
          f"{len({a for a, _b in fam_deps} | {b for _a, b in fam_deps})}"
          f" / {len({v[1] for v in mod2dc.values()})}")

    OUTJ.parent.mkdir(parents=True, exist_ok=True)
    OUTJ.write_text(json.dumps({
        "cats": dict(cats), "total": tot,
        "cross": len(cross_edges), "cross_fam": len(cross_fam_edges),
        "pair_counts": {f"{a}|{b}": v for (a, b), v in pair_c.items()},
        "mutual_pairs": mutual // 2,
        "fam_dep_edges": sum(fam_deps.values()),
        "fam_dep_pairs": len(fam_deps),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    L = ["# W52 · 问 4：真正的桥梁在哪", "",
         "## 一、内部边的四种形态", "",
         "| 形态 | 边数 | 占比 |", "|---|---|---|"]
    for k in ("同科同族", "同科跨族", "跨科同族", "跨科跨族"):
        L.append(f"| {k} | {cats[k]} | {cats[k]/tot*100:.2f}% |")
    L += ["", "## 二、什么才算「桥梁」", "",
          "| 类型 | 边数 | 是否算桥梁 |", "|---|---|---|",
          f"| 跨学科（全部）| {len(cross_edges)} | 部分 |",
          f"| **跨科且跨族** | **{len(cross_fam_edges)}** | "
          f"**是 —— 借用外域工具** |",
          f"| 跨科但同族 | "
          f"{len(cross_edges)-len(cross_fam_edges)} | "
          f"否 —— 同族内部分工 |", "",
          "**费马大定理式的桥梁**（椭圆曲线 ← 模形式）对应的是"
          "**跨科且跨族**这一类。", "",
          f"⇒ 全部 {tot} 条内部边里，只有 **{len(cross_fam_edges)}** 条"
          f"（**{len(cross_fam_edges)/tot*100:.3f}%**）属于这一类。", "",
          "## 三、集中度：这些桥梁落在哪", "",
          "| 学科对 | 边数 |", "|---|---|"]
    for (a, b), v in pair_c.most_common(12):
        L.append(f"| {a} ↔ {b} | {v} |")
    if pair_c:
        top = sum(v for _k, v in pair_c.most_common(3))
        L += ["", f"**Top-3 学科对占 "
                  f"{top}/{len(cross_fam_edges)} = "
                  f"{top/max(1,len(cross_fam_edges))*100:.0f}%**"]
    L += ["", "## 四、结果族之间的依赖（不按学科切）", "",
          f"- 跨族依赖边：**{sum(fam_deps.values())}** 条",
          f"- 涉及有序族对：**{len(fam_deps)}** 个",
          f"- 有跨族依赖的族："
          f"**{len({a for a, _b in fam_deps} | {b for _a, b in fam_deps})}**"
          f" / {len({v[1] for v in mod2dc.values()})}"]
    OUTM.write_text("\n".join(L), encoding="utf-8")
    print(f"\n  -> {OUTJ.relative_to(ROOT)}")
    print(f"  -> {OUTM.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
