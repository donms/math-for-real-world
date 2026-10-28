#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""三套候选方案的全指标复核（论文 7 章与结论速览的唯一数字来源）。"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import w58_core as c
from w58_core import P0, equilibrium, resistance

R = HERE.parent / "results"
V = 21.23

DESIGNS = {
    "现役（标称）": dict(),
    "A 极速优先": dict(b_front=0.34, delta_front_deg=2.5, b_rear=0.26,
                        delta_rear_deg=-1.5, h_wheel_gap=0.042),
    "B 抗浪优先": dict(b_front=0.33, delta_front_deg=11.0, b_rear=0.36,
                        delta_rear_deg=-1.8, h_wheel_gap=0.046),
    "C 均衡": dict(b_front=0.38, delta_front_deg=5.2, b_rear=0.37,
                    delta_rear_deg=-1.6, h_wheel_gap=0.032),
}


def evaluate(p):
    ms = c.max_speed(p, n=160)
    eq = equilibrium(V, p)
    res = resistance(V, p, eq, include_wheel_drag=False)
    out = dict(vmax_kmh=c.kmh(ms["V_max"]), drag=res["total"],
               draft_f_cm=eq["h_front"] * 100, draft_r_cm=eq["h_rear"] * 100,
               hw_cm=c.wheel_immersion(eq, p) * 100,
               theta_deg=math.degrees(eq["theta"]),
               power_ideal_kmh=c.kmh(c.power_limited_speed(p)))
    for Hs, Tp in ((0.5, 4.8), (1.0, 5.5), (1.5, 6.2)):
        o = c.simulate(V, p, Hs=Hs, Tp=Tp, t_end=18.0, dt=0.005,
                       speed_hold=False, throttle=1.0, fixed_speed=True,
                       t_warm=3.0)
        m = o["metrics"]
        out[f"Hs{Hs}"] = dict(az_rms_g=m["az_rms_g"], az_p95_g=m["az_p95"] / c.G,
                              wheel_out=m["hw_out_frac"], air=m["air_frac"],
                              bow=m["bow_dive_frac"],
                              hold=m["thrust_mean"] >= m["drag_mean"] * 0.98,
                              T=m["thrust_mean"], D=m["drag_mean"])
    return out


def main():
    res = {}
    for name, kw in DESIGNS.items():
        p = P0.with_(**kw)
        res[name] = evaluate(p)
        print(f"[{name}] Vmax={res[name]['vmax_kmh']:.1f} "
              f"Hs1.0 az_p95={res[name]['Hs1.0']['az_p95_g']:.2f}g "
              f"wheel_out={res[name]['Hs1.0']['wheel_out']*100:.0f}%")
    c.to_json(res, R / "q5_候选.json")

    lines = ["| 方案 | 极速 km/h | 巡航阻力 N | 吃水 前/后 cm | $H_s$=0.5 砰击(g) | $H_s$=1.0 砰击(g) | $H_s$=1.0 脱水 | $H_s$=1.5 砰击(g) |",
             "|---|---|---|---|---|---|---|---|"]
    for name, r in res.items():
        lines.append(f"| {name} | {r['vmax_kmh']:.1f} | {r['drag']:.0f} | "
                     f"{r['draft_f_cm']:.2f}/{r['draft_r_cm']:.2f} | "
                     f"{r['Hs0.5']['az_p95_g']:.2f} | {r['Hs1.0']['az_p95_g']:.2f} | "
                     f"{r['Hs1.0']['wheel_out']*100:.0f}% | "
                     f"{r['Hs1.5']['az_p95_g']:.2f} |")
    md = "\n".join(lines)
    (R / "q5_候选.md").write_text(md + "\n", encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
