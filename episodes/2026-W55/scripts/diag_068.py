#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **诊断**：0.68 s 到底是"维持 80 kN 的时长"还是别的？

## 我在两处用了 0.68 s，含义不同 —— 必须查清

| 出处 | 我写的 |
|---|---|
| `models/03_气罐预算.md` §3.4.2 | "从 35 MPa 开始、喷口 25 cm² ⇒ **能维持 ≥80 kN 约 0.68 s**" |
| `fig_nozzle_pressure.png` | 图上标"跌破 80 kN ≈ 0.00 s" |

**⇒ 两者矛盾。**

## 本脚本要回答

1. 若喷口按 **35 MPa 下 80 kN** 设计，能维持 80 kN 多久？
2. 若按 **20 MPa 下 80 kN** 设计（问题 3 的口径），能维持多久？
3. **0.68 s 到底是什么量？**
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph      # noqa: E402
import nozzles as nz      # noqa: E402


def main() -> int:
    print("=" * 84)
    print("  W55 · 0.68 s 到底是什么")
    print("=" * 84)

    print(f"\n  基准：罐 {ph.M_AIR} kg / {ph.V_TANK} m³ ⇒ "
          f"p0 = {ph.P_TANK/1e6:.2f} MPa")
    print(f"        v_e(p0) = {nz.ve_of(ph.P_TANK):.0f} m/s")

    # ---- 情形 A：按 35 MPa 下 80 kN 设计 ----
    print(f"\n【A】喷口按 **35 MPa 下 80 kN** 设计")
    at_a = nz.area_for_force(80e3, ph.P_TANK)
    md_a = nz.mdot_of_area(at_a, ph.P_TANK)
    print(f"    喉部面积 {at_a*1e4:.2f} cm²")
    print(f"    满罐推力 {nz.force_of_area(at_a, ph.P_TANK)/1000:.1f} kN")
    print(f"    满罐出气率 {md_a:.1f} kg/s")
    print(f"    250 kg 全放完 {ph.M_AIR/md_a:.2f} s")
    print(f"    ⇒ **维持 80 kN 的时间 ≈ 0**（满罐刚好 80，一放就降）")
    print(f"    ⇒ 图 3 标出的 t≈0.00 s 是**正确的**")

    # ---- 情形 B：按 20 MPa 下 80 kN 设计 ----
    print(f"\n【B】喷口按 **20 MPa 下 80 kN** 设计（问题 3 的口径）")
    at_b = nz.area_for_force(80e3, 20e6)
    md_b0 = nz.mdot_of_area(at_b, ph.P_TANK)
    print(f"    喉部面积 {at_b*1e4:.2f} cm²")
    print(f"    满罐推力 {nz.force_of_area(at_b, ph.P_TANK)/1000:.1f} kN")
    print(f"    满罐出气率 {md_b0:.1f} kg/s")
    m_to_20 = ph.M_AIR * (1 - 20e6 / ph.P_TANK)
    t_35_20 = m_to_20 / md_b0
    print(f"    从 35 → 20 MPa 需放掉 {m_to_20:.1f} kg，耗时 "
          f"**{t_35_20:.2f} s**")
    print(f"    ⇒ 这 **{t_35_20:.2f} s** 就是模型文档里的 0.68 s")
    print(f"    ⇒ 但它是**压力从 35 降到 20 MPa 的时间**，")
    print(f"       **不是「维持 80 kN 的时长」** ——")
    print(f"       因为满罐时是 {nz.force_of_area(at_b, ph.P_TANK)/1000:.0f} kN，")
    print(f"       80 kN 只在降到 20 MPa 那**一刻**出现。")

    # ---- 修正说法 ----
    print("\n" + "=" * 84)
    print("  ★ 正确的说法")
    print("=" * 84)
    print(f"  ① 若喷口按 35 MPa 下 80 kN 设计（面积 {at_a*1e4:.1f} cm²）：")
    print(f"     · 满罐 80 kN，之后**单调下降**；")
    print(f"     · 250 kg 全放完 {ph.M_AIR/md_a:.2f} s；")
    print(f"     · **没有任何「维持 80 kN」的平台期**。")
    print()
    print(f"  ② 若把喷口做大到 20 MPa 下 80 kN（面积 {at_b*1e4:.1f} cm²）：")
    print(f"     · 满罐 {nz.force_of_area(at_b, ph.P_TANK)/1000:.0f} kN，"
          f"降到 20 MPa 时 80 kN；")
    print(f"     · 从 35 降到 20 MPa 用 {t_35_20:.2f} s；")
    print(f"     · 这段时间里推力从 {nz.force_of_area(at_b, ph.P_TANK)/1000:.0f} "
          f"降到 80 kN。")
    print()
    print(f"  ★★ 所以 0.68 s 应改述为：")
    print(f"     **「在 25 cm² 喷口下，罐压从 35 MPa 降到 20 MPa 需 0.68 s，")
    print(f"      推力在这段时间里从 114 kN 降到 80 kN。」**")
    print(f"  ★★ 而 0–60 mph 的 0.81 s ⇒ 与之同量级，仍是有效对照：")
    print(f"     说明加速演示的时长受**气量而非电机**限制。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
