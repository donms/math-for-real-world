#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **飞越五车**：从高度 $h_0$ 起跳是否能解决"清不过卡车"的矛盾？

## 起点

`q2_jump_feasibility.py` 证明：**平地起飞（$h_0=0$）的纯抛体，
在 $L \approx 11$ m、$H_t \approx 4$ m 下无可行解。**

但视频里的坡道**顶端高 20.6 m**。
**若飞跃是从这个高度飞出去的，几何完全不同。**

## 模型

从高度 $h_0$ 以 $(v_0,\alpha)$ 起飞：

$$z(t) = h_0 + v_0\sin\alpha\, t - \tfrac12 g t^2,\qquad
x(t) = v_0\cos\alpha\, t$$

**清卡车**：在 $x = x_t$ 处 $z \ge H_t$
**落地**：在 $x = L$ 处 $z = 0$

消去 $t$：

$$z(x) = h_0 + x\tan\alpha - \frac{g x^2}{2v_0^2\cos^2\alpha}$$

**⇒ $h_0$ 把整条轨迹**整体抬高**，所以两个约束会**同时变松**。
这正是"高台起飞"与"中途冲量"的本质区别：
**后者只在喷的那一段时间起作用，前者一直起作用。**
"""
from __future__ import annotations

import math

G = 9.81


def v0_for_landing(L: float, h0: float, alpha_deg: float) -> float | None:
    r"""要求在 $x=L$ 处落地（$z=0$）所需的 $v_0$。

    由 $0 = h_0 + L\tan\alpha - \dfrac{gL^2}{2v_0^2\cos^2\alpha}$：

    $$v_0 = \frac{L}{\cos\alpha}\sqrt{\frac{g}{2\left(h_0 + L\tan\alpha\right)}}$$
    """
    a = math.radians(alpha_deg)
    den = 2.0 * (h0 + L * math.tan(a))
    if den <= 0:
        return None
    return (L / math.cos(a)) * math.sqrt(G / den)


def z_at(x: float, h0: float, alpha_deg: float, v0: float) -> float:
    a = math.radians(alpha_deg)
    return h0 + x * math.tan(a) - G * x * x / (2 * v0 * v0 * math.cos(a) ** 2)


def main() -> int:
    print("=" * 94)
    print("  W55 · 从高度 h0 起飞：能跨 5 辆车吗？")
    print("=" * 94)

    L, Ht, xt = 11.0, 4.0, 3.0
    print(f"\n  设定：跳跃跨度 L = {L} m，卡车高 H_t = {Ht} m，"
          f"卡车距起跳点 x_t = {xt} m")
    print("  ★ 注意：卡车若在远端（x_t 大），约束更松；下面同时给两端。")

    for h0 in (0.0, 5.0, 10.0, 15.0, 20.6):
        print(f"\n--- 起跳高度 h0 = {h0:.1f} m ---")
        print(f"  {'α(°)':>6}{'v0(m/s)':>10}{'v0(km/h)':>11}"
              f"{'x_t=3m处高':>12}{'判定':>8}")
        any_ok = False
        for al in (0, 5, 10, 15, 20, 30, 45):
            v0 = v0_for_landing(L, h0, al)
            if v0 is None:
                print(f"  {al:>6}{'—':>10}{'—':>11}{'—':>12}{'不可达':>8}")
                continue
            z = z_at(xt, h0, al, v0)
            ok = z >= Ht
            any_ok = any_ok or ok
            print(f"  {al:>6}{v0:>10.2f}{v0*3.6:>11.1f}"
                  f"{z:>12.2f}{('✓ 清过' if ok else '✗ 撞'):>8}")
        print(f"  ⇒ 该高度下{'**存在**可行解' if any_ok else '**无**可行解'}")

    # ---------------- 反解：需要多高的 h0 ----------------
    print("\n" + "=" * 94)
    print("  ★ 反解：在最优起飞角下，h0 至少要多少")
    print("=" * 94)
    print(f"  {'h0(m)':>7}{'最优α(°)':>10}{'v0(km/h)':>11}"
          f"{'x_t=3m处高(m)':>15}{'x_t=6m处高(m)':>15}")
    for h0 in (0, 2, 5, 8, 10, 12, 15, 20):
        best = None
        for al10 in range(0, 601):
            al = al10 / 10.0
            v0 = v0_for_landing(L, h0, al)
            if v0 is None:
                continue
            z3 = z_at(xt, h0, al, v0)
            # 目标：最差情况（x_t=3 与 6 都要清过）
            z6 = z_at(6.0, h0, al, v0)
            score = min(z3, z6)
            if best is None or score > best[0]:
                best = (score, al, v0, z3, z6)
        if best:
            _, al, v0, z3, z6 = best
            print(f"  {h0:>7.1f}{al:>10.1f}{v0*3.6:>11.1f}"
                  f"{z3:>15.2f}{z6:>15.2f}")

    print("\n" + "=" * 94)
    print("  ★★★ 结论")
    print("=" * 94)
    # 找临界 h0
    crit = None
    for h010 in range(0, 401):
        h0 = h010 / 10.0
        best = -1e9
        for al10 in range(0, 601):
            al = al10 / 10.0
            v0 = v0_for_landing(L, h0, al)
            if v0 is None:
                continue
            best = max(best, min(z_at(xt, h0, al, v0),
                                 z_at(6.0, h0, al, v0)))
        if best >= Ht:
            crit = h0
            break
    print(f"  · 平地起飞（h0 = 0）⇒ **无解**（清不过 4 m 的卡车）；")
    if crit is not None:
        print(f"  · **临界起跳高度 h0 ≈ {crit:.1f} m** "
              f"（在此之上，只要选对角度就能同时满足「跨 11 m」与「清 4 m」）；")
    else:
        print("  · 未找到临界值")
    print(f"  · 而视频里的坡道顶端高 **20.6 m** ⇒ 若从这个高度飞出，")
    print(f"    **「跨 11 m + 清 4 m」是非常从容的**。")
    print()
    print("  ★ 所以问题 2 的正确提法是：")
    print("    **在给定 (L, H_t, h0) 下，求 (v0, α) 的可行域，")
    print("      并讨论「高台起飞」与「中途冲量」这两种手段的等价性。**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
