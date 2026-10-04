#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W45 · Q3 收尾：把 R₀ 接到**真实的 MemOS 事件**上。

## 要回答题面 Q3 第 4 小问

> 「没有证据显示已扩散」这件事，与 $R_0$ 的大小是否一致？
> 你的模型支持还是不支持这个表态？

## 关键张力（必须解释清楚）

* **平均 $R_0 < 1$**（$p_c \approx 0.58$）⇒ 从**随机一个包**出发，扩散会熄火；
* **但** Q2 实测：入度最高的包在 $p=1$ 时能波及 **142** 个包。

⇒ **$R_0$ 是平均值，掩盖了极端异质性。**
本期要量化：**R₀ 的分布**（逐节点的局部 $R_0$），以及
"有多少比例的包，其 $R_0 \ge 1$"（即**超级传播者**的比例）。

## 还要做：查真实事件里那两个包

* PyPI `MemoryOS`（被投毒的实际包）
* npm `@memtensor/memos-cloud-openclaw-plugin`

看它们在**我们的图里**是什么位置、局部 $R_0$ 多大。

用法：
    $PY q3b_superspreader.py
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
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

import re                                                    # noqa: E402
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
    prop = defaultdict(list)
    for a, b in edges:
        prop[b].append(a)

    deg = np.array([len(prop.get(n, ())) for n in nodes], dtype=float)
    print("=" * 92)
    print("  W45 · Q3 收尾：超级传播者与真实事件校验")
    print("=" * 92)

    # ---------- 1) 局部 R0 分布 ----------
    # 局部 R0(p) = p * 该节点在传播图上的出度
    print(f"\n  ── 1) 逐节点局部 R0（p = 0.2）──")
    p = 0.2
    local = p * deg
    print(f"     均值 {local.mean():.4f}  中位 {np.median(local):.4f}  "
          f"P99 {np.percentile(local,99):.2f}  最大 {local.max():.2f}")

    print(f"\n  ── 2) 『超级传播者』比例：局部 R0 ≥ 1 意味着它自己就能爆发 ──")
    print(f"     {'p':>7}{'局部R0≥1 的节点数':>20}{'占比':>10}")
    sup = {}
    for pp in (0.5, 0.3, 0.2, 0.1, 0.05, 0.02, 0.01):
        k = int((pp * deg >= 1).sum())
        sup[pp] = k
        print(f"     {pp:>7.2f}{k:>20}{k/len(nodes)*100:>9.2f}%")

    print(f"\n     ⇒ 只要 p ≥ {1/deg.max():.4f}，"
          f"出度最高的那个包（度 {int(deg.max())}）自己就 ≥1")
    print(f"        但**这样的包只有 {sup.get(0.2,0)} 个**"
          f"（p=0.2 时）⇒ 风险极度集中在少数节点")

    # ---------- 3) 真实事件校验 ----------
    print(f"\n  ── 3) 真实事件：MemOS 的两个被投毒包在我们的图里在哪？──")
    targets = ["MemoryOS", "@memtensor/memos-cloud-openclaw-plugin", "memos"]
    by_base = defaultdict(list)
    for n in nodes:
        by_base[base_name(n)].append(n)
    for t in targets:
        hits = by_base.get(t, [])
        print(f"\n     [{t}]")
        if not hits:
            print(f"       ❌ **不在本图内**（我们的 20 个仓库没有依赖它）")
            print(f"          ⇒ 这本身就是一个结论：")
            print(f"            它不在主流依赖闭包里，**扩散的起点不占结构优势**")
            continue
        for h in hits[:3]:
            dg = len(prop.get(h, ()))
            print(f"       {h}")
            print(f"          被 {dg} 个包依赖 ⇒ p=0.2 时局部 R0 = {0.2*dg:.3f}"
                  f"  {'≥1 会爆发' if 0.2*dg >= 1 else '<1 会熄火'}")

    # ---------- 4) R0 平均值 vs 尾部 ----------
    print(f"\n  ── 4) 为什么『平均 R0 < 1』与『142 包的级联』能同时成立 ──")
    print(f"     平均出度 {deg.mean():.3f} ⇒ 平均 R0(0.2) = {p*deg.mean():.3f} < 1"
          f"  ⇒ 随机包会熄火")
    print(f"     但出度分布：P90 {np.percentile(deg,90):.0f}  "
          f"P99 {np.percentile(deg,99):.0f}  最大 {deg.max():.0f}")
    print(f"     出度 ≥ 5 的包 {int((deg>=5).sum())} 个 "
          f"({(deg>=5).mean()*100:.1f}%)  ⇒ 只有它们能撑起大级联")
    print(f"     ⇒ **平均值掩盖了异质性**：R0 是『平均每次感染产生多少新感染』，")
    print(f"        但真正决定大规模爆发的是**尾部的少数节点**。")

    # ---------- 出图 ----------
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    ax = axes[0]
    dpos = deg[deg > 0]
    ax.hist(np.log10(dpos), bins=35, color="#c0392b", alpha=0.85)
    ax.axvline(np.log10(1 / p), ls="--", color="black", lw=1.5)
    ax.text(np.log10(1 / p) + 0.03, ax.get_ylim()[1] * 0.85,
            f"p={p} 时局部R0=1 的阈值\n(出度={1/p:.0f})", fontsize=9)
    ax.set_xlabel("log10(传播图出度 = 被多少个包依赖)")
    ax.set_ylabel("包数")
    ax.set_title("出度分布：只有极少数包能自我维持扩散", fontsize=12)
    ax.grid(alpha=0.3)

    ax = axes[1]
    pps = sorted(sup)
    fr = [sup[k] / len(nodes) * 100 for k in pps]
    ax.semilogx(pps, fr, "o-", color="#2c6fbb", lw=2)
    ax.set_xlabel("执行概率 p")
    ax.set_ylabel("『局部 R0 ≥ 1』的包占比（%）")
    ax.set_title("超级传播者的比例随 p 上升", fontsize=12)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    f1 = FIGS / "fig4_超级传播者.png"
    fig.savefig(f1, dpi=150)
    plt.close(fig)
    print(f"\n     {f1.name}")

    out = {"p_ref": p, "deg_mean": float(deg.mean()),
           "deg_p99": float(np.percentile(deg, 99)),
           "deg_max": float(deg.max()),
           "local_r0_mean": float(local.mean()),
           "superspreader_frac": {str(k): v / len(nodes)
                                  for k, v in sup.items()},
           "superspreader_count": {str(k): v for k, v in sup.items()},
           "p_c_single_node": float(1 / deg.max()),
           "targets_in_graph": {t: len(by_base.get(t, []))
                                for t in targets},
           "deg_ge5_frac": float((deg >= 5).mean())}
    (RES / "q3b_统计.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"     {RES/'q3b_统计.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
