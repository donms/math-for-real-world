#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **水平加减速改用轮胎（油门/刹车）可行吗？**

## 用户的问题

> **"加速和减速用车的油门和刹车，可行吗"**

## 为什么这个问题不像看上去那么简单

**轮胎能传递的最大水平力受"抓地力上限"限制**：

$$F_{\max} = \mu N$$

其中 $N$ 是**法向力**。平时 $N = mg$，但**这辆车有风扇**：

$$\boxed{N = mg + F_{\text{fan}}}$$

**⇒ 风扇下压力 46.1 kN 是车重的 2.35 倍 ⇒ $N$ 变成 3.35 倍 ⇒
抓地力上限也变成 3.35 倍。**

$$\Rightarrow\quad a_{\max} = \mu\left(g + \frac{F_{\text{fan}}}{m}\right)$$

**⇒ 这辆车的"油门"加速能力，可能远超普通跑车 ——
甚至可能不需要主推进器就能达到公布的加速度。**

## 要回答的三件事

1. **加速**：0 → 60 km/h 用轮胎要多久、多远？与公布 0-60 mph 0.81 s 是否矛盾？
2. **减速**：落地后 60 km/h → 0 用刹车要多久、多远？
3. **对气罐的影响**：水平方向不用气，气罐预算省多少？
"""
from __future__ import annotations

import math

# ---- 车辆参数 ----
M = 2000.0            # 整备质量 (kg)
G = 9.81
F_FAN = 46.1e3        # 风扇下压力 (N)，演示 HUD 显示 ≈4700 kgf
V_JUMP = 60 / 3.6     # 起跳水平速度 (m/s) = 60 km/h
P_MOTOR = 745e3       # 电机功率 ≈1000 hp (W)

# 轮胎附着系数（干沥青）
MU = {
    "街道高性能胎": 1.10,
    "半热熔": 1.30,
    "赛道光头胎": 1.50,
}


def piecewise_time(v_end: float, a_tr: float, v_star: float
                   ) -> tuple[float, float]:
    r"""**分段**算纯电机加速：低速抓地限、高速功率限。

    $$a(v) = \min\left(\mu(g+F/m),\ \frac{P}{mv}\right)$$

    * $v < v^*$：$a = a_{tr}$ 常数 ⇒ $t_1 = v^*/a_{tr}$
    * $v > v^*$：$a = P/(mv)$ ⇒
      $\displaystyle t_2 = \int\frac{m v\,dv}{P}
      = \frac{m(v^2 - v^{*2})}{2P}$

    **★ 注意：这是"纯电机"的能力，不含主推进器。**
    """
    v1 = min(v_star, v_end)
    t1 = v1 / a_tr
    d1 = 0.5 * a_tr * t1 * t1
    if v_end <= v_star:
        return t1, d1
    t2 = M * (v_end ** 2 - v_star ** 2) / (2 * P_MOTOR)
    # 距离 t2 段：∫ v dt = ∫ v·(mv/P) dv = m(v²-v*²)... 数值积一下
    n = 400
    d2 = 0.0
    for i in range(n):
        vv = v_star + (v_end - v_star) * (i + 0.5) / n
        dt = M * (v_end - v_star) / (n * P_MOTOR) * vv
        d2 += vv * dt
    return t1 + t2, d1 + d2


def accel_time(v: float, a: float) -> tuple[float, float]:
    r"""匀加速到 $v$ 的时间与距离。"""
    t = v / a
    return t, 0.5 * a * t * t


def main() -> int:
    print("=" * 88)
    print("  W55 · 水平加减速改用轮胎：可行吗")
    print("=" * 88)

    W = M * G
    print(f"\n  车重 W = {W/1000:.1f} kN")
    print(f"  风扇下压力 = {F_FAN/1000:.1f} kN = 车重的 "
          f"{F_FAN/W:.2f} 倍")
    print(f"  ⇒ 有风扇时法向力 N = {(W+F_FAN)/1000:.1f} kN"
          f"（车重的 {(W+F_FAN)/W:.2f} 倍）")

    print(f"\n【1】抓地力上限下的最大加速度")
    print(f"  {'轮胎':<14}{'μ':>6}{'无风扇 a':>11}{'有风扇 a':>11}"
          f"{'有风扇 g 数':>12}")
    for nm, mu in MU.items():
        a0 = mu * G
        a1 = mu * (G + F_FAN / M)
        print(f"  {nm:<14}{mu:>6.2f}{a0:>10.1f}{a1:>11.1f}"
              f"{a1/G:>12.2f}")

    print(f"\n【2】★ 加速的真实限制：**低速受抓地力限、高速受功率限**")
    print(f"  抓地极限 $a_{{tr}} = \\mu(g + F/m)$；"
          f"功率极限 $a_{{pw}} = P/(mv)$")
    print(f"  两者相等处的速度 $v^* = P/(m\\,a_{{tr}})$")
    print()
    print(f"  {'轮胎':<14}{'a_tr':>8}{'v*':>8}{'0-60km/h':>10}{'距离':>8}"
          f"{'0-60mph':>10}")
    for nm, mu in MU.items():
        atr = mu * (G + F_FAN / M)
        vstar = P_MOTOR / (M * atr)
        t60, d60 = piecewise_time(V_JUMP, atr, vstar)
        t96, _ = piecewise_time(60 * 1609.344 / 3600, atr, vstar)
        print(f"  {nm:<14}{atr:>8.1f}{vstar:>8.2f}{t60:>10.2f}{d60:>8.1f}"
              f"{t96:>10.2f}")
    print(f"  ★ 电机 {P_MOTOR/1000:.0f} kW ⇒ 功率极限在 60 km/h 处只有 "
          f"{P_MOTOR/(M*V_JUMP):.1f} m/s²"
          f"（{P_MOTOR/(M*V_JUMP)/G:.2f} g）")

    print(f"\n【3】落地后刹停（60 km/h → 0）")
    print(f"  {'轮胎':<14}{'a(m/s²)':>10}{'耗时(s)':>10}{'距离(m)':>10}")
    for nm, mu in MU.items():
        a = mu * (G + F_FAN / M)
        t, d = accel_time(V_JUMP, a)
        print(f"  {nm:<14}{a:>10.1f}{t:>10.2f}{d:>10.1f}")

    print(f"\n【4】与公布数据对照")
    pub_t = 0.81
    pub_v = 60 * 1609.344 / 3600      # 60 mph in m/s
    a_pub = pub_v / pub_t
    print(f"  公布 **0–60 mph 0.81 s** ⇒ 0→{pub_v:.2f} m/s"
          f"，平均 a = **{a_pub:.1f} m/s² = {a_pub/G:.2f} g**")
    print(f"  {'':<22}{'需要 a':>10}{'哪种轮胎够':>14}")
    for nm, mu in MU.items():
        a1 = mu * (G + F_FAN / M)
        tag = "够" if a1 >= a_pub else "不够"
        print(f"  {nm:<22}{a_pub:>10.1f}{tag:>14}")
    a_no_fan = MU['赛道光头胎'] * G
    print(f"  ★ 若无风扇（仅车重）：光头胎也只有 {a_no_fan:.1f} m/s²"
          f"（{a_no_fan/G:.2f} g）⇒ **不够**")
    print(f"  ⇒ **正是风扇的下压力，让「轮胎方案」变得可行。**")

    print(f"\n【5】对气罐的影响")
    I_acc = M * V_JUMP
    I_brake = M * V_JUMP
    print(f"  水平加速冲量 {I_acc/1000:.1f} kN·s、"
          f"制动冲量 {I_brake/1000:.1f} kN·s")
    print(f"  若全用冷气：合计 **{(I_acc+I_brake)/1000:.1f} kN·s**"
          f" = 气罐可用量（164）的 "
          f"{(I_acc+I_brake)/1000/164.1*100:.0f}%")
    print(f"  若改用轮胎：**水平耗气 = 0** ⇒ 气罐只服务竖直方向")
    print(f"  ⇒ 竖直两段 67.8 kN·s 占 41%，**余量从 59% 变成 100% 全留**")

    print("\n" + "=" * 88)
    print("  ★★★ 结论（分两步看，答案不一样）")
    print("=" * 88)
    print("  ① **对「跳 60 km/h」这件事：完全可行，不用气**")
    print("     纯电机 0→60 km/h：半热熔 **0.47 s / 4.4 m**")
    print("     ⇒ 只要 **4.4 m 助跑**，气罐一点不动")
    print()
    print("  ② **但公布的 0–60 mph 0.81 s，纯电机做不到**")
    print("     纯电机 0→60 mph：半热熔 **1.07 s**（差 0.26 s，慢 32%）")
    print("     原因：60 mph 处功率极限只剩 "
          f"{P_MOTOR/(M*26.82):.1f} m/s²")
    print("     ⇒ **这正是主推进器存在的理由**（补上 0.26 s 的差）")
    print()
    print("  ③ **刹车**：60→0 半热熔 **0.39 s / 3.3 m**")
    print("     刹车不受功率限制（只受抓地力），所以比加速更利索")
    print()
    print("  ④ **气罐影响**：水平耗气 **从 66.7 降到 0**")
    print("     ⇒ 气罐只服务竖直，余量从 59% 变成"
          " **100% 可用**（实际只花 41%）")
    print()
    print("  ⑤ ★ **一个反直觉的要点**：")
    print(f"     无风扇时光头胎只有 {MU['赛道光头胎']*G:.1f} m/s²（1.50 g），")
    print(f"     **连 60 km/h 都要 1.1 s** —— 风扇把法向力提到 3.35 倍车重，")
    print(f"     才让「轮胎方案」站得住。**风扇不只是过弯用的。**")
    print()
    print("  ⇒ 建议：**加速与制动都用轮胎**，气罐专供竖直（起飞/缓冲/调姿）。")
    print("     这样气罐余量充足，且全部有官方数据支撑。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
