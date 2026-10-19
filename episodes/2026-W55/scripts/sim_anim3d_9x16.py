#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · 抖音首屏专用的**竖屏 9:16** 仿真（飞跃五车 + 落地偏移），**7 秒版**。

## 2026-10-19 重做：从 2.27 s 扩到 7.00 s（用户："模拟视频有点短，一闪就过了"）

上一版竖屏只有 **68 帧 = 2.2667 s**，而且 A 段被时隙逼到 **30 帧（1 s）** ——
"飞跃五车"这件事在竖屏里几乎没出现。本轮抖音屏 01 的时隙扩到 **210 帧**，
A/B 两段终于能按横屏的比例展开：

| 段 | 内容 | 机位 | 任务窗 | 帧数 | 播放 |
|---|---|---|---|---|---|
| **A** | 起飞 → 越车 → 最高点 | **3/4 斜侧视**（`az=44°`、`pitch=10°`、`follow=0.60`）| `[0.00, 2.30]` s | **120** | **4.00 s** |
| **B** | 下落 → 缓冲点火 → 落地 → 停留 | **后视推近**（`follow=0.95`，y 锚中线）| `[2.30, 3.925]` s | **75** | 2.50 s |
| **B-h** | 落地停留 | 同上 | `3.925` s | **15** | 0.50 s |

合计 **210 帧 = 7.0000 s**，正好等于抖音屏 01 的 splice 时隙（210 帧），
`setpts` 比 **1.000** —— 不做任何时域拉伸。

## 与横屏（`sim_anim3d_v3.py`）同源、不同焦距口径

* A 段直接复用横屏的 `q34` 机位与 `solve_A_pan()`：**焦距按帧自算**
  （`a_focal_bound`），硬切点的画面平移由 `cut_pct` **代数地**解出 ⇒ 硬切不跳。
* `cut_pct` 不再手填：先按 B 段投影出**切换帧车心**在画面的百分比，再拿它当
  A 段的锚点 —— 两个镜头的衔接由构造保证，而不是"渲完再看"。
* B 段沿用竖屏机位（`D=8.5 m`），但 **`fk0` 从 1.30 降到 0.55**：
  切换点车还在 9.93 m 高空，`fk0=1.30` 会让它一进入 B 段就变成 28% 画宽
  （A 段末帧只有约 12%），硬切时尺寸突跳 2.3 倍。`fk0=0.55` 让切换点车宽
  与 A 段对齐，再用 2.5 s 把它推到 **15.6**（焦距 1.7 倍）—— 这就是"推近"。

## 三个必须守住的点

1. **相机跟"场景"、不跟车**：A 段 `follow=0.60`（横屏同一取值）；
   B 段虽 `follow=0.95`，但**横向 y 锚在跑道中线**（不跟横漂）——
   正因为不跟，车相对白线的偏移才留得下来。
2. **A 段五台障碍车必须 100% 在画内**（`--probe` 判据 ③）。
3. **去掉原始 HUD**：`draw_frame()` 会把 `3D 复刻〔A · 越车段〕…` 画成
   axes 标题，竖屏铺满画布时它贴在画面最上沿、且与卡片标题重复 ⇒ 渲染时清掉。

## 用法

    $PY episodes/2026-W55/scripts/sim_anim3d_9x16.py           # 7.0 s / 210 帧
    $PY episodes/2026-W55/scripts/sim_anim3d_9x16.py --probe    # 只做几何自检
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402
from matplotlib.animation import FuncAnimation, FFMpegWriter        # noqa: E402

EP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EP / "scripts"))

import car3d as c3                                                 # noqa: E402
import sim_anim3d_v3 as M                                          # noqa: E402

OUT = EP / "publish" / "视频" / "sim_jump_3d_9x16_raw.mp4"

# ★ **共用同一个 STATE 字典**：`M.probe()` 改的就是它。
#   若各建一份，几何自检量到的会是"另一台相机"（W55 实测过一次：
#   探针报切换点 Δ=0.0%、落地帧车跑到画外，全是读错 STATE 造成的假数）。
STATE = M.STATE
STATE["stage"] = "A"
STATE["close"] = False

# A 段：**3/4 斜侧视**，机位沿用横屏 `sim_anim3d_v3.A_CAM`（az=44°/pitch=10°/follow=0.60）。
#
# ## ★ 竖屏必须让**机位按帧跟焦**，不能固定平移
#
# 横屏用 `solve_A_pan()` 解出一个**固定** `(c_x,c_y)`：整段 A 都用同一个平移。
# 这套在 16:9 能成立，是因为画面够宽、`(u_max-u_c)` 与 `(u_c-u_min)` 都不紧。
# **竖屏照抄会塌**：A 段早期车还在车队**右侧**（x=0 时车心 u≈+0.30，
# 五车在 u∈[-0.38,-0.10]），车锚在 40% 处 ⇒ 焦距上界被
# `a/(u_c-u_min)=3.68/0.68≈5` 卡死，五车+车只占画宽 **37%**，其余 63% 是空的
# （实测预览：整幅内容压在画面中间一条 150 px 的带子里）。
#
# ⇒ 竖屏改成**锚点随帧移动**（等价于"摄像师跟拍"）：
#   * 起手车靠右（`A_A0=0.88`）、内容向左铺满画宽；
#   * 到硬切点**收敛到 B 段切换帧的车位**（`cut_pct`，由 B 段反解）
#     ⇒ 硬切不跳是**构造**保证，而不是渲完再调。
#   * 焦距仍按帧由 `a_focal_bound()` 闭式给出（该式对任意锚点都保证内容入画）。
A_CAM9 = dict(mode="q34", az=44.0, pitch=10.0, R=34.0,
              ax=0.0, ay=0.0, atz=1.0, follow=0.60, fk=0.985,
              pan=None, cut_pct=(40.0, 31.6), fmax=26.0)
A_A0, A_B0 = 0.88, 0.50       # A 段起手的车心位置（画宽 / 画高 比例）

# B 段：后视**推近**（焦距随高度推：`fk0` 高空 → `fk` 贴地），y 锚在跑道中线。
#   `az/bz` 让机位随车下沉：切换点车还在 9.93 m 高，钉在地面的机位会让它飞出画面。
#   `fk0=0.55`（≈焦距 5.06）让切换点车宽 ≈ 12%（与 A 段末帧对齐），
#   落地时 `fk=1.70`（焦距 15.64）⇒ 落地偏移 ≈ 15% 画宽。
B_CAM9 = dict(follow=0.95, D=8.5, tf=1.4, h0=4.6, az=0.75, tz0=1.0, bz=0.75,
              fk=1.70, fk0=0.55, zref=9.93, ey=-0.20)

T_CUT = 2.60          # 硬切时刻（最高点 2.083 s 之后的下落途中）
# ⚠️ 为什么不是 2.30：B 段机位在切换帧位于 `base-D`，而 `D=8.5` ⇒ 2.30 时
#    机位在 x≈26.1，**正落在五车队列中部那台 4 m 高的箱体上方**（x∈[24.9,31.1]）
#    ⇒ 广角（`fk0=0.55`）把它的顶面投成**占满画面下半幅的灰色大板**（实测抽帧，
#    只在切换后 2–3 帧，但那正是硬切后第一眼）。取 2.60 时机位 x≈30.9 已越过该箱体。
T_A_FROM = 0.00       # A 段起点（含起飞）
N_A = 120             # A 段 4.00 s
HOLD = 0.50           # 落地停留 0.50 s
DUR = 7.0             # = 210 帧，正好等于抖音屏 01 的 splice 时隙

# 跑道常量转发（measure_offset_px.py 仍按 `S9.X_BACK` 取，保持兼容）
LANE_HALF = M.LANE_HALF
X_BACK, X_FWD = M.X_BACK, M.X_FWD
RULER_HALF, RULER_STEP = M.RULER_HALF, M.RULER_STEP
draw_runway = M.draw_runway


def make_camera_portrait():
    r"""竖屏相机：**A/B 分段**。

    * B 段：直接用 `sim_anim3d_v3.make_cameras()`（后视推近）。
    * A 段：本文件自己算，锚点 `(a,b)` 按帧从 `(A_A0,A_B0)` 平滑收敛到
      `cut_pct`（B 段切换帧的车位），焦距仍由 `a_focal_bound()` 闭式给出。
    """
    b_make = M.make_cameras(A_CAM9, B_CAM9, state=STATE)

    def _cam(fr, w, h):
        if (STATE.get("stage") or "A") == "B":
            return b_make(fr, w, h)
        return _a_cam(fr, w, h)

    return _cam


# ==================== B 段不画障碍队列 ====================
# B 段是**后视推近**：机位在 `base-D`，其中 D=8.5 m，而车队沿 x 占 22.8 m
# ⇒ 切换点机位正落在队列上方，用 `fk0` 的广角（焦距 ≈5）向下看时，
#   最近那台箱体的**顶面**会被投成一块占满画面下半幅的灰板（实测抽帧确认，
#   颜色 154,159,165 = 障碍色 226,232,240 的受光面）。
# 横屏 B 段看不到队列，是因为它的 `fk0=1.6`（焦距 ≈14.7，垂直半视角 17°），
# 近地自然出画。竖屏为了在硬切点对齐 A 段车宽，必须用广角，于是撞上这条。
# ⇒ 与横屏 B 段保持一致：**B 段不画队列**（车已经飞过去了，队列在后视里没有信息；
#   落地偏移看的是地面刻度尺）。A 段完全不受影响（五车 100% 在画内）。
_ORIG_COLLECT = c3.collect_drawables


def collect_drawables_portrait(fr, cam, focal, cx, cy, row_x=None):
    if (STATE.get("stage") or "A") == "B":
        return _ORIG_COLLECT(fr, cam, focal, cx, cy, 1e6)   # |row_x-x|<22 失效
    if row_x is None:
        return _ORIG_COLLECT(fr, cam, focal, cx, cy)
    return _ORIG_COLLECT(fr, cam, focal, cx, cy, row_x)


c3.collect_drawables = collect_drawables_portrait


def _a_cam(fr, w: float, h: float):
    r"""A 段：**逐帧锚点**的 3/4 斜侧视。

    $$a(s)=(1-\beta)a_0+\beta a_{\rm cut},\quad
      b(s)=(1-\beta)b_0+\beta b_{\rm cut},\quad
      \beta=s^2(3-2s),\quad s=\frac{t-t_0}{t_{\rm cut}-t_0}$$

    $$F=\mathrm{fk}\cdot F_{\rm upper}(u_{\min},u_{\max},v_{\min},v_{\max};
      \bar u,\bar v;\;\tfrac a w,\tfrac b h),\qquad
      c_x=a-F\bar u,\;\;c_y=b+F\bar v$$

    `a_focal_bound` 保证"内容外接框 + 车心在 $(a,b)$"这一约束下 $F$ 取到闭式上界，
    故**任意锚点**都不会把五车或车挤出画面。
    """
    P = A_CAM9
    base = c3.ROW_X * (1.0 - P["follow"]) + fr.x * P["follow"]
    eye, aim = M._a_eye(P, base)
    cam = c3.make_cam(eye, aim)
    uv = M.content_uv(fr, cam)
    if uv is None:
        return cam, min(w, h) * 0.9, w * 0.5, h * 0.5
    bb, (uc, vc) = uv
    span = max(T_CUT - T_A_FROM, 1e-6)
    s = min(1.0, max(0.0, (fr.t - T_A_FROM) / span))
    beta = s * s * (3.0 - 2.0 * s)
    a = (1.0 - beta) * A_A0 * w + beta * P["cut_pct"][0] / 100.0 * w
    b = (1.0 - beta) * A_B0 * h + beta * P["cut_pct"][1] / 100.0 * h
    focal = P["fk"] * M.a_focal_bound(bb, uc, vc, w, h,
                                      (100.0 * a / w, 100.0 * b / h))
    focal = min(focal, float(P.get("fmax", 26.0)))
    return cam, focal, a - focal * uc, b + focal * vc


def car_rect(fr, cam, focal, cx, cy):
    r"""车体**真实轮廓**的屏幕包围框（`M.probe` 用的是同一份 `car_faces`）。"""
    ps = [c3.project(cam, v, focal, cx, cy)
          for (vs, _c, _ctr) in c3.car_faces(fr.x, fr.z, fr.theta, fr.y)
          for v in vs]
    if any(p is None for p in ps):
        return None
    xs = [p[0] for p in ps]
    ys = [p[1] for p in ps]
    return (min(xs), min(ys), max(xs), max(ys))


def row_boxes() -> list:
    r"""五台障碍车的包围盒 8 角（与 `car3d.collect_drawables` 同一份常量的推导）。"""
    return [[(x, y, z)
             for x in (c3.ROW_X + dx - L / 2, c3.ROW_X + dx + L / 2)
             for y in (-1.0, 1.0) for z in (0.0, Hx)]
            for (dx, L, Hx, _c) in c3.OBSTACLES]


def solve_cut_pct_from_b(cut_fr) -> tuple:
    r"""用 **B 段机位**投影切换帧车心 ⇒ A 段锚点 `cut_pct`（画面百分比）。

    这样两个镜头的衔接是**构造出来**的：A 段 `solve_A_pan()` 会把切换帧车心
    钉在同一处 ⇒ $\Delta x=\Delta y=0$ 附近，不靠"渲完再调"。
    """
    cam = make_camera_portrait()
    STATE["stage"] = "B"
    cam_, focal, cx, cy = cam(cut_fr, M.VIEW_W, M.VIEW_H)
    cr = car_rect(cut_fr, cam_, focal, cx, cy)
    STATE["stage"] = "A"
    if cr is None:
        return (40.0, 31.6)
    return (100.0 * (cr[0] + cr[2]) / 2 / M.VIEW_W,
            100.0 * (cr[1] + cr[3]) / 2 / M.VIEW_H)


def portrait_report(recs, idx, stages) -> dict:
    r"""竖屏验收判据（五车入画 / 车宽峰值 / 落地偏移），与画面同一条投影管线。"""
    W, H = M.VIEW_W, M.VIEW_H
    boxes = row_boxes()
    cam = make_camera_portrait()

    def rect(pts, focal, cx, cy, cam_):
        ps = [c3.project(cam_, p, focal, cx, cy) for p in pts]
        if any(p is None for p in ps):
            return None
        xs = [p[0] for p in ps]
        ys = [p[1] for p in ps]
        return (min(xs), min(ys), max(xs), max(ys))

    def inside(r, m=0.0):
        return (r is not None and r[0] >= m and r[1] >= m
                and r[2] <= W - m and r[3] <= H - m)

    # ③ A 段：五车 100% 在画内
    n5 = na = 0
    for k, st in zip(idx, stages):
        if st != "A":
            continue
        na += 1
        STATE["stage"] = "A"
        cam_, focal, cx, cy = cam(recs[k], W, H)
        ok = all(inside(rect(b, focal, cx, cy, cam_)) for b in boxes)
        n5 += bool(ok)

    # ④ A 段峰值帧（最高点）车宽占画宽
    ai = [(i, k) for i, (k, st) in enumerate(zip(idx, stages)) if st == "A"]
    i_pk, k_pk = max(ai, key=lambda t: recs[t[1]].z)
    STATE["stage"] = "A"
    cam_, focal, cx, cy = cam(recs[k_pk], W, H)
    crp = car_rect(recs[k_pk], cam_, focal, cx, cy)
    w_peak = (crp[2] - crp[0]) / W if crp else 0.0

    # ⑤ B 段落地帧：车心到中线占画宽 + 车是否完整入画
    t_land = next((r.t for r in recs if r.z <= 0.02 and r.t > 2.0), recs[-1].t)
    k_land = min(idx, key=lambda k: abs(recs[k].t - t_land))
    STATE["stage"] = "B"
    cam_, focal, cx, cy = cam(recs[k_land], W, H)
    crl = car_rect(recs[k_land], cam_, focal, cx, cy)
    q = c3.project(cam_, (recs[k_land].x, 0.0, 0.0), focal, cx, cy)
    off = abs(q[0] - (crl[0] + crl[2]) / 2) / W if (crl and q) else 0.0
    STATE["stage"] = "A"
    return {"na": na, "n5": n5, "w_peak": w_peak, "i_pk": i_pk,
            "off": off, "land_ok": inside(crl), "crl": crl,
            "w_land": (crl[2] - crl[0]) / W if crl else 0.0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--dur", type=float, default=DUR)
    ap.add_argument("--t-cut", type=float, default=T_CUT)
    ap.add_argument("--t-a-from", type=float, default=T_A_FROM)
    ap.add_argument("--n-a", type=int, default=N_A)
    ap.add_argument("--hold", type=float, default=HOLD)
    ap.add_argument("--probe", action="store_true", help="只做几何自检，不出片")
    ap.add_argument("--max-frames", type=int, default=0, help=">0 时只渲这么多帧（测速）")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    M.setup()
    # 视口比例**必须等于画布 1080:1920 = 0.5625**，否则 `set_aspect("equal")`
    # 会在上下留出同色 letterbox（旧版 9.2×16=0.575 ⇒ 上下各 10 px 暗带），
    # 而且 ffmpeg 再 scale 到 1080×1920 时会把画面纵向拉伸 2%。
    M.VIEW_W = 9.2
    M.VIEW_H = M.VIEW_W * 1920 / 1080          # = 16.3556
    M.GROUND_HOOK = M.draw_runway

    recs = M.ns.run_mission10_auto(1 / 120)
    t_land = next((r.t for r in recs if r.z <= 0.02 and r.t > 2.0), recs[-1].t)

    idx, stages, na, nb, nhold = M.build_timeline(
        recs, args.fps, args.dur, args.hold, args.t_cut,
        n_a=args.n_a, t_a_from=args.t_a_from, t_b_to=t_land)

    # ★ 先由 B 段解出 A 段的硬切锚点（硬切跳变由构造保证，不靠渲完再看）
    A_CAM9["cut_pct"] = solve_cut_pct_from_b(recs[idx[na - 1]])
    _c, f_cut, cx_cut, cy_cut = _a_cam(recs[idx[na - 1]], M.VIEW_W, M.VIEW_H)
    # ⚠️ `make_cameras()` 会把 `A_CAM9` **拷一份**（`dict(pa)`）⇒ A 段必须走
    #    本文件的 `_a_cam()`（每次现读 `A_CAM9`）。本轮实测过一次：先建相机、
    #    后解锚点 ⇒ 闭包里存的是 `pan=None` 的旧副本，画面按默认中心取景，
    #    而探针报的又是另一套数（探针 94/120、报告 104/120，两边都不是真值）。
    c3.camera_for = make_camera_portrait()

    print("=" * 78)
    print(f"  竖屏 9:16 · VIEW {M.VIEW_W}x{M.VIEW_H} · {args.fps} fps · "
          f"{len(idx)} 帧 = {len(idx)/args.fps:.4f} s（抖音时隙 210 帧）")
    print(f"  A 段 {na} 帧（{na/args.fps:.2f} s）：任务 t ∈ "
          f"[{recs[idx[0]].t:.2f}, {recs[idx[na-1]].t:.2f}] s "
          f"⇒ 慢放 {(na/args.fps)/max(recs[idx[na-1]].t - recs[idx[0]].t, 1e-6):.2f}×")
    print(f"  B 段 {nb} 帧（{nb/args.fps:.2f} s）+ 停留 {nhold} 帧"
          f"：任务 t ∈ [{recs[idx[na]].t:.2f}, {recs[idx[-1]].t:.2f}] s"
          f"（落地 {t_land:.2f}）"
          f"⇒ 慢放 {(nb/args.fps)/max(recs[idx[-1]].t - recs[idx[na]].t, 1e-6):.2f}×")
    print("  分段机位：A q34（az=44° pitch=10° follow=0.60）→ "
          "B 后视推近（follow=0.95，y 锚中线），硬切")
    print(f"  A 段锚点：起手 ({100*A_A0:.0f}%, {100*A_B0:.0f}%) → 硬切点 "
          f"({A_CAM9['cut_pct'][0]:.1f}%, {A_CAM9['cut_pct'][1]:.1f}%)"
          f"（由 B 段切换帧反解）")
    print(f"     切换帧焦距 F_cut={f_cut:.2f}"
          f"  pan=({cx_cut:.2f},{cy_cut:.2f})"
          f"  ⇒ 与 B 段首帧同位（硬切 Δ≈0）")
    print("=" * 78)

    rep = portrait_report(recs, idx, stages)
    print(f"  ③ A 段五车**全部**在画内：{rep['n5']}/{rep['na']}"
          f"（{100*rep['n5']/max(rep['na'],1):.1f}%）  "
          f"{'[OK]' if rep['n5'] == rep['na'] and rep['n5'] > 0 else '[X]'}")
    print(f"  ④ A 段峰值帧 #{rep['i_pk']} t={recs[idx[rep['i_pk']]].t:.3f}s："
          f"车宽 {100*rep['w_peak']:.1f}% 画宽（门槛 10.0%）  "
          f"{'[OK]' if rep['w_peak'] >= 0.10 else '[X]'}")
    print(f"  ⑤ B 段落地帧：偏移 {100*rep['off']:.2f}% 画宽（门槛 8.00%）｜"
          f"车宽 {100*rep['w_land']:.1f}%｜"
          f"车{'完整入画' if rep['land_ok'] else '[X] 被切'}  "
          f"{'[OK]' if rep['off'] >= 0.08 and rep['land_ok'] else '[X]'}")
    print(f"  ⑥ 帧数：{len(idx)} 帧 / {len(idx)/args.fps:.4f} s"
          f"（setpts 比 = 时隙/片段 = 210/210 = 1.000）")

    if args.probe:
        return M.probe(recs, idx, stages, args.fps, w_peak_min=0.10)

    fig = plt.figure(figsize=(8.0, 8.0 * 1920 / 1080), dpi=135)   # = 1080×1920
    fig.patch.set_facecolor("#0b1220")
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    n_frames = len(idx) if not args.max_frames else min(len(idx), args.max_frames)

    # ⚠️ 两行小字必须**建一次、逐帧改 alpha**。
    #    上一版在 `upd()` 里每帧新建一个 `fig.text(...)`，而旧的从不删除 ⇒
    #    到 B 段时画面上同时叠着 A 段那几十个"3/4 斜视 ｜ 飞越五车"副本，
    #    与"落地：偏在白线一侧"重影（实测预览：两行字糊成一行）。
    lab_a = fig.text(0.08, 0.075, "3/4 斜视 ｜ 飞越五车", ha="left", va="center",
                     color="#c9d8e8", fontsize=27, alpha=0.0)
    lab_b = fig.text(0.92, 0.075, "落地：偏在白线一侧", ha="right", va="center",
                     color="#c9d8e8", fontsize=27, alpha=0.0)

    def upd(i):
        k = idx[i]
        STATE["stage"] = stages[i]
        STATE["close"] = stages[i] == "B"
        M.RULER_ON = STATE["close"]        # 刻度尺只在落地段
        M.draw_frame(ax, recs[k], recs[:k + 1])
        ax.set_title("")                   # ★ 去掉横屏那张 HUD（竖屏卡片自带标题）
        if stages[i] == "B":
            hp = (i - na) / max(len(idx) - na - 1, 1)
            lab_a.set_alpha(0.0)
            lab_b.set_alpha(min(1.0, max(0.0, (hp - 0.20) / 0.40)))
        else:
            hp = i / max(na - 1, 1)
            lab_b.set_alpha(0.0)
            lab_a.set_alpha(min(1.0, max(0.0, (0.18 - hp) / 0.10)))

    out = Path(args.out) if args.out else OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    anim = FuncAnimation(fig, upd, frames=n_frames,
                         interval=1000 / args.fps, repeat=False)
    anim.save(str(out), writer=FFMpegWriter(fps=args.fps, bitrate=5000))
    plt.close(fig)
    dt = time.time() - t0
    print(f"  [OK] {out.name}  {out.stat().st_size/1e6:.2f} MB"
          f"  {n_frames} 帧  用时 {dt:.1f}s（{dt/max(n_frames,1):.2f}s/帧）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
