#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W45 · 依赖图体检：给题面与分析报告提供**真实数字**。

## 产出

* 图的基本规模（节点/边/连通性/度分布）
* **入度分布**：有多少包是"广泛被依赖"的（这些是投毒的甜点）
* **可达性**：随机一个包被投毒，平均能"向下"波及多少包
* 把结果落盘 `data/clean/graph_stats.json`

## 为什么要先做这一步

题面里必须写**真实数字**（选题卡的规矩：先实测再评分）。
而且 Q1 的"建图与体检"本身就是题目第一问，先跑通等于验证可行性。

用法：
    $PY graph_health.py
"""
from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# ⚠️ 脚本在 episodes/2026-W45/scripts/ 下 ⇒ parents[0]=scripts [1]=2026-W45
#    [2]=episodes [3]=NewsMCM。sourcing/ 挂在 NewsMCM 下，故用 parents[3]。
#    （W44 与本文件都因层级算错把结果写到了工作区外，这是本项目高频坑。）
SRC = (Path(__file__).resolve().parents[3] / "sourcing" / "runs"
       / "sbom_graph.json")
OUT = ROOT / "data" / "clean"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    d = json.loads(SRC.read_text(encoding="utf-8"))
    nodes = set(d["nodes"])
    edges = [(a, b) for a, b in d["edges"]]
    roots = set(d["roots"])

    fwd = defaultdict(set)          # A -> 它依赖的（下游执行链）
    rev = defaultdict(set)          # B -> 依赖它的（上游影响者）
    for a, b in edges:
        fwd[a].add(b)
        rev[b].add(a)

    indeg = {n: len(rev[n]) for n in nodes}
    outdeg = {n: len(fwd[n]) for n in nodes}

    print("=" * 90)
    print("  W45 · 依赖图体检（GitHub SBOM 聚合）")
    print("=" * 90)
    n, m = len(nodes), len(edges)
    print(f"\n  节点 {n}   边 {m}   根包 {len(roots)}")
    print(f"  平均入度 {m/n:.2f}   平均出度 {m/n:.2f}")

    # ---- 度分布 ----
    print("\n  ── 入度分布（被多少包依赖 = 投毒的『收益』）──")
    buckets = [(0, 0), (1, 1), (2, 4), (5, 9), (10, 49), (50, 10**9)]
    for lo, hi in buckets:
        c = sum(1 for v in indeg.values() if lo <= v <= hi)
        label = f"{lo}" if lo == hi else (f"{lo}+" if hi > 10**8
                                          else f"{lo}–{hi}")
        bar = "#" * min(60, int(c / max(1, n) * 120))
        print(f"    入度 {label:<8}{c:>6}  ({c/n*100:>5.1f}%)  {bar}")

    print("\n    入度最高的 12 个包：")
    for name, v in sorted(indeg.items(), key=lambda kv: -kv[1])[:12]:
        print(f"      {v:>4}  {name}")

    # ---- 可达性：投毒一个包，向下能波及多少 ----
    print("\n  ── 下游可达规模（投毒该包，能执行到它的包数）──")
    sys_set = __import__("sys")
    sys_set.setrecursionlimit(10000)

    def reachable(src: str) -> int:
        seen, q = set(), deque([src])
        while q:
            x = q.popleft()
            for y in fwd[x]:
                if y not in seen:
                    seen.add(y)
                    q.append(y)
        return len(seen - {src})

    sizes = []
    for nd in nodes:
        sizes.append((reachable(nd), nd))
    sizes.sort(reverse=True)
    tot = sum(s for s, _ in sizes)
    print(f"    平均下游可达 {tot/n:.2f} 个包（即投毒一个包，平均波及这么多）")
    print(f"    中位数 {sorted(s for s, _ in sizes)[n//2]}")
    print(f"    最大 {sizes[0][0]}（{sizes[0][1][:46]}）")
    print("\n    下游可达最大的 12 个（= 最值得投毒的包）：")
    for s, nd in sizes[:12]:
        print(f"      {s:>5}  {nd}")

    # ---- 连通性 ----
    print("\n  ── 连通性 ──")
    # 无向弱连通分量
    seen = set()
    comps = []
    und = defaultdict(set)
    for a, b in edges:
        und[a].add(b)
        und[b].add(a)
    for nd in nodes:
        if nd in seen:
            continue
        q, comp = deque([nd]), 0
        seen.add(nd)
        while q:
            x = q.popleft()
            comp += 1
            for y in und[x]:
                if y not in seen:
                    seen.add(y)
                    q.append(y)
        comps.append(comp)
    comps.sort(reverse=True)
    print(f"    弱连通分量 {len(comps)} 个")
    print(f"    最大分量 {comps[0]} 个包（占 {comps[0]/n*100:.1f}%）")
    print(f"    前 8 大分量：{comps[:8]}")

    stats = {
        "nodes": n, "edges": m, "roots": len(roots),
        "avg_indeg": m / n, "max_indeg": max(indeg.values()),
        "top_indeg": sorted(indeg.items(), key=lambda kv: -kv[1])[:20],
        "avg_reach": tot / n,
        "max_reach": sizes[0][0],
        "top_reach": [[s, x] for s, x in sizes[:20]],
        "weak_components": len(comps),
        "largest_component": comps[0],
        "isolated": sum(1 for c in comps if c == 1),
    }
    (OUT / "graph_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {OUT/'graph_stats.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
