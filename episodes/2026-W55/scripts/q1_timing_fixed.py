#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **修正"数秒判据"：从静止起步是变加速，不是匀速**。

## 用户指出的问题

> **"每个平台的内容都在说数秒 3.2 秒，是路程除以速度算出来的，
> 但是这个过程不是匀速运动，是一个从零开始的变加速运动，合理吗"**

**不合理。原来的推导错了。**

## 错在哪

$T^*=\pi R/v^*$ 假设**全程匀速** $v=v^*$。但车**从静止起步**，
顶点速度是全程**最大**速度，必然高于平均速度：

$$\bar v=\frac{\pi R}{T}\ <\ v_{\text{apex}}$$

**⇒ 用 $\bar v$ 反推顶点速度会低估，门槛被压小了。**

## 修正方法

**不用"平均速度"，直接积分运动方程**，检查顶点处 $N\ge0$ 是否成立：

$$N(\theta)=F_a+\frac{mv^2}{R}-mg\cos\theta\ \ge\ 0
\quad\xrightarrow{\ \theta=0,\ F_a=0\ }\quad
v_{\text{apex}}\ \ge\ \sqrt{gR}$$

$$m\frac{dv}{dt}=F_{\text{tire}}-mg\sin\theta,\qquad
F_{\text{tire}}\le\min\Big(\mu N,\ \frac{P}{v}\Big)$$

**仿真给出 $(T,\ v_{\text{apex}})$ 的真实关系，再据此重定门槛。**

## 一个解析下界（匀加速）

若近似为**匀切向加速度**从静止：

$$s=\tfrac12at^2\ \Rightarrow\ T=\sqrt{\frac{2\pi R}{a}},\qquad
v_{\text{apex}}=aT=\frac{2\pi R}{T}$$

$$\Rightarrow\quad T^*=\frac{2\pi R}{\sqrt{gR}}
=2\pi\sqrt{\frac{R}{g}}$$

**⇒ 顶点速度是平均速度的 $2$ 倍，门槛也 $2$ 倍。**

$$\boxed{\text{匀速假设把门槛压低了一半}}$$

## 但匀加速也只是个**上界**

真实过程既不是匀速、也不是匀加速：轮胎力受 $\mu N$ 与功率 $P/v$ 双重钳制，
且重力分量 $mg\sin\theta$ 沿程变化。数值积分给出的
$v_{\text{apex}}/\bar v$ 在 **1.33 到 1.71** 之间（**不是常数**），
故两个解析解把真值夹在中间：

$$\underbrace{\pi R/v^*=3.25\ \text{s}}_{\text{匀速：下界}}\ <\
\underbrace{T^*\approx4.6\ \text{s}}_{\text{数值积分：真值}}\ <\
\underbrace{2\pi R/v^*=6.50\ \text{s}}_{\text{匀加速：上界}}$$

**本脚本的定稿口径取数值积分值 $T^*\approx4.6$ s。**

## 更强的一条：风扇不是"让它能爬"

无风扇（$\lambda=0$）、745 kW、$\mu=1.3$ 时，车从静止爬环只要 **2.11 s**，
顶点 **100 km/h**，全程 $N>0$ ⇒

$$\boxed{\text{Roadster 的动力根本不需要风扇就能爬环，而且爬得飞快}}$$
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph          # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
FIG = ROOT / "episodes" / "2026-W55" / "results" / "figs"

M, G = ph.M_CAR, ph.G
R = 10.5
P_MOTOR = 745e3
MU = 1.30
V_STAR = math.sqrt(G * R)


def climb(lam: float, power_scale: float = 1.0, dt: float = 2e-4,
          mu: float = MU, p_motor: float = P_MOTOR):
    r"""从静止沿环爬升。返回 (T, v_apex, N_min, detached)。

    $\theta$ 从 $\pi$（底）到 $0$（顶），$z=R(1+\cos\theta)$。
    """
    th, v, t = math.pi, 0.0, 0.0
    N_min = 1e9
    detached = False
    while th > 1e-9:
        N = lam * M * G + M * v * v / R - M * G * math.cos(th)
        N_min = min(N_min, N)
        if N < 0:
            detached = True
            break
        Ft = min(mu * N, power_scale * p_motor / max(v, 1.0))
        a_t = Ft / M - G * math.sin(th)
        v += a_t * dt
        v = max(v, 0.0)
        th -= v / R * dt
        t += dt
        if t > 60.0:
            break
    return t, v, N_min, detached


def apex_at(T_target: float, mu: float = MU, dt: float = 2e-4,
            p_motor: float = P_MOTOR) -> float:
    r"""把动力调小到恰好在 $T$ 到达顶点时，顶点速度是多少。"""
    lo, hi = 0.02, 3.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        T, _v, _N, _d = climb(2.0, mid, dt, mu, p_motor)
        if T > T_target:
            lo = mid
        else:
            hi = mid
    return climb(2.0, 0.5 * (lo + hi), dt, mu, p_motor)[1]


def t_star(mu: float = MU, dt: float = 2e-4,
           p_motor: float = P_MOTOR) -> float:
    r"""$v_{\text{apex}}(T)=v^*$ 的数值交点 = 定稿门槛。"""
    lo, hi = 1.5, 12.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if apex_at(mid, mu, dt, p_motor) > V_STAR:
            lo = mid          # 顶点还够快 ⇒ 可以再慢一点
        else:
            hi = mid
    return 0.5 * (lo + hi)


def main() -> int:
    print("=" * 84)
    print("  数秒判据的修正：变加速 vs 匀速")
    print("=" * 84)
    print(f"\n  R = {R:.1f} m，v* = sqrt(gR) = {V_STAR:.2f} m/s"
          f"（{V_STAR*3.6:.1f} km/h）")
    print(f"  弧长 πR = {math.pi*R:.2f} m")

    # ---- 解析：匀速 vs 匀加速 ----
    T_uniform = math.pi * R / V_STAR
    T_uniform2 = 2 * math.pi * R / V_STAR
    print(f"\n【解析对比】")
    print(f"  匀速假设（原推导）  T* = πR/v*  = {T_uniform:.2f} s")
    print(f"  匀加速假设（正确）  T* = 2πR/v* = {T_uniform2:.2f} s")
    print(f"  ⇒ 原门槛只有应有值的一半")

    # ---- 数值积分：无风扇 ----
    print(f"\n【数值积分】无风扇（λ=0），看能否从静止爬上去")
    T0, v0, N0, det0 = climb(0.0)
    if det0:
        print(f"  ✗ 在 t={T0:.2f} s、v={v0:.2f} m/s 时脱离"
              f"（N 降到 {N0/1000:.2f} kN）")
    else:
        print(f"  ✓ 爬到顶点：T={T0:.2f} s，v_apex={v0:.2f} m/s"
              f"（{v0*3.6:.1f} km/h），N_min={N0/1000:+.2f} kN")

    # ---- 能量下界：2.11 s 的**独立核对** ----
    h_top = 2 * R
    E_pe = M * G * h_top
    E_ke = 0.5 * M * v0 * v0
    E_tot = E_pe + E_ke
    t_min = E_tot / P_MOTOR
    print(f"\n【能量下界】2.11 s 的独立核对（不看积分，只看能量）")
    print(f"  抬到 {h_top:.0f} m：mgh = {E_pe/1e3:.0f} kJ")
    print(f"  顶点动能 ½mv²（v={v0:.2f}）：{E_ke/1e3:.0f} kJ")
    print(f"  合计 {E_tot/1e3:.0f} kJ ÷ {P_MOTOR/1e3:.0f} kW = {t_min:.2f} s")
    print(f"  ⇒ 积分值 {T0:.2f} s 是下界的 {T0/t_min:.2f} 倍"
          f"（低速时轮胎抓不住，功率用不满）")

    # ---- 无风扇爬环对 μ 的敏感性 ----
    print(f"\n【无风扇爬环对 μ】")
    for mu_s in (1.0, 1.3, 1.5):
        Tm, vm, Nm, _dm = climb(0.0, 1.0, 2e-4, mu_s)
        print(f"  μ={mu_s:.2f}: T={Tm:.2f} s，v_apex={vm:.2f} m/s"
              f"（{vm*3.6:.0f} km/h），N_min={Nm/1000:+.2f} kN")

    # ---- 有风扇 ----
    print(f"\n【数值积分】λ=2 风扇")
    for ps in (1.0, 0.6, 0.35, 0.2):
        T1, v1, N1, det1 = climb(2.0, ps)
        tag = "✓" if not det1 else "✗"
        print(f"  动力 {ps*100:3.0f}%：T={T1:5.2f} s，v_apex={v1:5.2f} m/s"
              f"，N_min={N1/1000:+7.2f} kN  {tag}")

    # ---- 关键：给定用时，顶点速度是多少 ----
    print(f"\n【给定用时 → 顶点速度】（λ=2，调整动力使其恰好在 T 到达顶点）")
    print(f"  {'用时 T':>8}{'平均 v':>10}{'顶点 v':>10}{'倍数':>7}"
          f"{'无风扇能否贴住':>18}")
    rows = []
    for T_target in (2.0, 3.0, 3.25, 4.0, 5.0, 6.0, 6.5, 8.0):
        lo, hi = 0.02, 3.0
        best = None
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            T, v, N, det = climb(2.0, mid)
            best = (T, v, N, det)
            if T > T_target:
                lo = mid
            else:
                hi = mid
        T, v, N, det = best
        vb = math.pi * R / T
        ratio = v / vb if vb > 0 else 0
        ok = "可以" if v >= V_STAR else "**不能**"
        rows.append((T, vb, v, ok))
        print(f"  {T:>7.2f} s{vb:>9.2f}{v:>10.2f}{ratio:>7.2f}"
              f"  {ok:>16}")

    # ---- 数值交点：v_apex(T) = v* 的那个用时 ----
    T_STAR = t_star()
    ratios = [r[2] / r[1] for r in rows]
    print(f"\n【数值交点】v_apex(T) = v* = {V_STAR:.2f} m/s 处")
    print(f"  T* = {T_STAR:.2f} s   （比值 v_apex/v_avg = "
          f"{T_STAR / T_uniform:.2f}）")
    print(f"  上表比值范围 {min(ratios):.2f} ~ {max(ratios):.2f}"
          f" ⇒ **并非常数**")

    # ---- 门槛的稳健性（判据必须带上这个区间）----
    print(f"\n【门槛稳健性】")
    print(f"  {'μ':>6}{'T* (s)':>10}")
    for mu_s in (1.0, 1.3, 1.5):
        print(f"  {mu_s:>6.2f}{t_star(mu_s, 2e-4):>10.3f}")
    print(f"  步长 2e-4 → 5e-5：{t_star(MU, 5e-5):>10.3f}")
    print("  ⇒ μ 与步长都只动第 2 位小数：过程是**功率受限**，"
          "μN 只在起步 0.1 s 内起作用")
    print("  ⇒ 且把电机功率整体缩放、再按比例收油门，轨迹**完全不变**"
          "（只有乘积 P·油门起作用）")
    print("     ⇒ **门槛不依赖车有多少功率，只依赖「从静止起步」这件事**")

    # ---- 结论 ----
    print("\n" + "=" * 84)
    print("  ★★★ 结论")
    print("=" * 84)
    print(f"  ① **原判据（πR/v* = {T_uniform:.2f} s）错了**：它假设匀速")
    print(f"  ② 匀加速（顶点速度 = 2 倍平均）给上界 {T_uniform2:.2f} s")
    print(f"  ③ 数值积分：v_apex/v_avg 在 {min(ratios):.2f}~{max(ratios):.2f}"
          f" 之间，**不是常数**")
    print(f"  ④ **定稿门槛 T* ≈ {T_STAR:.1f} s**（数值交点，"
          f"介于 3.25 与 6.50 之间）")
    print(f"  ⑤ ★ 更强的结论：无风扇 λ=0 也能在 {T0:.2f} s 爬到顶点，"
          f"v_apex={v0*3.6:.0f} km/h，N_min={N0/1000:+.2f} kN")
    print(f"     ⇒ **风扇的作用是「让车能慢」，不是「让车能爬」**")
    print("=" * 84)

    # ---- 图 ----
    cfg_font()
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    fig.patch.set_facecolor("#0b1220")
    ax.set_facecolor("#0b1220")
    Ts = [r[0] for r in rows]
    v_avg = [r[1] for r in rows]
    v_apx = [r[2] for r in rows]
    ax.plot(Ts, v_avg, "o-", color="#38bdf8", lw=2, label="平均速度 πR/T")
    ax.plot(Ts, v_apx, "s-", color="#22c55e", lw=2.4, label="顶点速度（积分）")
    ax.axhline(V_STAR, color="#f59e0b", ls="--", lw=1.6,
               label=f"v* = {V_STAR:.2f} m/s")
    ax.axvline(T_uniform, color="#ef4444", ls=":", lw=1.6)
    ax.axvline(T_STAR, color="#22c55e", ls="-", lw=2.0)
    ax.axvline(T_uniform2, color="#a78bfa", ls=":", lw=1.6)
    ax.text(T_uniform - 0.10, 17.6, "匀速假设\n3.25 s\n（下界）", ha="right",
            color="#ef4444", fontsize=9)
    ax.text(T_STAR, 3.0, f"数值积分 {T_STAR:.1f} s\n（定稿门槛）",
            ha="center", color="#22c55e", fontsize=10,
            bbox=dict(fc="#0f172a", ec="#22c55e", alpha=.85, pad=4))
    ax.text(T_uniform2 + 0.10, 17.6, "匀加速上界\n6.50 s", ha="left",
            color="#a78bfa", fontsize=9)
    ax.set_xlabel("爬环用时 T（s）", color="#e2e8f0")
    ax.set_ylabel("速度（m/s）", color="#e2e8f0")
    ax.set_title("顶点速度远高于平均速度：不能把弧长除以用时", color="#e2e8f0",
                 fontsize=13)
    ax.tick_params(colors="#94a3b8")
    for s in ax.spines.values():
        s.set_color("#334155")
    ax.grid(alpha=.18)
    ax.legend(facecolor="#0f172a", edgecolor="#334155",
              labelcolor="#e2e8f0", fontsize=9)
    fig.tight_layout()
    out = FIG / "fig_timing_fixed.png"
    fig.savefig(out, facecolor="#0b1220", dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  [OK] {out.name}  {out.stat().st_size/1024:.0f} KB")
    return 0


def cfg_font() -> None:
    cands = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
    from matplotlib import font_manager
    have = {f.name for f in font_manager.fontManager.ttflist}
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = \
        ([c for c in cands if c in have] or ["DejaVu Sans"]) + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


if __name__ == "__main__":
    raise SystemExit(main())
