#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **空中调姿**：半圈/整圈要多少力、用哪几个喷口、怎么配合。

## ★ 先纠正我上一版的错误

上一版我假设"调姿喷口 500 N"，算出**半圈需 4.49 s、整圈需 6.35 s**，
而腾空只有 **2.5–3.7 s** ⇒ **判定"时间不够"**，
但结论里我却写了"时间上够" —— **自相矛盾**。

**根因**：**500 N 这个假设太小了。**
一个 2 000 kg 的车要绕横轴转半圈，500 N 的喷口配 2.25 m 力臂
只能给出 2 250 N·m，而 $J_{\text{pitch}} = 3\,375$ kg·m²
⇒ 角加速度只有 0.67 rad/s² ⇒ **转动太慢**。

**⇒ 本版改为"由时间反解所需推力"**，这才是有意义的问法。

## 两种姿态要求（用户给定）

| 场景 | 旋转 | 起始 | 终止 | 难点 |
|---|---|---|---|---|
| **倒挂**（问题 1）| **半圈 180°** | 完全倒置 | 正立 | ★ **姿态唯一**，停不准就撞顶 |
| **飞跃**（问题 2）| **整圈 360°** | 正立 | 正立 | 有对称余量，可整圈 |

## ★ 关键：绕哪个轴转，代价差 4 倍

| 轴 | $J$ (kg·m²) | 说明 |
|---|---|---|
| **横轴（pitch，俯仰）** | **3 375** | 车"前后翻转" |
| **纵轴（roll，滚转/桶滚）** | **854** | 车"绕自身长轴滚" |
| **竖轴（yaw，偏航）** | **3 517** | 车"水平打转" |

$$\frac{J_{\text{pitch}}}{J_{\text{roll}}} = \frac{3375}{854} = \mathbf{4.0}$$

**⇒ 桶滚（roll）比前后翻（pitch）省 4 倍角动量** ——
因为车**又长又窄**，绕自身长轴的惯性最小。
"""
from __future__ import annotations

import math

G = 9.81
M_CAR = 2000.0
L_CAR, W_CAR, H_CAR = 4.5, 2.0, 1.2

J_PITCH = M_CAR * (L_CAR ** 2 + H_CAR ** 2) / 12.0
J_ROLL = M_CAR * (W_CAR ** 2 + H_CAR ** 2) / 12.0
J_YAW = M_CAR * (L_CAR ** 2 + W_CAR ** 2) / 12.0

R_ARM = 2.25          # 力臂（半车长）
T_INVERT = 3.7        # 倒挂腾空（HUD 实测）
T_FLAT = 2 * math.sqrt(2 * 9.81 * 7.74) / 9.81   # 飞跃腾空 2.51 s


def bang_bang(angle_rad: float, J: float, T: float
              ) -> tuple[float, float]:
    r"""**bang-bang 最小时间**：加速一半、减速一半。

    $$\theta = \alpha\left(\frac{T}{2}\right)^2
    \quad\Longrightarrow\quad
    \alpha = \frac{4\theta}{T^2}$$

    返回 (所需角加速度 α, 所需力偶矩 M = J·α)。
    """
    alpha = 4 * angle_rad / T ** 2
    return alpha, J * alpha


def main() -> int:
    print("=" * 94)
    print("  W55 · 空中调姿：半圈 / 整圈 要多少力")
    print("=" * 94)

    print(f"\n  车体 {L_CAR}×{W_CAR}×{H_CAR} m，{M_CAR:.0f} kg")
    print(f"  J_pitch = **{J_PITCH:.0f}** kg·m²（横轴，前后翻）")
    print(f"  J_roll  = **{J_ROLL:.0f}** kg·m²（纵轴，桶滚）★ 最小")
    print(f"  J_yaw   = **{J_YAW:.0f}** kg·m²（竖轴，水平转）")
    print(f"\n  ★ J_pitch / J_roll = **{J_PITCH/J_ROLL:.1f} 倍**")
    print(f"  ⇒ 桶滚用滚转轴最划算；若必须绕横轴翻，代价大 "
          f"{J_PITCH/J_ROLL:.0f} 倍")

    # ---------------- 1) 由时间反解所需力 ----------------
    print("\n" + "=" * 94)
    print("【1】★ 由时间反解所需力偶与单喷口推力")
    print("=" * 94)
    print(f"  腾空时间：倒挂 {T_INVERT:.2f} s；飞跃 {T_FLAT:.2f} s")
    print(f"  力偶用**成对喷口**（各 F，力臂 r={R_ARM} m）⇒ M = 2 F r")
    print()
    print(f"  {'场景':<22}{'轴':<8}{'T(s)':>7}{'α(rad/s²)':>12}"
          f"{'M(N·m)':>11}{'每喷口 F(N)':>13}{'(kgf)':>9}")
    rows = []
    for label, ang_deg, T in (
        ("倒挂 半圈 180°", 180, T_INVERT),
        ("倒挂 半圈 180°", 180, T_INVERT * 0.7),      # 留 30% 余量
        ("飞跃 整圈 360°", 360, T_FLAT),
        ("飞跃 整圈 360°", 360, T_FLAT * 0.7),
    ):
        for axis, J in (("pitch", J_PITCH), ("roll", J_ROLL)):
            a_rad = math.radians(ang_deg)
            alpha, M = bang_bang(a_rad, J, T)
            F = M / (2 * R_ARM)
            print(f"  {label:<22}{axis:<8}{T:>7.2f}{alpha:>12.2f}"
                  f"{M:>11.0f}{F:>13.0f}{F/G:>9.0f}")
            rows.append((label, axis, T, alpha, M, F))

    # ---------------- 2) 哪个轴更可行 ----------------
    print("\n" + "=" * 94)
    print("【2】★ 结论：用哪个轴？")
    print("=" * 94)
    for label, ang_deg, T in (
        ("倒挂 半圈（T=3.7 s）", 180, T_INVERT),
        ("飞跃 整圈（T=2.51 s）", 360, T_FLAT),
    ):
        a_rad = math.radians(ang_deg)
        _, M_p = bang_bang(a_rad, J_PITCH, T)
        _, M_r = bang_bang(a_rad, J_ROLL, T)
        Fp = M_p / (2 * R_ARM)
        Fr = M_r / (2 * R_ARM)
        print(f"\n  {label}")
        print(f"    pitch（前后翻）：M = {M_p:>6.0f} N·m，每喷口 "
              f"**{Fp:>5.0f} N（{Fp/G:.0f} kgf）**")
        print(f"    roll （桶滚）  ：M = {M_r:>6.0f} N·m，每喷口 "
              f"**{Fr:>5.0f} N（{Fr/G:.0f} kgf）**")
        print(f"    ⇒ roll 省 {M_p/M_r:.1f} 倍")

    # ---------------- 3) 与主推进器对比 ----------------
    print("\n" + "=" * 94)
    print("【3】★★ 调姿喷口与主推进器的规格差")
    print("=" * 94)
    a_rad = math.pi
    _, M = bang_bang(a_rad, J_PITCH, T_INVERT)
    F_att = M / (2 * R_ARM)
    F_main = 80e3
    print(f"  主推进器：**{F_main/1000:.0f} kN**")
    print(f"  调姿喷口：**{F_att/1000:.1f} kN**（半圈俯仰，3.7 s）")
    print(f"  ⇒ 相差 **{F_main/F_att:.0f} 倍**，**两个数量级**")
    print()
    print("  ★ 这解释了为什么「10 个喷口」必须**分规格**：")
    print("    · 主推进/竖推：几十 kN，管「起飞」；")
    print("    · 调姿：1–3 kN，管「转过来」。")
    print("    ⇒ 用同一套既推不动车，也浪费气。")

    # ---------------- 4) 喷口布局与点火时序 ----------------
    print("\n" + "=" * 94)
    print("【4】★★★ 10 个喷口的分工与点火时序")
    print("=" * 94)
    layout = [
        ("1", "车尾 主推进", "纵轴 +X", "加速/抬升主推力", "大 (>80 kN)"),
        ("2", "车底 竖推", "竖直 +Z", "起飞抬升（飞跃）", "大 (20 kN)"),
        ("3", "车尾 竖推", "竖直 +Z", "抬车尾 → 抬头（pitch+）", "中 (5 kN)"),
        ("4", "车头 竖推", "竖直 +Z", "抬头 → 抬车头（pitch−）", "中 (5 kN)"),
        ("5", "车顶 竖推", "竖直 −Z", "倒挂时朝地推（分离）", "中 (5 kN)"),
        ("6", "左侧 横向", "横向 ±Y", "滚转力偶（roll）", "小 (2 kN)"),
        ("7", "右侧 横向", "横向 ±Y", "滚转力偶（roll）", "小 (2 kN)"),
        ("8", "车头 横向", "横向 ±Y", "偏航力偶（yaw）", "小 (2 kN)"),
        ("9", "车尾 横向", "横向 ±Y", "偏航力偶（yaw）", "小 (2 kN)"),
        ("10", "车侧 反推", "纵轴 −X", "减速/姿态配平", "中 (5 kN)"),
    ]
    print(f"  {'#':>3}{'位置':<14}{'方向':<11}{'作用':<24}{'规格':>13}")
    for n, pos, d, use, spec in layout:
        print(f"  {n:>3}{pos:<14}{d:<11}{use:<24}{spec:>13}")
    print()
    print("  ★ 关键：**产生纯力偶必须成对、反向、等量点火**")
    print("    · 单喷口点火 = 力矩 + 平动（车会侧移）")
    print("    · 成对反向 = 只有力矩，平动抵消")
    print("    ⇒ 这就是「为什么需要这么多个喷口」的物理答案。")

    # ---------------- 5) 点火时序（半圈 vs 整圈） ----------------
    print("\n" + "=" * 94)
    print("【5】★ 点火时序：半圈与整圈的区别")
    print("=" * 94)
    print("\n  ── 倒挂：半圈 180°（pitch），T = 3.7 s ──")
    print(f"    0.00–{T_INVERT/2:.2f} s：喷口 3（车尾竖推）点火 → 车头抬起")
    print(f"    {T_INVERT/2:.2f}–{T_INVERT:.2f} s：喷口 4（车头竖推）点火 → 反向减速")
    print(f"    3.70 s 时：姿态 = 正立，ω = 0 ⇒ **落地**")
    print(f"    ★ 减速段必须**精确**在 180° 时把 ω 归零，"
          f"否则车顶朝地")
    print()
    print("  ── 飞跃：整圈 360°（roll），T = 2.51 s ──")
    print(f"    0.00–{T_FLAT/2:.2f} s：左侧喷口 6 点火 → 开始滚转")
    print(f"    {T_FLAT/2:.2f}–{T_FLAT:.2f} s：右侧喷口 7 点火 → 反向减速")
    print(f"    2.51 s 时：姿态 = 正立（转了一整圈），ω = 0 ⇒ 落地")
    print(f"    ★ 整圈有**对称余量**：多转 20° 还能靠视觉/悬挂吸收；")
    print(f"      半圈多转 20° 就是车顶擦地。")

    print("\n" + "=" * 94)
    print("  ★★★ 结论")
    print("=" * 94)
    # ★ 用户 2026-10-17 确认：**两段都是滚转**（绕纵轴）
    F_half = bang_bang(math.pi, J_ROLL, T_INVERT)[1] / (2 * R_ARM)
    F_circ = bang_bang(2 * math.pi, J_ROLL, T_FLAT)[1] / (2 * R_ARM)
    print(f"  ① **两段都是滚转**（绕纵轴，J_roll = {J_ROLL:.0f}）：")
    print(f"     · 倒挂半圈：每喷口约 **{F_half/1000:.2f} kN**"
          f"（T = {T_INVERT:.1f} s）；")
    print(f"     · 飞跃整圈：每喷口约 **{F_circ/1000:.2f} kN**"
          f"（T = {T_FLAT:.2f} s）；")
    print(f"  ② **成对反向点火**是产生纯力偶的唯一办法 ⇒ 10 个喷口的必要性；")
    print(f"  ③ ★ **滚转比俯仰省 {J_PITCH/J_ROLL:.1f} 倍角动量** ——")
    print(f"     若误把倒挂段按俯仰算，所需推力会高估 {J_PITCH/J_ROLL:.1f} 倍；")
    print(f"  ④ **半圈比整圈难**：半圈要求姿态**唯一且精确**，整圈有对称余量；")
    print(f"  ⑤ **真正的工程难点是「停准」**（bang-bang 的切换时刻），"
          f"不是「转得动」。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
