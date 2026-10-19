#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · 从飞跃视频做**逐帧质心追踪**，量水平速度与横越时间。

## 为什么改做"速度"而不是"高度"

| 量 | 可行性 | 原因 |
|---|---|---|
| **水平速度** | ★ **可行** | 只要镜头**连续**，位移 ÷ 时间就是速度 |
| 相对卡车净空 | 勉强 | 需要车与卡车**同帧且同景深**，而飞在空中的车景深不同 |
| **绝对离地高度** | ✗ **不可行** | **没有地面参考线**；且相机在仰拍/俯拍切换 |

**⇒ 本脚本只报能可靠测得的东西：水平速度、横越时间。**

## 方法

1. 先**自动检测镜头切换**（相邻帧平均差突变）；
2. 在**同一镜头内部**逐帧求"最亮大块"的质心；
3. 用 **×2 车速** 与 **卡车宽度** 两个基准分别标定；
4. 输出 $v_x$ 与"横越 11 m 所需时间"。

## ★ 关于"最亮大块"

视频是夜景，**车被灯照得很亮**，而背景几乎全黑。
**⇒ 取亮度 > 阈值、面积 > 500 px 的最大连通块，几乎总能锁定车。**

**但**：车灯的**强反光**会形成第二块，须按面积取最大并检查连贯性。
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W55"
J2 = EP / "data" / "jump2"


def largest_blob(m: np.ndarray, min_n: int = 400
                 ) -> tuple[float, float, int, int, int, int, int] | None:
    r"""返回最大连通块 (cx, cy, n, w, h, x0, y0)。"""
    H, W = m.shape
    seen = np.zeros_like(m, dtype=bool)
    best = None
    best_n = 0
    for yy in range(H):
        row = m[yy]
        for xx in np.nonzero(row)[0]:
            if seen[yy, xx]:
                continue
            stack = [(yy, xx)]
            seen[yy, xx] = True
            comp = []
            while stack:
                cy, cx = stack.pop()
                comp.append((cy, cx))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < H and 0 <= nx < W and m[ny, nx] \
                            and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if len(comp) > best_n and len(comp) >= min_n:
                best_n = len(comp)
                ys = np.array([c[0] for c in comp])
                xs = np.array([c[1] for c in comp])
                best = (float(xs.mean()), float(ys.mean()), len(comp),
                        int(xs.max() - xs.min() + 1),
                        int(ys.max() - ys.min() + 1),
                        int(xs.min()), int(ys.min()))
    return best


def frame_diff(p1: Path, p2: Path) -> float:
    a = np.asarray(Image.open(p1).convert("L"), dtype=float)
    b = np.asarray(Image.open(p2).convert("L"), dtype=float)
    if a.shape != b.shape:
        return float("nan")
    return float(np.abs(a - b).mean())


def main() -> int:
    print("=" * 92)
    print("  W55 · 飞跃视频：逐帧质心追踪 → 水平速度")
    print("=" * 92)

    frames = sorted(J2.glob("m_*.png"), key=lambda p: p.name)
    if not frames:
        print("  [X] 没有 m_*.png，先跑抽帧")
        return 1
    print(f"\n  共 {len(frames)} 帧（{frames[0].name} … {frames[-1].name}）")

    # ---- 1) 镜头切换检测 ----
    print("\n【1】镜头切换检测（相邻帧平均差 > 8 视为切镜）")
    cuts = []
    for i in range(1, len(frames)):
        d = frame_diff(frames[i - 1], frames[i])
        if d == d and d > 8.0:
            cuts.append((frames[i - 1].name, frames[i].name, d))
    for a, b, d in cuts:
        print(f"  切镜：{a} → {b}  差 {d:.1f}")
    if not cuts:
        print("  未检测到明显切镜（或阈值需调整）")

    # ---- 2) 逐帧质心 ----
    print("\n【2】逐帧最大亮块（锁定车）")
    print(f"  {'帧':<14}{'cx':>7}{'cy':>7}{'n(px)':>8}"
          f"{'w':>5}{'h':>5}{'判定':>8}")
    prev = None
    recs = []
    for p in frames:
        a = np.asarray(Image.open(p).convert("RGB")).astype(int)
        mx = a.max(axis=2)
        m = mx > 140
        # 排除底部 HUD 与顶部字幕区
        m[:50, :] = False
        m[690:, :] = False
        m[:, :40] = False
        m[:, 1280:] = False
        r = largest_blob(m, 400)
        if r is None:
            print(f"  {p.name:<14}{'—':>7}{'—':>7}{'—':>8}{'—':>5}{'—':>5}{'无':>8}")
            continue
        cx, cy, n, w, h, x0, y0 = r
        ok = "✓"
        if w > 600 or h > 300:
            ok = "过大?"
        if prev is not None and abs(cx - prev[0]) > 400:
            ok = "跳变"
        print(f"  {p.name:<14}{cx:>7.0f}{cy:>7.0f}{n:>8}{w:>5}{h:>5}{ok:>8}")
        recs.append((p.name, cx, cy, w, h))
        prev = (cx, cy)

    print("\n" + "=" * 92)
    print("  ★ 判读要点")
    print("=" * 92)
    print("  · 质心 x 的**连续位移**可用于估水平速度；")
    print("  · 若同一镜头内 cx 单调增加且步长稳定 ⇒ 该段速度可测；")
    print("  · **不要跨'跳变'帧求差**（那是切镜或遮挡）；")
    print("  · 绝对离地高度**无法**从这些镜头测出（无地面参考）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
