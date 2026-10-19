#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **数喷口**：从视频里的羽流（plume）确认竖推到底几个。

## 为什么必须回原始视频数

我此前按"物理必要性"**推**了一个 10 喷口布局，其中**竖推 2 个**。
用户看视频说**竖推是 4 个**。

**⇒ 用户看到的是"羽流条数"，那是最直接的证据。**
本脚本的任务：**从视频帧里自动/半自动定位羽流，计数并给出位置。**

## 方法

1. 冷气推进的羽流是**淡蓝色**（视频里很显眼）；
2. 用**色相与亮度**双重判据做掩膜：
   $B > R$、$B > 90$、$B-G$ 不太大（白蓝色而非深蓝）；
3. 对掩膜做**连通域**，统计"竖条"（高宽比 > 2）；
4. 输出每条羽流的**起止 x、长度、倾角**，用于判断"1 条粗的"还是"2 条细的"。

## ★ 为什么不能只数连通域

**两条紧邻的羽流在低分辨率下会连成一片** ⇒ 必须再看
**沿水平方向的亮度分布有几个峰**（每个峰 = 一条羽流）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W55"


def plume_mask(a: np.ndarray) -> np.ndarray:
    r"""羽流掩膜：**淡蓝/白蓝**。

    ## ★ 判据为什么要这么细

    * 纯蓝背景（夜空）$B$ 也高，但**亮度低** ⇒ 用 $B > 90$ 排掉；
    * 白烟（撞击扬尘）$R\approx G\approx B$ 且很亮 ⇒ 用 $B-R > 18$ 排掉；
    * 羽流是**冷气**，偏蓝白 ⇒ $B-R$ 中等（20–90）。
    """
    r_, g_, b_ = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    return (b_ > 90) & (b_ - r_ > 18) & (b_ - g_ > 4) & (b_ - r_ < 130)


def column_profile(mask: np.ndarray, y0: int, y1: int
                   ) -> np.ndarray:
    r"""在 $[y_0, y_1)$ 行内，按列统计羽流像素数。"""
    return mask[y0:y1].sum(axis=0)


def main() -> int:
    print("=" * 88)
    print("  W55 · 从羽流数喷口")
    print("=" * 88)

    # 选几帧羽流最明显的
    cands = sorted((EP / "data" / "jump2").glob("k_*.png"))
    cands += sorted((EP / "data" / "jump2").glob("m_2*.png"))
    cands += [EP / "data" / "frames" / "f_9.png"]
    cands = [p for p in cands if p.exists()]

    print(f"\n  候选帧 {len(cands)} 张，先看哪几张羽流最强")
    best = []
    for p in cands:
        a = np.asarray(Image.open(p).convert("RGB")).astype(int)
        m = plume_mask(a)
        n = int(m.sum())
        best.append((n, p))
    best.sort(reverse=True)
    for n, p in best[:8]:
        print(f"    {p.name:<16} 羽流像素 {n:>6}")

    # 取羽流最多的一帧做详细分析
    n_best, p_best = best[0]
    print(f"\n  ⇒ 分析 {p_best.name}（羽流 {n_best} px）")
    a = np.asarray(Image.open(p_best).convert("RGB")).astype(int)
    H, W, _ = a.shape
    m = plume_mask(a)
    print(f"    图像 {W}×{H}")

    # ---- 逐行看羽流的水平分布 ----
    ys = np.nonzero(m)[0]
    if len(ys) == 0:
        print("  [X] 无羽流像素")
        return 1
    y_lo, y_hi = int(ys.min()), int(ys.max())
    print(f"    羽流纵向范围 y = [{y_lo}, {y_hi}]")

    prof = column_profile(m, y_lo, y_hi + 1)
    # 找峰：连续非零段
    nz = prof > 0
    segs = []
    i = 0
    while i < len(nz):
        if nz[i]:
            j = i
            while j + 1 < len(nz) and (nz[j + 1] or
                                       (j + 3 < len(nz) and nz[j + 3])):
                j += 1
            segs.append((i, j, int(prof[i:j + 1].sum())))
            i = j + 1
        else:
            i += 1
    segs = [s for s in segs if s[2] > 40]
    print(f"\n    按列分段的羽流（每段可能=1 条或几条紧邻羽流）：")
    print(f"    {'x 范围':>14}{'像素':>8}{'宽度':>7}")
    for x0, x1, tot in segs:
        print(f"    {x0:>6}–{x1:<7}{tot:>8}{x1-x0+1:>7}")
    print(f"    ⇒ 共 **{len(segs)} 段**")

    # ---- 对最宽的一段再做细分峰检测 ----
    segs_sorted = sorted(segs, key=lambda s: -s[2])
    if segs_sorted:
        x0, x1, _ = segs_sorted[0]
        sub = prof[x0:x1 + 1].astype(float)
        # 简单平滑 + 局部极大
        k = 5
        sm = np.convolve(sub, np.ones(k) / k, mode="same")
        peaks = [i for i in range(2, len(sm) - 2)
                 if sm[i] >= sm[i - 1] and sm[i] >= sm[i + 1]
                 and sm[i] > sm.max() * 0.25]
        # 合并相邻峰
        merged: list[int] = []
        for pk in peaks:
            if merged and pk - merged[-1] <= 6:
                continue
            merged.append(pk)
        print(f"\n    ★ 最宽那段 x=[{x0},{x1}] 的**子峰**（可能对应多条紧邻羽流）：")
        print(f"      {[x0 + i for i in merged]}  ⇒ **{len(merged)} 个子峰**")
        print(f"      各峰强度："
              f"{[round(float(sm[i]), 0) for i in merged]}")

    print("\n" + "=" * 88)
    print("  ★ 判读原则")
    print("=" * 88)
    print("  · **一条羽流 = 一个喷口**（冷气推进没有「合并喷流」的机制）；")
    print("  · 但两条紧邻的羽流在低清画面下会**粘连** ⇒ 必须看子峰；")
    print("  · 羽流**数量**比「位置」可靠（位置受透视影响）。")
    print()
    print("  ★ 用户说「竖推是四个」—— 需要确认这 4 条羽流")
    print("    是**同时在喷**（4 个独立喷口）还是**2 个喷口各喷两次**。")
    print("    ⇒ 看**同一帧内**的羽流条数即可区分。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
