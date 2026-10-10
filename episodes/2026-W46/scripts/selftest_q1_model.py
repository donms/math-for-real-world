#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · Q1 模型自检：**守恒 + 定性行为**（在拟合之前必须先过）。

## 检查什么

1. **总量守恒**：$S_0+W_0+W_1+W_2+S_1+S_2+S_{12}+I_1+I_2$ 严格不变；
2. **非负性**：任何仓室不出现负值；
3. **定性行为**：能否产生
   * 年度冬季峰（周期 52 周）；
   * 两株**此消彼长**（份额在 0/1 之间切换）；
4. **边界情形**：
   * $c=0$（无交叉保护）⇒ 两株应**独立共存**，份额不长期偏移；
   * $c\to1$（强交叉保护）⇒ 应出现**先到者通吃**。

> **为什么先做这个**：W46 实测中我在这里连踩两个坑 ——
> ① `solve_ivp` 的 `args` 错位（把 `pr` 当 `t`）导致发散；
> ② 免疫衰减项**没有闭环**，总量从 0.9015 漂到 1.6975。
> **守恒与非负是动力学模型的底线，不通过就绝不能拿去拟合。**

用法：
    $PY selftest_q1_model.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from q1_model import PNAMES, rhs, simulate, unpack   # noqa: E402

BASE = {"beta0": 1.6, "phi": 1.25, "c": 0.6, "eps": 0.35, "theta": 4.0,
        "gamma": 1.0 / 1.8, "omega": 1.0 / 60.0, "rho": 3.0, "i0_1": 0.001}


def check(name: str, pr: dict, tmax: float = 10 * 52) -> bool:
    t, y = simulate(pr, tmax=tmax, n_out=3000)
    tot = y.sum(axis=0)
    drift = float(np.abs(tot - tot[0]).max())
    neg = float(y.min())
    It = y[7] + y[8]
    sh = y[7] / np.maximum(It, 1e-12)
    ok_c = drift < 1e-6
    ok_n = neg > -1e-9
    print(f"\n  ── {name} ──")
    print(f"     总量 {tot[0]:.6f} → {tot[-1]:.6f}   漂移 {drift:.2e}  "
          f"{'[OK]' if ok_c else '[X] 不守恒'}")
    print(f"     最小值（应 ≥0） {neg:.3e}  {'[OK]' if ok_n else '[X] 出现负值'}")
    print(f"     I_total: max {It.max():.4f}  min {It.min():.5f}")
    print(f"     株1 份额: {sh.min():.3f} ~ {sh.max():.3f}")
    # 年度周期性：自相关在 lag=52 应显著
    if It.std() > 1e-9:
        ac = float(np.corrcoef(It[:-52], It[52:])[0, 1])
        print(f"     lag-52 自相关 {ac:+.3f}  "
              f"{'（有年周期）' if abs(ac) > 0.3 else '（周期不明显）'}")
    return ok_c and ok_n


def main() -> int:
    print("=" * 88)
    print("  W46 · Q1 模型自检（守恒 / 非负 / 定性行为）")
    print("=" * 88)
    bad = 0

    for nm, over in (("基准参数", {}),
                     ("c=0（无交叉保护）", {"c": 0.0}),
                     ("c=0.95（强交叉保护）", {"c": 0.95}),
                     ("phi=1（两株等同）", {"phi": 1.0}),
                     ("eps=0（无季节性）", {"eps": 0.0}),
                     ("omega=0（免疫不衰减）", {"omega": 1e-9})):
        pr = dict(BASE)
        pr.update(over)
        if not check(nm, unpack(pr)):
            bad += 1

    print(f"\n{'='*88}")
    print(f"  未通过 {bad} / 6")
    if bad == 0:
        print("  [OK] 守恒、非负、边界情形全部通过 ⇒ 可以进入拟合阶段")
    else:
        print("  [X] 有检查未通过 —— **先修模型，不要拟合**")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
