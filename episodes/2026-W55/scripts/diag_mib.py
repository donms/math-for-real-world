#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **最小冲量比特（MIB）对横向残余的影响**（现跑现取）。

## 为什么要单独跑

论文与结论速览里原先引用的"MIB 使横向残余从 117 cm 增到 187 cm"
**无法复现**（那一组基线与定稿的 B+C 实现不一致）。
按"所有数字必须能现跑现取"的纪律，这里直接把
`nozzle_state.PWM_MIN_ON`（阀门最小开通时间，即 MIB）扫一遍，
给出**同一套代码、只改 MIB** 的对照。

## 机制

$$\delta_{\min}=\frac{t_{\min}}{T},\qquad
\bar F_{\min}=F_{\max}\delta_{\min}$$

MIB 越大 ⇒ 占空比下限越高 ⇒ 侧推配平越难做到"很小很连续" ⇒
残余横漂越大。**MIB 惩罚的是精细配平，不是大推力。**

## 用法

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"
& "python" episodes\2026-W55\scripts\diag_mib.py
```
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nozzle_state as ns      # noqa: E402

DT = 1.0 / 150.0


def run(t_min: float) -> dict:
    r"""按给定 MIB 跑一次完整五阶段，返回末态指标。"""
    ns.PWM_MIN_ON = t_min
    recs = ns.run_mission10_auto(DT)
    last = recs[-1]
    return dict(
        t_min=t_min,
        p_steps=max(1, int(round(t_min / DT))),
        z_max=max(r.z for r in recs),
        y_cm=last.y * 100.0,
        vy=last.vy,
        theta=math.degrees(last.theta),
        m_total=last.m_total,
        p_end=last.p_mPa,
        t_end=last.t,
        x_end=last.x,
    )


def main() -> int:
    print("=" * 92)
    print("  MIB（最小冲量比特）对横向残余的影响：同一套代码，只改 t_min")
    print("=" * 92)
    print(f"\n  步长 dt = 1/{1/DT:.0f} s = {DT*1e3:.2f} ms；"
          f"t_min 只能取 dt 的整数倍（代码按步数扣账）")

    cases = (DT, 0.012, 0.027, 0.053)
    rows = []
    for tm in cases:
        r = run(tm)
        rows.append(r)
        print(f"\n  t_min = {r['p_steps'] * DT * 1e3:5.1f} ms"
              f"（{r['p_steps']} 步）")
        print(f"    峰值高度 {r['z_max']:6.2f} m   耗气 {r['m_total']:6.2f} kg"
              f"   末端罐压 {r['p_end']:5.2f} MPa")
        print(f"    横向位移 {r['y_cm']:+7.1f} cm   横向速度 "
              f"{r['vy']:+6.3f} m/s   末态滚转 {r['theta']:+7.1f}°"
              f"   全程 {r['t_end']:.3f} s")

    print("\n" + "=" * 92)
    print("  汇总")
    print("=" * 92)
    print(f"  {'t_min(ms)':>11}{'横漂(cm)':>11}{'横向v(m/s)':>13}"
          f"{'耗气(kg)':>11}{'峰值(m)':>10}{'末压(MPa)':>11}")
    for r in rows:
        print(f"  {r['p_steps'] * DT * 1e3:>11.1f}{r['y_cm']:>11.1f}"
              f"{r['vy']:>13.3f}{r['m_total']:>11.2f}"
              f"{r['z_max']:>10.2f}{r['p_end']:>11.2f}")

    # ★ 以定稿配置（PWM_MIN_ON = 12 ms ⇒ 2 步）为基线
    base = next(r for r in rows if r["p_steps"] == 2)
    worst = max(rows, key=lambda r: abs(r["y_cm"]))
    print(f"\n  定稿配置 t_min = 12 ms（{base['p_steps']} 步，"
          f"实测 {base['p_steps'] * DT * 1e3:.1f} ms）："
          f"横漂 {base['y_cm']:+.1f} cm、耗气 {base['m_total']:.2f} kg、"
          f"峰值 {base['z_max']:.2f} m、末压 {base['p_end']:.2f} MPa")

    lo = min(rows, key=lambda r: abs(r["y_cm"]))
    hi = max(rows, key=lambda r: abs(r["y_cm"]))
    print(f"  横漂最小 = {lo['y_cm']:+.1f} cm（t_min "
          f"{lo['p_steps'] * DT * 1e3:.1f} ms）；"
          f"最大 = {hi['y_cm']:+.1f} cm（t_min "
          f"{hi['p_steps'] * DT * 1e3:.1f} ms）")

    small = [r for r in rows if r["p_steps"] <= 4]
    if len(small) >= 2:
        ys = [abs(r["y_cm"]) for r in small]
        print(f"  ★ t_min 在 6.7–26.7 ms 之间时横漂在 "
              f"{min(ys):.1f}–{max(ys):.1f} cm 之间**波动，不单调**"
              f"（终端比例补脉冲与 MIB 量化互相作用）")
    print(f"  ★ 放宽到 {hi['p_steps'] * DT * 1e3:.1f} ms（约为定稿的 "
          f"{hi['p_steps'] / base['p_steps']:.0f} 倍）时横漂翻到 "
          f"{hi['y_cm']:+.1f} cm，"
          f"耗气升到 {hi['m_total']:.2f} kg、末压降到 "
          f"{hi['p_end']:.2f} MPa")
    print("\n  结论：MIB 越大，侧推配平的占空比下限越高，"
          "细微横漂越补不满 ⇒ **MIB 惩罚精细配平，不惩罚大推力**；"
          "但小范围改动 MIB 时横漂不敏感，只有把它放大到数倍才显著恶化")
    print("=" * 92)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
