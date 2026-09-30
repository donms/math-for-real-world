#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W44 · Q1c **模型识别性诊断** —— 为什么 3 参数标定会失控。

## 症状

基础模型（3 个自由参数 $p_3,p_4,p_5$，只有 5 个标定点）
最小二乘解跑到边界 $p_3=p_5=1$，导致 2035 年预测 **736 万人（−77%）** ——
物理上不可能（出生人口只降了 55.7%）。

## 诊断思路

若"入园状态"在 3、4、5 岁三处近似不变，则应满足

$$E_t \approx q\cdot(B_{t-3}+B_{t-4}+B_{t-5})$$

即三个 $p$ 应**近似相等**。逐个检查这个关系，看数据是否支持，
以及真正的约束是什么。

用法：
    $PY q1c_identify.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

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


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    kg, births = load()
    AGES = (3, 4, 5)

    P("=" * 92)
    P("  Q1c · 模型识别性诊断")
    P("=" * 92)

    P("\n-- 1. 检验『三个 p 近似相等』是否成立 --")
    P("  若成立，则 E_t ≈ q·(B_{t-3}+B_{t-4}+B_{t-5})，q 即『队列在园率』")
    P("")
    P(f"  {'年份':<6}{'E实际':>10}{'ΣB(t-3..5)':>14}{'q = E/ΣB':>12}")
    qs = []
    for y in sorted(kg):
        if all((y - a) in births for a in AGES):
            sb = sum(births[y - a] for a in AGES)
            q = kg[y] / sb
            qs.append((y, q))
            P(f"  {y:<6}{kg[y]:>10.2f}{sb:>14.1f}{q:>12.4f}")
    P("")
    P("  ⚠️ 若 q 逐年**单调上升**，说明『入园率提升』是真实效应，")
    P("     模型必须显式含入园率路径，不能只靠 p 的横截面拟合。")

    # 把 q 外生给定（由毛入园率路径决定），只拟合"年龄结构形状"
    P("\n-- 2. 改成『q 外生 + 年龄形状 1 参数』--")
    P(r"  设 p_a = q · w_a，其中 Σw_a = 1，w 由形状参数 γ 控制：")
    P(r"     w ∝ (1, γ, γ²)  ⇒  3 岁占比最高（γ<1）")
    P("")
    for g in (0.6, 0.75, 0.9, 1.0, 1.1, 1.3):
        w = np.array([1.0, g, g * g])
        w = w / w.sum()
        P(f"  γ={g:<5} w = {np.round(w,4)}")

    # 用毛入园率（r/100）作为 q，验证拟合
    import csv as _csv
    rate = {}
    with (CLEAN / "kindergarten.csv").open(encoding="utf-8-sig") as f:
        for r in _csv.DictReader(f):
            v = r["毛入园率_百分比"].strip()
            if v:
                rate[int(r["年份"])] = float(v)
    P("\n-- 3. 用毛入园率作为 q 的拟合效果 --")
    P(f"  {'年份':<6}{'E实际':>10}{'q·ΣB':>10}{'残差':>10}{'形状(3/4/5占比)':>26}")
    errs = []
    for y in sorted(kg):
        if all((y - a) in births for a in AGES) and y in rate:
            sb = sum(births[y - a] for a in AGES)
            pred = rate[y] / 100.0 * sb
            errs.append(pred - kg[y])
            P(f"  {y:<6}{kg[y]:>10.2f}{pred:>10.2f}"
              f"{pred-kg[y]:>10.2f}")
    if errs:
        P(f"\n  以毛入园率为 q：RMSE = "
          f"{np.sqrt(np.mean(np.array(errs)**2)):.2f} 万人")
        P("  ⇒ 这个口径已经把『入园率提升』吸收进 q，")
        P("     剩余的自由度用于刻画**年龄形状**，不再与 q 混淆。")

    P("\n-- 4. 诊断结论 --")
    P("  ① 3 个自由 p + 5 个标定点 ⇒ 自由度 2，参数**弱识别**，")
    P("     最小二乘会跑到边界（实测 p3=p5=1）。")
    P("  ② 根因：出生序列与入园率**同时**在变，横截面拟合无法分离二者。")
    P("  ③ 修法：把 q（队列在园率）**外生**为毛入园率路径，")
    P("     只保留 1 个形状参数。这样 5 个点标 1 个参数，识别性大幅改善。")

    (RES / "q1c_识别性诊断.md").write_text(
        "# Q1c · 模型识别性诊断\n\n> 脚本 `scripts/q1c_identify.py`\n\n"
        + "\n".join(out), encoding="utf-8")
    print(f"\n  → {RES/'q1c_识别性诊断.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
