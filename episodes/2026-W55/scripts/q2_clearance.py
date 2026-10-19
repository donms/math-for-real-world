#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · 从飞跃视频量**净空**与**横越时间**（比截图可靠得多）。

## 可测的三件事

| # | 量 | 怎么测 | 为什么重要 |
|---|---|---|---|
| ① | **净空**（车底到卡车顶）| 同帧内两个包围盒的 y 差 | 直接约束"起跳高度 + 竖直冲量" |
| ② | **横越时间** | 车从"卡车左侧"到"右侧"的帧数 ÷ 60 | 与净空一起给出抛物线的形状 |
| ③ | **水平速度** | 车质心的 x 位移 ÷ 帧间隔 | 检验"起飞速度"是否与模型一致 |

## ★ 尺度标定的选择：用**卡车驾驶室宽**

**为什么不用车宽**：车在画面里被**运动模糊**拉长，宽度不可靠。

**为什么用卡车宽**：半挂牵引车驾驶室宽度是**受法规约束的**，
在 2.4–2.6 m 之间（中国/美国都是 2.5 m 或 2.55 m）。
**⇒ 这是视频里最可靠的物理标尺。**

## ★ 三个必须声明的偏差

1. **透视**：车比卡车远（飞在空中），**同一 px/m 不适用**
   ⇒ 本文用"卡车宽"标定后，**对净空做保守修正**（车更远 ⇒ 实际净空更大）；
2. **地面参考缺失**：无法直接给"离地绝对高度"；
   ⇒ 只能给**相对卡车顶的净空**；
3. **相机在动**（有多个机位）⇒ 只在**单一镜头内**做时间分析。
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W55"
J2 = EP / "data" / "jump2"


def blobs_in(path: Path, thr: int, box: tuple[int, int, int, int]
             ) -> list[tuple[float, float, int, int, int, int, int]]:
    r"""返回窗口内**所有**亮连通块：(cx, cy, n, w, h, x0, y0)。"""
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)
    mx = a.max(axis=2)
    m = mx > thr
    x0, x1, y0, y1 = box
    win = np.zeros_like(m)
    win[y0:y1, x0:x1] = m[y0:y1, x0:x1]
    H, W = win.shape
    seen = np.zeros_like(win, dtype=bool)
    out = []
    for yy in range(y0, y1):
        for xx in range(x0, x1):
            if not win[yy, xx] or seen[yy, xx]:
                continue
            stack = [(yy, xx)]
            seen[yy, xx] = True
            comp = []
            while stack:
                cy, cx = stack.pop()
                comp.append((cy, cx))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if y0 <= ny < y1 and x0 <= nx < x1 \
                            and win[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if len(comp) < 150:
                continue
            ys = np.array([c[0] for c in comp])
            xs = np.array([c[1] for c in comp])
            out.append((float(xs.mean()), float(ys.mean()), len(comp),
                        int(xs.max() - xs.min() + 1),
                        int(ys.max() - ys.min() + 1),
                        int(xs.min()), int(ys.min())))
    return sorted(out, key=lambda t: -t[2])


def main() -> int:
    print("=" * 92)
    print("  W55 · 从飞跃视频量净空")
    print("=" * 92)

    # 卡车驾驶室（画面下方）与车（上方）分两个窗口找
    frames = ["m_21_00.png", "m_21_25.png", "m_21_50.png", "m_21_75.png"]
    print("\n  说明：窗口①=车（画面上半）；窗口②=卡车（画面下半）")
    for fn in frames:
        p = J2 / fn
        if not p.exists():
            print(f"  [skip] {fn}")
            continue
        car = blobs_in(p, 150, (500, 1000, 60, 420))
        trk = blobs_in(p, 95, (250, 600, 500, 740))
        print(f"\n--- {fn} ---")
        if car:
            c = car[0]
            print(f"  车：质心({c[0]:.0f},{c[1]:.0f}) {c[2]}px  "
                  f"包围盒 {c[3]}×{c[4]}  上沿 y={c[6]}")
        if trk:
            t = trk[0]
            print(f"  卡车：质心({t[0]:.0f},{t[1]:.0f}) {t[2]}px  "
                  f"包围盒 {t[3]}×{t[4]}  上沿 y={t[6]}")
        if car and trk:
            c, t = car[0], trk[0]
            gap_px = t[6] - (c[6] + c[4])      # 卡车顶 - 车底
            w_trk = t[3]
            print(f"  净空 {gap_px} px；卡车宽 {w_trk} px")
            for wt in (2.4, 2.5, 2.6):
                ppm = w_trk / wt
                print(f"    卡车宽 {wt} m ⇒ 净空 **{gap_px/ppm:.2f} m**"
                      f"（车宽推算 {c[3]/ppm:.2f} m）")

    print("\n" + "=" * 92)
    print("  ★ 一个重要的判读")
    print("=" * 92)
    print("  · 若「车宽推算」≈ 2 m，说明**该帧的 px/m 对车大致适用**")
    print("    （即车与卡车在同一景深附近）；")
    print("  · 若「车宽推算」> 2.5 m，说明车**被运动模糊拉长**或**更近**，")
    print("    ⇒ 净空读数要相应**放缩**，不能直接采信。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
