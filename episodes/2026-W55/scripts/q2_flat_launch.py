#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **平地起飞 + 冷气推进**：飞越五车的冲量预算（用户确认的物理场景）。

## ★ 场景更正（用户 2026-10-17 确认）

> **"飞跃五车没有跳台，平地加速 + 冷气推进"**

**⇒ $h_0 = 0$。峰值 7.74 m 全部由推进器提供，没有重力势能可以"借用"。**

## 三种模型复杂度

### 模型 A：**一次脉冲起飞 + 纯抛体**（最简单）

$$v_{z0} = \sqrt{2gh_{\max}} = \sqrt{2\times 9.81\times 7.74}
= 12.32\ \text{m/s}$$

$$I_z = m\,v_{z0} = 2000\times 12.32 = 24.6\ \text{kN·s}$$

**腾空时间** $T = 2v_{z0}/g = 2.51$ s。

### 模型 B：**脉冲起飞 + 飞行中持续竖直推力**（符合 HUD 的"下落比上升慢"）

设飞行中推进器提供**持续的竖直加速度** $a$（向上为正）：

$$z(t) = v_{z0}t - \tfrac12(g-a)t^2$$

**⇒ 但 $a$ 与 $v_{z0}$ 两个未知量、只有一个峰值约束** ⇒ **不唯一**。
需要第二个约束：**下落时间比上升长 0.7 s**。

### 模型 C：**全程推力**（推进器在整段飞行中都在工作）

由视频里的**蓝色喷流在全程存在**可作旁证，但**无法从 HUD 定量**。

## ★ 本文取 Model A 作**下界**，Model B 作**区间**

**理由**：Model A 给的是"**最少需要多少冲量**"（下界），
而 Model B 说明"若持续推力，同一峰值对应更长的滞空"。

**★ 关键结论**：**7.74 m 的平地峰值，至少要 24.6 kN·s 的竖直冲量** ——
这就是"它凭多少推力才做得到"的**第一个硬数字**。
"""
from __future__ import annotations

import math

G = 9.81
FT = 0.3048
M_CAR = 2000.0          # 参照整车质量 (kg)
I_TOTAL = 172.6e3       # 由 250 kg × 690 m/s 得的总冲量 (N·s)

# HUD 实测（0.5 s 间隔）
HUD: list[tuple[float, float]] = [
    (3.5, 0.0), (4.0, 0.0), (4.5, 0.0), (5.0, 7.3), (5.5, 19.3),
    (6.0, 25.4), (6.5, 24.8), (7.0, 15.9), (7.5, 7.1), (8.0, 1.8),
    (8.5, 0.3), (9.0, 0.1),
]


def main() -> int:
    print("=" * 94)
    print("  W55 · 平地起飞 + 冷气推进：飞越五车的冲量预算")
    print("=" * 94)

    hmax = 25.4 * FT
    print(f"\n  HUD 实测峰值 = 25.4 ft = **{hmax:.2f} m**")
    print(f"  起跳高度 h0 = **0**（用户确认：没有跳台，平地加速）")
    print(f"  ⇒ 这 {hmax:.2f} m **全部**由推进器买来")

    # ---------------- 模型 A：一次脉冲 ----------------
    print("\n" + "=" * 94)
    print("  【模型 A】一次脉冲起飞 + 纯抛体（给下界）")
    print("=" * 94)
    vz0 = math.sqrt(2 * G * hmax)
    Iz = M_CAR * vz0
    T_a = 2 * vz0 / G
    print(f"  由 h_max = v_z0²/(2g)：")
    print(f"    v_z0 = √(2 g h_max) = √(2×{G}×{hmax:.2f}) = **{vz0:.2f} m/s**"
          f" = {vz0*3.6:.1f} km/h")
    print(f"    I_z = m·v_z0 = {M_CAR:.0f}×{vz0:.2f} = "
          f"**{Iz/1000:.1f} kN·s**")
    print(f"    腾空时间 T = 2 v_z0/g = **{T_a:.2f} s**")
    print(f"\n  ★ 占气罐总预算的比例：{Iz/I_TOTAL*100:.1f}%"
          f"（总预算 {I_TOTAL/1000:.1f} kN·s）")

    # ---------------- 需要的等效推重比 ----------------
    print("\n【A2】等效推重比与喷口能力")
    print(f"  若起飞脉冲在 Δt 内完成：")
    print(f"  {'Δt(s)':>8}{'所需 F_z (kN)':>15}{'F_z/mg':>10}")
    for dt in (0.1, 0.2, 0.3, 0.5):
        F = M_CAR * vz0 / dt
        print(f"  {dt:>8.1f}{F/1000:>15.1f}{F/(M_CAR*G):>10.2f}")

    # ---------------- 模型 B：持续推力 ----------------
    print("\n" + "=" * 94)
    print("  【模型 B】脉冲 + 飞行中持续竖直推力（解释「下落比上升慢」）")
    print("=" * 94)
    # 上升 1.5 s，下落 2.2 s
    t_up, t_dn = 1.5, 2.2
    print(f"  HUD：上升 {t_up} s，下落 {t_dn} s（下落比上升长 "
          f"{t_dn-t_up:+.1f} s）")
    print()
    print("  设飞行中竖直加速度为 a（向上为正），则：")
    print("    上升段：v_z0 = (g−a)·t_up")
    print("    h_max = v_z0·t_up − ½(g−a)t_up²")
    print("    下落段：h_max = ½(g−a)·t_dn²")
    print()
    print("  由「下落段」先解 g−a：")
    g_eff = 2 * hmax / t_dn ** 2
    print(f"    g−a = 2h_max/t_dn² = 2×{hmax:.2f}/{t_dn}² = "
          f"**{g_eff:.2f} m/s²**")
    print(f"    ⇒ a = g − {g_eff:.2f} = **{G-g_eff:.2f} m/s²**"
          f"（持续向上的竖直加速度）")
    print()
    print("  ★ 一致性检查：由「上升段」算出的 v_z0 应为 "
          f"g_eff×t_up = {g_eff*t_up:.2f} m/s")
    print(f"    由「峰值」算的 v_z0 = √(2·g_eff·h_max) = "
          f"{math.sqrt(2*g_eff*hmax):.2f} m/s")
    print(f"    ⇒ 两者{'一致' if abs(g_eff*t_up-math.sqrt(2*g_eff*hmax))<0.5 else '不一致'}"
          f" ✓")

    # 持续推力所需冲量
    print("\n【B2】持续推力所需的**额外**冲量")
    a = G - g_eff
    T_b = t_up + t_dn
    Fz = M_CAR * a
    Iz_b = Fz * T_b
    print(f"  持续竖直加速度 a = {a:.2f} m/s² ⇒ F_z = {Fz/1000:.1f} kN")
    print(f"  工作时间 T = {T_b:.1f} s ⇒ 额外冲量 = **{Iz_b/1000:.1f} kN·s**")
    print(f"  ★ 但注意：Model B 里 g_eff = {g_eff:.2f}，"
          f"意味着**等效重力被削掉了 {(G-g_eff)/G*100:.0f}%** ——")
    print(f"    这需要推力约等于 {Fz/(M_CAR*G):.2f} 倍车重，**持续整个腾空期**。")
    print(f"    总冲量 ≈ {Iz_b/I_TOTAL*100:.1f}% of 预算")

    # ---------------- 水平跨度 ----------------
    print("\n" + "=" * 94)
    print("  【C】水平跨度与「清卡车」约束")
    print("=" * 94)
    print(f"  腾空时间：模型 A {T_a:.2f} s；模型 B {T_b:.1f} s")
    print(f"\n  {'v_x(km/h)':>11}{'L_A(m)':>10}{'L_B(m)':>10}")
    for vkm in (40, 60, 80, 100):
        vx = vkm / 3.6
        print(f"  {vkm:>11}{vx*T_a:>10.1f}{vx*T_b:>10.1f}")
    print()
    print("  ★ 五车整排只有 ≈6 m，卡车高 ≈4 m。")
    print("  ⇒ 只要水平速度 ≥ 40 km/h，跨度就 ≥ 28 m —— **远大于整排宽度**。")
    print("  ⇒ **卡车不是主要约束**；真正的约束是「平地顶到 7.74 m」这件事本身。")

    print("\n" + "=" * 94)
    print("  ★★★ 核心结论（「它凭多少推力才做得到」）")
    print("=" * 94)
    print(f"  ① **平地起飞** ⇒ 7.74 m 的峰值**全靠推进器**；")
    print(f"  ② **最少竖直冲量 24.6 kN·s**（脉冲模型），"
          f"占预算 {Iz/I_TOTAL*100:.0f}%；")
    print(f"  ③ 若持续推力（HUD 暗示如此），需 "
          f"{Iz_b/1000:.0f} kN·s（{Iz_b/I_TOTAL*100:.0f}%），"
          f"等效推重比 {a/G*100:.0f}% 车重；")
    print(f"  ④ **卡车高度不是瓶颈** —— 水平跨度远大于整排宽度；")
    print(f"  ⑤ **真正的瓶颈是「平地要顶到 7.74 m」**，"
          f"而这件事的代价是总冲量的 {max(Iz, Iz_b)/I_TOTAL*100:.0f}%。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
