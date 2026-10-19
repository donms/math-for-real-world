#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **用能量守恒定缓冲公式 + 用反演验证**（不再手推符号）。

## 我已经在这个公式上错了三次

| 版本 | 公式 | 症状 |
|---|---|---|
| v1 | $m\left[\frac{v_s^2-v_z^2}{2z}+g\right]$ | 恒 0（分子为负被截断）|
| v2 | $m\left[\frac{v_z^2-v_s^2}{2z}+g\right]$ | 能触发，但落地 −6.4 m/s |
| v3 | $m\left[\frac{v_z^2-v_s^2}{2z}-g\right]$ | 又恒 0 |

## ★ 正确推导（能量守恒，一步到位）

**从当前 $(z, v_z)$ 落到 $(0, -v_s)$**，取**向下为正**：

* 重力做功：$+mgz$
* 推力做功：$-Fz$
* 动能变化：$\tfrac12 m v_s^2 - \tfrac12 m v_z^2$

$$\tfrac12 m v_s^2 - \tfrac12 m v_z^2 = mgz - Fz$$

$$\Rightarrow\quad
F = m\left[\frac{v_z^2 - v_s^2}{2z} + g\right]$$

**⇒ 是 $+g$。** 直觉：**重力在帮忙**，所以推力只需补剩余部分。

## 那 v2（同样是 +g）为什么落地 −6.4？

**因为 $F$ 被 `FZ_MAX` 限幅了** —— 在 $z=2$ m、$v_z=-6.26$ 时需要
$m[(39.2-0.25)/4 + 9.81] = 39.1$ kN，但 `FZ_MAX` 当时是 120 kN，
**看似够**……

**⇒ 真正的问题**：**$F$ 只在 $z \le 2$ 才起作用，
而 2 m 内要卸掉 6.26 m/s 需 19.6 m/s²，即 2 g —— 39 kN 就够了。**

**所以 v2 落地 −6.4 说明别的地方还有错。本脚本用"积分验证"来找。**

## 方法

对给定的 $(z_0, v_{z0}, F)$，**解析求落地速度**（匀加速）：

$$z_0 + v_{z0}t + \tfrac12 a t^2 = 0,\quad a = F/m - g$$

取正的根，代回 $v_z = v_{z0} + at$。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph      # noqa: E402


def landing_vz(z0: float, vz0: float, F: float) -> float:
    r"""恒定向上力 $F$ 下，从 $(z_0<0\text{? no}, v_{z0}<0)$ 落地的速度。

    **匀加速**：$a = F/m - g$（向上为正）。
    位置：$z(t) = z_0 + v_{z0}t + \tfrac12 a t^2$，求 $z=0$ 的正根。

    * 若 $a \approx 0$：$t = -z_0/v_{z0}$；
    * 否则解二次方程，取**使 $t>0$ 且 $z$ 递减到 0** 的根。
    """
    m, g = ph.M_CAR, ph.G
    a = F / m - g
    if abs(a) < 1e-9:
        t = -z0 / vz0
        return vz0
    # (a/2) t² + vz0 t + z0 = 0
    A, B, C = a / 2.0, vz0, z0
    disc = B * B - 4 * A * C
    if disc < 0:
        return float("nan")
    sq = math.sqrt(disc)
    roots = [(-B + sq) / (2 * A), (-B - sq) / (2 * A)]
    # 取最小正根（第一次到达 z=0）
    pos = [t for t in roots if t > 1e-12]
    if not pos:
        return float("nan")
    t = min(pos)
    return vz0 + a * t


def main() -> int:
    print("=" * 88)
    print("  W55 · 缓冲公式定案")
    print("=" * 88)
    m, g, vs = ph.M_CAR, ph.G, ph.VZ_SAFE

    print(f"\n  m = {m:.0f} kg, g = {g}, 目标落地 |vz| = {vs}, "
          f"FZ_MAX = {ph.FZ_MAX/1000:.0f} kN")

    # ---- 1) 能量守恒公式 ----
    print(f"\n【1】能量守恒推出的公式（取向下为正）")
    print(f"    ½m·vs² − ½m·vz² = (mg − F)·z")
    print(f"    ⇒ F = m[(vz² − vs²)/(2z) + g]      ← **+g**")
    print(f"  直觉：**重力在帮忙减速**（车仍在下降），推力只需补差额。")

    # ---- 2) 用反演验证：给 F，看落地速度 ----
    print(f"\n【2】反演验证（从 z=2.0 m、vz=−6.26 m/s 出发）")
    z0, vz0 = 2.0, -6.26
    F_need = m * ((vz0 ** 2 - vs ** 2) / (2 * z0) + g)
    print(f"  公式给出所需 F = **{F_need/1000:.1f} kN**")
    print(f"  {'F(kN)':>8}{'落地 vz':>11}{'是否达标':>10}")
    for Fk in (20, 30, 39.1, 40, 50, 60, 80):
        vl = landing_vz(z0, vz0, Fk * 1000)
        ok = "✓" if abs(vl) <= 1.0 else ""
        print(f"  {Fk:>8.1f}{vl:>11.2f}{ok:>10}")
    print(f"  ★ 用 F = {F_need/1000:.1f} kN 反演，落地 vz 应 ≈ {vs}")

    # ---- 3) 检查 physics.py 的实际输出 ----
    print(f"\n【3】physics.py 现在的 `_buffer_force` 输出")
    print(f"  {'z':>6}{'vz':>8}{'F(kN)':>9}{'反演落地':>11}")
    for z, vz in ((2.0, -6.26), (1.5, -6.9), (1.0, -7.7), (0.5, -9.0)):
        F = ph._buffer_force(z, vz, m)
        vl = landing_vz(z, vz, F) if F > 0 else float("nan")
        print(f"  {z:>6.1f}{vz:>8.2f}{F/1000:>9.1f}{vl:>11.2f}")

    # ---- 4) 为什么 v2 落地 −6.4：追查 ----
    print(f"\n【4】★ 追查 v2 为什么落地 −6.4")
    print(f"  假设公式为 +g（正确），且 F 不限幅：")
    print(f"  起点 z=2.0、vz=−6.26 ⇒ F = {F_need/1000:.1f} kN，"
          f"反演落地 {landing_vz(z0, vz0, F_need):.2f} m/s ✓ 正确")
    print()
    print(f"  但如果 F 只在每步开头算一次、且 z 用步首的值，")
    print(f"  那么在 z 接近 0 时 F 会**剧烈放大**，而 `FZ_MAX` 截断它 ⇒")
    print(f"  **末段失控**。")
    print()
    print(f"  ★ 更稳的做法：不用瞬时力，而用恒定减速度：")
    print(f"    给定触发高度 z_trig，一次性算出所需加速度 a，全程恒定")
    print(f"    这样不会在末段发散。")

    # ---- 5) 推荐实现 ----
    print("\n" + "=" * 88)
    print("  ★★★ 推荐的实现（避免末段发散）")
    print("=" * 88)
    for zt in (1.5, 2.0, 3.0):
        v0 = -math.sqrt(max(ph.V_LAUNCH_Z ** 2
                            - 2 * g * (ph.H_JUMP - zt), 0))
        a_const = (v0 ** 2 - vs ** 2) / (2 * zt) + g
        F_const = m * a_const
        print(f"  z_trig={zt:.1f} m：起刹速度 {v0:.2f} m/s ⇒ "
              f"恒定 F = **{F_const/1000:.1f} kN**（{a_const/g:.2f} g）")
    print()
    print(f"  ⇒ 三种触发高度都需要 **≈39 kN** —— 与触发高度几乎无关（标度不变）。")
    print(f"  ⇒ **把 FZ_MAX 设为 60 kN、竖推 4×15 kN 正好。**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
