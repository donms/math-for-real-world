#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **把落地横漂拆成"哪一段贡献的"**（判"未收敛"时必须能说清残余从哪来）。

## 要回答的三个问题

1. 横漂是**滚转段**攒的，还是**缓冲段**攒的？
2. 缓冲段的贡献是不是由**终端姿态残差**放大的？
3. 残余横速 $\pm0.5$ m/s 在 **1.0 s** 的缓冲+下落里，能积出多少 $y$？

## 做法

按相位切窗口，逐窗口累计：

$$\Delta y=\int v_y\,dt,\qquad \Delta v_y=\frac{1}{m}\int \sum F_y\,dt$$

并把升力（随 $\theta$ 倾斜）与侧推（专门配平）分开记 ——
两者的**差**就是净横漂，而它们各自是**大数**。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nozzle_state as ns     # noqa: E402
import physics as ph          # noqa: E402

LIFT = ("LIFT_FL", "LIFT_FR", "LIFT_RL", "LIFT_RR")


def run(dt: float, ledger: str = "analytic") -> None:
    recs = ns.run_mission10_auto(dt, ledger=ledger, quiet=True)
    t_b = ns.run_mission10_auto.t_burn
    T_roll = ns.run_mission10_auto.T_roll
    t_r0, t_r1 = t_b, t_b + T_roll
    # 起飞段起点：vz 首次 > 0
    t_to = next((r.t for r in recs if r.vz > 0.01), 0.0)

    # 相位边界：accel | takeoff | roll | buffer
    bounds = [("助跑", 0.0, t_to), ("起飞", t_to, t_b),
              ("滚转", t_r0, t_r1), ("缓冲", t_r1, recs[-1].t + 1e-9)]

    print(f"\n  dt=1/{round(1/dt)}（{ledger}）  末态 y={recs[-1].y*100:+.2f} cm，"
          f"vy={recs[-1].vy:+.4f} m/s")
    print(f"  {'相位':<6}{'窗口(s)':>15}{'∫Fy_lift dt':>14}{'∫Fy_side dt':>14}"
          f"{'净Δvy':>10}{'Δy(cm)':>10}{'θ范围(°)':>16}")
    tot = 0.0
    for name, t0, t1 in bounds:
        seg = [r for r in recs if t0 <= r.t < t1]
        if not seg:
            continue
        fl = fs = 0.0
        for r in seg:
            cth, sth = math.cos(r.theta), math.sin(r.theta)
            # 升力喷口在世界系的横向分量：F*sinθ（+Z 轴绕 x 转后的 y 分量）
            f_lift = sum(r.f[n] for n in LIFT)
            # +Z 轴绕 x 转后世界系 y 分量 = -sinθ（不是 +sinθ）
            fl += -f_lift * sth * dt
            fs += (r.f["SIDE_P"] - r.f["SIDE_N"]) * cth * dt
        dy = (seg[-1].y - seg[0].y) * 100
        dvy = seg[-1].vy - seg[0].vy
        th = (math.degrees(seg[0].theta), math.degrees(seg[-1].theta))
        tot += dy
        print(f"  {name:<6}{f'{t0:.3f}–{t1:.3f}':>15}{fl:>14.1f}{fs:>14.1f}"
              f"{dvy:>+10.3f}{dy:>+10.2f}{f'{th[0]:+.0f} → {th[1]:+.0f}':>16}")
    print(f"  {'合计':<6}{'':>15}{'':>14}{'':>14}{'':>10}{tot:>+10.2f}")

    # 缓冲段的"姿态杠杆"：θ 残差 1° ⇒ 80 kN 竖推的横向分量
    print(f"  ★ 缓冲段升力横向力 ≈ 4×20 kN×sinθ："
          f"θ=1° ⇒ {80e3*math.sin(math.radians(1))/1e3:.1f} kN，"
          f"θ=5° ⇒ {80e3*math.sin(math.radians(5))/1e3:.1f} kN")


def main() -> int:
    print("=" * 96)
    print("  W55 · 落地横漂的相位分解（残余原因）")
    print("=" * 96)
    for dt in (1 / 240, 1 / 960, 1 / 3840):
        run(dt)
    print("\n" + "=" * 96)
    print("  ★ 若横漂主要在【滚转】段攒下，且升力与侧推两列都是大数、净差很小，")
    print("    说明它是**两个大数相减**的结果 —— 这种量的相对误差必然被放大。")
    print("  ★ 若【缓冲】段的 Δy 也不小，则终端姿态残差（MIB 死区 ±2°）是第二个放大器。")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
