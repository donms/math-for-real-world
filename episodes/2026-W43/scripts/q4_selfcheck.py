#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""Q3 的**决定性数值自检** —— 用解析可算的极端情形验函数。

构造一个"一眼可判"的案例：
* 补贴率 = 0 ⇒ 净造价 = C = 500,000
* κ = 1 ⇒ WTP = 净造价 ⇒ **总剩余 = 0** ⇒ 所有层基准净收益 = 0
* L1 = 120,000、L2 = 60,000，**不给补偿**（comp=0）

则一层的参与约束为 $u_1 \ge L_1$（净收益必须覆盖损失）。
当 $u_1 = 0$、$L_1 = 120{,}000$ 时 ⇒ **缺口 = 120,000**。

用法：
    $PY q4_selfcheck.py
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

EP = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "q4", EP / "scripts" / "q4_mechanisms.py")
q4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q4)

C = 500_000.0
H, PF, GAMMA = q4.H, q4.PF, q4.GAMMA
S = q4.S

print("=" * 88)
print("  决定性自检：surplus = 0 时的参与约束")
print("=" * 88)

cases = [
    ("剩余=0, 损失120k/60k, 不补偿", 0.0, 1.0, 120_000, 60_000, 0.0),
    ("剩余=0, 损失120k/60k, 全额补偿", 0.0, 1.0, 120_000, 60_000, float("inf")),
    ("剩余=0, 无损失", 0.0, 1.0, 0, 0, 0.0),
    ("剩余=30万, 损失120k/60k, 不补偿", 0.4, 2.0, 120_000, 60_000, 0.0),
    ("剩余=30万, 损失120k/60k, 全额补偿", 0.4, 2.0, 120_000, 60_000, float("inf")),
]
for name, sr, kp, L1, L2, comp in cases:
    e = q4.evaluate(C, sr, kp, L1, L2, comp=comp)
    surplus = e["总剩余"]
    # 解析预期
    u1 = S[1] * surplus
    u2 = S[2] * surplus
    exp_gap1 = max(0.0, L1 - u1)
    exp_gap2 = max(0.0, L2 - u2)
    print(f"\n  【{name}】")
    print(f"    净={e['净造价']:,.0f} WTP={e['WTP']:,.0f} 剩余={surplus:,.0f}")
    print(f"    预期缺口: 一层 {exp_gap1:,.0f}  二层 {exp_gap2:,.0f}")
    print(f"    函数缺口: 一层 {e['每层'][1]['缺口']:,.0f}  "
          f"二层 {e['每层'][2]['缺口']:,.0f}")
    print(f"    需求={e['补偿需求']:,.0f} 能力={e['补偿能力']:,.0f} "
          f"P3={e['P3_可谈成']}")
    ok = (abs(e['每层'][1]['缺口'] - exp_gap1) < 1.0
          and abs(e['每层'][2]['缺口'] - exp_gap2) < 1.0)
    print(f"    ⇒ 缺口计算 **{'一致 ✅' if ok else '不一致 ❌'}**")
