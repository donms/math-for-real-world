#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W45 · Q2 级联扩散（**方向已修正**）。

## ★★ 修正记录：原版把传播方向搞反了，导致级联规模恒为 0

**症状**：拿**入度最高**的包 `@babel/helper-plugin-utils@7.29.7`（入度 97）
当种子，算出的级联规模 = **0**，`p_exec` 从 1 扫到 0.01 **全部 100% 灭绝**。

**根因**：我把传播定义成"沿出边"（A → A 依赖的包）。
但入度 97 的包**出度约等于 0** —— 它是**叶子**（工具库，自己不依赖别人）。
于是"沿出边"从它出发走不动。

**概念澄清**（两种传播都存在，但方向相反）：

| 传播类型 | 现实含义 | 图论方向 | 规模 = |
|---|---|---|---|
| **分发级联** | 包 X 被下毒 → **依赖 X 的人**装上就中招 | 沿 **入边反向**（X 的上游）| **上游可达** |
| **导入级联** | X 被感染 → 执行时**它 import 的包**也被注入 | 沿 **出边** | 下游可达 |

MemOS 事件**两种都有**：
载荷在 `import` 时执行（可注入 X 的依赖）**且**偷令牌后重发毒版本
（感染所有依赖 X 的项目）。

⇒ 本脚本**两种都建，主结论用「分发级联」**（用户侧影响），
   「导入级联」作为补充。

用法：
    $PY q2_cascade.py [每点模拟次数，默认 200]
"""
from __future__ import annotations

import csv
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict, deque
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
SRC = HERE.parents[3] / "sourcing" / "runs" / "sbom_graph.json"
CLEAN = ROOT / "data" / "clean"
RES = ROOT / "results"
FIGS = RES / "figs"
RES.mkdir(parents=True, exist_ok=True)
FIGS.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

ACTION_RE = re.compile(r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+@[0-9a-f]{40}$")


def base_name(nid: str) -> str:
    if nid.startswith("@"):
        p = nid.split("@")
        return "@" + p[1] if len(p) > 1 else nid
    return nid.split("@")[0]


def load_graph():
    d = json.loads(SRC.read_text(encoding="utf-8"))
    drop = {n for n in d["nodes"] if ACTION_RE.match(n)}
    nodes = [n for n in d["nodes"] if n not in drop]
    edges = [(a, b) for a, b in d["edges"]
             if a not in drop and b not in drop]
    return nodes, edges


def load_maintainers():
    p = CLEAN / "maintainers.csv"
    if not p.exists():
        return {}
    own = defaultdict(set)
    with open(p, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            own[row["maintainer"]].add(row["package"])
    return {k: v for k, v in own.items() if len(v) > 1}


def reach(start, adj) -> set:
    seen, q = set(), deque([start])
    while q:
        x = q.popleft()
        for y in adj.get(x, ()):
            if y not in seen:
                seen.add(y)
                q.append(y)
    return seen


def sim(start: str, adj, p: float, rng: random.Random,
        owner_of=None, maint_pkgs=None, p_maint: float = 0.0,
        nodeset=frozenset(), cap: int = 100_000) -> int:
    """独立级联。adj 决定方向：传 up_adj 得到分发级联，传 dn_adj 得导入级联。"""
    infected = {start}
    frontier = [start]
    steps = 0
    while frontier and steps < cap:
        nxt = []
        for x in frontier:
            steps += 1
            for y in adj.get(x, ()):
                if y not in infected and rng.random() < p:
                    infected.add(y)
                    nxt.append(y)
            if p_maint > 0 and owner_of is not None:
                for m in owner_of.get(base_name(x), ()):
                    if rng.random() >= p_maint:
                        continue
                    for z in maint_pkgs.get(m, ()):
                        if z not in infected and z in nodeset:
                            infected.add(z)
                            nxt.append(z)
        frontier = nxt
    return len(infected) - 1


def main() -> int:
    n_sim = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    nodes, edges = load_graph()
    nodeset = frozenset(nodes)
    dn = defaultdict(list)          # A -> A 依赖的（出边）
    up = defaultdict(list)          # B -> 依赖 B 的（入边反向）
    indeg, outdeg = Counter(), Counter()
    for a, b in edges:
        dn[a].append(b)
        up[b].append(a)
        outdeg[a] += 1
        indeg[b] += 1

    maint = load_maintainers()
    owner_of = defaultdict(set)
    for m, pkgs in maint.items():
        for pk in pkgs:
            owner_of[pk].add(m)

    print("=" * 94)
    print("  W45 · Q2 级联扩散（方向已修正：主结论用【分发级联】）")
    print("=" * 94)
    print(f"\n  图：节点 {len(nodes)}  边 {len(edges)}")
    print(f"  维护者层：{len(maint)} 位维护多包者")

    top_in = indeg.most_common(1)[0][0]
    top_out = outdeg.most_common(1)[0][0]
    print(f"\n  入度最高（被最多包依赖）: {top_in}  入度 {indeg[top_in]}"
          f"  出度 {outdeg[top_in]}")
    print(f"  出度最高（依赖最多）    : {top_out[:52]}  出度 {outdeg[top_out]}")

    rng = random.Random(20260928)
    seeds = rng.sample(nodes, min(200, len(nodes)))

    results = {}
    for label, adj, seed_node, note in (
        ("分发级联（主）", up, top_in,
         "包被下毒 → 所有【依赖它】的项目中招"),
        ("导入级联（补）", dn, top_out,
         "包被感染 → 它 import 的包也被注入"),
    ):
        print(f"\n{'='*94}")
        print(f"  【{label}】{note}")
        print(f"  种子 = {seed_node[:60]}")
        print("=" * 94)

        # p = 1 精确
        r1 = len(reach(seed_node, adj))
        rv = np.array([len(reach(s, adj)) for s in seeds], dtype=float)
        print(f"\n  p=1（精确）: 种子级联 {r1}   随机200种子 "
              f"均值 {rv.mean():.2f} 中位 {np.median(rv):.0f} "
              f"最大 {rv.max():.0f}")
        print(f"  比值（种子 / 随机均值）= {r1/max(rv.mean(),1e-9):.1f} 倍")

        # p 扫描
        ps = [1.0, 0.5, 0.3, 0.2, 0.15, 0.1, 0.07, 0.05, 0.03, 0.02, 0.01]
        curve = []
        print(f"\n  {'p':>6}{'均值':>10}{'中位':>8}{'P90':>8}"
              f"{'灭绝%':>9}{'ms/次':>8}")
        for p in ps:
            t0 = time.time()
            vals = [sim(seed_node, adj, p, rng) for _ in range(n_sim)]
            ms = (time.time() - t0) / n_sim * 1000
            v = np.array(vals, dtype=float)
            curve.append({"p": p, "mean": float(v.mean()),
                          "median": float(np.median(v)),
                          "p90": float(np.percentile(v, 90)),
                          "max": float(v.max()),
                          "extinct": float((v == 0).mean() * 100),
                          "ms": ms})
            print(f"  {p:>6.2f}{v.mean():>10.2f}{np.median(v):>8.0f}"
                  f"{np.percentile(v,90):>8.0f}"
                  f"{(v==0).mean()*100:>9.1f}{ms:>8.2f}")

        # 维护者层（只对分发级联做，因为"偷令牌重发"正是这个机制）
        mcurve = []
        if label.startswith("分发"):
            print(f"\n  ── 加入维护者层（p 固定 0.2）──")
            for pm in (0.0, 0.2, 0.5, 1.0):
                vals = [sim(seed_node, adj, 0.2, rng, owner_of=owner_of,
                            maint_pkgs=maint, p_maint=pm, nodeset=nodeset)
                        for _ in range(max(50, n_sim // 4))]
                v = np.array(vals, dtype=float)
                mcurve.append({"p_maint": pm, "mean": float(v.mean()),
                               "p90": float(np.percentile(v, 90))})
                print(f"     p_maint={pm:<5} 均值 {v.mean():>8.2f}  "
                      f"P90 {np.percentile(v,90):>7.0f}")

        results[label] = {"seed": seed_node, "p1": r1,
                          "random_mean": float(rv.mean()),
                          "random_median": float(np.median(rv)),
                          "random_max": float(rv.max()),
                          "curve": curve, "maintainer": mcurve,
                          "random_dist": rv.tolist()}

    # ---------- 出图 ----------
    main_r = results["分发级联（主）"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    ax = axes[0]
    for label, color in (("分发级联（主）", "#c0392b"),
                         ("导入级联（补）", "#2c6fbb")):
        c = results[label]["curve"]
        ax.loglog([x["p"] for x in c],
                  np.maximum([x["mean"] for x in c], 0.5), "o-",
                  color=color, lw=2, label=label)
    ax.set_xlabel("执行概率 p")
    ax.set_ylabel("期望级联规模（包数）")
    ax.set_title("两种方向的扩散规模 vs 执行概率", fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, which="both", alpha=0.3)

    ax = axes[1]
    rd = np.array(main_r["random_dist"], dtype=float)
    ax.hist(np.log10(np.maximum(rd, 0.5)), bins=40,
            color="#c0392b", alpha=0.85)
    ax.set_xlabel("log10(级联规模 + 1)")
    ax.set_ylabel("种子数")
    ax.set_title(f"分发级联 p=1 时随机种子的规模分布\n"
                 f"中位数 {np.median(rd):.0f}", fontsize=12)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    f1 = FIGS / "fig2_级联规模.png"
    fig.savefig(f1, dpi=150)
    plt.close(fig)
    print(f"\n     {f1.name}")

    out = {"graph": {"nodes": len(nodes), "edges": len(edges)},
           "top_indeg": [indeg[top_in], top_in],
           "top_outdeg": [outdeg[top_out], top_out],
           "results": results, "n_sim": n_sim}
    (RES / "q2_统计.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"     {RES/'q2_统计.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
