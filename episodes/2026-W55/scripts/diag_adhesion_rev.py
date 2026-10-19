#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **倒挂段法向力方程改正后**的全部数值（2026-10-17 修正版）。

## 改了什么

旧式（错）：
$$N=F_a-mg\cos\theta-\frac{mv^2}{R}$$

新式（正）：
$$N=F_a+\frac{mv^2}{R}-mg\cos\theta$$

## 为什么旧式错

几何：半圆环圆心在 $(0,R)$，顶点在 $(0,2R)$，**圆心在车下方**。
顶点处：

* 重力：向下 = **指向**圆心；
* 坡面反力 $N$：坡面在上、推车向下 = **指向**圆心；
* 风扇吸附 $F_a$：把车吸向坡面 = 向上 = **背离**圆心。

取指向圆心为正：$mg+N-F_a=mv^2/R$，解得上式。

## 判据的物理解读（这才是重点）

$$\lambda\ge\cos\theta-\frac{v^2}{gR}$$

顶点：$\lambda\ge 1-\dfrac{v^2}{gR}$，等价于 $v^2\ge(1-\lambda)gR$。

| | $\lambda=0$（无风扇） | $\lambda=2$（2G） |
|---|---|---|
| 顶点判据 | $v\ge\sqrt{gR}=10.15$ m/s | **无速度约束** |
| 解读 | 太快不行，**必须够快** | **可以任意慢** |

$$\boxed{\text{风扇的作用是"让车能慢慢爬"，不是"让车能更快"}}$$

## 用法

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"
& "python" episodes\2026-W55\scripts\diag_adhesion_rev.py
```
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
H_DETACH = 21.0                # 脱轨高度（报道 ①）
R_ARC = H_DETACH / 2.0         # 半圆环 ⇒ R = 10.5 m
LAM = 2.0                      # 风扇吸附 ≈ 2G（报道 ①）
V_CLIMB = 9.34                 # 采用车速（自定 ③，保持与飞跃段一致）
A_EFF = 4.0                    # 有效吸附面积 m²（自定 ③）


def N_new(th: float, v: float, lam: float = LAM) -> float:
    r"""改正后的法向力 $N=F_a+mv^2/R-mg\cos\theta$。"""
    return lam * M * G + M * v * v / R_ARC - M * G * math.cos(th)


def lam_min(v: float, R: float) -> float:
    r"""顶点所需吸附倍数下界 $\lambda\ge 1-v^2/(gR)$（截断于 0）。"""
    return max(0.0, 1.0 - v * v / (G * R))


def main() -> int:
    print("=" * 88)
    print("  倒挂段法向方程改正后的数值（N = Fa + m v^2/R - m g cosθ）")
    print("=" * 88)

    print(f"\n  几何：脱轨高度 {H_DETACH:.1f} m（①），半圆环 ⇒ "
          f"R = {R_ARC:.2f} m（②），圆心在 (0, R)，**圆心在车下方**")
    print(f"  吸附 λ = {LAM:.1f} G（①），采用车速 {V_CLIMB:.2f} m/s"
          f"（{V_CLIMB * 3.6:.1f} km/h，③）")

    print("\n【1】顶点法向力（θ = 0）")
    n0 = N_new(0.0, V_CLIMB)
    print(f"  N(0) = λmg + m v²/R − mg = "
          f"{LAM * M * G / 1e3:.2f} + {M * V_CLIMB ** 2 / R_ARC / 1e3:.2f}"
          f" − {M * G / 1e3:.2f} = **{n0 / 1e3:+.2f} kN**")
    print(f"  ★ 与旧式对照（F_a − mg − mv²/R）会得 "
          f"{(LAM * M * G - M * G - M * V_CLIMB ** 2 / R_ARC) / 1e3:+.2f} kN")

    print("\n【2】法向力沿程（λ = 2, v = 9.34 m/s）")
    print(f"  {'θ(°)':>6}{'cosθ':>9}{'N(kN)':>10}")
    for deg in (0, 15, 30, 45, 60, 90, 120, 150, 180):
        th = math.radians(deg)
        print(f"  {deg:>6}{math.cos(th):>9.3f}{N_new(th, V_CLIMB) / 1e3:>10.2f}")
    print("  ⇒ 单调：θ=0（顶点）最小，θ=180°（地面）最大 ⇒ 顶点最危险")

    print("\n【3】顶点所需吸附倍数 λ_min = max(0, 1 − v²/(gR))")
    vlist = (10, 20, 30, 36.5, 45, 60, 90)
    Rlist = (8.0, 10.0, 15.0, 20.0)
    print(f"  {'v(km/h)':>9}" + "".join(f"{f'R={r:g}':>11}" for r in Rlist))
    for kmh in vlist:
        v = kmh / 3.6
        row = "".join(f"{lam_min(v, r):>11.3f}" for r in Rlist)
        print(f"  {kmh:>9}{row}")

    print("\n【4】无风扇（λ = 0）所需最低车速 v ≥ √(gR)")
    print(f"  {'R(m)':>7}{'v_min(m/s)':>13}{'km/h':>10}")
    for r in Rlist:
        v = math.sqrt(G * r)
        print(f"  {r:>7}{v:>13.2f}{v * 3.6:>10.1f}")
    print(f"  ⇒ 本文演示 R = {R_ARC:.2f} m 时 v_min = "
          f"{math.sqrt(G * R_ARC):.2f} m/s（{math.sqrt(G * R_ARC) * 3.6:.1f} km/h）")
    print(f"  ⇒ 采用车速 {V_CLIMB:.2f} m/s **低于**该值 ⇒ "
          f"无风扇时顶点 N = "
          f"{(M * V_CLIMB ** 2 / R_ARC - M * G) / 1e3:+.2f} kN < 0 ⇒ 必须靠吸附")

    print("\n【5】所需吸附力与等效压差（顶点，A = 4 m²，λ 取上式）")
    print(f"  {'R(m)':>6}{'v(km/h)':>9}{'λ_min':>9}{'Fa(N)':>11}{'Δp(kPa)':>10}")
    for r in Rlist:
        for kmh in (10, 20, 30, 45, 60):
            v = kmh / 3.6
            lm = lam_min(v, r)
            fa = lm * M * G
            print(f"  {r:>6}{kmh:>9}{lm:>9.3f}{fa:>11.0f}"
                  f"{fa / A_EFF / 1e3:>10.2f}")
        print()

    print("【6】临界角：F_a = 0 时仍不脱离的角度范围")
    ratio = V_CLIMB ** 2 / (G * R_ARC)
    th_star = math.degrees(math.acos(min(1.0, ratio)))
    print(f"  令 F_a = 0 ⇒ cosθ ≤ v²/(gR) = {ratio:.3f}"
          f" ⇒ θ* = {th_star:.1f}°")
    print(f"  ⇒ 吸附只在顶点附近 |θ| < {th_star:.1f}° 内是**必要**的；"
          f"过了这一段即使 F_a = 0 也不会脱离")

    print("\n【7】λ ≤ 1 的含义（改正后）")
    print("  λ ≤ 1 ⇒ 顶点 λ ≥ 1 − v²/(gR) 只在 v > 0 时才可能满足")
    print("  ⇒ λ ≤ 1 时**无法静止倒挂**（v = 0 时 N = F_a − mg ≤ 0），"
          "必须靠速度")
    for lam in (0.0, 0.5, 1.0, 2.0):
        if lam >= 1.0:
            print(f"  λ = {lam:.1f}：v_min = 0（可以静止倒挂）")
        else:
            v = math.sqrt((1.0 - lam) * G * R_ARC)
            print(f"  λ = {lam:.1f}：v_min = {v:.2f} m/s"
                  f"（{v * 3.6:.1f} km/h）")

    print("\n" + "=" * 88)
    print("  ★ 全部数字由本脚本现跑现取，文档不得手抄")
    print("=" * 88)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
