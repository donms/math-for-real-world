#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W44 · Q1b 诊断：**学年切点**（8/31）对峰值年的影响。

## 问题

基础模型 $E_t=\sum_{a=3}^{5}B_{t-a}p_a$ 算出峰值在 **2021**，
而数据峰值在 **2020**（4818.26 vs 4805.21，相差仅 13 万人）。

## 根因假设

模型把"某年出生的孩子"整体当作同一年龄，但**入学按学年**划分：
* 8/31 前出生 → 满 3 周岁当年 9 月入园 ⇒ 出生年 + 3 入园
* 9/1 后出生 → 次年 9 月入园 ⇒ 出生年 + 4 入园

若出生在年内的分布均匀，则 **约 2/3 在 (出生年+3) 入园、1/3 在 (出生年+4) 入园**。

这会让**有效入园年龄整体前移**，从而把峰值年从 2021 拉向 2020。

## 做法

对切点比例 $\theta$（出生年+3 入园的比例，均匀分布时 $\theta=8/12$）
做扫描，看模型峰值年与拟合 RMSE 随 $\theta$ 的变化，
由**数据**选择 $\theta$，而不是拍一个数。

用法：
    $PY q1b_cutoff_diag.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
CLEAN = EP / "data" / "clean"
RES = EP / "results"

out: list[str] = []


def P(s: str = "") -> None:
    out.append(s)
    print(s, flush=True)


def load():
    kg, births = {}, {}
    with (CLEAN / "kindergarten.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            v = r["在园幼儿_万人"].strip()
            if v:
                kg[int(r["年份"])] = float(v)
    with (CLEAN / "births.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            births[int(r["年份"])] = float(r["出生人口_万人"])
    return kg, births


def design(ys, births, theta):
    """构造设计矩阵：列 = [3岁入园部分, 4岁入园部分, 5岁入园部分]。

    简化处理：把"出生年+a 入园"里的人再按 θ 前移一年：
    实际入园年 = 出生年+3（占 θ）或 出生年+4（占 1-θ）。
    ⇒ 在第 t 年新入园的，来自 B_{t-3} 的 θ 与 B_{t-4} 的 (1-θ)。
    之后再在园 3 年（含当年）。
    """
    # 第 t 年在园 = 第 t,t-1,t-2 年新入园之和
    A = []
    for y in ys:
        row = []
        for k in range(3):          # 在园第 k 年（0=当年入园）
            t = y - k
            # t 年新入园人数 = θ·B_{t-3} + (1-θ)·B_{t-4}
            b3 = births.get(t - 3, np.nan)
            b4 = births.get(t - 4, np.nan)
            row.append(theta * b3 + (1 - theta) * b4)
        A.append(row)
    return np.array(A, dtype=float)


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    kg, births = load()
    P("=" * 90)
    P("  Q1b · 学年切点 θ 对峰值年与拟合优度的影响")
    P("=" * 90)
    P(f"\n  在园幼儿数据年份：{sorted(kg)}")
    P(f"  出生数据年份：{sorted(births)}")

    rows = []
    for theta in [0.0, 1 / 12, 2 / 12, 3 / 12, 4 / 12, 6 / 12, 8 / 12,
                  9 / 12, 1.0]:
        ys = [y for y in sorted(kg)
              if y >= 2016 and all(np.isfinite(v)
                                   for v in design([y], births, theta)[0])]
        if len(ys) < 4:
            continue
        A = design(ys, births, theta)
        e = np.array([kg[y] for y in ys])
        r = least_squares(lambda p: A @ p - e,
                          x0=np.array([0.33, 0.33, 0.33]),
                          bounds=(np.zeros(3), np.ones(3)))
        pred = A @ r.x
        rmse = float(np.sqrt(np.mean((pred - e) ** 2)))
        # 历史峰值年（用 2018 起有 E 的年份里拟合值最大的）
        hist = {y: float(v) for y, v in zip(ys, pred)}
        yhat = max(hist, key=hist.get)
        yact = max(kg, key=kg.get)
        rows.append({"theta": theta, "n": len(ys), "p": r.x.tolist(),
                     "RMSE": rmse, "峰值年_模型": yhat, "峰值年_实际": yact,
                     "命中": yhat == yact})
        P(f"\n  θ={theta:.4f}（{theta*12:.0f}/12）　样本 {len(ys)}")
        P(f"     p = {np.round(r.x,4)}   合计 {r.x.sum():.4f}")
        P(f"     RMSE = {rmse:7.2f} 万人　峰值年 模型 {yhat} / 实际 {yact}"
          f"  {'✅' if yhat == yact else '❌'}")

    P(f"\n{'='*90}")
    P("  结论")
    P("=" * 90)
    ok = [r for r in rows if r["命中"]]
    if ok:
        best = min(ok, key=lambda r: r["RMSE"])
        P(f"  ✅ 能命中峰值年 {best['峰值年_实际']} 的 θ 有 "
          f"{len(ok)} 个；其中 RMSE 最小的：")
        P(f"     θ = {best['theta']:.4f}（{best['theta']*12:.0f}/12），"
          f"RMSE = {best['RMSE']:.2f} 万人")
        P(f"     p = {np.round(best['p'],4)}")
    else:
        P("  ❌ 没有任何 θ 能命中实际峰值年")
    P("")
    P("  参考：年内出生均匀分布 ⇒ θ ≈ 8/12 = 0.6667")

    # 存 json 供 Q1 复用
    import json
    (CLEAN / "q1b_theta_scan.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (RES / "q1b_切点诊断.md").write_text(
        "# Q1b · 学年切点诊断\n\n> 脚本 `scripts/q1b_cutoff_diag.py`\n\n"
        + "\n".join(out), encoding="utf-8")
    print(f"\n  → {RES/'q1b_切点诊断.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
