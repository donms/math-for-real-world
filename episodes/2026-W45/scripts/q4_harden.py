#!/usr/bin/env python -u
# -*- coding: utf-8 -*-
r"""W45 · Q4 加固优化（**加权修正版**）。

## 为什么必须加权（自诊断发现）

未加权的贪心给出 k=1 的最优解是 **`@docusaurus/core`**（改善 18.36%）。
但实测：**它只出现在 1 个仓库闭包（jest 的）里** ——
那 18% 全部来自 jest 那棵 2501 节点的巨树，**不是生态级风险**。

⇒ 不加权时，贪心会去**攻击我们自己的采样方式**（哪棵树大就保护哪棵树）。

## 修法：给每个被保护节点按「被多少真实项目用到」加权

$$W(S)=\sum_{v\notin S} w_v\cdot\big|\mathrm{reach}(v)\setminus S\big|,
\qquad w_v=\big|\{r:\ v\in \mathrm{closure}(r)\}\big|$$

$w_v$ = 这个包被我们扫描的 20 个仓库里**多少个**用到。
⇒ 保护一个"只有 1 个项目用"的包，收益自然就小。

## 产出

* 加权 vs 未加权 的**名单差异**（这是决策 3 要的"结论稳健性"证据）
* 与暴力搜索验证贪心质量
* 与三个常见直觉比对

用法：
    $PY q4_harden.py
"""
from __future__ import annotations

import csv
import itertools
import json
import math
import re
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


def main() -> int:
    d = json.loads(SRC.read_text(encoding="utf-8"))
    drop = {n for n in d["nodes"] if ACTION_RE.match(n)}
    nodes = [n for n in d["nodes"] if n not in drop]
    edges = [(a, b) for a, b in d["edges"]
             if a not in drop and b not in drop]
    roots = list(d["roots"])

    dep = defaultdict(list)          # a -> a 的依赖
    prop = defaultdict(list)         # b -> 依赖 b 的人（传播方向）
    for a, b in edges:
        dep[a].append(b)
        prop[b].append(a)

    # ---- 项目权重：每节点被多少个仓库闭包包含 ----
    w = Counter()
    for r in roots:
        seen, q = set([r]), deque([r])
        while q:
            x = q.popleft()
            for y in dep.get(x, ()):
                if y not in seen:
                    seen.add(y)
                    q.append(y)
        for n in seen:
            w[n] += 1
    N = len(nodes)
    wv = np.array([w.get(n, 0) for n in nodes])
    print("=" * 94)
    print("  W45 · Q4 加固优化（加权修正版）")
    print("=" * 94)
    print(f"\n  节点 {N}  边 {len(edges)}  根 {len(roots)}")
    print(f"  项目权重：max {wv.max()}  均值 {wv.mean():.2f}  "
          f"权重≥2 的节点 {int((wv>=2).sum())} ({(wv>=2).mean()*100:.1f}%)")
    print(f"  权重=1 的节点 {int((wv==1).sum())} ({(wv==1).mean()*100:.1f}%)"
          f"  ← 只被 1 个项目用到")

    def reach(nodes_, adj, blocked):
        """返回 {节点: 可达集合}。"""
        out = {}
        for s in nodes_:
            if s in blocked:
                out[s] = set()
                continue
            seen, q = set(), deque([s])
            while q:
                x = q.popleft()
                for y in adj.get(x, ()):
                    if y not in seen and y not in blocked:
                        seen.add(y)
                        q.append(y)
            out[s] = seen
        return out

    def score(blocked, weighted: bool):
        """越大越好（返回负的受害总量）。"""
        r = reach(nodes, prop, blocked)
        if weighted:
            tot = sum(w.get(s, 0) * (1 + len(v)) for s, v in r.items())
        else:
            tot = sum(1 + len(v) for v in r.values())
        return -tot

    deg = Counter({a: len(v) for a, v in prop.items()})
    pool = [n for n, _ in deg.most_common(300)]

    def greedy(k, weighted, cand):
        blocked, chosen = set(), []
        base = score(blocked, weighted)
        for _ in range(k):
            best, bv = None, base
            for c in cand:
                if c in blocked:
                    continue
                v = score(blocked | {c}, weighted)
                if v > bv:
                    bv, best = v, c
            if best is None:
                break
            blocked.add(best)
            chosen.append(best)
            base = bv
        return chosen, base

    # ---- 1) 加权 vs 未加权 ----
    print(f"\n  ── 1) 加权 vs 未加权（k=1,3,5,10,20）──")
    out_rows = {}
    for tag, wtd in (("未加权", False), ("加权", True)):
        base = score(set(), wtd)
        rows = []
        print(f"\n     【{tag}】基线 {base:.0f}")
        for k in (1, 3, 5, 10, 20):
            ch, val = greedy(k, wtd, pool)
            gain = (val - base) / abs(base) * 100
            rows.append({"k": k, "chosen": ch, "gain_pct": gain})
            print(f"       k={k:<3} 改善 {gain:>6.2f}%   "
                  f"{[base_name(c)[:26] for c in ch[:3]]}"
                  f"{'…' if len(ch) > 3 else ''}")
        out_rows[tag] = rows

    print(f"\n     ── 名单差异（k=10）──")
    A = set(out_rows["未加权"][3]["chosen"])
    B = set(out_rows["加权"][3]["chosen"])
    print(f"       未加权独有: {[base_name(x) for x in sorted(A - B)][:6]}")
    print(f"       加权独有  : {[base_name(x) for x in sorted(B - A)][:6]}")
    print(f"       共同      : {[base_name(x) for x in sorted(A & B)]}")

    # ---- 2) 暴力搜索验证 ----
    print(f"\n  ── 2) 暴力搜索验证（加权目标，60 节点子图）──")
    sub = pool[:60]
    subset = set(sub)
    se = [(a, b) for a, b in edges if a in subset and b in subset]
    sdep, sprop = defaultdict(list), defaultdict(list)
    for a, b in se:
        sdep[a].append(b)
        sprop[b].append(a)
    sw = Counter()
    for r in roots:
        seen, q = set([r]), deque([r])
        while q:
            x = q.popleft()
            for y in sdep.get(x, ()):
                if y not in seen:
                    seen.add(y)
                    q.append(y)
        for n in seen:
            if n in subset:
                sw[n] += 1

    # ⚠️ 加权目标里"受害者总量"包含**种子自身**的权重，
    #    所以即使封锁全部节点也不会归零 ⇒ 比较应针对
    #    **可改善部分**（基线 - 最优），而不是绝对值。
    def sscore(blocked):
        r = reach(sub, sprop, blocked)
        return sum(sw.get(s, 0) * (1 + len(v)) for s, v in r.items())

    sbase = sscore(set())
    for k in (1, 2, 3):
        be, bx = 1e18, None
        for comb in itertools.combinations(sub, k):
            v = sscore(set(comb))
            if v < be:
                be, bx = v, comb
        # 子图贪心（最小化受害量）
        blocked, chosen = set(), []
        cur = sbase
        for _ in range(k):
            best, bv = None, cur
            for c in sub:
                if c in blocked:
                    continue
                v = sscore(blocked | {c})
                if v < bv:
                    bv, best = v, c
            if best is None:
                break
            blocked.add(best)
            chosen.append(best)
            cur = bv
        gain_opt = sbase - be
        gain_grd = sbase - cur
        ratio_s = (f"达最优比例 {gain_grd/gain_opt:.4f}"
                   if gain_opt > 0 else "n/a（无可改善空间）")
        print(f"     k={k}: 穷举最优受害 {be:.0f}  贪心 {cur:.0f}  "
              f"（基线 {sbase:.0f}）  {ratio_s}")
        if k == 1 and bx:
            print(f"          穷举选中: {base_name(bx[0])[:34]}")
            print(f"          贪心选中: {base_name(chosen[0])[:34] if chosen else '—'}")

    # ---- 3) 三个常见直觉 ----
    print(f"\n  ── 3) 三个常见直觉 vs 贪心（加权，k=10）──")
    own = defaultdict(set)
    with open(CLEAN / "maintainers.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            own[r["maintainer"]].add(r["package"])
    mpk = {p for _, v in sorted(own.items(), key=lambda kv: -len(kv[1]))[:3]
           for p in v}
    intu = {
        "A 被依赖最多": pool[:10],
        "B 维护者掌握包最多者的包": [n for n in nodes
                                     if base_name(n) in mpk][:10],
        "C 旧版本(0/1/2.x)": sorted(
            [n for n in nodes if re.search(r"@(0|1|2)\.", n)],
            key=lambda n: -deg.get(n, 0))[:10],
    }
    wbase = score(set(), True)
    g10 = "%.2f" % out_rows["加权"][3]["gain_pct"]
    print(f"     贪心 k=10（加权）: {g10}%")
    for label, S in intu.items():
        if not S:
            print(f"     {label:<26} 候选为空")
            continue
        v = (score(set(S), True) - wbase) / abs(wbase) * 100
        print(f"     {label:<26} {v:>6.2f}%")

    # ---- 出图 ----
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    ax = axes[0]
    ks = [r["k"] for r in out_rows["加权"]]
    ax.plot(ks, [r["gain_pct"] for r in out_rows["未加权"]], "o--",
            color="#7f8c8d", label="未加权（受采样偏差影响）")
    ax.plot(ks, [r["gain_pct"] for r in out_rows["加权"]], "o-",
            color="#c0392b", lw=2, label="加权（按项目数）")
    ax.set_xlabel("加固预算 k（个包）")
    ax.set_ylabel("改善（%）")
    ax.set_title("加固效果：边际递减（次模性）", fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    ax = axes[1]
    labels = ["A 被依赖\n最多", "B 维护者\n包最多", "C 旧版本", "贪心\n最优"]
    vals = []
    for S in intu.values():
        vals.append((score(set(S), True) - wbase) / abs(wbase) * 100
                    if S else 0.0)
    vals.append(out_rows["加权"][3]["gain_pct"])
    ax.bar(labels, vals, color=["#7f8c8d", "#e67e22", "#8e44ad", "#c0392b"])
    ax.set_ylabel("改善（%）")
    ax.set_title("三个常见直觉 vs 贪心最优（加权，k=10）", fontsize=12)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.1, f"{v:.1f}", ha="center", fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    f1 = FIGS / "fig5_加固优化.png"
    fig.savefig(f1, dpi=150)
    plt.close(fig)
    print(f"\n     {f1.name}")

    (RES / "q4_统计.json").write_text(json.dumps({
        "nodes": N, "edges": len(edges),
        "weight_max": int(wv.max()), "weight_ge2_frac": float((wv >= 2).mean()),
        "weight_eq1_frac": float((wv == 1).mean()),
        "rows": out_rows,
        "list_diff_k10": {"only_unweighted": sorted(A - B),
                          "only_weighted": sorted(B - A),
                          "common": sorted(A & B)},
        "intuitions": {k: v for k, v in intu.items()},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"     {RES/'q4_统计.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
