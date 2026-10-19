#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **车尾 4 台主推进器对 0–96 km/h 的影响**。

> 用户："向后的喷口变成四个了，是不是 0-60 的加速就对了？"

## 背景

`models/02` 里算过：**只靠电机**，0–96 km/h 需 **1.07 s**，
而发布会实测 **0.81 s**（报道原文："0–96 km/h 加速仅需 1 秒；实测 0.81 秒"）。

**⇒ 差的这 0.26 s，正是冷气推进器要补的。**

## 模型

$$a_{\text{tire}}(v)=\min\!\Big(\underbrace{\mu(g+F_{\text{fan}}/m)}_{\text{抓地}},
\ \underbrace{P/(mv)}_{\text{功率}}\Big)
\qquad
a_{\text{total}}=a_{\text{tire}}+\frac{F_{\text{rear}}}{m}$$

**车尾 4 台合计 80 kN** ⇒ 额外 $80/2=40$ m/s²。

## 要回答两件事

1. 装上 4 台车尾后，0–96 km/h 是几秒？
2. 若比 0.81 s 还快，说明**实际不会全程开满**，
   或者主推进器的推力小于 80 kN（80 kN 是**全系统**10 个喷口的总和）。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph          # noqa: E402

M = ph.M_CAR
G = ph.G
V96 = 96 / 3.6                # 26.667 m/s
MU_TIRE = 1.30
A_TIRE = MU_TIRE * (G + ph.FAN_FORCE / M)
P_MOTOR = 745e3
F_REAR_TOTAL = 80e3


def a_tire(v: float) -> float:
    r"""轮胎可用加速度（抓地/功率双限）。"""
    if v < 1e-6:
        return A_TIRE
    return min(A_TIRE, P_MOTOR / (M * v))


def time_to(v_target: float, F_rear: float, dt: float = 1e-5) -> float:
    v, t = 0.0, 0.0
    while v < v_target:
        a = a_tire(v) + F_rear / M
        v += a * dt
        t += dt
    return t


def dist_to(v_target: float, F_rear: float, dt: float = 1e-5) -> float:
    v, x = 0.0, 0.0
    while v < v_target:
        a = a_tire(v) + F_rear / M
        v += a * dt
        x += v * dt
    return x


def main() -> int:
    print("=" * 84)
    print("  车尾主推进器对 0–96 km/h 的影响")
    print("=" * 84)
    print(f"\n  质量 {M:.0f} kg，轮胎抓地上限 {A_TIRE:.2f} m/s²"
          f"（{A_TIRE/G:.2f} g），电机 {P_MOTOR/1000:.0f} kW")
    print(f"  目标车速 96 km/h = {V96:.2f} m/s")

    print(f"\n  {'车尾总推力':>12}{'额外加速度':>12}{'0–96 时间':>11}"
          f"{'距离':>9}{'耗气(估)':>10}")
    rows = []
    for F in (0.0, 10e3, 20e3, 40e3, 60e3, 80e3):
        t = time_to(V96, F)
        d = dist_to(V96, F)
        # 耗气：mdot = F/ve，ve≈691 m/s
        md = F / 691.0 * t
        rows.append((F, t, d, md))
        print(f"  {F/1000:>10.0f} kN{F/M:>11.1f} m/s²{t:>10.3f} s"
              f"{d:>8.1f} m{md:>9.1f} kg")

    print(f"\n  报道实测：**0.81 s**")

    # 反解：需要多大车尾推力才能做到 0.81 s
    lo, hi = 0.0, 200e3
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if time_to(V96, mid) > 0.81:
            lo = mid
        else:
            hi = mid
    F_need = 0.5 * (lo + hi)
    print(f"  ⇒ 要做到 0.81 s，需车尾推力 **{F_need/1000:.1f} kN**"
          f"（{F_need/M/G:.2f} g）")
    print(f"  ⇒ 占全系统 80 kN 的 **{F_need/80e3*100:.0f}%**")

    t80 = time_to(V96, 80e3)
    print(f"\n  ★ 若 4 台全开（80 kN）：**{t80:.3f} s**"
          f"，比 0.81 s 快 {0.81/t80:.1f} 倍")
    print(f"  ⇒ 说明**实际不会全程开满**，或主推进器推力远小于 80 kN")

    print("\n" + "=" * 84)
    print("  ★★★ 结论")
    print("=" * 84)
    print(f"  ① **只靠电机**：{time_to(V96, 0.0):.2f} s（比实测慢 "
          f"{(time_to(V96,0.0)/0.81-1)*100:.0f}%）")
    print(f"  ② **加车尾推进器后确实能到 0.81 s**，只需约 "
          f"{F_need/1000:.0f} kN；")
    print(f"  ③ **但不能按 80 kN 全开**：那会到 {t80:.2f} s，"
          f"比实测快一倍多；")
    print(f"  ④ 报道的 80 kN 是**整机 10 个喷口的总和**，"
          f"不是车尾 4 台的；")
    print(f"  ⑤ ⇒ 车尾 4 台更可能是 **{F_need/4/1000:.1f} kN × 4**"
          f"（合计 {F_need/1000:.0f} kN）量级。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
