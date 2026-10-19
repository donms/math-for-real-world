#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **步长收敛扫描**：把"记账方式"钉死之后，再看飞行结果随 $\Delta t$ 怎么变。

## 为什么要扫

`paper/论文.md` §6.7 记录的事实是：同一任务、只改脉冲记账方式，
落地横漂在 **0.57 – 8.28 m** 之间跳（14 倍）。三档记账都"没算错"，
错的是把任何一个当成物理结论。

⇒ 本脚本用**新的、与步长无关的记账**（`pfm.py` 的 `analytic` 档，
记账守恒已由 `verify_pfm_ledger.py` 证明），
在 $dt=1/60\ldots1/960$ 上扫五点，回答：

$$\boxed{\text{落地横漂到底有没有极限？极限是多少？}}$$

## 判据（用户给定，不许放宽）

1. $dt\le1/240$ 之后，各量相对**最细步长**的相对差 $<2\%$；
2. $1/120$ **不再是离群点**。

达不到就如实报"未收敛"，并给出残余原因 —— **不许为了让某个数好看去调参数**。

## 附带三个诊断（判"未收敛"时必须能说清是哪一类）

| 诊断 | 回答什么 |
|---|---|
| `1/3840` 补一点 | 是"还在漂"还是"已经到底" |
| MIB 微扰 $t_{\min}\pm0.5\%$ | 结果对**脉冲时刻**的敏感度（条件数）|
| 各量的收敛性分开看 | 是**全部**不收敛，还是**只有 $y$** 不收敛 |
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nozzle_state as ns     # noqa: E402
import physics as ph          # noqa: E402

DTS = (1 / 60, 1 / 120, 1 / 240, 1 / 480, 1 / 960)


def one(dt: float, ledger: str = "analytic", t_min: float | None = None) -> dict:
    r"""跑一个步长，返回七个量的字典。"""
    old = ns.PWM_MIN_ON
    if t_min is not None:
        ns.PWM_MIN_ON = t_min
    try:
        recs = ns.run_mission10_auto(dt, ledger=ledger, quiet=True)
    finally:
        ns.PWM_MIN_ON = old
    L = recs[-1]
    pfm = ns.run_mission10.pfm
    return {
        "y": L.y,
        "vz": L.vz,
        "zmax": max(r.z for r in recs),
        "t_end": L.t,
        "x": L.x,
        "m": L.m_total,
        "p": L.p_mPa,
        # ---- 诊断 ----
        "t_burn": ns.run_mission10_auto.t_burn,
        "T_roll": ns.run_mission10_auto.T_roll,
        "theta": math.degrees(L.theta),
        "n_pulse": pfm.n_pulse,
        "vy": L.vy,
    }


KEYS = [
    ("落地横向 y (cm)", "y", 100.0),
    ("落地 vz (m/s)", "vz", 1.0),
    ("峰值 z (m)", "zmax", 1.0),
    ("飞行时间 (s)", "t_end", 1.0),
    ("落地 x (m)", "x", 1.0),
    ("耗气 (kg)", "m", 1.0),
    ("末端罐压 (MPa)", "p", 1.0),
]


def fmt_row(name: str, key: str, scale: float, rows: list[dict]) -> str:
    ref = rows[-1][key] * scale
    cells = []
    worst = 0.0
    for r in rows:
        v = r[key] * scale
        d = abs(v - ref) / abs(ref) * 100 if ref != 0 else 0.0
        worst = max(worst, d)
        mark = "" if d < 2.0 else "!"
        cells.append(f"{v:>12.4f}{d:>8.2f}%{mark:<1}")
    return f"  {name:<18}" + "".join(cells)


def main() -> int:
    print("=" * 110)
    print("  W55 · 步长收敛扫描（记账已钉死为 analytic）")
    print("=" * 110)
    print(f"  MIB t_min = {ns.PWM_MIN_ON*1e3:.1f} ms，"
          f"档位 dt = " + " / ".join(f"1/{round(1/d)}" for d in DTS))

    rows: list[dict] = []
    for dt in DTS:
        t0 = time.time()
        d = one(dt)
        rows.append(d)
        print(f"  … 1/{round(1/dt):<5} {time.time()-t0:5.1f}s  "
              f"y={d['y']*100:+9.2f} cm  zmax={d['zmax']:.3f}  "
              f"t={d['t_end']:.3f}  m={d['m']:.2f}")

    hdr = "  " + " " * 18 + "".join(f"{'1/' + str(round(1 / d)):>12}{'Δ%':>9}"
                                    for d in DTS)
    print("\n" + "=" * 110)
    print("  一、原始表（Δ% 相对**最细步长** 1/960）")
    print("=" * 110)
    print(hdr)
    print("  " + "-" * 106)
    for name, key, sc in KEYS:
        print(fmt_row(name, key, sc, rows))

    print("\n  【诊断量】")
    print(hdr)
    print("  " + "-" * 106)
    for name, key, sc in (("熄火时刻 (s)", "t_burn", 1.0),
                          ("滚转窗 (s)", "T_roll", 1.0),
                          ("末态姿态 (°)", "theta", 1.0),
                          ("残余横速 (m/s)", "vy", 1.0)):
        print(fmt_row(name, key, sc, rows))
    print(f"  {'脉冲总数':<18}" + "".join(f"{r['n_pulse']:>18}" for r in rows))

    # ---------------- 判据 ----------------
    print("\n" + "=" * 110)
    print("  二、判据（① dt≤1/240 后各量差 <2%   ② 1/120 不再是离群点）")
    print("=" * 110)
    ok_all = True
    for name, key, sc in KEYS:
        ref = rows[-1][key] * sc
        ds = [abs(r[key] * sc - ref) / abs(ref) * 100 for r in rows]
        tail = ds[2:]                     # 1/240, 1/480, 1/960
        worst = max(tail)
        # 1/120 是不是离群点：看它到"相邻两档"的偏离是否显著大于尾部离散
        gap = abs(ds[1] - ds[2])
        tail_spread = max(tail) - min(tail)
        outlier = gap > max(3 * tail_spread, 2.0)
        ok = worst < 2.0 and not outlier
        ok_all &= ok
        print(f"  {name:<18} 尾部最大差 {worst:>6.2f}%   1/120 偏离 {gap:>6.2f}%   "
              f"尾部离散 {tail_spread:>5.2f}%   "
              f"{'✓' if ok else '✗'}")
    print(f"\n  ★ 判据总判定：{'**收敛**' if ok_all else '**未达到收敛判据**'}")

    # ---------------- 补一点：1/3840 ----------------
    print("\n" + "=" * 110)
    print("  三、补一点 1/3840：是「还在漂」还是「已经到底」")
    print("=" * 110)
    t0 = time.time()
    fine = one(1 / 3840)
    print(f"  1/3840  y={fine['y']*100:+9.2f} cm  zmax={fine['zmax']:.3f}  "
          f"t={fine['t_end']:.3f}  m={fine['m']:.2f}   [{time.time()-t0:.1f}s]")
    for name, key, sc in KEYS:
        v960 = rows[-1][key] * sc
        v3840 = fine[key] * sc
        d = abs(v3840 - v960) / abs(v3840) * 100 if v3840 else 0.0
        print(f"  {name:<18} 1/960 = {v960:>12.4f}   1/3840 = {v3840:>12.4f}"
              f"   相差 {d:>6.2f}%")

    # ---------------- 微扰：t_min ±0.5% ----------------
    print("\n" + "=" * 110)
    print("  四、MIB 微扰（t_min ±0.5%，dt 固定 1/480）：结果对**脉冲时刻**的条件数")
    print("=" * 110)
    base = one(1 / 480)
    print(f"  基准 t_min={ns.PWM_MIN_ON*1e3:.3f} ms：y={base['y']*100:+.2f} cm")
    for k in (-0.005, 0.005):
        tm = ns.PWM_MIN_ON * (1 + k)
        r = one(1 / 480, t_min=tm)
        print(f"  t_min{(k*100):+.1f}% = {tm*1e3:.4f} ms："
              f"y={r['y']*100:+9.2f} cm   "
              f"Δy={r['y']*100-base['y']*100:+9.2f} cm   "
              f"（{(r['y']-base['y'])/base['y']*100:+.1f}%）")
    print("\n  ⇒ 若 0.5% 的 t_min 改动就让 y 变几十个百分点，"
          "则 y 的条件数来自「脉冲落在哪一毫秒」，不是来自物理。")
    print("=" * 110)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
