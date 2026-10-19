#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **数羽流 v4（最终）**：全羽流区 + 双阈值 + 出图。

## 我目前掌握的

`j_19_0.png`（车在空中、羽流最清晰的一帧）里，
**左半部分（x≈490–580）有两条明显的橙蓝色羽流带的两个峰**，
右半部分被**烟云/雾化**覆盖，不易分离。

## v4 的做法

1. **窗口扩到 x∈[380, 1000]**（覆盖全部可见羽流）；
2. 用"**亮度 + 饱和度**"双判据，且**只取羽流根部 60 行**（靠车底）；
3. **同时画三条曲线**：根部亮度、根部蓝色分量、全窗平均
   —— 三条曲线的峰若**一致**，才算一条羽流；
4. **出图给人复核**（不从自动结果直接下结论）。

## ★ 为什么最终要以"人看图"为准

自动峰检测在**弥散烟云**上不可靠（试了三版：36 峰 / 2 段 / 7 峰，都不稳定）。
**⇒ 本脚本的定位是"把证据整理好"，结论由人确认。**
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


def smooth(v: np.ndarray, k: int = 9) -> np.ndarray:
    return np.convolve(v, np.ones(k) / k, mode="same")


def main() -> int:
    setup()
    print("=" * 88)
    print("  W55 · 数羽流 v4（最终版）")
    print("=" * 88)

    fn = "j_19_0.png"
    a = np.asarray(Image.open(EP / "data" / "jump2" / fn)
                   .convert("RGB")).astype(int)
    H, W, _ = a.shape

    x0, x1 = 380, 1010
    y0, y1 = 272, 500
    root_h = 70            # 羽流根部取靠车底的 70 行
    print(f"\n  {fn}  {W}×{H}")
    print(f"  窗口 x∈[{x0},{x1}]  y∈[{y0},{y1}]，根部取前 {root_h} 行")

    win = a[y0:y1, x0:x1]
    lum = win.max(axis=2).astype(float)
    blue = win[:, :, 2].astype(float) - win[:, :, 0].astype(float)

    p_lum_root = smooth(lum[:root_h].mean(axis=0))
    p_blue_root = smooth(blue[:root_h].mean(axis=0))
    p_lum_all = smooth(lum.mean(axis=0))

    xs = np.arange(x0, x1)
    fig, axes = plt.subplots(3, 1, figsize=(14, 10),
                             gridspec_kw={"height_ratios": [1, 1, 1.6]})

    ax = axes[0]
    ax.plot(xs, p_lum_root, color="#2980b9", lw=1.8, label="根部亮度")
    ax.set_ylabel("亮度", fontsize=10)
    ax.set_title("羽流根部亮度剖面（靠车底，最清晰）", fontsize=12)
    ax.grid(alpha=.25, ls=":")

    ax = axes[1]
    ax.plot(xs, p_blue_root, color="#27ae60", lw=1.8, label="根部蓝色分量 B−R")
    ax.plot(xs, p_lum_all, color="#7f8c8d", lw=1.1, alpha=.7,
            label="全窗亮度（参考）")
    ax.set_ylabel("强度", fontsize=10)
    ax.set_title("蓝色分量剖面 —— 羽流偏蓝，烟云偏白", fontsize=12)
    ax.legend(fontsize=9, frameon=False)
    ax.grid(alpha=.25, ls=":")

    ax = axes[2]
    ax.imshow(a[y0:y1, x0:x1].astype(np.uint8),
              extent=[x0, x1, y1, y0], aspect="auto")
    ax.set_xlabel("图像 x（px）", fontsize=11)
    ax.set_ylabel("y（px）", fontsize=11)
    ax.set_title("原图（同一窗口）—— 请在此图上目视确认羽流条数",
                 fontsize=12)
    # 20px 网格线帮助读数
    for gx in range(x0, x1 + 1, 40):
        ax.axvline(gx, color="#e74c3c", lw=.6, alpha=.35)

    fig.suptitle("数羽流：每条竖向羽流 = 一个点火的喷口",
                 fontsize=14, y=1.002)
    fig.tight_layout()
    out = FIG / "fig_plume_count.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  [OK] {out.name}  {out.stat().st_size/1024:.0f} KB")

    # ---- 自动给出"候选峰"（仅供参考）----
    print("\n【自动候选峰】（仅供参考，需人眼复核）")
    for name, prof, thr_frac in (("根部亮度", p_lum_root, .35),
                                 ("根部蓝分量", p_blue_root, .40)):
        thr = prof.max() * thr_frac
        pk = []
        for i in range(6, len(prof) - 6):
            if prof[i] >= thr and prof[i] >= prof[i - 1] \
                    and prof[i] >= prof[i + 1]:
                if pk and i - pk[-1] < 18:
                    if prof[i] > prof[pk[-1]]:
                        pk[-1] = i
                    continue
                pk.append(i)
        print(f"  {name}：{len(pk)} 个峰 → x = "
              f"{[int(x0 + i) for i in pk]}")

    print("\n" + "=" * 88)
    print("  ★ 交给人工判断")
    print("=" * 88)
    print("  请看图 3（原图）并数竖向的蓝色羽流条数。")
    print("  已知观察：左侧两条（x≈510、560）非常清晰；")
    print("  右侧被烟云遮挡，需要靠蓝色分量曲线判断。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
