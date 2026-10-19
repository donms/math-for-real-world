#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · 用**俯视截图**标定"飞越五车"的几何（跨度 $L$、越障高度 $h$）。

## 这张图的特殊价值

用户提供的截图是**近乎俯视**的角度 —— 这比侧视更适合量"跨度"：
侧视里水平距离会被透视压缩，俯视里"车辆排列方向"的长度**接近真实比例**。

## 方法（全部以**轿车长度**为尺度基准）

1. 量出图中**一辆轿车**的像素长度 $l_{\text{px}}$（已知实车约 4.6–4.9 m）；
2. 得尺度 $\kappa = l_{\text{px}} / l_{\text{m}}$（px/m）；
3. 量出**五辆车整排**在画面里的跨度 $S_{\text{px}}$；
4. 换成米：$S = S_{\text{px}}/\kappa$；
5. **跳跃的水平跨度** $L$ ≈ $S$ + 起跳/落地余量（车长的一部分）。

## ★ 为什么必须给区间

* 图中车辆是**斜置**的（不是正对相机），长度会被缩短或拉长；
* 俯视有**角度**，不是正俯；
* 五辆车的**具体型号**不知道（用"轿车"统一长度是近似）；
* **起跳点与落地点**在图中**看不到**（截图是空中的一刻），
  只能由"整车排跨度"加余量估计。

**⇒ 本文只给 $L$ 的**量级与区间**，不给单点值。**
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W55"
JP = EP / "data" / "jump"


def main() -> int:
    print("=" * 92)
    print("  W55 · 从俯视截图标定「飞越五车」的几何")
    print("=" * 92)

    p = JP / "jump_overhead.png"
    a = np.asarray(Image.open(p).convert("RGB")).astype(int)
    H, W, _ = a.shape
    print(f"\n  图像 {W}×{H}")

    # ---------------- 1) 金色轿车的像素长度 ----------------
    # 该车在图中位于 x≈140..290, y≈370..430（见 row_zoom8x.png 的 8× 放大）
    print("\n【1】金色轿车（尺度基准）")
    sub = a[365:435, 135:300]
    mx = sub.max(axis=2)
    mn = sub.min(axis=2)
    # 车身：亮、暖色（金色/香槟），且不是纯白高光
    warm = (sub[:, :, 0] > 90) & (sub[:, :, 0] - sub[:, :, 2] > 22)
    ys, xs = np.nonzero(warm)
    if len(xs) < 200:
        print("  掩膜像素过少，改用更宽阈值")
        warm = mx > 85
        ys, xs = np.nonzero(warm)
    l_px = xs.max() - xs.min() + 1
    h_px = ys.max() - ys.min() + 1
    diag = math.hypot(l_px, h_px)
    print(f"  包围盒：宽 {l_px} px　高 {h_px} px　对角线 {diag:.1f} px")
    print(f"  ★ 车在图中**斜置** ⇒ 用对角线作为「车长」的上界，")
    print(f"    用宽度作为下界 ⇒ 车长落在 [{l_px}, {diag:.0f}] px")

    # ---------------- 2) 尺度 ----------------
    print("\n【2】尺度标定（轿车实车长 4.6–4.9 m）")
    print(f"  {'假设车长(m)':>12}{'车长(px)':>10}{'px/m':>9}{'整排跨度→m':>14}")
    # 整排跨度：五辆车沿排列方向的总长（图中可见 x≈140..330, y≈330..430）
    # 用"排列方向上的投影"估计
    S_px = 205.0        # 手工读数：五辆车排列方向跨度约 205 px
    res = []
    for Lreal in (4.6, 4.75, 4.9):
        kappa = l_px / Lreal
        S_m = S_px / kappa
        res.append((Lreal, kappa, S_m))
        print(f"  {Lreal:>12.2f}{l_px:>10}{kappa:>9.2f}{S_m:>14.1f}")

    # ---------------- 3) 跳跃跨度 L ----------------
    print("\n【3】跳跃水平跨度 L 的估计")
    print("  L ≈ 五车整排跨度 + 起跳/落地各留约半个车长（保守取 0.5 车长 ×2）")
    Ls = []
    for Lreal, kappa, S_m in res:
        L_est = S_m + 1.0 * Lreal
        Ls.append(L_est)
        print(f"    车长 {Lreal:.2f} m ⇒ 整排 {S_m:.1f} m + 余量 {Lreal:.1f} m"
              f" ⇒ **L ≈ {L_est:.1f} m**")

    # ---------------- 4) 与模型需要的对比 ----------------
    print("\n" + "=" * 92)
    print("【4】这组 (L, h) 对问题 2 意味着什么")
    print("=" * 92)
    L_mid = float(np.mean(Ls))
    print(f"  取 L ≈ **{L_mid:.1f} m**")
    print()
    print("  抛体：v0² · sin(2α) / g = L（等高点落地）")
    print(f"  {'起飞角 α(°)':>12}{'所需 v0 (m/s)':>15}{'(km/h)':>11}"
          f"{'最大高度(m)':>13}")
    g = 9.81
    for alpha in (15, 20, 25, 30, 35, 40, 45):
        ar = math.radians(alpha)
        # L = v0^2 sin(2a)/g  => v0 = sqrt(L g / sin(2a))
        s2 = math.sin(2 * ar)
        if s2 <= 0:
            continue
        v0 = math.sqrt(L_mid * g / s2)
        hmax = (v0 * math.sin(ar)) ** 2 / (2 * g)
        print(f"  {alpha:>12}{v0:>15.2f}{v0*3.6:>11.1f}{hmax:>13.2f}")

    print()
    print("  ★ 判读：")
    print("    · 起飞角 25–35° 时，所需 v0 约 15–19 m/s（55–68 km/h）；")
    print("    · 轨迹最高点约 3–6 m —— 而卡车高约 4 m ⇒ **要清卡车顶，")
    print("      最高点必须 ≥ 4 m 出头** ⇒ 限制了最小起飞角与最小 v0。")
    print()
    print("  卡车高度约束（关键）：")
    for Ht in (3.8, 4.1):
        for alpha in (20, 25, 30, 35):
            ar = math.radians(alpha)
            s2 = math.sin(2 * ar)
            v0 = math.sqrt(L_mid * g / s2)
            hmax = (v0 * math.sin(ar)) ** 2 / (2 * g)
            ok = "✓" if hmax >= Ht else "✗"
            print(f"    H_truck={Ht} m，α={alpha}° ⇒ 最高点 {hmax:.2f} m {ok}")
    print()
    print("  ⇒ **同时满足「跨越 L」与「清过卡车顶」的可行起飞角很窄**，")
    print("     这正是问题 2 要有「可行域」而不是「唯一解」的原因。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
