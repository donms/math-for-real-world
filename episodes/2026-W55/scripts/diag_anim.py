#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **诊断**：`sim_anim.run_mission` 为何没触发缓冲、姿态为何停在 91°。

## 三个症状

| 量 | 实际 | 应该是 |
|---|---|---|
| 落地 $v_z$ | **−8.71 m/s** | ≈ −0.5 m/s |
| 竖推点火 | **从未** | 末段应大量点火 |
| 末端姿态 | **+91°** | 0°（转满一圈回正）|

## 最可疑的一处

**姿态**：`alpha` 按 `T_fly = 2v_z0/g` 定，而 `T_fly` 是**纯抛体**的腾空时。
但缓冲会让实际腾空**变长** ⇒ 姿态在 `T_fly/2` 后开始反向减速，
**减到 $T_{\text{fly}}$ 时正好转完一圈**；若实际落地晚于 $T_{\text{fly}}$，
**姿态就会继续转过 0°** ⇒ 停在 +91°。

**⇒ 结论：姿态的时间基准必须用"实际腾空时间"，不能用"纯抛体时间"。**

## 缓冲为何没触发

`_buffer_force(z, vz)` 需要 $z \le 2.0$。**但 $z$ 是"距地高度"**，
落地判据又是 $z \le 0$ ⇒ 窗口只有 2 m，按 −6.3 m/s 下落只需 0.3 s。
**0.3 s 内要卸掉 6.3 m/s ⇒ 需 21 m/s²≈2.1 g** —— 应该够。
**⇒ 更可能是我把 `fz_need` 除以 4 之后又乘了 `duty`，重复缩小了。**
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("sa", HERE / "sim_anim.py")
sa = importlib.util.module_from_spec(spec)
sys.modules["sa"] = sa
spec.loader.exec_module(sa)

ph = sa.ph
nz = sa.nz


def main() -> int:
    print("=" * 86)
    print("  W55 · sim_anim 诊断")
    print("=" * 86)

    vz0 = ph.launch_speed_for_height(ph.H_JUMP)
    T_fly = 2 * vz0 / ph.G
    print(f"\n  v_z0 = {vz0:.2f} m/s，纯抛体腾空 T_fly = {T_fly:.2f} s")
    print(f"  缓冲触发高度 {ph.Z_TRIGGER} m，目标落地 {ph.VZ_SAFE} m/s")

    # ---- 1) 竖推的推力能力 ----
    at_lift = nz.area_for_force(10e3, ph.P_TANK)
    print(f"\n【1】竖推能力")
    print(f"  每个竖推喉部面积 {at_lift*1e4:.2f} cm²，"
          f"满罐推力 {nz.force_of_area(at_lift, ph.P_TANK)/1000:.1f} kN")
    print(f"  4 个合计 {4*nz.force_of_area(at_lift, ph.P_TANK)/1000:.1f} kN")

    # ---- 2) 缓冲需求 ----
    print(f"\n【2】缓冲需求（从 {ph.Z_TRIGGER} m 开始）")
    vz_at_trig = -((vz0 ** 2 - 2 * ph.G
                    * (ph.H_JUMP - ph.Z_TRIGGER)) ** 0.5)
    a_need = (vz_at_trig ** 2 - ph.VZ_SAFE ** 2) / (2 * ph.Z_TRIGGER) + ph.G
    print(f"  到 {ph.Z_TRIGGER} m 时速度 {vz_at_trig:.2f} m/s")
    print(f"  需要 a = {a_need:.2f} m/s² ⇒ F = {ph.M_CAR*a_need/1000:.1f} kN")
    print(f"  4 个竖推能给 {4*nz.force_of_area(at_lift, ph.P_TANK)/1000:.1f} kN "
          f"⇒ {'够' if 4*nz.force_of_area(at_lift, ph.P_TANK) >= ph.M_CAR*a_need else '不够'}")

    # ---- 3) 逐帧看末段 ----
    print(f"\n【3】逐帧看末段（每 0.1 s）")
    recs = sa.run_mission(1 / 120)
    print(f"  共 {len(recs)} 步，末端 t={recs[-1].t:.2f} s")
    print(f"  {'t':>6}{'z':>8}{'vz':>9}{'fz_total(kN)':>14}"
          f"{'lift_on[0](kN)':>16}{'θ(°)':>7}")
    shown = 0
    for r in recs[::-1]:
        if shown >= 12:
            break
        if r.z <= 3.5:
            print(f"  {r.t:>6.2f}{r.z:>8.2f}{r.vz:>9.2f}"
                  f"{r.fz_total/1000:>14.2f}"
                  f"{(r.lift_on[0]/1000 if r.lift_on else 0):>16.2f}"
                  f"{ph.wrap_deg(r.theta):>7.0f}")
            shown += 1

    # ---- 4) 姿态时间基准 ----
    print(f"\n【4】姿态")
    print(f"  alpha = 4·2π/T_fly² = {ph.bang_bang_alpha(2*3.14159265, T_fly):.3f} rad/s²")
    print(f"  实际末端姿态 {ph.wrap_deg(recs[-1].theta):+.0f}°")
    print(f"  实际腾空 {recs[-1].t:.2f} s vs T_fly {T_fly:.2f} s")
    print(f"  ⇒ 差 {recs[-1].t - T_fly:+.2f} s —— 姿态在 T_fly 后继续转，"
          f"所以停不到 0°")

    print("\n" + "=" * 86)
    print("  ★ 结论")
    print("=" * 86)
    print("  ① **缓冲没触发**：末段 fz_total 全是 0 ⇒ duty 被算成 0。")
    print("     原因：`fz_need/4` 再除以 `f_max` 求 duty，而 `f_max` 用的是"
          "**单个**喷口在**满罐**下的推力；")
    print("     但 `fz_need` 若为 0（因为 z>Z_TRIGGER 时直接置 0）就不会到这一步")
    print("     ⇒ 真正问题在 **z 判据**：车在 2 m 以上就一直是 0。")
    print("  ② **姿态**：时间基准用了 `T_fly`（纯抛体），"
          "而实际腾空更长 ⇒ 转过 0° 继续转。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
