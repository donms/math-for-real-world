#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **飞越五车**的几何可行性（诊断：为什么"普通抛体"不够）。

## 这张截图给出的两个硬数

* 五车整排跨度 $S \approx 6$ m（以轿车长 4.75 m 标定）
* 跳跃水平跨度 $L \approx 11$ m

## 但立刻出现一个矛盾

$$\text{等高点抛体：}\ L = \frac{v_0^2\sin 2\alpha}{g}
\quad\Longrightarrow\quad
h_{\max} = \frac{v_0^2\sin^2\alpha}{2g} = \frac{L}{4}\tan\alpha$$

**⇒ 跨 11 m 时，即使 45° 起飞，最高点也只有 $11/4 = 2.75$ m。**

**而卡车高约 4 m —— 普通抛体根本清不过去。**

## 本脚本要回答：要怎么才过得去

约束有两条：

$$
\begin{cases}
\text{① 在卡车位置 } x_t \text{ 处，轨迹高度 } \ge H_t \\
\text{② 在 } x = L \text{ 处落回地面}
\end{cases}
$$

**关键洞察**：卡车**不在**跳跃中点，而是**紧挨起跳端**
（截图里卡车车头几乎贴着平板前端）。
**⇒ 轨迹必须在"刚起飞不久"就达到 4 m 高，这要求**起飞角很大**。

**★ 这正好解释了为什么演示里车是"喷气跃过"而不是"冲上跳台飞出去"**：
**纯抛体做不到，必须叠加推进器的竖直冲量。**
"""
from __future__ import annotations

import math

G = 9.81


def v0_needed(xt: float, ht: float, alpha_deg: float) -> float | None:
    r"""要在水平距离 $x_t$ 处达到高度 $h_t$，所需的 $v_0$。

    由 $h = x\tan\alpha - \dfrac{gx^2}{2v_0^2\cos^2\alpha}$ 解 $v_0$：

    $$v_0^2 = \frac{gx^2}{2\cos^2\alpha\left(x\tan\alpha - h\right)}$$

    返回 `None` 表示该角度下**几何上不可达**（分母 $\le 0$）。
    """
    a = math.radians(alpha_deg)
    den = 2 * math.cos(a) ** 2 * (xt * math.tan(a) - ht)
    if den <= 0:
        return None
    return math.sqrt(G * xt * xt / den)


def y_at(x: float, alpha_deg: float, v0: float) -> float:
    a = math.radians(alpha_deg)
    return x * math.tan(a) - G * x * x / (2 * v0 * v0 * math.cos(a) ** 2)


def main() -> int:
    print("=" * 94)
    print("  W55 · 飞越五车：为什么「普通抛体」做不到")
    print("=" * 94)

    L = 11.0          # 跳跃水平跨度 (m)
    print(f"\n  已知：L ≈ {L:.1f} m（由轿车长 4.75 m 标定整排 ~6 m + 两端余量）")

    # ---------------- 1) 等高点抛体的高度上限 ----------------
    print(f"\n【1】等高点抛体的高度上限（跨 {L:.0f} m 时）")
    print(f"  {'α(°)':>6}{'v0(m/s)':>10}{'v0(km/h)':>11}{'h_max(m)':>10}")
    for al in (20, 30, 45, 60, 70):
        a = math.radians(al)
        v0 = math.sqrt(L * G / math.sin(2 * a))
        hmax = v0 ** 2 * math.sin(a) ** 2 / (2 * G)
        print(f"  {al:>6}{v0:>10.2f}{v0*3.6:>11.1f}{hmax:>10.2f}")
    print(f"\n  ★ 恒定关系：$h_{{\\max}} = (L/4)\\tan\\alpha$")
    print(f"     ⇒ 45° 时 h_max = {L/4*math.tan(math.radians(45)):.2f} m")
    print(f"     ⇒ 要 h_max ≥ 4.5 m 需 tan α ≥ {4.5/(L/4):.2f}"
          f" ⇒ α ≥ **{math.degrees(math.atan(4.5/(L/4))):.0f}°**")
    print(f"     ⇒ 但那会让水平射程大幅缩短 ⇒ **不可能同时满足**。")

    # ---------------- 2) 同时满足两个约束 ----------------
    print(f"\n【2】若卡车靠近起跳端（x_t 小），约束变松")
    print(f"  条件① 在 x_t 处高度 ≥ H_t；条件② 在 x = L 处落地")
    for Ht in (4.0, 4.4):
        print(f"\n  --- 卡车高 H_t = {Ht} m ---")
        hdr = f"  {'x_t(m)':>7}"
        for al in (30, 40, 50, 60, 70):
            hdr += f"{'α=' + str(al) + '°':>10}"
        print(hdr)
        for xt in (2.0, 3.0, 4.0, 5.0, 6.0):
            row = f"  {xt:>7.1f}"
            for al in (30, 40, 50, 60, 70):
                v = v0_needed(xt, Ht, al)
                row += f"{('—' if v is None else f'{v*3.6:.0f}'):>10}"
            print(row)
        print("    （表内为满足条件①所需的最低车速 km/h）")

    # ---------------- 3) 判读：需要的"额外推力" ----------------
    print("\n" + "=" * 94)
    print("【3】★ 结论：必须叠加推进器")
    print("=" * 94)
    xt, Ht = 3.0, 4.0
    al = 60.0
    v_need = v0_needed(xt, Ht, al)
    if v_need is None:
        print(f"  取卡车在 x_t = {xt} m、高 {Ht} m、起飞角 {al:.0f}° ⇒ "
              f"**该角度下几何不可达**（需 tanα ≥ H_t/x_t）")
        v_need = float("nan")
    else:
        print(f"  取卡车在 x_t = {xt} m、高 {Ht} m、起飞角 {al:.0f}°：")
        print(f"    条件① 要求 v0 ≥ {v_need:.2f} m/s = {v_need*3.6:.0f} km/h")
    if v_need == v_need:
        y = y_at(L, al, v_need)
        print(f"    此时在 x = L = {L} m 处的高度 y = {y:.2f} m")
        if y > 0:
            print(f"    ⇒ **还差 {y:.2f} m 才能落回地面** —— "
                  f"水平射程不够，说明纯抛体在这个角度下过不去。")
    else:
        y = float("nan")
    print()
    print("  ★ 三条出路：")
    print("    (a) **水平速度更大**（射程够），但 h_max 会随之变化，需联立；")
    print("    (b) ★ **在飞行中再喷一次竖直冲量**，把轨迹「顶」起来 ——")
    print("        这正是 Roadster 装推进器的意义，也是演示里看到的那股白气；")
    print("    (c) ★ **从有高度的坡道起飞**（像倒挂演示那样冲上坡道再飞出），")
    print("        起跳高度 $h_0 > 0$ 会直接抬升整条轨迹。")
    print()
    print("  ⇒ **问题 2 的正确建模不是「一个抛体」，而是「抛体 + 中途冲量」**。")
    print("     这一点是本节最重要的发现。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
