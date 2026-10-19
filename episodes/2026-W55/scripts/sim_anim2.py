#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **仿真动画 v2**：显示全部 **10 个喷口**（用户要求）。

## 相对 v1 的改动

| 项 | v1 | **v2** |
|---|---|---|
| 喷口状态 | 只显示 4 个竖推 | ★ **全部 10 个**（含待机）|
| 喷口模型 | 内联在动画里 | ★ 抽到 `nozzle_state.py`（单一来源）|
| 车身姿态 | 矩形 | 矩形 + **滚转示意**（车身宽度方向翻转）|
| 面板 | 4 格 | **10 格 + 状态文字** |

## ★ 关于"滚转"在二维侧视里怎么画

**滚转是绕纵轴（前后方向）转 —— 在侧视图里看不到"翻转"，只看到车身侧影不变。**

**⇒ 必须加一个"姿态小表盘"**：在 HUD 旁画一个圆 + 一根指针对应该角度，
让人能看到"车正在滚"。**否则动画里完全看不出滚转。**

**这是"二维画面表达三维转动"的标准做法** ——
主视图给轨迹与位置，小表盘给姿态。
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.animation import FuncAnimation, FFMpegWriter  # noqa: E402
from matplotlib.patches import Rectangle, Polygon, Circle, FancyArrowPatch  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph          # noqa: E402
import nozzle_state as ns     # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W55"
OUT = EP / "publish" / "视频"
FIG = EP / "results" / "figs"


def setup() -> None:
    cands = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
    have = {f.name for f in font_manager.fontManager.ttflist}
    pick = [c for c in cands if c in have] or ["DejaVu Sans"]
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = pick + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 100


# ==================== 车身 ====================

def body_poly(x: float, z: float, th: float = 0.0) -> list[tuple[float, float]]:
    r"""**侧视图里的车身轮廓**：一律水平。

    ## ★ 为什么不按 $\theta$ 旋转

    姿态是**绕纵轴（前后方向）的滚转**。
    **侧视图的观察方向沿左右（$y$）** ⇒ 纵轴在画面里是一条水平线，
    **滚转不改变侧影**（车看起来还是那个长方形，只是"上下两面互换"，
    而那在侧视图里看不出差别）。

    **⇒ 在侧视图里把车身按 $\theta$ 转，画出来的就是俯仰** ——
    这正是用户指出的"看起来像俯仰"。

    **⇒ 滚转必须用"后视图"表达（见 `draw_rear`）。**
    """
    L, H = ph.L_CAR, ph.H_CAR
    return [(x - L / 2, z - H / 2), (x + L / 2, z - H / 2),
            (x + L / 2, z + H / 2), (x - L / 2, z + H / 2)]


def body_frame_local(meta: dict) -> tuple[float, float]:
    r"""喷口在**车体坐标**下的位置（$x$ 沿车身，$z$ 垂直车身）。"""
    return meta["pos"]


def nozzle_world(r: "ns.Rec10", meta: dict) -> tuple[float, float]:
    r"""喷口在**侧视图**里的位置。

    **★ 不按 $\theta$ 旋转**（理由同 `body_poly`）：
    滚转只让"上下两面互换"，在侧视图里位置几乎不变。
    """
    lx, lz = body_frame_local(meta)
    return (r.x + lx, r.z + lz)


# ==================== 绘制 ====================

def draw(ax, ax_g, r: "ns.Rec10", hist: list["ns.Rec10"],
         recs: list["ns.Rec10"]) -> None:
    ax.clear()
    ax_g.clear()

    # ---------- 主视图 ----------
    W_VIEW = 26.0
    x_c = max(6.0, r.x + 3.0)
    ax.set_xlim(x_c - W_VIEW * .38, x_c + W_VIEW * .62)
    ax.set_ylim(-2.0, 15.0)
    ax.set_facecolor("#0b1220")
    ax.grid(color="#1e293b", ls=":", lw=.7)
    ax.tick_params(colors="#94a3b8", labelsize=8)
    for sp in ax.spines.values():
        sp.set_color("#334155")

    ax.axhline(0, color="#475569", lw=2.0, zorder=1)

    x0v, x1v = ax.get_xlim()
    # ★★★ 5 辆车**沿行进方向首尾一串**（俯视图确认；串长 22.8 m）
    #   我原来把 4 辆车摆在 y=±5.5/±8.5，那是"横向一堵墙"—— 错的。
    x_row = 28.0
    if x_row + 12 > x0v and x_row - 12 < x1v:
        for (dx, Lx, Hx, col) in ((-9.20, 4.40, 1.50, "#64748b"),
                                  (-4.60, 4.40, 1.50, "#64748b"),
                                  (+0.00, 6.20, 4.00, "#e2e8f0"),
                                  (+4.60, 4.40, 1.50, "#64748b"),
                                  (+9.20, 4.40, 1.50, "#64748b")):
            ax.add_patch(Rectangle((x_row + dx - Lx / 2, 0), Lx, Hx,
                                   fc=col, ec="#475569", lw=.7, zorder=2))
        if x0v < x_row < x1v:
            ax.text(x_row, 4.35, "卡车 4 m", ha="center", fontsize=7.5,
                    color="#cbd5e1")
    # 轨迹
    if len(hist) > 2:
        xs = [h.x for h in hist]
        zs = [h.z for h in hist]
        m = [(-5 < x < x1v + 5) for x in xs]
        if any(m):
            ax.plot([x for x, k in zip(xs, m) if k],
                    [z for z, k in zip(zs, m) if k],
                    color="#38bdf8", lw=1.4, alpha=.45, zorder=3)

    # ---------- 10 个喷口（逐一画）----------
    # 先画羽流（在车身后面），再画车身，最后画喷口点
    for meta in ns.NOZZLE_META:
        n = meta["name"]
        f = r.f.get(n, 0.0)
        if f <= 1.0:
            continue
        px, pz = nozzle_world(r, meta)
        ax_dir = meta["axis"]
        # ★★★ 羽流方向 = **推力方向的反向**（动量守恒）
        #   竖推推力向上(+Z) ⇒ 排气向下(−Z)；UNCAP 推力向下 ⇒ 排气向上。
        #   我第一版把"推力方向"当"喷流方向"画，结果是落地时羽流朝上 —— 错的。
        thrust_dir = {"+X": (1, 0), "-X": (-1, 0), "+Z": (0, 1),
                      "-Z": (0, -1), "+Y": (0.35, 0), "-Y": (-0.35, 0)}[ax_dir]
        dx, dz = -thrust_dir[0], -thrust_dir[1]
        ln = min(3.0, 0.12 + f / 22000.0 * 2.8)
        ax.plot([px, px + dx * ln], [pz, pz + dz * ln],
                color=meta["color"], lw=5.5, alpha=.60,
                solid_capstyle="round", zorder=4)
        ax.plot([px, px + dx * ln], [pz, pz + dz * ln],
                color="#f8fafc", lw=1.6, alpha=.85, zorder=5)

    # 车身
    pl = body_poly(r.x, r.z, r.theta)
    ax.add_patch(Polygon(pl, closed=True, fc="#cbd5e1", ec="#94a3b8",
                         lw=1.6, zorder=6))
    hx = r.x + (ph.L_CAR / 2 - .35)
    hz = r.z
    ax.plot([hx], [hz], "o", color="#0f172a", ms=5.5, zorder=7)

    # 喷口位置点（10 个都画，亮的表示正在喷；**只给正在喷的加标签**以免重叠）
    for meta in ns.NOZZLE_META:
        n = meta["name"]
        f = r.f.get(n, 0.0)
        px, pz = nozzle_world(r, meta)
        on = f > 1.0
        ax.plot([px], [pz], "o", ms=7.0 if on else 3.6,
                mec="#0f172a", mew=.6, zorder=8,
                mfc=meta["color"] if on else "#475569")
        if on:
            lx, lz = meta["pos"]
            dy = .52 if lz >= 0 else -.52
            ax.text(px, pz + dy, meta["short"],
                    ha="center", va="center", fontsize=7,
                    color=meta["color"], zorder=9,
                    bbox=dict(fc="#0b1220", ec="none", alpha=.8, pad=1.4))

    # ---------- HUD ----------
    hud = "\n".join([
        f"t = {r.t:5.2f} s",
        f"高度 {r.z:5.2f} m",
        f"竖直速度 {r.vz:+6.2f} m/s",
        f"罐压 {r.p_mPa:4.1f} MPa",
        f"已耗气 {r.m_total:5.1f} kg",
    ])
    ax.text(.985, .975, hud, transform=ax.transAxes, va="top", ha="right",
            fontsize=8, color="#e2e8f0", linespacing=1.45,
            bbox=dict(fc="#0f172a", ec="#334155", alpha=.95, pad=5))

    ax.set_xlabel("水平距离 (m)", fontsize=8.5, color="#94a3b8")
    ax.set_ylabel("高度 (m)", fontsize=8.5, color="#94a3b8")
    ax.set_title("TESLA Roadster 飞跃五车 · 仿真　侧视（车身水平，滚转见左侧后视图）",
                 fontsize=12, color="#e2e8f0", pad=7)

    # ---------- 后视图：滚转在这里才能看见 ----------
    draw_rear(ax_g, r)


def draw_rear(axg, r: "ns.Rec10") -> None:
    r"""**后视图**：从车尾看过去，车身横截面绕中心旋转。

    ## 为什么必须有这个视图

    **滚转绕纵轴（前后）⇒ 从后面看，车身就是一个矩形在转。**
    * 角度 0°：正立（车顶朝上）；
    * 角度 180°：倒立（车顶朝下）；
    * 角度 90°/270°：车身侧躺。

    **⇒ 这是"滚转"唯一直观可读的视图。**

    **★ 侧视图里车身始终水平** —— 两个视图配合才完整。
    """
    axg.clear()
    axg.set_aspect("equal")
    axg.set_xlim(-1.55, 1.55)
    axg.set_ylim(-1.55, 1.55)
    axg.axis("off")
    axg.set_facecolor("#0b1220")

    # 参考圆
    axg.add_patch(Circle((0, 0), 1.12, fc="#0f172a", ec="#334155", lw=1.2))
    # 地面参考（下方短横线）
    axg.plot([-1.35, 1.35], [-1.42, -1.42], color="#475569", lw=1.6)

    # 车身横截面：宽 W、高 H，按 theta 旋转
    W, H = ph.W_CAR, ph.H_CAR
    c, s = math.cos(r.theta), math.sin(r.theta)
    pts = []
    for (a, b) in ((-W / 2, -H / 2), (W / 2, -H / 2),
                   (W / 2, H / 2), (-W / 2, H / 2)):
        pts.append((a * c - b * s, a * s + b * c))
    axg.add_patch(Polygon(pts, closed=True, fc="#cbd5e1",
                          ec="#94a3b8", lw=1.4, zorder=3))
    # 车顶标记（一端小三角，跟随旋转）
    tip = []
    for (a, b) in ((-0.35, H / 2), (0.35, H / 2), (0.0, H / 2 + 0.30)):
        tip.append((a * c - b * s, a * s + b * c))
    axg.add_patch(Polygon(tip, closed=True, fc="#38bdf8", ec="none",
                          zorder=4))
    # 四个竖推的位置（在后视图里是四个角）
    for meta in ns.NOZZLE_META:
        if not meta["name"].startswith("LIFT_"):
            continue
        wx = -W / 2 + (0.0 if meta["pos"][0] < 0 else W)
        wz = -H / 2 + (0.0 if meta["pos"][1] < 0 else H)
        xr, zr = wx * c - wz * s, wx * s + wz * c
        f = r.f.get(meta["name"], 0.0)
        axg.plot([xr], [zr], "o", ms=5.0 if f > 1 else 3.2,
                 mfc=meta["color"] if f > 1 else "#475569",
                 mec="#0f172a", mew=.5, zorder=6)

    axg.text(0, -1.62, f"后视 · 滚转 {ph.wrap_deg(r.theta):+.0f}°",
             ha="center", fontsize=7.5, color="#94a3b8")
    axg.set_title("从车尾看（滚转）", fontsize=8, color="#94a3b8", pad=2)


def draw_panel(axp, r: "ns.Rec10") -> None:
    r"""**10 个喷口的状态条**（横向一排，用户明确要求）。"""
    axp.clear()
    axp.set_xlim(0, 10)
    axp.set_ylim(0, 1.55)
    axp.axis("off")
    axp.set_facecolor("#0b1220")
    axp.text(-0.06, 1.42, "10 个喷口当前推力（颜色越亮 = 推力越大；灰 = 待机）",
             fontsize=8, color="#94a3b8", va="top")
    for k, meta in enumerate(ns.NOZZLE_META):
        n = meta["name"]
        f = r.f.get(n, 0.0)
        frac = min(1.0, f / 20000.0)
        bx = k + 0.10
        W = 0.80
        # 底槽
        axp.add_patch(Rectangle((bx, .30), W, .68,
                                fc="#111827", ec="#334155", lw=.7))
        # 填充
        if frac > 0.004:
            axp.add_patch(Rectangle((bx, .30), W, .68 * frac,
                                    fc=meta["color"], ec="none"))
        # 名称（上）+ 轴（下）
        axp.text(bx + W / 2, 1.10, meta["short"], ha="center",
                 fontsize=7.5, color="#e2e8f0" if f > 1 else "#64748b")
        axp.text(bx + W / 2, .12, f"{f/1000:.0f}" if f > 1 else "—",
                 ha="center", fontsize=7,
                 color=meta["color"] if f > 1 else "#475569")


def main() -> int:
    setup()
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    print("=" * 84)
    print("  W55 · 仿真动画 v2（10 个喷口）")
    print("=" * 84)

    dt = 1 / 150
    recs = ns.run_mission10_auto(dt)
    s = ns.summarize10(recs)
    print(f"\n  {len(recs)} 步，{s['t_end']:.2f} s")
    print(f"  峰值 {s['z_max']:.2f} m，落地 vz {s['vz_land']:+.2f} m/s")
    print(f"  姿态 {s['theta_end_deg']:+.0f}°（共转 "
          f"{s['theta_total_deg']:.0f}°）")
    print(f"  耗气 {s['m_total']:.1f} kg，罐压 {s['p_end']:.1f} MPa")

    fps = 30
    step = max(1, int(round(len(recs) / (fps * 9.0))))
    idx = list(range(0, len(recs), step))
    print(f"\n  抽帧 {len(idx)} 张，{fps} fps ⇒ {len(idx)/fps:.1f} s")

    fig = plt.figure(figsize=(13.6, 8.2))
    fig.patch.set_facecolor("#0b1220")
    # ★ 布局：主视图在上（横跨全宽），下方一行放"姿态盘 + 10 喷口面板"
    gs = fig.add_gridspec(2, 2, width_ratios=[1.35, 6.6],
                          height_ratios=[6.4, 1.7],
                          left=.045, right=.98, top=.935, bottom=.055,
                          wspace=.05, hspace=.16)
    ax = fig.add_subplot(gs[0, :])          # 主视图：占满上排
    ax_g = fig.add_subplot(gs[1, 0])        # 姿态盘：左下
    ax_p = fig.add_subplot(gs[1, 1])        # 10 喷口：右下横条

    def upd(i: int) -> None:
        k = idx[i]
        draw(ax, ax_g, recs[k], recs[:k + 1], recs)
        draw_panel(ax_p, recs[k])

    anim = FuncAnimation(fig, upd, frames=len(idx),
                         interval=1000 / fps, repeat=False)
    out = OUT / "sim_jump_10nozzle.mp4"
    anim.save(str(out), writer=FFMpegWriter(fps=fps, bitrate=3400))
    plt.close(fig)
    print(f"  [OK] {out.name}  {out.stat().st_size/1e6:.2f} MB")

    # 关键帧：每格用 gridspec 给主视图 + 小姿态盘
    keys = [0, len(idx) // 6, len(idx) // 3, len(idx) // 2,
            2 * len(idx) // 3, len(idx) - 1]
    fig2 = plt.figure(figsize=(17.5, 9.0))
    fig2.patch.set_facecolor("#0b1220")
    gs2 = fig2.add_gridspec(2, 3, left=.02, right=.985, top=.94,
                            bottom=.05, wspace=.06, hspace=.12)
    for j, k in enumerate(keys):
        row, col = divmod(j, 3)
        axm = fig2.add_subplot(gs2[row, col])
        axg2 = axm.inset_axes([.015, .72, .13, .26])
        draw(axm, axg2, recs[k], recs[:k + 1], recs)
    png = FIG / "fig_sim_keyframes_10nozzle.png"
    fig2.savefig(png, bbox_inches="tight", facecolor="#0b1220")
    plt.close(fig2)
    print(f"  [OK] {png.name}  {png.stat().st_size/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
