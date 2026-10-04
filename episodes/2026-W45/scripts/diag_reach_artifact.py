#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W45 · 诊断：合并 20 棵 SBOM 树后，"下游可达"是否被跨仓库边放大。

## 疑点

`q1_graph_profile.py` 报"去根包后下游可达前 10 全是 Docusaurus 插件（各约 1100）"。
但 Docusaurus 不是我们扫描的根包 —— 它凭什么是 1100？

## 猜想

GitHub SBOM 给的是**每个仓库的依赖闭包**（本质可能是一棵树：
小仓库 requests 是 30 包 / 29 边，边数 ≈ 节点数-1）。
**20 棵树合并成一个 DAG 后**，来自不同仓库的边会**跨树相连**，
于是某个节点的"下游可达"不再等于它在自己那棵树里的子树大小，
而被其他仓库的闭包**放大**。

## 本脚本要回答

1. 每个仓库的闭包是树吗（边数 vs 节点数-1）？
2. 各仓库闭包大小分布？
3. **同一口径下**（只看单棵树）的下游可达分布 vs 合并图上的分布 —— 差多少？
4. Docusaurus 的 1100 是从哪棵树借来的？

用法：
    $PY diag_reach_artifact.py
"""
from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
SRC = HERE.parents[3] / "sourcing" / "runs" / "sbom_graph.json"


def main() -> int:
    d = json.loads(SRC.read_text(encoding="utf-8"))
    nodes = list(d["nodes"])
    edges = [tuple(e) for e in d["edges"]]
    roots = sorted(d["roots"])

    fwd = defaultdict(set)
    rev = defaultdict(set)
    for a, b in edges:
        fwd[a].add(b)
        rev[b].add(a)

    print("=" * 92)
    print("  W45 · 诊断：下游可达是否被跨仓库边放大")
    print("=" * 92)

    # ---- 1) 从每个根包算闭包（该仓库的依赖闭包）----
    print("\n  ── 1) 各根的闭包规模（该仓库 SBOM 的节点数）──")
    closure = {}
    for r in roots:
        seen, q = set(), deque([r])
        seen.add(r)
        while q:
            x = q.popleft()
            for y in fwd.get(x, ()):
                if y not in seen:
                    seen.add(y)
                    q.append(y)
        closure[r] = seen
    sizes = sorted(((len(v), k) for k, v in closure.items()), reverse=True)
    for n, r in sizes:
        print(f"     {n:>5}  {r}")
    print(f"\n     闭包之和 {sum(len(v) for v in closure.values())}"
          f"（含重复）  去重后 {len(set().union(*closure.values()))}")

    # ---- 2) 闭包是树吗 ----
    print("\n  ── 2) 每个闭包内部的边数 vs 节点数（树的话 边=节点-1）──")
    for n, r in sizes[:8]:
        cs = closure[r]
        e = sum(1 for a, b in edges if a in cs and b in cs)
        print(f"     {r[:40]:<42} 节点 {n:>5}  边 {e:>6}  "
              f"边/节点 {e/max(n,1):.2f}")

    # ---- 3) 单树口径 vs 合并口径 ----
    print("\n  ── 3) 下游可达：单树口径 vs 合并图口径 ──")
    # 每个节点"属于"哪些树的闭包
    belongs = defaultdict(list)
    for r, cs in closure.items():
        for x in cs:
            belongs[x].append(r)
    print(f"     出现在多个仓库闭包里的节点："
          f"{sum(1 for v in belongs.values() if len(v) > 1)} / {len(nodes)}")

    # 单树口径：节点在其所属各树中的子树大小，取最大
    def subtree_sizes(root: str) -> dict:
        cs = closure[root]
        sub = {x: set() for x in cs}
        # 按拓扑序反向累计
        order, indeg = [], {x: 0 for x in cs}
        for a, b in edges:
            if a in cs and b in cs:
                indeg[b] += 1
        q = deque([x for x in cs if indeg[x] == 0])
        while q:
            x = q.popleft()
            order.append(x)
            for y in fwd.get(x, ()):
                if y in cs:
                    indeg[y] -= 1
                    if indeg[y] == 0:
                        q.append(y)
        for x in reversed(order):
            s = set()
            for y in fwd.get(x, ()):
                if y in cs:
                    s.add(y)
                    s |= sub[y]
            sub[x] = s
        return {x: len(v) for x, v in sub.items()}

    per_tree_max = defaultdict(int)
    for r in roots:
        for x, v in subtree_sizes(r).items():
            if v > per_tree_max[x]:
                per_tree_max[x] = v

    # 合并图口径
    def reach_union(x):
        seen, q = set(), deque([x])
        while q:
            y = q.popleft()
            for z in fwd.get(y, ()):
                if z not in seen:
                    seen.add(z)
                    q.append(z)
        return len(seen)

    import numpy as np
    union_vals, tree_vals = [], []
    for x in nodes:
        u = reach_union(x)
        t = per_tree_max.get(x, 0)
        union_vals.append(u)
        tree_vals.append(t)
    uv, tv = np.array(union_vals, float), np.array(tree_vals, float)
    print(f"     合并图口径：均值 {uv.mean():.2f}  中位数 {np.median(uv):.0f}"
          f"  最大 {uv.max():.0f}")
    print(f"     单树口径  ：均值 {tv.mean():.2f}  中位数 {np.median(tv):.0f}"
          f"  最大 {tv.max():.0f}")

    # ---- 4) Docusaurus 的可达从哪来 ----
    print("\n  ── 4) Docusaurus 插件的可达来源 ──")
    for probe in ("@docusaurus/plugin-pwa@3.10.2",
                  "@docusaurus/preset-classic@3.10.2"):
        if probe not in belongs:
            print(f"     {probe} 不在任何闭包里？")
            continue
        print(f"     {probe}")
        print(f"       属于 {len(belongs[probe])} 个仓库闭包："
              f"{[b[:26] for b in belongs[probe]][:5]}")
        print(f"       合并图可达 {reach_union(probe)}"
              f"   单树可达 {per_tree_max.get(probe, 0)}")

    out = {
        "closure_sizes": {k: len(v) for k, v in closure.items()},
        "union_nodes": len(nodes),
        "union_edges": len(edges),
        "nodes_in_multiple_closures": sum(1 for v in belongs.values()
                                          if len(v) > 1),
        "reach_union": {"mean": float(uv.mean()),
                        "median": float(np.median(uv)),
                        "max": float(uv.max())},
        "reach_single_tree": {"mean": float(tv.mean()),
                              "median": float(np.median(tv)),
                              "max": float(tv.max())},
    }
    (ROOT / "results" / "q1_诊断_可达口径.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
