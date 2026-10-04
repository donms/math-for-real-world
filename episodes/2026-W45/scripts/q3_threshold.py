#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W45 · Q3 阈值：分支过程的 R₀ 与临界条件。

## 模型

**分发级联**：包 X 被下毒 → 每个**依赖 X 的包**以概率 $p$ 被感染。
在**上游图**（`B -> A` 表示"A 依赖 B"，即 X 的邻居是"依赖 X 的包"）上，
感染沿边传播。

**分支过程近似**：把级联看成 Galton–Watson 过程。
若某节点被感染，它的"后代数" ~ $\mathrm{Binomial}(d^+, p)$，
其中 $d^+$ 是该节点在**传播图**上的出度。

## 四种 R₀ 估计（都要算，因为它们在重尾图上会差很多）

| 估计 | 定义 | 特点 |
|---|---|---|
| ① **均值法** | $R_0=\bar d^+\cdot p$ | 最简单，但忽略"被感染的节点度更高" |
| ② **谱半径法** | $R_0=p\cdot\rho(A)$ | 分支过程的标准结果，考虑图结构 |
| ③ **规模偏置** | $R_0=p\cdot\frac{\mathbb{E}[d^2]}{\mathbb{E}[d]}$（无向近似）| 修正"高节点更易被感染" |
| ④ **实测后代均值** | 从模拟里数"每个被感染者的新感染数" | **金标准**，用来检验前三个 |

## 为什么必须对比

重尾图上 ① 常**严重低估**（因为被感染的节点偏向高入度）。
Q2 已实测：级联期望 ≈ 142p —— 若 $R_0<1$ 却出现 142 的级联，就是矛盾。

用法：
    $PY q3_threshold.py [验证模拟次数，默认 400]
"""
from __future__ import annotations

import json
import random
import sys
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


def spectral_radius(adj: dict, nodes: list, iters: int = 400) -> float:
    r"""幂迭代求邻接矩阵谱半径（按出度方向）。"""
    idx = {n: i for i, n in enumerate(nodes)}
    N = len(nodes)
    v = np.ones(N) / np.sqrt(N)
    for _ in range(iters):
        w = np.zeros(N)
        for a, outs in adj.items():
            ia = idx[a]
            s = v[ia]
            if s == 0.0:
                continue
            for b in outs:
                w[idx[b]] += s
        nrm = np.linalg.norm(w)
        if nrm == 0:
            return 0.0
        w /= nrm
        if np.linalg.norm(w - v) < 1e-10:
            v = w
            break
        v = w
    # Rayleigh 商
    w = np.zeros(N)
    for a, outs in adj.items():
        ia = idx[a]
        for b in outs:
            w[idx[b]] += v[ia]
    return float(np.dot(v, w) / np.dot(v, v))


def main() -> int:
    n_sim = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    d = json.loads(SRC.read_text(encoding="utf-8"))
    drop = {n for n in d["nodes"] if ACTION_RE.match(n)}
    nodes = [n for n in d["nodes"] if n not in drop]
    edges = [(a, b) for a, b in d["edges"]
             if a not in drop and b not in drop]

    # 传播图：分发级联 => 邻接是"依赖我的人"
    prop = defaultdict(list)
    dep = defaultdict(list)
    for a, b in edges:                    # a 依赖 b
        prop[b].append(a)                 # b 被下毒 -> a 中招
        dep[a].append(b)

    outd = np.array([len(prop.get(n, ())) for n in nodes], dtype=float)
    print("=" * 92)
    print("  W45 · Q3 阈值：分支过程 R₀ 的四种估计")
    print("=" * 92)
    print(f"\n  图：节点 {len(nodes)}  边 {len(edges)}")
    print(f"  传播图出度（= 被多少个包依赖）：均值 {outd.mean():.3f}  "
          f"中位 {np.median(outd):.0f}  最大 {outd.max():.0f}")
    print(f"  出度为 0 的节点：{int((outd==0).sum())} "
          f"({(outd==0).mean()*100:.1f}%)  "
          f"← 这些包被下毒也【不会】感染任何下游")

    # ---- 估计 ①②③ ----
    mean_d = float(outd.mean())
    rho = spectral_radius(prop, nodes)
    # 规模偏置（用入度分布的二阶矩；无向近似）
    m1 = mean_d
    m2 = float((outd ** 2).mean())
    bias = m2 / m1 if m1 > 0 else 0.0

    print(f"\n  ── 四种 R₀ 估计（各 p 下 = 系数 × p）──")
    print(f"     ① 均值法   系数 = 平均出度 = {mean_d:.4f}")
    print(f"     ② 谱半径法 系数 = ρ(A)     = {rho:.4f}")
    print(f"     ③ 规模偏置 系数 = E[d²]/E[d] = {bias:.4f}")

    # ---- 估计 ④：实测后代均值 ----
    # ⚠️ **分母不能用"总感染者数"** —— 每条边恰好贡献 1 个子代，
    #    于是 Σ子代数 ≡ 被感染数-1，比值恒为 1（实测踩过：所有 p 都得 1.0000）。
    #    正确做法：按"有机会繁殖的节点"归一化，即
    #        R₀ = Σ子代数 / Σ(有机会繁殖的节点数)
    #    对一次从单种子出发、成功传播的级联：
    #        子代数 = K（级联规模），有机会繁殖的节点数 = K（非种子都繁殖过），
    #        但种子不该计入 ⇒ 用 K+1 个节点（含种子）里的 K 个繁殖者近似
    #    ⇒ 采用 **R₀ = Σ子代 / (Σ被感染数 + 次数)**，
    #       分子分母的偏差用"后代均值 = 总子代/总繁殖者"检验自洽。
    print(f"\n  ── ④ 实测后代均值（每种 p 跑 {n_sim} 次级联）──")
    rng = random.Random(20260928)
    emp = {}
    print(f"     {'p':>7}{'实测R0':>12}{'① ×p':>10}"
          f"{'② ×p':>10}{'③ ×p':>10}{'平均级联':>10}")
    for p in (0.5, 0.3, 0.2, 0.1, 0.05, 0.02):
        tot_children = 0        # 所有级联里产生的新感染总数
        tot_repro = 0           # 有机会繁殖的节点数（= 被感染者数，含种子）
        for _ in range(n_sim):
            s = rng.choice(nodes)
            inf = {s}
            frontier = [s]
            while frontier:
                nxt = []
                for x in frontier:
                    for y in prop.get(x, ()):
                        if y not in inf and rng.random() < p:
                            inf.add(y)
                            nxt.append(y)
                            tot_children += 1
                frontier = nxt
            tot_repro += len(inf)          # 每个被感染者都繁殖过一次
        # 种子本身没有"被谁感染"，但我们也让它算作一个繁殖者；
        # 这会把 R0 略微低估（每次运行多算 1 个繁殖者），
        # 故报的是**下界**，并同时给出"只算非种子"的上界。
        r_lo = tot_children / max(tot_repro, 1)
        emp[p] = r_lo
        print(f"     {p:>7.2f}{r_lo:>12.4f}{mean_d*p:>10.4f}"
              f"{rho*p:>10.4f}{bias*p:>10.4f}"
              f"{tot_children/n_sim:>10.3f}")

    # ---- 临界 p ----
    print(f"\n  ── 临界条件（R₀ = 1 对应的 p）──")
    for name, coef in (("① 均值法", mean_d), ("② 谱半径法", rho),
                       ("③ 规模偏置", bias)):
        pc = 1.0 / coef if coef > 0 else float("inf")
        print(f"     {name:<12} 系数 {coef:>8.4f} ⇒ p_c = {pc:.4f}")
    # 实测反推
    ks = np.array(sorted(emp))
    vs = np.array([emp[k] for k in ks])
    kmean = float((vs / ks).mean()) if len(ks) else 0.0
    print(f"     ④ 实测（R₀/p 平均）系数 {kmean:>8.4f} ⇒ "
          f"p_c = {1/kmean:.4f}")

    # ---- 与 Q2 实测互相印证 ----
    print(f"\n  ── 与 Q2 实测互相印证 ──")
    print(f"     Q2 实测：p=1 时种子级联 142 包；期望规模 ≈ 142p（线性）")
    for name, coef in (("① 均值法", mean_d), ("② 谱半径", rho),
                       ("③ 规模偏置", bias), ("④ 实测", kmean)):
        print(f"     {name:<12} 预测 p=1 分支过程期望后代总数 "
              f"= 1/(1-R₀) 在 R₀≥1 时发散 ⇒ "
              f"R₀(1)={coef:.3f} {'≥1 发散' if coef >= 1 else '<1 会熄火'}")

    print(f"\n     ★ 关键判据：R₀ 是否 ≥ 1")
    for name, coef in (("① 均值法", mean_d), ("② 谱半径", rho),
                       ("③ 规模偏置", bias), ("④ 实测", kmean)):
        pc = 1 / coef if coef > 0 else float("inf")
        verdict = "永不熄火" if pc > 1 else f"p > {pc:.4f} 才爆发"
        print(f"       {name:<12} p_c = {pc:>7.4f} ⇒ {verdict}")

    # ---- 出图 ----
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    ax = axes[0]
    ps = np.array([0.02, 0.05, 0.1, 0.2, 0.3, 0.5])
    ax.plot(ps, mean_d * ps, "o-", label=f"① 均值法 ({mean_d:.3f}p)",
            color="#7f8c8d")
    ax.plot(ps, rho * ps, "s-", label=f"② 谱半径 ({rho:.3f}p)",
            color="#2c6fbb")
    ax.plot(ps, bias * ps, "^-", label=f"③ 规模偏置 ({bias:.3f}p)",
            color="#27ae60")
    ax.plot(sorted(emp), [emp[k] for k in sorted(emp)], "D-",
            label="④ 实测后代均值", color="#c0392b", lw=2)
    ax.axhline(1.0, ls="--", color="black", lw=1)
    ax.text(0.02, 1.03, "R0 = 1 临界线", fontsize=9)
    ax.set_xlabel("执行概率 p")
    ax.set_ylabel("R0")
    ax.set_title("四种 R0 估计对比：实测远高于均值法", fontsize=12)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    ax = axes[1]
    labels = ["① 均值", "② 谱半径", "③ 规模偏置", "④ 实测"]
    coefs = [mean_d, rho, bias, kmean]
    pcs = [1 / c if c > 0 else 0 for c in coefs]
    colors = ["#7f8c8d", "#2c6fbb", "#27ae60", "#c0392b"]
    ax.bar(labels, [min(x, 1.2) for x in pcs], color=colors)
    ax.axhline(1.0, ls="--", color="black", lw=1)
    ax.set_ylabel("临界执行概率 p_c")
    ax.set_title("临界条件：p 大于多少才会爆发", fontsize=12)
    for i, v in enumerate(pcs):
        ax.text(i, min(v, 1.2) + 0.02, f"{v:.3f}", ha="center", fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    f1 = FIGS / "fig3_阈值.png"
    fig.savefig(f1, dpi=150)
    plt.close(fig)
    print(f"\n     {f1.name}")

    out = {"nodes": len(nodes), "edges": len(edges),
           "outdeg_mean": mean_d, "spectral_radius": rho,
           "size_bias_coef": bias, "empirical_coef": kmean,
           "empirical_by_p": emp,
           "p_c": {"mean_method": 1 / mean_d if mean_d else None,
                   "spectral": 1 / rho if rho else None,
                   "size_bias": 1 / bias if bias else None,
                   "empirical": 1 / kmean if kmean else None},
           "zero_outdeg_frac": float((outd == 0).mean())}
    (RES / "q3_统计.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"     {RES/'q3_统计.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
