#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **3D 车身与渲染的唯一真源**（Python 侧）。

## 为什么要抽这个模块

同一辆车被我实现过四遍：
1. `sim_anim3d_v2.py` 的方块版；
2. `car_model.py` 的放样版；
3. `publish/sim.html` 的 JS 方块版；
4. `preview_html3d2.py` 的复算版。

**每多一份实现，就多一处走样的机会**（这一期已经因为"双重旋转 / 漏旋转"
翻车两次）。**⇒ 收敛到一个模块，动画与预览都调它。**

## 与 `sim.html` 的对应关系

本模块的 `CAR_PARTS` / `BODY_LIFT` / 车轮参数与 `sim.html` 里
的 `CAR_PARTS` / `BODY_LIFT` **逐字段一致**；
渲染四步（相机基 → 透视 → 背面剔除 → Lambert）也一致。

**⇒ 改一边必须改另一边，并在 `verify_html_3d.js` 之后重跑本模块的动画。**

## 车身设计（用户认可的版本）

| 部件 | 颜色 | 作用 |
|---|---|---|
| 车身 | 银灰 | 主体 |
| **车顶** | **亮青** | ★ 滚转时"哪面朝上"的唯一高对比参照 |
| 底板 | 深灰 | 车底不是白纸 |
| 座舱 | 近黑 | 驾驶舱 |
| 前鼻 / 前灯 / 尾灯 / 尾翼 | — | 车头车尾可辨 |
| **四轮** | 近黑圆柱 | 任何角度都看得见 |

## ★ 两个必须记住的约定

$$\text{部件 } oz \text{ 是**相对质心**（质心离地 BODY\_LIFT）}$$

$$\text{轮心 } oz = R - \text{BODY\_LIFT} \Rightarrow \text{轮底恰好擦地}$$

**局部尺寸也必须随 $\theta$ 旋转** —— 只转中心会让盒子在世界系里保持轴对齐。
"""
from __future__ import annotations

import math

# ==================== 车身 ====================
BODY_LIFT = 0.60          # 质心离地高度
PIVOT_Z = 0.62            # 滚转轴高度（略高于质心）

# (名称, L, W, H, ox, oy, oz, RGB)
#
# ★ oz 一律**相对质心**（质心离地 BODY_LIFT = 0.60）。
#   离地高度 = BODY_LIFT + oz，见每个部件右边的注释。
CAR_PARTS = [
    # ---- 车身主体：下段 + 上段（让侧影有层次，不是一整块盒子）----
    ("车身下", 4.50, 2.00, 0.44, +0.00, 0.0, -0.20, (196, 205, 215)),  # 0.18–0.62
    ("车身上", 3.55, 1.86, 0.18, -0.10, 0.0, +0.11, (208, 216, 226)),  # 0.62–0.80
    # ---- 车底：深色薄板（滚转时看到的是它，不是白纸）----
    ("底板", 4.28, 1.90, 0.08, +0.00, 0.0, -0.40, (31, 41, 55)),       # 0.16–0.24
    # ---- 座舱：后移（挡风根 x/L=0.24 ⇒ x=+1.17）----
    ("座舱", 1.92, 1.50, 0.40, -0.06, 0.0, +0.38, (32, 42, 54)),       # 0.78–1.18
    # ---- ★ 车顶：亮青，滚转姿态的唯一高对比参照 ----
    ("车顶", 1.80, 1.42, 0.04, -0.06, 0.0, +0.60, (56, 189, 248)),     # 1.18–1.22
    # ---- 楔形前鼻 ----
    ("前鼻", 1.00, 1.90, 0.30, +1.75, 0.0, -0.15, (222, 229, 238)),    # 0.30–0.60
    # ---- ★ 全宽细灯条（图片是贯穿式）----
    ("前灯", 0.06, 1.86, 0.06, +2.24, 0.0, -0.04, (255, 255, 255)),    # 0.53–0.59
    ("尾灯", 0.06, 1.86, 0.06, -2.24, 0.0, +0.02, (239, 68, 68)),      # 0.59–0.65
    # ---- ★ 大尾翼 + 两根立柱（图片里翼接近全宽且很高）----
    ("尾翼", 0.38, 1.94, 0.06, -2.02, 0.0, +0.50, (52, 62, 76)),       # 1.07–1.13
    ("翼柱L", 0.10, 0.08, 0.30, -2.00, -0.72, +0.32, (44, 53, 66)),    # 0.77–1.07
    ("翼柱R", 0.10, 0.08, 0.30, -2.00, +0.72, +0.32, (44, 53, 66)),
]

# 车轮
R_WHEEL = 0.37
W_WHEEL = 0.34
Y_TRACK = 1.02
X_AXLE = 1.44
N_SEG = 12
WHEEL_COL = (20, 27, 38)
WHEEL_CAP = (14, 20, 30)

# 光照方向（世界系）
LIGHT = (-0.45, -0.72, 0.52)

# 车队（沿 x 一排，与 sim.html / physics 一致）
ROW_X = 28.0
OBSTACLES = [
    (-9.20, 4.40, 1.50, (100, 116, 139)),
    (-4.60, 4.40, 1.50, (100, 116, 139)),
    (0.00, 6.20, 4.00, (226, 232, 240)),
    (4.60, 4.40, 1.50, (100, 116, 139)),
    (9.20, 4.40, 1.50, (100, 116, 139)),
]

# ==================== 向量 ====================


def vsub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vdot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vcross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def vnorm(a):
    L = math.hypot(*a) or 1.0
    return (a[0] / L, a[1] / L, a[2] / L)


# ==================== 几何 ====================


def rot_yz(y, z, th):
    r"""绕 $x$ 轴滚转 $\theta$（绕高度 `PIVOT_Z`）。

    $$\begin{pmatrix}y'\\z'\end{pmatrix}
    = \begin{pmatrix}\cos\theta&-\sin\theta\\
                     \sin\theta&\cos\theta\end{pmatrix}
    \begin{pmatrix}y\\ z-\text{PIVOT}\end{pmatrix}
    +\begin{pmatrix}0\\ \text{PIVOT}\end{pmatrix}$$
    """
    c, s = math.cos(th), math.sin(th)
    dz = z - PIVOT_Z
    return (y * c - dz * s, PIVOT_Z + y * s + dz * c)


def car_center_offset(oy, oz, th):
    r"""部件中心在**车体坐标**下经滚转后的 $(y,z)$。"""
    return rot_yz(oy, oz, th)


def world_z_offset(cz):
    r"""车体坐标 $z$ → 世界偏移：抬 `BODY_LIFT`。"""
    return BODY_LIFT + cz


def box_faces(cx, cy, cz, L, W, H, col, ctr, roll=0.0):
    r"""长方体六面（**局部尺寸随 roll 旋转**）。

    ## ★ 为什么必须带 roll

    只把中心转到位、却让盒子保持世界轴对齐 ⇒
    **看起来是"盒子在滑移"，不是"车身在翻滚"**。
    """
    hx, hy, hz = L / 2, W / 2, H / 2
    rc, rs = math.cos(roll), math.sin(roll)
    P = {}
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                yl, zl = sy * hy, sz * hz
                P[(sx, sy, sz)] = (cx + sx * hx,
                                   cy + yl * rc - zl * rs,
                                   cz + yl * rs + zl * rc)
    quads = [
        [(-1, -1, -1), (-1, 1, -1), (-1, 1, 1), (-1, -1, 1)],
        [(1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1)],
        [(-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)],
        [(-1, 1, -1), (1, 1, -1), (1, 1, 1), (-1, 1, 1)],
        [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1)],
        [(-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)],
    ]
    return [([P[k] for k in q], col, ctr) for q in quads]


def car_faces(x0: float, z0: float, th: float,
              y0: float = 0.0) -> list[tuple]:
    r"""整车：`[(faces, rgb, ctr)]`。$z_0$ 是**接地高度**（物理里的 $z$）。

    ## ★ `y0`：车体的**横向基座**（2026-10-18 修 bug）

    原签名只有 `(x0, z0, th)`，$y$ 分量**只来自车体自身的 `oy`** ⇒
    **车永远画在 $y=0$ 的中线上**。

    后果：物理里算出的横漂（落地 0.57–1.14 m）**从未被画出来**，
    所以这部片子从第一版起就"看不出偏"——不是看不见，是根本没偏。
    像素法实测：车包围盒中心 545 px ≈ 中线 540 px，偏移 0.69%。

    ⇒ 加 `y0`，默认 **0.0**（老调用行为不变），由 `collect_drawables` 传 `fr.y`。

    ⚠️ 注意 `ctr`（第三个返回值）也加了 `y0`：它用于**画家算法按质心深度排序**，
    漏加会让排序在车横向偏离时出错。
    """
    faces = []
    for (_nm, Lx, Wx, Hx, ox, oy, oz, col) in CAR_PARTS:
        cy, cz = car_center_offset(oy, oz, th)
        cxx = x0 + ox
        cy += y0
        czz = z0 + world_z_offset(cz)
        faces += box_faces(cxx, cy, czz, Lx, Wx, Hx, col, (cxx, cy, czz), th)

    wc, ws = math.cos(th), math.sin(th)
    for (wx, wy) in ((X_AXLE, -Y_TRACK), (X_AXLE, Y_TRACK),
                     (-X_AXLE, -Y_TRACK), (-X_AXLE, Y_TRACK)):
        # ★ 轮心 oz 相对质心：R - BODY_LIFT ⇒ 世界高度 R
        cyw, czw0 = car_center_offset(wy, R_WHEEL - BODY_LIFT, th)
        cyw += y0
        cwx, cwy, cwz = x0 + wx, cyw, z0 + world_z_offset(czw0)
        ra, rb = [], []
        for k in range(N_SEG):
            a = 2 * math.pi * k / N_SEG
            dx, dz = R_WHEEL * math.cos(a), R_WHEEL * math.sin(a)
            # ★ 轮盘局部偏移也要随滚转（轮轴不再固定沿世界 y）
            ya = (-W_WHEEL / 2) * wc - dz * ws
            za = (-W_WHEEL / 2) * ws + dz * wc
            yb = (W_WHEEL / 2) * wc - dz * ws
            zb = (W_WHEEL / 2) * ws + dz * wc
            ra.append((cwx + dx, cwy + ya, cwz + za))
            rb.append((cwx + dx, cwy + yb, cwz + zb))
        WC = (cwx, cwy, cwz)
        for k in range(N_SEG):
            m = (k + 1) % N_SEG
            faces.append(([ra[k], ra[m], rb[m], rb[k]], WHEEL_COL, WC))
        faces.append((list(ra), WHEEL_CAP, WC))
        faces.append((list(rb), WHEEL_CAP, WC))
    return faces


# ==================== 相机 ====================


def make_cam(eye, tgt, up=(0.0, 0.0, 1.0)):
    r"""相机基。**`up` 必须是世界"上" $(0,0,1)$** ——
    写成 $(0,1,0)$ 会把世界侧翻 90°（地面跑到天上）。"""
    f = vnorm(vsub(tgt, eye))
    r = vnorm(vcross(f, up))
    return eye, f, r, vcross(r, f)


def project(cam, p, focal, cx, cy):
    eye, f, r, u = cam
    d = vsub(p, eye)
    x, y, z = vdot(d, r), vdot(d, u), vdot(d, f)
    if z < 0.12:
        return None
    s = focal / z
    return (cx + x * s, cy - y * s, z)


def camera_for(fr, w: float, h: float):
    r"""与 `sim.html` 一致的机位：**站在 $-y$ 侧**，使 $+x$ 显示为屏幕右。

    $$\hat r \propto (f_y,\,-f_x,\,0)$$
    要 $\hat r \propto (1,0,0)$ ⇒ $f_y>0$ ⇒ 相机在 $y<0$。
    """
    eye = (fr.x - 6.0, -11.5, fr.z + 5.2)
    tgt = (fr.x + 3.2, 0.0, max(0.55, fr.z * 0.72 + 0.55))
    cam = make_cam(eye, tgt)
    focal = min(w, h) * 0.95
    return cam, focal, w * 0.5, h * 0.56


def collect_drawables(fr, cam, focal, cx, cy, row_x=ROW_X):
    r"""把整车 + 障碍 + 地面网格的可见面算成屏幕多边形，按深度排好。

    返回 `[(poly, rgb_shaded)]`，**已剔除背面**。
    """
    Lg = vnorm(LIGHT)
    # ★ `fr.y` 必须传进去：否则车永远画在中线上、横漂看不见（2026-10-18 修）
    faces = car_faces(fr.x, fr.z, fr.theta, fr.y)
    if abs(row_x - fr.x) < 22:
        for (dx, Lx, Hx, col) in OBSTACLES:
            cxx = row_x + dx
            faces += box_faces(cxx, 0, Hx / 2, Lx, 2.0, Hx, col,
                               (cxx, 0, Hx / 2), 0.0)

    items = []
    for (vs, col, ctr) in faces:
        pr = [project(cam, p, focal, cx, cy) for p in vs]
        if any(p is None for p in pr):
            continue
        depth = sum(p[2] for p in pr) / len(pr)
        nrm = vnorm(vcross(vsub(vs[1], vs[0]), vsub(vs[2], vs[0])))
        mid = tuple(sum(p[i] for p in vs) / len(vs) for i in range(3))
        # 法向校正朝外
        if vdot(nrm, vsub(mid, ctr)) < 0:
            nrm = (-nrm[0], -nrm[1], -nrm[2])
        to_cam = vnorm(vsub(cam[0], mid))
        # ★ 背面剔除（凸体只需画正面）
        if vdot(nrm, to_cam) <= 1e-4:
            continue
        lam = max(0.0, vdot(nrm, Lg))
        k = 0.36 + 0.64 * lam
        rgb = (col[0] * k / 255, col[1] * k / 255, col[2] * k / 255)
        items.append(([(p[0], p[1]) for p in pr], rgb, depth))

    items.sort(key=lambda it: -it[2])
    return [(poly, rgb) for (poly, rgb, _d) in items]


def horizon_y(fr, cam, focal, cx, cy, h):
    r"""地平线在屏幕上的行号（用于填地面）。

    $$\hat f_h=\frac{(f_x,f_y,0)}{\|\cdot\|},\quad
    p_h=\operatorname{proj}\left(\mathbf e+900\hat f_h\right)$$
    """
    fh = vnorm((cam[1][0], cam[1][1], 0.0))
    hp = project(cam, (cam[0][0] + fh[0] * 900,
                       cam[0][1] + fh[1] * 900,
                       cam[0][2]), focal, cx, cy)
    return max(0.0, min(h, hp[1])) if hp else h * 0.55
