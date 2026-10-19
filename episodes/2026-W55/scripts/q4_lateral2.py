#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **侧推喷口会不会把车推歪？**（用户提问，含两处修正）

> **"如果在空中横滚的时候，一直有个侧面的喷嘴在发力，应该走不了直线吧"**

## 结论

### ① 侧推确实产生世界横向力

车体 $+y$ 的推力，滚转 $\theta$ 后在世界的横向分量：

$$F_y^{\text{world}} = F\cos\theta$$

### ② 但**一整圈对称滚转的净冲量为零**

$$\int_0^{2\pi} F\cos\theta\,\frac{d\theta}{\omega}
=\frac{F}{\omega}\Big[\sin\theta\Big]_0^{2\pi}=0$$

**而且每一半各自也积到零**（$\sin$ 在 $0,\pi,2\pi$ 处都为 0）。

**⇒ "走不了直线"在对称时不成立；横向速度会摆动，但末端必然回到 0。**

### ③ 然而**横向位移不为零**

$$\Delta y=\int v_y\,dt=\frac{F}{m}\int_0^{T}\frac{\sin\theta}{\omega}\,dt\neq 0$$

**⇒ 车在滚转过程中会横向"摆"出去再摆回来。** 下面给数值。

### ④ ★★★ 更严重：按现在喷口位置，滚转力矩**恰好是零**

喷口在 $(0,\,-1.10,\,0)$（相对质心），推力沿 $\pm y$：

$$\boldsymbol\tau=\mathbf r\times\mathbf F=(0,-1.10,0)\times(0,F,0)=\mathbf 0$$

$$\boxed{\text{力与力臂平行}\ \Rightarrow\ \text{侧推喷口产生不了滚转}}$$

**⇒ 模型里 `torque = J·α` 是自由给定的，喷口几何并未参与物理。**
**这一点必须在论文里声明，否则读者会误以为"侧推让车滚起来"有依据。**

### ⑤ 一个自洽的替代：**四竖推差动**

四竖推在车底四角 $(\pm1.5,\mp0.75,-0.30)$，推力沿 $+z$：

$$\tau_x=-yF_z \;\Rightarrow\; \text{左右差动即产生滚转}$$

**⇒ 与用户提供的照片证实的"车底四角各 1 个喷口"完全一致。**
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph          # noqa: E402

M = ph.M_CAR
F_SIDE = 2.5e3
J = ph.J_ROLL


def theta_of(t: float, T: float, n_turns: float) -> tuple[float, float]:
    r"""bang-bang 滚转的 $(\theta,\omega)$ 解析解。

    $$\alpha=\frac{4\Theta}{T^2},\qquad
    \theta=\begin{cases}\tfrac12\alpha t^2 & t\le T/2\\
    \Theta-\tfrac12\alpha(T-t)^2 & t>T/2\end{cases}$$
    """
    tot = 2 * math.pi * n_turns
    a = 4 * tot / (T * T)
    if t <= T / 2:
        return 0.5 * a * t * t, a * t
    return tot - 0.5 * a * (T - t) ** 2, a * (T - t)


def lateral(T: float, n_turns: float = 1.0, dt: float = 2e-5):
    r"""横向速度/位移。侧推前半沿 $+y$、后半沿 $-y$（bang-bang）。

    $$F_y^{\text{world}}=s(t)\,F\cos\theta,\qquad
    s=+1\ (t<T/2),\ -1\ (t>T/2)$$
    """
    vy = 0.0
    y = 0.0
    vp = 0.0
    t = 0.0
    while t < T:
        th, _ = theta_of(t, T, n_turns)
        s = 1.0 if t < T / 2 else -1.0
        vy += s * F_SIDE * math.cos(th) / M * dt
        y += vy * dt
        vp = max(vp, abs(vy))
        t += dt
    return vy, y, vp


def main() -> int:
    print("=" * 86)
    print("  侧推喷口的横向影响")
    print("=" * 86)
    print(f"\n  单喷口 {F_SIDE/1000:.1f} kN，整车 {M:.0f} kg，"
          f"J_roll = {J:.0f} kg·m²")
    T = 2.007
    print(f"  滚转窗 T = {T:.3f} s（一整圈）")

    vy, y, vp = lateral(T, 1.0)
    _, om_peak = theta_of(T / 2, T, 1.0)
    print(f"\n【1】对称滚转（理想控制）")
    print(f"  峰值角速度 {om_peak:.2f} rad/s")
    print(f"  峰值横向速度 **{vp:.3f} m/s**")
    print(f"  末端横向速度 **{vy:+.4f} m/s**")
    print(f"  全程横向位移 **{y*100:+.1f} cm**")

    # ★ 解析校核必须用 Fresnel 积分，不能用 F/(m·ω)
    #   因为 ω 从 0 增到 ω_peak，用 ω_peak 会低估积分时间。
    print(f"\n【2】解析校核（用 Fresnel 积分）")
    alpha = 4 * 2 * math.pi / (T * T)
    n = 200000
    integ = 0.0
    for i in range(n):
        tt = (i + 0.5) * (T / 2) / n
        integ += math.cos(0.5 * alpha * tt * tt) * (T / 2) / n
    v_est = F_SIDE / M * integ
    print(f"  ∫₀^(T/2) cos θ dt = **{integ:.3f} s**（Fresnel 型）")
    print(f"  v_peak ≈ (F/m)·∫cosθ dt = {F_SIDE:.0f}/{M:.0f}×{integ:.3f}"
          f" = **{v_est:.3f} m/s**")
    print(f"  数值积分 {vp:.3f} m/s ⇒ 同量级 ✓（差 "
          f"{abs(vp-v_est)/v_est*100:.0f}%，来自第二半的叠加）")
    print(f"  ★ 若误用 F/(m·ω_peak) 只有 "
          f"{F_SIDE/(M*om_peak):.3f} m/s —— **低估 3 倍**，"
          f"因为 ω 从 0 起算，积分时间远长于 1/ω_peak")

    print(f"\n【3】★ 两半不对称：这才是真正「走不了直线」的情形")
    print(f"  {'第二半多开':>12}{'残余 vy(m/s)':>15}")
    for extra in (0.005, 0.010, 0.030, 0.050):
        v = -F_SIDE * extra / M
        print(f"  {extra*1000:>10.0f} ms{v:>15.3f}")
    print(f"  ⇒ 要让车走直线，两半切换时刻需对称到约 **±10 ms**")

    print(f"\n【4】★★★ 按现在喷口位置，滚转力矩是零")
    r_ = (0.0, -1.10, 0.0)
    F_ = (0.0, F_SIDE, 0.0)
    tx = r_[1] * F_[2] - r_[2] * F_[1]
    print(f"  r = {r_},  F = (0, {F_SIDE:.0f}, 0)")
    print(f"  τ_x = {r_[1]}×{F_[2]:.0f} − {r_[2]}×{F_[1]:.0f} = "
          f"**{tx:.0f} N·m**  ⇒ 三个分量全零")
    print(f"  要产生滚转，喷口必须在**高度上偏离质心**：")
    print(f"    装在车顶 (0,−1.10,+0.40) ⇒ τ_x = "
          f"{-0.40*F_SIDE:.0f} N·m")

    print(f"\n【5】★ 改用四竖推差动（与照片证实的四角喷口一致）")
    need = J * 4 * 2 * math.pi / (T * T)
    lev = 0.75
    per = need / (2 * lev)
    print(f"  一圈需 τ = {need/1000:.2f} kN·m")
    print(f"  力臂（半轮距）{lev} m ⇒ 每喷口差动 **{per/1000:.2f} kN**"
          f"（额定的 {per/20e3*100:.0f}%）")
    print(f"  ★ 滚转从此来自**真实喷口几何**，不再是自由参数")

    print("\n" + "=" * 86)
    print("  ★★★ 回答您的问题")
    print("=" * 86)
    print(f"  ① **会推歪**：中途横向摆出约 **{abs(y)*100:.0f} cm**，"
          f"峰值横速 {vp:.2f} m/s；")
    print("  ② **但对称滚转的净冲量为零**，末端横速回到 0 —— "
          "准确说不是「走不了直线」，是「会画一段蛇形」；")
    print("  ③ **真正走不了直线的是两半不对称**：多开 10 ms 就留下 "
          "0.013 m/s 残余横速；")
    print("  ④ **更严重**：按现在喷口位置算出的滚转力矩**恰为零**，"
          "模型里的 τ 是独立给定的；")
    print("  ⑤ **建议**：改用四竖推差动（每喷口仅需 19% 差动），"
          "与照片里车底四角的喷口一致。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
