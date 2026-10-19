#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""`sim.html` 的 3D 视图预览（用 `car3d.py` 复算同一套算法）。

## 这个脚本还留着做什么

沙箱里起不了浏览器，**拿不到网页截图**。
本脚本用 **与网页同一份几何与同一套渲染四步**（都取自 `car3d.py`）画出 10 个时刻，
**作为"网页应该长什么样"的对照物**。

**⇒ 若网页效果与此图不一致，说明 `sim.html` 的 JS 与 `car3d.py` 走样了。**

## 与动画脚本的分工

| 脚本 | 用途 |
|---|---|
| `sim_anim3d_v3.py` | 出**视频**（含 HUD、喷口条、落地停留）|
| 本脚本 | 出**静帧拼图**（便于逐帧比对网页）|
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402
from matplotlib.patches import Polygon  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nozzle_state as ns     # noqa: E402
import car3d as c3            # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
FIG = ROOT / "episodes" / "2026-W55" / "results" / "figs"

VIEW_W, VIEW_H = 16.0, 9.2


def setup() -> None:
    cands = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
    have = {f.name for f in font_manager.fontManager.ttflist}
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = \
        ([c for c in cands if c in have] or ["DejaVu Sans"]) + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def render(ax, fr) -> None:
    ax.set_xlim(0, VIEW_W)
    ax.set_ylim(VIEW_H, 0)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_facecolor("#0b1220")

    cam, focal, cx, cy = c3.camera_for(fr, VIEW_W, VIEW_H)
    hy = c3.horizon_y(fr, cam, focal, cx, cy, VIEW_H)
    ax.add_patch(Polygon([(0, hy), (VIEW_W, hy), (VIEW_W, VIEW_H), (0, VIEW_H)],
                         closed=True, fc="#22314c", ec="none", zorder=0))

    draws = c3.collect_drawables(fr, cam, focal, cx, cy)
    if draws:
        ax.add_collection(PolyCollection(
            [d[0] for d in draws],
            facecolors=[d[1] for d in draws],
            edgecolors=(0.06, 0.09, 0.16, 0.5), linewidths=0.35, zorder=3))

    # 滚转轴
    a = c3.project(cam, (fr.x - 3.65, 0, fr.z + c3.BODY_LIFT), focal, cx, cy)
    b = c3.project(cam, (fr.x + 3.65, 0, fr.z + c3.BODY_LIFT), focal, cx, cy)
    if a and b:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#fbbf24", lw=1.6,
                ls=(0, (6, 4)), zorder=6)


def main() -> int:
    setup()
    recs = ns.run_mission10_auto(1 / 150)
    n = len(recs)
    keys = [min(n - 1, int(n * f))
            for f in (0.02, 0.12, 0.24, 0.36, 0.48,
                      0.60, 0.72, 0.84, 0.93, 0.99)]
    fig, axs = plt.subplots(2, 5, figsize=(17.5, 7.6))
    fig.patch.set_facecolor("#0b1220")
    for ax, k in zip(axs.ravel(), keys):
        r = recs[k]
        render(ax, r)
        ax.set_title(f"t={r.t:.2f}s  z={r.z:.2f}m  "
                     f"滚转{math.degrees(r.theta):+.0f}°",
                     fontsize=9, color="#e2e8f0", pad=3)
    fig.suptitle("sim.html 的 3D 视图（与 car3d.py 同源，Python 复算）",
                 color="#e2e8f0", fontsize=13, y=0.985)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    out = FIG / "fig_html3d_preview.png"
    fig.savefig(out, facecolor="#0b1220", dpi=110, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] {out.name}  {out.stat().st_size/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
