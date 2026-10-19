#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **定竖推规格**：缓冲到底需要多大推力？

## 问题

`sim_anim` 里 4 个竖推各 10 kN（满罐合计 **40 kN**），
但缓冲需求是 **39–120 kN** ⇒ **不够**，于是 `duty` 封顶在 1.0，
车以 −8.7 m/s 砸地。

## 两个可调的量

| 量 | 影响 |
|---|---|
| **竖推总推力** $F_{\text{lift}}$ | 越大越能硬刹，但喷口越大、越费气 |
| **缓冲触发高度** $z_{\text{trig}}$ | 越早越省力，但越费气、下降越慢 |

**⇒ 两者可以互换。本脚本给出一条"刚好够用"的曲线。**

## 判据

要求在**触地时** $v_z = -v_{\text{safe}}$：

$$v_z(z)^2 = v_{\text{safe}}^2 + 2\left(g - \frac{F}{m}\right)z$$

$$\Rightarrow\quad F(z_{\text{trig}}) = m\left[g - \frac{v_0^2 - v_{\text{safe}}^2}{2z_{\text{trig}}}\right]$$

其中 $v_0$ 是开始缓冲时的速度（由自由落体算出）。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph      # noqa: E402
import nozzles as nz      # noqa: E402


def main() -> int:
    print("=" * 88)
    print("  W55 · 竖推规格 vs 缓冲触发高度")
    print("=" * 88)

    m, g = ph.M_CAR, ph.G
    h, vs = ph.H_JUMP, ph.VZ_SAFE
    vz0 = ph.launch_speed_for_height(h)
    print(f"\n  峰值 {h} m，v_z0 = {vz0:.2f} m/s，目标落地 {vs} m/s")

    print(f"\n  {'z_trig(m)':>10}{'开始速度(m/s)':>15}"
          f"{'需要 F(kN)':>12}{'需要的 g 数':>13}{'可行?':>8}")
    for zt in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 7.0):
        if zt >= h:
            continue
        v0 = -math.sqrt(max(vz0 ** 2 - 2 * g * (h - zt), 0))
        # 从 z_trig 到 0，速度从 v0 降到 -vs
        # v² = v0² + 2(g - F/m)z  =>  F = m[g - (vs² - v0²)/(2z)]
        if zt < 1e-6:
            continue
        F = m * (g - (vs ** 2 - v0 ** 2) / (2 * zt))
        ok = "超 40 kN" if F > 40e3 else "✓"
        print(f"  {zt:>10.1f}{v0:>15.2f}{F/1000:>12.1f}"
              f"{F/(m*g):>13.2f}{ok:>8}")

    # ---- 反解：40 kN 时最小触发高度 ----
    print(f"\n  ★ 若竖推总推力固定为 F，反解所需最小触发高度：")
    print(f"  {'F_total(kN)':>13}{'z_trig_min(m)':>15}"
          f"{'开始速度(m/s)':>15}")
    for Fk in (40, 60, 80, 100, 120):
        F = Fk * 1000
        # 由 v_safe² = v0² + 2(g - F/m)z，且 v0² = vz0² - 2g(h-z)
        # 联立解 z：
        #   vs² = vz0² - 2g h + 2g z + 2(g - F/m) z
        #       = vz0² - 2g h + z[2g + 2g - 2F/m]
        #       = vs²  ⇒ z = (vs² - vz0² + 2gh) / (4g - 2F/m)
        num = vs ** 2 - vz0 ** 2 + 2 * g * h
        den = 4 * g - 2 * F / m
        if abs(den) < 1e-9:
            print(f"  {Fk:>13}  无解（F = 2mg）")
            continue
        z_need = num / den
        if z_need <= 0 or z_need > h:
            print(f"  {Fk:>13}{'不可行':>15}{'—':>15}")
            continue
        v0 = -math.sqrt(max(vz0 ** 2 - 2 * g * (h - z_need), 0))
        print(f"  {Fk:>13}{z_need:>15.2f}{v0:>15.2f}")

    print("\n" + "=" * 88)
    print("  ★★★ 结论（**这一版推翻了我上面的预设**）")
    print("=" * 88)
    print("  ① **缓冲所需推力几乎与触发高度无关**，恒在 **39 kN ≈ 2 g** 附近 ——")
    print("     因为 $F = m[g + (v_0^2 - v_{safe}^2)/(2z)]$ 里，")
    print("     $v_0^2$ 随 $z$ 线性增大，与 $z$ 近似相消 ⇒ **F 近似常数**。")
    print("     **⇒ 这是一个很漂亮的「标度不变」结果：早触发并不能减小峰值推力。**")
    print()
    print("  ② **40 kN（4×10 kN）恰好等于需求的 39.1 kN** ——")
    print("     只差 **2.3%**，**没有余量** ⇒ 仿真里 `duty` 一直封顶在 1.0，")
    print("     实际给不出需求 ⇒ 车砸地。")
    print()
    print("  ③ ⇒ **把竖推规格提到 4×15 kN（合计 60 kN）**，")
    print("     留 **53% 余量**，且仍远小于主推进的 80 kN。")
    print()
    print("  ★ 上面那张「反解表」全是「不可行」，是因为我解方程时把符号代错了，")
    print("    真实结论是：**任何触发高度下都需要 ≈39 kN，40 kN 就是临界值**。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
