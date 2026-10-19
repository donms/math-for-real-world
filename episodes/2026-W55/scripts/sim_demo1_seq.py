#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **演示①正确版**：静止起步 → 爬环 → 顶部脱轨 → 左飞 → 调姿 180° → 缓冲落地。

## 用户口述的完整动作（2026-10-17）

> **"从半圆环底部静止起步，一直开到顶部，这是车子倒置，
> 然后顺势往左飞出，在空中调姿 180°，然后缓冲落地。"**

$$\text{① 静止起步}\to\text{② 爬环}\to\text{③ 顶部倒置脱轨}
\to\text{④ 左飞}\to\text{⑤ 调姿 }180°\to\text{⑥ 缓冲落地}$$

## ★ 姿态：为什么是 **180° 滚转**，不是滚转

在圆环**顶部**，车的切向（$+x$）仍水平，但**车体 $+z$（车顶方向）指向圆心 = 向下**。

$$\text{车体 }+\hat z\text{ 朝下}\ \Longrightarrow\
\text{绕 }y\text{ 轴（横轴）转了 }180°$$

**⇒ 要把车翻正，必须**滚转 180°**（用 $J_{\text{pitch}}$），把 $\hat z$ 转回来。**

$$\boxed{\text{"倒挂"是滚转 }180°\text{ 造成的，不是滚转}}$$

## 各段模型

### ② 爬环（风扇吸附）

$$\theta:\ 0^\circ(\text{底})\to180^\circ(\text{顶}),\qquad
z=R(1+\cos\theta)\Big|_{\theta=\pi}=0,\
z\Big|_{\theta=0}=2R$$

法向力（指向圆心为正）：

$$N(\theta)=F_a-mg\cos\theta-\frac{mv^2}{R}\ \ge 0$$

$\lambda=2$（报道 2G）⇒ $v\le\sqrt{gR}=10.15$ m/s。

### ③ 顶部脱轨

速度水平、**指向 $-x$**（沿圆环左行）：

$$\mathbf v=(-v_{\text{top}},\,0),\qquad z=2R=21\ \text{m}$$

### ⑤ 空中调姿 180°（滚转）

$$\alpha=\frac{4\theta}{T^2},\qquad M=J_{\text{pitch}}\alpha$$

**由车底 4 台差动实现**（前两 vs 后两）：

$$\tau_y=r_zF_x-r_xF_z=-r_xF_z
\;\Longrightarrow\;
\tau_y=1.5\times2F=3F$$
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import Polygon  # noqa: E402
from matplotlib.animation import FuncAnimation, FFMpegWriter  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph          # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W55"
OUT = EP / "publish" / "视频"
FIG = EP / "results" / "figs"

M = ph.M_CAR
G = ph.G
R = 10.5
H_TOP = 2 * R
LAM = 2.0
V_MIN_NOFAN = math.sqrt(G * R)   # ★ 无风扇所需的最低车速（不是上限）
V_TOP = 9.34                     # 采用车速（自定，低于 V_MIN_NOFAN ⇒ 须靠吸附）
A_UP = 3.0
V_TOUCH = 0.5
F_TOT = ph.FZ_MAX
J_P = ph.J_ROLL      # ★ 调姿是**滚转**（翻正且保持航向）
T_ROT = 1.70


def climb():
    r"""① 静止起步 + ② 爬环。返回 (t, x, z, vx, vz, theta, N, 记录)。"""
    recs, t, th, v = [], 0.0, math.pi, 0.0
    s = 0.0                     # 沿轨弧长
    dt = 1.0 / 200
    while th > 1e-9:
        a = A_UP if v < V_TOP else 0.0
        v = min(V_TOP, v + a * dt)
        s += v * dt
        th = math.pi - s / R
        if th < 0:
            th = 0.0
        t += dt
        x = R * math.sin(th)
        z = R * (1.0 + math.cos(th))
        # 切向速度（沿环向上 => 世界分量）
        vx = v * math.cos(th) * (-1.0)
        vz = v * math.sin(th)
        # ★ 2026-10-17 修正：v² 项符号（圆心在车下方 ⇒ 重力与反力都指向圆心）
        N = LAM * M * G + M * v * v / R - M * G * math.cos(th)
        recs.append(dict(t=t, x=x, z=z, vx=vx, vz=vz, th=th, pitch=th - math.pi,
                         ph="climb", N=N))
    return recs


def flight(recs, dt=1.0 / 200):
    r"""③ 脱轨 → ④ 左飞 → ⑤ 调姿 → ⑥ 缓冲。"""
    r = recs[-1]
    x, z, vx, vz = r["x"], r["z"], -V_TOP, 0.0
    pitch = 0.0                      # 相对"正立"的滚转角，倒挂时为 π
    # 顶部时车体 +z 朝下 ⇒ 滚转 = π
    pitch = math.pi
    t = r["t"]
    om = 0.0
    alpha = 4 * math.pi / (T_ROT * T_ROT)
    recs.append(dict(t=t, x=x, z=z, vx=vx, vz=vz, th=0.0, pitch=pitch,
                     ph="detach", N=0.0))
    # ④+⑤ 空中：自由落体 + 滚转 180°
    a_max = F_TOT / M - G
    z_trig = None
    for _ in range(200000):
        stop = vz ** 2 / (2 * a_max) if a_max > 0 else 0.0
        if z <= stop * 1.35:
            z_trig = z
            break
        # 滚转律：bang-bang 一半加速一半减速
        # ★ 从 π 转到 0（共 180°）；bang-bang 一半加速一半减速
        if pitch <= 1e-9:
            acc = 0.0
        else:
            acc = alpha if (t - r["t"]) < T_ROT / 2 else -alpha
        om += acc * dt
        pitch -= om * dt                 # 朝正立方向转
        if pitch < 0.0:
            pitch, om = 0.0, 0.0
        vz -= G * dt
        z += vz * dt
        x += vx * dt
        t += dt
        recs.append(dict(t=t, x=x, z=z, vx=vx, vz=vz, th=0.0, pitch=pitch,
                         ph="air", N=0.0))
        if z <= 0.3:
            z_trig = z
            break
    # ⑥ 缓冲
    for _ in range(200000):
        if abs(vz) <= V_TOUCH:
            F = M * G
        else:
            a_need = (vz ** 2 - V_TOUCH ** 2) / (2.0 * max(z, 1e-6))
            F = min(F_TOT, M * (G + max(0.0, a_need)))
        vz += (F / M - G) * dt
        z += vz * dt
        x += vx * dt
        t += dt
        pitch = max(0.0, pitch - om * dt)
        if z <= 0.02:
            z = 0.0
            break
        recs.append(dict(t=t, x=x, z=z, vx=vx, vz=vz, th=0.0, pitch=pitch,
                         ph="thrust", N=0.0))
    recs.append(dict(t=t, x=x, z=0.0, vx=vx, vz=vz, th=0.0, pitch=pitch,
                     ph="land", N=0.0))
    return recs, z_trig


def cfg():
    cands = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
    have = {f.name for f in font_manager.fontManager.ttflist}
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = \
        ([c for c in cands if c in have] or ["DejaVu Sans"]) + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


COL = {"climb": "#38bdf8", "detach": "#f59e0b", "air": "#ef4444",
       "thrust": "#22c55e", "land": "#a78bfa"}
LAB = {"climb": "爬环（倒挂）", "detach": "顶部脱轨", "air": "左飞 + 调姿",
       "thrust": "缓冲", "land": "落地"}


def draw(ax, r, trail):
    ax.clear()
    ax.set_xlim(-30, 14)
    ax.set_ylim(-3, H_TOP + 6)
    ax.axis("off")
    ax.set_facecolor("#0b1220")
    ax.plot([-30, 14], [0, 0], color="#475569", lw=2)
    arc = [(R * math.sin(a), R * (1 + math.cos(a)))
           for a in [math.pi * i / 90 for i in range(0, 181)]]
    ax.plot([p[0] for p in arc], [p[1] for p in arc], color="#64748b", lw=4)
    if len(trail) > 1:
        ax.plot([p[0] for p in trail], [p[1] for p in trail],
                color="#38bdf8", lw=1.6, alpha=.5)
    L, H = 4.5, 1.19
    # ★ 车身姿态：
    #   爬环段 —— 机头**沿轨道切线**（一路沿着环的方向开），随 θ 连续转动；
    #   空中段 —— 保持脱轨瞬间的姿态（机头朝 -x、车顶朝下），
    #              滚转 180° 在侧视图里看不出来，只由文字给出角度。
    if r["ph"] == "climb":
        ang = math.atan2(math.sin(r["th"]), -math.cos(r["th"]))
    else:
        ang = math.pi
    ca, sa = math.cos(ang), math.sin(ang)
    pts = [(-L / 2, 0), (L / 2, 0), (L / 2, H), (-L / 2, H)]
    body = [(r["x"] + px * ca - py * sa, r["z"] + px * sa + py * ca)
            for px, py in pts]
    ax.add_patch(Polygon(body, closed=True, fc="#c9d3de", ec="#64748b",
                         lw=1.0, zorder=6))
    roof = [(r["x"] + px * ca - py * sa, r["z"] + px * sa + py * ca)
            for px, py in [(-L / 2 * .95, H), (L / 2 * .95, H),
                           (L / 2 * .95, H - .14), (-L / 2 * .95, H - .14)]]
    ax.add_patch(Polygon(roof, closed=True, fc="#38bdf8", ec="none", zorder=7))
    ax.text(-8, H_TOP + 4.2,
            f"{LAB[r['ph']]}  t={r['t']:.2f}s  z={r['z']:.1f}m  "
            f"滚转={math.degrees(r['pitch']):.0f}°",
            ha="center", fontsize=11, color=COL[r["ph"]], weight="bold")


def main():
    cfg()
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    print("=" * 82)
    print("  演示① 正确版：静止起步 → 爬环 → 顶部脱轨 → 左飞 → 调姿180° → 落地")
    print("=" * 82)
    print(f"\n  R = {R:.2f} m（顶高 {H_TOP:.0f} m），λ = {LAM:.1f}")
    print(f"  无风扇时所需最低车速 = {V_MIN_NOFAN:.2f} m/s；"
          f"取 v_top = {V_TOP:.2f} m/s（{V_TOP*3.6:.1f} km/h）⇒ 须靠吸附")

    recs = climb()
    n1 = len(recs)
    nmin = min(r["N"] for r in recs)
    recs, z_trig = flight(recs)
    print(f"\n  ①② 爬环：{n1} 步，{recs[n1-1]['t']:.2f} s")
    print(f"     全程最小法向力 N_min = {nmin/1000:+.2f} kN"
          f"（{'✓ 未脱离' if nmin >= 0 else '✗ 脱离'}）")
    last = recs[-1]
    print(f"  ③ 顶部脱轨：z = {H_TOP:.0f} m，vx = {-V_TOP:+.2f} m/s（向左）")
    print(f"  ④⑤ 空中：滚转 180°，用时 {T_ROT:.2f} s")
    alpha = 4 * math.pi / (T_ROT ** 2)
    print(f"     α = {alpha:.2f} rad/s²，J_roll={J_P:.0f} "f"M = {J_P*alpha/1000:.1f} kN·m"
          f" ⇒ 每喷 {J_P*alpha/3/1000:.2f} kN")
    print(f"  ⑥ 缓冲点火高度 z_i = {z_trig:.2f} m")
    print(f"\n  落地：t = {last['t']:.2f} s，vz = {last['vz']:+.3f} m/s，"
          f"x = {last['x']:.2f} m，末态滚转 = {math.degrees(last['pitch']):.0f}°")

    # 图
    fig, axs = plt.subplots(1, 3, figsize=(16, 5.0))
    fig.patch.set_facecolor("#0b1220")
    for ax in axs:
        ax.set_facecolor("#0b1220")
        ax.tick_params(colors="#94a3b8")
        for s in ax.spines.values():
            s.set_color("#334155")
        ax.grid(alpha=.18)
    ts = [r["t"] for r in recs]
    axs[0].plot(ts, [r["z"] for r in recs], color="#38bdf8", lw=2)
    axs[0].axhline(H_TOP, color="#f59e0b", ls="--", lw=1)
    axs[0].set_title("高度 z(t)", color="#e2e8f0")
    axs[1].plot(ts, [math.degrees(r["pitch"]) for r in recs],
                color="#ef4444", lw=2)
    axs[1].axhline(180, color="#f59e0b", ls="--", lw=1)
    axs[1].set_title("滚转角（180° = 倒挂，0° = 正立）", color="#e2e8f0")
    axs[1].set_ylim(-8, 200)
    cl = recs[:n1]
    axs[2].plot([math.degrees(r["th"]) for r in cl],
                [r["N"] / 1000 for r in cl], color="#22c55e", lw=2)
    axs[2].axhline(0, color="#94a3b8", ls="--", lw=1)
    axs[2].set_title(f"爬环法向力（λ={LAM:.1f}）", color="#e2e8f0")
    axs[2].set_xlabel("θ (°，180=底，0=顶)", color="#e2e8f0")
    for a in axs:
        a.set_xlabel(a.get_xlabel() or "t (s)", color="#e2e8f0")
    fig.tight_layout()
    png = FIG / "fig_inverted_sequence.png"
    fig.savefig(png, facecolor="#0b1220", dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  [OK] {png.name}  {png.stat().st_size/1024:.0f} KB")

    fig2, ax2 = plt.subplots(figsize=(10.0, 7.4))
    fig2.patch.set_facecolor("#0b1220")
    step = max(1, len(recs) // 240)
    frames = list(range(0, len(recs), step)) + [len(recs) - 1] * 25
    trail = []

    def upd(i):
        r = recs[frames[i]]
        trail.append((r["x"], r["z"]))
        draw(ax2, r, trail)
        return []

    anim = FuncAnimation(fig2, upd, frames=len(frames),
                         interval=1000 / 30, repeat=False)
    mp4 = OUT / "sim_inverted_seq.mp4"
    anim.save(str(mp4), writer=FFMpegWriter(fps=30, bitrate=3600))
    plt.close(fig2)
    print(f"  [OK] {mp4.name}  {mp4.stat().st_size/1e6:.2f} MB")
    print("\n" + "=" * 82)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
