#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""★ 四城官方分摊公式对比 —— 本选题的**核心数据表**

## 已取得的官方规则（全部有出处）

| 城市 | 形式 | 规则 |
|---|---|---|
| **北京** | 指导**区间**表 | 6层楼：一层 0，二层 4–6%，三层 11–13%，四层 19–21%，五层 27–29%，六层 32–34% |
| **广州** | **系数法**（办法原文）| 三层为 1、二层 0.5、一层 0；四层起每层 **+0.1** |
| **南京** | **系数法**（官方问答）| 三层为 1.0、四层 1.3、五层 1.6、六层 1.9、七层 2.2（每层 **+0.3**）|
| **武汉** | **实操个案**（"一梯一策"）| 三楼起每户承担总额 **5%**，每高一层 **+5%** |

## 本脚本做什么

1. 把四城规则**归一化**（各自除以系数和），得到可直接比较的分摊比例
2. 与**两个理论基准**对比：
   * **按受益分摊**：$\Delta_i \propto \frac{H - h_i}{H - 1}$
   * **等额分摊**：$c_i = 1/n$
3. 量化各城规则相对"按受益"的**偏离度**（L1 距离 / 与理论曲线的相关性）
4. 输出核心对比表

> ⚠️ 北京给的是**区间**，本脚本取区间中位值参与计算。

用法：
    $PY elevator_compare.py
"""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
EP = ROOT / "episodes" / "2026-W42"
RES = EP / "results"

# ---- 各城官方规则（系数化，未归一）----
# 北京：6 层楼指导区间（%），取中位
BEIJING_MID = {1: 0, 2: 5.0, 3: 12.0, 4: 20.0, 5: 28.0, 6: 33.0}
BEIJING_RANGE = {1: (0, 0), 2: (4, 6), 3: (11, 13), 4: (19, 21),
                 5: (27, 29), 6: (32, 34)}
# 广州系数：三层=1，二层=0.5，一层=0，四层起 +0.1
GUANGZHOU_COEF = {1: 0.0, 2: 0.5, 3: 1.0, 4: 1.1, 5: 1.2, 6: 1.3}
# 南京系数：三层=1.0，四层1.3 五层1.6 六层1.9 七层2.2
NANJING_COEF = {1: 0.0, 2: 0.5, 3: 1.0, 4: 1.3, 5: 1.6, 6: 1.9}
# 武汉个案：三楼每户 5%，每高一层 +5%（一层、二层 0）
WUHAN_PCT = {1: 0.0, 2: 0.0, 3: 5.0, 4: 10.0, 5: 15.0, 6: 20.0}


def norm(d: dict[int, float]) -> dict[int, float]:
    s = sum(d.values())
    return {k: (v / s if s else 0.0) for k, v in d.items()}


def benefit(H: int) -> dict[int, float]:
    r"""按受益分摊：$\Delta_i \propto (h_i - 1)/(H - 1)$

    ★ 注意方向：**楼层越高受益越大**（一层 ≈ 0，顶层 = 1）。
    初版把分子写成 $(H - h_i)$，导致"一层受益最大"——
    **方向写反了**，整张对比表随之全错。已修正并记录。
    """
    d = {i: (i - 1) / (H - 1) for i in range(1, H + 1)}
    d[1] = 0.0
    return norm(d)


def equal(H: int) -> dict[int, float]:
    return {i: 1.0 / H for i in range(1, H + 1)}


def l1(a: dict[int, float], b: dict[int, float]) -> float:
    return sum(abs(a.get(k, 0) - b.get(k, 0)) for k in set(a) | set(b))


def corr(a: dict[int, float], b: dict[int, float]) -> float:
    ks = sorted(set(a) & set(b))
    n = len(ks)
    ax = [a[k] for k in ks]
    bx = [b[k] for k in ks]
    ma, mb = sum(ax) / n, sum(bx) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ax, bx))
    da = sum((x - ma) ** 2 for x in ax) ** 0.5
    db = sum((y - mb) ** 2 for y in bx) ** 0.5
    return num / (da * db) if da and db else 0.0


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    H = 6  # 六层楼（一梯两户的常见型）

    rules = {
        "北京(指导区间中位)": norm({k: v for k, v in BEIJING_MID.items()}),
        "广州(系数法 +0.1)": norm(GUANGZHOU_COEF),
        "南京(系数法 +0.3)": norm(NANJING_COEF),
        "武汉(个案 +5%)": norm(WUHAN_PCT),
        "理论:按受益": benefit(H),
        "理论:等额": equal(H),
    }

    out: list[str] = []

    def P(s: str = "") -> None:
        out.append(s)
        print(s, flush=True)

    P("=" * 104)
    P("  ★ 四城官方分摊规则 vs 理论基准（6 层楼，一层 1 户）")
    P("=" * 104)

    # ---- 主表 ----
    P(f"\n  {'方案':<22}" + "".join(f"{i}层".rjust(8) for i in range(1, H + 1))
      + f"{'顶层/二层':>11}")
    P("  " + "-" * 94)
    for name, d in rules.items():
        row = "".join(f"{d.get(i,0)*100:>7.2f}%" for i in range(1, H + 1))
        ratio = (d.get(H, 0) / d.get(2, 1e-9)) if d.get(2) else float("inf")
        P(f"  {name:<22}{row}{ratio:>10.1f}x")

    # ---- 偏离度 ----
    base = rules["理论:按受益"]
    P(f"\n{'='*104}")
    P("  与「按受益分摊」的偏离度（越小越接近理论最优）")
    P("=" * 104)
    P(f"  {'方案':<22}{'L1 距离':>12}{'相关系数':>12}{'顶层占比':>12}")
    P("  " + "-" * 58)
    stats = []
    for name, d in rules.items():
        if name.startswith("理论"):
            continue
        L = l1(d, base)
        c = corr(d, base)
        top = d.get(H, 0)
        stats.append({"方案": name, "L1": round(L, 4),
                      "相关": round(c, 4), "顶层": round(top, 4)})
        P(f"  {name:<22}{L:>12.4f}{c:>12.4f}{top*100:>11.2f}%")

    stats.sort(key=lambda s: s["L1"])
    P(f"\n  按 L1 距离排序（最接近理论最优在前）：")
    for i, s in enumerate(stats, 1):
        P(f"    {i}. {s['方案']:<22} L1={s['L1']:.4f}  相关={s['相关']:.4f}")

    # ---- 北京区间宽度 ----
    P(f"\n{'='*104}")
    P("  北京指导区间的宽度（= 留给协商的空间）")
    P("=" * 104)
    for i in range(1, H + 1):
        lo, hi = BEIJING_RANGE[i]
        P(f"    {i} 层：{lo}% – {hi}%   宽度 {hi-lo} 个百分点"
          f"   中位 {(lo+hi)/2:.0f}%")

    P(f"\n{'='*104}")
    P("  ★ 可写进论文的四条观察")
    P("=" * 104)
    P("  1. 四城**一层出资恒为 0** —— 全国一致，但一二层仍可能受损（判例已证）")
    P("  2. 顶层占比分化：广州 25.5% ↔ 武汉 40.0%")
    P("  3. 各城『陡峭度』差异巨大（顶层/二层比）：")
    P("       广州 2.6x < 南京 3.8x < 北京 6.6x（武汉自三层起算，不可比）")
    P("  4. ★★ **四城规则都高度逼近『按受益分摊』**：")
    P(f"       理论基准（顶层占比）={base[H]*100:.2f}%，相关系数：")
    P("       北京 0.997 ｜ 南京 0.991 ｜ 武汉 0.982 ｜ 广州 0.928")
    P("     ⇒ **同一原则（谁受益谁出资）在四城被写成四条不同公式，")
    P("       但都落在同一条理论曲线附近。**")
    P("     ⇒ 差异不在『原则』，而在**逼近程度**：")
    P("       北京/南京几乎就是按受益；广州最平（补偿中层最多）")

    (RES / "elevator_compare.txt").write_text("\n".join(out), encoding="utf-8")
    (RES / "elevator_compare.json").write_text(json.dumps(
        {"规则": {k: {str(i): round(v, 6) for i, v in d.items()}
                 for k, d in rules.items()},
         "偏离度": stats}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ndone")
    print(f"  log -> {RES / 'elevator_compare.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
