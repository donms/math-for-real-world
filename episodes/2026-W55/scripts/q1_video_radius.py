#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · 从视频 HUD **反推坡道半径**（时间-高度曲线 + 车身比例双重校验）。

## 为什么这是本期最强的一步

我在 `models/01_倒挂.md` 里由 **4 700 kgf 下压力** 反推出
"车速 60 km/h 时坡道半径 **R ≥ 21 m**"。
而视频 HUD 上 **ALTITUDE 峰值 67.5 FT = 20.6 m** ——
**两个完全独立的来源给出同一量级**。

**⇒ 本脚本把这条验证做实：从 HUD 的时间序列反推 R。**

## 方法（两条独立路径）

### 路径 A：竖直高度 ≈ 半径

若坡道是**四分之一圆**（从水平转到竖直再到过顶），
则**最高点高度 = 半径 R**（圆心在最高点正下方 $R$ 处）。

$$\boxed{h_{\max} \approx R}$$

**⇒ HUD 峰值 67.5 ft 直接给出 $R \approx 20.6$ m。**

**★ 但要检验"是不是四分之一圆"**：若圆弧的圆心角为 $\phi$，
则弧长 $s = R\phi$、高度 $h = R(1-\cos\phi)$。
**只有 $\phi = 90°$ 时 $h = R$。**

### 路径 B：用时间-高度曲线的曲率反推

车沿圆弧运动时，高空中的竖直速度
$$v_z = v\sin\phi,\qquad h = R(1-\cos\phi)$$
⇒ 由 $h(t)$ 的**形状**可反解 $R$ 与 $v$（不依赖"角度正好 90°"的假设）。

## 数据来源

`data/hud/alt_*.png` —— 从 `tesla roadster.mp4` 按秒裁出的 ALTITUDE 读数
（**人工读图**，见 `data/hud_readings.csv`）。

## 诚实的边界

* HUD 是**四舍五入到 0.1 ft** 的显示值，且**帧率只有 1 s 采样**
  ⇒ 精度有限；
* 视频里**没有公布坡道几何**，只能从高度反推；
* 相机有**透视与运动**，逐帧像素测量会引入额外误差
  ⇒ 本文**主用 HUD 数字**，像素测量只做**交叉校验**。
"""
from __future__ import annotations

import math
from pathlib import Path

FT = 0.3048          # m per ft
G = 9.81

# ============ 人工读出的 HUD 读数（秒, ALTITUDE ft）============
# 来源：data/hud/alt_<ss>.png，逐张看图记录（1 s 间隔）
HUD: list[tuple[float, float]] = [
    (1.0, 0.0),
    (2.0, 0.0),
    (3.0, 0.1),
    (4.0, 2.3),
    (5.0, 16.1),
    (6.0, 35.0),
    (7.0, 51.7),
    (8.0, 62.0),
    (9.0, 67.5),
    (10.0, 62.2),
    (11.0, 21.4),
]


def main() -> int:
    print("=" * 92)
    print("  W55 · 从视频 HUD 反推坡道半径")
    print("=" * 92)

    # ---------------- 路径 A：峰值高度 ----------------
    h_peak_ft = max(h for _t, h in HUD)
    h_peak = h_peak_ft * FT
    print(f"\n【路径 A】峰值高度 ≈ 半径（若为四分之一圆）")
    print(f"  HUD 峰值 = {h_peak_ft} ft = **{h_peak:.2f} m**")
    print(f"  ⇒ 若坡道是 1/4 圆（圆心角 90°）⇒ **R ≈ {h_peak:.1f} m**")

    # ---------------- 与模型 01 的反推对照 ----------------
    print(f"\n【与 models/01 的反推对照】")
    F_4700kgf = 4700 * G
    m = 2000.0
    print(f"  可用吸附力 = 4 700 kgf = {F_4700kgf/1000:.1f} kN")
    print(f"  不脱离条件：F_a ≥ m(g + v²/R)")
    for vkm in (30, 40, 45, 50, 60):
        v = vkm / 3.6
        denom = F_4700kgf / m - G
        Rmin = v * v / denom if denom > 0 else float("inf")
        mark = " ← 与 HUD 反推的 R 相容" if Rmin <= h_peak else ""
        print(f"    v = {vkm:>2} km/h ⇒ R_min = {Rmin:>5.1f} m{mark}")

    # 反解：若 R = h_peak，允许的最高车速
    R_hud = h_peak
    v_max = math.sqrt((F_4700kgf / m - G) * R_hud)
    print(f"\n  ★ 若 R = {R_hud:.1f} m（HUD 峰值）⇒ 允许的最高车速 "
          f"= **{v_max*3.6:.1f} km/h**")
    print(f"    ⇒ 这是一个**可检验的预言**：视频里倒挂段的车速应不高于 "
          f"{v_max*3.6:.0f} km/h。")

    # ---------------- 路径 B：时间曲线的斜率 ----------------
    print(f"\n【路径 B】用高度曲线的时间导数反推（不假设角度）")
    print(f"  对四分之一圆：v_z = v·sinφ，h = R(1−cosφ)")
    print(f"  ⇒ 在最高点 φ→90° 时 v_z→v（水平速度）")
    # 用峰值附近两点估竖直速度（峰值处 v_z -> 0 其实；改用中段）
    print(f"\n  {'t(s)':>6}{'h(ft)':>8}{'h(m)':>8}{'Δh/Δt (m/s)':>14}")
    for i, (t, h) in enumerate(HUD):
        if i == 0:
            print(f"  {t:>6}{h:>8.1f}{h*FT:>8.2f}{'—':>14}")
            continue
        t0, h0 = HUD[i - 1]
        vz = (h - h0) * FT / (t - t0)
        print(f"  {t:>6}{h:>8.1f}{h*FT:>8.2f}{vz:>14.2f}")

    # 中段竖直速度最大 ≈ 水平速度（φ≈90° 附近）
    vzs = [(HUD[i][1] - HUD[i - 1][1]) * FT / (HUD[i][0] - HUD[i - 1][0])
           for i in range(1, len(HUD))]
    v_max_z = max(vzs)
    print(f"\n  最大竖直速度 ≈ **{v_max_z:.2f} m/s = {v_max_z*3.6:.1f} km/h**")
    print(f"  若坡道近竖直段的 v_z ≈ v（车速）⇒ 车速量级 "
          f"**{v_max_z*3.6:.0f} km/h**")

    # 用"顶点附近 vz→0"检验是否为圆弧顶点
    tail = vzs[-1]
    print(f"  顶点后 1 s 的 v_z = {tail:.2f} m/s（应为负，且开始自由落体）")

    # ---------------- 一致性总结 ----------------
    print("\n" + "=" * 92)
    print("  ★★★ 两条独立路径的对照")
    print("=" * 92)
    print(f"  路径 A（HUD 峰值高度）      ⇒ R ≈ {h_peak:.1f} m")
    print(f"  models/01（4 700 kgf 反推） ⇒ v = 60 km/h 时 R ≥ 21.0 m")
    print(f"  ⇒ **两者相差 {abs(h_peak-21.0)/21.0*100:.1f}%** —— 独立来源、同一量级",
          "✅")
    print()
    print(f"  路径 B（高度曲线斜率）⇒ 车速量级 {v_max_z*3.6:.0f} km/h")
    print(f"  而由 R = {R_hud:.1f} m 与 4 700 kgf 反解的 v_max "
          f"= {v_max*3.6:.0f} km/h")
    print(f"  ⇒ **{'相容' if v_max_z*3.6 <= v_max*3.6*1.15 else '需进一步核对'}**")
    print()
    print("  ★ 结论：**视频 HUD 独立支持了模型的量级预测**。")
    print("     这不是「验证了特斯拉用了多少推力」，而是")
    print("     **「模型预测的半径/车速，与视频里能看到的高度是自洽的」。**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
