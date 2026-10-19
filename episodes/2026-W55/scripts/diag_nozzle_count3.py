#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **数羽流 v3**：手动定窗 + 画亮度剖面直方图给人看。

## 前两版为什么不可靠

| 版本 | 问题 |
|---|---|
| v1（颜色掩膜 + 峰）| 把整片烟云算进来，得 36 个子峰 |
| v2（竖直连贯性）| 车底自动检测取到 92 分位 ⇒ 剖面落在车下方太远，全在烟里 |

## 本版做法

**不自动检测，改人工定窗**（我已从图上看到羽流大致在哪个范围），
然后**把剖面画出来** —— 让人一眼能数峰。

**★ 这是"自动方法不可靠时退回到可视化"的正确做法**：
与其调参调到出个数字，不如**把证据摆出来**。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W55"
FIG = EP / "results" / "figs"


def setup() -> None:
    from matplotlib import font_manager
    cands = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
    have = {f.name for f in font_manager.fontManager.ttflist}
    pick = [c for c in cands if c in have] or ["DejaVu Sans"]
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = pick + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 130


def main() -> int:
    setup()
    print("=" * 88)
    print("  W55 · 数羽流 v3（画剖面给人看）")
    print("=" * 88)

    fn = "j_19_0.png"
    a = np.asarray(Image.open(EP / "data" / "jump2" / fn)
                   .convert("RGB")).astype(int)
    H, W, _ = a.shape
    print(f"\n  {fn}  {W}×{H}")

    # ★ 人工定窗：从放大图看到的羽流区（原图坐标）
    #   车底约 y=270，地面约 y=500
    y0, y1 = 275, 495
    #   羽流横向大致 x=390..830
    x0, x1 = 380, 840
    print(f"  羽流取窗 x∈[{x0},{x1}]  y∈[{y0},{y1}]")

    band = a[y0:y1, x0:x1]
    lum = band.max(axis=2).astype(float)
    prof = lum.mean(axis=0)              # 每列平均亮度
    prof_top = lum[:40].mean(axis=0)     # 顶部 40 行（靠车底，羽流最清晰）
    prof_bot = lum[-40:].mean(axis=0)    # 底部 40 行

    # 平滑
    def smooth(v: np.ndarray, k: int = 7) -> np.ndarray:
        return np.convolve(v, np.ones(k) / k, mode="same")

    ps = smooth(prof)
    pt = smooth(prof_top)

    fig, axes = plt.subplots(2, 1, figsize=(13, 7.6), sharex=True)

    ax = axes[0]
    ax.plot(np.arange(x0, x1), pt, color="#2980b9", lw=1.8,
            label="靠车底 40 行（羽流根部，最清晰）")
    ax.plot(np.arange(x0, x1), ps, color="#7f8c8d", lw=1.2, alpha=.75,
            label="全窗平均")
    ax.set_ylabel("列平均亮度", fontsize=11)
    ax.set_title("羽流亮度剖面：每个峰 ≈ 一条羽流", fontsize=13, pad=10)
    ax.legend(fontsize=9, frameon=False)
    ax.grid(alpha=.28, ls=":")

    # 找峰（在"靠车底"那条上找，最可靠）
    v = pt
    thr = v.max() * 0.30
    peaks = []
    for i in range(3, len(v) - 3):
        if v[i] >= thr and v[i] >= v[i - 1] and v[i] >= v[i + 1]:
            if peaks and i - peaks[-1] < 12:
                if v[i] > v[peaks[-1]]:
                    peaks[-1] = i
                continue
            peaks.append(i)
    for pk in peaks:
        ax.axvline(x0 + pk, color="#c0392b", ls="--", lw=1.0, alpha=.7)
        ax.annotate(f"#{peaks.index(pk)+1}", (x0 + pk, v[pk]),
                    textcoords="offset points", xytext=(0, 6),
                    ha="center", fontsize=9, color="#c0392b")
    print(f"\n  ★ 在「靠车底」剖面上找到 **{len(peaks)} 个峰**：")
    for k, pk in enumerate(peaks, 1):
        print(f"      #{k}  x = {x0+pk}  亮度 {v[pk]:.0f}")

    # ---- 下：把该窗口的图直接画出来，供人核对 ----
    ax2 = axes[1]
    ax2.imshow(a[y0:y1, x0:x1].astype(np.uint8),
               extent=[x0, x1, y1, y0], aspect="auto")
    for pk in peaks:
        ax2.axvline(x0 + pk, color="#e74c3c", ls="--", lw=1.4, alpha=.9)
    ax2.set_xlabel("图像 x 坐标（px）", fontsize=11)
    ax2.set_ylabel("y（px）", fontsize=11)
    ax2.set_title("同一窗口的原图（红线 = 检测到的峰）",
                  fontsize=12, pad=8)

    fig.tight_layout()
    out = FIG / "fig_plume_count.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  [OK] {out.name}  {out.stat().st_size/1024:.0f} KB")
    print("\n  ★ 结论：看这张图 —— 峰数就是羽流条数，")
    print("    也就是同时点火的竖推喷口数。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
