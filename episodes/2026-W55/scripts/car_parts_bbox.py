#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · 把 `only_car.png` 按**颜色分层**拆开，看是哪一部分把包围盒中心拉偏。

## 为什么要问这个

像素法量出：车包围盒中心 **(88..1008) ⇒ 548 px**，而车原点投影在 **401 px**，
**差 147 px ≈ 0.6 m**。横漂只有 138 px ⇒ 两者几乎抵消，画面"看不出偏"。

**关键问题：这 0.6 m 是模型真的左右不对称（尾翼/立柱伸出一侧），还是我把某个
不应该算进车身的东西算进去了？**

## 做法

按颜色分组（每 8 级量化一次），每组算包围盒与中心，按面积排序。
同时报每个组的 **左右臂长**（中心到 bbox 左右边的距离）——
**臂长不等的那一组，就是把中心拉偏的元凶。**
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

EP = Path(r".\episodes\2026-W55")
SRC = EP.parents[1] / ".workbuddy" / "tmp" / "w55_s01" / "only_car.png"


def main() -> int:
    im = Image.open(SRC).convert("RGBA")
    a = np.asarray(im)
    rgb, alpha = a[..., :3].astype(np.int16), a[..., 3]
    mask = alpha > 8
    ys, xs = np.nonzero(mask)
    print("=" * 96)
    print("  车身各部件包围盒（按颜色分组，%s）" % SRC.name)
    print("=" * 96)
    print("  整幅：%dx%d   车身像素 %d" % (im.width, im.height, mask.sum()))
    bb = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    print("  总包围盒：x %d..%d  y %d..%d   宽 %d   中心 x=%.1f  y=%.1f"
          % (bb[0], bb[2], bb[1], bb[3], bb[2] - bb[0],
             (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2))

    q = (rgb[mask] // 8)
    key = q[:, 0].astype(np.int32) * 1024 + q[:, 1].astype(np.int32) * 32 + q[:, 2]
    px, py = xs, ys
    uk, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
    order = np.argsort(-cnt)

    print("\n  %-4s %-14s %7s  %-26s %8s %8s %8s %8s"
          % ("#", "代表色", "像素", "包围盒 x..y", "中心x", "左臂", "右臂", "臂差"))
    print("  " + "-" * 92)
    rows = []
    for rank, j in enumerate(order[:12], 1):
        sel = inv == j
        if cnt[j] < 200:
            continue
        cxs, cys = px[sel], py[sel]
        x0, x1 = int(cxs.min()), int(cxs.max()) + 1
        y0, y1 = int(cys.min()), int(cys.max()) + 1
        cx = (x0 + x1) / 2
        # 代表色：该组内真实颜色的中位数
        sub = rgb[mask][sel]
        col = tuple(int(v) for v in np.median(sub, axis=0))
        rows.append((rank, col, int(cnt[j]), (x0, x1, y0, y1), cx))
        print("  %-4d rgb%-11s %7d  x %4d..%4d y %4d..%4d  %8.1f %8.1f %8.1f %+8.1f"
              % (rank, str(col), cnt[j], x0, x1, y0, y1, cx,
                 cx - x0, x1 - cx, (x1 - cx) - (cx - x0)))
    print("\n  注：臂差 = 右臂 − 左臂（>0 表示该部件往右伸得更远，把中心往右拉）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
