#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · 横向偏移时刻图（实拍对照用的小插图）。

**这张图存在的唯一理由**：实拍那一帧在**顶点附近**，而下落还有半程。
拿它去对模型的**落地**横向残余（85.0 cm）是**跨时刻比两个位置**。
同一时刻（顶点）模型只有 **72.2 cm**。

三个锚点（`results/real_offset_timeline.csv` 现跑落盘，可溯源）：

| 时刻 | 横向 y |
|---|---|
| 顶点 t≈2.05 s | **+72.2 cm** |
| 横向峰值 t≈3.69 s | **+95.8 cm** |
| 落地 t≈4.33 s | **+85.0 cm** |

⇒ 过顶点后车**还在继续外扩 +23.6 cm**，接近地面才回收 **−10.8 cm**。
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                            # noqa: E402
import numpy as np                                          # noqa: E402

EP = Path(__file__).resolve().parents[1]
CSV = EP / "results" / "real_offset_timeline.csv"

NAVY = "#1F3B63"
RED = "#C0392B"
DARKRED = "#922B21"
GREY = "#5A6672"
YEL = "#FFD400"
CHIP = "#F1F2EE"


def load() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    d = np.genfromtxt(CSV, delimiter=",", names=True, encoding="utf-8")
    return d["t_s"], d["z_m"], d["y_cm"]


def anchors() -> dict:
    r"""三个锚点。

    ⚠️ **顶点那一步 z 在两个相邻采样上几乎相等**（2.047/2.053，差 <1e-4 m）。
    若 CSV 只写 4 位小数会变成平局，`argmax` 取到前一个 ⇒ 顶点横向读成 71.4
    而不是 72.2。故 CSV 里 z 写 6 位小数；这里再按"平局取 y 更大的那个"兜底。
    """
    t, z, y = load()
    zmax = float(np.max(z))
    near = np.nonzero(z >= zmax - 1e-6)[0]
    ia = int(near[np.argmax(y[near])])
    iy = int(np.argmax(y))
    return {
        "t": t, "z": z, "y": y,
        "apex": (float(t[ia]), float(y[ia]), float(z[ia])),
        "ypeak": (float(t[iy]), float(y[iy]), float(z[iy])),
        "land": (float(t[-1]), float(y[-1]), float(z[-1])),
    }


def draw(ax, scale: float = 1.0, show_text: bool = True,
         show_band: bool = True, mark: str = "land") -> dict:
    r"""把 y(t) 画到给定 axes 上。

    `mark` 决定"实拍竖线"画在哪：
    * `"land"`（默认）：画在**曲线终点 t≈4.33 s**。实拍那张是**落地态**，
      对照点就是终点。★ 2026-10-18 用户定：**曲线终点 = 对照点**。
    * `"apex"`：画在顶点（旧版用法，仅需强调顶点时用）。
    """
    a = anchors()
    t, y = a["t"], a["y"]
    ta, ya, _ = a["apex"]
    tp, yp, _ = a["ypeak"]
    tl, yl, _ = a["land"]

    if show_band:
        ax.axhspan(50, 150, color=YEL, alpha=0.16, lw=0,
                   label="实拍的量级带 50 到 150 厘米", zorder=0)
    ax.plot(t, y, color=NAVY, lw=2.2 * scale, zorder=4,
            solid_capstyle="round")

    # 实拍竖线：默认画在**曲线终点（落地）** —— 实拍那张就是落地态
    tm = tl if mark == "land" else ta
    ax.axvline(tm, color=GREY, lw=1.3 * scale, ls=(0, (4, 4)), zorder=2)
    ax.plot([ta], [ya], "o", ms=7 * scale, mfc="#FFFFFF", mec=NAVY,
            mew=2.2 * scale, zorder=6)
    ax.plot([tp], [yp], "o", ms=7 * scale, mfc=RED, mec="#FFFFFF",
            mew=1.6 * scale, zorder=6)
    ax.plot([tl], [yl], "o", ms=7 * scale, mfc=DARKRED, mec="#FFFFFF",
            mew=1.6 * scale, zorder=6, clip_on=False)

    fs = 9.2 * scale
    ax.annotate(f"顶点 {ya:.1f}", xy=(ta, ya), xytext=(ta + 0.16, ya - 3),
                fontsize=fs, color=NAVY, fontweight="bold", va="center")
    ax.annotate(f"横向峰值 {yp:.1f}", xy=(tp, yp), xytext=(tp - 0.20, yp + 9),
                fontsize=fs, color=RED, fontweight="bold", ha="right",
                va="center")
    ax.annotate(f"落地 {yl:.1f}", xy=(tl, yl), xytext=(tl - 0.16, yl - 12),
                fontsize=fs, color=DARKRED, fontweight="bold", ha="right",
                va="center")

    ax.set_xlim(0, 4.42)
    ax.set_ylim(0, 118)
    ax.set_xticks([0, 1, 2, 3, 4])
    ax.set_yticks([0, 50, 100])
    ax.tick_params(labelsize=fs * 0.95, colors=GREY, length=3 * scale)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#C8CDD2")
        ax.spines[s].set_linewidth(0.9 * scale)
    ax.grid(True, axis="y", ls=(0, (2, 3)), color="#D8DCE0", lw=0.8 * scale)
    ax.set_axisbelow(True)
    # ★ 不画 xlabel：横屏素材底部 120 px 要留给字幕，多一行会被压住。
    #   时间单位写进标题里。
    ax.set_ylabel("横向偏移 y（厘米）", fontsize=fs, color=GREY, labelpad=2)
    ax.set_title("横向偏移随时间（秒，模型 10 个喷口）", fontsize=fs * 1.08,
                 color=NAVY, loc="left", pad=4)

    if show_text:
        ax.text(0.012, 0.885, "实拍的量级带 50 到 150 厘米",
                transform=ax.transAxes, fontsize=fs * 0.95, color="#8A7414",
                va="top", ha="left")
        ax.text(0.985, 0.045,
                f"实拍是落地之后（曲线终点）\n"
                f"车在空中一路外扩 +{yp - ya:.1f}，落地才回收 −{yp - yl:.1f}",
                transform=ax.transAxes, fontsize=fs * 0.92, color=GREY,
                va="bottom", ha="right", linespacing=1.45)
    # "实拍（落地后）"贴着竖线标，说明对照点在哪（放**顶部**，底部留给图内注释）
    ax.text(tm - 0.05, 114.0, "实拍（落地后）", fontsize=fs * 0.92,
            color=GREY, ha="right", va="top", zorder=9)
    return a
