#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **演示① 3D 版**：静止起步 → 内侧爬环 → 顶部脱轨 → 左飞 → 滚转翻正 → 落地。

## 与 2D 版的差别

2D 侧视图只能看轨迹；**滚转在侧视图里看不见**。
3D 版把**俯仰（沿环）**与**滚转（空中翻正）**都画出来。

## 姿态分解（两轴）

$$R=R_x(\theta_{\text{roll}})\,R_y(\phi_{\text{pitch}})$$

* **爬环**：$\phi$ 从 0 转到 $\pi$（机头沿轨道切线，车顶朝圆心）；
* **空中**：$\phi$ 保持 $\pi$（倒挂），$\theta_{\text{roll}}$ 从 0 转到 $\pi$ ⇒ 车顶翻回朝上，
  **机头仍朝 $-x$**（向左飞）。

$$\text{俯仰 }180°\text{ 会反转机头；滚转 }180°\text{ 只翻车顶}\Rightarrow\text{用滚转}$$
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
from matplotlib.animation import FuncAnimation, FFMpegWriter  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph          # noqa: E402
import car3d as c3            # noqa: E402
import nozzle_state as ns     # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W55"
OUT = EP / "publish" / "视频"
FIG = EP / "results" / "figs"

M, G = ph.M_CAR, ph.G
R, LAM = 10.5, 2.0
H_TOP = 2 * R
V_MIN_NOFAN = math.sqrt(G * R)   # ★ 无风扇所需的最低车速（不是上限）
V_TOP = 9.34                     # 采用车速（自定，低于 V_MIN_NOFAN ⇒ 须靠吸附）
A_UP = 3.0
V_TOUCH = 0.5
F_TOT = ph.FZ_MAX
J_R = ph.J_ROLL
T_ROT = 1.70
PWM_MIN_ON = 0.012     # ★ MIB：阀门最小开通 12 ms
W, H = 17.0, 9.6
TRACK_W = 7.0          # 赛道宽度 m
N_SEG_TRACK = 60


# ---------------- 姿态：俯仰 + 滚转 ----------------
def rot_mat(pitch: float, roll: float):
    r"""$R=R_x(\theta)R_y(\phi)$ 的 3×3。"""
    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)
    # Ry
    Ry = [[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]]
    # Rx
    Rx = [[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]]
    return [[sum(Rx[i][k] * Ry[k][j] for k in range(3)) for j in range(3)]
            for i in range(3)]


def apply(Rm, v):
    return (sum(Rm[0][j] * v[j] for j in range(3)),
            sum(Rm[1][j] * v[j] for j in range(3)),
            sum(Rm[2][j] * v[j] for j in range(3)))


def box_faces(cx, cy, cz, Lx, Wx, Hx, col, ctr, Rm):
    hx, hy, hz = Lx / 2, Wx / 2, Hx / 2
    P = {}
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                d = apply(Rm, (sx * hx, sy * hy, sz * hz))
                P[(sx, sy, sz)] = (cx + d[0], cy + d[1], cz + d[2])
    quads = [
        [(-1, -1, -1), (-1, 1, -1), (-1, 1, 1), (-1, -1, 1)],
        [(1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1)],
        [(-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)],
        [(-1, 1, -1), (1, 1, -1), (1, 1, 1), (-1, 1, 1)],
        [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1)],
        [(-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)],
    ]
    return [([P[k] for k in q], col, ctr) for q in quads]


def car_faces(x0, z0, pitch, roll):
    Rm = rot_mat(pitch, roll)
    cx0 = x0
    cz0 = z0 + c3.BODY_LIFT
    faces = []
    for (_n, Lx, Wx, Hx, ox, oy, oz, col) in c3.CAR_PARTS:
        d = apply(Rm, (ox, oy, oz))
        c = (cx0 + d[0], d[1], cz0 + d[2])
        faces += box_faces(c[0], c[1], c[2], Lx, Wx, Hx, col, c, Rm)
    for (wx, wy) in ((c3.X_AXLE, -c3.Y_TRACK), (c3.X_AXLE, c3.Y_TRACK),
                     (-c3.X_AXLE, -c3.Y_TRACK), (-c3.X_AXLE, c3.Y_TRACK)):
        d = apply(Rm, (wx, wy, c3.R_WHEEL - c3.BODY_LIFT))
        c = (cx0 + d[0], d[1], cz0 + d[2])
        ra, rb = [], []
        for k in range(c3.N_SEG):
            a = 2 * math.pi * k / c3.N_SEG
            dx = c3.R_WHEEL * math.cos(a)
            dz = c3.R_WHEEL * math.sin(a)
            pa = apply(Rm, (dx, -c3.W_WHEEL / 2, dz))
            pb = apply(Rm, (dx, c3.W_WHEEL / 2, dz))
            ra.append((c[0] + pa[0], c[1] + pa[1], c[2] + pa[2]))
            rb.append((c[0] + pb[0], c[1] + pb[1], c[2] + pb[2]))
        for k in range(c3.N_SEG):
            m2 = (k + 1) % c3.N_SEG
            faces.append(([ra[k], ra[m2], rb[m2], rb[k]], c3.WHEEL_COL, c))
        faces.append((list(ra), c3.WHEEL_CAP, c))
        faces.append((list(rb), c3.WHEEL_CAP, c))
    return faces


def render(ax, st, trail):
    ax.clear()
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_facecolor("#16202f")
    # ★★ 固定机位：一开场就能看到**完整右半环 + 地面**
    eye = (20.0, -27.0, 13.0)
    tgt = (1.5, 0.0, 9.5)
    cam = c3.make_cam(eye, tgt)
    focal = min(W, H) * 1.05
    cx, cy = W * 0.52, H * 0.56

    # ★★ 地面：投影一张大四边形 + 网格（不再是屏幕空间填充）
    gq = [c3.project(cam, p, focal, cx, cy) for p in
          ((-34, -22, 0), (26, -22, 0), (26, 22, 0), (-34, 22, 0))]
    if all(p is not None for p in gq):
        ax.add_patch(Polygon([(p[0], p[1]) for p in gq], closed=True,
                             fc="#1a2333", ec="none", zorder=0))
        for gx in range(-34, 28, 6):
            a = c3.project(cam, (gx, -22, 0), focal, cx, cy)
            b = c3.project(cam, (gx, 22, 0), focal, cx, cy)
            if a and b:
                ax.plot([a[0], b[0]], [a[1], b[1]], color="#26344a",
                        lw=0.6, zorder=0)
        for gy in range(-22, 24, 6):
            a = c3.project(cam, (-34, gy, 0), focal, cx, cy)
            b = c3.project(cam, (26, gy, 0), focal, cx, cy)
            if a and b:
                ax.plot([a[0], b[0]], [a[1], b[1]], color="#26344a",
                        lw=0.6, zorder=0)
    # ★★ 圆环做成**有宽度的 3D 条带**（赛道宽 TRACK_W）
    hw = TRACK_W / 2.0
    band, band_d = [], []
    for i in range(0, N_SEG_TRACK):
        a0 = math.pi * i / N_SEG_TRACK
        a1 = math.pi * (i + 1) / N_SEG_TRACK
        quad_w = []
        ok = True
        for a in (a0, a1):
            for sy in (-hw, +hw):
                p = c3.project(cam,
                               (R * math.sin(a), sy, R * (1 + math.cos(a))),
                               focal, cx, cy)
                if p is None:
                    ok = False
                    break
                quad_w.append(p)
            if not ok:
                break
        if not ok or len(quad_w) != 4:
            continue
        # quad_w 顺序：a0-left, a0-right, a1-left, a1-right
        poly = [(quad_w[0][0], quad_w[0][1]), (quad_w[1][0], quad_w[1][1]),
                (quad_w[3][0], quad_w[3][1]), (quad_w[2][0], quad_w[2][1])]
        band.append(poly)
        band_d.append(sum(p[2] for p in quad_w) / 4)
    order = sorted(range(len(band)), key=lambda i: -band_d[i])
    if band:
        ax.add_collection(PolyCollection(
            [band[i] for i in order],
            facecolors="#2b3a52", edgecolors="none", linewidths=0, zorder=1))
    if len(trail) > 1:
        ax.plot([p[0] for p in trail], [p[1] for p in trail],
                color="#38bdf8", lw=1.4, alpha=.5, zorder=1)
    Lg = c3.vnorm(c3.LIGHT)
    items = []
    for (vs, col, ctr) in car_faces(st["x"], st["z"], st["pitch"], st["roll"]):
        pr = [c3.project(cam, p, focal, cx, cy) for p in vs]
        if any(p is None for p in pr):
            continue
        depth = sum(p[2] for p in pr) / len(pr)
        nrm = c3.vnorm(c3.vcross(c3.vsub(vs[1], vs[0]), c3.vsub(vs[2], vs[0])))
        mid = tuple(sum(p[i] for p in vs) / len(vs) for i in range(3))
        if c3.vdot(nrm, c3.vsub(mid, ctr)) < 0:
            nrm = (-nrm[0], -nrm[1], -nrm[2])
        if c3.vdot(nrm, c3.vnorm(c3.vsub(cam[0], mid))) <= 1e-4:
            continue
        k = 0.36 + 0.64 * max(0.0, c3.vdot(nrm, Lg))
        items.append(([(p[0], p[1]) for p in pr],
                      (col[0] * k / 255, col[1] * k / 255, col[2] * k / 255),
                      depth))
    items.sort(key=lambda t: -t[2])
    if items:
        ax.add_collection(PolyCollection(
            [t[0] for t in items], facecolors=[t[1] for t in items],
            edgecolors=(0.06, 0.09, 0.16, 0.5), linewidths=0.35, zorder=3))

    # ★★ 喷口羽流：从每个点火喷口的**实际位置**沿排气方向画箭头
    dnow = st.get("duty") or {}
    if dnow:
        Rm = rot_mat(st["pitch"], st["roll"])
        base = {"+X": (1, 0, 0), "-X": (-1, 0, 0), "+Z": (0, 0, 1),
                "-Z": (0, 0, -1), "+Y": (0, 1, 0), "-Y": (0, -1, 0)}
        for m in ns.NOZZLE_META:
            v = dnow.get(m["name"], 0.0)
            if v <= 0.01:
                continue
            ub = base[m["axis"]]
            uw = apply(Rm, ub)                 # 推力方向（世界）
            pb = (m["pos"][0], m["pos"][1], m["pos2_z"])
            pw = apply(Rm, pb)
            p0w = (st["x"] + pw[0], pw[1], st["z"] + c3.BODY_LIFT + pw[2])
            L = 2.4 + 5.6 * min(1.0, v)        # ★ 加长，更醒目
            p1w = (p0w[0] - uw[0] * L, p0w[1] - uw[1] * L,
                   p0w[2] - uw[2] * L)
            a0 = c3.project(cam, p0w, focal, cx, cy)
            a1 = c3.project(cam, p1w, focal, cx, cy)
            if a0 and a1:
                xs, ys = [a0[0], a1[0]], [a0[1], a1[1]]
                # ★ 四层辉光：外晕 -> 中层 -> 本体 -> 白芯
                ax.plot(xs, ys, color=m["color"], lw=15, alpha=.16,
                        solid_capstyle="round", zorder=4)
                ax.plot(xs, ys, color=m["color"], lw=9, alpha=.34,
                        solid_capstyle="round", zorder=4)
                ax.plot(xs, ys, color=m["color"], lw=4.6, alpha=.72,
                        solid_capstyle="round", zorder=5)
                ax.plot(xs, ys, color="#ffffff", lw=1.7, alpha=.95,
                        solid_capstyle="round", zorder=6)
                ax.plot([a0[0]], [a0[1]], marker="o", ms=11,
                        mfc=m["color"], mec="#ffffff", mew=0.8,
                        alpha=.85, zorder=6)

    ax.text(W / 2, 0.55,
            f"{st['lab']}   t={st['t']:.2f}s  z={st['z']:.1f}m  "
            f"俯仰 {math.degrees(st['pitch']):.0f}°  "
            f"滚转 {math.degrees(st['roll']):.0f}°",
            ha="center", fontsize=12, color=st["col"], weight="bold")


def seq(dt=1.0 / 200):
    # ★★★ PFM（脉冲频率调制）+ MIB：与"飞跃五车"同一套做法
    #   冷气推力器只能开关 ⇒ 用"攒够一个最小脉宽就点火一次"代替半推力。
    pwm_acc = {}
    pwm_left = {}

    def _pfm(ch, d, dtp, t_now):
        r"""返回该通道本步是否**真正点火**（点火则满推力）。"""
        if d <= 1e-9:
            return False
        pwm_acc[ch] = pwm_acc.get(ch, 0.0) + d * dtp
        n = max(1, int(round(PWM_MIN_ON / dtp)))
        if pwm_left.get(ch, 0) <= 0 and pwm_acc[ch] >= n * dtp:
            pwm_left[ch] = n
            pwm_acc[ch] -= n * dtp
        on = pwm_left.get(ch, 0) > 0
        if on:
            pwm_left[ch] -= 1
        return on

    out = []
    t, s, v = 0.0, 0.0, 0.0
    th = math.pi
    while th > 1e-9:
        a = A_UP if v < V_TOP else 0.0
        v = min(V_TOP, v + a * dt)
        s += v * dt
        th = max(0.0, math.pi - s / R)
        t += dt
        out.append(dict(t=t, x=R * math.sin(th), z=R * (1 + math.cos(th)),
                        pitch=th - math.pi, roll=0.0, duty={}, fan=th / math.pi,
                        vz=v * math.sin(th), ph="climb",
                        lab="爬环（车顶朝圆心）", col="#38bdf8"))
        if th <= 1e-9:
            break
    x, z, vx, vz = 0.0, H_TOP, -V_TOP, 0.0
    pitch, roll, om = math.pi, 0.0, 0.0
    alpha = 4 * math.pi / (T_ROT ** 2)
    a_max = F_TOT / M - G
    z_trig = None
    for _ in range(200000):
        if z <= (vz ** 2 / (2 * a_max)) * 1.35:
            z_trig = z
            break
        acc = 0.0 if roll >= math.pi else (alpha if t -
                                          (out[-1]["t"]) < T_ROT else -alpha)
        om += acc * dt
        roll = min(math.pi, roll + om * dt)
        vz -= G * dt
        z += vz * dt
        x += vx * dt
        t += dt
        dcz = 0.32 if roll < math.pi - 1e-9 else 0.0
        # ★★★ C 方案：侧推配平。同侧两喷的合力 2F 在车体 +z，
        #     车滚转后其世界横向分量 = 2F·sinθ；侧推 F_s 提供 F_s·cosθ，
        #     ⇒ F_s = 2F·tanθ（限幅 SIDE_MAX，θ→90° 发散是固有缺陷）。
        F_pair = 0.32 * 20e3
        cth_r, sth_r = math.cos(roll), math.sin(roll)
        if abs(cth_r) > 0.15:
            fs = 2.0 * F_pair * sth_r / cth_r
        else:
            fs = 2.0 * F_pair * (1.0 if sth_r > 0 else -1.0)
        fs = max(-8.0e3, min(8.0e3, fs))
        side_nm = "SIDE_P" if fs > 0 else "SIDE_N"
        side_dc = min(1.0, abs(fs) / 8.0e3) if abs(fs) > 200 else 0.0
        pair_on = _pfm("lift", dcz, dt, t)
        side_on = _pfm("side", side_dc, dt, t)
        _d = {}
        if pair_on:
            _d["LIFT_FL"] = 1.0
            _d["LIFT_RL"] = 1.0
        if side_on:
            _d[side_nm] = 1.0
        out.append(dict(t=t, x=x, z=z, vz=vz, pitch=pitch, roll=roll,
                        duty=_d, fan=0.0, ph="air",
                        lab="左飞 + 滚转翻正", col="#ef4444"))
        if z <= 0.3:
            z_trig = z
            break
    while z > 0.0:
        if abs(vz) <= V_TOUCH:
            F = M * G
        else:
            F = min(F_TOT, M * (G + max(0.0, (vz ** 2 - V_TOUCH ** 2)
                                        / (2 * max(z, 1e-6)))))
        vz += (F / M - G) * dt
        z += vz * dt
        x += vx * dt
        t += dt
        if z <= 0.02:
            z = 0.0
            break
        dcb = min(1.0, F / max(1.0, F_TOT))
        out.append(dict(t=t, x=x, z=z, vz=vz, pitch=pitch, roll=roll,
                        duty=({k: 1.0 for k in ("LIFT_FL", "LIFT_FR",
                                                "LIFT_RL", "LIFT_RR")}
                               if _pfm("lift", dcb, dt, t) else {}),
                        fan=0.0, ph="thr",
                        lab="缓冲", col="#22c55e"))
    out.append(dict(t=t, x=x, z=0.0, vz=vz, pitch=pitch, roll=math.pi, duty={}, fan=0.0, ph="land",
                    lab="落地（正立）", col="#a78bfa"))
    return out, z_trig


def nozzle_panel(ax, st):
    """底部 10 喷口状态条 + 风扇吸附指示。"""
    ax.clear()
    ax.set_xlim(0, 10.0)
    ax.set_ylim(0, 1.2)
    ax.axis("off")
    ax.set_facecolor("#0b1220")
    d = st.get("duty") or {}
    for k, m in enumerate(ns.NOZZLE_META):
        nm, v = m["name"], d.get(m["name"], 0.0)
        bx = k + 0.12
        ax.add_patch(plt.Rectangle((bx, .25), .76, .48,
                                   fc="#111827", ec="#334155", lw=.6))
        if v > 0.01:
            ax.add_patch(plt.Rectangle((bx, .25), .76, .48 * v,
                                       fc=m["color"], ec="none"))
        ax.text(bx + .38, .85, m["short"], ha="center", fontsize=6.5,
                color="#e2e8f0" if v > .01 else "#64748b")
        ax.text(bx + .38, .62, f"{v:.0f}" if v > .01 else "-",
                ha="center", fontsize=6.0,
                color=m["color"] if v > .01 else "#475569")
    ax.text(5.0, 1.05, f"风扇吸附 {st.get('fan', 0.0)*100:.0f}%",
            ha="center", fontsize=7, color="#38bdf8")


def cfg():
    cands = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
    have = {f.name for f in font_manager.fontManager.ttflist}
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = \
        ([c for c in cands if c in have] or ["DejaVu Sans"]) + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def main():
    cfg()
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    print("=" * 80)
    print("  演示① 3D：起步→内侧爬环→顶部脱轨→左飞→滚转翻正→落地")
    print("=" * 80)
    recs, z_trig = seq()
    print(f"\n  R={R:.1f} m，v_top={V_TOP:.2f} m/s，"
          f"滚转 180° 用 {T_ROT:.2f} s")
    print(f"  缓冲点火 z={z_trig:.2f} m")
    last = recs[-1]
    print(f"  落地：t={last['t']:.2f}s，vz={last['vz']:.3f} m/s，"
          f"x={last['x']:.1f} m，滚转={math.degrees(last['roll']):.0f}°")

    fig2 = plt.figure(figsize=(10.5, 7.6))
    ax2 = fig2.add_axes([0.01, 0.16, 0.98, 0.82])
    axp = fig2.add_axes([0.06, 0.01, 0.88, 0.10])
    fig2.patch.set_facecolor("#0b1220")
    step = max(1, len(recs) // 220)
    frames = list(range(0, len(recs), step)) + [len(recs) - 1] * 25
    trail = []

    def upd(i):
        st = dict(recs[frames[i]])
        if st["z"] > 0.02:
            p = c3.project(c3.make_cam((st["x"] + 9.0, -15.0, st["z"] + 5.5),
                                       (st["x"] - 2.0, 0.0,
                                        max(1.0, st["z"] * 0.75 + 0.8))),
                           (st["x"], 0, st["z"]),
                           min(W, H) * 0.80, W * 0.5, H * 0.55)
            if p:
                trail.append((p[0], p[1]))
        render(ax2, st, trail)
        nozzle_panel(axp, st)
        return []

    anim = FuncAnimation(fig2, upd, frames=len(frames),
                         interval=1000 / 30, repeat=False)
    mp4 = OUT / "sim_demo1_3d.mp4"
    anim.save(str(mp4), writer=FFMpegWriter(fps=30, bitrate=3600))
    plt.close(fig2)
    print(f"\n  [OK] {mp4.name}  {mp4.stat().st_size/1e6:.2f} MB")

    # 关键帧图
    fig3, axs = plt.subplots(2, 3, figsize=(16.5, 9.4))
    fig3.patch.set_facecolor("#0b1220")
    keys = [0, len(recs) // 5, 2 * len(recs) // 5, 3 * len(recs) // 5,
            4 * len(recs) // 5, len(recs) - 1]
    for a, k in zip(axs.ravel(), keys):
        render(a, dict(recs[k]), [])
    fig3.tight_layout()
    png = FIG / "fig_demo1_3d_keyframes.png"
    fig3.savefig(png, facecolor="#0b1220", dpi=110, bbox_inches="tight")
    plt.close(fig3)
    print(f"  [OK] {png.name}  {png.stat().st_size/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
