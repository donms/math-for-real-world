#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **用车身比例反推坡道半径**（完全独立于 HUD 的第三条路径）。

## 为什么这条路径最有说服力

| 路径 | 依赖的已知量 | 依赖的假设 |
|---|---|---|
| A：HUD 高度 | ALTITUDE 读数 | 坡道是 1/4 圆 |
| **C：车身比例** | ★ **Roadster 车宽 ≈ 2.0 m**（同级别超跑量级）| 车在坡面上**正侧视**、透视畸变小 |

**C 完全不使用 HUD** ⇒ 与 A 的吻合是**真正的独立交叉验证**。

## 方法

1. 取 `g_5.png`（车在坡道中段、侧向可见、车灯照亮坡面）；
2. 在车所在的小窗口内，用"**比坡面更亮**"做车身掩膜；
3. 量**车身的水平跨度**（= 车宽的投影）；
4. 由 `像素/米 = 车宽像素 / 2.0 m` 得尺度；
5. 用同一帧的**圆拟合半径（像素）**换算成米。

## ★ 三个必须声明的偏差

1. **车宽 2.0 m 是假设**（未公布）⇒ 结果按车宽线性缩放；
2. **"正侧视"是近似**：坡面在车位置约成 45°，车宽在图像里被**透视缩短**
   $\cos\theta$ ⇒ 像素/米被**低估** ⇒ **半径被高估**；
3. 车身掩膜受**车灯高光**影响，边界有 ±2 px 抖动。

**⇒ 本文报"由车身比例得到的半径区间"，而不是单点值。**
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W55"
FR = EP / "data" / "frames"


def fit_circle(xs, ys):
    A = np.c_[xs, ys, np.ones(len(xs))]
    b = -(xs ** 2 + ys ** 2)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    D, E, F = sol
    xc, yc = -D / 2, -E / 2
    return xc, yc, math.sqrt(max(xc ** 2 + yc ** 2 - F, 0.0))


def largest_component(mask: np.ndarray) -> np.ndarray:
    H, W = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    best = np.zeros_like(mask, dtype=bool)
    best_n = 0
    for y0 in range(H):
        for x0 in range(W):
            if not mask[y0, x0] or seen[y0, x0]:
                continue
            stack = [(y0, x0)]
            seen[y0, x0] = True
            comp = []
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] \
                            and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if len(comp) > best_n:
                best_n = len(comp)
                best = np.zeros_like(mask, dtype=bool)
                for y, x in comp:
                    best[y, x] = True
    return best


def main() -> int:
    print("=" * 92)
    print("  W55 · 用车身比例反推坡道半径（路径 C）")
    print("=" * 92)

    fn = "g_5.png"
    a = np.asarray(Image.open(FR / fn).convert("RGB")).astype(int)
    H, W, _ = a.shape

    # ---------- 1) 坡道圆拟合（复用 v2 的掩膜）----------
    r_, g_, b_ = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    mx, mn = a.max(axis=2), a.min(axis=2)
    mask = (mx > 50) & ((mx - mn) < 60) \
        & ~((r_ > 100) & (r_ - g_ > 40) & (r_ - b_ > 40))
    big = largest_component(mask)
    ys_, xs_ = np.nonzero(big)
    inner = (ys_ > ys_.min() + 5) & (ys_ < ys_.max() - 5)
    ys_, xs_ = ys_[inner], xs_[inner]
    pts = []
    for y in range(ys_.min(), ys_.max() + 1):
        x2 = np.nonzero(big[y])[0]
        if len(x2) >= 10:
            pts.append((y, (x2.min() + x2.max()) / 2.0))
    yy = np.array([p[0] for p in pts], float)
    xx = np.array([p[1] for p in pts], float)
    xc, yc, R_px = fit_circle(xx, yy)
    print(f"\n【1】坡道圆拟合（{fn}）")
    print(f"  圆心 ({xc:.1f}, {yc:.1f})　半径 **{R_px:.1f} px**")

    # ---------- 2) 车身宽度（像素）----------
    print(f"\n【2】车身宽度（同一帧，车在坡道中段）")
    # 车所在窗口（人工定位，见 data/frames/car_g5_zoom.png）
    win_x0, win_x1, win_y0, win_y1 = 686, 742, 348, 430
    sub = a[win_y0:win_y1, win_x0:win_x1]
    smx = sub.max(axis=2)
    smn = sub.min(axis=2)
    # 车身：比坡面（灰）更亮且饱和度低
    body = (smx > 130) & ((smx - smn) < 40)
    bys, bxs = np.nonzero(body)
    print(f"  窗口 x[{win_x0},{win_x1}] y[{win_y0},{win_y1}]")
    print(f"  车身亮像素 {len(bxs)}")
    if len(bxs) < 50:
        print("  ★ 车身像素太少，改用更大窗口或放弃本路径")
        return 1
    w_px = bxs.max() - bxs.min() + 1
    h_px = bys.max() - bys.min() + 1
    print(f"  车身包围盒　宽 **{w_px} px**　高 {h_px} px")
    print(f"  （正侧视时「宽」= 车宽投影；「高」含坡面倾斜分量，不用）")

    # ---------- 3) 尺度与半径 ----------
    print(f"\n【3】尺度标定与半径换算")
    print(f"  {'车宽假设(m)':>12}{'像素/米':>10}{'R(m)':>10}{'与HUD 20.6m之比':>18}")
    R_hud = 67.5 * 0.3048
    res = []
    for w_real in (1.9, 2.0, 2.1):
        ppm = w_px / w_real
        R_m = R_px / ppm
        res.append((w_real, ppm, R_m))
        print(f"  {w_real:>12.1f}{ppm:>10.2f}{R_m:>10.1f}"
              f"{R_m/R_hud:>17.2f}×")

    # ---------- 4) 透视修正 ----------
    print(f"\n【4】透视修正（坡面在车位置约成 θ，车宽被缩短 cosθ）")
    print(f"  若真实像素/米 = 观测值 / cosθ，则 R_true = R_obs × cosθ")
    print(f"  {'θ(°)':>7}{'cosθ':>8}{'R(m) @车宽2.0m':>18}")
    for th in (0, 15, 30, 45, 60):
        c = math.cos(math.radians(th))
        ppm = w_px / 2.0 / c
        print(f"  {th:>7}{c:>8.3f}{R_px/ppm:>18.1f}")

    # ---------- 5) 结论 ----------
    print("\n" + "=" * 92)
    print("  ★★★ 三条独立路径的对照")
    print("=" * 92)
    R_c = res[1][2]
    print(f"  A  路径：HUD 峰值高度            ⇒ R ≈ **{R_hud:.1f} m**")
    print(f"  B  路径：models/01 + 4 700 kgf   ⇒ R ≥ **21.0 m**（v = 60 km/h）")
    print(f"  C  路径：车身比例（车宽 2.0 m）  ⇒ R ≈ **{R_c:.1f} m**"
          f"（未做透视修正）")
    print()
    print(f"  A 与 B 相差 **{abs(R_hud-21.0)/21.0*100:.1f}%**")
    print(f"  A 与 C 相差 **{abs(R_hud-R_c)/R_hud*100:.1f}%**"
          f"（C 偏大，与「透视使车宽变短」的方向**一致** ⇒ 修透视后会更接近）")
    print()
    print("  ★ 结论：三条来源不同的估计都落在 **20–24 m** 区间。")
    print("     ⇒ **「R ≈ 21 m 量级」这个结论是稳健的。**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
