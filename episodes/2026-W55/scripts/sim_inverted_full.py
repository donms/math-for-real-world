#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **演示①完整复刻**：倒挂爬升 → 脱轨 → 自由落体 → 推进器减速落地。

## 报道里的四段（第一电动网/快科技，2026-10-17）

> "Roadster 沿着环形轨道**倒挂爬升**，攀升至约 **21 m** 高度后
> **脱离轨道自由坠落**，随后冷气推进器**启动喷气减速**，**平稳落地**。"

$$\text{① 倒挂爬升}\ \to\ \text{② 脱轨}\ \to\ \text{③ 自由落体}\ \to\ \text{④ 推进器减速}$$

## 各段模型

### ① 倒挂爬升（风扇吸附）

半圆轨道，半径 $R$，圆心在 $(0,R)$（**不在**地面）；$\theta$ 从 **180°（地面）** 到 **0°（顶点）**：

$$x=R\sin\theta,\qquad z=R(1+\cos\theta)
\;\Longrightarrow\;z_{\max}=2R=21\ \text{m}
\;\Longrightarrow\;\boxed{R=10.5\ \text{m}}$$

## ★★★ 2026-10-17 修正：法向力的 $v^2$ 项符号原来是错的

顶点处**圆心在车下方**，故：重力向下 = **指向**圆心；坡面反力 $N$（坡面在上、推车向下）= **指向**圆心；风扇吸附 $F_a$（把车吸向坡面 = 向上）= **背离**圆心。取指向圆心为正：

$$mg+N-F_a=\frac{mv^2}{R}
\;\Longrightarrow\;\boxed{N(\theta)=F_a+\frac{mv^2}{R}-mg\cos\theta}$$

旧稿写成 $N=F_a-mg\cos\theta-mv^2/R$，把 $v^2$ 项的符号搞反了。
**方程形式只差一个符号，结论方向完全相反**：

$$N\ge0\iff\lambda\ge\cos\theta-\frac{v^2}{gR}
\;\xrightarrow{\ \theta=0\ }\;\lambda\ge1-\frac{v^2}{gR}$$

* **无风扇（$\lambda=0$）**：需 $v\ge\sqrt{gR}=10.15$ m/s（36.5 km/h），**必须够快**才贴得住；
* **2G 风扇（$\lambda=2$）**：判据恒成立 ⇒ **无速度约束，可以任意慢**。

$$\boxed{\text{风扇的作用是"让车能慢慢爬"，不是"让车能更快"}}$$

本文取 $F_a=2mg$（报道约 2G）与 $v=9.34$ m/s（自定，与飞跃段一致）。
该车速**低于**无风扇所需的 10.15 m/s ⇒ 无风扇时顶点 $N=-3.00$ kN（会脱离）⇒ **吸附在本演示中确实不可省**。
有吸附时顶点 $N=mg+mv^2/R=\mathbf{+36.24}$ kN。

### ② 脱轨

在顶点 $z=21$ m、速度**水平**（圆顶点切线水平），$v_x=v$、$v_z=0$。

### ③ 自由落体

$$\ddot z=-g,\qquad \ddot x=0$$

### ④ 推进器减速落地

四角竖推产生的净减速（含重力）：

$$a_{\text{net}}=\frac{F}{m}-g$$

从 $z_i$ 以 $v_{z0}$ 减速到地面时 $v_z=-0.5$ m/s：

$$\boxed{F=m\left(g+\frac{v_{z0}^2-v_t^2}{2z_i}\right)}$$

**⇒ 与"飞跃"段用的是同一个缓冲控制器，只是初条件不同。**
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.animation import FuncAnimation, FFMpegWriter  # noqa: E402
from matplotlib.patches import Polygon  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph          # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W55"
OUT = EP / "publish" / "视频"
FIG = EP / "results" / "figs"

M = ph.M_CAR
G = ph.G
H_DETACH = 21.0                # 脱轨高度（报道）
R_ARC = H_DETACH / 2.0         # 半圆轨道 ⇒ R = 10.5 m
LAM = 2.0                      # 风扇吸附 ≈ 2G（报道 ①）
# ★★★ 改正后：sqrt(gR) 是**无风扇时所需的最低车速**，不是"车速上限"。
#   有 2G 吸附时判据恒成立，不存在速度上限。
V_MIN_NOFAN = math.sqrt(G * R_ARC)      # 10.15 m/s（36.5 km/h）
V_CLIMB = 9.34                 # 采用车速（自定 ③，与飞跃段一致）
V_TOUCH = 0.5                  # 目标触地速度
F_LIFT_TOT = ph.FZ_MAX         # 四角竖推总推力 80 kN


def adhesion_ok(theta: float, v: float) -> float:
    r"""改正后的法向力 $N(\theta)=F_a+\dfrac{mv^2}{R}-mg\cos\theta$。

    **2026-10-17 修正**：旧稿为 $F_a-mg\cos\theta-mv^2/R$，$v^2$ 项符号反了。
    顶点处圆心在车下方 ⇒ 重力与坡面反力都**指向**圆心、吸附力**背离**圆心。
    """
    return LAM * M * G + M * v * v / R_ARC - M * G * math.cos(theta)


def simulate(dt: float = 1.0 / 200):
    r"""四段全程，返回记录列表。"""
    recs = []
    # ---------- ① 倒挂爬升：theta 180° -> 0 ----------
    t = 0.0
    th = math.pi
    while th > 0.0:
        th -= V_CLIMB / R_ARC * dt
        t += dt
        th = max(th, 0.0)
        x = R_ARC * math.sin(th)
        z = R_ARC * (1.0 + math.cos(th))
        vx = V_CLIMB * math.cos(th)
        vz = V_CLIMB * math.sin(th)
        recs.append(dict(t=t, x=x, z=z, vx=vx, vz=vz, th=th,
                         ph="climb", N=adhesion_ok(th, V_CLIMB)))
    # ---------- ② 脱轨（瞬间） ----------
    x, z = 0.0, H_DETACH
    vx, vz = V_CLIMB, 0.0
    t_det = t
    recs.append(dict(t=t, x=x, z=z, vx=vx, vz=vz, th=0.0, ph="detach",
                     N=0.0))
    # ---------- ③ 自由落体（拖到"最后一刻"才点火） ----------
    # ★ 点火判据：以**额定推力**能提供的最大净减速 a_max，
    #   此刻开始刹车的制动距离 = vz^2/(2 a_max)；
    #   当 z 接近该距离（留 10% 裕度）才点火 ⇒ 自由落体段最长。
    a_max = F_LIFT_TOT / M - G
    z_trig = None
    for _ in range(200000):
        stop_dist = vz ** 2 / (2.0 * a_max) if a_max > 0 else 0.0
        if z <= stop_dist * 1.35:
            z_trig = z
            break
        vz -= G * dt
        z += vz * dt
        x += vx * dt
        t += dt
        recs.append(dict(t=t, x=x, z=z, vx=vx, vz=vz, th=0.0, ph="fall",
                         N=0.0))
        if z <= 0.05:
            z_trig = z
            break
    # ---------- ④ 推进器减速（"冻结减速"律） ----------
    for _ in range(200000):
        if abs(vz) <= V_TOUCH:
            # 已达目标速度 ⇒ 用 F=mg 维持等速下降（松油门会重新加速）
            F = M * G
        else:
            a_need = (vz ** 2 - V_TOUCH ** 2) / (2.0 * max(z, 1e-6))
            F = min(F_LIFT_TOT, M * (G + max(0.0, a_need)))
        az = F / M - G
        vz += az * dt
        z += vz * dt
        x += vx * dt
        t += dt
        if z <= 0.02:
            z = 0.0
            break
        recs.append(dict(t=t, x=x, z=z, vx=vx, vz=vz, th=0.0, ph="thrust",
                         N=0.0))
    recs.append(dict(t=t, x=x, z=0.0, vx=vx, vz=vz, th=0.0, ph="land", N=0.0))
    return recs, z_trig, t_det


def cfg() -> None:
    cands = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
    have = {f.name for f in font_manager.fontManager.ttflist}
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = \
        ([c for c in cands if c in have] or ["DejaVu Sans"]) + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


PH_COL = {"climb": "#38bdf8", "detach": "#f59e0b", "fall": "#ef4444",
          "thrust": "#22c55e", "land": "#a78bfa"}


def draw(ax, r, trail) -> None:
    ax.clear()
    ax.set_xlim(-14, 14)
    ax.set_ylim(-2.5, H_DETACH + 4)
    ax.axis("off")
    ax.set_facecolor("#0b1220")
    # 地面
    ax.plot([-14, 14], [0, 0], color="#475569", lw=2)
    # 半圆轨道（圆心在地面，半径 R）
    arc = [(R_ARC * math.sin(a), R_ARC * (1 + math.cos(a)))
           for a in [math.pi * i / 90 for i in range(0, 91)]]
    ax.plot([p[0] for p in arc], [p[1] for p in arc],
            color="#64748b", lw=4, alpha=.85)
    ax.plot([p[0] for p in arc], [p[1] for p in arc],
            color="#cbd5e1", lw=1.2, alpha=.9)
    # 轨迹
    if len(trail) > 1:
        ax.plot([p[0] for p in trail], [p[1] for p in trail],
                color="#38bdf8", lw=1.6, alpha=.55)
    # 车
    L, H = 4.5, 1.19
    ang = r["th"] if r["ph"] == "climb" else 0.0
    ca, sa = math.cos(ang), math.sin(ang)
    # 倒挂段：车底朝圆心（法向朝外）
    flip = -1.0 if r["ph"] == "climb" else 1.0
    pts = [(-L / 2, 0), (L / 2, 0), (L / 2, H), (-L / 2, H)]
    body = [(r["x"] + px * ca - flip * py * sa,
             r["z"] + px * sa + flip * py * ca) for px, py in pts]
    ax.add_patch(Polygon(body, closed=True, fc="#c9d3de", ec="#64748b",
                         lw=1.0, zorder=6))
    roof = [(r["x"] + px * ca - flip * py * sa,
             r["z"] + px * sa + flip * py * ca)
            for px, py in [(-L / 2 * .95, H), (L / 2 * .95, H),
                           (L / 2 * .95, H - .12), (-L / 2 * .95, H - .12)]]
    ax.add_patch(Polygon(roof, closed=True, fc="#38bdf8", ec="none",
                         zorder=7))
    lab = {"climb": "① 倒挂爬升（风扇吸附）", "detach": "② 脱轨",
           "fall": "③ 自由落体", "thrust": "④ 推进器减速",
           "land": "落地"}[r["ph"]]
    ax.text(0, H_DETACH + 2.2,
            f"{lab}    t={r['t']:.2f}s   z={r['z']:.2f} m   "
            f"vz={r['vz']:+.2f} m/s",
            ha="center", fontsize=12, color=PH_COL[r["ph"]], weight="bold")


def main() -> int:
    cfg()
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    print("=" * 80)
    print("  演示①完整复刻：倒挂爬升 → 脱轨 → 自由落体 → 推进器减速")
    print("=" * 80)
    print(f"\n  轨道半径 R = {R_ARC:.2f} m（半圆顶 = {H_DETACH:.0f} m），"
          f"圆心在 (0, R) ⇒ 顶点处圆心在车下方")
    print(f"  吸附 λ = {LAM:.1f} G（报道）⇒ 判据 λ ≥ cosθ − v²/(gR)"
          f" 恒成立 ⇒ **无速度上限**")
    print(f"  无风扇时所需**最低**车速 v_min = √(gR) = "
          f"{V_MIN_NOFAN:.2f} m/s（{V_MIN_NOFAN*3.6:.1f} km/h）")
    print(f"  采取车速 {V_CLIMB:.2f} m/s（{V_CLIMB*3.6:.1f} km/h，自定）；"
          f"低于 v_min ⇒ 无风扇会脱离 ⇒ 吸附不可省")

    recs, z_trig, t_det = simulate()
    n0 = sum(1 for r in recs if r["ph"] == "climb")
    n1 = sum(1 for r in recs if r["ph"] == "fall")
    n2 = sum(1 for r in recs if r["ph"] == "thrust")
    print(f"\n  ① 爬升 {n0} 步，用时 {t_det:.2f} s")
    print(f"     顶点法向力 N = {recs[n0-1]['N']/1000:+.2f} kN"
          f"（应 ≥ 0）")
    print(f"  ③ 自由落体 {n1} 步，点火高度 z_i = {z_trig:.2f} m")
    print(f"  ④ 推进器减速 {n2} 步")
    last = recs[-1]
    print(f"\n  落地：t = {last['t']:.2f} s，vz = {last['vz']:+.3f} m/s，"
          f"x = {last['x']:.2f} m")
    print(f"  全程 {last['t']:.2f} s")

    # ---- 关键图 ----
    fig, axs = plt.subplots(1, 3, figsize=(16, 5.2))
    fig.patch.set_facecolor("#0b1220")
    for ax in axs:
        ax.set_facecolor("#0b1220")
        ax.tick_params(colors="#94a3b8")
        for s in ax.spines.values():
            s.set_color("#334155")
        ax.grid(alpha=.18)
    ts = [r["t"] for r in recs]
    axs[0].plot(ts, [r["z"] for r in recs], color="#38bdf8", lw=2)
    axs[0].axhline(H_DETACH, color="#f59e0b", ls="--", lw=1.2)
    axs[0].set_title("高度 z(t)", color="#e2e8f0")
    axs[0].set_xlabel("t (s)", color="#e2e8f0")
    axs[0].set_ylabel("z (m)", color="#e2e8f0")
    axs[1].plot(ts, [r["vz"] for r in recs], color="#ef4444", lw=2)
    axs[1].set_title("竖直速度 vz(t)", color="#e2e8f0")
    axs[1].set_xlabel("t (s)", color="#e2e8f0")
    axs[1].set_ylabel("vz (m/s)", color="#e2e8f0")
    cl = [r for r in recs if r["ph"] == "climb"]
    axs[2].plot([math.degrees(r["th"]) for r in cl],
                [r["N"] / 1000 for r in cl], color="#22c55e", lw=2)
    axs[2].axhline(0, color="#94a3b8", ls="--", lw=1)
    axs[2].set_title(f"倒挂段法向力 N(θ)（λ={LAM:.1f}）", color="#e2e8f0")
    axs[2].set_xlabel("θ (°，180 = 地面，0 = 顶点)", color="#e2e8f0")
    axs[2].set_ylabel("N (kN)", color="#e2e8f0")
    fig.tight_layout()
    png = FIG / "fig_inverted_full.png"
    fig.savefig(png, facecolor="#0b1220", dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  [OK] {png.name}  {png.stat().st_size/1024:.0f} KB")

    # ---- 动画 ----
    fig2, ax2 = plt.subplots(figsize=(9.0, 8.2))
    fig2.patch.set_facecolor("#0b1220")
    step = max(1, len(recs) // 200)
    frames = list(range(0, len(recs), step)) + [len(recs) - 1] * 25
    trail: list[tuple[float, float]] = []

    def upd(i):
        r = recs[frames[i]]
        trail.append((r["x"], r["z"]))
        draw(ax2, r, trail)
        return []

    anim = FuncAnimation(fig2, upd, frames=len(frames),
                         interval=1000 / 30, repeat=False)
    mp4 = OUT / "sim_inverted_full.mp4"
    anim.save(str(mp4), writer=FFMpegWriter(fps=30, bitrate=3600))
    plt.close(fig2)
    print(f"  [OK] {mp4.name}  {mp4.stat().st_size/1e6:.2f} MB")

    print("\n" + "=" * 80)
    print("  ★ 四段全部跑通")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
