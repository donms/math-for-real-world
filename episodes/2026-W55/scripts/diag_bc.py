#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""诊断 **B+C 方案**：同侧两竖推滚转 + 侧推配平。

## 要验的三件事

1. **滚转是否转够**（362° 左右）；
2. **侧推是否真的在配平**（$F_s\approx 2F\tan\theta$，且被 `SIDE_MAX` 限幅）；
3. **残余横漂有多大** —— 这是 B+C 的固有代价，必须如实报告。

## 理论预期

$$\tau_x=2\times0.55F=1.1F\ \Rightarrow\ F=\frac{J\alpha}{1.1}$$

$$F_s=2F\tan\theta\ \text{（}\theta\to90°\text{ 发散 ⇒ 必须限幅）}$$

**⇒ 限幅之后必有残余横漂，大小取决于 $\theta$ 超过多少度开始饱和。**
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nozzle_state as ns     # noqa: E402
import physics as ph          # noqa: E402

P = 1.0 / 150


def main() -> int:
    recs = ns.run_mission10_auto(P)
    t0 = ns.run_mission10.t_burn
    win = getattr(ns.run_mission10, "roll_win", None)

    print("=" * 84)
    print("  B+C 方案诊断（同侧两竖推 + 侧推配平）")
    print("=" * 84)
    print(f"\n  滚转窗 = ({win[0]:.3f}, {win[1]:.3f}) s"
          f" ⇒ 结束于 {win[0] + win[1]:.3f} s" if win else "  [无滚转窗]")
    if win:
        alpha = ph.bang_bang_alpha(2 * math.pi, win[1])
        F_b = ph.J_ROLL * alpha / ns.ROLL_ARM_PAIR
        print(f"  α = {alpha:.3f} rad/s²，τ = {ph.J_ROLL*alpha/1000:.2f} kN·m")
        print(f"  同侧两喷各需 F = τ/1.1 = **{F_b/1000:.2f} kN**"
              f"（共 {2*F_b/1000:.2f} kN 竖直力）")
        print(f"  侧推限幅 SIDE_MAX = {ns.SIDE_MAX/1000:.1f} kN")

    if not win:
        return 1
    in_win = [r for r in recs if win[0] <= r.t <= win[0] + win[1]]
    if not in_win:
        print("  [窗内无记录]")
        return 1

    print(f"\n  {'t':>6}{'θ(°)':>7}{'τx(kN·m)':>10}{'τy':>7}{'τz':>7}"
          f"{'FL':>6}{'RL':>6}{'FR':>6}{'RR':>6}{'S+':>6}{'S-':>6}")
    for r in in_win[:: max(1, len(in_win) // 12)]:
        print(f"  {r.t:>6.2f}{math.degrees(r.theta):>7.0f}"
              f"{r.tau/1000:>10.2f}{r.tau_y/1000:>7.2f}{r.tau_z/1000:>7.2f}"
              f"{r.duty.get('LIFT_FL', 0):>6.2f}{r.duty.get('LIFT_RL', 0):>6.2f}"
              f"{r.duty.get('LIFT_FR', 0):>6.2f}{r.duty.get('LIFT_RR', 0):>6.2f}"
              f"{r.duty.get('SIDE_P', 0):>6.2f}{r.duty.get('SIDE_N', 0):>6.2f}")

    d_deg = math.degrees(in_win[-1].theta - in_win[0].theta)
    tx_avg = sum(abs(r.tau) for r in in_win) / len(in_win)
    ty_pk = max(abs(r.tau_y) for r in in_win)
    tz_pk = max(abs(r.tau_z) for r in in_win)
    print(f"\n  窗内转过 **{d_deg:.1f}°**")
    print(f"  |τx| 均值 {tx_avg/1000:.2f} kN·m")
    print(f"  |τy| 峰值 {ty_pk/1000:.3f} kN·m"
          f"（相对 {ty_pk/max(tx_avg,1)*100:.2f}%）")
    print(f"  |τz| 峰值 {tz_pk/1000:.3f} kN·m"
          f"（相对 {tz_pk/max(tx_avg,1)*100:.2f}%）")

    last = recs[-1]
    print(f"\n  末态：θ = {math.degrees(last.theta):+.1f}°，"
          f"x = {last.x:.2f} m")
    print(f"         y = {last.y*100:+.1f} cm，vy = {last.vy:+.3f} m/s")
    print(f"  峰值高度 {max(r.z for r in recs):.2f} m，"
          f"耗气 {last.m_total:.1f} kg，末端罐压 {last.p_mPa:.1f} MPa")

    print("\n" + "=" * 84)
    print("  ★ B+C 的固有代价：残余横漂")
    print("=" * 84)
    print(f"  横向位移 **{last.y*100:+.1f} cm**，横向速度 **{last.vy:+.3f} m/s**")
    print(f"  对比 D（力偶）：横向 −50 cm / −0.76 m/s")
    print("=" * 84)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
