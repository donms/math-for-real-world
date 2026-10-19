#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **定量数羽流**：用列亮度剖面找"竖直条带"。

## 上一版为什么失败

我用"淡蓝色掩膜 + 峰检测"，得到 36 个子峰 —— **因为把整片烟云都算进去了**。
**烟云是弥散的大面积，羽流是细长的竖直条带** ⇒ 判据必须区分这两者。

## 本版的三条改进

1. **只在"车底到地面"这一段取剖面**（避开烟云主体）；
2. **不用颜色掩膜，而用"竖直连贯性"**：
   对每一列，统计"从车底往下连续有多少行是亮的" ——
   **羽流在这一列上连贯很长；烟云则参差不齐**；
3. **用连通域的"细长比"过滤**：羽流的 $h/w \gg 1$。

**⇒ 输出：几个竖直条带、各自中心 x、高度、平均宽度。**
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W55"


def plume_columns(a: np.ndarray, y_top: int, y_bot: int,
                  thr: int = 62, min_run: int = 60) -> np.ndarray:
    r"""对每一列，求"最长连续亮行数"（在 $[y_{top}, y_{bot})$ 内）。

    **★ 羽流判据的核心**：
    羽流在某列上是**从上到下连续的**；烟云则**断裂**。
    ⇒ 用"最长连续段长度"而不是"总亮像素数"。
    """
    band = a[y_top:y_bot]
    # 亮度：取 max(RGB)（羽流是亮蓝白）
    lum = band.max(axis=2)
    lit = lum > thr
    H, W = lit.shape
    runs = np.zeros(W, dtype=int)
    for x in range(W):
        col = lit[:, x]
        best = cur = 0
        for v in col:
            cur = cur + 1 if v else 0
            best = max(best, cur)
        runs[x] = best
    return runs


def segments(runs: np.ndarray, min_run: int = 60,
             min_w: int = 6) -> list[tuple[int, int, int]]:
    r"""把"连续满足 $runs \ge min\_run$ 的列"聚成段。"""
    ok = runs >= min_run
    segs = []
    x = 0
    W = len(ok)
    while x < W:
        if ok[x]:
            j = x
            while j + 1 < W and ok[j + 1]:
                j += 1
            if j - x + 1 >= min_w:
                segs.append((x, j, int(runs[x:j + 1].max())))
            x = j + 1
        else:
            x += 1
    return segs


def main() -> int:
    print("=" * 88)
    print("  W55 · 定量数羽流（竖直连贯性判据）")
    print("=" * 88)

    frames = ["j_19_0.png", "m_22_75.png", "m_23_00.png", "m_23_25.png"]
    for fn in frames:
        p = EP / "data" / "jump2" / fn
        if not p.exists():
            print(f"  [skip] {fn}")
            continue
        a = np.asarray(Image.open(p).convert("RGB")).astype(int)
        H, W, _ = a.shape

        # 自动定 y_top：先找"车底"（最亮大块的底边）
        lum = a.max(axis=2)
        bright = lum > 150
        ys, xs = np.nonzero(bright)
        if len(ys) < 50:
            print(f"\n--- {fn} ---  无亮块，跳过")
            continue
        y_top = int(np.percentile(ys, 92))
        y_bot = H
        print(f"\n--- {fn}（{W}×{H}）---")
        print(f"  剖面取 y ∈ [{y_top}, {y_bot}]（车底以下）")

        runs = plume_columns(a, y_top, y_bot, thr=62)
        print(f"  最长的 8 列连续长度："
              f"{sorted(runs, reverse=True)[:8]}")

        for mr in (50, 70, 90, 110):
            segs = segments(runs, min_run=mr)
            widths = [s[1] - s[0] + 1 for s in segs]
            print(f"  阈值 {mr:>3}：段数 **{len(segs)}**，"
                  f"段宽 {widths}")
            if mr == 70 and segs:
                for i, (x0, x1, mx) in enumerate(segs, 1):
                    print(f"      #{i} x=[{x0},{x1}] 宽{x1-x0+1} "
                          f"最长{mx}px 中心x={(x0+x1)//2}")

    print("\n" + "=" * 88)
    print("  ★ 判读")
    print("=" * 88)
    print("  · 一个稳定出现的「竖直条带」= 一条羽流 = 一个喷口；")
    print("  · 需要**多帧一致**才算数（单帧可能是烟云缝隙）；")
    print("  · 若同一帧出现 4 条 ⇒ 用户说的「竖推 4 个」成立。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
