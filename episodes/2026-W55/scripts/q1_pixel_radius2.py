#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **像素法 v2**：先用连通域锁定坡道主体，再拟合圆弧。

## v1 为什么失败

直接对"亮且低饱和"的掩膜按行取中点，**把背景里的灰色物体
（看台、护栏、地面反光）也算进去了** ⇒ 拟合残差中位 13–44 px，半径不可信。

## v2 的做法

1. **连通域标记**（`scipy.ndimage.label`），取**面积最大的连通域**
   —— 坡道是画面里最大的灰色亮块；
2. 只在该连通域内**按行取左右边界的中点**；
3. 逐行中点做**最小二乘圆拟合**；
4. **残差中位数 > 8 px 就判为"拟合不可信"**，不给半径；
5. 输出**掩膜叠图**供人眼确认（`data/frames/_mask_*.png`）。

## ★ 为什么必须"看得见"

像素法的失败方式是**静默的**：残差大也会给出一个半径数字。
**⇒ 必须把掩膜画出来看**，否则会把噪声当结论。
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W55"
FR = EP / "data" / "frames"


def largest_component(mask: np.ndarray) -> np.ndarray:
    r"""返回掩膜里**面积最大的连通域**（4 邻域）。"""
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


def fit_circle(xs: np.ndarray, ys: np.ndarray) -> tuple[float, float, float]:
    A = np.c_[xs, ys, np.ones(len(xs))]
    b = -(xs ** 2 + ys ** 2)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    D, E, F = sol
    xc, yc = -D / 2, -E / 2
    R = math.sqrt(max(xc ** 2 + yc ** 2 - F, 0.0))
    return xc, yc, R


def main() -> int:
    print("=" * 92)
    print("  W55 · 像素法 v2（连通域锁定坡道）")
    print("=" * 92)

    for fn in ("f_3.png", "f_9.png", "g_5.png"):
        p = FR / fn
        if not p.exists():
            print(f"[skip] {fn}")
            continue
        rgb = Image.open(p).convert("RGB")
        a = np.asarray(rgb).astype(int)
        H, W, _ = a.shape
        r_, g_, b_ = a[:, :, 0], a[:, :, 1], a[:, :, 2]
        mx, mn = a.max(axis=2), a.min(axis=2)
        # 坡道：亮灰、低饱和、非红边
        mask = (mx > 50) & ((mx - mn) < 60) \
            & ~((r_ > 100) & (r_ - g_ > 40) & (r_ - b_ > 40))
        big = largest_component(mask)
        ys_, xs_ = np.nonzero(big)
        print(f"\n--- {fn} ---")
        print(f"  原掩膜 {int(mask.sum())} px ⇒ 最大连通域 {int(big.sum())} px")
        if big.sum() < 3000:
            print("  连通域太小，跳过")
            continue
        print(f"  连通域包围盒 x[{xs_.min()},{xs_.max()}] "
              f"y[{ys_.min()},{ys_.max()}]")

        # 逐行取中点（只取该连通域）
        pts = []
        for y in range(ys_.min(), ys_.max() + 1):
            xs2 = np.nonzero(big[y])[0]
            if len(xs2) < 10:
                continue
            pts.append((y, (xs2.min() + xs2.max()) / 2.0))
        ys = np.array([q[0] for q in pts], float)
        xs = np.array([q[1] for q in pts], float)
        xc, yc, Rpx = fit_circle(xs, ys)
        res = np.abs(np.hypot(xs - xc, ys - yc) - Rpx)
        med = float(np.median(res))
        ok = med <= 8.0
        print(f"  拟合：圆心 ({xc:.1f}, {yc:.1f})  R = **{Rpx:.1f} px**")
        print(f"  残差 中位 {med:.2f} px，最大 {res.max():.2f} px "
              f"⇒ {'可信' if ok else '★ 不可信（>8 px）'}")

        # 叠图（绿色 = 连通域，黄色 = 拟合圆，红十字 = 圆心）
        out = np.zeros((H, W, 3), dtype=np.uint8)
        out[..., 0] = 20
        out[big] = (0, 200, 0)
        th = np.linspace(0, 2 * math.pi, 2000)
        cx = (xc + Rpx * np.cos(th)).astype(int)
        cy = (yc + Rpx * np.sin(th)).astype(int)
        for x, y in zip(cx, cy):
            for dy in (-1, 0, 1):
                yy = y + dy
                if 0 <= yy < H and 0 <= x < W:
                    out[yy, x] = (255, 220, 0)
        for dx in range(-8, 9):
            for dy in range(-1, 2):
                xx, yy = int(xc) + dx, int(yc) + dy
                if 0 <= yy < H and 0 <= xx < W:
                    out[yy, xx] = (255, 0, 0)
        Image.fromarray(out).save(FR / f"_mask_{fn}")
        print(f"  叠图 ⇒ data/frames/_mask_{fn}")

    print("\n" + "=" * 92)
    print("  判读")
    print("=" * 92)
    print("  · 只有【残差中位 ≤ 8 px】的帧才可用来量 R；")
    print("  · 且 R 是**像素**半径，要换成米还需要该帧的（像素/米）标定，")
    print("    而标定只能用 HUD 高度 ⇒ **像素法无法完全独立于 HUD**；")
    print("  · ⇒ 像素法的定位是【形状检验】：圆弧假设是否成立。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
