#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""诊断：加上起飞推进段后，为什么落地 $v_z$ 变成 −2.28。

## 期望链路

1. 四竖推全推力（4×20 kN @ 满罐）点火，$a = 40 - 9.81 = 30.2\ \text{m/s}^2$；
2. 到 $z + v_z^2/2g \ge 7.74$ 熄火；
3. 惯性爬升到 7.74 m；
4. 下落，$z\le2.5$ 时缓冲控制器冻结所需推力；
5. 落地 $v_z \approx -0.5$。

## 要查的三件事

* 熄火时刻与熄火高度；
* 缓冲触发时的 $(z, v_z)$ 与冻结的 $F$；
* **此时罐压还能给多大推力**（起飞耗气会让压降，这是新出现的耦合）。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph          # noqa: E402
import nozzle_state as ns     # noqa: E402
import nozzles as nz          # noqa: E402


def main() -> int:
    print("=" * 84)
    print("  起飞推进段 + 缓冲 诊断")
    print("=" * 84)

    recs = ns.run_mission10(1 / 120)
    print(f"\n  步数 {len(recs)}，时长 {recs[-1].t:.2f} s")
    print(f"  峰值 {max(r.z for r in recs):.2f} m，"
          f"落地 vz {recs[-1].vz:+.2f} m/s")

    # 找起飞熄火：竖推首次全部不点火
    lift4 = ("LIFT_FL", "LIFT_FR", "LIFT_RL", "LIFT_RR")
    t_burn = None
    for r in recs:
        if all(r.f.get(n, 0.0) < 1.0 for n in lift4) and r.vz > 0:
            t_burn = r.t
            z_burn = r.z
            vz_burn = r.vz
            break
    if t_burn is not None:
        print(f"\n【1】熄火时刻 t = {t_burn:.3f} s")
        print(f"     熄火高度 z = {z_burn:.2f} m，vz = {vz_burn:.2f} m/s")
        print(f"     剩余可爬升 vz²/2g = {vz_burn**2/(2*ph.G):.2f} m")
        print(f"     合计 → {z_burn + vz_burn**2/(2*ph.G):.2f} m"
              f"（目标 {ph.H_JUMP}）")
    else:
        print("\n【1】★ 没找到熄火时刻（竖推一直没停？）")

    # 缓冲触发
    trig = None
    for r in recs:
        if r.z <= ph.Z_TRIGGER and r.vz < 0:
            trig = r
            break
    if trig is not None:
        print(f"\n【2】缓冲触发 t = {trig.t:.3f} s，"
              f"z = {trig.z:.3f} m，vz = {trig.vz:.2f} m/s")
        need = ph.M_CAR * ((trig.vz ** 2 - ph.VZ_SAFE ** 2)
                           / (2 * trig.z) + ph.G)
        print(f"     所需推力 = {need/1000:.1f} kN")
        # 当时的罐压与四竖推能力
        p_now = trig.p_mPa * 1e6
        at_lift = nz.area_for_force(20e3, ph.P_TANK)
        f_each = nz.force_of_area(at_lift, p_now)
        print(f"     当时罐压 {trig.p_mPa:.1f} MPa ⇒ "
              f"每竖推 {f_each/1000:.1f} kN，四个 {4*f_each/1000:.1f} kN")
        print(f"     ⇒ {'够' if 4*f_each >= need else '★ 不够'}")

    print(f"\n【3】末段逐帧（倒序 8 步）")
    print(f"     {'t':>6}{'z':>8}{'vz':>8}{'fz总(kN)':>11}{'罐压':>8}")
    for r in recs[-8:]:
        print(f"     {r.t:>6.2f}{r.z:>8.2f}{r.vz:>8.2f}"
              f"{sum(r.f.get(n,0) for n in lift4)/1000:>11.1f}"
              f"{r.p_mPa:>8.1f}")

    print("\n" + "=" * 84)
    print("  ★ 判读")
    print("=" * 84)
    print("  · 若触发点『不够』⇒ 起飞耗气把罐压拉低，缓冲推力不足；")
    print("  · 解决办法：把缓冲触发高度提高（F ∝ 1/z，越早越省力），")
    print("    或把竖推喉部面积加大（同样压力下推力更大）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
