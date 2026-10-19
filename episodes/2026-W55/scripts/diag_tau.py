#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **裁决**：从 35 → 20 MPa 到底要 0.52 s 还是 0.68 s？

## 两个数怎么来的

| 数 | 怎么算 | 问题 |
|---|---|---|
| **0.52 s** | $\Delta m / \dot m_0$（用**初始**出气率）| 高估了平均出气率 |
| **0.68 s** | 数值积分（$\dot m$ 随 $p_0$ 衰减）| 正确 |

## 为什么 0.52 是错的

**$\dot m \propto p_0$**  ⇒  **随着放气，出气率持续下降**。
用**初始** $\dot m_0$ 去除总质量，等于假设"全程按最快速度放气"
⇒ **必然低估时间**。

## 解析解

由 $\dot m_t = -p_0 V/(R T)C A_t$ 与 $p_0 = m R T/V$：

$$\frac{dm}{dt} = -m\,C A_t$$

$$\Rightarrow\quad m(t) = m_0 e^{-C A_t t}
\quad\Rightarrow\quad
\boxed{t = \frac{1}{C A_t}\ln\frac{m_0}{m_1}}$$

**⇒ 指数衰减，时间与 $\ln(m_0/m_1)$ 成正比。**

**★ 这是一个"一阶惯性"过程，时间常数 $\tau = 1/(C A_t)$。**
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph      # noqa: E402
import nozzles as nz      # noqa: E402


def main() -> int:
    print("=" * 88)
    print("  W55 · 裁决：35 → 20 MPa 需要多久")
    print("=" * 88)

    p0i = ph.P_TANK
    at = nz.area_for_force(80e3, 20e6)
    C = nz.C_CHOKED
    print(f"\n  罐 {ph.M_AIR} kg / {ph.V_TANK} m³ ⇒ p0 = {p0i/1e6:.2f} MPa")
    print(f"  喉部面积（20 MPa 设计点）= {at*1e4:.2f} cm²")
    print(f"  壅塞常数 C = {C:.6e}")

    # ---- 解析解 ----
    # ★ 由 ṁ = C·A_t·p0 与 p0 = mRT/V 得
    #     dm/dt = −ṁ = −C·A_t·(RT/V)·m  ⇒  一阶惯性
    #     τ = V / (C·A_t·R·T)      ← **量纲：m³ / (m·m²·J/(kg·K)·K) = s**
    K = C * at * ph.R_GAS * ph.T0 / ph.V_TANK      # 1/s
    tau = 1.0 / K
    m1 = ph.M_AIR * (20e6 / p0i)
    t_analytic = tau * math.log(ph.M_AIR / m1)
    print(f"\n【解析解】dm/dt = K m，K = C·A_t·RT/V = "
          f"{K:.4f} s⁻¹")
    print(f"  时间常数 τ = 1/K = **{tau:.3f} s**")
    print(f"  目标质量 m1 = {m1:.1f} kg（对应 20 MPa）")
    print(f"  t = τ·ln(m0/m1) = {tau:.3f}×ln({ph.M_AIR:.0f}/{m1:.1f}) "
          f"= **{t_analytic:.3f} s**")

    # ---- 数值积分 ----
    t = 0.0
    m = ph.M_AIR
    dt = 1e-4
    while m > m1 and t < 10:
        p = m * ph.R_GAS * ph.T0 / ph.V_TANK
        md = nz.mdot_of_area(at, p)
        m -= md * dt
        t += dt
    print(f"\n【数值积分】t = **{t:.3f} s**（与解析解差 "
          f"{abs(t-t_analytic)*1000:.1f} ms）")

    # ---- 错误算法 ----
    md0 = nz.mdot_of_area(at, p0i)
    t_wrong = (ph.M_AIR - m1) / md0
    print(f"\n【错误算法】Δm/ṁ₀ = {ph.M_AIR-m1:.1f}/{md0:.1f} = "
          f"**{t_wrong:.3f} s**")
    print(f"  ⇒ 比真值低 **{(1-t_wrong/t)*100:.0f}%** ——")
    print(f"    因为用初始 ṁ 除总质量，等于假设全程按最快出气。")

    # ---- 结论 ----
    print("\n" + "=" * 88)
    print("  ★ 裁决结果")
    print("=" * 88)
    print(f"  ① **正确值 ≈ {t:.2f} s**（解析 {t_analytic:.2f} s）")
    print(f"  ② 我先前写 0.52 s 是**错的**（用了初始出气率）")
    print(f"  ③ 0.68 s 才是对的（那是图 3 的数值积分结果，本来就对）")
    print(f"  ④ **⇒ 我在文档里把对的改成了错的，现在要改回来**")
    print()
    print(f"  ★★ 教训：**「总量 ÷ 初始速率」永远低估时间**——")
    print(f"     只要速率随某个状态量衰减，就必须用积分或解析解。")
    print(f"     判据：dm/dt ∝ m ⇒ **一阶惯性**。")
    print()
    print(f"  ★ 附带结论：**时间常数 τ = {tau:.3f} s** ——")
    print(f"    这就是「气罐的时间尺度」，与 0.81 s 的加速成绩同量级。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
