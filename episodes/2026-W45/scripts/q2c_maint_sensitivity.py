#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W45 · 维护者层的**敏感性**：它要多大覆盖面才有影响？

## 上一轮的结论与困惑

`q2b_maint_effect.py`（配对 t 检验，150 组）：
**9 个 (p, p_maint) 组合全部 |t| < 0.8，测不出放大效应。**
但结构诊断说"理论上最多能带来 60 个新节点" —— 看似矛盾。

**已查明的根因（非 bug）**：维护者层只覆盖 **28 个包名 / 7830 节点 = 0.36%**。
1 个维护者平均只掌握 3.75 个包（60 对 / 16 人）。
> 级联平均规模才 4 个节点，**极少撞到那 28 个包** ⇒ 效应小于噪声。

## 本脚本要回答

**"维护者层要多大，才真的能放大扩散？"** —— 这比"有/没有"更有用：
它给出一条**判据**，让读者知道在什么条件下该担心、什么条件下不用。

做法：
1. 用**种子定向**（只从维护者包的"上游"里选种子）⇒ 保证撞得上；
2. 用**人工扩大的维护者集**（把同 scope 的包视为同一维护者，
   模拟"一个组织掌握很多包"）⇒ 扫描覆盖面；
3. 报告"覆盖面 → 放大倍数"的曲线。

用法：
    $PY q2c_maint_sensitivity.py
"""
from __future__ import annotations

import csv
import json
import random
from collections import Counter, defaultdict, deque
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
SRC = HERE.parents[3] / "sourcing" / "runs" / "sbom_graph.json"
CLEAN = ROOT / "data" / "clean"
RES = ROOT / "results"

import re                                                    # noqa: E402
ACTION_RE = re.compile(r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+@[0-9a-f]{40}$")


def base_name(nid: str) -> str:
    if nid.startswith("@"):
        p = nid.split("@")
        return "@" + p[1] if len(p) > 1 else nid
    return nid.split("@")[0]


def load():
    d = json.loads(SRC.read_text(encoding="utf-8"))
    drop = {n for n in d["nodes"] if ACTION_RE.match(n)}
    nodes = [n for n in d["nodes"] if n not in drop]
    edges = [(a, b) for a, b in d["edges"]
             if a not in drop and b not in drop]
    return nodes, edges


def load_maint():
    own = defaultdict(set)
    p = CLEAN / "maintainers.csv"
    with open(p, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            own[r["maintainer"]].add(r["package"])
    return {k: v for k, v in own.items() if len(v) > 1}


def upstream(x, up) -> set:
    seen, q = set(), deque([x])
    while q:
        y = q.popleft()
        for z in up.get(y, ()):
            if z not in seen:
                seen.add(z)
                q.append(z)
    return seen


def sim(seed, up, p, rng, owner_of, maint, p_maint, nodeset,
        cap=100_000):
    infected = {seed}
    frontier = [seed]
    steps = 0
    while frontier and steps < cap:
        nxt = []
        for x in frontier:
            steps += 1
            for y in up.get(x, ()):
                if y not in infected and rng.random() < p:
                    infected.add(y)
                    nxt.append(y)
            if p_maint > 0:
                for m in owner_of.get(base_name(x), ()):
                    if rng.random() < p_maint:
                        for z in maint.get(m, ()):
                            if z not in infected and z in nodeset:
                                infected.add(z)
                                nxt.append(z)
        frontier = nxt
    return len(infected) - 1


def main() -> int:
    nodes, edges = load()
    nodeset = frozenset(nodes)
    up, indeg = defaultdict(list), Counter()
    for a, b in edges:
        up[b].append(a)
        indeg[b] += 1
    maint0 = load_maint()

    print("=" * 92)
    print("  W45 · 维护者层敏感性：覆盖多大才有效？")
    print("=" * 92)

    # ---------- 1) 原始维护者集：定向种子（保证撞得上）----------
    pkgs0 = {p for v in maint0.values() for p in v}
    owner0 = defaultdict(set)
    for m, v in maint0.items():
        for p in v:
            owner0[p].add(m)
    print(f"\n  ── 1) 原始维护者集（{len(pkgs0)} 个包名，"
          f"占 {len(pkgs0)/len(set(base_name(n) for n in nodes))*100:.2f}% 包名）──")

    # 种子池：维护者包的"上游"（谁装了它们）
    seed_pool = []
    for p in list(pkgs0)[:40]:
        node = next((n for n in nodes if base_name(n) == p), None)
        if node:
            seed_pool.extend(list(upstream(node, up))[:50])
    seed_pool = [s for s in seed_pool if s in nodeset]
    print(f"     定向种子池 {len(seed_pool)} 个（维护者包的上游）")

    rng = random.Random(7)
    for p in (0.2, 0.1):
        for pm in (0.0, 1.0):
            rb = random.Random(999)
            rt = random.Random(999)
            sd = [rng.choice(seed_pool) for _ in range(200)]
            base = [sim(s, up, p, rb, owner0, maint0, 0.0, nodeset)
                    for s in sd]
            tr = [sim(s, up, p, rt, owner0, maint0, pm, nodeset)
                  for s in sd]
            d = [t - b for t, b in zip(tr, base)]
            mb = sum(base) / len(base)
            md = sum(d) / len(d)
            print(f"     p={p} p_maint={pm}: 均值 {mb:>7.2f} → "
                  f"{mb+md:>7.2f}  配对差 {md:>+6.2f} "
                  f"({md/max(mb,1e-9)*100:>+6.1f}%)")

    # ---------- 2) 人工扩大维护者集：按 scope 归并 ----------
    print(f"\n  ── 2) 扩大覆盖面：把同 scope 的包视为同一维护者 ──")
    print(f"     （模拟『一个组织掌握很多包』，如 @babel/* @radix-ui/*）")
    base_names = sorted({base_name(n) for n in nodes})
    for scope in ("@babel", "@radix-ui", "@types", "@csstools", "@docusaurus"):
        grp = [p for p in base_names if p.startswith(scope + "/")]
        if len(grp) < 2:
            continue
        own = {"__scope__": set(grp)}
        oo = defaultdict(set)
        for p in grp:
            oo[p].add("__scope__")
        cover = len(grp) / len(base_names) * 100
        rng2 = random.Random(7)
        rb, rt = random.Random(999), random.Random(999)
        pool = [n for n in nodes if base_name(n) in set(grp)]
        pool = pool or nodes
        sd = [rng2.choice(pool) for _ in range(120)]
        b = [sim(s, up, 0.1, rb, oo, own, 0.0, nodeset) for s in sd]
        t = [sim(s, up, 0.1, rt, oo, own, 1.0, nodeset) for s in sd]
        mb = sum(b) / len(b)
        md = sum(x - y for x, y in zip(t, b)) / len(b)
        print(f"     {scope+'/*':<14}{len(grp):>4} 个包 "
              f"({cover:>5.2f}% 包名)  均值 {mb:>6.2f} → {mb+md:>6.2f}  "
              f"配对差 {md:>+6.2f}")

    # ---------- 3) 判据 ----------
    print(f"\n  ── 3) 判据 ──")
    print(f"     维护者层要产生影响，需要『级联能撞到该维护者的包』：")
    print(f"       期望撞到数 ≈ 级联规模 × 该维护者包数 / 总节点数")
    avg_cas = 4.14      # 来自 q2 的 p=0.2 随机种子均值
    per = len(pkgs0) / len(maint0)
    hit = avg_cas * per / len(nodes)
    print(f"     例：级联 {avg_cas} 包 × 每人 {per:.1f} 包 / {len(nodes)} 节点"
          f" = **{hit:.5f}**")
    print(f"     ⇒ 撞上的概率约 {hit*100:.3f}%，**所以测不出来是正常的**")
    need = len(nodes) / max(avg_cas, 1e-9)
    print(f"     要让『每次级联都撞到』，维护者需掌握约 **{need:.0f} 个包**"
          f"（即 100% 覆盖率）")

    out = {"maint_pkgs": len(pkgs0), "maint_people": len(maint0),
           "packages_per_maint": per,
           "hit_prob_per_cascade": hit,
           "nodes": len(nodes), "avg_cascade_p02": avg_cas}
    (RES / "q2c_维护者层敏感性.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {RES/'q2c_维护者层敏感性.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
