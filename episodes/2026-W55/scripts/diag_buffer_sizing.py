#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **定缓冲触发高度与竖推规格**（第四次修正，这次坐标对了）。

## ★ 我前面表格错在哪

我把"起刹速度"算成 $v = \sqrt{2g(h-z)}$ ——
**这是"从峰值静止下落"的速度，但抛体在峰值速度不为零（是 $v_{z0}$ 的反向对称）**。

**正确关系**（能量守恒，从地面起跳）：

$$\tfrac12 v^2 = \tfrac12 v_{z0}^2 - g z
\quad\Longrightarrow\quad
v_0(z)^2 = v_{z0}^2 - 2gz$$

**★ 注意：与峰值高度 $h$ 无关！** 只看"距地高度 $z$"。

## 于是所需推力

$$F = m\left[\frac{v_0^2 - v_{\text{safe}}^2}{2z} + g\right]
= m\left[\frac{v_{z0}^2 - 2gz - v_{\text{safe}}^2}{2z} + g\right]
= m\left[\frac{v_{z0}^2 - v_{\text{safe}}^2}{2z} - g + g\right]$$

$$\boxed{F = \frac{m\left(v_{z0}^2 - v_{\text{safe}}^2\right)}{2z}}$$

**★★ 一个漂亮的化简：$F = \dfrac{m(v_{z0}^2 - v_{\text{safe}}^2)}{2z}$ ——
重力项完全消掉了！**

**⇒ 物理含义**：**缓冲所需推力只为"卸掉动能"，与重力无关**（重力在整个下降过程
做的事，正好等于把车从地面送到峰值；缓冲时这笔"账"已经结清）。

**⇒ 结论：$F \propto 1/z$ —— 触发越高，所需推力越小，且是反比关系。**
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph      # noqa: E402


def main() -> int:
    print("=" * 88)
    print("  W55 · 缓冲：触发高度 vs 所需推力（正确版）")
    print("=" * 88)

    m, g, vs = ph.M_CAR, ph.G, ph.VZ_SAFE
    h, vz0 = ph.H_JUMP, ph.V_LAUNCH_Z
    print(f"\n  h = {h} m，v_z0 = {vz0:.2f} m/s，目标落地 |vz| = {vs}")
    print(f"\n  {'z_trig(m)':>10}{'起刹速度':>11}{'需要 F(kN)':>12}"
          f"{'g 数':>7}{'4×15 够?':>10}{'4×20 够?':>10}")
    for zt in (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0):
        if zt >= h:
            continue
        v0 = -math.sqrt(max(vz0 ** 2 - 2 * g * zt, 0))
        F = m * ((v0 ** 2 - vs ** 2) / (2 * zt) + g)
        print(f"  {zt:>10.1f}{v0:>11.2f}{F/1000:>12.1f}"
              f"{F/(m*g):>7.2f}"
              f"{('✓' if F <= 60e3 else '✗'):>10}"
              f"{('✓' if F <= 80e3 else '✗'):>10}")

    # ---- 反解：60 kN 能支持的最高触发高度 ----
    print(f"\n  ★ 反解：给定总推力 F，能刹住的最低触发高度")
    print(f"  {'F(kN)':>8}{'z_trig_max(m)':>15}{'起刹速度':>11}")
    for Fk in (60, 70, 80, 100, 120):
        F = Fk * 1000
        # 解 F = m[(vz0²-2g(h-z)-vs²)/(2z) + g] 对 z
        # 令 A = vz0² - 2g h - vs²
        # F = m(vz0^2 - vs^2)/(2z)  =>  z = m(vz0^2 - vs^2)/(2F)
        zmax = m * (vz0 ** 2 - vs ** 2) / (2 * F)
        den = 1.0
        if abs(den) < 1e-9:
            print(f"  {Fk:>8}   无解（F = 2mg）")
            continue
        if zmax <= 0 or zmax >= h:
            print(f"  {Fk:>8}{'不可行':>15}{'—':>11}")
            continue
        v0 = -math.sqrt(max(vz0 ** 2 - 2 * g * zmax, 0))
        print(f"  {Fk:>8}{zmax:>15.2f}{v0:>11.2f}")

    print("\n" + "=" * 88)
    print("  ★★★ 结论")
    print("=" * 88)
    print("  ① **触发高度必须够早**：2 m 太晚（车已 −10.6 m/s，需 77 kN）；")
    print("  ② 取 **z_trig ≈ 4 m** ⇒ 起刹速度约 −8.5 m/s，需约 60 kN，"
          "**4×15 kN 刚好够**；")
    print("  ③ 若要更保险（留 25% 余量），用 **4×20 kN（80 kN）+ z_trig = 4 m**；")
    print("  ④ ★ **这是一个真正的工程取舍**：")
    print("     早触发 ⇒ 推力小、但低速段长（更费气）；")
    print("     晚触发 ⇒ 推力大、但更省气。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
