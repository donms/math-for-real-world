#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **实拍里的三种工作模式**与本文模型为什么不同。

> 用户观察（2026-10-17）：
> **"为什么侧面的喷嘴没有工作？我看实拍视频里有时候是四个竖向的一起工作，
> 有时候是同侧的两个工作，配合侧向的。"**

## 三种模式

| 模式 | 喷口 | 用途 | 净力 |
|---|---|---|---|
| **A** 四竖推 | `LIFT_FL/FR/RL/RR` | 起飞 / 落地 | 竖直 |
| **B** 同侧两竖推 | 左侧两喷 | **滚转** | 竖直 $2F$（偏心）|
| **C** 侧向 | 侧推喷口 | **抵消 B 的横向反应** | 横向 |

**⇒ 实拍是"B + C 配合"，本文模型用的是"力偶"（另一种做法）。**

## 关键差异

### B 方案（同侧两竖推）

$$\tau_x=-yF_z\times 2=0.55\times 2F=1.1F$$

**但净竖直力 $\sum F_z=2F\neq 0$**，且车滚转 $\theta$ 后合推力有横向分量：

$$F_y^{\text{world}}=-2F\sin\theta$$

### C 方案（侧推补偿）

侧推喷口沿 $\pm y$，世界横向分量：

$$F_y^{(C)}=F_s\cos\theta$$

**要抵消 B：**

$$F_s\cos\theta=2F\sin\theta
\;\Longrightarrow\;
F_s=2F\tan\theta$$

$$\boxed{\theta\to90°\ \text{时}\ F_s\to\infty}$$

**⇒ 单靠一个定值侧推，物理上无法在整圈内抵消。**

**⇒ 要么接受残余横漂，要么把侧推做成"随 $\theta$ 调制"。**
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
Y_LIFT = 0.55
Y_ATT = 0.85


def main() -> int:
    need = J * 4 * 2 * math.pi / (T * T)
    print("=" * 84)
    print("  三种滚转方案对比")
    print("=" * 84)
    print(f"\n  一圈需 τ = {need/1000:.2f} kN·m（T = {T:.2f} s）")

    print(f"\n【A】四竖推 —— 只做升降")
    print(f"  对称点火 ⇒ τ = 0，净力 = 4F（纯升降）")

    print(f"\n【B】同侧两竖推（实拍观察到的模式）")
    F_b = need / (2 * Y_LIFT)
    print(f"  τ = 2×{Y_LIFT}×F = {2*Y_LIFT:.2f}F")
    print(f"  ⇒ 每喷 F = {F_b/1000:.2f} kN")
    print(f"  ⇒ **净竖直力 = 2F = {2*F_b/1000:.2f} kN**"
          f"（占重量 {2*F_b/(M*G)*100:.0f}%）")
    print(f"  ★ 滚转时还会甩出横向力 2F·sinθ")

    print(f"\n【C】侧推补偿 B 的横向反应")
    print(f"  需要 F_s = 2F·tanθ")
    print(f"  {'θ(°)':>6}{'需侧推 F_s':>14}{'相对 2F':>10}")
    for deg in (0, 15, 30, 45, 60, 75, 89):
        th = math.radians(deg)
        fs = 2 * F_b * math.tan(th)
        print(f"  {deg:>6}{fs/1000:>12.1f} kN"
              f"{fs/(2*F_b):>10.2f}×")
    print(f"  ★ θ→90° 时发散 ⇒ **定值侧推不可能全程抵消**")

    print(f"\n【D】力偶（本文采用）")
    d = Y_ATT + Y_LIFT
    F_d = need / d
    print(f"  ATT(向下) + 对侧 LIFT(向上)，力臂 d = {d:.2f} m")
    print(f"  每喷 F = {F_d/1000:.2f} kN")
    print(f"  净竖直力 = F − F = **0**")
    print(f"  净横向力 = **0**（推力始终沿车体 ±z，成对相消）")
    print(f"  ★ 不需要任何侧推喷口")

    print("\n" + "=" * 84)
    print("  为什么本文的动画里侧面喷嘴不工作")
    print("=" * 84)
    print("  ① 本文用的是 **力偶方案**：ATT（向下）+ 对侧 LIFT（向上）")
    print("     ⇒ 净力恒为零，**不需要侧推补偿** ⇒ 侧推喷口没有被建模；")
    print("  ② 实拍观察到的 **同侧两竖推 + 侧推** 是**另一种方案**：")
    print("     差动升力产生滚转，侧推喷口去抵消横向反应；")
    print("  ③ 该方案在 θ→90° 时需要无穷大侧推推力 ⇒ **必然有残余横漂**；")
    print("  ④ 两种方案都能滚，区别在**代价放在哪**：")
    print(f"     力偶：多耗约 14.5 kg 气，几乎零横漂；")
    print(f"     差动+侧推：省气，但要接受横漂与竖直力耦合。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
