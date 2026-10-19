#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **3D 动画 v3**：车身与 `sim.html` 同源（`car3d.py`）。

## 为什么重写（第一版）

`sim_anim3d_v2.py` 里同时躺着三套车身代码（`CAR_PARTS` / `car_meshes` /
`cm.car_mesh` 放样），**改一处不知道另外两处会不会失效**。
这一期已因"双重旋转 / 漏旋转"翻车两次。

**⇒ 车身几何与渲染全部收敛到 `car3d.py`，本脚本只负责"驱动动画"。**

## 2026-10-18 重做：**一段片子，两个镜头**

用户看 `_logs/抽帧核对/bili_s08_254500ms.png` 指出：车已落地（t=3.93 s，高度 0.00 m），
缓冲喷口在喷，**五台障碍车一台都看不见**。根因很简单：

$$\boxed{\text{镜头跟着车走，就必然丢掉"越过了什么"}}$$

落地时车在 $x\approx62$ m、车队在 $x\approx28$ m，差 34 m —— 跟车的机位
不可能同时框住两者。旧版 `camera_for` 的 `eye.x = fr.x-6` 是**满跟随**
（`follow=1.0`），所以越车段与落地段被同一个机位讲，两件事都讲不清。

**⇒ 拆成两个镜头（硬切），每段只讲一件事：**

| 段 | 内容 | 机位 | 占比 |
|---|---|---|---|
| **A** | 起步 → 起飞 → **越过五台车** → 最高点 | **侧视宽机位**（`follow=0.30`，缓慢平移）| ~60% |
| **B** | 下落 → 缓冲点火 → 落地 → 停住 | **后视推近**（`follow=0.95`），车 + 跑道中线同框 | ~40% |

三个必须记住的约束：

1. **`follow` 是分段常量**（A 段 0.30 / B 段 0.95），不是一条曲线跟到底。
2. **切换点是最高点之后的下落途中**（`T_CUT = 2.30 s`，最高点在 2.083 s），
   而且是**硬切**（不给渐变：渐变会把两个机位糊在一起）。
3. ★★ **A 段机位放在 $+y$ 侧（"镜像侧视"）**，让 $+x$ 显示在**屏幕左边**。
   理由：后视机位里车（$y\approx+0.9$）出现在中线**左侧**；A 段若从 $-y$ 侧看，
   车飞越后在画面**右侧**收尾 ⇒ 硬切时车会从 60% 跳到 40%（约 300 px 的跳感）。
   镜像之后两边都在左侧，实测切换点跳变只有 **Δx≈-5%、Δy≈+1%**。

## 与 HTML 的关系

| 项 | `sim.html` | 本脚本 |
|---|---|---|
| 车身 | `CAR_PARTS`（8 个盒 + 4 圆柱轮）| **同一个 `car3d.CAR_PARTS`** |
| 相机 | `eye=(-6.0,-11.5,+5.2)`、`focal=0.95·min(w,h)` | 透视与焦距同源，机位按 A/B 分段 |
| 剔除/着色 | 背面剔除 + Lambert | **同** |
| 地面 | 地平线以下填带 | **同** |

## 用法

    # 屏 02 用（10.9333 s = 328 帧，与 splice 窗口 328 帧一一对应）
    $PY scripts/sim_anim3d_v3.py --dur 10.9333 --out sim_jump_3d.mp4
    # 屏 08 用（9.4 s = 282 帧）
    $PY scripts/sim_anim3d_v3.py --dur 9.4 --out sim_jump_3d_s08.mp4
    # 只打印机位几何、不出片（几秒）
    $PY scripts/sim_anim3d_v3.py --probe
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.animation import FuncAnimation, FFMpegWriter  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402
from matplotlib.patches import Polygon, Circle  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph          # noqa: E402
import nozzle_state as ns     # noqa: E402
import car3d as c3            # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W55"
OUT = EP / "publish" / "视频"
FIG = EP / "results" / "figs"

# 视口单位。**宽高比与画布上的坐标轴框一致**（12.74 : 6.56 in），
# 否则 `set_aspect("equal")` 会在轴内留出同色空白，画面内容变窄 12%
# （W55 实测：旧值 16×9.2 时仿真内容只占 1300 px 画布的 1141 px）。
VIEW_W, VIEW_H = 16.0, 9.2

FIG_W, FIG_H, DPI = 13.0, 8.0, 100
AX_RECT = [0.01, 0.13, 0.98, 0.82]

# ==================== 镜头：A / B 两段（分段常量 follow）====================

STATE = {"stage": "A", "close": False}   # 每帧由主循环改写
RULER_ON = False                # B 段才画地面刻度尺

# A 段：**3/4 斜侧视**（2026-10-19 改；用户否掉了"正侧视宽机位"）
#
# 用户对上一版的判词：车宽只占约 9% 画宽、车在顶部车队在底部、中间约 40% 空。
# 根因是**正侧视**把 22.8 m 的车队平铺在画宽上 ⇒ 焦距被车队逼小。
#
# 改成 $\beta=40^\circ$ 的斜侧视后车队沿透视方向铺开，但"五台车 100% 在画内"
# 仍是一条**硬**约束（`--probe` 判据 ①），而 A 段起点车在 x=0、车队远到 x=39.4
# （跨度 39.4 m）。若全程固定焦距，这个跨度决定焦距上界 ⇒ 峰值帧车仍然只有
# 11% 左右。**⇒ 焦距按帧自算**（机位不动、只推镜），见 `_a_span()`。
#
# 参数含义（q34 模式）：
#   az/pitch  —— 视线方位角（与跑道 +x 轴）与俯角；az 必须落在 35°–45°
#   R         —— 相机到"目标点"的距离（决定透视强度，不影响构图大小）
#   ax/ay/az  —— 目标点相对 `base` 的偏移
#   follow    —— 机位沿 x 的平移比例（0=不动，1=完全跟车）
#   fk        —— 每帧焦距 = fk × 该帧构图上界（<1 留边）
#   pan       —— (cx, cy)，由 `solve_A_pan()` 解出，见下
A_CAM = dict(mode="q34", az=44.0, pitch=10.0, R=34.0,
             ax=0.0, ay=0.0, atz=1.0, follow=0.60, fk=0.985, pan=None)

# B 段：后视**推近**（焦距随高度推：`fk0` 高空 → `fk` 贴地）。
#
# 为什么不把机位怼近：切换点车还在 9.9 m 高空，机位若在车后 6.6 m，车的**尾端**
# 离镜头只有 4.7 m ⇒ 车占画宽 40%、上下被切，硬切时车从 36% 跳到 23%。
# 退到 12 m + 焦距随高度从 1.6 推到 3.2 之后：切换点车宽 16.8%（A 段 11%，
# 尺寸不跳），位置 (40.0%, 31.6%) vs A 段 (36.5%, 31.8%) ⇒ **Δ=(+3.5%, −0.2%)**；
# 落地帧偏移 **13.05% 画宽**（占成片 10.5%）。
# `ey=+0.3` 是**纯构图平移**（相机沿 y 挪 30 cm）：只左右挪画面，不改"车—中线"距离。
B_CAM = dict(follow=0.95, D=12.0, tf=1.4, h0=4.6, az=0.45, tz0=1.2, bz=0.85,
             fk=3.20, fk0=1.60, zref=9.93, ey=+0.30)

T_CUT = 2.30                    # 硬切时刻（最高点 2.083 s 之后的下落途中）
A_RATIO = 0.60                  # A 段占"运动帧"的比例
HOLD = 1.0                      # 落地后停留（秒）

# 跑道几何（米）。**所有线都走 c3.project()**，不用屏幕坐标硬画。
LANE_HALF = 3.5          # 车道边界 y=±3.5
GRID_STEP = 5.0          # 横向刻线间距（5 m 一格 ⇒ 透视收缩看得出来）
X_BACK, X_FWD = 26.0, 46.0
RULER_HALF = 4.0         # 落地刻度尺半宽（m）
RULER_STEP = 0.25        # 每格 0.25 m
DASH_ON, DASH_OFF = 4.0, 3.0   # 中线虚线：4 m 实、3 m 空


def setup() -> None:
    cands = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
    have = {f.name for f in font_manager.fontManager.ttflist}
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = \
        ([c for c in cands if c in have] or ["DejaVu Sans"]) + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


# ==================== 相机（A/B 分段）====================

# 车体局部包围盒 8 角（**从 `car3d.car_faces` 抽，不手抄**）。
_CAR0 = c3.car_faces(0.0, 0.0, 0.0)
_C0 = [v for (vs, _c, _ctr) in _CAR0 for v in vs]
CAR_BB_LOCAL = [(x, y, z)
                for x in (min(p[0] for p in _C0), max(p[0] for p in _C0))
                for y in (min(p[1] for p in _C0), max(p[1] for p in _C0))
                for z in (min(p[2] for p in _C0), max(p[2] for p in _C0))]

ROW_CORNERS = [(x, y, z)
               for (_dx, _L, _Hx, _c) in c3.OBSTACLES
               for x in (c3.ROW_X + _dx - _L / 2, c3.ROW_X + _dx + _L / 2)
               for y in (-1.0, 1.0) for z in (0.0, _Hx)]


def car_corners(fr) -> list:
    r"""车体**真实轮廓**的全部顶点（与 `collect_drawables` 同一份 `car_faces`）。

    ⚠️ 不要用"轴对齐包围盒的 8 角"当内容边界：车在峰值处已滚转 −244°，
    8 角盒比真实轮廓**大一圈**，会把焦距压小 —— 实测同机位下
    车宽从 9.3% 掉到 ~7%（白扔 20% 画面）。
    ⇐ 判据 ② 是"车宽占画宽"，边界必须**紧**，否则等于自己放弃画幅。
    """
    return [v for (vs, _c, _ctr) in
            c3.car_faces(fr.x, fr.z, fr.theta, fr.y) for v in vs]


def content_uv(fr, cam):
    r"""本帧**构图内容**（五车 + 车）的 $(u,v)$ 极值 **与车心** $(\bar u,\bar v)$。

    $$u=\frac{\hat r\cdot(P-E)}{\hat f\cdot(P-E)},\qquad
      v=\frac{\hat u\cdot(P-E)}{\hat f\cdot(P-E)},\qquad
      s_x=c_x+Fu,\;\; s_y=c_y-Fv$$

    ⚠️ 车心用**真实轮廓顶点的均值**（`car_corners` 已改成真实轮廓）。
    """
    eye, fv, rv, uv_ = cam

    def _uv(p):
        d = c3.vsub(p, eye)
        z = c3.vdot(d, fv)
        if z < 0.12:
            return None
        return (c3.vdot(d, rv) / z, c3.vdot(d, uv_) / z)

    cq = [q for q in (_uv(p) for p in car_corners(fr)) if q]
    rq = [q for q in (_uv(p) for p in ROW_CORNERS) if q]
    qs = cq + rq
    if not qs or not cq:
        return None
    uc = sum(q[0] for q in cq) / len(cq)
    vc = sum(q[1] for q in cq) / len(cq)
    return ((min(q[0] for q in qs), max(q[0] for q in qs),
             min(q[1] for q in qs), max(q[1] for q in qs)), (uc, vc))


def _a_eye(P, base):
    b, p = math.radians(P["az"]), math.radians(P["pitch"])
    d = (math.cos(p) * math.cos(b), -math.cos(p) * math.sin(b), -math.sin(p))
    aim = (base + P["ax"], P["ay"], P["atz"])
    return (aim[0] - P["R"] * d[0], aim[1] - P["R"] * d[1],
            aim[2] - P["R"] * d[2]), (base + P["ax"], P["ay"], P["atz"])


def a_focal_bound(bb, uc, vc, w, h,
                  cut_pct: tuple[float, float] = (40.0, 31.6)) -> float:
    r"""**闭式**焦距上界（不要迭代！）。

    平移由硬切约束**代数地**给出：$c_x=a-F\bar u,\; c_y=b+F\bar v$
    （$a=0.40w,\;b=0.316h$）。代入 $s_x=c_x+Fu\in[0,w]$、$s_y=c_y-Fv\in[0,h]$：

    $$F\le\frac{w-a}{u_{\max}-\bar u},\quad
      F\le\frac{a}{\bar u-u_{\min}},\quad
      F\le\frac{b}{v_{\max}-\bar v},\quad
      F\le\frac{h-b}{\bar v-v_{\min}}$$

    ⚠️ **不能**把它写成"先定 $c_x,c_y$ 再算上界"的不动点迭代 ——
    实测会发散（$c_x=6.4-F\bar u$ 与上界里的 $(w-c_x)$ 互相喂正反馈，
    第一次改成真实轮廓后就炸到 $10^{31}$）。⇒ 必须用上面这个闭式。
    """
    umin, umax, vmin, vmax = bb
    a, b = cut_pct[0] / 100 * w, cut_pct[1] / 100 * h
    out = 1e18
    if umax - uc > 1e-9:
        out = min(out, (w - a) / (umax - uc))
    if uc - umin > 1e-9:
        out = min(out, a / (uc - umin))
    if vmax - vc > 1e-9:
        out = min(out, b / (vmax - vc))
    if vc - vmin > 1e-9:
        out = min(out, (h - b) / (vc - vmin))
    return out


def solve_A_pan(pa: dict, cut_fr, w: float, h: float,
                cut_pct: tuple[float, float] = (40.0, 31.6)) -> tuple:
    r"""解 A 段的**画面平移** $(c_x,c_y)$，使硬切从构造上就不跳。

    $$c_x=a-F_{\rm cut}\bar u_{\rm cut},\qquad c_y=b+F_{\rm cut}\bar v_{\rm cut}$$

    其中 $F_{\rm cut}=\mathrm{fk}\cdot F_{\rm upper}$ 也是闭式（`a_focal_bound`）
    ⇒ 一次算完，**不迭代**。
    """
    P = dict(pa)
    base = c3.ROW_X * (1.0 - P["follow"]) + cut_fr.x * P["follow"]
    eye, aim = _a_eye(P, base)
    cam = c3.make_cam(eye, aim)
    uv = content_uv(cut_fr, cam)
    if uv is None:
        return (w * cut_pct[0] / 100, h * cut_pct[1] / 100)
    bb, (uc, vc) = uv
    F = P["fk"] * a_focal_bound(bb, uc, vc, w, h, cut_pct)
    a, b = cut_pct[0] / 100 * w, cut_pct[1] / 100 * h
    return (a - F * uc, b + F * vc), F


def make_cameras(pa: dict | None = None, pb: dict | None = None,
                 state: dict | None = None):
    r"""返回一个 `camera_for(fr, w, h)`：**按 `state["stage"]` 切机位**。

    $$\text{base}_A=R\,(1-f_A)+x\,f_A,\qquad
      \text{base}_B=R\,(1-f_B)+x\,f_B,\qquad R=\text{ROW\_X}=28$$

    A 段（侧视宽机位）：
        `eye=(base_A+tx, ey, h)`、`tgt=(base_A+tx, 0, tz)`
    B 段（后视推近，**y 锚在中线**）：
        `eye=(base_B−D, ey, h0+az·z)`、`tgt=(base_B+tf, ey, tz0+bz·z)`

    ★ `az/bz` 让机位**随车一起下沉**：切换点车还在 9.9 m 高，
    机位若钉在地面，车会从画面顶上飞出去（实测第一版就是这样）。
    """
    A = dict(A_CAM if pa is None else pa)
    B = dict(B_CAM if pb is None else pb)
    st = STATE if state is None else state

    def _cam(fr, w, h):
        stage = st.get("stage") or ("B" if st.get("close") else "A")
        P = B if stage == "B" else A
        base = c3.ROW_X * (1.0 - P["follow"]) + fr.x * P["follow"]
        fk = P["fk"]
        if stage == "B":
            z = fr.z
            eye = (base - P["D"], P["ey"], P["h0"] + P["az"] * z)
            tgt = (base + P["tf"], P["ey"], P["tz0"] + P["bz"] * z)
            # ★ 焦距随高度**推近**：切换点车还在 10 m 高空，用长焦会把它切成
            #   "半屏特写"（实测 bbox 占画高 63%，离上边框只剩 0.14 单位）。
            #   取 `fk0`（高空）→ `fk`（贴地），**落地帧才是最紧的那一帧**。
            if "fk0" in P:
                t = min(1.0, max(0.0, 1.0 - z / max(P.get("zref", 9.93), 1e-6)))
                fk = P["fk0"] + (P["fk"] - P["fk0"]) * (t * t * (3 - 2 * t))
        else:
            if P.get("mode") == "q34":
                # ---- 3/4 斜侧视：机位随 `follow` 平移，**焦距按帧自算** ----
                eye, aim = _a_eye(P, base)
                cam = c3.make_cam(eye, aim)
                uv = content_uv(fr, cam)
                pan = P.get("pan") or (0.5 * w, 0.5 * h)
                if uv is None:
                    return cam, fk * min(w, h), pan[0], pan[1]
                bb, (uc, vc) = uv
                focal = P["fk"] * a_focal_bound(bb, uc, vc, w, h,
                                                P.get("cut_pct", (40.0, 31.6)))
                return cam, focal, pan[0], pan[1]
            x0 = base + P["tx"]
            eye = (x0, P["ey"], P["h"])
            tgt = (x0, 0.0, P["tz"])
        cam = c3.make_cam(eye, tgt)
        return cam, min(w, h) * fk, w * 0.5, h * 0.5

    return _cam


# ==================== 跑道（A/B 共用；GROUND_HOOK）====================


def draw_runway(ax, fr, cam, focal, cx, cy) -> None:
    r"""画一条**有透视的跑道**，让"横"这个字有地平面可依。

    1. 路面带：`y∈[-3.5, 3.5]` 填一层比地面略亮的深灰 ⇒ 车道"立"起来
    2. 两侧实线：`y=±3.5`，连续
    3. 中线：`y=0`，**虚线**（与两侧实线构成跑道）
    4. 横向刻线：每 5 m 一条，**远了淡出** ⇒ 透视收缩 = 地面感
    5. 贴地时：从**车体中心**拉一条垂直投影线到 `(x,0,0)`，地面点画小圈
    6. `RULER_ON` 时：地面横向刻度尺（每 0.25 m 一格，±4 m）
       —— 用户定："偏了两格"比"偏了 85 厘米"更能在画面里站住。
    """
    def P(p):
        return c3.project(cam, p, focal, cx, cy)

    x0, x1 = fr.x - X_BACK, fr.x + X_FWD

    for xa in range(int(x0), int(x1), 2):
        q = [(xa, -LANE_HALF, 0), (xa + 2, -LANE_HALF, 0),
             (xa + 2, LANE_HALF, 0), (xa, LANE_HALF, 0)]
        ps = [P(t) for t in q]
        if all(ps):
            ax.add_patch(Polygon([(p[0], p[1]) for p in ps], closed=True,
                                 fc="#2c3d5c", ec="none", alpha=0.75,
                                 zorder=0.5))

    for y in (-LANE_HALF, LANE_HALF):
        a, b = P((x0, y, 0)), P((x1, y, 0))
        if a and b:
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#8fa6c8",
                    lw=1.6, alpha=0.95, solid_capstyle="butt", zorder=1.2)

    xx = x0
    while xx < x1:
        a, b = P((xx, 0, 0)), P((min(xx + DASH_ON, x1), 0, 0))
        if a and b:
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#f5c542",
                    lw=1.8, alpha=0.95, solid_capstyle="butt", zorder=1.3)
        xx += DASH_ON + DASH_OFF

    gx = int(x0 // GRID_STEP) * GRID_STEP
    while gx <= x1:
        d = abs(gx - fr.x)
        al = max(0.10, 0.55 * (1 - d / (X_FWD + 6)))
        a, b = P((gx, -LANE_HALF - 0.6, 0)), P((gx, LANE_HALF + 0.6, 0))
        if a and b:
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#6f86a8",
                    lw=0.9, alpha=al, zorder=1.1)
        gx += GRID_STEP

    if fr.z < 1.2:
        g = P((fr.x, 0.0, 0))
        c_ = P((fr.x, fr.y, fr.z))
        if g and c_:
            ax.plot([c_[0], g[0]], [c_[1], g[1]], color="#ffffff", lw=1.4,
                    ls=(0, (2, 3)), alpha=0.9, zorder=2.5)
            ax.plot([g[0]], [g[1]], "o", ms=6, mfc="none", mec="#ffffff",
                    mew=1.6, alpha=0.95, zorder=2.6)

    if RULER_ON:
        rx = fr.x - 2.0                      # 尺子放在车后 2 m 的地面上
        a, b = P((rx, -RULER_HALF, 0)), P((rx, RULER_HALF, 0))
        if a and b:
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#9fb4d4",
                    lw=1.1, alpha=0.85, zorder=1.4)
        n = int(RULER_HALF / RULER_STEP)
        for k in range(-n, n + 1):
            yy = k * RULER_STEP
            maj = abs(yy - round(yy)) < 1e-6
            ln = 0.55 if maj else 0.28
            p0, p1 = P((rx - ln, yy, 0)), P((rx, yy, 0))
            if p0 and p1:
                ax.plot([p0[0], p1[0]], [p0[1], p1[1]],
                        color="#cfe0f5" if maj else "#7f96b8",
                        lw=1.5 if maj else 0.9,
                        alpha=0.95 if maj else 0.7, zorder=1.4)


GROUND_HOOK = draw_runway     # 主循环里可直接置 None 关掉

# ==================== 羽流 ====================


def body_to_world(axis: str, th: float) -> tuple[float, float, float]:
    r"""体轴 → 世界（绕 $x$ 滚转 $\theta$）。**喷口与车身固连。**"""
    base = {"+X": (1, 0, 0), "-X": (-1, 0, 0), "+Z": (0, 0, 1),
            "-Z": (0, 0, -1), "+Y": (0, 1, 0), "-Y": (0, -1, 0)}[axis]
    c, s = math.cos(th), math.sin(th)
    return (base[0], base[1] * c - base[2] * s,
            base[1] * s + base[2] * c)


# ★ 喷口 3D 位置**从 NOZZLE_META 推导**，不再手抄（手抄必走样）。
NOZZLE_POS3D = {
    m["name"]: (m["pos"][0], m["pos"][1], m["pos2_z"])
    for m in ns.NOZZLE_META
}


def draw_frame(ax, fr, hist) -> None:
    ax.clear()
    ax.set_xlim(0, VIEW_W)
    ax.set_ylim(VIEW_H, 0)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_facecolor("#0b1220")

    cam, focal, cx, cy = c3.camera_for(fr, VIEW_W, VIEW_H)

    # ---- 地面：地平线以下填带 ----
    hy = c3.horizon_y(fr, cam, focal, cx, cy, VIEW_H)
    ax.add_patch(Polygon([(0, hy), (VIEW_W, hy), (VIEW_W, VIEW_H), (0, VIEW_H)],
                         closed=True, fc="#22314c", ec="none", zorder=0))

    # ---- 地面装饰钩子（默认 None，原行为不变）----
    if GROUND_HOOK is not None:
        GROUND_HOOK(ax, fr, cam, focal, cx, cy)

    # ---- 地面网格 ----
    for gx in range(int(fr.x) - 24, int(fr.x) + 40, 4):
        a = c3.project(cam, (gx, -22, 0), focal, cx, cy)
        b = c3.project(cam, (gx, 7, 0), focal, cx, cy)
        if a and b:
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#2a3b57",
                    lw=0.6, zorder=1)
    for gy in range(-20, 8, 4):
        a = c3.project(cam, (fr.x - 24, gy, 0), focal, cx, cy)
        b = c3.project(cam, (fr.x + 40, gy, 0), focal, cx, cy)
        if a and b:
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#2a3b57",
                    lw=0.6, zorder=1)

    # ---- 轨迹 ----
    if len(hist) > 2:
        pts = []
        for q in hist:
            p = c3.project(cam, (q.x, 0, q.z), focal, cx, cy)
            if p:
                pts.append((p[0], p[1]))
        if len(pts) > 1:
            ax.plot([p[0] for p in pts], [p[1] for p in pts],
                    color="#38bdf8", lw=1.2, alpha=.45, zorder=2)

    # ---- 车 + 障碍（已剔除、已排序、已着色）----
    draws = c3.collect_drawables(fr, cam, focal, cx, cy)
    if draws:
        ax.add_collection(PolyCollection(
            [d[0] for d in draws],
            facecolors=[d[1] for d in draws],
            edgecolors=(0.06, 0.09, 0.16, 0.5), linewidths=0.4, zorder=3))

    # ---- 羽流（排气 = 推力反向，随滚转）----
    th = fr.theta
    for nz in ns.NOZZLE_META:
        fv = fr.f.get(nz["name"], 0.0)
        if fv <= 1.0:
            continue
        lx, ly, lz = NOZZLE_POS3D[nz["name"]]
        cw, sw = math.cos(th), math.sin(th)
        wy = ly * cw - lz * sw
        wz = ly * sw + lz * cw
        p0 = c3.project(cam, (fr.x + lx, wy, fr.z + c3.BODY_LIFT + wz),
                        focal, cx, cy)
        if not p0:
            continue
        w = body_to_world(nz["axis"], th)
        df = fr.duty.get(nz["name"], 0.0)
        ln = 2.2 * (0.45 + 0.55 * min(1.0, df))
        tip = c3.project(cam, (fr.x + lx - w[0] * ln,
                               wy - w[1] * ln,
                               fr.z + c3.BODY_LIFT + wz - w[2] * ln),
                         focal, cx, cy)
        if not tip:
            continue
        ax.plot([p0[0], tip[0]], [p0[1], tip[1]], color=nz["color"],
                lw=7, alpha=.5, solid_capstyle="round", zorder=4)
        ax.plot([p0[0], tip[0]], [p0[1], tip[1]], color="#f8fafc",
                lw=1.8, alpha=.9, zorder=5)
        ax.plot([p0[0]], [p0[1]], marker="o", ms=9, mfc=nz["color"],
                mec="none", alpha=.28, zorder=5)

    # ---- 滚转轴（黄虚线）----
    a = c3.project(cam, (fr.x - c3.CAR_PARTS[0][1] / 2 - 1.4, 0,
                         fr.z + c3.BODY_LIFT), focal, cx, cy)
    b = c3.project(cam, (fr.x + c3.CAR_PARTS[0][1] / 2 + 1.4, 0,
                         fr.z + c3.BODY_LIFT), focal, cx, cy)
    if a and b:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#fbbf24", lw=1.8,
                ls=(0, (6, 4)), zorder=6)

    seg = "A · 越车段" if STATE.get("stage") != "B" else "B · 落地段"
    ax.set_title(f"3D 复刻〔{seg}〕　t = {fr.t:5.2f} s　高度 {fr.z:5.2f} m　"
                 f"绕纵轴滚转 {math.degrees(fr.theta):+.0f}°",
                 fontsize=11, color="#e2e8f0", pad=5)


def draw_rear(ax2, fr) -> None:
    ax2.clear()
    ax2.set_aspect("equal")
    ax2.set_xlim(-1.4, 1.4)
    ax2.set_ylim(-1.5, 1.3)
    ax2.axis("off")
    ax2.set_facecolor("#0b1220")
    ax2.add_patch(Circle((0, 0.02), 1.0, fc="#0f172a", ec="#334155", lw=1.0))
    W, H = ph.W_CAR, ph.H_CAR
    c, s = math.cos(fr.theta), math.sin(fr.theta)
    pts = [(a * c - b * s, a * s + b * c + 0.02)
           for (a, b) in ((-W / 2, -H / 2), (W / 2, -H / 2),
                          (W / 2, H / 2), (-W / 2, H / 2))]
    ax2.add_patch(Polygon(pts, closed=True, fc="#c9d3de", ec="#94a3b8", lw=1.0))
    tip = [(a * c - b * s, a * s + b * c + 0.02)
           for (a, b) in ((-0.3, H / 2), (0.3, H / 2), (0, H / 2 + 0.24))]
    ax2.add_patch(Polygon(tip, closed=True, fc="#38bdf8", ec="none"))
    ax2.text(0, -1.34, f"后视 · {math.degrees(fr.theta):+.0f}°",
             ha="center", fontsize=7, color="#94a3b8")


def draw_panel(axp, fr) -> None:
    axp.clear()
    axp.set_xlim(0, 10)
    axp.set_ylim(0, 1.5)
    axp.axis("off")
    axp.set_facecolor("#0b1220")
    axp.text(-0.04, 1.44, "10 个喷口推力（kN）", fontsize=7,
             color="#94a3b8", va="top")
    for k, nz in enumerate(ns.NOZZLE_META):
        fv = fr.f.get(nz["name"], 0.0)
        frac = min(1.0, fv / max(1.0, 20e3))
        bx, W = k + 0.10, 0.80
        axp.add_patch(plt.Rectangle((bx, .30), W, .64,
                                    fc="#111827", ec="#334155", lw=.6))
        if frac > 0.004:
            axp.add_patch(plt.Rectangle((bx, .30), W, .64 * frac,
                                        fc=nz["color"], ec="none"))
        axp.text(bx + W / 2, 1.06, nz["short"], ha="center", fontsize=6.8,
                 color="#e2e8f0" if fv > 1 else "#64748b")
        axp.text(bx + W / 2, .12, f"{fv/1000:.0f}" if fv > 1 else "—",
                 ha="center", fontsize=6.3,
                 color=nz["color"] if fv > 1 else "#475569")


# ==================== 时间轴 ====================


def sample_idx(recs, t0: float, t1: float, n: int) -> list[int]:
    r"""在任务时间 $[t_0,t_1]$ 上**均匀取 n 帧**（端点都取），返回记录下标。"""
    n = max(int(n), 1)
    i0 = next((i for i, r in enumerate(recs) if r.t >= t0 - 1e-9), 0)
    i1 = next((i for i, r in enumerate(recs) if r.t >= t1 - 1e-9), len(recs) - 1)
    i1 = max(i1, i0 + 1)
    if n == 1:
        return [i0]
    return [i0 + int(round(k * (i1 - i0) / (n - 1))) for k in range(n)]


def build_timeline(recs, fps: int, dur: float, hold: float, t_cut: float,
                   a_ratio: float = A_RATIO, n_a: int | None = None,
                   t_a_from: float = 0.0, t_b_to: float | None = None):
    r"""帧序列 + 每帧属于哪一段。

    $$\underbrace{n_A}_{\text{A 段}}\;+\;\underbrace{n_B}_{\text{B 段}}\;+\;
      \underbrace{n_{\rm hold}}_{\text{落地停留}} = \text{round}(T\cdot fps)$$

    * A 段：$[t_{a0},\,t_{\rm cut}]$ —— 起步→起飞→越车→最高点
    * B 段：$[t_{\rm cut},\,t_{\rm end}]$ —— 下落→点火→落地→停住
    * 两段在 $t_{\rm cut}$ 处**共用同一条记录**（硬切：最后一帧 A 与第一帧 B
      是同一瞬间，肉眼只看到机位变了）
    """
    n_total = int(round(dur * fps))
    n_hold = int(round(hold * fps))
    n_mot = max(n_total - n_hold, 2)
    na = int(n_a) if n_a is not None else int(round(n_mot * a_ratio))
    na = max(1, min(na, n_mot - 1))
    nb = n_mot - na
    t_end = float(recs[-1].t if t_b_to is None else t_b_to)
    idx = (sample_idx(recs, t_a_from, t_cut, na)
           + sample_idx(recs, t_cut, t_end, nb)
           + [sample_idx(recs, t_end, t_end, 1)[0]] * n_hold)
    stages = ["A"] * na + ["B"] * nb + ["B"] * n_hold
    return idx[:n_total], stages[:n_total], na, nb, n_hold


# ==================== 几何自检（--probe）====================


def probe(recs, idx, stages, fps: int, w_peak_min: float = 0.20) -> int:
    r"""**不渲染**也能验的三件事（`c3.project` 投影，与画面同一条管线）。

    ① A 段五台障碍车的包围盒是否四点都在画内
    ② B 段落地帧：车心到跑道中线占画宽多少
    ③ 切换点前后：车的屏幕位置跳变

    `w_peak_min`：①b 的车宽门槛。横屏（16:9）是 0.20；竖屏 9:16 画面更窄、
    车队必然更占宽度，判据是 **0.10**（竖屏脚本传进来，默认值保持横屏口径不变）。
    """
    boxes = []
    for k, (dx, L, Hx, _c) in enumerate(c3.OBSTACLES, 1):
        x0, x1 = c3.ROW_X + dx - L / 2, c3.ROW_X + dx + L / 2
        boxes.append((k, [(x, y, z) for x in (x0, x1) for y in (-1.0, 1.0)
                          for z in (0.0, Hx)]))

    def rect(fr, cam, focal, cx, cy, pts):
        ps = [c3.project(cam, p, focal, cx, cy) for p in pts]
        if any(p is None for p in ps):
            return None
        xs = [p[0] for p in ps]
        ys = [p[1] for p in ps]
        return (min(xs), min(ys), max(xs), max(ys))

    def inside(r, m=0.0):
        return (r is not None and r[0] >= m and r[1] >= m
                and r[2] <= VIEW_W - m and r[3] <= VIEW_H - m)

    def car_rect(fr, cam, focal, cx, cy):
        faces = c3.car_faces(fr.x, fr.z, fr.theta, fr.y)
        return rect(fr, cam, focal, cx, cy,
                    [v for (vs, _c, _ctr) in faces for v in vs])

    print("=" * 88)
    print(f"  几何自检 · VIEW {VIEW_W}×{VIEW_H} · {fps} fps · {len(idx)} 帧")
    print("=" * 88)

    # ---- ① A 段 ----
    n5 = nc = nb = 0
    first = None
    for i, (k, st) in enumerate(zip(idx, stages)):
        if st != "A":
            continue
        r = recs[k]
        STATE["stage"] = st
        cam, focal, cx, cy = c3.camera_for(r, VIEW_W, VIEW_H)
        ok5 = all(inside(rect(r, cam, focal, cx, cy, b)) for (_n, b) in boxes)
        cr = car_rect(r, cam, focal, cx, cy)
        cin = inside(cr)
        n5 += ok5
        nc += cin
        nb += (ok5 and cin)
        if ok5 and cin and first is None:
            first = (i, r, cr)
    na = stages.count("A")
    print(f"  ① A 段 {na} 帧：五车**全部**在画内 {n5}/{na}"
          f"（{100*n5/max(na,1):.0f}%）｜ 车在画内 {nc}/{na}"
          f"｜ 两者同框 {nb}/{na}"
          f"  {'[OK]' if n5 > 0 and nb > 0 else '[X]'}")
    if first:
        i, r, cr = first
        print(f"     同框最早一帧：第 {i} 帧 t={r.t:.2f}s x={r.x:.1f} z={r.z:.2f}"
              f"  车框 x {cr[0]:.2f}–{cr[2]:.2f} y {cr[1]:.2f}–{cr[3]:.2f}")

    # ---- ①b ★ 车宽占画宽（用户判据 ②：峰值高度那一帧 ≥ 20%）----
    ai = [(i, k) for i, (k, st) in enumerate(zip(idx, stages)) if st == "A"]
    k_pk = max(ai, key=lambda t: recs[t[1]].z)
    i_pk, kk = k_pk
    rp = recs[kk]
    STATE["stage"] = "A"
    cam, focal, cx, cy = c3.camera_for(rp, VIEW_W, VIEW_H)
    crp = car_rect(rp, cam, focal, cx, cy)
    w_peak = (crp[2] - crp[0]) / VIEW_W if crp else 0.0
    print(f"  ①b 峰值帧 #{i_pk} t={rp.t:.3f}s z={rp.z:.2f}m x={rp.x:.1f}m："
          f"**车宽 {crp[2]-crp[0]:.2f} 单位 = {100*w_peak:.1f}% 画宽**"
          f"（门槛 {100*w_peak_min:.0f}%）  "
          f"{'[OK]' if w_peak >= w_peak_min else '[X]'}")
    print(f"     车框 x {crp[0]:.2f}–{crp[2]:.2f} y {crp[1]:.2f}–{crp[3]:.2f}"
          f"  中心 ({100*(crp[0]+crp[2])/2/VIEW_W:.1f}%, "
          f"{100*(crp[1]+crp[3])/2/VIEW_H:.1f}%)"
          f"  f={focal:.2f}  pan=({cx:.2f},{cy:.2f})")
    # 五车在**同一帧**的屏幕框（由近及远 ⇒ 屏幕 x 递减 + 框越来越小）
    rows = [(nm, rect(rp, cam, focal, cx, cy, b)) for (nm, b) in boxes]
    rows.sort(key=lambda t: -t[1][0])
    print("     五车（按屏幕 x 从右到左 = 由近及远）：")
    prev = None
    for (nm, rr) in rows:
        gap = "" if prev is None else f"  与上一台间隙 {prev - rr[2]:+.2f}"
        print(f"       车{nm}  x {rr[0]:5.2f}–{rr[2]:5.2f} (宽 "
              f"{100*(rr[2]-rr[0])/VIEW_W:4.1f}%)  y {rr[1]:5.2f}–{rr[3]:5.2f}"
              f"  中心 x {100*(rr[0]+rr[2])/2/VIEW_W:5.1f}%{gap}")
        prev = rr[0]
    # A 段全帧的车宽（看它是否单调变大）
    ws = []
    for (i, k) in ai:
        STATE["stage"] = "A"
        rr = car_rect(recs[k], *c3.camera_for(recs[k], VIEW_W, VIEW_H))
        ws.append((100 * (rr[2] - rr[0]) / VIEW_W if rr else 0.0, recs[k].t))
    print(f"     A 段车宽范围 {min(w for w, _t in ws):.1f}%–"
          f"{max(w for w, _t in ws):.1f}%（首帧 {ws[0][0]:.1f}%，"
          f"末帧 {ws[-1][0]:.1f}%）")

    # ---- ③ 切换点 ----
    ia = na - 1
    if ia + 1 < len(idx):
        rA = recs[idx[ia]]
        rB = recs[idx[ia + 1]]
        out = []
        for i_frame, st in ((ia, "A"), (ia + 1, "B")):
            STATE["stage"] = st
            r = recs[idx[i_frame]]
            cam, focal, cx, cy = c3.camera_for(r, VIEW_W, VIEW_H)
            out.append(car_rect(r, cam, focal, cx, cy))
        print(f"  ③ 硬切：A 末帧 #{ia} t={rA.t:.2f}s ｜ B 首帧 #{ia+1} "
              f"t={rB.t:.2f}s")
        for nm, rr in zip(("A", "B"), out):
            print(f"     {nm} 车位 x {rr[0]:6.2f}–{rr[2]:6.2f} "
                  f"y {rr[1]:5.2f}–{rr[3]:5.2f}  中心 "
                  f"({100*(rr[0]+rr[2])/2/VIEW_W:5.1f}%, "
                  f"{100*(rr[1]+rr[3])/2/VIEW_H:5.1f}%)")
        dx = 100 * (((out[1][0] + out[1][2]) - (out[0][0] + out[0][2])) / 2) / VIEW_W
        dy = 100 * (((out[1][1] + out[1][3]) - (out[0][1] + out[0][3])) / 2) / VIEW_H
        print(f"     ★ 跳变 Δx = {dx:+.1f}% 画宽，Δy = {dy:+.1f}% 画高")

    # ---- ② 落地帧 ----
    t_land = next((r.t for r in recs if r.z <= 0.02 and r.t > 2.0), recs[-1].t)
    k_land = next(k for k in idx if recs[k].t >= t_land - 1e-9) \
        if any(recs[k].t >= t_land - 1e-9 for k in idx) else idx[-1]
    r = recs[k_land]
    STATE["stage"] = "B"
    cam, focal, cx, cy = c3.camera_for(r, VIEW_W, VIEW_H)
    cr = car_rect(r, cam, focal, cx, cy)
    q = c3.project(cam, (r.x, 0.0, 0.0), focal, cx, cy)
    if cr and q:
        cc = (cr[0] + cr[2]) / 2
        print(f"  ② 落地帧 t={r.t:.2f}s x={r.x:.1f} y={r.y:+.3f}："
              f"车框 x {cr[0]:.2f}–{cr[2]:.2f} y {cr[1]:.2f}–{cr[3]:.2f}"
              f"（中心 {100*cc/VIEW_W:.1f}%）｜ 中线 {q[0]:.2f}"
              f"（{100*q[0]/VIEW_W:.1f}%）｜ **偏移 "
              f"{100*abs(q[0]-cc)/VIEW_W:.2f}% 画宽**（门槛 8.00%）"
              f"｜车{'完整入画' if inside(cr) else '[X] 被切'}")

    # ---- ④ 逐帧余量：B 段的车不许贴边（A 段允许车从边框进来/出去）----
    for stage in ("A", "B"):
        m = 1e9
        worst = None
        STATE["stage"] = stage
        for k, st in zip(idx, stages):
            if st != stage:
                continue
            rr = car_rect(recs[k], *c3.camera_for(recs[k], VIEW_W, VIEW_H))
            if rr is None:
                continue
            mm = min(rr[0], rr[1], VIEW_W - rr[2], VIEW_H - rr[3])
            if mm < m:
                m, worst = mm, recs[k]
        print(f"  ④ {stage} 段车框最小余量 {m:+.2f} 单位"
              f"（t={worst.t:.2f}s z={worst.z:.2f}）"
              f"  {'[OK]' if m >= 0 else '[X] 贴边/出画'}")
    STATE["stage"] = "A"
    print()
    return 0


# ==================== main ====================


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--dur", type=float, default=10.9333,
                    help="片段时长（秒）。★ 由 splice 的时隙倒推：屏 02 = 10.9333 s"
                         "（328 帧）、屏 08 = 9.4 s（282 帧）")
    ap.add_argument("--hold", type=float, default=HOLD, help="落地停留（秒）")
    ap.add_argument("--t-cut", type=float, default=T_CUT, help="硬切时刻（秒）")
    ap.add_argument("--a-ratio", type=float, default=A_RATIO)
    ap.add_argument("--out", default="sim_jump_3d.mp4")
    ap.add_argument("--probe", action="store_true", help="只做几何自检，不出片")
    ap.add_argument("--max-frames", type=int, default=0, help=">0 只渲这么多帧（测速）")
    ap.add_argument("--skip-fig", action="store_true")
    args = ap.parse_args()

    setup()
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    print("=" * 88)
    print("  W55 · 3D 动画 v3（车身与 sim.html 同源；A/B 两镜头硬切）")
    print("=" * 88)

    dt = 1 / 120
    recs = ns.run_mission10_auto(dt)
    s = ns.summarize10(recs)
    print(f"\n  {len(recs)} 步，{s['t_end']:.2f} s")
    print(f"  峰值 {s['z_max']:.2f} m，落地 vz {s['vz_land']:+.2f} m/s")
    print(f"  共转 {s['theta_end_deg']:+.0f}°，耗气 {s['m_total']:.1f} kg")

    idx, stages, na, nb, nhold = build_timeline(
        recs, args.fps, args.dur, args.hold, args.t_cut, args.a_ratio)
    print(f"\n  时间轴：A {na} 帧 + B {nb} 帧 + 停留 {nhold} 帧 "
          f"= {len(idx)} 帧 = {len(idx)/args.fps:.3f} s")
    print(f"  A 段任务窗 [{recs[idx[0]].t:.3f}, {recs[idx[na-1]].t:.3f}] s "
          f"⇒ {na/args.fps:.2f} s 播完"
          f"（慢放 {na/args.fps/max(recs[idx[na-1]].t - recs[idx[0]].t, 1e-6):.2f}×）")
    print(f"  B 段任务窗 [{recs[idx[na]].t:.3f}, {recs[idx[-1]].t:.3f}] s "
          f"⇒ {nb/args.fps:.2f} s 播完"
          f"（慢放 {nb/args.fps/max(recs[idx[-1]].t - recs[idx[na]].t, 1e-6):.2f}×）")

    # ★ A 段的画面平移**先解出来**（硬切跳变由构造保证为 0，而不是渲完再看）
    if A_CAM.get("mode") == "q34":
        A_CAM["pan"], _fcut = solve_A_pan(A_CAM, recs[idx[na - 1]],
                                          VIEW_W, VIEW_H)
        print(f"  A 段 q34 机位：az={A_CAM['az']:.0f}° pitch={A_CAM['pitch']:.0f}° "
              f"R={A_CAM['R']:.0f} follow={A_CAM['follow']:.2f} "
              f"fk={A_CAM['fk']:.3f}")
        print(f"    平移（由硬切约束解出）pan = "
              f"({A_CAM['pan'][0]:.3f}, {A_CAM['pan'][1]:.3f})"
              f"  ⇒ 切换帧焦距 F = {_fcut:.3f}")

    c3.camera_for = make_cameras()
    if args.probe:
        return probe(recs, idx, stages, args.fps)

    fig = plt.figure(figsize=(FIG_W, FIG_H), dpi=DPI)
    fig.patch.set_facecolor("#0b1220")
    ax = fig.add_axes(AX_RECT)
    ax2 = fig.add_axes([0.008, 0.005, 0.085, 0.14])
    axp = fig.add_axes([0.105, 0.004, 0.88, 0.11])

    n_frames = len(idx) if not args.max_frames else min(len(idx), args.max_frames)

    def upd(i):
        global RULER_ON
        k = idx[i]
        STATE["stage"] = stages[i]
        RULER_ON = stages[i] == "B"
        draw_frame(ax, recs[k], recs[:k + 1])
        draw_rear(ax2, recs[k])
        draw_panel(axp, recs[k])

    anim = FuncAnimation(fig, upd, frames=n_frames,
                         interval=1000 / args.fps, repeat=False)
    out = OUT / args.out
    anim.save(str(out), writer=FFMpegWriter(fps=args.fps, bitrate=3600))
    plt.close(fig)
    print(f"  [OK] {out.name}  {out.stat().st_size/1e6:.2f} MB"
          f"  {n_frames} 帧")

    if not args.skip_fig:
        # 关键帧图：A 段同框帧 / 起飞 / 最高点 / 切换前 / 切换后 / 落地
        global RULER_ON
        k_cut = idx[na - 1]
        pick = [idx[0],
                next(k for k in idx if recs[k].z > 1.0),
                max(idx[:na], key=lambda k: recs[k].z),
                k_cut, idx[min(na, len(idx) - 1)], idx[-1]]
        fig2, axs = plt.subplots(2, 3, figsize=(17, 9.6))
        fig2.patch.set_facecolor("#0b1220")
        for a2, k in zip(axs.ravel(), pick):
            STATE["stage"] = "A" if k <= k_cut else "B"
            RULER_ON = STATE["stage"] == "B"
            draw_frame(a2, recs[k], recs[:k + 1])
        fig2.tight_layout()
        png = FIG / "fig_sim_3d_keyframes.png"
        fig2.savefig(png, facecolor="#0b1220", dpi=110, bbox_inches="tight")
        plt.close(fig2)
        print(f"  [OK] {png.name}  {png.stat().st_size/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
