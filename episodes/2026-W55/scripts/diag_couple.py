#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""诊断：力偶的力矩是否真的恒为 $1.40F$。

## 要验的两件事

1. $\tau_x(\theta)$ 是否**与姿态无关**（力偶应当恒定）；
2. 两个喷口的**净竖直力**是否为零（力偶的判据）。

$$\tau_x=r_yF_z-r_zF_y,\qquad
r_w=R_x(\theta)\,r_b,\qquad F_w=R_x(\theta)\,F_b$$
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nozzle_state as ns     # noqa: E402

META = {m["name"]: m for m in ns.NOZZLE_META}


def wrench(name: str, th: float, F: float):
    m = META[name]
    c, s = math.cos(th), math.sin(th)
    w = ns.body_to_world(m["axis"], c, s)
    ly, lz = m["pos"][1], m["pos2_z"]
    wy = ly * c - lz * s
    wz = ly * s + lz * c
    fx, fy, fz = F * w[0], F * w[1], F * w[2]
    tx = wy * fz - wz * fy
    return fx, fy, fz, tx


def main() -> int:
    F = 1000.0
    print("=" * 78)
    print(f"  力偶力矩检查（每个喷口 F = {F:.0f} N）")
    print("=" * 78)
    print(f"\n  {'θ(°)':>6}"
          f"{'ATT_L τx':>10}{'LIFT_RR τx':>12}{'合计 τx':>10}"
          f"{'净 Fz':>10}{'净 Fy':>10}")
    print(f"  {'':>6}{'N·m':>10}{'N·m':>12}{'N·m':>10}"
          f"{'N':>10}{'N':>10}")
    worst = 0.0
    netmax = 0.0
    for deg in range(0, 361, 30):
        th = math.radians(deg)
        a = wrench("ATT_L", th, F)
        b = wrench("LIFT_RR", th, F)
        tot = a[3] + b[3]
        nfz = a[2] + b[2]
        nfy = a[1] + b[1]
        worst = max(worst, abs(tot - 1.40 * F))
        netmax = max(netmax, abs(nfz), abs(nfy))
        print(f"  {deg:>6}{a[3]:>10.1f}{b[3]:>12.1f}{tot:>10.1f}"
              f"{nfz:>10.2f}{nfy:>10.2f}")

    print(f"\n  理论值 1.40×F = {1.40*F:.1f} N·m")
    print(f"  力矩与理论的最大偏差 {worst:.3f} N·m")
    print(f"  净力绝对值的最大值 {netmax:.2f} N")
    print()
    if worst < 1e-6 and netmax < 1e-6:
        print("  ★ 力矩恒定且净力为零 ⇒ 力偶成立 ✓")
    else:
        print("  ★ 力偶不成立，需检查几何")

    print("\n" + "=" * 78)
    print("  各喷口的有效力臂（θ=0）")
    print("=" * 78)
    for nm in ("ATT_L", "ATT_R", "LIFT_FL", "LIFT_FR", "LIFT_RL", "LIFT_RR"):
        m = META[nm]
        print(f"  {nm:<10} y={m['pos'][1]:+.2f}  z={m['pos2_z']:+.2f}  "
              f"轴={m['axis']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
