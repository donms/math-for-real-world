#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **记账守恒验证**：先证明账目对，再谈飞行结果。

## 为什么必须单独做这一步

`nozzle_state.run_mission10` 里，"物理积分"与"脉冲记账"原本搅在一起。
于是当落地横漂在 0.57 – 8.28 m 之间跳时，**说不清是物理错了还是记账错了**。
（见 `paper/论文.md` §6.7。）

⇒ 本脚本**不看飞行**，只回答一个问题：

$$\boxed{\text{给定一条已知的 } d(t)\text{，}\int F\,dt\ \text{与}\ \int\dot m\,dt
\ \text{是否等于}\ F_{\text{full}}\!\int\! d\,dt\ \text{与}\ \dot m_{\text{full}}\!\int\! d\,dt\;?}$$

## 三条 $d(t)$（覆盖三种形态）

| 曲线 | 表达式 | 考什么 |
|---|---|---|
| 常数 | $d=0.37$ | 最干净：任何误差都是记账误差 |
| 正弦 | $d=0.5+0.45\sin(2\pi\cdot1.3t)$ | **连续变化**：步首/步中点采样差别最大 |
| 阶跃 | $0.05\to0.90\to0.15$ | **跳变**：跨越跳变点的记账最容易错 |

## 判据（两条，缺一不可）

1. **幅度**：$|\,I/(F_{\text{full}}\!\int\! d\,dt)-1\,|<0.5\%$，
   质量同；
2. ★ **与步长无关**：同一 ledger 下，**不同 $dt$ 之间的误差极差 $<0.01\%$**
   —— 只满足 1 不满足 2，说明"这个步长恰好对"，换个步长就错。

## 一个必须说清的边界

PFM 的**瞬时**力不可能等于 $F_{\text{full}}d(t)$（它是开关型），
所以任意窗口内必然留下**至多 $t_{\min}$ 的量化赤字**：

$$\Big|\int F\,dt-F_{\text{full}}\!\int\! d\,dt\Big|\le F_{\text{full}}\,t_{\min}$$

⇒ 相对误差的理论下界是 $t_{\min}/\int d\,dt$。
本脚本把**实测误差**与**这个下界**并排打印 ——
误差贴着下界跑才叫"账目对"；超过下界才叫"记账错"。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pfm as pfm_mod          # noqa: E402

# ---- 名义满推力与满流量（只用于把 on-time 换算成冲量/质量，比值与取值无关）----
F_FULL = 20.0e3        # N
MDOT_FULL = 0.65       # kg/s
T_END = 10.0           # s，窗口长度
DTS = (1 / 60, 1 / 120, 1 / 240, 1 / 480, 1 / 960)
T_MIN = 0.012          # MIB = 12 ms

CURVES: dict[str, tuple[str, object]] = {
    "常数  d=0.37": ("const", 0.37),
    "正弦  d=0.5+0.45sin(2π·1.3t)": ("sine", (0.5, 0.45, 1.3)),
    "阶跃  0.05→0.90→0.15": ("step", ((0.0, 0.05), (2.0, 0.90), (5.5, 0.15))),
}


def d_of(kind: str, par, t: float) -> float:
    if kind == "const":
        return float(par)
    if kind == "sine":
        a0, a1, f = par
        return a0 + a1 * math.sin(2 * math.pi * f * t)
    # step
    v = 0.0
    for t0, val in par:
        if t >= t0:
            v = val
    return v


def d_ref(kind: str, par) -> float:
    r"""$\int_0^{T} d\,dt$，用 **1e-4 步长的 Simpson**（与积分器无关的独立算法）。"""
    n = 200000
    h = T_END / n
    s = d_of(kind, par, 0.0) + d_of(kind, par, T_END)
    for i in range(1, n):
        s += (4 if i % 2 else 2) * d_of(kind, par, i * h)
    return s * h / 3.0


def run(kind: str, par, ledger: str, dt: float) -> dict:
    r"""跑完一整条曲线，返回账目。"""
    m = pfm_mod.PFM(t_min=T_MIN, ledger=ledger)
    use_mid = ledger in pfm_mod.NEEDS_MID
    n = int(round(T_END / dt))
    imp = mass = 0.0
    for i in range(n):
        t = i * dt
        d_beg = d_of(kind, par, t)
        d_use = d_of(kind, par, t + dt / 2) if use_mid else d_beg
        on = m.step(t, dt, {"ch": d_use})
        ff, mf = m.scales(on.get("ch", 0.0))
        imp += F_FULL * ff * dt
        mass += MDOT_FULL * mf * dt
    return {"imp": imp, "mass": mass, "n_pulse": m.n_pulse,
            "on_time": m.on_time.get("ch", 0.0),
            "demand": m.demand.get("ch", 0.0)}


def main() -> int:
    print("=" * 92)
    print("  W55 · 记账守恒验证（先证明账目对，再谈飞行结果）")
    print(f"  窗口 0 – {T_END:g} s｜MIB t_min = {T_MIN*1e3:.1f} ms｜"
          f"F_full = {F_FULL/1e3:.0f} kN｜mdot_full = {MDOT_FULL:g} kg/s")
    print("=" * 92)

    ledgers = ("legacy1", "legacy2", "legacy3", "analytic")
    summary = []
    for name, (kind, par) in CURVES.items():
        D = d_ref(kind, par)
        bound = T_MIN / D * 100          # 相对误差的**理论下界**（%）
        print(f"\n{'#' * 92}")
        print(f"#  {name}")
        print(f"#  ∫d dt = {D:.6f} s（独立 Simpson）｜"
              f"理论量化下界 t_min/∫d = {bound:.4f}%")
        print(f"{'#' * 92}")
        for led in ledgers:
            print(f"\n  --{led}: {pfm_mod.LEDGERS[led]}--")
            print(f"  {'dt':>9}{'冲量误差%':>12}{'质量误差%':>12}"
                  f"{'脉冲数':>8}{'on合计(s)':>12}{'量化赤字(ms)':>14}")
            errs_i, errs_m = [], []
            for dt in DTS:
                r = run(kind, par, led, dt)
                ei = (r["imp"] / (F_FULL * D) - 1) * 100
                em = (r["mass"] / (MDOT_FULL * D) - 1) * 100
                errs_i.append(ei)
                errs_m.append(em)
                print(f"  1/{round(1/dt):>6}{ei:>12.4f}{em:>12.4f}"
                      f"{r['n_pulse']:>8d}{r['on_time']:>12.6f}"
                      f"{(r['demand'] - r['on_time'])*1e3:>14.3f}")
            spread_i = max(errs_i) - min(errs_i)
            spread_m = max(errs_m) - min(errs_m)
            ok_i = max(abs(e) for e in errs_i)
            ok_m = max(abs(e) for e in errs_m)
            verdict = []
            verdict.append("幅度✓" if ok_i < 0.5 and ok_m < 0.5 else "幅度✗")
            verdict.append("与dt无关✓" if spread_i < 0.01 and spread_m < 0.01
                           else "与dt无关✗")
            print(f"  ⇒ 最大|误差| {ok_i:.4f}% / {ok_m:.4f}%｜"
                  f"**跨 dt 极差** {spread_i:.4f}% / {spread_m:.4f}%｜"
                  + " ".join(verdict))
            summary.append((name.split()[0], led, ok_i, ok_m,
                            spread_i, spread_m, bound))

    # ---------------- 总表 ----------------
    print("\n" + "=" * 92)
    print("  总表")
    print("=" * 92)
    print(f"  {'曲线':<10}{'ledger':<10}{'冲量误差%':>11}{'质量误差%':>11}"
          f"{'极差I%':>9}{'极差m%':>9}{'下界%':>8}  判定")
    for name, led, oi, om, si, sm, bd in summary:
        bad = oi >= 0.5 or om >= 0.5 or si >= 0.01 or sm >= 0.01
        print(f"  {name:<10}{led:<10}{oi:>11.4f}{om:>11.4f}"
              f"{si:>9.4f}{sm:>9.4f}{bd:>8.4f}  "
              f"{'✗ 不守恒' if bad else '✓ 守恒'}")

    # ---------------- 结论 ----------------
    a = [s for s in summary if s[1] == "analytic"]
    print("\n" + "=" * 92)
    print("  ★ 判定")
    print("=" * 92)
    ok = all(oi < 0.5 and om < 0.5 and si < 0.01 and sm < 0.01
             for _, _, oi, om, si, sm, _ in a)
    print(f"  analytic（本版）：{'**通过**' if ok else '**不通过**'}"
          f"｜三条曲线最大冲量误差 {max(x[2] for x in a):.4f}%，"
          f"最大跨 dt 极差 {max(x[4] for x in a):.4f}%")
    worst = max(summary, key=lambda s: s[4])
    print(f"  legacy 最差的一档：{worst[1]}，跨 dt 极差 {worst[4]:.3f}% "
          f"⇒ **同一个账目，换个步长就换了答案**")
    print("\n  ⇒ 记账对，可以谈飞行结果了；错的账，飞行结果不可用。")
    print("=" * 92)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
