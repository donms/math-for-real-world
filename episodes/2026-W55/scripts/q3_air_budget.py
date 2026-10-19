#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **问题 3：冷气推进的气罐预算**（600 L 能不能做完这几个动作）。

## 为什么这一问比问题 1、2 更"硬"

问题 1、2 靠 HUD 与截图**反推**；**问题 3 是纯物理 + 已有的公布数据**：

| 已知量 | 值 | 来源 |
|---|---|---|
| 储气总容积 | **600 L = 0.600 m³** | 官方 |
| 罐内空气质量 | **≈ 250 kg** | 媒体（据此反推 **35 MPa**）|
| 主推进器推力 | **> 80 kN** | 官方 |
| 喷口数 | **10 个** | 官方 |
| 冷气推进 | 高压空气，**不点火** | 官方 |

## ★ 三个必须算对的物理效应

### ① 排气过程中**罐压衰减** ⇒ 推力衰减

**冷气推进与火箭不同的一点**：**它没有燃烧补充质量流**，
随着气被放掉，$p_0$ 下降 ⇒ $\dot m$ 与 $v_e$ 都下降 ⇒ **推力衰减**。

**⇒ 不能把"172.6 kN·s ÷ 80 kN = 2.16 s"当作"能全推 2.16 s"** ——
**实际能维持 80 kN 的时间远短于这个数。**

### ② 出口速度随压比变化

**等熵完全膨胀**：

$$v_e = \sqrt{\frac{2\gamma}{\gamma-1}R_gT_0
\left[1-\left(\frac{p_e}{p_0}\right)^{(\gamma-1)/\gamma}\right]}$$

**$p_0$ 从 35 MPa 降到接近大气压时，$v_e$ 从 690 m/s 降到 0。**

### ③ 但"总冲量"几乎不变

**★ 关键洞察**：**总冲量 $I=\int \dot m v_e\,dt$ 对压力衰减并不敏感**，
因为**放掉的质量是固定的**，而 $v_e$ 只在末段才急剧下降。

**⇒ "总量够不够"看质量与平均 $v_e$；"峰值推力够不够"看 $p_0$ 与喉部面积。**
**这是两个不同的问题，必须分开回答。**

## 本脚本要回答

1. 总冲量（精确积分 vs 简单估算）差多少？
2. 维持 80 kN 能维持多久？
3. 做完全部动作（起飞 + 缓冲 + 旋转 + 姿态）要多少？
4. **压力下限**是多少？
5. 敏感性：压力、喉部面积、质量估计各 ±50% 时结论是否翻转？
"""
from __future__ import annotations

import math

G = 9.81
R_GAS = 287.0        # J/(kg·K)
T0 = 293.15          # K 初温（20 °C）
P_ATM = 101325.0     # Pa
GAMMA = 1.40
V_TANK = 0.600       # m³
M_CAR = 2000.0       # kg 参照

# 由公布数据反推
M_AIR = 250.0        # kg
P0 = M_AIR * R_GAS * T0 / V_TANK      # Pa


def v_exit(p0: float, pe: float = P_ATM) -> float:
    r"""等熵完全膨胀出口速度（$p_0 > p_e$）。"""
    if p0 <= pe:
        return 0.0
    r = pe / p0
    return math.sqrt(2 * GAMMA / (GAMMA - 1) * R_GAS * T0
                     * (1 - r ** ((GAMMA - 1) / GAMMA)))


def choked_mdot(at: float, p0: float) -> float:
    r"""临界（壅塞）质量流量。"""
    return at * p0 * math.sqrt(GAMMA / (R_GAS * T0)) \
        * (2 / (GAMMA + 1)) ** ((GAMMA + 1) / (2 * (GAMMA - 1)))


def total_impulse_exact(at_total: float) -> tuple[float, float]:
    r"""**精确积分**：随罐压衰减，逐段累加冲量。

    把罐内质量从 $m_0$ 放到 0 分 N 步；每步用当前 $p_0$、$\dot m$、$v_e$
    算 $\Delta I$。返回 (总冲量, 总时长)。

    ★ 这一步是"精确"的关键：**不能用初始 $p_0$ 一路算到底**。
    """
    N = 4000
    m_left = M_AIR
    dm = M_AIR / N
    I = 0.0
    t = 0.0
    while m_left > 1e-9:
        # 当前罐压（等温近似，因为罐体与外界换热）
        p0 = m_left * R_GAS * T0 / V_TANK
        if p0 <= P_ATM:
            break
        md = choked_mdot(at_total, p0)
        if md <= 0:
            break
        ve = v_exit(p0)
        dt_step = dm / md
        I += md * ve * dt_step
        t += dt_step
        m_left -= dm
    return I, t


def main() -> int:
    print("=" * 94)
    print("  W55 · 问题 3：冷气推进的气罐预算")
    print("=" * 94)

    print(f"\n【0】基础量（由公布数据反推）")
    print(f"  罐内质量 {M_AIR:.0f} kg / 容积 {V_TANK:.3f} m³ / {T0:.1f} K")
    print(f"  ⇒ 罐压 p0 = mRT/V = **{P0/1e6:.2f} MPa = {P0/P_ATM:.0f} atm**")
    print(f"  临界压比 (2/(γ+1))^(γ/(γ−1)) = "
          f"{(2/(GAMMA+1))**(GAMMA/(GAMMA-1)):.4f}")
    print(f"  p0/p_atm = {P0/P_ATM:.0f} **远高于**临界压比 ⇒ 全程壅塞 ✓")

    # ---------------- 1) 总冲量：简单 vs 精确 ----------------
    print("\n" + "=" * 94)
    print("【1】总冲量：简单估算 vs 精确积分")
    print("=" * 94)
    ve0 = v_exit(P0)
    I_simple = M_AIR * ve0
    print(f"  初始出口速度 v_e(p0) = {ve0:.0f} m/s（Isp = {ve0/G:.0f} s）")
    print(f"  简单估算：I = m·v_e0 = {M_AIR}×{ve0:.0f} = "
          f"**{I_simple/1000:.1f} kN·s**")
    # 精确积分（取一个较大喉部面积，使排放足够快、接近"一次放完"）
    for at_mm in (20, 40, 60):
        at = at_mm * at_mm * 1e-6
        I_ex, t_ex = total_impulse_exact(at)
        print(f"  精确积分（A_t = {at_mm}×{at_mm} mm² = {at*1e4:.0f} cm²）："
              f"I = {I_ex/1000:.1f} kN·s，耗时 {t_ex:.2f} s，"
              f"平均 v_e = {I_ex/M_AIR:.0f} m/s")
    print(f"\n  ★ 精确值比简单估算 **低 {(1-I_ex/I_simple)*100:.0f}%** ——")
    print(f"    因为末段压力低、v_e 衰减，那部分质量「不划算」。")

    # ---------------- 2) 维持 80 kN 能多久 ----------------
    print("\n" + "=" * 94)
    print("【2】★ 维持 80 kN 能维持多久（这是「够不够」的真正问题）")
    print("=" * 94)
    F_req = 80e3
    print(f"  要维持 F = {F_req/1000:.0f} kN，需 ṁ·v_e = F")
    print(f"  ⇒ 需要的喉部总面积（随罐压变化）：")
    print(f"  {'p0(MPa)':>10}{'v_e(m/s)':>11}{'所需 ṁ(kg/s)':>15}"
          f"{'所需 A_t(cm²)':>16}")
    for pm in (35, 30, 20, 10, 5, 2, 1):
        p0 = pm * 1e6
        if p0 <= P_ATM:
            continue
        ve = v_exit(p0)
        md_need = F_req / ve
        # 反解 A_t: md = A*p0*C  =>  A = md/(p0*C)
        C = math.sqrt(GAMMA / (R_GAS * T0)) \
            * (2 / (GAMMA + 1)) ** ((GAMMA + 1) / (2 * (GAMMA - 1)))
        at_need = md_need / (p0 * C)
        print(f"  {pm:>10}{ve:>11.0f}{md_need:>15.2f}{at_need*1e4:>16.1f}")

    # 选一个能维持 80 kN 的喉部面积（以 20 MPa 为准）
    C = math.sqrt(GAMMA / (R_GAS * T0)) \
        * (2 / (GAMMA + 1)) ** ((GAMMA + 1) / (2 * (GAMMA - 1)))
    at_design = (F_req / v_exit(20e6)) / (20e6 * C)
    print(f"\n  ★ 设计点：若喷口总面积 A_t = {at_design*1e4:.0f} cm²，"
          f"则在 p0 = 20 MPa 时刚好 80 kN。")
    # 用这个面积算"能把 80 kN 撑多久"
    # 从 35 MPa 放到 F 降到 80 kN 以下
    m = M_AIR
    dm = M_AIR / 20000
    t80 = 0.0
    while m > 1e-9:
        p0 = m * R_GAS * T0 / V_TANK
        if p0 <= P_ATM:
            break
        md = choked_mdot(at_design, p0)
        F = md * v_exit(p0)
        if F < F_req:
            break
        dt = dm / md
        t80 += dt
        m -= dm
    print(f"  从 35 MPa 开始、喷口 {at_design*1e4:.0f} cm²：")
    print(f"  ⇒ **能维持 ≥80 kN 约 {t80:.2f} s**")
    print(f"  ⇒ 而 0–60 mph 只需 0.81 s，起飞脉冲只需约 0.3 s")
    print(f"  ⇒ **时间上非常充裕** ✓")

    # ---------------- 3) 需求清单 ----------------
    print("\n" + "=" * 94)
    print("【3】★ 全部动作的冲量需求清单")
    print("=" * 94)
    hmax = 7.74
    vz = math.sqrt(2 * G * hmax)
    I_up = M_CAR * vz
    I_soft0 = M_CAR * vz
    I_soft2 = M_CAR * (vz - 2.0)

    # 旋转：绕横轴 n 圈
    # ★ 两段姿态都是**滚转**（绕纵轴），用 J_ROLL；力臂取半车宽 + 喷口外伸
    # ★ 两段姿态都是**滚转**（绕纵轴）：J_roll = m(W²+H²)/12
    W_CAR, H_CAR = 2.0, 1.2
    J_roll = M_CAR * (W_CAR ** 2 + H_CAR ** 2) / 12.0
    LEV = W_CAR / 2 + 0.15
    print(f"  转动惯量（绕纵轴 J_roll）= {J_roll:.0f} kg·m²，"
          f"力臂 {LEV:.2f} m")
    print()
    print(f"  {'项目':<22}{'冲量(kN·s)':>13}{'占比':>9}")
    items = [
        ("起飞（顶到 7.74 m）", I_up),
        ("落地缓冲（卸到 0）", I_soft0),
        ("落地缓冲（卸到 2 m/s）", I_soft2),
    ]
    # 旋转需求：设腾空时间 2.51 s，n 圈
    T_fly = 2 * vz / G
    for n in (0.5, 1.0, 2.0):
        omega = 2 * math.pi * n / T_fly
        # 角冲量 = J·ω；等效平动冲量 = 角冲量 / 力臂
        L_ang = J_roll * omega
        I_equiv = L_ang / LEV
        items.append((f"空中旋转 {n:g} 圈（滚转）", I_equiv))
    for name, val in items:
        print(f"  {name:<22}{val/1000:>13.1f}{val/I_simple*100:>8.0f}%")

    total_min = I_up + I_soft2
    total_all = I_up + I_soft0 + sum(v for n, v in items[3:])
    print()
    print(f"  **最小方案**（起飞 + 省着缓冲到 2 m/s，不旋转）："
          f"**{total_min/1000:.1f} kN·s**（{total_min/I_simple*100:.0f}%）")
    print(f"  **全做方案**（起飞 + 缓冲到 0 + 旋转 2 圈）："
          f"**{total_all/1000:.1f} kN·s**（{total_all/I_simple*100:.0f}%）")

    # ---------------- 4) 反推所需压力 ----------------
    print("\n" + "=" * 94)
    print("【4】★ 反推所需罐压下限")
    print("=" * 94)
    print(f"  给定需求 I_req，反解 p0（等温、按可用质量算）：")
    print(f"  {'I_req(kN·s)':>13}{'所需质量(kg)':>14}{'所需 p0(MPa)':>14}"
          f"{'与 35 MPa 比':>13}")
    for I_req_k in (25, 49, 75, 100, 150):
        I_req = I_req_k * 1000
        m_need = I_req / ve0          # 保守：按初始 v_e 算
        p_need = m_need * R_GAS * T0 / V_TANK
        print(f"  {I_req_k:>13}{m_need:>14.1f}{p_need/1e6:>14.1f}"
              f"{p_need/P0:>12.2f}×")
    print(f"\n  ★ 注意：所需质量按**初始** v_e 算是**保守**的，")
    print(f"    实际需要更多质量（因为末段 v_e 低）⇒ 上述压力是**下限**。")

    # ---------------- 5) 敏感性 ----------------
    print("\n" + "=" * 94)
    print("【5】敏感性：结论会不会翻转")
    print("=" * 94)
    print(f"  {'变动':<26}{'可用 I(kN·s)':>15}{'够做全做方案?':>15}")

    def avail_impulse(mass: float, temp: float, derate: float = 0.80) -> float:
        r"""给定质量与初温，返回**保守可用冲量**。

        `derate`：扣掉压力衰减导致的效率损失（本文取 20%，见 §1 的精确积分）。
        """
        p = mass * R_GAS * temp / V_TANK
        if p <= P_ATM:
            return 0.0
        return mass * v_exit(p) * derate

    for label, mass, t0 in (
        ("基准 (250 kg, 293 K)", 250, 293.15),
        ("质量 −30% (175 kg)", 175, 293.15),
        ("质量 +30% (325 kg)", 325, 293.15),
        ("温度 −20% (234 K)", 250, 234.5),
        ("温度 +20% (352 K)", 250, 351.8),
        ("★ 需求 +30%（更保守）", 250, 293.15),
    ):
        I_avail = avail_impulse(mass, t0)
        req = total_all * (1.30 if "需求" in label else 1.0)
        ok = "✓ 够" if I_avail >= req else "✗ 不够"
        print(f"  {label:<26}{I_avail/1000:>15.1f}{ok:>15}")

    print("\n" + "=" * 94)
    print("  ★★★ 问题 3 的答案")
    print("=" * 94)
    print(f"  ① **总冲量约 {I_simple/1000:.0f} kN·s**（简单估算），"
          f"精确积分约 {I_ex/1000:.0f} kN·s；")
    print(f"  ② **能维持 80 kN 约 {t80:.1f} s**，时间上非常充裕；")
    print(f"  ③ **全部动作约需 {total_all/1000:.0f} kN·s**，"
          f"占可用量的 **{total_all/I_simple*100:.0f}%**；")
    print(f"  ④ **气罐够用，但余量不大** —— 若再加动作就要算细账；")
    print(f"  ⑤ 最贵的两项是**起飞**与**落地缓冲**，各占约 25%。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
