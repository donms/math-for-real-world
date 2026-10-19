#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **用"画出来的像素"量落地帧的横向偏移**（不依赖任何模型坐标）。

## 为什么必须这么量

我先前用 `c3.project(fr.x, fr.y, fr.z)` 得到"车心在 37.2%、线在 50%"，
据此报"偏 138 px"。用户看渲染图：**车看起来正压在线上**。

根因（用户指出）：**`fr` 是车的坐标原点（pivot），不是车身的视觉中心。**
车体是若干 box 拼的，尾翼和立柱还把包围盒拉宽 ⇒
"原点偏 138 px"与"车看起来在正中"**可以同时为真**。

$$\boxed{\text{别投影"原点"，要量"画出来的包围盒中心"}}$$

## 做法

1. **只画车**（不画地面/跑道/线），透明背景存 PNG ⇒ 取 alpha>0 的**包围盒中心**
2. **只画中线**（不画车），取黄像素的平均 x
3. `offset_px = cx_line - cx_car`，报 `offset_px / 画宽`

## 验收（用户定）

$$\text{offset\_px} / \text{画宽} \ge 8\%\quad\text{才算"看得出"}$$

同时打印三个数核对：
① 车的世界 y ② 车原点投影的屏幕 x ③ 车像素包围盒中心 x

## ★ 两个必须守住的实现细节

**① 机位从仿真脚本里 import，不手抄。**
旧版把落地段机位复制了一份常量，`car3d.car_faces` 修好 `y0` 之后车真的偏
0.92 m，**同一机位下车被切掉左半**（包围盒 x∈[0,642]）—— 而复制的那份常量
**永远不会跟着变**。现在直接调仿真脚本的相机工厂。

**② 画布几何也从仿真脚本里取。**
`--view 16x9` 用的是 `sim_anim3d_v3` 的 `FIG_W/FIG_H/DPI/AX_RECT`：
它的坐标轴框只占画宽的 1141/1300（`set_aspect("equal")` 的留边），
分母必须用**真实画宽**，否则会把偏移量高估 14%。

## 用法

    $PY scripts/measure_offset_px.py                 # 竖屏 9:16（1080 宽）
    $PY scripts/measure_offset_px.py --view 16x9     # 横屏 B站（1300 宽）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                  # noqa: E402
from matplotlib.collections import PolyCollection                 # noqa: E402

EP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EP / "scripts"))

import car3d as c3                                                # noqa: E402
import nozzle_state as ns                                         # noqa: E402
import sim_anim3d_v3 as M                                         # noqa: E402
import sim_anim3d_9x16 as S9                                      # noqa: E402

OUT = EP.parents[1] / ".workbuddy" / "tmp" / "w55_s01"
OUT.mkdir(parents=True, exist_ok=True)

THRESH = 0.08          # 用户定的门槛：8% 画宽

VIEWS = {
    "9x16": dict(w=9.2, h=16.0, figw=8.0, figh=14.22, dpi=135,
                 rect=[0.0, 0.0, 1.0, 1.0], label="竖屏 9:16（抖音）"),
    "16x9": dict(w=M.VIEW_W, h=M.VIEW_H, figw=M.FIG_W, figh=M.FIG_H, dpi=M.DPI,
                 rect=list(M.AX_RECT), label="横屏 16:9（B站屏 02/08）"),
}


def landing_rec(dt: float = 1 / 120):
    recs = ns.run_mission10_auto(dt)
    ia = max(range(len(recs)), key=lambda i: recs[i].z)
    for i in range(ia, len(recs)):
        if recs[i].z <= 0.02:
            return recs[i]
    return recs[-1]


def video_cam(view: str):
    r"""**视频里那台相机**：直接问仿真脚本要，不复制常量。

    两个变体都取 **B 段（落地段）** 机位：
    横屏 → `sim_anim3d_v3.B_CAM`；竖屏 → `sim_anim3d_9x16.B_CAM9`。
    """
    if view == "16x9":
        M.STATE["stage"] = "B"
        return M.make_cameras(M.A_CAM, M.B_CAM)
    S9.STATE["stage"] = "B"
    S9.STATE["close"] = True
    return S9.make_camera_portrait()


def fig_ax(v: dict):
    fig = plt.figure(figsize=(v["figw"], v["figh"]), dpi=v["dpi"])
    ax = fig.add_axes(v["rect"])
    ax.set_xlim(0, v["w"])
    ax.set_ylim(v["h"], 0)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_alpha(0)
    ax.set_facecolor("none")
    return fig, ax


def alpha_bbox(path: Path):
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    a = im.split()[3]
    bb = a.getbbox()
    if not bb:
        return None, im.size
    return bb, im.size


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--view", default="9x16", choices=sorted(VIEWS))
    ap.add_argument("--out-tag", default="")
    args = ap.parse_args()
    v = VIEWS[args.view]
    W, H = v["w"], v["h"]

    fr = landing_rec()
    cam, focal, cx, cy = video_cam(args.view)(fr, W, H)
    print("=" * 84)
    print(f"  落地帧像素级横向偏移测量 · {v['label']}")
    src = ("  相机取自 sim_anim3d_v3.B_CAM（不是手抄常量）"
           if args.view == "16x9" else
           "  相机取自 sim_anim3d_9x16.B_CAM9（不是手抄常量）")
    print(src)
    print("=" * 84)
    print(f"  VIEW {W}×{H}   画布 {v['figw']}×{v['figh']} in @ {v['dpi']} dpi"
          f"   坐标轴框 {v['rect']}")
    print("  模型：x=%.3f y=%.3f z=%.3f  t=%.3f" % (fr.x, fr.y, fr.z, fr.t))

    # ---- ① 只画车 ----
    tag = args.out_tag or args.view
    p_car = OUT / f"only_car_{tag}.png"
    fig, ax = fig_ax(v)
    draws = c3.collect_drawables(fr, cam, focal, cx, cy)
    ax.add_collection(PolyCollection(
        [d[0] for d in draws], facecolors=[d[1] for d in draws],
        edgecolors="none", zorder=1))
    fig.savefig(p_car, transparent=True, dpi=v["dpi"])
    plt.close(fig)
    bb, sz = alpha_bbox(p_car)
    px_w, px_h = sz
    car_cx = (bb[0] + bb[2]) / 2.0 if bb else None
    car_w = (bb[2] - bb[0]) if bb else 0
    print("  ① 车：包围盒 %s  宽 %d px  中心 x=%.1f px"
          % (str(bb), car_w, car_cx or -1))

    # ---- ② 只画中线（与 draw_runway 完全同一套写法：y=0 的虚线）----
    p_line = OUT / f"only_line_{tag}.png"
    fig, ax = fig_ax(v)
    x0, x1 = fr.x - M.X_BACK, fr.x + M.X_FWD
    xx = x0
    while xx < x1:                      # DASH_ON 实、DASH_OFF 空，同 draw_runway
        a = c3.project(cam, (xx, 0.0, 0.0), focal, cx, cy)
        b = c3.project(cam, (min(xx + M.DASH_ON, x1), 0.0, 0.0), focal, cx, cy)
        if a and b:
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#f5c542", lw=1.8,
                    solid_capstyle="butt")
        xx += M.DASH_ON + M.DASH_OFF
    fig.savefig(p_line, transparent=True, dpi=v["dpi"])
    plt.close(fig)
    bb2, _ = alpha_bbox(p_line)
    line_cx = (bb2[0] + bb2[2]) / 2.0 if bb2 else None
    print("  ② 线：包围盒 %s  中心 x=%.1f px" % (str(bb2), line_cx or -1))

    # ---- ③ 三个数核对 ----
    q = c3.project(cam, (fr.x, fr.y, fr.z), focal, cx, cy)
    px_pivot = (q[0] / W) * px_w if q else None
    print("\n  三个数放一起：")
    print("     ① 世界 y            = %.4f m" % fr.y)
    print("     ② 原点投影的屏幕 x  = %.1f px" % (px_pivot or -1))
    print("     ③ 像素包围盒中心 x  = %.1f px" % (car_cx or -1))
    print("        （②−③ = %.1f px ⇒ pivot 与视觉中心的差）"
          % ((px_pivot or 0) - (car_cx or 0)))

    rc = 0
    print("\n  " + "-" * 78)
    if car_cx and line_cx:
        off = line_cx - car_cx
        frac = abs(off) / px_w
        print("  ★ offset_px = %.1f px   占画宽 %.2f%%   （门槛 %.0f%%）"
              % (off, 100 * frac, 100 * THRESH))
        print("    车宽 %.1f px 占画宽 %.1f%%" % (car_w, 100 * car_w / px_w))
        print("    （占 16 单位视口 = %.2f%%；成片里该视口换算见报告）"
              % (100 * abs(off) / (px_w * (1140.87 / 1300))
                 if args.view == "16x9" else 100 * abs(off) / px_w))
        ok_off = frac >= THRESH
        clip_l, clip_r = bb[0] <= 0, bb[2] >= px_w
        clip_t, clip_b = bb[1] <= 0, bb[3] >= px_h
        print("    车是否被切：左=%s 右=%s 上=%s 下=%s"
              % (clip_l, clip_r, clip_t, clip_b))
        ok_clip = not (clip_l or clip_r or clip_t or clip_b)
        print("    判定：偏移 %s ｜ 完整入画 %s"
              % ("[OK]" if ok_off else "[X] 太小", "[OK]" if ok_clip else "[X] 被切"))
        rc = 0 if (ok_off and ok_clip) else 1
    else:
        print("  [X] 取不到车或线的包围盒")
        rc = 1
    print("\n  产物：%s" % OUT)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
