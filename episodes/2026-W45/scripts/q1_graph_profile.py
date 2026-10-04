#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W45 · Q1 定稿：剔除 CI/平台构件，只用**真软件包**重算。

## 本次要修的两个数据问题（都是自诊断发现的）

### 问题 1：GitHub Actions 混进了依赖图

曝光榜前列全是 `actions/upload-artifact`、`actions/checkout`、
`actions/setup-python` —— 这些是 **CI 工作流步骤**，**不是软件包**。
它们出现在 SBOM 里，但对"供应链蠕虫"这个问题**毫无意义**
（没人会 `import` 一个 GitHub Action）。

判定：`actions/*`、`pypa/gh-action-*`、`peter-evans/*` 等
`owner/name@<40位十六进制>` 形态的，都是 Action（用 commit SHA 钉版本）。

### 问题 2："项目曝光度"在 20 个项目下太稀疏

最大只有 **12** —— 用它排序几乎全是并列，**没有区分度**。
⇒ **降级为参考指标**，主结论改用**包图入度**（生态广度）。

## 定稿的三个口径

| 口径 | 定义 | 用途 |
|---|---|---|
| **包图入度** | 被多少个**包**依赖 | **主指标**（生态广度，稳健）|
| **下游可达** | 单树子树大小 | **参考**（受巨型树支配）|
| 项目曝光度 | 被多少个**被扫描项目**直接依赖 | 参考（样本太稀疏）|

用法：
    $PY q1_graph_profile.py
"""
from __future__ import annotations

import json
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
RES = ROOT / "results"
FIGS = RES / "figs"
RES.mkdir(parents=True, exist_ok=True)
FIGS.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

# GitHub Action：owner/name@<40 位 hex SHA>
ACTION_RE = re.compile(r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+@[0-9a-f]{40}$")


def is_action(nid: str) -> bool:
    return bool(ACTION_RE.match(nid))


def is_gh(nid: str) -> bool:
    return nid.startswith("com.github.")


def base_name(nid: str) -> str:
    if nid.startswith("@"):
        p = nid.split("@")
        return "@" + p[1] if len(p) > 1 else nid
    return nid.split("@")[0]


def gini(v: np.ndarray) -> float:
    x = np.sort(v.astype(float))
    n = x.size
    if n == 0 or x.sum() == 0:
        return 0.0
    idx = np.arange(1, n + 1)
    return float(2 * np.sum(idx * x) / (n * x.sum()) - (n + 1) / n)


def desc(a, name: str) -> dict:
    v = np.array(list(a), dtype=float)
    if v.size == 0:
        return {"name": name, "n": 0}
    return {"name": name, "n": int(v.size), "mean": float(v.mean()),
            "median": float(np.median(v)),
            "p90": float(np.percentile(v, 90)),
            "p99": float(np.percentile(v, 99)),
            "max": float(v.max()),
            "zero_frac": float((v == 0).mean()),
            "gini": gini(v)}


def main() -> int:
    d = json.loads(SRC.read_text(encoding="utf-8"))
    nodes_all = list(d["nodes"])
    edges_all = [tuple(e) for e in d["edges"]]
    roots = list(d["roots"])

    # ---------- 清洗 ----------
    actions = [n for n in nodes_all if is_action(n)]
    gh = [n for n in nodes_all if is_gh(n)]
    print("=" * 94)
    print("  W45 · Q1 建图与体检（定稿：剔除 CI/平台构件）")
    print("=" * 94)
    print(f"\n  ── 清洗 ──")
    print(f"     原始节点 {len(nodes_all)}  边 {len(edges_all)}")
    print(f"     其中 GitHub Action（CI 步骤，非软件包）: {len(actions)}")
    print(f"     其中 com.github.* 根包标记            : {len(gh)}")
    for a in sorted(actions)[:6]:
        print(f"        - {a[:66]}")
    drop = set(actions)
    # ⚠️ **不要删 `com.github.*`** —— 根包本身就是这个形式
    #    （`com.github.astral-sh/uv@main`）。全删会让闭包为空、
    #    下游可达恒为 0（实测踩过）。只删 Action 即可。
    nodes = [n for n in nodes_all if n not in drop]
    edges = [(a, b) for a, b in edges_all if a not in drop and b not in drop]
    print(f"     清洗后节点 {len(nodes)}  边 {len(edges)}"
          f"（删除 {len(nodes_all)-len(nodes)} 个 Action）")

    fwd = defaultdict(set)
    for a, b in edges:
        fwd[a].add(b)

    # ---------- 口径 1：包图入度（主指标）----------
    indeg = Counter()
    for a, b in edges:
        indeg[b] += 1
    iv = [indeg.get(n, 0) for n in nodes]
    d1 = desc(iv, "包图入度")
    print(f"\n  ── 主指标：包图入度（被多少个包依赖）──")
    print(f"     均值 {d1['mean']:.3f}  中位数 {d1['median']:.0f}  "
          f"P90 {d1['p90']:.0f}  P99 {d1['p99']:.0f}  "
          f"最大 {d1['max']:.0f}  基尼 {d1['gini']:.3f}")
    buckets = [(0, 0), (1, 1), (2, 4), (5, 9), (10, 49), (50, 10**9)]
    dist = []
    for lo, hi in buckets:
        c = sum(1 for v in iv if lo <= v <= hi)
        lab = f"{lo}" if lo == hi else (f"{lo}+" if hi > 10**8
                                        else f"{lo}-{hi}")
        dist.append({"bucket": lab, "count": c, "frac": c / len(iv)})
        print(f"     入度 {lab:<7}{c:>6}  ({c/len(iv)*100:>5.1f}%)")
    print(f"\n     被依赖最多（入度前 20）：")
    top_indeg = indeg.most_common(20)
    for n, c in top_indeg:
        print(f"       {c:>4}  {n}")

    # ---------- 口径 2：下游可达（参考）----------
    closure = {}
    for r in roots:
        if r in drop:
            continue
        seen, q = set([r]), deque([r])
        while q:
            x = q.popleft()
            for y in fwd.get(x, ()):
                if y not in seen:
                    seen.add(y)
                    q.append(y)
        closure[r] = seen
    sub_max: dict[str, int] = defaultdict(int)
    for r, cs in closure.items():
        ind2 = Counter()
        for a, b in edges:
            if a in cs and b in cs:
                ind2[b] += 1
        order, q = [], deque([x for x in cs if ind2[x] == 0])
        while q:
            x = q.popleft()
            order.append(x)
            for y in fwd.get(x, ()):
                if y in cs:
                    ind2[y] -= 1
                    if ind2[y] == 0:
                        q.append(y)
        sub = {x: set() for x in cs}
        for x in reversed(order):
            s = set()
            for y in fwd.get(x, ()):
                if y in cs:
                    s.add(y)
                    s |= sub[y]
            sub[x] = s
        for x, v in sub.items():
            if len(v) > sub_max[x]:
                sub_max[x] = len(v)
    rv = [sub_max.get(n, 0) for n in nodes]
    d2 = desc(rv, "下游可达")
    print(f"\n  ── 参考指标：下游可达（单棵依赖树内的子树大小）──")
    print(f"     均值 {d2['mean']:.2f}  中位数 {d2['median']:.0f}  "
          f"最大 {d2['max']:.0f}  基尼 {d2['gini']:.3f}")
    print(f"     ⚠️ 受巨型依赖树支配，**不作主结论**")

    # ---------- 集中度（主指标）----------
    print(f"\n  ── 『被依赖』集中度（主指标）──")
    arr = np.sort(np.array(iv, dtype=float))[::-1]
    tot = arr.sum()
    conc = {}
    for pct in (0.1, 1, 5, 10, 20):
        k = max(1, int(len(arr) * pct / 100))
        sh = float(arr[:k].sum() / tot) if tot else 0.0
        conc[pct] = sh
        print(f"     前 {pct:>4}% 的包 占被依赖总量 {sh*100:>5.1f}%")

    # ---------- 样本结构 ----------
    print(f"\n  ── 样本结构（诚实性声明用）──")
    cs_sorted = sorted(((len(v), k) for k, v in closure.items()),
                       reverse=True)[:5]
    for c, r in cs_sorted:
        print(f"     {c:>5} 节点  占清洗后 {c/len(nodes)*100:>5.1f}%  {r}")

    # ---------- 出图 ----------
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    ax = axes[0]
    v = np.array(iv, dtype=float)
    xs = np.sort(v[v > 0])
    ax.loglog(xs, 1 - np.arange(len(xs)) / len(xs), "o", ms=3,
              alpha=0.5, color="#c0392b")
    ax.set_xlabel("入度 k（被多少个包依赖）")
    ax.set_ylabel("P(K >= k)")
    ax.set_title(f"包图入度分布（双对数）\n基尼 {d1['gini']:.3f}",
                 fontsize=12)
    ax.grid(True, which="both", alpha=0.25)

    ax = axes[1]
    rank = np.arange(1, len(arr) + 1) / len(arr) * 100
    ax.plot(rank, np.cumsum(arr) / tot * 100, color="#2c6fbb", lw=2)
    ax.plot([0, 100], [0, 100], "--", color="gray", lw=1)
    ax.set_xlabel("按入度降序排列的包（前 x%）")
    ax.set_ylabel("累计占被依赖总量（%）")
    ax.set_title("『投毒收益』高度集中（洛伦兹曲线）", fontsize=12)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    f1 = FIGS / "fig1_度分布与集中度.png"
    fig.savefig(f1, dpi=150)
    plt.close(fig)
    print(f"\n     {f1.name}")

    out = {
        "clean": {"nodes_raw": len(nodes_all), "edges_raw": len(edges_all),
                  "actions_dropped": len(actions),
                  "gh_roots_dropped": len(gh),
                  "nodes": len(nodes), "edges": len(edges)},
        "in_degree": d1, "in_degree_dist": dist,
        "downstream_reach": d2,
        "top_in_degree": [[c, n] for n, c in top_indeg],
        "concentration": conc,
        "closure_top5": [[c, r] for c, r in cs_sorted],
        "merged_byname": {
            "nodes": len({base_name(n) for n in nodes}),
        },
        "actions_examples": sorted(actions)[:10],
    }
    (RES / "q1_统计.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"     {RES/'q1_统计.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
