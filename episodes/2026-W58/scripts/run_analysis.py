#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""2026-W58 主求解脚本：一次跑完五问，结果落盘到 results/。

用法
----
    $PY scripts/run_analysis.py            # 全量（约 6–8 分钟，主要花在第 5 问）
    $PY scripts/run_analysis.py --quick    # 快速（第 5 问只跑 24 个样本）
"""
from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

import w58_core as c
from w58_core import G, P0, Params, equilibrium, resistance, spring_stiffness

R = c.RESULTS
R.mkdir(parents=True, exist_ok=True)

V_CRUISE = 40_740 / (32 * 60)          # 40.74 km / 32 min = 21.23 m/s
V_CRUISE = 21.23


def pct(x):
    return f"{x*100:.1f}%"


# ================================================================ Q1 姿态
def q1(p: Params):
    out = {}
    rows = []
    for V in (18.0, V_CRUISE, 23.0, 25.0, 27.0, 29.0):
        eq = equilibrium(V, p)
        res = resistance(V, p, eq, include_wheel_drag=False)
        # Savitsky 互校
        lwf = c.wetted_length(eq["h_front"], eq["alpha_front"], p.b_front, p.c_spray_root)
        lwr = c.wetted_length(eq["h_rear"], eq["alpha_rear"], p.b_rear, p.c_spray_root)
        sav_f = c.savitsky_lift(V, p.b_front, eq["h_front"], eq["alpha_front"])
        sav_r = c.savitsky_lift(V, p.b_rear, eq["h_rear"], eq["alpha_rear"])
        rows.append(dict(
            V=V, kmh=c.kmh(V), draft_f_cm=eq["h_front"] * 100,
            draft_r_cm=eq["h_rear"] * 100, theta_deg=math.degrees(eq["theta"]),
            alpha_f_deg=math.degrees(eq["alpha_front"]),
            alpha_r_deg=math.degrees(eq["alpha_rear"]),
            Lf=eq["l_front"], Lr=eq["l_rear"],
            share_f=eq["l_front"] / (eq["l_front"] + eq["l_rear"]),
            lw_f_cm=lwf * 100, lw_r_cm=lwr * 100,
            S_wet_cm2=res["S_wet"] * 1e4,
            drag=res["total"], power_kw=res["total"] * V / p.eta_drive / 1000,
            # 若仅有浮力：需要排开多少水
            buoy_m3=p.weight / (c.RHO * G),
            sav_f=sav_f, sav_r=sav_r,
            sav_ratio_f=sav_f / max(eq["l_front"], 1e-9),
            sav_ratio_r=sav_r / max(eq["l_rear"], 1e-9),
        ))
    out["rows"] = rows
    # 巡航点单独取出
    cr = [r for r in rows if abs(r["V"] - V_CRUISE) < 1e-6][0]
    out["cruise"] = cr
    # 浮力对比：车重需要多少排水体积 vs 实际浮力体
    out["buoyancy"] = dict(need_m3=p.weight / (c.RHO * G),
                           have_m3=p.v_buoy,
                           ratio=(p.v_buoy / (p.weight / (c.RHO * G))))
    # 巡航点：速度掉多少会"托不住"
    V_floor = math.sqrt(p.weight / (0.5 * c.RHO * (p.b_front + p.b_rear)
                                    * p.kL * 0.06))   # 允许 6 cm 浸深
    out["V_floor_ms"] = V_floor
    out["V_floor_kmh"] = c.kmh(V_floor)
    # 能量：32 min 耗油
    P_cr = cr["power_kw"]
    out["energy"] = dict(P_kw=P_cr, hours=32 / 60,
                         kWh=P_cr * 32 / 60,
                         fuel_kg=P_cr * 32 / 60 * 0.35,
                         fuel_L=P_cr * 32 / 60 * 0.35 / 0.75)
    return out


# ================================================================ Q2 校验
def q2(p: Params):
    out = {}
    # --- 功率-阻力账
    ms = c.max_speed(p)
    out["vmax_kmh"] = c.kmh(ms["V_max"])
    info = ms["info"]
    out["vmax_detail"] = dict(
        kmh=c.kmh(info["V"]), thrust=info["thrust"], drag=info["drag"],
        u=info["u"], slip=info["slip"], power_kw=info["power"] / 1000,
        hw_cm=info["hw"] * 100, rpm=info["u"] / p.r_wheel * p.gear * 60 / (2 * math.pi),
    )
    out["power_limited_kmh"] = c.kmh(c.power_limited_speed(p))

    # --- 阻力分解（巡航点）
    eq = equilibrium(V_CRUISE, p)
    res = resistance(V_CRUISE, p, eq, include_wheel_drag=False)
    out["drag_break"] = {k: float(v) for k, v in res.items()
                         if isinstance(v, (int, float))}

    # --- 2009 反向校验
    out["backtest_2009"] = backtest_2009(p)
    out["backtest_curve"] = backtest_curve(p)

    # --- 巡航：解出"刚好平衡阻力"的油门，而不是全油门
    out["cruise"] = cruise_state(p, V_CRUISE)
    return out


def cruise_state(p: Params, V: float) -> dict:
    """巡航工况：油门刚好把阻力顶平。"""
    eq = equilibrium(V, p)
    D = resistance(V, p, eq, include_wheel_drag=False)["total"]
    hw = c.wheel_immersion(eq, p)
    lo, hi = 0.0, 1.0
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        T = c.thrust_at(V, hw, p, p.gear, mid)[0]
        if T < D:
            lo = mid
        else:
            hi = mid
    thr = 0.5 * (lo + hi)
    T, u, slip, _ = c.thrust_at(V, hw, p, p.gear, thr)
    return dict(V=V, kmh=c.kmh(V), drag=D, thrust=T, throttle=thr, u=u,
                slip=slip, power_kw=T * u / p.eta_drive / 1000,
                drag_power_kw=D * V / p.eta_drive / 1000,
                jet_loss_kw=(T * u - D * V) / p.eta_drive / 1000,
                hw_cm=hw * 100)


def backtest_2009(p: Params, entry_kmh: float = 60.0, h_allow: float = 0.06,
                  b_plate: float = 0.18, cd_extra: float = 1.35) -> dict:
    """2009 年"20 米就沉"的反向校验。

    同一套升力/阻力模型，只把参数换回 2009 年的简陋改装：
    两块焊在车轮上的铁皮（各 0.18 m 宽）、没有浮力体、姿态不可控。
    物理判据：**当速度降到"用允许浸深也托不住车重"时，就再也起不来**。
    """
    V_floor = math.sqrt(p.weight / (0.5 * c.RHO * 2 * b_plate * p.kL * h_allow))
    q2009 = p.with_(b_front=b_plate, b_rear=b_plate, v_buoy=0.0,
                    delta_front_deg=0.0, delta_rear_deg=0.0,
                    z_off_front=0.30, z_off_rear=0.30, a_app=0.0035,
                    h_wheel_gap=0.0)
    V0 = entry_kmh / 3.6
    ds, V = 0.0, V0
    dstep = 0.02
    while V > V_floor and ds < 500:
        eq = equilibrium(V, q2009)
        res = resistance(V, q2009, eq, include_wheel_drag=True)["total"] * cd_extra
        a = res / p.mass
        ds += dstep
        V = math.sqrt(max(V * V - 2 * a * dstep, 1e-6))
    return dict(V_floor_kmh=c.kmh(V_floor), entry_kmh=entry_kmh,
                distance_m=ds, V_end_kmh=c.kmh(V),
                note="距离 = 从入水速度减速到最低滑行速度所走过的路程")


def backtest_curve(p: Params, h_allow: float = 0.06,
                   b_plate: float = 0.18) -> dict:
    """扫入水速度 → 滑出距离，并反推 20 m / 26 m 所需的入水速度。"""
    entries = np.arange(50, 96, 5, dtype=float)
    pts = []
    for e in entries:
        r = backtest_2009(p, entry_kmh=float(e), h_allow=h_allow, b_plate=b_plate)
        pts.append(dict(entry_kmh=float(e), distance_m=r["distance_m"]))
    d = np.array([q["distance_m"] for q in pts])
    v = np.array([q["entry_kmh"] for q in pts])
    order = np.argsort(d)
    need20 = float(np.interp(20.0, d[order], v[order])) if d.max() >= 20 else float("nan")
    need26 = float(np.interp(26.0, d[order], v[order])) if d.max() >= 26 else float("nan")
    return dict(points=pts,
                V_floor_kmh=backtest_2009(p, 60, h_allow, b_plate)["V_floor_kmh"],
                entry_for_20m=need20, entry_for_26m=need26)


# ================================================================ Q3 极速
def q3(p: Params):
    out = {}
    base = c.max_speed(p)
    out["base_kmh"] = c.kmh(base["V_max"])
    out["power_limited_kmh"] = c.kmh(c.power_limited_speed(p))
    b = base["info"]
    out["base_detail"] = dict(slip=b["slip"], power_kw=b["power"] / 1000,
                              hw_cm=b["hw"] * 100, u=b["u"])

    # 敏感性：参数 ±
    sens = {}
    grid = {
        "功率 +20%": dict(p_max_kw=p.p_max_kw * 1.2),
        "功率 -20%": dict(p_max_kw=p.p_max_kw * 0.8),
        "功率 60kW": dict(p_max_kw=60.0),
        "质量 +10%": dict(m_rider=p.m_rider * 1.1 + 7.2),
        "质量 -10%": dict(m_rider=p.m_rider * 0.9 - 7.2),
        "轮底偏置 1cm": dict(h_wheel_gap=0.010),
        "轮底偏置 4cm": dict(h_wheel_gap=0.040),
        "桨叶数 3": dict(n_blade=3.0),
        "桨叶数 1": dict(n_blade=1.0),
        "后板 +20%": dict(b_rear=p.b_rear * 1.2),
        "后板 -20%": dict(b_rear=p.b_rear * 0.8),
        "前板 -20%": dict(b_front=p.b_front * 0.8),
        "kL +15%": dict(kL=p.kL * 1.15),
        "kL -15%": dict(kL=p.kL * 0.85),
    }
    for k, kw in grid.items():
        pp = p.with_(**kw)
        try:
            out_k = c.kmh(c.max_speed(pp)["V_max"])
        except Exception:
            out_k = float("nan")
        sens[k] = out_k
    out["sensitivity_kmh"] = sens

    # 功率扫描（0.5–2.0 倍）
    sweep = []
    for fac in (0.6, 0.8, 1.0, 1.2, 1.5, 1.8):
        pp = p.with_(p_max_kw=p.p_max_kw * fac)
        sweep.append(dict(fac=fac, kw=p.p_max_kw * fac,
                          vmax_kmh=c.kmh(c.max_speed(pp)["V_max"]),
                          ideal_kmh=c.kmh(c.power_limited_speed(pp))))
    out["power_sweep"] = sweep

    # 三种"上限"对比
    out["three_limits"] = dict(
        ideal_power=out["power_limited_kmh"],
        with_slip=out["base_kmh"],
        reported_kmh=90.0,
    )
    return out


# ================================================================ Q4 波浪
def q4(p: Params, quick: bool = False):
    out = {"cases": []}
    Hs_list = (0.2, 0.5, 1.0, 1.5, 2.0)
    if quick:
        Hs_list = (0.5, 1.5)
    for Hs in Hs_list:
        Tp = 4.0 + 1.5 * Hs                   # 浪越大周期越长（工程近似）
        t_end = 18.0
        o = c.simulate(V_CRUISE, p, Hs=Hs, Tp=Tp, t_end=t_end, dt=0.004,
                       speed_hold=False, throttle=1.0, fixed_speed=True,
                       t_warm=3.0)
        m = o["metrics"]
        # 维持速度的能力：全油门平均推力 vs 平均阻力
        out["cases"].append(dict(
            Hs=Hs, Tp=Tp, az_rms_g=m["az_rms_g"], az_p95=m["az_p95"],
            az_max_g=m["az_max"] / G, theta_rms_deg=m["theta_rms_deg"],
            theta_max_deg=m["theta_max_deg"], wheel_out=m["hw_out_frac"],
            air_frac=m["air_frac"], bow_dive=m["bow_dive_frac"],
            h_f_max_cm=m["h_f_max"] * 100,
            thrust_mean=m["thrust_mean"], drag_mean=m["drag_mean"],
            can_hold=bool(m["thrust_mean"] >= m["drag_mean"] * 0.98),
        ))
    # 速度-海况包线：给定 Hs，找"还能维持"的最高速度
    env = []
    for Hs in (0.2, 0.5, 1.0, 1.5):
        best = 0.0
        for V in (25.0, 23.0, 21.2, 19.0, 17.0, 15.0, 13.0, 11.0, 9.0, 7.0):
            o = c.simulate(V, p, Hs=Hs, Tp=4.0 + 1.5 * Hs,
                           t_end=14.0, dt=0.005, speed_hold=False, throttle=1.0,
                           fixed_speed=True, t_warm=3.0)
            m = o["metrics"]
            if m["thrust_mean"] >= m["drag_mean"] * 0.98 and m["az_p95"] < 3.5 * G:
                best = V
                break
        env.append(dict(Hs=Hs, V_hold_kmh=c.kmh(best)))
    out["envelope"] = env
    # 时域与"静态吃水 vs 波幅"的对照
    out["static_draft_cm"] = equilibrium(V_CRUISE, p)["h_rear"] * 100
    return out


# ================================================================ Q5 设计
def lhs(n: int, dim: int, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = np.zeros((n, dim))
    for j in range(dim):
        perm = rng.permutation(n)
        out[:, j] = (perm + rng.random(n)) / n
    return out


def design_params(base: Params, x) -> Params:
    bf = 0.20 + 0.18 * x[0]
    df = 2.0 + 10.0 * x[1]
    br = 0.26 + 0.20 * x[2]
    dr = -2.0 + 12.0 * x[3]
    gap = 0.012 + 0.038 * x[4]
    return base.with_(b_front=bf, delta_front_deg=df, b_rear=br,
                      delta_rear_deg=dr, h_wheel_gap=gap)


def pareto_mask(F: np.ndarray) -> np.ndarray:
    """F: (n, k) 全部为"越小越好"。"""
    n = len(F)
    mask = np.ones(n, dtype=bool)
    for i in range(n):
        if not mask[i]:
            continue
        for j in range(n):
            if i == j:
                continue
            if np.all(F[j] <= F[i]) and np.any(F[j] < F[i]):
                mask[i] = False
                break
    return mask


def q5(p: Params, n: int = 160, quick: bool = False):
    t0 = time.time()
    xs = lhs(n, 5, seed=2026)
    recs = []
    for i, x in enumerate(xs):
        pp = design_params(p, x)
        try:
            vmax = c.kmh(c.max_speed(pp, n=120)["V_max"])
        except Exception:
            vmax = 0.0
        eq = equilibrium(V_CRUISE, pp)
        res = resistance(V_CRUISE, pp, eq, include_wheel_drag=False)
        drag = res["total"]
        # 时域（定速、Hs=1.0）
        o = c.simulate(V_CRUISE, pp, Hs=1.0, Tp=5.5, t_end=16.0, dt=0.006,
                       speed_hold=False, throttle=1.0, fixed_speed=True,
                       record_every=8, t_warm=3.0)
        m = o["metrics"]
        recs.append(dict(
            i=i, x=[float(v) for v in x],
            b_front=pp.b_front, delta_front=pp.delta_front_deg,
            b_rear=pp.b_rear, delta_rear=pp.delta_rear_deg,
            gap_cm=pp.h_wheel_gap * 100,
            vmax_kmh=vmax, drag_cruise=drag,
            az_rms_g=m["az_rms_g"], az_p95_g=m["az_p95"] / G,
            wheel_out=m["hw_out_frac"], bow_dive=m["bow_dive_frac"],
            h_f_max_cm=m["h_f_max"] * 100,
        ))
        if (i + 1) % 20 == 0:
            print(f"  [q5] {i+1}/{n}  {time.time()-t0:.0f}s", flush=True)

    base = next(r for r in recs if abs(r["b_front"] - p.b_front) < 0.02
                and abs(r["b_rear"] - p.b_rear) < 0.02) if False else None
    # 目标：极速高、砰击小、后轮脱水少
    F = np.array([[(-r["vmax_kmh"]), r["az_rms_g"], r["wheel_out"]] for r in recs])
    mask = pareto_mask(F)
    pareto = [recs[i] for i in np.where(mask)[0]]
    pareto.sort(key=lambda r: -r["vmax_kmh"])

    # 基线（用标称参数跑一次同口径）
    o0 = c.simulate(V_CRUISE, p, Hs=1.0, Tp=5.5, t_end=16.0, dt=0.006,
                    speed_hold=False, throttle=1.0, fixed_speed=True,
                    record_every=8, t_warm=3.0)
    m0 = o0["metrics"]
    baseline = dict(vmax_kmh=c.kmh(c.max_speed(p, n=120)["V_max"]),
                    drag_cruise=resistance(V_CRUISE, p, equilibrium(V_CRUISE, p),
                                           include_wheel_drag=False)["total"],
                    az_rms_g=m0["az_rms_g"], az_p95_g=m0["az_p95"] / G,
                    wheel_out=m0["hw_out_frac"], bow_dive=m0["bow_dive_frac"],
                    h_f_max_cm=m0["h_f_max"] * 100)
    return dict(n=n, baseline=baseline, recs=recs, pareto=pareto,
                seconds=time.time() - t0)


# ================================================================ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    p = P0
    c.to_json(asdict(p), R / "params.json")

    print("[q1] 姿态与升力分配 ...")
    r1 = q1(p)
    c.to_json(r1, R / "q1_姿态.json")
    print(f"  巡航 {r1['cruise']['kmh']:.1f} km/h: 吃水 {r1['cruise']['draft_f_cm']:.2f}/"
          f"{r1['cruise']['draft_r_cm']:.2f} cm, 纵倾 {r1['cruise']['theta_deg']:.2f}°, "
          f"湿面积 {r1['cruise']['S_wet_cm2']:.0f} cm², 阻力 {r1['cruise']['drag']:.0f} N")

    print("[q2] 功率账与 2009 反算 ...")
    r2 = q2(p)
    c.to_json(r2, R / "q2_校验.json")
    print(f"  极速 {r2['vmax_kmh']:.1f} km/h, 功率上限 {r2['power_limited_kmh']:.1f} km/h, "
          f"2009 反算 {r2['backtest_2009']['distance_m']:.0f} m")

    print("[q3] 极速与敏感性 ...")
    r3 = q3(p)
    c.to_json(r3, R / "q3_极速.json")

    print("[q4] 海况响应 ...")
    r4 = q4(p, quick=args.quick)
    c.to_json(r4, R / "q4_波浪.json")

    print("[q5] 前后板设计扫描 ...")
    r5 = q5(p, n=24 if args.quick else 160, quick=args.quick)
    c.to_json(r5, R / "q5_设计.json")
    print(f"  Pareto {len(r5['pareto'])} 个, 用时 {r5['seconds']:.0f}s")

    print("[ok] 全部结果已落盘到", R)


if __name__ == "__main__":
    main()
