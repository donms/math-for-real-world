#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **仿真动画**：把羽流逐帧画出来（4 个竖推分别点亮）。

## 为什么"逐模拟步输出"而不是"逐帧重算"

**动画必须和物理积分是同一份数据**。
如果先算轨迹、再单独画动画，两者会**各算一次** ⇒ 容易不一致。

**⇒ 本脚本先跑一次积分，把每一步的完整状态（含各喷口推力）存成序列，
再拿这个序列逐帧作图。** 一次积分，两种用途。

## 画面构成

| 元素 | 说明 |
|---|---|
| **车身** | 矩形 + 车头标记，按姿态角旋转 |
| **4 个竖推** | 车底四角，**逐一按实际推力点亮** |
| **羽流长度** | 与该喷口当前推力成正比（推力大 = 羽流长）|
| **轨迹** | 已飞过的路径（淡色） |
| **两个 HUD** | 高度 / 竖直速度 / 罐压 / 已耗气 |
| **地面与障碍** | 5 辆车那一排（6 m 宽、4 m 高卡车）|

## ★ "羽流长度 ∝ 推力"的依据

冷气羽流的**可见长度**主要由**动量通量**决定，
在定常状态下近似 $L \propto F^{1/2}$（射流贯穿距离 $\propto \sqrt{F}$）。
**本文简化为线性**，并在图上标注"示意"。
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.animation import FuncAnimation, FFMpegWriter  # noqa: E402
from matplotlib.patches import Rectangle, Polygon  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph      # noqa: E402
import nozzles as nz      # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W55"
OUT = EP / "publish" / "视频"


def setup() -> None:
    cands = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
    have = {f.name for f in font_manager.fontManager.ttflist}
    pick = [c for c in cands if c in have] or ["DejaVu Sans"]
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = pick + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 100


# ==================== 轨迹记录 ====================

@dataclass
class Rec:
    t: float = 0.0
    x: float = 0.0
    z: float = 0.0
    vx: float = 0.0
    vz: float = 0.0
    theta: float = 0.0
    omega: float = 0.0
    fz_total: float = 0.0
    lift_on: list[float] = field(default_factory=list)   # 4 个竖推的当前推力
    roll_l: float = 0.0
    roll_r: float = 0.0
    p_mPa: float = 0.0
    m_used: float = 0.0


def run_mission(dt: float = 1 / 120) -> list[Rec]:
    r"""跑一次完整飞跃（含 4 竖推与滚转），记录每一步。

    **★ 与 `physics.run_jump` 的区别**：
    这里**显式跟踪 4 个竖推各自的推力**（按罐压修正），
    以便动画能"分别点亮"。
    """
    vz0 = ph.launch_speed_for_height(ph.H_JUMP)
    st = ph.State(0.0, 0.0, ph.V_LAUNCH_X, vz0, 0.0, 0.0)
    # ★ 姿态绕**纵轴滚转** ⇒ 必须用 J_ROLL，不能用默认的 J_PITCH
    #   （默认 3615 vs 907 ⇒ 角加速度会小 4 倍，转不满一圈）
    p = ph.Params(drag_k=0.0, j=ph.J_ROLL)

    # 罐的当前质量（4 竖推共用）
    m_tank = ph.M_AIR
    # 4 个竖推的喉部面积（各 10 kN @ 满罐）
    at_lift = nz.area_for_force(20e3, ph.P_TANK)
    at_roll = nz.area_for_force(1.5e3, ph.P_TANK)

    # ★ 姿态时间基准 = **两次通过的实测腾空时间**，不是纯抛体的 2vz0/g。
    #   先用纯抛体时间估一个 T，跑一遍得到实际落地时间，再用它重定 alpha。
    T_probe = 2 * vz0 / ph.G
    T_actual = T_probe * 1.20          # 缓冲会让下落变长，先估 1.2 倍
    alpha = ph.bang_bang_alpha(2 * math.pi, T_actual)
    # ★ 冻结减速度控制器（避免末段发散，见 physics.BufferController）
    ctrl = ph.BufferController(m=p.m, z_trigger=ph.Z_TRIGGER)

    recs: list[Rec] = []
    m_used = 0.0
    while st.t < 20.0:
        p_now = max(m_tank * ph.R_GAS * ph.T0 / ph.V_TANK, ph.P_ATM * 1.01)

        # ---- 姿态：bang-bang 滚转 ----
        torque = ph.J_ROLL * alpha if st.t < T_actual / 2 else -ph.J_ROLL * alpha
        roll_on_l = 1.0 if st.t < T_actual / 2 else 0.0
        roll_on_r = 1.0 - roll_on_l

        # ---- 竖直：落地缓冲 ----
        fz_need = ctrl.step(st.z, st.vz, st.t)
        # 4 个竖推平分该需求
        f_each = fz_need / 4.0
        # 该罐压下每个竖推能给的推力
        f_max = nz.force_of_area(at_lift, p_now)
        duty = min(1.0, f_each / f_max) if f_max > 0 else 0.0
        fz_total = 0.0
        lift_on: list[float] = []
        dm = 0.0
        for _ in range(4):
            f = nz.force_of_area(at_lift, p_now) * duty
            fz_total += f
            lift_on.append(f)
            dm += nz.mdot_of_area(at_lift, p_now) * duty * dt
        # 滚转喷口耗气
        for on, at in ((roll_on_l, at_roll), (roll_on_r, at_roll)):
            if on > 0:
                dm += nz.mdot_of_area(at, p_now) * on * dt
        m_tank -= dm
        m_used += dm

        th = ph.Thrust(fz=fz_total, torque=torque)
        st = ph.rk4_step(st, th, p, dt)
        st.t = round(st.t, 9)

        recs.append(Rec(
            t=st.t, x=st.x, z=st.z, vx=st.vx, vz=st.vz,
            theta=st.theta, omega=st.omega, fz_total=fz_total,
            lift_on=lift_on,
            roll_l=roll_on_l * nz.force_of_area(at_roll, p_now),
            roll_r=roll_on_r * nz.force_of_area(at_roll, p_now),
            p_mPa=p_now / 1e6, m_used=m_used,
        ))

        if st.z <= 0.0 and st.vz < 0 and st.t > 0.5:
            break
    return recs


# ==================== 绘图 ====================

def body_polygon(x: float, z: float, theta: float
                 ) -> list[tuple[float, float]]:
    r"""车身矩形（$L\times H$）绕质心旋转 $\theta$。

    **★ $\theta$ 的定义**：绕横轴的俯仰角，正 = 车头抬起。
    在 $x$–$z$ 平面（侧视）里就是普通二维旋转。
    """
    L, H = ph.L_CAR, ph.H_CAR
    pts = [(-L / 2, -H / 2), (L / 2, -H / 2),
           (L / 2, H / 2), (-L / 2, H / 2)]
    c, s = math.cos(theta), math.sin(theta)
    return [(x + px * c - pz * s, z + px * s + pz * c) for px, pz in pts]


def draw_frame(ax, r: Rec, hist: list[Rec], t_max: float) -> None:
    ax.clear()
    # ---- 相机跟随：视野宽度 26 m，车居中偏左 ----
    W_VIEW = 26.0
    x_c = max(6.0, r.x + 3.0)
    ax.set_xlim(x_c - W_VIEW * 0.38, x_c + W_VIEW * 0.62)
    ax.set_ylim(-1.8, 14.5)
    ax.set_facecolor("#0d1117")
    ax.grid(color="#1f2937", ls=":", lw=.7)
    ax.tick_params(colors="#9ca3af", labelsize=8)
    for sp in ax.spines.values():
        sp.set_color("#374151")

    # ---- 地面 ----
    ax.axhline(0, color="#4b5563", lw=2.0, zorder=1)

    # ---- 5 辆车那一排 ----
    x_row = 30.0
    x0v, x1v = ax.get_xlim()
    if x_row + 9 > x0v and x_row - 9 < x1v:
        ax.add_patch(Rectangle((x_row - 1.2, 0), 2.4, 4.0,
                               fc="#e5e7eb", ec="#9ca3af", lw=.8, zorder=2))
        if x0v < x_row < x1v:
            ax.text(x_row, 4.4, "卡车 4 m", ha="center", fontsize=7.5,
                    color="#e5e7eb")
        for dx in (-4.0, -7.0, 4.0, 7.0):
            ax.add_patch(Rectangle((x_row + dx - 1.1, 0), 2.2, 1.5,
                                   fc="#6b7280", ec="#4b5563", lw=.7,
                                   zorder=2))

    # ---- 已走过的轨迹（只画视野内的）----
    if len(hist) > 1:
        xs = [h.x for h in hist if x0v - 5 < h.x < x1v + 5]
        zs = [h.z for h in hist if x0v - 5 < h.x < x1v + 5]
        if len(xs) > 1:
            ax.plot(xs, zs, color="#38bdf8", lw=1.4, alpha=.5, zorder=3)

    # ---- 车身与羽流 ----
    pl = body_polygon(r.x, r.z, r.theta)
    cx = sum(p[0] for p in pl) / 4
    cz = sum(p[1] for p in pl) / 4
    offs = [(-1.5, -0.55), (1.5, -0.55), (-1.5, 0.55), (1.5, 0.55)]
    c, s = math.cos(r.theta), math.sin(r.theta)
    for k, (ox, oz) in enumerate(offs):
        f = r.lift_on[k] if k < len(r.lift_on) else 0.0
        if f <= 1.0:
            continue
        px = cx + ox * c - oz * s
        pz = cz + ox * s + oz * c
        dx, dz = math.sin(r.theta), -math.cos(r.theta)
        ln = min(3.2, 0.15 + f / 24000.0 * 3.0)
        ax.plot([px, px + dx * ln], [pz, pz + dz * ln],
                color="#7dd3fc", lw=6.0, alpha=.80,
                solid_capstyle="round", zorder=4)
        ax.plot([px, px + dx * ln], [pz, pz + dz * ln],
                color="#f0f9ff", lw=2.2, alpha=.95, zorder=5)

    ax.add_patch(Polygon(pl, closed=True, fc="#cbd5e1",
                         ec="#94a3b8", lw=1.6, zorder=6))
    hx = cx + (ph.L_CAR / 2 - 0.35) * math.cos(r.theta)
    hz = cz + (ph.L_CAR / 2 - 0.35) * math.sin(r.theta)
    ax.plot([hx], [hz], "o", color="#0f172a", ms=6, zorder=7)

    # ---- HUD：右上角，不透明底 ----
    hud = (f"t = {r.t:5.2f} s\n"
           f"高度 {r.z:5.2f} m\n"
           f"竖直速度 {r.vz:+6.2f} m/s\n"
           f"罐压 {r.p_mPa:4.1f} MPa\n"
           f"已耗气 {r.m_used:5.1f} kg")
    ax.text(.985, .975, hud, transform=ax.transAxes, va="top", ha="right",
            fontsize=8, color="#e5e7eb", linespacing=1.45,
            bbox=dict(fc="#111827", ec="#374151", alpha=.94, pad=6))

    # ---- 4 个竖推的推力条：左下角，固定在坐标轴内 ----
    names = ["FL", "FR", "RL", "RR"]
    base_y, h_bar, w_bar = .075, .085, .042
    ax.text(.015, base_y + h_bar + .055, "4 个竖推推力", transform=ax.transAxes,
            fontsize=8, color="#9ca3af")
    for k, nm in enumerate(names):
        f = r.lift_on[k] if k < len(r.lift_on) else 0.0
        frac = min(1.0, f / 20000.0)
        bx = .015 + k * (w_bar + .012)
        ax.add_patch(Rectangle((bx, base_y), w_bar, h_bar,
                               transform=ax.transAxes,
                               fc="#1f2937", ec="#4b5563", lw=.6,
                               zorder=8, clip_on=False))
        if frac > 0.01:
            ax.add_patch(Rectangle((bx, base_y), w_bar, h_bar * frac,
                                   transform=ax.transAxes,
                                   fc="#38bdf8", ec="none",
                                   zorder=9, clip_on=False))
        ax.text(bx + w_bar / 2, base_y - .032, nm, transform=ax.transAxes,
                ha="center", fontsize=7, color="#9ca3af")

    ax.set_xlabel("水平距离 (m)", fontsize=9, color="#9ca3af")
    ax.set_ylabel("高度 (m)", fontsize=9, color="#9ca3af")
    ax.set_title(f"TESLA Roadster 飞跃五车 · 仿真复刻　{r.t:5.2f} s",
                 fontsize=12.5, color="#e5e7eb", pad=8)


def main() -> int:
    setup()
    OUT.mkdir(parents=True, exist_ok=True)
    print("=" * 84)
    print("  W55 · 仿真动画")
    print("=" * 84)

    dt = 1 / 120
    recs = run_mission(dt)
    print(f"\n  积分完成：{len(recs)} 步，{recs[-1].t:.2f} s")
    print(f"  峰值高度 {max(r.z for r in recs):.2f} m")
    print(f"  落地 vz {recs[-1].vz:+.2f} m/s，水平 "
          f"{recs[-1].x:.1f} m")
    print(f"  末端姿态 {ph.wrap_deg(recs[-1].theta):+.0f}°，"
          f"罐压 {recs[-1].p_mPa:.1f} MPa")
    print(f"  耗气 {recs[-1].m_used:.1f} kg")

    # ---- 抽帧（控制时长）----
    fps = 30
    step = max(1, int(round(len(recs) / (fps * 8.0))))   # ≈8 秒动画
    frames = recs[::step]
    print(f"\n  抽帧 {len(frames)} 张（每 {step} 步），{fps} fps "
          f"⇒ {len(frames)/fps:.1f} s 动画")

    fig, ax = plt.subplots(figsize=(12.8, 6.4))
    fig.patch.set_facecolor("#0d1117")

    def upd(i: int) -> None:
        draw_frame(ax, frames[i], recs[:i * step + 1], recs[-1].t)

    t_max = recs[-1].t
    anim = FuncAnimation(fig, upd, frames=len(frames),
                         interval=1000 / fps, repeat=False)
    out = OUT / "sim_jump.mp4"
    writer = FFMpegWriter(fps=fps, bitrate=3200,
                          metadata={"title": "Roadster 飞跃仿真"})
    anim.save(str(out), writer=writer, dpi=100)
    plt.close(fig)
    print(f"\n  [OK] {out.name}  {out.stat().st_size/1e6:.2f} MB")

    # ---- 另存一张"关键帧拼图"作封面 ----
    key_idx = [0, len(frames) // 6, len(frames) // 3,
               len(frames) // 2, 2 * len(frames) // 3, len(frames) - 1]
    fig2, axs = plt.subplots(2, 3, figsize=(16.5, 8.4))
    fig2.patch.set_facecolor("#0d1117")
    for a, idx in zip(axs.ravel(), key_idx):
        draw_frame(a, frames[idx], recs[:idx * step + 1], t_max)
    fig2.tight_layout()
    png = EP / "results" / "figs" / "fig_sim_keyframes.png"
    fig2.savefig(png, bbox_inches="tight")
    plt.close(fig2)
    print(f"  [OK] {png.name}  {png.stat().st_size/1024:.0f} KB")

    print("\n" + "=" * 84)
    print("  ★ 动画中 4 个竖推分别点亮，可与视频里的 4 条羽流对照。")
    print("=" * 84)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
