#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""诊断：力偶是否**只**产生滚转力矩（$\tau_y,\tau_z$ 应为零）。

## 为什么必须有这个检查

用户问："ATT + 对侧 LIFT 不会出现对角线方向滚动吗？"

**会。** 旧配置 `ATT_L`$(x=-1.40)$ + `LIFT_RR`$(x=+1.50)$ 算得

$$\tau_x=1.40F,\qquad \tau_y=-2.90F$$

**俯仰力矩是滚转的 2 倍 ⇒ 绕对角线翻滚。**

**而仿真完全看不见**：`physics.State` 只有滚转自由度，
$\tau_y$ 既没累计也没积分。

$$\boxed{\text{维度缺失会让错误"合法地"存在}}$$

**⇒ 本脚本把三轴力矩全部算出来，逐角度检查。**
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
    lx, ly, lz = m["pos"][0], m["pos"][1], m["pos2_z"]
    wy = ly * c - lz * s
    wz = ly * s + lz * c
    fx, fy, fz = F * w[0], F * w[1], F * w[2]
    tx = wy * fz - wz * fy
    ty = wz * fx - lx * fz
    tz = lx * fy - wy * fx
    return fx, fy, fz, tx, ty, tz


def main() -> int:
    F = 1000.0
    print("=" * 86)
    print("  三轴力矩检查：力偶是否只产生滚转")
    print("=" * 86)
    for lab, pair in (("正半圈 ATT_L + LIFT_RR", ("ATT_L", "LIFT_RR")),
                      ("反半圈 ATT_R + LIFT_RL", ("ATT_R", "LIFT_RL"))):
        print(f"\n【{lab}】")
        pos = {n: META[n]["pos"][:2] + (META[n]["pos2_z"],) for n in pair}
        for n in pair:
            print(f"  {n:<9} x={pos[n][0]:+.2f} y={pos[n][1]:+.2f} "
                  f"z={pos[n][2]:+.2f}  轴={META[n]['axis']}")
        if abs(pos[pair[0]][0] - pos[pair[1]][0]) > 1e-9:
            print(f"  ★ 两者 x 不同（Δx="
                  f"{pos[pair[0]][0]-pos[pair[1]][0]:+.2f}）⇒ 必有 τ_y")
        print(f"  {'θ(°)':>6}{'τx':>10}{'τy':>10}{'τz':>10}"
              f"{'净Fy':>9}{'净Fz':>9}")
        worst = 0.0
        net = 0.0
        for deg in range(0, 361, 45):
            th = math.radians(deg)
            a = wrench(pair[0], th, F)
            b = wrench(pair[1], th, F)
            tx, ty, tz = a[3] + b[3], a[4] + b[4], a[5] + b[5]
            nfy, nfz = a[1] + b[1], a[2] + b[2]
            worst = max(worst, abs(ty), abs(tz))
            net = max(net, abs(nfy), abs(nfz))
            print(f"  {deg:>6}{tx:>10.1f}{ty:>10.1f}{tz:>10.1f}"
                  f"{nfy:>9.2f}{nfz:>9.2f}")
        print(f"  ⇒ |τy|,|τz| 峰值 {worst:.2f} N·m，净力峰值 {net:.2f} N")
        print(f"  {'✓ 纯滚转力偶' if worst < 1e-6 and net < 1e-6 else '✗ 不是纯力偶'}")

    print("\n" + "=" * 86)
    print(f"  力偶臂 d = {ns.COUPLE_ARM:.2f} m")
    print("=" * 86)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
