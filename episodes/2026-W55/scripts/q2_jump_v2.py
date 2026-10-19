#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **飞越五车**：可行域的干净推导（修正前一版的错误结论）。

## 前一版错在哪

`q2_jump_from_height.py` 得出"平地（$h_0=0$）无解、临界 $h_0\approx0.3$ m"，
**两个说法自相矛盾**（既然 0.3 m 就够，0 附近应该"勉强可行"而不是"无解"）。

**根因**：我用"**给定 (α, h0) 反解 $v_0$**"的写法，
再扫 α 找最优 —— 这个参数化在"卡车很近 + 角度很陡"的区域**会漏解**，
而且"无解"与"临界"用的是两段不同的搜索，**判据不一致**。

## 本版的做法：**直接消元，不用反解**

对固定 $h_0$，从"必须在 $x=L$ 落地"得

$$z(x) = h_0 + x\tan\alpha - \frac{gx^2}{2v_0^2\cos^2\alpha}$$

要求在 $x_t$ 处 $z \ge H_t$、在 $L$ 处 $z = 0$。**两式相减消去 $v_0$**：

$$\underbrace{z(L) - z(x_t)}_{= -H_t\text{ 下的必要关系}} = 0$$

**更直接的做法**：把"$z(L)=0$"解出的 $v_0^2$ 代回 $z(x_t)$，得到**一个只含 α 的函数**，
再判断它能否 $\ge H_t$。**这是本版的关键：** 
$z(x_t)$ 与 $H_t$ 的比较**不需要猜 $v_0$**。

**结论**：清车与落地**可以共存**，条件是一个**关于 α 的下界**。
前一版说"无解"是**搜索漏解**，不是物理不可能。
"""
from __future__ import annotations

import math

G = 9.81


def clearance(h0: float, L: float, xt: float, alpha_deg: float) -> float | None:
    r"""在"必须在 $L$ 落地"的前提下，$x_t$ 处能有多高。"""
    a = math.radians(alpha_deg)
    den = 2.0 * (h0 + L * math.tan(a))
    if den <= 0:
        return None
    v0 = (L / math.cos(a)) * math.sqrt(G / den)
    return h0 + xt * math.tan(a) - G * xt * xt / (2 * v0 * v0 * math.cos(a) ** 2)


def main() -> int:
    print("=" * 94)
    print("  W55 · 飞越五车：可行域的干净推导")
    print("=" * 94)

    L, Ht = 11.0, 4.0
    print(f"\n  L = {L} m（跳跃跨度），H_t = {Ht} m（卡车高）")
    print("  ★ 关键：卡车若靠近起跳点，就必须「陡起飞」；陡起飞又缩短射程。")

    for xt in (2.0, 3.0, 4.0, 6.0):
        print(f"\n--- 卡车距起跳点 x_t = {xt} m ---")
        print(f"  {'α(°)':>6}{'h0=0':>9}{'h0=2':>9}{'h0=5':>9}"
              f"{'h0=10':>9}{'h0=20':>9}")
        for al in (10, 20, 30, 40, 50, 55, 60, 65, 70, 75):
            row = f"  {al:>6}"
            for h0 in (0.0, 2.0, 5.0, 10.0, 20.0):
                c = clearance(h0, L, xt, al)
                row += f"{('—' if c is None else f'{c:.1f}'):>9}"
            print(row)
        print(f"    （表中为 $x_t$ 处的高度；需要 ≥ {Ht} m）")

    # ---------------- 反解临界角 ----------------
    print("\n" + "=" * 94)
    print("  ★ 反解：给定 h0，清过卡车所需的最小起飞角")
    print("=" * 94)
    print(f"  {'x_t(m)':>7}{'h0=0':>10}{'h0=5':>10}{'h0=10':>10}{'h0=20':>10}")
    for xt in (2.0, 3.0, 4.0, 5.0, 6.0, 8.0):
        row = f"  {xt:>7.1f}"
        for h0 in (0.0, 5.0, 10.0, 20.0):
            found = None
            for al10 in range(0, 900):
                al = al10 / 10.0
                c = clearance(h0, L, xt, al)
                if c is not None and c >= Ht:
                    found = al
                    break
            row += f"{('无解' if found is None else f'{found:.0f}°'):>10}"
        print(row)

    print("\n" + "=" * 94)
    print("  ★★★ 干净的结论")
    print("=" * 94)
    print("  ① **平地起飞（h0 = 0）是可以过五车的** —— 但要求起飞角很陡：")
    for xt in (2.0, 3.0, 4.0):
        for al10 in range(0, 900):
            al = al10 / 10.0
            c = clearance(0.0, L, xt, al)
            if c is not None and c >= Ht:
                print(f"     · 卡车在 x_t = {xt} m ⇒ 起飞角须 ≥ **{al:.0f}°**")
                break
    print()
    print("  ② **陡起飞角意味着很大的竖直速度分量** —— 这正是推进器的用武之地。")
    print()
    print("  ③ **从高处起飞（h0 大）会显著放宽角度约束**：")
    for h0 in (0.0, 5.0, 10.0, 20.0):
        for al10 in range(0, 900):
            al = al10 / 10.0
            c = clearance(h0, L, 3.0, al)
            if c is not None and c >= Ht:
                print(f"     · h0 = {h0:>4.1f} m，卡车在 x_t = 3 m ⇒ 起飞角 ≥ {al:.0f}°")
                break
    print()
    print("  ★ 前一版脚本说「平地无解」是**搜索漏解**，在此更正。")
    print("    正确的说法是：**平地可行，但需要很陡的起飞角（≈55–65°），")
    print("    而这要求极大的竖直冲量** —— 于是问题自然接到「推进器预算」。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
