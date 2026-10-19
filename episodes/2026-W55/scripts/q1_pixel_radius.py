#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **像素法**从视频里测量坡道半径 R（与 HUD 的高度反推互相独立）。

## 两条独立测量为什么必要

| 路径 | 用到的量 | 依赖的假设 |
|---|---|---|
| **A：HUD 高度** | ALTITUDE 峰值 67.5 ft = 20.6 m | 坡道是**四分之一圆**（否则 $h \ne R$）|
| **B：像素拟合** | 坡道边缘在画面里的位置 | 相机近似**正侧视**、透视畸变小 |

**两条路径都要做**：A 依赖"角度正好 90°"，B 依赖"视角"，**误差来源不同**。
**只有两者接近，结论才可信。**

## 方法

1. 对指定帧提取**坡道路面**（亮灰色）与**红色边缘线**的掩膜；
2. 按行统计路面的**左右边界**，取中点作为**坡道中线的采样点**；
3. 用**最小二乘圆拟合**求半径（像素单位）；
4. 用**车身长度**做尺度标定（像素/米）；
5. 输出 $R_{\text{pixels}} \to R_{\text{m}}$。

## ★ 诚实的边界

* **不是正侧视**：相机有透视，路面是**有宽度的曲面**
  ⇒ 中线在图像里不是精确的圆弧；
* **车身标定**：车身在画面里是**斜的**，长度投影会缩短
  ⇒ 标定把像素/米**系统性放大**，即**低估** $R$；
* **夜景 + 高对比度**：掩膜阈值敏感。

**⇒ 本文把像素法结果作为【量级校验】，主结论仍用 HUD。**
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W55"
FR = EP / "data" / "frames"


def fit_circle(xs: np.ndarray, ys: np.ndarray) -> tuple[float, float, float]:
    r"""最小二乘圆拟合（Kåsa 方法）：$x^2+y^2+Dx+Ey+F=0$。

    返回 $(x_c, y_c, R)$。
    """
    A = np.c_[xs, ys, np.ones(len(xs))]
    bvec = -(xs ** 2 + ys ** 2)
    sol, *_ = np.linalg.lstsq(A, bvec, rcond=None)
    D, E, F = sol
    xc, yc = -D / 2, -E / 2
    R = math.sqrt(xc ** 2 + yc ** 2 - F)
    return xc, yc, R


def road_mask(a: np.ndarray) -> np.ndarray:
    r"""坡道路面掩膜：**亮且低饱和**（灰色水泥），排除红色边缘与纯黑背景。"""
    r_, g_, b_ = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    mx = a.max(axis=2)
    mn = a.min(axis=2)
    bright = mx > 55
    low_sat = (mx - mn) < 55
    # 排除偏红的像素（边缘线）
    not_red = ~((r_ > 100) & (r_ - g_ > 40) & (r_ - b_ > 40))
    return bright & low_sat & not_red


def centers_per_row(mask: np.ndarray) -> list[tuple[int, float, float]]:
    r"""按行取掩膜的左右边界与中点，只保留"单段"行（避开托盘等干扰）。"""
    out: list[tuple[int, float, float]] = []
    H, W = mask.shape
    for y in range(H):
        xs = np.nonzero(mask[y])[0]
        if len(xs) < 12:
            continue
        # 找连续段
        segs = []
        start = xs[0]
        prev = xs[0]
        for x in xs[1:]:
            if x - prev > 6:
                segs.append((start, prev))
                start = x
            prev = x
        segs.append((start, prev))
        # 取最宽的一段（坡道主体）
        segs = [s for s in segs if s[1] - s[0] >= 14]
        if not segs:
            continue
        s = max(segs, key=lambda s: s[1] - s[0])
        out.append((y, float(s[0]), float(s[1])))
    return out


def main() -> int:
    print("=" * 92)
    print("  W55 · 像素法测量坡道半径")
    print("=" * 92)

    frames = ["f_3.png", "f_9.png", "g_2.png", "g_5.png"]
    for fn in frames:
        p = FR / fn
        if not p.exists():
            print(f"  [skip] 缺 {fn}")
            continue
        a = np.asarray(Image.open(p).convert("RGB")).astype(int)
        H, W, _ = a.shape
        m = road_mask(a)
        rows = centers_per_row(m)
        # 只取坡道主体区域：y 在画面中上段，且宽度适中
        pts = [(y, (x0 + x1) / 2) for y, x0, x1 in rows if 60 <= y <= H - 90]
        print(f"\n  --- {fn} （{W}x{H}）---")
        print(f"    掩膜像素 {int(m.sum())}；可用行 {len(rows)}；"
              f"用于拟合的点 {len(pts)}")
        if len(pts) < 20:
            print("    点太少，跳过")
            continue
        ys = np.array([p[0] for p in pts], dtype=float)
        xs = np.array([p[1] for p in pts], dtype=float)
        xc, yc, Rpx = fit_circle(xs, ys)
        # 残差
        res = np.abs(np.hypot(xs - xc, ys - yc) - Rpx)
        print(f"    拟合圆心 ({xc:.1f}, {yc:.1f})  半径 **{Rpx:.1f} px**")
        print(f"    残差 中位 {np.median(res):.2f} px / 最大 {res.max():.2f} px")
        print(f"    ⇒ 若圆心在画面内（x∈[0,{W}], y∈[0,{H}]）："
              f"{'是' if 0 <= xc <= W and 0 <= yc <= H else '否（正常，圆心在画外/画下）'}")

    # ---------------- 尺度标定：用 HUD 高度 ----------------
    print("\n" + "=" * 92)
    print("  ★ 像素→米的标定（用 HUD 已知高度，而不是猜车身长度）")
    print("=" * 92)
    print("  用 f_9（车在坡顶附近，ALTITUDE=67.5 ft）来标定：")
    print("  思路：坡顶在画面里的 y 坐标 与 地面的 y 坐标 之差 = 67.5 ft 的投影")
    print("  ⇒ 得到该视角下的 (像素/米)，再换算 R。")
    print()
    print("  ★ 但注意：不同帧的相机**机位/焦距不同**，不能跨帧套用同一标定。")
    print("  ⇒ 本文**不在像素法上强行给数值**，只把它当【形状检验】：")
    print("     若坡道中线能被一个圆弧很好地拟合（残差小），")
    print("     则「圆弧坡道」这个建模假设本身得到支持。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
