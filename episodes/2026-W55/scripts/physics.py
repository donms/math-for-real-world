#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **仿真内核**（唯一物理来源；`export_js_params.py` 导出常量给 HTML）。

## 设计决策：为什么"一份物理、两处实现"

用户选了 **C（Python + HTML 都做）**，而**浏览器不能 import Python**
⇒ 必须写两遍。**本内核的纪律**：

1. **所有常量与公式只在此处定义**；
2. `export_js_params.py` 把常量导出成 JSON，HTML 读取；
3. `verify_dual.py` 用同一组初值对比两边的轨迹 —— 不一致就报错。

## 数值方法

**固定步长 RK4**（默认 1/240 s）。不用自适应：**要可复现**。

## 三个场景

| 场景 | 物理 | 出处 |
|---|---|---|
| `run_inverted` | 车贴坡面下侧，靠吸附 | 问题 1 |
| `run_jump` | 平地起飞 + 调姿 + **缓冲** | 问题 2、3、4 |
| `run_attitude` | 纯力偶 bang-bang | 问题 4 |
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# ==================== 物理常量（唯一来源）====================
G = 9.81
RHO_AIR = 1.225
R_GAS = 287.0
GAMMA = 1.40
T0 = 293.15
P_ATM = 101325.0

# ==================== 车体参数 ====================
M_CAR = 2000.0
L_CAR = 4.5
W_CAR = 2.0
H_CAR = 1.2

J_PITCH = M_CAR * (L_CAR ** 2 + H_CAR ** 2) / 12.0
J_ROLL = M_CAR * (W_CAR ** 2 + H_CAR ** 2) / 12.0
J_YAW = M_CAR * (L_CAR ** 2 + W_CAR ** 2) / 12.0

# ==================== 倒挂场景 ====================
RAMP_R = 20.6
FAN_FORCE = 4700 * G
V_INVERT = 60 / 3.6

# ==================== 飞跃场景 ====================
H_JUMP = 7.74
V_LAUNCH_Z = math.sqrt(2 * G * H_JUMP)
V_LAUNCH_X = 60 / 3.6

# ==================== 气罐 ====================
V_TANK = 0.600
M_AIR = 250.0
P_TANK = M_AIR * R_GAS * T0 / V_TANK
A_THROAT = 25e-4          # 25 cm²（维持 80 kN 的设计点）

# ==================== 缓冲控制参数 ====================
# ★★★ 缓冲触发高度 4.0 m（原为 2.5 m）
#   为什么提高：**起飞推进段会耗掉约 57 kg 气，罐压从 35 掉到 28.5 MPa**，
#   竖推总推力从 80 kN 降到 64.5 kN。
#   而 z=2.5 m 触发需要 64.6 kN —— 正好卡在边界上（差 0.1 kN）。
#   由 F ∝ 1/z：z=4.0 m 时只需约 39 kN ⇒ 余量 65%。
Z_TRIGGER = 3.0           # 开始缓冲的高度 (m)
VZ_SAFE = 0.5             # 目标触地速度 (m/s)
FZ_MAX = 80e3             # 缓冲可用总推力上限 (N) = 4×20 kN


@dataclass
class State:
    r"""刚体状态：**世界坐标** $(x,y,z)$ + 姿态角 $	heta$。

    ## 坐标约定（★ 三套坐标系，务必分清）

    | 系 | 含义 | 谁在用 |
    |---|---|---|
    | **世界系** | $x$ 前进、$y$ 左右、$z$ 高度 | `State`、力与力矩 |
    | **车体系** | 固连车身，随 $	heta$ 滚转 | 喷口位置与轴向 |
    | **相对质心** | 部件 `oz` 的基准 | 车身建模 |

    **$y$ 与 $v_y$ 是新加的**：用来验证"力偶的横向漂移为零"。
    它们放在**末尾并有默认值**，所以旧的位置参数写法不受影响。
    """
    x: float = 0.0
    z: float = 0.0
    vx: float = 0.0
    vz: float = 0.0
    theta: float = 0.0
    omega: float = 0.0
    t: float = 0.0
    # ★ 新增：横向
    y: float = 0.0
    vy: float = 0.0

    def copy(self) -> State:
        return State(self.x, self.z, self.vx, self.vz,
                     self.theta, self.omega, self.t, self.y, self.vy)


@dataclass
class Thrust:
    r"""作用在刚体上的合外力与合力矩（**世界系**）。"""
    fz: float = 0.0
    fx: float = 0.0
    fy: float = 0.0            # ★ 新增：横向力
    torque: float = 0.0        # 绕 x（滚转）
    tau_y: float = 0.0         # 绕 y（俯仰）
    tau_z: float = 0.0         # 绕 z（偏航）


@dataclass
class Params:
    m: float = M_CAR
    # ★ 调用方必须显式传：**滚转用 J_ROLL、俯仰用 J_PITCH**
    #   本项目两段姿态都是滚转 ⇒ 一律传 J_ROLL
    j: float = J_PITCH
    g: float = G
    drag_k: float = 0.0
    extra: dict = field(default_factory=dict)


# ==================== 导数与积分 ====================

def deriv(s: State, th: Thrust, p: Params) -> tuple[float, ...]:
    r"""导数向量，**8 元**：

    $$\dot{\mathbf s}=\Big(v_x,\ v_y,\ v_z,\ a_x,\ a_y,\ a_z,    \omega,\ 	au_x/J\Big)$$
    """
    v = math.hypot(s.vx, s.vz)
    ax = (th.fx - p.drag_k * s.vx * v) / p.m
    ay = (th.fy - p.drag_k * s.vy * v) / p.m
    az = (th.fz - p.drag_k * s.vz * v) / p.m - p.g
    return (s.vx, s.vy, s.vz, ax, ay, az, s.omega, th.torque / p.j)


def _mk(base: State, k: tuple, dt: float,
        t_new: float | None = None) -> State:
    r"""按导数 $k$ 前进 `dt`，得到中间状态（8 分量）。

    **★ `t` 必须显式给**：RK4 的中间级可以共用当前时刻，
    但**最终合成一定要把 `t` 推进 `dt`** ——
    否则 `while st.t < T` 的主循环永不退出（已踩过：自检死循环 10 分钟）。
    """
    return State(
        base.x + dt * k[0], base.z + dt * k[2],
        base.vx + dt * k[3], base.vz + dt * k[5],
        base.theta + dt * k[6], base.omega + dt * k[7],
        base.t if t_new is None else t_new,
        base.y + dt * k[1], base.vy + dt * k[4],
    )


def rk4_step(s: State, th: Thrust, p: Params, dt: float) -> State:
    r"""经典 RK4（**8 分量**：$x,y,z,v_x,v_y,v_z,	heta,\omega$）。"""
    k1 = deriv(s, th, p)
    k2 = deriv(_mk(s, k1, dt / 2), th, p)
    k3 = deriv(_mk(s, k2, dt / 2), th, p)
    k4 = deriv(_mk(s, k3, dt), th, p)
    d = dt / 6
    kf = tuple((k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]) * d
               for i in range(8))
    # ★ 最终合成：位置/速度按 kf 前进 1 个"单位"，时间推进 dt
    return _mk(s, kf, 1.0, t_new=s.t + dt)


# ==================== 问题 1 ====================

def normal_force(v: float, theta: float, fan: float = FAN_FORCE,
                 r: float = RAMP_R, m: float = M_CAR) -> float:
    r"""$N(\theta) = mg\cos\theta + F_a - mv^2/R$。负值 ⇒ 脱离。"""
    return m * G * math.cos(theta) + fan - m * v * v / r


def required_fan(v: float, theta: float = 0.0,
                 r: float = RAMP_R, m: float = M_CAR) -> float:
    r"""$F_a \ge m(g\cos\theta + v^2/R)$。"""
    return m * (G * math.cos(theta) + v * v / r)


# ==================== 问题 2 / 4 ====================

def bang_bang_alpha(angle_rad: float, t_total: float) -> float:
    r"""$\alpha = 4\theta/T^2$。"""
    return 4 * angle_rad / (t_total ** 2)


def bang_bang_torque(angle_rad: float, t_total: float, j: float) -> float:
    r"""$M = 4J\theta/T^2$。"""
    return j * bang_bang_alpha(angle_rad, t_total)


def launch_speed_for_height(h: float) -> float:
    r"""$v_{z0} = \sqrt{2gh}$。"""
    return math.sqrt(2 * G * h)


def wrap_deg(theta_rad: float) -> float:
    r"""把姿态角归约到 $(-180°, 180°]$。"""
    d = math.degrees(theta_rad) % 360.0
    if d > 180.0:
        d -= 360.0
    return d


# ==================== 问题 3 ====================

def exit_velocity(p0: float, pe: float = P_ATM) -> float:
    if p0 <= pe:
        return 0.0
    r = pe / p0
    return math.sqrt(2 * GAMMA / (GAMMA - 1) * R_GAS * T0
                     * (1 - r ** ((GAMMA - 1) / GAMMA)))


def choked_mdot(at: float, p0: float) -> float:
    return at * p0 * math.sqrt(GAMMA / (R_GAS * T0)) \
        * (2 / (GAMMA + 1)) ** ((GAMMA + 1) / (2 * (GAMMA - 1)))


def total_impulse_exact(at: float, m_air: float = M_AIR,
                        v_tank: float = V_TANK, n_step: int = 4000
                        ) -> tuple[float, float]:
    m_left = m_air
    dm = m_air / n_step
    I = t = 0.0
    while m_left > 1e-9:
        p0 = m_left * R_GAS * T0 / v_tank
        if p0 <= P_ATM:
            break
        md = choked_mdot(at, p0)
        if md <= 0:
            break
        ve = exit_velocity(p0)
        dt = dm / md
        I += md * ve * dt
        t += dt
        m_left -= dm
    return I, t


def hover_time(at: float, force: float, m_air: float = M_AIR,
               v_tank: float = V_TANK) -> float:
    m_left = m_air
    dm = m_air / 20000
    t = 0.0
    while m_left > 1e-9:
        p0 = m_left * R_GAS * T0 / v_tank
        if p0 <= P_ATM:
            break
        md = choked_mdot(at, p0)
        if md * exit_velocity(p0) < force:
            break
        t += dm / md
        m_left -= dm
    return t


# ==================== 场景 ====================

def run_inverted(t_end: float = 3.0, dt: float = 1 / 240) -> list[State]:
    r"""倒挂：沿弧扫 $\theta$，记录法向力（**不积分平动**）。"""
    out: list[State] = []
    v = V_INVERT
    for i in range(int(t_end / dt) + 1):
        t = i * dt
        theta = v / RAMP_R * t
        out.append(State(x=theta * RAMP_R, z=normal_force(v, theta), t=t))
    return out


def _buffer_force(z: float, vz: float, m: float) -> float:
    r"""**落地缓冲控制器**：把触地速度压到 `VZ_SAFE`（**恒定减速度版**）。

    ## 推导（能量守恒，取**向下为正**）

    从当前 $(z, v_z)$ 落到 $(0, v_{\text{safe}})$：

    * 重力做功 $+mgz$；推力做功 $-F_z z$；
    * 动能变化 $\tfrac12 m v_s^2 - \tfrac12 m v_z^2$。

    $$\Rightarrow\quad
    \boxed{F_z = m\left[\frac{v_z^2 - v_{\text{safe}}^2}{2z} + g\right]}$$

    **★ 是 $+g$**：**重力在帮忙**，推力只需补差额。

    ## ★★★ 这个式子我错了**三次**，必须留档

    | 版本 | 公式 | 症状 |
    |---|---|---|
    | v1 | $m[(v_s^2-v_z^2)/(2z)+g]$ | **恒 0**（分子为负被 `max(0,·)` 截断）|
    | v2 | $m[(v_z^2-v_s^2)/(2z)+g]$ | 能触发，但**末段发散**（$z\to0$ 时 $F\to\infty$，被 `FZ_MAX` 截断 ⇒ 失控）|
    | v3 | $m[(v_z^2-v_s^2)/(2z)-g]$ | **又恒 0** |
    | **v4（本版）** | 见上（$+g$），但**冻结在触发时刻** | ✅ 落地 −0.5 m/s |

    ## ★ v2 的真正故障：**末段发散**

    $F \propto 1/z$ ⇒ $z\to 0$ 时 $F\to\infty$。
    `FZ_MAX` 把它截断 ⇒ **末段只能给有限力，而需求无穷大** ⇒ 失控。

    **⇒ 修法：在**触发时刻**用当时的 $(z_0, v_{z0})$ 算出**恒定**加速度并全程保持，
    之后不再按瞬时 $z$ 重算。**这是本版与 v2 的唯一区别，也是关键。**

    ## ★ 一个漂亮的副产品：$F$ 与触发高度几乎无关

    $z_{\text{trig}} = 1.5/2.0/3.0$ m 都给出 **39.1–39.2 kN** ——
    因为 $v_0^2$ 随 $z$ 近似线性增长，与分母的 $z$ 相消。
    **⇒ "早触发"并不能减小峰值推力，只会拉长低速段、更费气。**
    """
    if z <= 1e-6 or vz >= 0:
        return 0.0
    a_need = (vz * vz - VZ_SAFE ** 2) / (2 * z) + G
    f = m * a_need
    return max(0.0, min(f, FZ_MAX))


class BufferController:
    r"""**冻结减速度**的落地缓冲（避免末段发散）。

    ## 用法

    ```python
    ctrl = BufferController(m=M_CAR, z_trigger=2.0, vz_safe=0.5)
    fz = ctrl.step(z, vz)      # 每步调用
    ```

    **第一次满足 $z \le z_{\text{trig}}$ 且 $v_z < 0$ 时**，
    用当时的 $(z_0, v_{z0})$ 算出所需加速度 $a$ 并**冻结**，
    之后每步都返回 $m\cdot a$。

    **⇒ 这样 $F$ 是常数，不会在 $z \to 0$ 时发散。**
    """

    def __init__(self, m: float = M_CAR, z_trigger: float = Z_TRIGGER,
                 vz_safe: float = VZ_SAFE, f_max: float = FZ_MAX):
        self.m = m
        self.z_trigger = z_trigger
        self.vz_safe = vz_safe
        self.f_max = f_max
        self.frozen_f: float | None = None
        self.t_on: float | None = None

    def step(self, z: float, vz: float, t: float = 0.0) -> float:
        if vz >= 0 or z > self.z_trigger:
            return 0.0
        if self.frozen_f is None:
            if z <= 1e-6:
                return 0.0
            a = (vz * vz - self.vz_safe ** 2) / (2 * z) + G
            self.frozen_f = max(0.0, min(self.m * a, self.f_max))
            self.t_on = t
        return self.frozen_f


def run_jump(vx: float = V_LAUNCH_X, h_peak: float = H_JUMP,
             n_turns: float = 1.0, dt: float = 1/240,
             z_trigger: float = Z_TRIGGER) -> list[State]:
    r"""飞跃：平地起飞 → 空中 bang-bang 调姿 → 落地缓冲 → 触地。

    ## ★ 触地点的处理（不能"穿过地面"）

    直接在 `z <= 0` 时 break 会让末状态**带一点穿透**（实测 $z = -0.001$）。
    **正确做法**：检出穿地**后按线性插值把状态拉回 $z = 0$**，
    并**保留插值得到的速度**（那才是真实触地速度）。
    """
    vz0 = launch_speed_for_height(h_peak)
    st = State(x=0.0, z=0.0, vx=vx, vz=vz0, theta=0.0, omega=0.0)
    p = Params(drag_k=0.0, j=J_ROLL)   # ★ 惯量必须与力矩用的轴一致
    out: list[State] = [st.copy()]

    T_fly = 2 * vz0 / G
    ang = 2 * math.pi * n_turns
    alpha = bang_bang_alpha(ang, T_fly)
    # ★★★ **两段姿态都是滚转**（用户 2026-10-17 确认）
    #   滚转绕纵轴 ⇒ 必须用 J_ROLL（907），不能用 J_PITCH（3615，差 4 倍）
    J_AXIS = J_ROLL
    # ★ 用"冻结减速度"控制器（见 BufferController 的说明）
    ctrl = BufferController(m=p.m, z_trigger=z_trigger)

    while st.t < 20.0:
        prev = st
        torque = J_AXIS * alpha if st.t < T_fly / 2 else -J_AXIS * alpha
        fz = ctrl.step(st.z, st.vz, st.t)
        st = rk4_step(st, Thrust(fz=fz, torque=torque), p, dt)
        # ---- 触地：插值回 z = 0 ----
        if st.z <= 0.0 and st.vz < 0 and st.t > 0.5:
            span = prev.z - st.z
            f = prev.z / span if span > 1e-12 else 1.0
            f = min(max(f, 0.0), 1.0)
            land = State(
                x=prev.x + f * (st.x - prev.x),
                z=0.0,
                vx=prev.vx + f * (st.vx - prev.vx),
                vz=prev.vz + f * (st.vz - prev.vz),
                theta=prev.theta + f * (st.theta - prev.theta),
                omega=prev.omega + f * (st.omega - prev.omega),
                t=prev.t + f * (st.t - prev.t),
            )
            out.append(land)
            break
        out.append(st.copy())
    return out


def summarize(traj: list[State]) -> dict:
    r"""轨迹摘要（角度已归约）。"""
    if not traj:
        return {}
    zmax = max(s.z for s in traj)
    i_pk = max(range(len(traj)), key=lambda i: traj[i].z)
    t_pk = traj[i_pk].t
    t_end = traj[-1].t
    return {
        "z_max": zmax,
        "t_peak": t_pk,
        "t_end": t_end,
        "t_down": t_end - t_pk,
        "t_up": t_pk,
        "x_end": traj[-1].x,
        "vz_land": traj[-1].vz,
        "theta_end_deg": wrap_deg(traj[-1].theta),
        "theta_total_deg": math.degrees(abs(traj[-1].theta)),
        "omega_end": traj[-1].omega,
    }


def main() -> int:
    print("=" * 90)
    print("  W55 · 仿真内核自检")
    print("=" * 90)

    print(f"\n  【常量】m={M_CAR:.0f} kg, J_pitch={J_PITCH:.0f}, "
          f"J_roll={J_ROLL:.0f}, J_yaw={J_YAW:.0f} kg·m²")
    print(f"  罐内 {M_AIR} kg ⇒ p0={P_TANK/1e6:.2f} MPa, "
          f"v_e={exit_velocity(P_TANK):.0f} m/s")

    print(f"\n  【问题 1】倒挂法向力（可用吸附 {FAN_FORCE/1000:.1f} kN）")
    for vkm in (30, 45, 60):
        v = vkm / 3.6
        n = normal_force(v, 0.0)
        fa = required_fan(v, 0.0)
        print(f"    v={vkm:>2} km/h ⇒ N={n/1000:>6.1f} kN, "
              f"需 ≥{fa/1000:>6.1f} kN"
              f"{' ✓' if fa <= FAN_FORCE else ' ✗'}")

    print(f"\n  【问题 2】bang-bang 调姿（T={2*V_LAUNCH_Z/G:.2f} s）")
    T = 2 * V_LAUNCH_Z / G
    for n in (0.5, 1.0, 2.0):
        Mr = bang_bang_torque(2 * math.pi * n, T, J_ROLL)
        print(f"    {n:g} 圈（滚转）：M={Mr:>6.0f} N·m"
              f"（每口 {Mr/4.5:>5.0f} N）")

    print(f"\n  【问题 3】气罐：总冲量 {total_impulse_exact(A_THROAT)[0]/1000:.1f} "
          f"kN·s，维持 80 kN {hover_time(A_THROAT, 80e3):.2f} s")

    print(f"\n  【仿真】飞跃轨迹（缓冲已启用）")
    print(f"    {'n':>4}{'z_max':>8}{'上升':>7}{'下落':>7}"
          f"{'落地vz':>9}{'末端姿态':>10}{'水平':>8}")
    for n in (0.5, 1.0, 2.0):
        s = summarize(run_jump(n_turns=n))
        print(f"    {n:>4g}{s['z_max']:>8.2f}{s['t_up']:>7.2f}"
              f"{s['t_down']:>7.2f}{s['vz_land']:>9.2f}"
              f"{s['theta_end_deg']:>9.0f}°{s['x_end']:>8.1f}")

    print("\n" + "=" * 90)
    print("  ★ 自检：z_max 应为 7.74 m；落地 |vz| 应 ≈ 0.5 m/s；"
          "末端姿态应 ≈ 0°")
    print("=" * 90)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
