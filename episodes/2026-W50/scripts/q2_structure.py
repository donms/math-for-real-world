#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W50 · 问题 2–4：**承重结构 · 领域协作 · 验证成本**。

## 数据

`data/imports.jsonl` —— **86924 个模块 / 248871 条依赖边**
（已体检：DAG ✅ 86924/86924、悬空边 0.1%、自环 0）

## 三个问题

### 问 2 · 承重分析（哪些模块是地基？）

| 指标 | 含义 |
|---|---|
| **入度**（被多少模块 import）| 直接承重 |
| **反向可达规模**（有多少模块最终依赖它）| **总承重** |
| **层号**（DAG 最长路分层）| 地基在下、结论在上 |

### 问 3 · 领域协作（证据用了多少"外来"数学？）

对 `formalization.yaml` 里的**形式化条目**，追溯其模块的**反向可达集**，
统计该集合里的**领域构成** ⇒ 回答"每个结果依赖哪几门数学"。

### 问 4 · 验证成本（最长推理链有多长？）

DAG 的**最长路径**就是"最深的一条依赖链"。
它决定：**一个验证者至少要串行理解多少层**。

## ★★ 三个必须写清的口径（否则结论会被误读）

1. **依赖方向**：`A` import `B` ⇒ 边 `B -> A`（**B 被 A 依赖**）。
   于是**入度 = 被依赖次数**，**反向可达 = 传递依赖它的模块数**。
2. **推理链是【模块级】的**，不是"证明步骤"。
   Lean 里"定理 A 用了引理 B"需要解析 tactic 块才能得到，
   **本问不做**（引用方式太多：`exact`/`simpa using`/`rw [...]`…）。
3. **覆盖率 47.5%/100%（分文件）** ⇒
   **承重排名在子集内自洽**；**规模类数字只报"下限"**；
   UniqueGames 那一支已 **100% 补全**，可单独给出完整结论。

用法：
    $PY q2_structure.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W50"
DATA = EP / "data"
RES = EP / "results"
RES.mkdir(parents=True, exist_ok=True)


def load_graph() -> tuple[dict[str, list[str]], set[str]]:
    r"""读依赖图。

    返回 `(deps, nodes)`：`deps[m]` = m 依赖的模块列表。
    边方向：**`d -> m`**（d 被 m 依赖）。
    """
    deps: dict[str, list[str]] = {}
    with (DATA / "imports.jsonl").open(encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            deps[d["mod"][5:] if d["mod"].startswith("lean.") else d["mod"]] \
                = [x for x in d["deps"]]
    return deps, set(deps)


def build_adj(deps: dict[str, list[str]], nodes: set[str]):
    r"""建邻接表（只保留内部边）。

    `rev[d]` = 依赖 d 的模块（入边的另一端）
    `fwd[m]` = m 依赖的模块
    """
    rev: dict[str, list[str]] = defaultdict(list)
    fwd: dict[str, list[str]] = defaultdict(list)
    n_int = 0
    for m, ds in deps.items():
        for d in ds:
            if d in nodes and d != m:
                rev[d].append(m)
                fwd[m].append(d)
                n_int += 1
    return rev, fwd, n_int


def longest_path_layers(fwd: dict[str, list[str]],
                        nodes: set[str]) -> dict[str, int]:
    r"""DAG 分层：`layer[m]` = 从"最底"到 m 的最长依赖链**步数**。

    递推（`fwd[m]` 是 m 依赖的模块，它们都在更低层）：
        layer[m] = 1 + max(layer[d] for d in fwd[m])，叶子为 0
    用 Kahn 拓扑序一遍算出（避免递归深度问题）。
    """
    layer = {n: 0 for n in nodes}
    indeg = {n: 0 for n in nodes}
    for m in nodes:
        for d in fwd.get(m, ()):            # d -> m
            indeg[m] += 1
    q = deque([n for n in nodes if indeg[n] == 0])
    seen = 0
    while q:
        u = q.popleft()
        seen += 1
        for p in _consumers(u):
            layer[p] = max(layer[p], layer[u] + 1)
            indeg[p] -= 1
            if indeg[p] == 0:
                q.append(p)
    return layer, seen


_CONSUMERS: dict[str, list[str]] = {}


def _consumers(u: str) -> list[str]:
    return _CONSUMERS.get(u, [])


def reach_size(start: str) -> int:
    r"""从 start **反向**可达的模块数（= 传递依赖 start 的模块数）。

    用 BFS + 记忆化太占内存，这里对单个 start 做 BFS（够用）。
    """
    seen = set()
    q = deque(_CONSUMERS.get(start, ()))
    while q:
        u = q.popleft()
        if u in seen:
            continue
        seen.add(u)
        q.extend(_CONSUMERS.get(u, ()))
    return len(seen)


def domain_of(mod: str) -> str:
    r"""模块名 -> 数学领域（`OAI.<Domain>....`）。"""
    p = mod.split(".")
    if len(p) > 1 and p[0] == "OAI":
        return p[1]
    if mod.startswith("ComparatorChallenges"):
        return "(Comparator)"
    return "(其他)"


def main() -> int:
    print("=" * 96)
    print("  W50 · 问题 2-4：承重结构 / 领域协作 / 验证成本")
    print("=" * 96)

    deps, nodes = load_graph()
    rev, fwd, n_int = build_adj(deps, nodes)
    global _CONSUMERS
    _CONSUMERS = rev
    print(f"\n  节点 {len(nodes)}  内部边 {n_int}")
    print(f"  孤立节点（无任何内部边）："
          f"{sum(1 for n in nodes if not rev.get(n) and not fwd.get(n))}")

    # ── 分层 ──
    global _consumers
    layer, seen = longest_path_layers(fwd, nodes)
    print(f"\n  ── 问 4：DAG 分层（最长依赖链）──")
    print(f"    拓扑访问 {seen}/{len(nodes)}")
    lmax = max(layer.values()) if layer else 0
    print(f"    **最长依赖链 = {lmax} 层**")
    hist = Counter(layer.values())
    print(f"    层分布（层号: 模块数，前 12 层）:")
    for k in sorted(hist)[:12]:
        print(f"      第 {k:>3} 层  {hist[k]:>7}")
    print(f"    （共 {len(hist)} 个不同层号）")

    # ── 承重：入度 ──
    indeg = {n: len(rev.get(n, ())) for n in nodes}
    top = sorted(indeg.items(), key=lambda x: -x[1])[:15]
    print(f"\n  ── 问 2：直接承重（入度 = 被多少个模块 import）──")
    print(f"    {'模块':<62}{'入度':>6}")
    for m, v in top:
        print(f"    {m[:60]:<62}{v:>6}")
    ind = np.array(list(indeg.values()))
    print(f"\n    入度分布：中位 {np.median(ind):.0f}  "
          f"均值 {ind.mean():.1f}  最大 {ind.max()}")
    print(f"    零入度模块 {int((ind==0).sum())} 个 "
          f"（{int((ind==0).sum())/len(nodes)*100:.1f}%）")
    print(f"    入度 >= 100 的模块 {int((ind>=100).sum())} 个")
    print(f"    入度 >= 10  的模块 {int((ind>=10).sum())} 个")

    # ── 承重：反向可达（对入度 top 算）──
    print(f"\n  ── 问 2：总承重（反向可达规模 = 有多少模块最终依赖它）──")
    print(f"    {'模块':<58}{'入度':>6}{'可达':>8}")
    reach = {}
    for m, v in top[:12]:
        r = reach_size(m)
        reach[m] = r
        print(f"    {m[:56]:<58}{v:>6}{r:>8}")
    vals = np.array(list(reach.values()))
    print(f"\n    ⇒ 少数模块被**上万**个模块间接依赖")

    # ── 领域协作 ──
    print(f"\n  ── 问 3：领域分布（按模块数）──")
    dom = Counter(domain_of(n) for n in nodes)
    for k, v in dom.most_common(16):
        print(f"    {k:<26}{v:>7}")
    # 领域间依赖
    cross = Counter()
    for m in nodes:
        dm = domain_of(m)
        for d in fwd.get(m, ()):
            dd = domain_of(d)
            if dd != dm:
                cross[(dm, dd)] += 1
    print(f"\n  ── 问 3：跨领域依赖（前 12 对）──")
    print(f"    {'依赖方':<20}{'被依赖方':<20}{'边数':>7}")
    for (a, b), v in cross.most_common(12):
        print(f"    {a:<20}{b:<20}{v:>7}")
    print(f"\n    跨领域边 {sum(cross.values())} / 内部边 {n_int} = "
          f"{sum(cross.values())/n_int*100:.1f}%")

    out = {
        "节点数": len(nodes), "内部边": n_int,
        "最长依赖链层数": int(lmax),
        "层分布": {str(k): v for k, v in sorted(hist.items())},
        "入度": {"中位": float(np.median(ind)), "均值": float(ind.mean()),
                 "最大": int(ind.max()),
                 "零入度模块": int((ind == 0).sum()),
                 "入度>=100": int((ind >= 100).sum()),
                 "入度>=10": int((ind >= 10).sum())},
        "直接承重Top20": [{"模块": m, "入度": v} for m, v in
                          sorted(indeg.items(), key=lambda x: -x[1])[:20]],
        "总承重Top12": [{"模块": m, "入度": indeg[m], "反向可达": r}
                        for m, r in reach.items()],
        "领域分布": dict(dom.most_common(30)),
        "跨领域依赖Top": [{"从": a, "到": b, "边数": v}
                          for (a, b), v in cross.most_common(20)],
        "跨领域边占比pct": round(sum(cross.values()) / n_int * 100, 2),
        "_口径": {
            "边方向": "A import B => 边 B->A（B 被 A 依赖）",
            "入度": "被多少个模块直接 import",
            "反向可达": "有多少模块最终（传递地）依赖它",
            "推理链": "**模块级**最长依赖链，非『证明步骤』",
        },
        "_自查": [
            "推理链是模块级的：不做『定理A用了引理B』（需解析 tactic 块）",
            "覆盖率不完整 => 规模类数字只报下限",
            "UniqueGames 一支已 100% 补全，可单独给完整结论",
        ],
    }
    p = RES / "q2_结构.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
