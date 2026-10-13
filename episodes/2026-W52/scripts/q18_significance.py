#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W52 · 跨学科 vs 单学科：**四项指标的显著性检验**。

## 观察到的差异（描述性）

| 指标 | 跨学科（29 族）| 单学科（398 族）|
|---|---|---|
| 模块数（中位）| 15 | 47 |
| 被跨族引用（中位）| 1 | 0 |
| 命中 `formalization.yaml` | **10%** | **26%** |
| 进 `main_results` | **10%** | **36%** |

**差异很大，但 n=29** ⇒ 必须做检验，不能凭数字大小下结论。

## 检验设计

| 指标 | 类型 | 检验 |
|---|---|---|
| 模块数 / 被引数 | 连续、重尾 | **Mann-Whitney U**（不假设正态）|
| 命中形式化 / 进主结果 | 二值 | **Fisher 精确检验** |

**并报告效应量与置信区间**（比例差的 **Wilson/Newcombe** 区间），
不只报 p 值。

## ⚠️ 必须声明的多重比较问题

四个指标 = **四次检验** ⇒ 用 **Bonferroni 校正**（α = 0.05/4 = 0.0125），
否则"找到一个显著"的概率被抬高。

用法：
    $PY q18_significance.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W52"
SRC = EP / "results" / "q17_跨学科含金量.json"
OUT = EP / "results" / "q18_显著性.json"


# ---------- 统计工具（自实现，不依赖 scipy）----------
def mann_whitney_u(a: list[float], b: list[float]) -> tuple[float, float]:
    r"""返回 (U, 正态近似 p 值，双侧，带连续性校正)。"""
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0
    comb = sorted([(v, 0) for v in a] + [(v, 1) for v in b])
    # 秩（处理并列取平均秩）
    ranks = [0.0] * len(comb)
    i = 0
    while i < len(comb):
        j = i
        while j + 1 < len(comb) and comb[j + 1][0] == comb[i][0]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[k] = avg
        i = j + 1
    r1 = sum(ranks[k] for k in range(len(comb)) if comb[k][1] == 0)
    u1 = r1 - n1 * (n1 + 1) / 2
    mu = n1 * n2 / 2
    # 并列校正的标准差
    n = n1 + n2
    from collections import Counter
    tie = Counter(v for v, _ in comb)
    tie_corr = sum(t ** 3 - t for t in tie.values())
    sd = math.sqrt(n1 * n2 / 12 * ((n + 1) - tie_corr / (n * (n - 1))))
    if sd == 0:
        return u1, 1.0
    z = (abs(u1 - mu) - 0.5) / sd
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return u1, min(1.0, p)


def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    r"""2x2 表 [[a,b],[c,d]] 的双侧 Fisher 精确检验 p 值。"""
    from math import comb

    def hyper(k):
        return (comb(a + b, k) * comb(c + d, a + c - k)
                / comb(a + b + c + d, a + c))

    n = a + b + c + d
    lo = max(0, a + c - (c + d))
    hi = min(a + b, a + c)
    p0 = hyper(a)
    tot = 0.0
    for k in range(lo, hi + 1):
        pk = hyper(k)
        if pk <= p0 * (1 + 1e-9):
            tot += pk
    return min(1.0, tot)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def main() -> int:
    print("=" * 96)
    print("  W52 · 跨学科 vs 单学科：显著性检验")
    print("=" * 96)

    d = json.loads(SRC.read_text(encoding="utf-8"))
    rows = d["rows"]
    A, B = rows["cross"], rows["mono"]
    nA, nB = A["n"], B["n"]
    print(f"\n  跨学科族 n={nA}   单学科族 n={nB}")

    ALPHA = 0.05 / 4          # Bonferroni（四次检验）
    print(f"  Bonferroni 校正后 α = 0.05/4 = **{ALPHA:.4f}**")

    res = {}

    # ---- 1/2 连续：Mann-Whitney ----
    for key, label in (("mods", "模块数"), ("cited", "被跨族引用次数")):
        u, p = mann_whitney_u(A[key], B[key])
        import statistics
        mA, mB = statistics.median(A[key]), statistics.median(B[key])
        sig = "**显著**" if p < ALPHA else "不显著"
        print(f"\n  [{label}] Mann-Whitney U")
        print(f"     中位：跨学科 {mA:.0f}  vs  单学科 {mB:.0f}")
        print(f"     U = {u:.0f}   p = {p:.4f}   => {sig}")
        res[key] = {"median_cross": mA, "median_mono": mB,
                    "U": u, "p": p, "significant": p < ALPHA}

    # ---- 3/4 二值：Fisher ----
    for key, label in (("formal", "命中 formalization.yaml"),
                       ("main", "进 main_results")):
        a, b = A[key], nA - A[key]
        c, dd = B[key], nB - B[key]
        p = fisher_exact(a, b, c, dd)
        pa, pb = a / nA, c / nB
        la, ha = wilson(a, nA)
        lb, hb = wilson(c, nB)
        sig = "**显著**" if p < ALPHA else "不显著"
        print(f"\n  [{label}] Fisher 精确检验")
        print(f"     跨学科 {a}/{nA} = {pa*100:.1f}%  95%CI "
              f"[{la*100:.1f}, {ha*100:.1f}]")
        print(f"     单学科 {c}/{nB} = {pb*100:.1f}%  95%CI "
              f"[{lb*100:.1f}, {hb*100:.1f}]")
        print(f"     比值（单/跨）= {(pb/pa if pa else float('inf')):.1f} 倍")
        print(f"     p = {p:.4f}   => {sig}")
        res[key] = {"cross": a, "n_cross": nA, "mono": c, "n_mono": nB,
                    "p_cross": pa, "p_mono": pb, "p": p,
                    "significant": p < ALPHA,
                    "ci_cross": [la, ha], "ci_mono": [lb, hb]}

    # ---- 结论 ----
    n_sig = sum(1 for v in res.values() if v["significant"])
    print(f"\n  == 结论 ==")
    print(f"     四项检验中 **{n_sig} 项显著**（Bonferroni α={ALPHA:.4f}）")
    for k, v in res.items():
        mark = "**显著**" if v["significant"] else "不显著"
        print(f"       {k:<8} p={v['p']:.4f}  {mark}")

    print(f"\n  [!] 局限：n={nA} 的组太小，**即使不显著也不能断言「无差异」**"
          f"（可能是功效不足）。")

    OUT.write_text(json.dumps({"alpha": ALPHA, "n_cross": nA,
                               "n_mono": nB, "results": res},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
