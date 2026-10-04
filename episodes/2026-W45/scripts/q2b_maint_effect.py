#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W45 · 维护者层的放大效应：**大样本重测**（之前测不出来，是样本不够）。

## 问题

`q2_cascade.py` 里 p_maint 从 0 扫到 1，均值只在 **23.4 → 24.9** 之间抖动，
而单点标准差远大于这个差 —— **等于没测出来**。

## 为什么要认真测这个

选题卡里我**已经因为它改过一次结论**：
> 小样本（20 个流行包）里只有 2/46 位维护者管多包 ⇒ 我写"放大主要来自依赖层"；
> 扩样到 60 个高被依赖包 ⇒ **16/79 = 20.3%** 管多包，且有 Babel 三件套同属一小群人
> ⇒ **推翻**，改成"维护者层不可忽略"。

**但"有重叠"不等于"有放大"** —— 必须用模拟量化。

## 做法（提高统计功效）

* **多种子**：不再只用"入度最高"一个种子，而是从一个**固定种子集合**里抽样
* **多重复**：每个 p_maint 跑足够多次
* **配对比较**：同一批种子在两个条件下各跑一遍，**做配对差**（消除种子间方差）
* 报告**差值 + 标准误 + 配对 t 统计量**，而不是只看均值

用法：
    $PY q2b_maint_effect.py [每组重复次数，默认 120]
"""
from __future__ import annotations

import csv
import json
import math
import random
import sys
from collections import Counter, defaultdict
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


def load_graph():
    d = json.loads(SRC.read_text(encoding="utf-8"))
    drop = {n for n in d["nodes"] if ACTION_RE.match(n)}
    nodes = [n for n in d["nodes"] if n not in drop]
    edges = [(a, b) for a, b in d["edges"]
             if a not in drop and b not in drop]
    return nodes, edges


def load_maintainers():
    p = CLEAN / "maintainers.csv"
    own = defaultdict(set)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            own[row["maintainer"]].add(row["package"])
    return {k: v for k, v in own.items() if len(v) > 1}


def sim(seed, up, p, rng, owner_of=None, maint=None, p_maint=0.0,
        nodeset=frozenset(), cap=100_000):
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
            if p_maint > 0 and owner_of is not None:
                for m in owner_of.get(base_name(x), ()):
                    if rng.random() < p_maint:
                        for z in maint.get(m, ()):
                            if z not in infected and z in nodeset:
                                infected.add(z)
                                nxt.append(z)
        frontier = nxt
    return len(infected) - 1


def main() -> int:
    n_rep = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    nodes, edges = load_graph()
    nodeset = frozenset(nodes)
    up = defaultdict(list)
    indeg = Counter()
    for a, b in edges:
        up[b].append(a)
        indeg[b] += 1

    maint = load_maintainers()
    owner_of = defaultdict(set)
    for m, pkgs in maint.items():
        for pk in pkgs:
            owner_of[pk].add(m)

    print("=" * 92)
    print("  W45 · 维护者层放大效应（配对比较，提高统计功效）")
    print("=" * 92)
    print(f"\n  维护者层：{len(maint)} 位维护多包者，"
          f"涉及 {len({p for v in maint.values() for p in v})} 个包名")
    for m, pkgs in sorted(maint.items(), key=lambda kv: -len(kv[1]))[:5]:
        print(f"     {m[:24]:<26}{len(pkgs)} 个包")

    # 种子池：从"被依赖较多"的包里取，保证级联非平凡
    pool = [n for n, _ in indeg.most_common(400)]
    rng = random.Random(20260928)

    print(f"\n  每组重复 {n_rep} 次（配对：同一批种子在两种条件下各跑一次）")
    print(f"\n  {'p':>6}{'p_maint':>9}{'均值':>10}{'差(配对)':>11}"
          f"{'标准误':>9}{'t':>7}{'显著':>7}")

    rows = []
    for p in (0.2, 0.1, 0.05):
        for pm in (0.0, 0.5, 1.0):
            # 配对：同一批种子重复
            seeds = [rng.choice(pool) for _ in range(n_rep)]
            rng_base = random.Random(12345)
            base = [sim(s, up, p, rng_base, owner_of=owner_of, maint=maint,
                        p_maint=0.0, nodeset=nodeset) for s in seeds]
            rng_t = random.Random(12345)
            treat = [sim(s, up, p, rng_t, owner_of=owner_of, maint=maint,
                         p_maint=pm, nodeset=nodeset) for s in seeds]
            diffs = [t - b for t, b in zip(treat, base)]
            mb = sum(base) / len(base)
            md = sum(diffs) / len(diffs)
            sd = math.sqrt(sum((d - md) ** 2 for d in diffs)
                           / max(1, len(diffs) - 1))
            se = sd / math.sqrt(len(diffs)) if diffs else 0.0
            t = md / se if se > 0 else 0.0
            sig = "**是**" if abs(t) > 2 else "否"
            print(f"  {p:>6.2f}{pm:>9.2f}{mb:>10.2f}{md:>11.2f}"
                  f"{se:>9.3f}{t:>7.2f}{sig:>7}")
            rows.append({"p": p, "p_maint": pm, "base_mean": mb,
                         "paired_diff": md, "se": se, "t": t,
                         "significant": abs(t) > 2})

    # ---- 结论 ----
    print("\n  ── 判定 ──")
    sig_pos = [r for r in rows if r["significant"] and r["paired_diff"] > 0]
    if not sig_pos:
        verdict = ("维护者层**没有可测出的放大效应**"
                   "（所有配对差的 |t| < 2）")
    else:
        best = max(sig_pos, key=lambda r: r["paired_diff"])
        amp = best["base_mean"] + best["paired_diff"]
        verdict = (f"维护者层**有**可测出的放大：p={best['p']}, "
                   f"p_maint={best['p_maint']} 时均值 "
                   f"{best['base_mean']:.2f} → {amp:.2f}"
                   f"（+{best['paired_diff']:.2f}，"
                   f"{best['paired_diff']/max(best['base_mean'],1e-9)*100:.1f}%）")
    print(f"     {verdict}")

    # ---- 为什么？结构诊断 ----
    print("\n  ── 结构诊断：维护者层的边落在哪 ──")
    total_new = 0
    for m, pkgs in maint.items():
        # 该维护者的包在"依赖图上游可达"里是否已互相覆盖
        overlap = 0
        for x in pkgs:
            rx = set()
            stack = list(up.get(x, ()))
            while stack:
                y = stack.pop()
                if y in rx:
                    continue
                rx.add(y)
                stack.extend(up.get(y, ()))
            if rx & (pkgs - {x}):
                overlap += 1
        print(f"     {m[:24]:<26}{len(pkgs)} 个包，"
              f"其中 {overlap} 个的上游已包含同维护者的其他包")
        total_new += len(pkgs) - overlap
    print(f"\n     ⇒ 维护者层理论上最多带来 {total_new} 个**新**感染节点"
          f"（其余已被依赖层覆盖）")

    out = {"n_rep": n_rep, "rows": rows, "verdict": verdict,
           "maint_count": len(maint), "rows_note": "paired comparison"}
    (RES / "q2b_维护者层.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {RES/'q2b_维护者层.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
