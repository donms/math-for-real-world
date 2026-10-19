#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **修正后的冲量需求**（起飞是推进段 + 缓冲从 4 m 起）。

## 为什么要重算

加上"起飞推进段"之后，两段竖直推进的冲量都变了：

| 阶段 | 旧（凭空给初速度）| **新（真实推进）** |
|---|---|---|
| **起飞** | 24.6 kN·s（$mv_{z0}$ 一次给足）| **28.4 kN·s**（80 kN×0.355 s）|
| **缓冲** | 24.6 kN·s（2 m 起刹）| **33.6 kN·s**（38 kN×0.88 s）|

## 起飞的精确解

$$z_b = \frac{gH}{a+g},\quad a = \frac{F}{m}-g$$

$F=80$ kN、$m=2000$ kg ⇒ $a=30.19$ m/s²：

$$z_b = \frac{9.81\times7.74}{40} = 1.90\ \text{m},\quad
v_b = \sqrt{2az_b} = 10.71\ \text{m/s},\quad
t_b = 0.355\ \text{s}$$

## 缓冲的精确解

从 $z_{\text{trig}}=4$ m、$v=-\sqrt{2g(H-z)}=-8.61$ m/s 刹到 $-0.5$：

$$F = m\left[\frac{v^2 - v_s^2}{2z} + g\right] = 38.1\ \text{kN}$$

$$z = |v|t - \tfrac12 a t^2,\quad a = \frac{F}{m}-g = 9.24
\;\Longrightarrow\; t = 0.88\ \text{s}$$
"""
from __future__ import annotations

import math


def main() -> int:
    m, g, H = 2000.0, 9.81, 7.78
    print("=" * 76)
    print("  W55 · 修正后的冲量需求")
    print("=" * 76)

    # ---- 起飞 ----
    F1 = 80e3
    a1 = F1 / m - g
    zb = g * H / (a1 + g)
    vb = math.sqrt(2 * a1 * zb)
    tb = vb / a1
    I1 = F1 * tb
    print(f"\n【起飞】F = 80 kN，a = {a1:.2f} m/s²")
    print(f"  熄火高度 z = {zb:.2f} m，v = {vb:.2f} m/s，t = {tb:.3f} s")
    print(f"  冲量 = **{I1/1000:.1f} kN·s**")

    # ---- 缓冲 ----
    zt = 4.0
    v0 = math.sqrt(2 * g * (H - zt))
    F2 = m * ((v0 ** 2 - 0.25) / (2 * zt) + g)
    a2 = F2 / m - g
    disc = v0 * v0 - 2 * a2 * zt
    t2 = (v0 + math.sqrt(max(0.0, disc))) / a2
    I2 = F2 * t2
    print(f"\n【缓冲】从 z = {zt} m 起刹，v = -{v0:.2f} m/s")
    print(f"  F = {F2/1000:.1f} kN，a = {a2:.2f} m/s²，t = {t2:.3f} s")
    print(f"  冲量 = **{I2/1000:.1f} kN·s**")

    # ---- 旋转 ----
    Jr = 907.0
    T_fly = 2.82
    L1 = Jr * (2 * math.pi / T_fly)
    print(f"\n【旋转 1 圈（滚转）】")
    print(f"  角冲量 {L1:.0f} kg·m²/s，力臂 1.15 m ⇒ "
          f"等效平动冲量 **{L1/1.15/1000:.1f} kN·s**")

    tot = I1 + I2 + L1 / 1.15
    print(f"\n【合计】{tot/1000:.1f} kN·s")
    for avail, lab in ((173.0, "简单估算"), (164.1, "精确积分")):
        print(f"  占可用量（{lab} {avail} kN·s）= "
              f"**{tot/1000/avail*100:.0f}%**")

    print("\n" + "=" * 76)
    print("  ★ 结论")
    print("=" * 76)
    print(f"  ① 起飞 {I1/1000:.1f} + 缓冲 {I2/1000:.1f} + 旋转 "
          f"{L1/1.15/1000:.1f} = **{tot/1000:.1f} kN·s**")
    print(f"  ② 占精确可用量 **{tot/1000/164.1*100:.0f}%**，"
          f"罐够用但余量不宽")
    print(f"  ③ **起飞与缓冲各占一半**，旋转仍然最便宜")
    print(f"  ④ ★ 两段竖直推进都比旧估**大**："
          f"起飞 +{(I1/24.6e3-1)*100:.0f}%、"
          f"缓冲 +{(I2/24.6e3-1)*100:.0f}%")
    print("     原因：旧估按『瞬时给足冲量 + 2 m 起刹』，"
          "新算按『真实推进 + 4 m 起刹』")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
