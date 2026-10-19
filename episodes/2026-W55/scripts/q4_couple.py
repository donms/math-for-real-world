#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **差动升力 vs 力偶**：滚转的两种方案与文献中的成熟做法。

## 用户的判断

> **"左右差动应该就能滚，但是应该也避免不了横向位移，
> 额外的喷口应该就是用来调姿"**

**前半句对，后半句也对 —— 而且代价比"位移"更严重。**

## 一、差动升力的横向代价（本文量化）

四竖推在车底四角，$y=\pm0.75$，推力沿**车体** $+z$。

**滚转力矩**来自横向力臂：

$$\tau_x=-yF_z\;\Rightarrow\;
\tau_x=0.75\,(F_L-F_R)$$

**但要维持高度**必须 $F_L+F_R\approx mg$。
于是 $F_L-F_R$ 一出现，两侧推力就一大一小。

**关键**：合推力仍沿**车体** $+z$，而车体 $+z$ 在世界的方向是

$$\hat z_{\text{body}}^{\text{world}}=(0,\,-\sin\theta,\,\cos\theta)$$

$$\Rightarrow\quad F_y^{\text{world}}=-(F_L+F_R)\sin\theta\approx -mg\sin\theta$$

**⇒ 峰值横向力 ≈ 整车重量的 $\sin\theta$ 倍**，滚到 $90°$ 时是 **19.6 kN**。

$$\Delta v_y = g\int_0^{T/2}\sin\theta\,dt \approx 9.81\times0.49
\approx \mathbf{4.8\ m/s}$$

**⇒ 这不是"位移"，这是"整台车被甩出去"。**

## 二、文献中的判据：**力偶（couple）**

航天器推力器配置的标准写法是**配置矩阵**：

$$\mathbf w_i=\begin{pmatrix}\mathbf u_i\\ \mathbf r_i\times\mathbf u_i\end{pmatrix}
\in\mathbb R^6,\qquad
\mathbf B=[\mathbf w_1\ \cdots\ \mathbf w_n],\qquad
\mathbf B\mathbf f=\mathbf w_{\text{req}}$$

**一条基本事实**（见 TTU 学位论文）：
**单个推力器只要推力线不过质心，就必然"力与力矩同时产生"**。

**要纯力矩不要净力，必须成"力偶"**：

$$\mathbf F_1=-\mathbf F_2,\qquad
\text{两力作用线}\ \textbf{平行但不重合},\ \text{间距}\ d$$

$$\Rightarrow\quad \sum\mathbf F=\mathbf 0,\qquad
|\boldsymbol\tau|=F\,d$$

**★ 若两力作用线重合（间距为 0），力矩也是 0** ——
这正是我上一版"侧推喷口"犯的错：力与力臂平行。

## 三、对四竖推（全部朝下）意味着什么

**四个喷口都朝下 ⇒ 无法组成力偶**（力偶需要两力**反向**）。
只能做"差动"，而差动必然净力不为零 ⇒ 见第一节的 4.8 m/s。

$$\boxed{\text{全部朝下的喷口，做不出"纯滚转"}}$$

**⇒ 用户的判断成立：额外的喷口必须存在，且必须是"成对的、反向的"。**

## 四、10 个喷口能否做到 6 自由度全解耦

| 自由度 | 最少推力器数（纯力偶）|
|---|---|
| 3 轴平动 | 每个方向 1 对 ⇒ 6 |
| 3 轴转动 | 每个方向 1 对 ⇒ 6 |
| **合计（全解耦）** | **12** |

**⇒ 10 个无法全解耦，至少要有一个自由度接受耦合**
（用"分时"或"脉冲调制"补偿）。

## 五、本文推荐的 10 喷口配置（全部成力偶）

| # | 名称 | 位置 | 方向 | 作用 |
|---|---|---|---|---|
| 1-4 | `LIFT_FL/FR/RL/RR` | 车底四角 $(\pm1.5,\mp0.75,-0.30)$ | $+z$ | 起飞 / 缓冲（**差动亦可用于滚转，但有耦合**）|
| 5-6 | `ROLL_A/B` | 车顶与车底同侧 $(0,-1.10,+0.45)$ 与 $(0,-1.10,-0.35)$ | $\pm y$ | **滚转力偶**（间距 0.8 m）|
| 7-8 | `YAW_A/B` | 车头车尾 $(+1.6,0,\mp0.30)$ | $\pm y$ | **偏航力偶**（间距 3.2 m）|
| 9-10 | `PITCH_A/B` | 车头车顶 / 车尾车底 | 见注 | **俯仰力偶** |

**注**：俯仰力偶需要一力向上、一力向下的 $\pm z$ 对，
与四竖推"全朝下"冲突 —— 这是 10 个喷口下的真实取舍。

## 六、结论
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph          # noqa: E402

M = ph.M_CAR
G = ph.G
J = ph.J_ROLL
T = 2.007


def theta_of(t: float, T: float, turns: float = 1.0):
    tot = 2 * math.pi * turns
    a = 4 * tot / (T * T)
    if t <= T / 2:
        return 0.5 * a * t * t, a * t
    return tot - 0.5 * a * (T - t) ** 2, a * (T - t)


def integrate(fn, T: float, n: int = 400000):
    s = 0.0
    dt = T / n
    for i in range(n):
        s += fn((i + 0.5) * dt) * dt
    return s


def main() -> int:
    print("=" * 88)
    print("  滚转方案：差动升力 vs 力偶")
    print("=" * 88)
    W = M * G
    print(f"\n  整车 {M:.0f} kg，重量 {W/1000:.1f} kN，"
          f"J_roll = {J:.0f} kg·m²，滚转窗 {T:.2f} s")

    # ---- 1) 差动升力的横向代价 ----
    print(f"\n【1】差动升力：横向代价")
    tau_need = J * 4 * 2 * math.pi / (T * T)
    dF = tau_need / 0.75
    print(f"  滚一圈需 τ = {tau_need/1000:.2f} kN·m")
    print(f"  力臂 0.75 m ⇒ 需左右推力差 {dF/1000:.1f} kN")
    print(f"  维持高度需总和 {W/1000:.1f} kN")
    print(f"  ⇒ 左 {((W+dF)/2)/1000:.1f} kN、右 "
          f"{((W-dF)/2)/1000:.1f} kN")
    I_sin = integrate(lambda t: math.sin(theta_of(t, T)[0]), T / 2)
    print(f"\n  合推力沿车体 +z ⇒ 世界横向 = −(总和)·sinθ")
    print(f"  ∫₀^(T/2) sinθ dt = {I_sin:.3f} s")
    print(f"  ⇒ 峰值横向力 **{W/1000:.1f} kN × sinθ**"
          f"（滚到 90° 时 = {W/1000:.1f} kN，等于整车重量）")
    print(f"  ⇒ 横向速度增量 **Δv ≈ g·∫sinθ dt = "
          f"{G*I_sin:.2f} m/s**")
    print(f"  ★ 这不是小扰动，是「整台车被甩出去」")

    # ---- 2) 侧推力偶（我上一版的做法，力矩为零）----
    print(f"\n【2】侧推「力偶」：上一版为什么无效")
    print(f"  喷口 (0,−1.10,0)，推力沿 ±y ⇒ 力与力臂平行")
    print(f"  τ = r × F = 0  ⇒ **产生不了滚转**")
    print(f"  要让 τ ≠ 0，两力必须**平行但不重合**（间距 d>0）")

    # ---- 3) 正确的力偶 ----
    print(f"\n【3】滚转力偶：**力臂该取哪个方向**")
    print(f"  滚转绕 x 轴 ⇒ 力偶有两种取法，力臂长度完全不同：")
    print(f"  {'力偶构成':<32}{'力臂 d':>8}{'需单喷 F':>10}{'判定':>6}")
    for lab, d in (("两力沿 ±z、沿 y 分开（轮距）", 1.50),
                   ("两力沿 ±y、沿 z 分开（车高）", 0.80)):
        F = tau_need / d
        print(f"  {lab:<30}{d:>8.2f}{F/1000:>10.2f}"
              f"{'  ✓' if F <= 20e3 else '  ✗':>6}")
    print(f"  ★ **车高只有 1.2 m**，沿 z 分开最多 0.8 m ⇒ 需 7.1 kN/喷；")
    print(f"    **轮距 1.5 m** ⇒ 只需 **{tau_need/1.5/1000:.2f} kN/喷**，"
          f"省一半以上")
    print(f"  ⇒ 力臂应取**车最宽的方向**：左右分开 1.5 m")

    print(f"\n  ★★ 但四竖推**全部朝下** ⇒ 组不出「一上一下」的反向对")
    print(f"  ⇒ 必须**额外装 2 个朝上的喷口**（左右各一）")
    print(f"     · 左朝上 + 右朝下 ⇒ **纯滚转**（净力恰为零）")
    print(f"     · 左朝上 + 尾朝下 ⇒ 可组合出**纯俯仰**（同一对复用）")
    print(f"  ⇒ 这就是您说的「额外的喷口用来调姿」—— **且只需 2 个**")

    # ---- 4) 喷口数量 ----
    print(f"\n【4】10 个喷口够不够")
    print(f"  全解耦（每轴一力偶）需 **12** 个：3 平动对 + 3 转动对")
    print(f"  ⇒ 10 个至少要有一个自由度接受耦合")

    print("\n" + "=" * 88)
    print("  ★★★ 结论")
    print("=" * 88)
    print(f"  ① **差动升力不能用来滚**：横向速度会到 "
          f"{G*I_sin:.1f} m/s（整车重量侧向甩）；")
    print(f"  ② **纯滚转必须用力偶**：两力反向、平行、间距 d，"
          f"τ = F·d，净力为零；")
    print(f"  ③ **四竖推全朝下 ⇒ 做不出力偶** ⇒ 必须有额外喷口（您的判断对）；")
    print(f"  ④ **10 个喷口无法全解耦**（需 12）；"
          f"建议：4 竖推 + 滚转偶 2 + 偏航偶 2 + 主推进 1 + 备用 1；")
    print(f"  ⑤ 滚转偶只需 **{tau_need / 1.5 / 1000:.2f} kN × 2**"
          f"（力臂取轮距 1.5 m）；差动方案会让车横甩 "
          f"{G * I_sin:.1f} m/s，力偶则完全干净；")
    print(f"  ⑥ 建议布局：4 竖推 + **2 个朝上**（滚转/俯仰力偶）"
          f" + 2 偏航 + 1 主推进 + 1 备用 = 10。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
