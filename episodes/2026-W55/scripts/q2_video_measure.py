#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **从飞跃视频逐帧反推**：跳跃几��、离地多高、速度多少。

## 为什么这个视频比截图强

| 项 | 截图 | **本视频** |
|---|---|---|
| 时间分辨率 | 单帧 | **60 fps / 41.25 s** |
| 能否量速度 | 不能 | ★ **能**（逐帧位移 ÷ 帧间隔）|
| 能否量轨迹 | 不能 | ★ **能**（逐帧质心）|
| 尺度基准 | 只��车长 | ★ **车身宽 + 卡车宽 + 五车排** |

## 方法

1. **锁定候选帧**：人工看 `data/jump2/` 里的帧，找出"车与卡车同框"的时刻；
2. **车身掩膜**：车是全场最亮的物体（被灯照亮），用高阈值；
3. **逐帧质心**：在时间窗内逐帧求质心 → 得到 $(x(t), y(t))$；
4. **尺度标定**：用**卡车驾驶室宽度**（半挂牵引车约 2.4–2.6 m）
   或**Roadster 车宽**（约 2.0 m）标定 px/m；
5. **反推**：水平速度 $v_x$、竖直速度 $v_z$、跳跃跨度 $L$、最大离地高度 $h$。

## ★ 诚实性的三层

1. **相机在动**：视频里有多机位切换，**不能跨镜头叠加位移**；
   ⇒ 只在**单一连续镜头内**做逐帧分析；
2. **透视**：车在画面里的尺寸随距离变化 ⇒ 尺度不是常数；
3. **"离地高度"无从直接测量**（没有地面参考线在同一帧内）；
   ⇒ 只能量**相对卡车的高度**。

**⇒ 本文的核心可测量量是：①水平速度 ②相对卡车顶的净空 ③跨过整排的时间。**
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W55"
J2 = EP / "data" / "jump2"


def bright_blob(path: Path, thr: int = 150,
                box: tuple[int, int, int, int] | None = None
                ) -> tuple[float, float, int, int, int]:
    r"""返回最亮连通块的 (cx, cy, n_px, w_px, h_px)。

    `box` = (x0, x1, y0, y1) 限定搜索区。
    """
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)
    mx = a.max(axis=2)
    m = mx > thr
    if box is not None:
        x0, x1, y0, y1 = box
        m2 = np.zeros_like(m)
        m2[y0:y1, x0:x1] = m[y0:y1, x0:x1]
        m = m2
    ys, xs = np.nonzero(m)
    if len(xs) < 30:
        return (math.nan,) * 5
    return (float(xs.mean()), float(ys.mean()), len(xs),
            int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))


def main() -> int:
    print("=" * 92)
    print("  W55 · 飞跃视频逐帧分析")
    print("=" * 92)

    # 先用一帧确认尺度基准
    p = J2 / "k_20_4.png"
    if not p.exists():
        print(f"  [X] 缺 {p}")
        return 1
    a = np.asarray(Image.open(p).convert("RGB")).astype(int)
    print(f"\n  参考帧 {p.name}  尺寸 {a.shape[1]}×{a.shape[0]}")

    # ---- 1) 车（上半部）----
    print("\n【1】车（画面中上部，最亮物体）")
    cx, cy, n, w, h = bright_blob(p, thr=150, box=(500, 1000, 100, 400))
    print(f"  质心 ({cx:.1f}, {cy:.1f})  像素 {n}  包围盒 {w}×{h} px")

    # ---- 2) 卡车驾驶室（下半部）----
    print("\n【2】卡车驾驶室（画面底部）")
    cx2, cy2, n2, w2, h2 = bright_blob(p, thr=90, box=(280, 560, 560, 740))
    print(f"  质心 ({cx2:.1f}, {cy2:.1f})  像素 {n2}  包围盒 {w2}×{h2} px")

    # ---- 3) 尺度 ----
    print("\n【3】尺度标定")
    print(f"  卡车驾驶室宽度 {w2} px")
    print(f"  {'假设卡车宽(m)':>14}{'px/m':>9}"
          f"{'车宽推算(m)':>14}")
    for wt in (2.4, 2.5, 2.6):
        ppm = w2 / wt
        print(f"  {wt:>14.1f}{ppm:>9.2f}{w/ppm:>14.2f}")
    print("  ★ 若「车宽推算」落在 1.9–2.1 m ⇒ 尺度标定合理（双向校验）")

    # ---- 4) 净空（车底到卡车顶）----
    print("\n【4】相对卡车顶的净空")
    # 车包围盒的下沿、卡车包围盒的上沿
    car_bottom = cy + h / 2
    truck_top = cy2 - h2 / 2
    gap_px = truck_top - car_bottom
    print(f"  车底部 y ≈ {car_bottom:.1f}")
    print(f"  卡车顶 y ≈ {truck_top:.1f}")
    print(f"  间隙 {gap_px:.1f} px")
    for wt in (2.4, 2.5, 2.6):
        ppm = w2 / wt
        print(f"    卡车宽 {wt} m ⇒ 净空 ≈ **{gap_px/ppm:.2f} m**")

    print("\n" + "=" * 92)
    print("  ★ 下一步（需要多帧才能做）")
    print("=" * 92)
    print("  · **水平速度**：同一镜头内车质心的 x 位移 ÷ 帧间隔；")
    print("  · **跳跃跨度**：从「车离开卡车前」到「车越过整排」的 x 跨度；")
    print("  · **离地高度**：需要地面参考 —— 目前只能给「相对卡车顶的净空」。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
