#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""2026-W58 核心模型：两支撑滑行力学 + 桨轮推进 + 垂荡-纵倾时域 + 参数化几何。

设计原则
--------
1. **只用 numpy/scipy**，不依赖 CFD / 外部数据，任何人 clone 后可复现。
2. **每一个可调参数都必须有物理含义、有区间、能被敏感性分析扫到**。
3. **能闭式解就闭式解**（两支撑平衡是 2×2 线性系统），时域才用 RK4。

坐标与符号
----------
x : 沿车头向前，原点在整机重心（含骑手）的投影处
z : 向上，z=0 为静水面
θ : 纵倾角，抬头为正（rad）
V : 航速（m/s）
h_i : 第 i 块板尾缘的浸深（m，>0 表示入水）
δ_i : 第 i 块板的安装角（相对车架基准线，抬头为正）

升力模型（核心假设，论文 3.1 详述）
-----------------------------------
滑行面单位浸深的升力 ≈ 1/2 ρ V² b k_L（"动升力弹簧"，刚度 ∝ V²）。
再叠加一个**喷溅根项** c_s·b·α（即使浸深为 0，有迎角就有湿长度），
于是 L_i = k_i·(h_i + c_s b_i α_i)，k_i = 1/2 ρ V² b_i k_L。
这条式子与 Savitsky 公式在同一工况下互校（见 `savitsky_lift`）。
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------- 常量
G = 9.81
RHO = 1000.0          # 水密度 kg/m3
RHO_AIR = 1.2         # 空气密度
NU = 1.0e-6           # 运动黏度 m2/s

EP = Path(__file__).resolve().parent.parent
RESULTS = EP / "results"
FIGS = RESULTS / "figs"


# ================================================================ 参数
@dataclass
class Params:
    """整机与部件参数。默认值 = 本期标称工况（见 data/来源清单.md）。"""

    # ---- 质量（kg）----
    m_bike: float = 104.0      # 整车（报道值，A3）
    m_rider: float = 72.0      # 骑手（估计，区间 65–85）
    m_fuel: float = 4.0        # 32 min 耗油（估计，区间 3–6）
    m_kit: float = 18.0        # 前后板/浮板/尾鳍/气囊（估计，区间 12–25）

    # ---- 几何（m）----
    wheelbase: float = 1.48
    x_front: float = 0.71      # 前支撑 x（重心前）
    x_rear: float = -0.77      # 后支撑 x
    b_front: float = 0.26      # 前板宽
    b_rear: float = 0.34       # 后板宽
    l_front: float = 0.95      # 前板长
    l_rear: float = 0.85       # 后板长
    z_off_front: float = 0.42  # 前板底面在重心以下的距离
    z_off_rear: float = 0.40   # 后板底面在重心以下的距离
    x_cg_shift: float = 0.0    # 骑手前后移重心（+ 向前）

    # ---- 安装角（deg）----
    delta_front_deg: float = 6.0
    delta_rear_deg: float = 2.0

    # ---- 桨轮 ----
    r_wheel: float = 0.35      # 轮半径
    b_wheel: float = 0.13      # 轮宽（桨叶宽）
    h_wheel_gap: float = 0.020 # 轮底比后板底面低多少（"浸深偏置"）
    n_blade: float = 2.0       # 同时在水里的桨叶数
    cd_blade: float = 1.2      # 桨叶阻力系数
    eta_drive: float = 0.85    # 传动效率

    # ---- 发动机 ----
    p_max_kw: float = 44.7     # 60+ hp
    rpm_peak: float = 9000.0
    gear: float = 8.0          # 总传动比（发动机转数/轮转数）

    # ---- 阻力 ----
    cda_air: float = 0.60      # 迎风面积×Cd（骑手直立）
    cd_app: float = 0.80       # 附体（舵、支架、前叉）
    a_app: float = 0.0012      # 附体迎流面积 m2
    c_spray: float = 0.85      # 喷溅阻力系数（相对升力）
    cf_scale: float = 1.0      # 摩擦阻力修正

    # ---- 升力模型 ----
    kL: float = 1.00           # 动升力系数（标定量）
    c_spray_root: float = 0.15 # 喷溅根长度系数

    # ---- 动力学 ----
    ca_heave: float = 0.35     # 垂荡附加质量系数
    ca_pitch: float = 0.30     # 纵倾附加质量系数
    zeta: float = 0.55         # 阻尼比
    h_thrust: float = 0.58     # 推力线到重心的高度
    h_drag: float = 0.45       # 阻力线到重心的高度

    # ---- 浮力（低速/2009 场景）----
    v_buoy: float = 0.045      # 浮力体排水体积 m3（浮板+气囊）
    a_float: float = 0.55      # 浮板水线面积 m2

    @property
    def mass(self) -> float:
        return self.m_bike + self.m_rider + self.m_fuel + self.m_kit

    @property
    def weight(self) -> float:
        return self.mass * G

    @property
    def inertia(self) -> float:
        """纵倾转动惯量（绕重心），按 0.55·m·L² 估。"""
        return 0.55 * self.mass * self.wheelbase ** 2

    def delta_front(self) -> float:
        return math.radians(self.delta_front_deg)

    def delta_rear(self) -> float:
        return math.radians(self.delta_rear_deg)

    def with_(self, **kw) -> "Params":
        return replace(self, **kw)


P0 = Params()


# ================================================================ 升力
def spring_stiffness(V: float, b: float, kL: float = 1.0) -> float:
    """单位浸深的动升力刚度 N/m（∝ V²）。"""
    return 0.5 * RHO * V * V * b * kL


def support_lift(V: float, b: float, h: float, alpha: float,
                 kL: float = 1.0, c_spray_root: float = 0.15) -> float:
    """单块板的升力：浸深项 + 喷溅根项，负浸深不出力。"""
    h_eff = max(h, 0.0) + c_spray_root * b * max(alpha, 0.0)
    if h_eff <= 0.0:
        return 0.0
    return spring_stiffness(V, b, kL) * h_eff


def savitsky_lift(V: float, b: float, h: float, alpha: float,
                  deadrise_deg: float = 0.0) -> float:
    """Savitsky(1964) 滑行升力，用作**独立互校**（不参与主模型）。

    C_L0 = τ^1.1 (0.012 λ^0.5 + 0.0055 λ^2.5 / Cv²)，τ 取**度**。
    λ = l_w/b，l_w = h/sinτ。注意本车 Cv≈13，远超原始适用范围（Cv≲5），
    因此只用于"量级对不对"的对照，见论文 3.2 的适用性讨论。
    """
    tau_deg = math.degrees(max(alpha, 1e-3))
    sin_a = max(math.sin(alpha), 1e-3)
    lw = h / sin_a
    lam = max(lw / b, 1e-3)
    cv = V / math.sqrt(G * b)
    cl0 = tau_deg ** 1.1 * (0.0120 * lam ** 0.5 + 0.0055 * lam ** 2.5 / cv ** 2)
    cl = cl0 - 0.0065 * deadrise_deg * max(cl0, 1e-9) ** 0.6
    return 0.5 * RHO * V * V * b * b * max(cl, 0.0)


# ================================================================ 静平衡
def equilibrium(V: float, p: Params = P0, eta_f: float = 0.0,
                eta_r: float = 0.0, thrust: float | None = None,
                drag: float | None = None) -> dict:
    """给定速度与局部波面，解两支撑的垂荡 z 与纵倾 θ（闭式）。

    L_i = k_i (h_i + c_s b_i α_i)，h_i = z_off_i - (z + x_i sinθ) - η_i
    ΣL=W，a L_f - b L_r = D·h_D - T·h_T
    """
    a = p.x_front - p.x_cg_shift
    b = -p.x_rear + p.x_cg_shift
    df, dr = p.delta_front(), p.delta_rear()
    kf = spring_stiffness(V, p.b_front, p.kL)
    kr = spring_stiffness(V, p.b_rear, p.kL)
    cs = p.c_spray_root

    T = thrust if thrust is not None else 0.0
    D = drag if drag is not None else 0.0
    Q = D * p.h_drag - T * p.h_thrust        # 抬头为正

    W = p.weight
    Lf = max((b * W + Q) / (a + b), 0.0)
    Lr = max((a * W - Q) / (a + b), 0.0)

    # L_i = k_i [h_i + cs b_i (θ+δ_i)]  ⟹  h_i = L_i/k_i - cs b_i (θ+δ_i)
    # 又 h_i = z_off_i - z - x_i sinθ - η_i
    # 相减消去 z：
    #  (a+b)θ - cs(b_f-b_r)θ = (z_f-z_r) - (η_f-η_r) - L_f/k_f + L_r/k_r
    #                          + cs(b_f δ_f - b_r δ_r)
    num = ((p.z_off_front - p.z_off_rear) + (eta_f - eta_r)
           - Lf / kf + Lr / kr + cs * (p.b_front * df - p.b_rear * dr))
    den = (a + b) - cs * (p.b_front - p.b_rear)
    theta = math.asin(max(-0.5, min(0.5, num / den)))
    hf = Lf / kf - cs * p.b_front * (theta + df)
    hr = Lr / kr - cs * p.b_rear * (theta + dr)
    # h_f = z_off_f - z - a sinθ - η_f  ⟹  z
    z = p.z_off_front - a * math.sin(theta) + eta_f - hf
    return dict(z=z, theta=theta, h_front=hf, h_rear=hr,
                l_front=Lf, l_rear=Lr, v=math.sin(theta),
                alpha_front=theta + df, alpha_rear=theta + dr,
                airborne_front=bool(hf < 0), airborne_rear=bool(hr < 0))


def wetted_length(h: float, alpha: float, b: float,
                  c_spray_root: float = 0.15) -> float:
    """湿长度 = 几何浸没长度 + 喷溅根。"""
    if h <= 1e-9 or alpha <= 1e-9:
        return 0.0
    return h / math.sin(alpha) + c_spray_root * b


# ================================================================ 阻力
def resistance(V: float, p: Params = P0, eq: dict | None = None,
               include_wheel_drag: bool = False) -> dict:
    """总阻力分解（N）。"""
    if eq is None:
        eq = equilibrium(V, p)
    re_w = math.sqrt(G * 0.02) * 0.02 / NU  # 占位，避免未定义

    # 1) 摩擦
    lwf = wetted_length(eq["h_front"], eq["alpha_front"], p.b_front, p.c_spray_root)
    lwr = wetted_length(eq["h_rear"], eq["alpha_rear"], p.b_rear, p.c_spray_root)
    S_wet = p.b_front * min(lwf, p.l_front) + p.b_rear * min(lwr, p.l_rear)
    Re = V * max(min(lwf, p.l_front), 1e-3) / NU
    Cf = 0.075 / (math.log10(max(Re, 1e4)) - 2) ** 2
    R_f = 0.5 * RHO * V * V * S_wet * Cf * p.cf_scale

    # 2) 升力的水平分量（诱导/压力阻力）
    R_p = (eq["l_front"] * math.tan(max(eq["alpha_front"], 0.0))
           + eq["l_rear"] * math.tan(max(eq["alpha_rear"], 0.0))) * p.c_spray

    # 3) 空气
    R_a = 0.5 * RHO_AIR * V * V * p.cda_air

    # 4) 附体（含桨轮不推进时的阻力）
    R_app = 0.5 * RHO * V * V * p.a_app * p.cd_app
    if include_wheel_drag:
        hw = wheel_immersion(eq, p)
        a_w = p.b_wheel * min(hw, 0.25) if hw > 0 else 0.0
        R_app += 0.5 * RHO * V * V * a_w * p.cd_blade

    # 5) 喷溅（把水抛起来要带走的动能，按升力比例）
    R_s = 0.02 * (eq["l_front"] + eq["l_rear"])

    total = R_f + R_p + R_a + R_app + R_s
    return dict(total=total, friction=R_f, pressure=R_p, air=R_a,
                appendage=R_app, spray=R_s, S_wet=S_wet, Cf=Cf,
                lw_front=min(lwf, p.l_front), lw_rear=min(lwr, p.l_rear),
                Re=Re, _re_w=re_w)


def wheel_immersion(eq: dict, p: Params = P0) -> float:
    """桨轮浸深 = 后板浸深 + 轮底偏置（负值表示脱水）。"""
    return eq["h_rear"] + p.h_wheel_gap


def paddle_thrust(u: float, V: float, h_w: float, p: Params = P0) -> float:
    """桨轮叶元推力：T = 1/2 ρ Cd n A_sub (u-V)²，A_sub = b·h。"""
    if h_w <= 0 or u <= V:
        return 0.0
    a_sub = p.b_wheel * min(h_w, p.r_wheel)
    return 0.5 * RHO * p.cd_blade * p.n_blade * a_sub * (u - V) ** 2


def engine_torque(rpm: float, p: Params = P0) -> float:
    """单缸 450 的扭矩曲线（抛物线，峰值 ~52 N·m @ 7600 rpm）。"""
    # 峰值扭矩由额定功率反推：P_max = T_pk·ω(8500 rpm) / 1.10
    w_p = 2 * math.pi * 8500 / 60
    T_pk = 1.10 * p.p_max_kw * 1000.0 / w_p
    rpm_pk, w = 7600.0, 3200.0
    return T_pk * (0.45 + 0.55 * math.exp(-((rpm - rpm_pk) / w) ** 2))


def thrust_at(V: float, hw: float, p: Params = P0, gear: float = 8.0,
              throttle: float = 1.0, rpm_max: float = 11500.0):
    """准稳态：解出桨轮转速 u，使"桨叶水阻扭矩 = 发动机可供给扭矩"。

    返回 (推力 N, u m/s, 滑差, 轮上功率 W)。
    """
    if hw <= 0 or throttle <= 0:
        return 0.0, V, 1.0, 0.0
    u_max = rpm_max * 2 * math.pi / 60.0 * p.r_wheel / gear
    if u_max <= V * 1.001:
        return 0.0, V, 1.0, 0.0

    def cap(u):
        rpm = u / p.r_wheel * gear * 60.0 / (2 * math.pi)
        return engine_torque(min(rpm, rpm_max), p) * gear * p.eta_drive / p.r_wheel

    def g(u):
        return paddle_thrust(u, V, hw, p) - throttle * cap(u)

    lo, hi = V * 1.0001, u_max
    if g(hi) <= 0:                      # 全程推不动：卡在最高转速
        T = paddle_thrust(hi, V, hw, p)
        return T, hi, (hi - V) / hi, T * hi
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if g(mid) > 0:
            hi = mid
        else:
            lo = mid
    u = 0.5 * (lo + hi)
    T = paddle_thrust(u, V, hw, p)
    return T, u, (u - V) / u, T * u


# ================================================================ 极速
def solve_speed_for_thrust(V: float, p: Params = P0, gear: float = 8.0,
                           throttle: float = 1.0) -> dict:
    """给定速度下的推进状态：推力、滑差、功率、阻力。"""
    eq = equilibrium(V, p)
    res = resistance(V, p, eq, include_wheel_drag=False)
    hw = wheel_immersion(eq, p)
    T, u, slip, Pw = thrust_at(V, hw, p, gear, throttle)
    return dict(V=V, thrust=T, u=u, slip=slip, power=Pw / max(p.eta_drive, 1e-6),
                drag=res["total"], feasible=T >= res["total"] * 0.999,
                hw=hw, eq=eq, res=res)


def max_speed(p: Params = P0, gears=(6.5, 7.5, 8.5, 9.5),
              v_lo: float = 3.0, v_hi: float = 45.0, n: int = 260) -> dict:
    """扫速度，取"任一挡位能推得动"的最高速度（准稳态）。"""
    best, best_info = -1.0, None
    for V in np.linspace(v_lo, v_hi, n):
        info = None
        for gear in gears:
            r = solve_speed_for_thrust(float(V), p, gear)
            if r["feasible"] and (info is None or r["power"] < info["power"]):
                info = r
        if info is not None:
            best, best_info = float(V), info
    if best_info is None:
        best_info = solve_speed_for_thrust(v_lo, p, gears[0])
    return dict(V_max=best, info=best_info)


def power_limited_speed(p: Params = P0) -> float:
    """只用功率约束（忽略桨轮吃水）的理论极速，用于对比。"""
    P = p.p_max_kw * 1000.0
    lo, hi = 5.0, 60.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        eq = equilibrium(mid, p)
        res = resistance(mid, p, eq)["total"]
        if res * mid / p.eta_drive < P:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ================================================================ 波浪
def jonswap(w, Hs: float, Tp: float, gamma: float = 3.3):
    wp = 2 * math.pi / Tp
    sigma = np.where(w <= wp, 0.07, 0.09)
    r = np.exp(-((w - wp) ** 2) / (2 * sigma ** 2 * wp ** 2))
    alpha = 0.0624 / (0.230 + 0.0336 * gamma - 0.185 / (1.9 + gamma))
    S = alpha * G ** 2 / w ** 5 * np.exp(-1.25 * (wp / w) ** 4) * gamma ** r
    # 归一到目标 Hs：Hs = 4 sqrt(m0)
    m0 = np.trapz(S, w)
    return S * (Hs / (4 * math.sqrt(max(m0, 1e-12)))) ** 2


def wave_components(Hs: float, Tp: float, n: int = 40, seed: int = 7):
    rng = np.random.default_rng(seed)
    w = np.linspace(0.35, 3.2, n)
    S = jonswap(w, Hs, Tp)
    dw = w[1] - w[0]
    A = np.sqrt(2 * S * dw)
    phi = rng.uniform(0, 2 * math.pi, n)
    k = w ** 2 / G
    return dict(A=A, w=w, phi=phi, k=k, Hs=Hs, Tp=Tp)


def eta(wc: dict, x, t):
    """波面升高（迎浪：相位 kx+ωt）。"""
    ph = np.outer(x, wc["k"]) + np.outer(t, wc["w"]) + wc["phi"]
    return np.cos(ph) @ wc["A"]


def eta_dot(wc: dict, x, t):
    ph = np.outer(x, wc["k"]) + np.outer(t, wc["w"]) + wc["phi"]
    return (-np.sin(ph) * wc["w"]) @ wc["A"]


def eta_at(wc: dict, x: float, t: float) -> float:
    """单点波面升高（迎浪：相位 kx+ωt）。"""
    return float(np.cos(wc["k"] * x + wc["w"] * t + wc["phi"]) @ wc["A"])


def eta_dot_at(wc: dict, x: float, t: float) -> float:
    return float((-np.sin(wc["k"] * x + wc["w"] * t + wc["phi"]) * wc["w"]) @ wc["A"])


# ================================================================ 时域
def simulate(V0: float, p: Params = P0, Hs: float = 1.0, Tp: float = 5.0,
             t_end: float = 30.0, dt: float = 0.004, seed: int = 7,
             throttle: float = 1.0, slip: float = 0.30,
             speed_hold: bool = True, kp: float = 2.2, fixed_speed: bool = False,
             record_every: int = 5, t_warm: float = 2.0) -> dict:
    """垂荡-纵倾-纵荡三自由度时域积分（RK4，含出水与砰击）。

    状态 y = [x, z, θ, V, ż, θ̇]。
    ``speed_hold=True`` 时用一个"骑手定速"比例控制器调油门（0–1），
    并把"油门打满仍追不上目标速度"的比例记为 ``thr_sat_frac``。
    """
    wc = wave_components(Hs, Tp, seed=seed)
    m = p.mass
    m_eff = m * (1 + p.ca_heave)
    I_eff = p.inertia * (1 + p.ca_pitch)
    W = p.weight
    cs = p.c_spray_root
    df, dr = p.delta_front(), p.delta_rear()
    thr0 = throttle

    eq0 = equilibrium(V0, p)
    # 初始就把车放到"当地波面"上，避免 t=0 的假砰击
    ef0 = eta_at(wc, p.x_front, 0.0)
    er0 = eta_at(wc, p.x_rear, 0.0)
    z0 = eq0["z"] + 0.5 * (ef0 + er0)
    th0 = eq0["theta"] + math.atan2(ef0 - er0, p.x_front - p.x_rear)
    y = np.array([0.0, z0, th0, V0, 0.0, 0.0])
    # 定速前馈：额定工况所需的油门开度
    _hw0 = wheel_immersion(eq0, p)
    _T0 = thrust_at(V0, _hw0, p, p.gear, 1.0)[0]
    _D0 = resistance(V0, p, eq0, include_wheel_drag=False)["total"]
    thr_ff = min(1.0, max(0.05, _D0 / max(_T0, 1e-6))) if speed_hold else 1.0

    def f(y, t):
        x, z, th, V, zd, thd = y
        s = math.sin(th)
        c = math.cos(th)
        xf, xr = x + p.x_front, x + p.x_rear
        ef, er = eta_at(wc, xf, t), eta_at(wc, xr, t)
        edf, edr = eta_dot_at(wc, xf, t), eta_dot_at(wc, xr, t)

        hgf = p.z_off_front - (z + p.x_front * s) + ef
        hgr = p.z_off_rear - (z + p.x_rear * s) + er
        af, ar = th + df, th + dr
        kf = spring_stiffness(V, p.b_front, p.kL)
        kr = spring_stiffness(V, p.b_rear, p.kL)
        hf_eff = max(hgf, 0.0) + cs * p.b_front * max(af, 0.0)
        hr_eff = max(hgr, 0.0) + cs * p.b_rear * max(ar, 0.0)
        Lf = kf * hf_eff if hf_eff > 0 else 0.0
        Lr = kr * hr_eff if hr_eff > 0 else 0.0

        vf = zd + p.x_front * thd * c - edf
        vr = zd + p.x_rear * thd * c - edr
        zeta = p.zeta
        bf = 2 * zeta * math.sqrt(max(kf, 1.0) * m / 2)
        br = 2 * zeta * math.sqrt(max(kr, 1.0) * m / 2)
        # 砰击（附加）阻尼：随浸深与下沉速度增大
        slam_f = 0.9 * RHO * V * p.b_front * max(hgf, 0.0) * max(-vf, 0.0)
        slam_r = 0.9 * RHO * V * p.b_rear * max(hgr, 0.0) * max(-vr, 0.0)
        Ff = -(bf * vf + slam_f)
        Fr = -(br * vr + slam_r)

        hw = hgr + p.h_wheel_gap
        if speed_hold:
            thr = min(1.0, max(0.0, thr_ff + kp * (V0 - V) / max(V0, 1.0)))
        else:
            thr = throttle
        T, u, slip_now, Pw = thrust_at(V, hw, p, p.gear, thr)
        slip = slip_now
        res = resistance(V, p, dict(l_front=Lf, l_rear=Lr, h_front=hgf,
                                    h_rear=hgr, alpha_front=af, alpha_rear=ar),
                         include_wheel_drag=False)
        D = res["total"]

        hb = max(0.0, -(z - 0.30))
        B = RHO * G * min(p.v_buoy, p.a_float * hb)
        Fz = Lf + Lr - W + Ff + Fr + B
        Mth = (p.x_front * (Lf + Ff) + p.x_rear * (Lr + Fr)
               + T * p.h_thrust - D * p.h_drag)
        az = Fz / m_eff
        ath = Mth / I_eff
        dV = 0.0 if fixed_speed else (T - D) / m
        return np.array([V, zd, thd, dV, az, ath]), dict(
            Lf=Lf, Lr=Lr, hgf=hgf, hgr=hgr, hw=hw, T=T, D=D, ef=ef, er=er,
            thr=thr)

    n = int(t_end / dt)
    rec = {k: [] for k in ("t", "x", "z", "theta", "V", "zdot", "thetadot",
                           "h_f", "h_r", "hw", "Lf", "Lr", "az", "ath",
                           "thrust", "drag", "eta_f", "eta_r", "bow_z", "thr")}
    for i in range(n):
        t = i * dt
        k1, d1 = f(y, t)
        k2, _ = f(y + 0.5 * dt * k1, t + 0.5 * dt)
        k3, _ = f(y + 0.5 * dt * k2, t + 0.5 * dt)
        k4, _ = f(y + dt * k3, t + dt)
        y = y + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        y[4] = max(-15, min(15, y[4]))
        y[5] = max(-10, min(10, y[5]))
        y[2] = max(-0.7, min(0.7, y[2]))
        y[3] = max(0.2, min(2.2 * V0, y[3]))
        if i % record_every == 0:
            x, z, th, V, zd, thd = y
            dy, dd = f(y, t)
            bow_z = z + 1.05 * math.sin(th) + 0.30 - eta_at(wc, x + 1.05, t)
            rec["t"].append(t); rec["x"].append(x); rec["z"].append(z)
            rec["theta"].append(th); rec["V"].append(V)
            rec["zdot"].append(zd); rec["thetadot"].append(thd)
            for k in ("h_f", "h_r", "hw", "Lf", "Lr", "thrust", "drag",
                      "eta_f", "eta_r"):
                key = {"h_f": "hgf", "h_r": "hgr",
                       "thrust": "T", "drag": "D",
                       "eta_f": "ef", "eta_r": "er"}.get(k, k)
                rec[k].append(dd[key])
            rec["az"].append(float(dy[4]))
            rec["ath"].append(float(dy[5]))
            rec["thr"].append(float(dd["thr"]))
            rec["bow_z"].append(bow_z)

    out = {k: np.asarray(v) for k, v in rec.items()}
    msk = out["t"] >= t_warm
    if msk.sum() < 10:
        msk = np.ones_like(out["t"], dtype=bool)
    az = out["az"][msk]
    out["metrics"] = dict(
        az_rms=float(np.sqrt(np.mean(az ** 2))),
        az_rms_g=float(np.sqrt(np.mean(az ** 2)) / G),
        az_p95=float(np.percentile(np.abs(az), 95)),
        az_max=float(np.max(np.abs(az))),
        theta_rms_deg=float(np.degrees(np.sqrt(np.mean(out["theta"][msk] ** 2)))),
        theta_max_deg=float(np.degrees(np.max(np.abs(out["theta"])))),
        hw_out_frac=float(np.mean(out["hw"][msk] <= 0.003)),
        bow_dive_frac=float(np.mean(out["bow_z"][msk] < 0.0)),
        h_f_max=float(np.max(out["h_f"])),
        h_r_max=float(np.max(out["h_r"])),
        V_mean=float(np.mean(out["V"][msk])),
        V_min=float(np.min(out["V"][msk])),
        thrust_mean=float(np.mean(out["thrust"][msk])),
        drag_mean=float(np.mean(out["drag"][msk])),
        thr_sat_frac=float(np.mean((out["thr"][msk] >= 0.995)
                                   & (out["V"][msk] < 0.95 * V0))),
        air_frac=float(np.mean(out["h_r"][msk] < -0.005)),
    )
    out["wc"] = wc
    return out



# ================================================================ 频域
def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def freq_response(V: float, p: Params = P0, Hs: float = 1.0, Tp: float = 5.0,
                  n: int = 60, seed: int = 7) -> dict:
    """两自由度线性化频域响应（与 `simulate` 互为独立校核）。

    线性化：L_i = k_i(h_i + ...)，∂L/∂z = -k_i，∂L/∂θ = -k_i x_i。
    激励取各支撑处波面（含 kx 相位差，天然给出 encounter 频率）。
    """
    wc = wave_components(Hs, Tp, n=n, seed=seed)
    eq = equilibrium(V, p)
    kf = spring_stiffness(V, p.b_front, p.kL)
    kr = spring_stiffness(V, p.b_rear, p.kL)
    xf, xr = p.x_front, p.x_rear
    m = p.mass * (1 + p.ca_heave)
    I = p.inertia * (1 + p.ca_pitch)
    K = np.array([[kf + kr, kf * xf + kr * xr],
                  [kf * xf + kr * xr, kf * xf ** 2 + kr * xr ** 2]])
    M = np.diag([m, I])
    ev = np.linalg.eigvals(np.linalg.solve(M, K))
    w1, w2 = np.sqrt(np.sort(np.abs(ev)))
    zt = p.zeta
    Amat = np.array([[1.0, w1 ** 2], [1.0, w2 ** 2]])
    alpha, beta = np.linalg.solve(Amat, [2 * zt * w1, 2 * zt * w2])
    C = alpha * M + beta * K

    w = wc["w"]; k = wc["k"]; amp = wc["A"]
    we = w + k * V                      # 迎浪 encounter 频率
    sz2 = st2 = sd2f = sd2r = ra2 = 0.0
    for i in range(len(w)):
        ph_f = np.exp(1j * k[i] * xf)
        ph_r = np.exp(1j * k[i] * xr)
        # M q̈ + K q = K_η η  （η 抬高水面 ⟹ 升力增大）
        F = amp[i] * np.array([kf * ph_f + kr * ph_r,
                               kf * xf * ph_f + kr * xr * ph_r])
        H = np.linalg.inv(-we[i] ** 2 * M + 1j * we[i] * C + K)
        q = H @ F
        sz2 += abs(q[0]) ** 2 / 2
        st2 += abs(q[1]) ** 2 / 2
        df = -(q[0] + xf * q[1]) + amp[i] * ph_f
        dr = -(q[0] + xr * q[1]) + amp[i] * ph_r
        sd2f += abs(df) ** 2 / 2
        sd2r += abs(dr) ** 2 / 2
        ra2 += abs(we[i] ** 2 * q[0]) ** 2 / 2

    sdf, sdr = math.sqrt(sd2f), math.sqrt(sd2r)
    hf, hr = eq["h_front"], eq["h_rear"]
    zc = 1.96
    return dict(
        sigma_z=math.sqrt(sz2), sigma_theta=math.sqrt(st2),
        sigma_acc=math.sqrt(ra2), sigma_dh_f=sdf, sigma_dh_r=sdr,
        h_f=hf, h_r=hr, hw=wheel_immersion(eq, p),
        p_loss_f=_norm_cdf(-hf / max(sdf, 1e-6)),
        p_loss_r=_norm_cdf(-hr / max(sdr, 1e-6)),
        p_loss_w=_norm_cdf(-(hr + p.h_wheel_gap) / max(sdr, 1e-6)),
        acc_p95=zc * math.sqrt(ra2),
        acc_rms_g=math.sqrt(ra2) / G,
        delta_p95_f=zc * sdf, delta_p95_r=zc * sdr,
        theta_p95_deg=math.degrees(zc * math.sqrt(st2)),
        eq=eq,
    )


# ================================================================ 工具
def to_json(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    def conv(o):
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, Path):
            return str(o)
        raise TypeError(type(o))
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=conv),
                    encoding="utf-8")
    print(f"[json] {path}")


def kmh(V: float) -> float:
    return V * 3.6
