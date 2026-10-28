#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""2026-W58 三维参数化建模与时域姿态可视化。

产出
----
* ``results/figs/fig6_3d_views.png``   三视图（等轴/侧视/前视）
* ``results/figs/fig7_3d_sequence.png`` 过浪四连拍（基线 vs 改进方案）
* ``results/figs/w58_wave3d.mp4``      15 秒过浪动画（帧由时域解驱动）

设计
----
几何全部由参数生成（前后板宽度/长度/安装角/轮底偏置都能改），
姿态 (z, θ) 与波面 η(x,t) **直接来自** `w58_core.simulate` 的解，
不是手工 K 帧 —— 这一点写进论文 4.4 节。
"""
from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
EP = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EP.parent.parent / "scripts"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

import w58_core as c
from w58_core import P0

try:
    from common import setup_cn_font
    setup_cn_font()
except Exception as _e:
    print("[warn] 中文字体未注册:", _e)

R = EP / "results"
FIGS = R / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

COL = dict(body="#C0392B", frame="#34495E", tire="#212121", rim="#95A5A6",
           plate="#2E86C1", rider="#1F3B63", fin="#16A085", float="#F4D03F")


# ---------------------------------------------------------------- 网格工具
def box(cx, cy, cz, sx, sy, sz):
    x = np.array([-0.5, 0.5]) * sx + cx
    y = np.array([-0.5, 0.5]) * sy + cy
    z = np.array([-0.5, 0.5]) * sz + cz
    v = np.array([[x[i], y[j], z[k]] for i in range(2) for j in range(2)
                  for k in range(2)])
    f = np.array([[0, 1, 3, 2], [4, 5, 7, 6], [0, 1, 5, 4],
                  [2, 3, 7, 6], [0, 2, 6, 4], [1, 3, 7, 5]])
    return v, f


def cylinder(cx, cy, cz, r, w, axis="y", n=14, r2=None):
    r2 = r if r2 is None else r2
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    pts = []
    for yy, rr in ((-w / 2, r), (w / 2, r2)):
        for t in th:
            if axis == "y":
                pts.append([cx + rr * math.cos(t), cy + yy, cz + rr * math.sin(t)])
            else:
                pts.append([cx + rr * math.cos(t), cy + rr * math.sin(t), cz + yy])
    v = np.array(pts)
    f = []
    for i in range(n):
        j = (i + 1) % n
        f.append([i, j, n + j, n + i])
    f.append(list(range(n))[::-1])
    f.append([n + i for i in range(n)])
    return v, f


def plate(x0, x1, y_half, z0, thick=0.018, rocker=0.06, n=10, m=3,
          inc_deg=0.0):
    """带艏部上翘（rocker）与安装角的板。"""
    xs = np.linspace(x0, x1, n)
    ys = np.linspace(-y_half, y_half, m)
    v = []
    for zz in (0.0, -thick):
        for x in xs:
            t = (x - x0) / max(x1 - x0, 1e-6)
            zr = rocker * t ** 2 + math.tan(math.radians(inc_deg)) * (x - x0)
            for y in ys:
                v.append([x, y, z0 + zr + zz])
    v = np.array(v)
    f = []
    for i in range(n - 1):
        for j in range(m - 1):
            a = i * m + j
            f.append([a, a + 1, a + m + 1, a + m])
    off = n * m
    for i in range(n - 1):
        for j in range(m - 1):
            a = off + i * m + j
            f.append([a, a + m, a + m + 1, a + 1])
    return v, f


def merge(parts):
    """faces 用 list（允许变长多边形）。"""
    vs, fs, cs = [], [], []
    off = 0
    for v, f, col in parts:
        vs.append(v)
        for face in f:
            fs.append(np.asarray(face) + off)
            cs.append(matplotlib.colors.to_rgb(col))
        off += len(v)
    return np.vstack(vs), fs, np.array(cs)


# ---------------------------------------------------------------- 整车
def build_bike(p=P0, front_inc=None, rear_inc=None):
    f_inc = p.delta_front_deg if front_inc is None else front_inc
    r_inc = p.delta_rear_deg if rear_inc is None else rear_inc
    parts = []
    # 车轮
    for x, r, w in ((p.x_rear, 0.36, 0.13),):
        parts.append((*cylinder(x, 0, -0.06, r, w, "y", 18), COL["tire"]))
        parts.append((*cylinder(x, 0, -0.06, r * 0.35, w * 1.05, "y", 12), COL["rim"]))
    # 车架：主梁 / 发动机 / 油箱 / 座垫 / 前叉 / 后摇臂
    parts.append((*box(0.00, 0, 0.10, 0.95, 0.13, 0.10), COL["frame"]))
    parts.append((*box(0.05, 0, -0.10, 0.42, 0.28, 0.30), COL["frame"]))
    parts.append((*box(0.30, 0, 0.24, 0.40, 0.26, 0.16), COL["body"]))
    parts.append((*box(-0.30, 0, 0.26, 0.55, 0.24, 0.10), COL["frame"]))
    # 前叉（斜置）
    for yy in (-0.07, 0.07):
        v, f = box(0, 0, 0, 0.05, 0.04, 0.52)
        v[:, 0] += 0.71 - 0.10
        v[:, 1] += yy
        v[:, 2] += 0.06
        ang = math.radians(-25)
        x, z = v[:, 0] - 0.61, v[:, 2] - 0.06
        v[:, 0] = 0.61 + x * math.cos(ang) - z * math.sin(ang)
        v[:, 2] = 0.06 + x * math.sin(ang) + z * math.cos(ang)
        parts.append((v, f, COL["rim"]))
    parts.append((*box(-0.45, 0, -0.02, 0.52, 0.06, 0.06), COL["frame"]))
    # 骑手
    parts.append((*box(-0.05, 0, 0.55, 0.26, 0.34, 0.46), COL["rider"]))
    parts.append((*cylinder(0.02, 0, 0.84, 0.11, 0.20, "z", 12), COL["rider"]))
    for yy in (-0.20, 0.20):
        parts.append((*box(0.22, yy, 0.50, 0.34, 0.07, 0.07), COL["rider"]))
        parts.append((*box(-0.06, yy, 0.22, 0.10, 0.12, 0.34), COL["rider"]))
    # 前转向橇（前轮换成橇）+ 立柱
    parts.append((*plate(p.x_front - 0.30, p.x_front + 0.62, p.b_front / 2,
                         -p.z_off_front, inc_deg=f_inc), COL["plate"]))
    parts.append((*box(p.x_front, 0, -p.z_off_front / 2, 0.05, 0.06,
                       p.z_off_front), COL["rim"]))
    # 后板
    parts.append((*plate(p.x_rear - 0.45, p.x_rear + 0.40, p.b_rear / 2,
                         -p.z_off_rear, inc_deg=r_inc), COL["plate"]))
    # 后板侧挡板（围板）
    for yy in (-1, 1):
        v, f = plate(p.x_rear - 0.42, p.x_rear + 0.35, 0.012,
                     -p.z_off_rear, thick=0.10, rocker=0.03, n=6, m=2)
        v[:, 1] += yy * (p.b_rear / 2)
        parts.append((v, f, COL["fin"]))
    # 尾鳍
    v, f = plate(p.x_rear - 0.55, p.x_rear - 0.20, 0.012, -p.z_off_rear + 0.02,
                 thick=0.16, rocker=0.0, n=4, m=2)
    parts.append((v, f, COL["fin"]))
    # 浮力体（两侧）
    for yy in (-1, 1):
        parts.append((*box(0.05, yy * 0.36, -0.05, 0.85, 0.13, 0.10),
                      COL["float"]))
    return merge(parts)


def shade(faces, verts, facecolors, light=(0.25, -0.55, 0.9)):
    idx = np.array([f[:3] for f in faces])
    v0 = verts[idx[:, 0]]
    v1 = verts[idx[:, 1]]
    v2 = verts[idx[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln < 1e-12] = 1
    n = n / ln
    L = np.array(light, dtype=float)
    L /= np.linalg.norm(L)
    lam = np.clip(n @ L, 0.0, 1.0)
    shade_f = 0.62 + 0.55 * lam
    return np.clip(facecolors * shade_f[:, None] + 0.06, 0, 1)


# ---------------------------------------------------------------- 场景
VIEW_16 = dict(xlim=(-3.6, 3.6), ylim=(-2.0, 2.0), zlim=(-0.95, 1.15),
                aspect=(2.6, 1.6, 1.05), elev=23, azim=-66)
VIEW_9 = dict(xlim=(-1.9, 1.9), ylim=(-1.3, 1.3), zlim=(-0.45, 1.15),
              aspect=(1.0, 1.2, 1.05), elev=17, azim=-64, zoom=1.25)


def draw_scene(ax, p, z, th, x_bike, wc, t, dist=9.0, elev=23, azim=-66,
               show_water=True, view=None):
    verts, faces, cols = build_bike(p)
    Rm = np.array([[math.cos(th), 0, -math.sin(th)],
                   [0, 1, 0],
                   [math.sin(th), 0, math.cos(th)]])
    vv = verts @ Rm.T + np.array([0.0, 0.0, z])
    fc = shade(faces, vv, cols)
    pc = Poly3DCollection([vv[f] for f in faces], facecolors=fc,
                          edgecolors="none", linewidths=0)
    ax.add_collection3d(pc)

    if show_water:
        span = (view or VIEW_16)["xlim"][1] * 2.0
        xs = np.linspace(-span, span, 57) + x_bike
        ys = np.linspace(-(view or VIEW_16)["ylim"][1] * 1.3,
                         (view or VIEW_16)["ylim"][1] * 1.3, 15)
        X, Y = np.meshgrid(xs, ys)
        E = np.array([[c.eta_at(wc, xx, t) for xx in xs] for _ in ys])
        ax.plot_surface(X - x_bike, Y, E, rstride=2, cstride=2,
                        facecolors=plt.cm.Blues(0.30 + 0.60 * (E - E.min())
                                                / max(E.ptp(), 1e-3)),
                        linewidth=0, antialiased=False, shade=False, alpha=0.66,
                        edgecolor="none")
    v = view or VIEW_16
    ax.set_xlim(*v["xlim"])
    ax.set_ylim(*v["ylim"])
    ax.set_zlim(*v["zlim"])
    ax.set_box_aspect(v["aspect"], zoom=v.get("zoom", 1.0))
    ax.view_init(elev=v["elev"], azim=v["azim"])
    ax.set_axis_off()


def fig_views():
    p = P0
    fig = plt.figure(figsize=(14, 5.2))
    views = [(16, -58, "(a) 等轴视图"), (4, -90, "(b) 侧视"), (8, -2, "(c) 前视")]
    verts, faces, cols = build_bike(p)
    for i, (elev, azim, title) in enumerate(views):
        ax = fig.add_subplot(1, 3, i + 1, projection="3d")
        fc = shade(faces, verts, cols)
        ax.add_collection3d(Poly3DCollection([verts[f] for f in faces],
                                             facecolors=fc, edgecolors="none"))
        ax.set_xlim(-1.2, 1.2)
        ax.set_ylim(-0.6, 0.6)
        ax.set_zlim(-0.6, 1.1)
        ax.set_box_aspect((2.4, 1.2, 1.7))
        ax.view_init(elev=elev, azim=azim)
        ax.set_axis_off()
        ax.set_title(title, fontsize=13, color="#1F3B63")
    fig.suptitle("参数化三维模型：前板 %.2f m×%.2f m（安装角 %.1f°）、"
                 "后板 %.2f m×%.2f m（%.1f°）、轮底偏置 %.1f cm"
                 % (p.l_front, p.b_front, p.delta_front_deg,
                    p.l_rear, p.b_rear, p.delta_rear_deg, p.h_wheel_gap * 100),
                 fontsize=12, color="#1F3B63", y=0.98)
    fig.savefig(FIGS / "fig6_3d_views.png", dpi=220, bbox_inches="tight",
                facecolor="#FBFBF9")
    print("[fig]", FIGS / "fig6_3d_views.png")


def fig_sequence():
    """同一时刻，基线 vs 改进方案的姿态对比。"""
    p_base = P0
    p_new = p_base.with_(b_front=0.38, delta_front_deg=5.2, b_rear=0.37,
                         delta_rear_deg=-1.6, h_wheel_gap=0.032)
    sims = []
    for pp in (p_base, p_new):
        o = c.simulate(21.23, pp, Hs=1.0, Tp=5.5, t_end=20.0, dt=0.004,
                       speed_hold=False, throttle=1.0, fixed_speed=True,
                       record_every=5, t_warm=2.0)
        sims.append(o)
    wc = sims[0]["wc"]
    # 取"两车后轮浸深差最大"的 4 个时刻，而不是等间隔 —— 否则两排看起来一样
    t_common = sims[0]["t"]
    n = min(len(t_common), len(sims[1]["t"]))
    d = np.abs(sims[0]["hw"][:n] - sims[1]["hw"][:n])
    order = np.argsort(d)[::-1]
    picked = []
    for k in order:
        tt = float(t_common[k])
        if tt < 5.0:
            continue
        if all(abs(tt - q) > 1.2 for q in picked):
            picked.append(tt)
        if len(picked) == 4:
            break
    ts = sorted(picked)
    fig = plt.figure(figsize=(14, 8.4))
    for j, tt in enumerate(ts):
        for i, (o, pp, lab) in enumerate(zip(sims, (p_base, p_new),
                                             ("现役", "方案 C"))):
            ax = fig.add_subplot(2, 4, i * 4 + j + 1, projection="3d")
            k = int(np.argmin(np.abs(o["t"] - tt)))
            draw_scene(ax, pp, o["z"][k], o["theta"][k], o["x"][k], wc,
                       o["t"][k])
            ax.text2D(0.02, 0.92, f"{lab}  t={o['t'][k]:.1f}s", transform=ax.transAxes,
                      fontsize=9.5, color="#1F3B63")
            ax.text2D(0.02, 0.05,
                      f"后轮浸深 {o['hw'][k]*100:+.1f} cm",
                      transform=ax.transAxes, fontsize=9,
                      color="#C0392B" if o["hw"][k] < 0.005 else "#1E8449")
    fig.suptitle("过浪四连拍（$H_s$=1.0 m）：姿态由时域解驱动，不是手工 K 帧",
                 fontsize=13, color="#1F3B63")
    fig.savefig(FIGS / "fig7_3d_sequence.png", dpi=190, bbox_inches="tight",
                facecolor="#FBFBF9")
    print("[fig]", FIGS / "fig7_3d_sequence.png")


def movie(nframe=300, fps=15, out=None, portrait=False):
    p = P0
    o = c.simulate(21.23, p, Hs=1.0, Tp=5.5, t_end=22.0, dt=0.004,
                   speed_hold=False, throttle=1.0, fixed_speed=True,
                   record_every=5, t_warm=2.0)
    wc = o["wc"]
    tmp = EP / "_logs" / "_3d"
    tmp.mkdir(parents=True, exist_ok=True)
    for f in tmp.glob("*.png"):
        f.unlink()
    t0 = 3.0
    for i in range(nframe):
        tt = t0 + i / fps
        k = int(np.argmin(np.abs(o["t"] - tt)))
        fig = plt.figure(figsize=(7.2, 12.8) if portrait else (9.6, 5.4))
        ax = fig.add_subplot(111, projection="3d")
        draw_scene(ax, p, o["z"][k], o["theta"][k], o["x"][k], wc, o["t"][k],
                   view=VIEW_9 if portrait else VIEW_16)
        hw = o["hw"][k] * 100
        fs1, fs2 = (22, 21) if portrait else (12, 11)
        if portrait:
            fig.text(0.07, 0.955, f"$H_s$=1.0 m   V={o['V'][k]*3.6:.0f} km/h",
                     fontsize=fs1, color="#1F3B63")
            fig.text(0.07, 0.915,
                     f"后轮浸深 {hw:+.1f} cm   " +
                     ("推力在线" if hw > 0.3 else "★ 桨轮脱水"),
                     fontsize=fs2,
                     color="#1E8449" if hw > 0.3 else "#C0392B")
            fig.text(0.07, 0.06, f"t = {o['t'][k]:5.2f} s",
                     fontsize=fs1 - 2, color="#7F8C8D")
        else:
            ax.text2D(0.02, 0.93, f"$H_s$=1.0 m   V={o['V'][k]*3.6:.0f} km/h",
                      transform=ax.transAxes, fontsize=fs1, color="#1F3B63")
            ax.text2D(0.02, 0.86,
                      f"后轮浸深 {hw:+.1f} cm   " +
                      ("推力在线" if hw > 0.3 else "★ 桨轮脱水"),
                      transform=ax.transAxes, fontsize=fs2,
                      color="#1E8449" if hw > 0.3 else "#C0392B")
            ax.text2D(0.02, 0.06, f"t = {o['t'][k]:5.2f} s",
                      transform=ax.transAxes, fontsize=fs1 - 2, color="#7F8C8D")
        fig.subplots_adjust(0, 0, 1, 1)
        fig.savefig(tmp / f"f_{i:04d}.png", dpi=150 if portrait else 110,
                    facecolor="#FBFBF9")
        plt.close(fig)
        if i % 30 == 0:
            print(f"  frame {i}/{nframe}", flush=True)
    out = out or (FIGS / "w58_wave3d.mp4")
    cmd = ["ffmpeg", "-y", "-framerate", str(fps), "-i", str(tmp / "f_%04d.png"),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(out)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    print("[mp4]", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--views", action="store_true")
    ap.add_argument("--seq", action="store_true")
    ap.add_argument("--movie", action="store_true")
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--portrait", action="store_true")
    ap.add_argument("--out", default=None, help="输出 mp4 路径（默认 results/figs/w58_wave3d.mp4）")
    ap.add_argument("--fps", type=int, default=15)
    a = ap.parse_args()
    if not (a.views or a.seq or a.movie):
        a.views = a.seq = a.movie = True
    if a.views:
        fig_views()
    if a.seq:
        fig_sequence()
    if a.movie:
        movie(nframe=a.frames, fps=a.fps, portrait=a.portrait,
              out=Path(a.out) if a.out else None)
