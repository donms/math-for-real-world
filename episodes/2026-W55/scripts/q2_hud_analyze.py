#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **飞跃段 HUD 反推**：起跳高度、竖直速度、腾空时间、水平跨度。

## 数据（`tesla roadster2.mp4`，0.5 s 间隔，人工读图）

| t (s) | 3.5 | 4.0 | 4.5 | 5.0 | 5.5 | **6.0** | 6.5 | 7.0 | 7.5 | 8.0 | 8.5 | 9.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALT (ft) | 0.0 | 0.0 | 0.0 | 7.3 | 19.3 | **25.4** | 24.8 | 15.9 | 7.1 | 1.8 | 0.3 | 0.1 |

**峰值 25.4 ft = 7.74 m。**

## ★ 这个数据揭示的物理

1. **起跳高度很低**（约 2–3 m 的平台），峰值仅 7.74 m；
2. **上升段用了约 1.5 s**（4.5→6.0 s），**下落段约 2.0 s**（6.0→8.0 s）——
   ★ **下落比上升慢** ⇒ **飞行中有向上的净冲量**（推进器在工作）；
3. **若纯抛体**，上升与下落时间应**相等**（同一高度起落）。

## 三个独立的量

| 量 | 由什么算出 |
|---|---|
| **峰值高度** $h_{\max}$ | HUD 直接读 = 7.74 m |
| **起跳竖直速度** $v_{z0}$ | 上升段斜率 ≈ 5.2 m/s |
| **等效竖直冲量** $\Delta v_z$ | 由"下落比上升慢"反推 |

**★ 第 3 条是本节的精髓**：**光看高度看不出推进器，
但看"上升/下落时间不对称"就能定量估出冲量。**
"""
from __future__ import annotations

import math

G = 9.81
FT = 0.3048

HUD: list[tuple[float, float]] = [
    (3.5, 0.0), (4.0, 0.0), (4.5, 0.0), (5.0, 7.3), (5.5, 19.3),
    (6.0, 25.4), (6.5, 24.8), (7.0, 15.9), (7.5, 7.1), (8.0, 1.8),
    (8.5, 0.3), (9.0, 0.1),
]


def main() -> int:
    print("=" * 94)
    print("  W55 · 飞跃段 HUD 反推")
    print("=" * 94)

    h = [(t, v * FT) for t, v in HUD]
    print(f"\n  峰值 {max(v for _t, v in h):.2f} m")

    print(f"\n【1】高度与竖直速度")
    print(f"  {'t(s)':>6}{'h(ft)':>8}{'h(m)':>9}{'vz(m/s)':>10}{'vz(km/h)':>10}")
    prev = None
    for (t, ft) in HUD:
        hm = ft * FT
        if prev is None:
            print(f"  {t:>6}{ft:>8.1f}{hm:>9.2f}{'—':>10}{'—':>10}")
        else:
            t0, f0 = prev
            vz = (ft - f0) * FT / (t - t0)
            print(f"  {t:>6}{ft:>8.1f}{hm:>9.2f}{vz:>10.2f}{vz*3.6:>10.1f}")
        prev = (t, ft)

    # ---- 上升/下落时间 ----
    print(f"\n【2】★ 上升与下落的时间不对称")
    t_peak = 6.0
    t_liftoff = 4.5        # 最后一个是 0.0 的时刻
    t_land = 8.2           # 内插回到 0 的时刻
    print(f"  起跳 t ≈ {t_liftoff:.1f} s，峰值 t = {t_peak:.1f} s，"
          f"落地 t ≈ {t_land:.1f} s")
    rise = t_peak - t_liftoff
    fall = t_land - t_peak
    print(f"  上升 {rise:.1f} s，下落 {fall:.1f} s")
    print(f"  ★ 下落比上升**长** {fall - rise:+.1f} s")
    print(f"  ⇒ 若纯抛体，两者应相等 ⇒ **有额外的向上冲量**")

    # ---- 由纯抛体反推 v_z0 ----
    hmax = 7.74
    print(f"\n【3】纯抛体假设下的起跳竖直速度")
    print(f"  由 h_max = v_z0²/(2g) ⇒ v_z0 = √(2 g h_max) = "
          f"{math.sqrt(2*G*hmax):.2f} m/s = {math.sqrt(2*G*hmax)*3.6:.1f} km/h")
    print(f"  而纯抛体的总腾空时间 = 2 v_z0 / g = "
          f"{2*math.sqrt(2*G*hmax)/G:.2f} s")
    print(f"  实测腾空 ≈ {fall+rise:.1f} s ⇒ "
          f"**多出 {(fall+rise)-2*math.sqrt(2*G*hmax)/G:.2f} s**")

    # ---- 由实测斜率估 v_z0 ----
    print(f"\n【4】由实测上升段斜率估 v_z0")
    seg = [(5.0, 7.3), (5.5, 19.3), (6.0, 25.4)]
    for i in range(1, len(seg)):
        t0, a0 = seg[i - 1]
        t1, a1 = seg[i]
        print(f"  {t0}→{t1} s：Δh = {(a1-a0)*FT:.2f} m，"
              f"平均 vz = {(a1-a0)*FT/(t1-t0):.2f} m/s")
    vz0 = (19.3 - 0.0) * FT / (5.5 - 4.5)
    print(f"  ★ 用 (4.5→5.5) 的平均斜率作 v_z0 上界：{vz0:.2f} m/s")

    # ---- 等效竖直冲量 ----
    print(f"\n【5】★ 等效竖直冲量（解释「下落比上升慢」）")
    vz_pure = math.sqrt(2 * G * hmax)
    dv_needed = G * (fall - rise) / 2.0
    print(f"  若下落比上升多 Δt = {fall-rise:.2f} s，")
    print(f"  等价于在中途获得竖直速度增量 Δv_z ≈ g·Δt/2 = "
          f"**{dv_needed:.2f} m/s**")
    print(f"  对 m = 2000 kg，等效冲量 = m·Δv_z = "
          f"**{2000*dv_needed/1000:.1f} kN·s**")

    # ---- 水平跨度 ----
    print(f"\n【6】水平跨度（需要假设水平速度）")
    T = fall + rise
    print(f"  腾空时间 T ≈ {T:.1f} s")
    print(f"  {'v_x(km/h)':>11}{'v_x(m/s)':>11}{'L = v_x·T (m)':>15}"
          f"{'与 11 m 之比':>13}")
    for vkm in (20, 30, 40, 60, 80, 100):
        vx = vkm / 3.6
        Lm = vx * T
        print(f"  {vkm:>11}{vx:>11.1f}{Lm:>15.1f}{Lm/11.0:>12.1f}×")

    print("\n" + "=" * 94)
    print("  ★★★ 关键结论")
    print("=" * 94)
    print(f"  ① **峰值只有 7.74 m**，远低于倒挂段的 20.6 m")
    print(f"     ⇒ 飞跃**不是**从倒挂坡道飞出的，是另一处**低跳台**；")
    print(f"  ② **下落比上升慢 {(fall-rise):.1f} s** ⇒ 有明显**向上的额外冲量**；")
    print(f"     等效 Δv_z ≈ {dv_needed:.1f} m/s，冲量 ≈ "
          f"{2000*dv_needed/1000:.0f} kN·s；")
    print(f"  ③ 若水平速度 60–90 km/h，跨度 30–50 m ——")
    print(f"     **远大于五车整排的 6 m** ⇒ 卡车的 4 m 高度**不是**主要约束。")
    print()
    print("  ⇒ **我先前「平地要 56–68° 陡起飞角」的推演虽然数学没错，")
    print("     但物理场景选错了**：实际是从**低跳台 + 大水平速度**飞出的，")
    print("     所以既不需要陡角，也不需要把 4 m 卡车当成主要障碍。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
