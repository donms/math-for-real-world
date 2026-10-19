#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **风扇是否在工作的可检验判据**。

## 问题

> 用户："没有风扇是不是连圆环都爬不上？"

**答案：不是。** 无风扇也能爬，但顶点必须够快：

$$N_{\text{no fan}}(\theta)=\frac{mv^2}{R}-mg\cos\theta\ \ge\ 0
\quad\xrightarrow{\theta=0}\quad
v\ \ge\ v^*=\sqrt{gR}$$

有风扇（$\lambda=F_a/mg$）时：

$$N=F_a+\frac{mv^2}{R}-mg\cos\theta$$

$$\boxed{\text{风扇把"贴住"从动力学要求变成静力学要求}}$$

## 本文给出的可检验判据

**实拍里若能估计出顶点附近的车速 $v_{\text{top}}$：**

| 观测 | 结论 |
|---|---|
| $v_{\text{top}}<v^*$ 却仍贴住 | **风扇必然在工作**（无风扇必脱离）|
| $v_{\text{top}}\ge v^*$ | 无法区分（无风扇也贴得住）|

$$\boxed{\text{这是一条能反过来验证实拍的推论，本文自己算出来的}}$$

## 附：从爬环时间反推平均车速

半圈弧长 $\pi R$，用时 $T_{\text{climb}}$：

$$\bar v=\frac{\pi R}{T_{\text{climb}}}$$

**视频里 HUD 的 ALTITUDE 从 0 涨到 67.5 ft（20.6 m）的时长即可估 $T_{\text{climb}}$。**
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
H_TOP = 2 * R
V_STAR = math.sqrt(G * R)


def N_no_fan(v: float, th: float = 0.0) -> float:
    return M * v * v / R - M * G * math.cos(th)


def N_fan(v: float, lam: float, th: float = 0.0) -> float:
    return lam * M * G + M * v * v / R - M * G * math.cos(th)


def cfg() -> None:
    cands = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
    have = {f.name for f in font_manager.fontManager.ttflist}
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = \
        ([c for c in cands if c in have] or ["DejaVu Sans"]) + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def main() -> int:
    cfg()
    FIG.mkdir(parents=True, exist_ok=True)
    print("=" * 84)
    print("  风扇是否在工作：可检验判据")
    print("=" * 84)
    print(f"\n  R = {R:.1f} m，顶点高 {H_TOP:.0f} m")
    print(f"  无风扇所需最低顶点车速 v* = sqrt(gR) = "
          f"**{V_STAR:.2f} m/s（{V_STAR*3.6:.1f} km/h）**")

    # ---- 判据表 ----
    print(f"\n  {'顶点车速':>12}{'km/h':>9}{'无风扇 N':>12}"
          f"{'λ=2 时 N':>12}{'判定':>22}")
    rows = []
    for v in (0.0, 2.0, 4.0, 6.0, 8.0, 10.15, 12.0, 15.0):
        n0 = N_no_fan(v) / 1000
        n2 = N_fan(v, 2.0) / 1000
        if v < V_STAR - 1e-6:
            verdict = "无风扇必脱离 ⇒ 靠风扇"
        else:
            verdict = "无风扇也贴得住 ⇒ 无法区分"
        rows.append((v, n0, n2, verdict))
        print(f"  {v:>10.2f} m/s{v*3.6:>9.1f}{n0:>+12.2f}{n2:>+12.2f}"
              f"  {verdict}")

    # ---- 爬环时间 → 平均车速 ----
    print(f"\n  从爬环时间反推平均车速（弧长 πR = {math.pi*R:.1f} m）")
    print(f"  {'爬环用时 T':>12}{'平均车速':>12}{'km/h':>9}"
          f"{'无风扇能否贴住':>18}")
    for T in (2.0, 2.5, 3.0, 3.5, 4.0, 5.0):
        vb = math.pi * R / T
        ok = "可以" if vb >= V_STAR else "**不能**"
        print(f"  {T:>10.1f} s{vb:>11.2f} m/s{vb*3.6:>9.1f}"
              f"  {ok:>16}")

    print("\n" + "=" * 84)
    print("  ★★★ 结论")
    print("=" * 84)
    print(f"  ① **没有风扇也能爬环**：只要顶点车速 ≥ {V_STAR:.1f} m/s"
          f"（{V_STAR*3.6:.0f} km/h）")
    print(f"  ② 但**从静止起步**要在 {math.pi*R:.0f} m 内把速度提到 "
          f"{V_STAR:.1f} m/s，需平均切向加速度 "
          f"{V_STAR**2/(2*math.pi*R):.1f} m/s²，轮胎够用")
    print(f"  ③ **风扇的作用不是「能爬」，而是「能慢慢爬」**：λ=2 时顶点"
          f"即使 v=0 也有 N = mg")
    print(f"  ④ **可检验判据**：实拍中若顶点车速明显低于 "
          f"{V_STAR*3.6:.0f} km/h 却仍贴住 ⇒ 风扇必然在工作")
    print("=" * 84)

    # ---- 图 ----
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    fig.patch.set_facecolor("#0b1220")
    ax.set_facecolor("#0b1220")
    vs = [i * 16.0 / 400 for i in range(401)]
    ax.plot(vs, [N_no_fan(v) / 1000 for v in vs], color="#ef4444", lw=2.4,
            label="无风扇（λ=0）")
    ax.plot(vs, [N_fan(v, 2.0) / 1000 for v in vs], color="#22c55e", lw=2.4,
            label="2G 风扇（λ=2）")
    ax.axhline(0, color="#94a3b8", ls="--", lw=1.2)
    ax.axvline(V_STAR, color="#f59e0b", ls=":", lw=1.6)
    ax.fill_between([0, V_STAR], -300, 0, color="#ef4444", alpha=.10)
    ax.annotate(f"v* = {V_STAR:.2f} m/s\n({V_STAR*3.6:.1f} km/h)",
                xy=(V_STAR, 0), xytext=(V_STAR + 1.2, -30),
                color="#f59e0b", fontsize=10,
                arrowprops=dict(arrowstyle="->", color="#f59e0b"))
    ax.text(V_STAR / 2, -55, "无风扇：\n这一区间必脱离",
            ha="center", color="#ef4444", fontsize=10)
    ax.set_xlabel("顶点车速 v（m/s）", color="#e2e8f0")
    ax.set_ylabel("顶点法向力 N（kN）", color="#e2e8f0")
    ax.set_title(f"顶点是否能贴住：无风扇 vs 2G 风扇（R={R:.1f} m）",
                 color="#e2e8f0", fontsize=13)
    ax.tick_params(colors="#94a3b8")
    for s in ax.spines.values():
        s.set_color("#334155")
    ax.grid(alpha=.18)
    ax.legend(facecolor="#0f172a", edgecolor="#334155",
              labelcolor="#e2e8f0", fontsize=10)
    ax.set_ylim(-120, 120)
    fig.tight_layout()
    out = FIG / "fig_fan_verdict.png"
    fig.savefig(out, facecolor="#0b1220", dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  [OK] {out.name}  {out.stat().st_size/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
