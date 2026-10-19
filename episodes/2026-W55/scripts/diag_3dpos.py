#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""诊断：车身的 **世界 $z$ 范围** 是否贴在物理高度 $r.z$ 附近。

## 为什么需要这个检查

这一期有两次"车沉到地下 / 轮子跑到车顶"的错，**根因都是高度基准算错**。
本脚本把所有顶点投影到世界系，直接打印 $z$ 的上下界：

* **应当**满足 $z_{\min} \approx r.z$（轮底贴地）；
* $z_{\max} \approx r.z + 1.19$（车顶）。

**差得远就说明 `BODY_LIFT` 或轮心 $oz$ 又算错了。**

> ★ 这正是"用可复现的检查代替肉眼"的尝试：
> 前几次高度错都是用户先看出来的，机器没有守住。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nozzle_state as ns     # noqa: E402
import car3d as c3            # noqa: E402


def main() -> int:
    print("=" * 78)
    print("  车身世界 z 范围诊断")
    print("=" * 78)
    top = c3.BODY_LIFT + 0.25 + 0.02
    print(f"  BODY_LIFT = {c3.BODY_LIFT}，轮半径 = {c3.R_WHEEL}")
    print(f"  预期：z_min ≈ r.z（轮底贴地），z_max ≈ r.z + {top:.2f}")

    recs = ns.run_mission10_auto(1 / 150)
    print(f"\n  {'t':>6}{'r.z':>8}{'θ(°)':>8}"
          f"{'z_min':>9}{'z_max':>9}{'z_min-r.z':>12}{'判定':>7}")
    bad = 0
    for frac in (0.0, 0.10, 0.22, 0.34, 0.46, 0.58, 0.72, 0.86, 0.94, 0.995):
        k = min(len(recs) - 1, int(len(recs) * frac))
        r = recs[k]
        zs = [v[2] for faces, _c, _ctr in c3.car_faces(r.x, r.z, r.theta)
              for v in faces]
        zmin, zmax = min(zs), max(zs)
        dz = zmin - r.z
        # ★★★ 只在"接近正立"时判定。
        #   车身是刚体，绕中心滚转后最低点本就会离开轮底平面：
        #   滚 θ 角时单侧车轮下移 ≈ Y_TRACK·sinθ（θ=4° 时约 7 cm）。
        #   滚到 90° 时"最低点"已经是车身侧面，与 r.z 无可比性。
        deg = (r.theta * 57.2958) % 360.0
        upright = min(deg, 360.0 - deg) < 6.0
        if upright:
            ok = abs(dz) <= 0.15
            if not ok:
                bad += 1
            tag = '  ✓' if ok else '  ✗'
        else:
            tag = '  —'
        print(f"  {r.t:>6.2f}{r.z:>8.2f}"
              f"{r.theta * 57.2958:>8.0f}{zmin:>9.2f}{zmax:>9.2f}"
              f"{dz:>12.3f}{tag:>7}")

    print("\n" + "=" * 78)
    if bad == 0:
        print("  ★ 正立时刻全部正常（轮底贴地），滚转中的偏离属刚体正常行为")
    else:
        print(f"  ★ {bad} 个时刻高度异常 ⇒ 检查 BODY_LIFT / 轮心 oz")
    print("=" * 78)
    return 0 if bad == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
