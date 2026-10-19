#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **10 个喷口的完整状态**（供动画逐一点亮）。

## 用户的第二条要求

> **"不光四个竖向喷嘴要显示，其余的喷嘴也要显示。"**

## 为什么这带来实质工作量

原来 `Rec` 只记 `lift_on`（4 个竖推）与 `roll_l`/`roll_r`（2 个滚转）。
**现在必须记全部 10 个**，而且每个的**推力、占空比、累计出气量**都要有。

## 10 个喷口的任务与"谁在什么时候喷"

| # | 名称 | 轴 | 什么时候工作 |
|---|---|---|---|
| 1 | `MAIN` | +X | **本次演出不用**（没有水平加速段）|
| 2-5 | `LIFT_FL/FR/RL/RR` | +Z | **起飞** + **落地缓冲** |
| 6 | `PITCH_UP` | +Z（尾）| **倒挂翻正**上半段 |
| 7 | `PITCH_DN` | +Z（头）| **倒挂翻正**下半段 |
| 8 | `UNCAP` | −Z（顶）| **倒挂分离**（脱离坡面）|
| 9 | `ROLL_L` | +Y | **飞跃滚转**上半段 |
| 10 | `ROLL_R` | −Y | **飞跃滚转**下半段 |

**★ 注意**：`PITCH_UP`/`PITCH_DN` 与 `ROLL_L`/`ROLL_R` 都是 **bang-bang 的先后两段**，
**不会同时点火** —— 动画里必须体现出"先 A 后 B"。

## 时间线（本次演出）

| 阶段 | 时刻 | 工作喷口 |
|---|---|---|
| ① 倒挂行驶 | 0 – 0.20 s | 无（风扇电驱）|
| ② 分离 | 0.20 – 0.40 s | `UNCAP` |
| ③ **翻正半圈（俯仰）** | 0.40 – 2.40 s | `PITCH_UP` → `PITCH_DN` |
| ④ 起飞 | 2.40 – 3.10 s | 4 竖推 |
| ⑤ **滚转整圈（左右翻转）** | 3.10 – 5.60 s | `ROLL_L` → `ROLL_R` |
| ⑥ 落地缓冲 | 5.60 – 6.40 s | 4 竖推 |

**★ 但"倒挂"与"飞跃"是两次独立的演示**，
所以本动画的"飞跃"段**从起飞开始**（不含 ①②③）。
**⇒ 要显示倒挂段的喷口，得另做一段动画。本脚本先给"飞跃"的完整 10 喷口。**
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph      # noqa: E402
import nozzles as nz      # noqa: E402
import pfm as pfm_lib     # noqa: E402


# 10 个喷口的元信息（名称、轴、颜色、在车体上的示意位置）
# ★ B 方案：同侧两喷（y=±0.55）同时开 ⇒ τ = 2×0.55×F = 1.1F
ROLL_ARM_PAIR = 1.10

# ★ C 方案：侧推配平推力上限（N）。$F_s=2F\tan\theta$ 在 θ→90° 发散，
#   必须限幅，并如实报告残余横漂。
SIDE_MAX = 8.0e3

# ★★★ MIB（最小冲量比特）与脉冲调制参数
#   冷气推力器是开关型，阀门最短开通时间决定了占空比下限。
PWM_MIN_ON = 0.012          # 12 ms（阀门响应 + 建立推力）
# 同一逻辑动作的喷口必须同步脉冲，否则对称性被破坏（会带出 τy）
COUPLE_TRIM_F = 5.0e3      # 补段时按 2F=5 kN 量级配平
TRIM_TOL = 0.035            # 2 deg 终端补脉冲死区
TRIM_MAX_T = 2.50           # 补脉冲最长时间 (s)
CHANNEL = {
    "LIFT_FL": "lift", "LIFT_FR": "lift",
    "LIFT_RL": "lift", "LIFT_RR": "lift",
    "SIDE_P": "side", "SIDE_N": "side",
}


def channel_of(name: str) -> str:
    return CHANNEL.get(name, name)


def _balance_side(duty: dict, st, F_both: float, p_now: float,
                  AREA: dict) -> None:
    cth, sth = math.cos(st.theta), math.sin(st.theta)
    if abs(cth) > 0.15:
        fs = F_both * sth / cth
    else:
        fs = F_both * (1.0 if sth > 0 else -1.0)
    fs = max(-SIDE_MAX, min(SIDE_MAX, fs))
    if abs(fs) > 1.0:
        nm = "SIDE_P" if fs > 0 else "SIDE_N"
        fa = nz.force_of_area(AREA[nm], p_now)
        if fa > 0:
            duty[nm] = min(1.0, abs(fs) / fa)


def body_to_world(axis: str, c: float, s: float) -> tuple[float, float, float]:
    r"""车体系推力方向 → 世界系（绕 $x$ 滚转 $	heta$）。"""
    base = {"+X": (1, 0, 0), "-X": (-1, 0, 0), "+Z": (0, 0, 1),
            "-Z": (0, 0, -1), "+Y": (0, 1, 0), "-Y": (0, -1, 0)}[axis]
    return (base[0], base[1] * c - base[2] * s, base[1] * s + base[2] * c)


NOZZLE_META: list[dict] = [
    # ---- ★ 车尾扩散器 4 台主推进器（轴 −X：向后喷 ⇒ 车向前加速）----
    {"i": 1,  "name": "REAR_1",  "axis": "-X", "short": "R1",
     "color": "#f59e0b", "pos": (-2.10, -0.75), "pos2_z": 0.00},
    {"i": 2,  "name": "REAR_2",  "axis": "-X", "short": "R2",
     "color": "#fbbf24", "pos": (-2.10, -0.25), "pos2_z": 0.00},
    {"i": 3,  "name": "REAR_3",  "axis": "-X", "short": "R3",
     "color": "#fcd34d", "pos": (-2.10, +0.25), "pos2_z": 0.00},
    {"i": 4,  "name": "REAR_4",  "axis": "-X", "short": "R4",
     "color": "#fde68a", "pos": (-2.10, +0.75), "pos2_z": 0.00},
    # ---- 车底四角竖推（起降 / 缓冲 / 滚转）----
    {"i": 5,  "name": "LIFT_FL", "axis": "+Z", "short": "FL",
     "color": "#ef4444", "pos": (+1.5, -0.55), "pos2_z": -0.30},
    {"i": 6,  "name": "LIFT_FR", "axis": "+Z", "short": "FR",
     "color": "#dc2626", "pos": (+1.5, +0.55), "pos2_z": -0.30},
    {"i": 7,  "name": "LIFT_RL", "axis": "+Z", "short": "RL",
     "color": "#b91c1c", "pos": (-1.5, -0.55), "pos2_z": -0.30},
    {"i": 8,  "name": "LIFT_RR", "axis": "+Z", "short": "RR",
     "color": "#991b1b", "pos": (-1.5, +0.55), "pos2_z": -0.30},
    # ---- 侧面 2 台（横向配平）----
    {"i": 9,  "name": "SIDE_P",  "axis": "+Y", "short": "S+",
     "color": "#3b82f6", "pos": (0.0, -1.10), "pos2_z": 0.00},
    {"i": 10, "name": "SIDE_N",  "axis": "-Y", "short": "S-",
     "color": "#1d4ed8", "pos": (0.0, +1.10), "pos2_z": 0.00},
]


NAMES = [m["name"] for m in NOZZLE_META]


@dataclass
class Rec10:
    r"""单步状态（含**全部 10 个喷口**）。"""
    t: float = 0.0
    x: float = 0.0
    z: float = 0.0
    vx: float = 0.0
    vz: float = 0.0
    theta: float = 0.0
    omega: float = 0.0
    # 每个喷口的当前推力（N），键 = 名称
    f: dict = field(default_factory=dict)
    # 每个喷口的占空比（0..1）
    duty: dict = field(default_factory=dict)
    # 每个喷口的累计出气量（kg）
    m_used: dict = field(default_factory=dict)
    # ★ 新加：横向自由度与力矩（用于验证"力偶净力/净横向为零"）
    y: float = 0.0
    vy: float = 0.0
    tau: float = 0.0
    tau_y: float = 0.0
    tau_z: float = 0.0
    p_mPa: float = 0.0
    m_total: float = 0.0


LIFT4 = ("LIFT_FL", "LIFT_FR", "LIFT_RL", "LIFT_RR")


# ============================================================================
#  控制律（**纯函数**：只读状态，不推进相位、不改任何外部变量）
# ============================================================================
#  ★★★ 2026-10-18 第三次修：**为什么必须拆成纯函数**
#
#  冲量与质量的记账要改成"步中点采样"，就必须能在**半步处的预测状态**上
#  再求一次控制律。而原来的控制律与相位机搅在一起（`t_burn = st.t`、
#  `t_trim = st.t`、`ctrl.step()` 会冻结减速度），
#  **每步调用两次就会把相位推进两次** —— 那是一个更隐蔽的错误。
#
#  ⇒ 拆成三层：
#    ① `_advance_phase`：只管相位转移与副作用（每步一次）；
#    ② `_duty_at`：纯函数，任意状态都能求值（每步 1～2 次）；
#    ③ 主循环：状态钳制 + 轮胎力 + PFM + 积分。
# ============================================================================


def _roll_duty(st, ctx: dict) -> dict[str, float]:
    r"""滚转段的占空比（主段 bang-bang / 补段比例闭环）。"""
    duty: dict[str, float] = {}
    t0, Td = ctx["roll_win"]
    if st.t < t0 + Td:
        # ---- 主段：开环 bang-bang（B 方案）+ 侧推配平（C 方案）----
        alpha = ph.bang_bang_alpha(2 * math.pi * ctx["n_turns"], Td)
        first_half = st.t < t0 + Td / 2
        tau_need = abs(ph.J_ROLL * alpha)
        F_b = tau_need / ROLL_ARM_PAIR
        fm_lift = ctx["fm_lift"]
        dc_b = min(1.0, F_b / fm_lift) if fm_lift > 0 else 0.0
        if first_half:
            duty["LIFT_FL"] = dc_b
            duty["LIFT_RL"] = dc_b
        else:
            duty["LIFT_FR"] = dc_b
            duty["LIFT_RR"] = dc_b
        _balance_side(duty, st, 2.0 * F_b, ctx["p_now"], ctx["AREA"])
        return duty
    # ---- 补段：比例闭环，死区 2°，超时 1 s ----
    dth = ctx["target"] - st.theta
    want = dth - 0.35 * st.omega
    dc_t = min(0.95, max(0.10, abs(want) * 2.5))
    if want > 0.0:
        duty["LIFT_FR"] = dc_t
        duty["LIFT_RR"] = dc_t
    else:
        duty["LIFT_FL"] = dc_t
        duty["LIFT_RL"] = dc_t
    _balance_side(duty, st, COUPLE_TRIM_F, ctx["p_now"], ctx["AREA"])
    return duty


def _duty_at(st, phase: str, ctx: dict) -> dict[str, float]:
    r"""**纯**占空比：给定状态与相位，返回 10 个喷口的 $d$。

    无副作用 ⇒ 可以在步首、步中点、甚至任意试探状态上重复调用。
    """
    duty = {n: 0.0 for n in NAMES}
    if phase == "takeoff":
        for n in LIFT4:
            duty[n] = 1.0
    elif phase == "roll":
        if ctx["roll_win"] is not None:
            duty.update(_roll_duty(st, ctx))
    elif phase == "buffer":
        fz_need = ctx.get("fz_need", 0.0)
        if fz_need > 0.0:
            fm = ctx["fm_lift"]
            d = min(1.0, fz_need / 4.0 / fm) if fm > 0 else 0.0
            for n in LIFT4:
                duty[n] = d
    return duty


def _advance_phase(st, phase: str, ctx: dict) -> str:
    r"""相位机（**每步只调一次**）：转移 + 副作用（$t_{\text{burn}}$、$t_{\text{trim}}$、冻结减速度）。"""
    if phase == "accel":
        if st.vx >= ph.V_LAUNCH_X - 1e-6:
            phase = "takeoff"
    if phase == "takeoff":
        still_climbing = (st.z + st.vz * st.vz / (2 * ph.G)) < ph.H_JUMP - 0.42
        if not still_climbing:
            ctx["t_burn"] = st.t
            phase = "roll"
    if phase == "roll":
        if ctx["roll_win"] is None:
            phase = "buffer"                 # 探路那遍不滚转
        elif st.t >= ctx["roll_win"][0] + ctx["roll_win"][1]:
            if ctx["t_trim"] is None:
                ctx["t_trim"] = st.t
            dth = ctx["target"] - st.theta
            settled = abs(dth) <= TRIM_TOL and abs(st.omega) <= 0.15
            if settled or (st.t - ctx["t_trim"] > TRIM_MAX_T):
                phase = "buffer"
    if phase == "buffer":
        ctx["fz_need"] = ctx["ctrl"].step(st.z, st.vz, st.t)
    return phase


def run_mission10(dt: float = 1 / 150, n_turns: float = 1.0,
                  roll_win: tuple[float, float] | None = None,
                  ledger: str = "analytic") -> list[Rec10]:
    r"""跑一次**完整五阶段任务**，记录全部 10 个喷口。

    ## `ledger`：脉冲记账方式（见 `pfm.py`）

    | 值 | 含义 |
    |---|---|
    | `analytic`（默认） | 步中点累积 + 解析脉冲队列（**与步长无关**）|
    | `asrun` | 旧代码的真实行为（记录分数步、动力学整步）|
    | `legacy1/2/3` | 旧对照表的三档 |

    旧实现把"记账"与"物理"搅在一起，导致同一任务、只改记账方式，
    落地横漂在 0.57 – 8.28 m 之间跳（14 倍）。现拆开后，
    **记账对不对**由 `verify_pfm_ledger.py` 单独证明，
    **飞行结果**由 `scan_dt_convergence.py` 扫步长。

    ## 五阶段（用户要求把加减速改用轮胎）

    | # | 阶段 | 触发 → 结束 | 水平 | 竖向 |
    |---|---|---|---|---|
    | ① | **助跑** | $v_x < v_{\text{jump}}$ | **轮胎** | 贴地 |
    | ② | **起飞** | 开始 → 熄火 | — | 4 竖推 |
    | ③ | **滚转** | 熄火 → 缓冲起点 | — | 2 滚转 |
    | ④ | **缓冲** | 缓冲起点 → 触地 | — | 4 竖推 |
    | ⑤ | **制动** | 触地 → $v_x = 0$ | **刹车** | 贴地 |

    ## ★★ 为什么助跑与制动不用冷气

    **轮胎的抓地极限被风扇大幅抬高**：

    $$N = mg + F_{\text{fan}} = 3.35\,mg
    \;\Longrightarrow\; a_{\max} = \mu N/m = 4.35\,g$$

    **⇒ 0→60 km/h 只需 0.47 s / 4.4 m，零耗气。**

    **⇒ 气罐从此只服务竖直方向，余量充足。**
    """
    p = ph.Params(drag_k=0.0, j=ph.J_ROLL)

    m_tank = ph.M_AIR
    tau_y_peak = 0.0
    tau_z_peak = 0.0
    at_lift = nz.area_for_force(20e3, ph.P_TANK)
    # -- 力偶喷口面积：按 8 kN 设计。每喷需 F = tau/d = 5663/1.40 = 4.05 kN；
    #    罐压降到 24 MPa 时 8 kN 档仍能出约 5.5 kN => duty 约 0.74，不钳制。
    #    原来按 2.5 kN => duty 钳在 1.0 => 两侧推力不等 => 力偶失效。
    at_side = nz.area_for_force(8.0e3, ph.P_TANK)   # 侧推配平档
    at_pitch = nz.area_for_force(5e3, ph.P_TANK)
    at_uncap = nz.area_for_force(5e3, ph.P_TANK)
    at_main = nz.area_for_force(80e3, ph.P_TANK)  # 4 台合计 80 kN

    AREA = {
        "REAR_1": at_main / 4.0, "REAR_2": at_main / 4.0,
        "REAR_3": at_main / 4.0, "REAR_4": at_main / 4.0,
        "LIFT_FL": at_lift, "LIFT_FR": at_lift,
        "LIFT_RL": at_lift, "LIFT_RR": at_lift,
        "SIDE_P": at_side, "SIDE_N": at_side,
    }

    # ---- 轮胎参数 ----
    MU_TIRE = 1.30                       # 半热熔干沥青
    F_FAN = nz.F_FAN if hasattr(nz, "F_FAN") else 46.1e3
    P_MOTOR = 745e3                      # ≈1000 hp
    A_GRIP = MU_TIRE * (ph.G + F_FAN / ph.M_CAR)   # 抓地极限

    def a_tire(v: float, driving: bool) -> float:
        r"""轮胎可提供的加速度（驱动力受限，刹车不受功率限）。"""
        if not driving:
            return A_GRIP
        return min(A_GRIP, P_MOTOR / (ph.M_CAR * max(v, 0.5)))

    used = {n: 0.0 for n in NAMES}
    st = ph.State(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    H_PEAK = ph.H_JUMP
    V_JUMP = ph.V_LAUNCH_X

    phase = "accel"
    ctrl = ph.BufferController(m=p.m, z_trigger=ph.Z_TRIGGER)

    # ---- 相位机上下文（`_duty_at` / `_advance_phase` 的输入）----
    ctx: dict = {
        "roll_win": roll_win,
        "n_turns": n_turns,
        "target": -2.0 * math.pi * n_turns,
        "t_burn": None,
        "t_trim": None,
        "ctrl": ctrl,
        "AREA": AREA,
        "p_now": ph.P_TANK,
        "fm_lift": nz.force_of_area(at_lift, ph.P_TANK),
        "fz_need": 0.0,
    }
    # ---- ★ 脉冲记账器（唯一一处决定"记账方式"的地方）----
    pfm = pfm_lib.PFM(PWM_MIN_ON, ledger=ledger)
    use_mid = ledger in pfm_lib.NEEDS_MID
    thrust_prev = ph.Thrust()          # 预测步中点用的上一拍合力

    recs: list[Rec10] = []

    def p_of(mass: float) -> float:
        return max(mass * ph.R_GAS * ph.T0 / ph.V_TANK, ph.P_ATM * 1.01)

    while st.t < 20.0 and len(recs) < 200000:
        p_now = p_of(m_tank)
        f_now = {n: 0.0 for n in NAMES}
        duty = {n: 0.0 for n in NAMES}
        dm_total = 0.0
        fx = 0.0
        fx_total = 0.0
        fy_total = 0.0
        torque = 0.0
        tau_y = 0.0
        tau_z = 0.0
        fz_total = 0.0
        LIFT4 = ("LIFT_FL", "LIFT_FR", "LIFT_RL", "LIFT_RR")

        # ================= 阶段推进（每步一次）=================
        ctx["p_now"] = p_now
        ctx["fm_lift"] = nz.force_of_area(at_lift, p_now)
        phase = _advance_phase(st, phase, ctx)

        # ================= 控制律：步首 + 步中点 =================
        duty_beg = _duty_at(st, phase, ctx)
        if use_mid:
            # ★ 步中点用**上一拍**的合力预测（误差 O(dt²)），
            #   不能在本步内迭代求解 —— 那会让"力"依赖"记账"、"记账"依赖"力"。
            k_pred = ph.deriv(st, thrust_prev, p)
            st_mid = ph._mk(st, k_pred, dt / 2, t_new=st.t + dt / 2)
            duty = _duty_at(st_mid, phase, ctx)
        else:
            duty = duty_beg

        # ================= 脉冲调制（PFM / MIB） =================
        # ★★★ 2026-10-18 第三次修：**调制器独立成 `pfm.py`**
        #
        # 旧实现把三件事混在一个循环里：① 预算怎么累积 ② 脉冲何时点火
        # ③ 力与耗气按什么比例施加。于是"落地横漂 0.566 → 8.281 m（14 倍）"
        # 这个现象**无法归因**（见 paper/论文.md §6.7）。
        #
        # 现在：`pfm.PFM` 只管 ① ②，账目守恒由 `verify_pfm_ledger.py`
        # 用三条已知 d(t) 单独证明（冲量/质量相对误差 < 0.2%，
        # 且**跨 dt 极差 0.0000%**）。
        ch_duty: dict[str, float] = {}
        for n in NAMES:
            if duty[n] > 0:
                ch = channel_of(n)
                ch_duty[ch] = max(ch_duty.get(ch, 0.0), duty[n])
        on = pfm.step(st.t, dt, ch_duty)

        # ================= 状态钳制 / 触地 / 轮胎力 =================
        if phase == "accel":
            fx = ph.M_CAR * a_tire(st.vx, driving=True)
            st.z = 0.0
            st.vz = 0.0

        # 触地判据用**本步开始前**的状态（与原实现一致：rk4 还没跑）
        if phase == "buffer" and st.z <= 0.0 and st.vz < 0.0:
            phase = "brake"
            st.z = 0.0
            st.vz = 0.0

        if phase == "brake":
            st.z = 0.0
            st.vz = 0.0
            if st.vx <= 1e-3:
                fx = -ph.M_CAR * st.vx / dt      # 精确停在 0
            else:
                fx = -ph.M_CAR * a_tire(st.vx, driving=False)

        # ================= 喷口计算 =================
        for n in NAMES:
            if duty[n] <= 0:
                continue
            ch = channel_of(n)
            ff, mf = pfm.scales(on.get(ch, 0.0))
            if ff <= 0.0 and mf <= 0.0:
                f_now[n] = 0.0
                continue
            ffull = nz.force_of_area(AREA[n], p_now)
            # ★★★ 2026-10-18 第三次修：**记录值与实际施加值必须是同一个数**
            #
            # 旧代码：
            #     f_now[n] = fnow * on_frac      # 记录（动画用）
            #     fz_n = fnow * w[2]             # ← 动力学用**满推力**
            # ⇒ 注释写着"本步只施加与该脉冲重叠的那部分"，动力学走的却是整步。
            #   这类错**不会报错**，因为动画是对的、报表也是对的；
            #   只有"记账守恒脚本"能抓到它（见 `verify_pfm_ledger.py`）。
            f_eff = ffull * ff
            f_now[n] = f_eff
            # ★★ 耗气按同一比例的 mf：推力与耗气**必须逐项同源**，
            #    否则罐压掉的快慢与冲量不对应 ⇒ 轨迹整体漂移。
            dm = nz.mdot_of_area(AREA[n], p_now) * dt * mf
            used[n] += dm
            dm_total += dm
            # ★★★ 由**喷口几何**算力与力矩（不再自由给定力矩）。
            #   喷口位置在车体坐标；绕 x 滚转 θ 后转世界系。
            meta = next(mm for mm in NOZZLE_META if mm["name"] == n)
            cth, sth = math.cos(st.theta), math.sin(st.theta)
            # 推力方向（车体系 → 世界系）
            w = body_to_world(meta["axis"], cth, sth)
            # 喷口位置（车体系 → 世界系，绕 x 转）
            ly, lz = meta["pos"][1], meta["pos2_z"]
            wy = ly * cth - lz * sth
            wz = ly * sth + lz * cth
            fx_n = f_eff * w[0]
            fy_n = f_eff * w[1]
            fz_n = f_eff * w[2]
            fx_total += fx_n
            fy_total += fy_n
            fz_total += fz_n
            # τ = r × F（三个分量都算，用于检验"是否只产生滚转"）
            wx = meta["pos"][0]
            torque += wy * fz_n - wz * fy_n          # τ_x
            tau_y += wz * fx_n - wx * fz_n           # τ_y  ← 寄生俯仰
            tau_z += wx * fy_n - wy * fx_n           # τ_z  ← 寄生偏航
            tau_y_peak = max(tau_y_peak, abs(tau_y))
            tau_z_peak = max(tau_z_peak, abs(tau_z))

        thrust_now = ph.Thrust(fz=fz_total, fx=fx + fx_total,
                               fy=fy_total, torque=torque)
        m_tank -= dm_total
        st = ph.rk4_step(st, thrust_now, p, dt)
        thrust_prev = thrust_now
        recs.append(Rec10(
            t=st.t, x=st.x, z=st.z, vx=st.vx, vz=st.vz,
            y=st.y, vy=st.vy, tau=torque, tau_y=tau_y, tau_z=tau_z,
            theta=st.theta, omega=st.omega,
            f=dict(f_now), duty=dict(duty), m_used=dict(used),
            p_mPa=p_now / 1e6, m_total=sum(used.values()),
        ))
        if phase == "brake" and st.vx <= 1e-3:
            break

    run_mission10.t_burn = ctx["t_burn"]   # type: ignore[attr-defined]
    run_mission10.phase_end = phase        # type: ignore[attr-defined]
    run_mission10.roll_win = roll_win      # type: ignore[attr-defined]
    run_mission10.t_trig = None            # type: ignore[attr-defined]
    run_mission10.pfm = pfm                # type: ignore[attr-defined]
    return recs


def run_mission10_auto(dt: float = 1 / 150,
                       n_turns: float = 1.0,
                       ledger: str = "analytic",
                       quiet: bool = False) -> list[Rec10]:
    r"""**两遍法**：先测真实腾空时间，再据此定滚转窗口。

    ## 为什么必须两遍

    滚转要在"熄火 → 落地"这段完成**恰好** $n$ 圈。
    但这段时长**依赖落地缓冲**（缓冲拉长下落），
    **而缓冲又依赖罐压**（起飞耗气会降压）—— 环环相扣。

    **⇒ 只能先跑一遍测出时长，再回头定角加速度。**
    这是"被控量的后果反过来影响被控量"时的标准做法：**迭代一次**。

    ## 第一遍（探路）

    不滚转，测出熄火时刻 $t_b$ 与落地时刻 $t_L$。

    ## 第二遍（定稿）

    滚转窗口 $=(t_b,\ t_L-t_b)$，按 $\alpha = 4\theta/T^2$ 反解，
    **保证落地瞬间正好转完 $n$ 圈**。

    **★ 这修正了一个真实错误**：原来用
    $T_{\text{est}} = 2v_{z0}/g\times1.2$ 估时间，
    与"含起飞推进段"的真实腾空不符，实测**转到了 511°**（应 360°）。
    """
    probe = run_mission10(dt, n_turns=0.0, roll_win=None, ledger=ledger)
    t_b = getattr(run_mission10, "t_burn", None) or 0.0
    # ★★★ 滚转必须在**落地缓冲开始之前**完成。
    #   原因：喷口与车身固连，竖推的竖直分量 = F·cosθ。
    #   若滚转还没转完（θ 接近 90°），缓冲不但不托车，还会把车往侧下方推。
    #   实测把滚转铺满整个腾空段 ⇒ 落地 vz = −4.65 m/s（曾到 −12.2）。
    # ★ 必须加 `r.t > t_b + 0.05`：助跑阶段车贴地（z=0），
    #   积分器会给出极小的负 vz，会被误判成"缓冲起点"（实测拿到 0.007 s，
    #   导致滚转窗几乎为 0、角加速度爆炸到 2.5×10⁷ 度）。
    t_trig = probe[-1].t
    for r in probe:
        if r.t > t_b + 0.05 and r.vz < -1.0 and r.z <= ph.Z_TRIGGER:
            t_trig = r.t
            break
    T_roll = max(0.20, t_trig - t_b)
    if not quiet:
        print(f"  [两遍法] 熄火 {t_b:.3f} s，缓冲起 {t_trig:.3f} s"
              f"（z={ph.Z_TRIGGER} m）")
        print(f"           滚转窗 {T_roll:.3f} s，**落在缓冲之前**")
    recs = run_mission10(dt, n_turns=n_turns, roll_win=(t_b, T_roll),
                         ledger=ledger)
    # 记下探路得到的窗口，扫描脚本要报告"窗口本身是否随 dt 变"
    run_mission10_auto.t_burn = t_b           # type: ignore[attr-defined]
    run_mission10_auto.t_trig = t_trig        # type: ignore[attr-defined]
    run_mission10_auto.T_roll = T_roll        # type: ignore[attr-defined]
    return recs


def summarize10(recs: list[Rec10]) -> dict:
    if not recs:
        return {}
    last = recs[-1]
    active = {n: last["m_used"][n] if isinstance(last, dict) else
              last.m_used[n] for n in NAMES}
    return {
        "t_end": last.t,
        "z_max": max(r.z for r in recs),
        "vz_land": last.vz,
        "theta_end_deg": ph.wrap_deg(last.theta),
        "theta_total_deg": math.degrees(abs(last.theta)),
        "x_end": last.x,
        "p_end": last.p_mPa,
        "m_total": last.m_total,
        "per_nozzle": active,
    }


def main() -> int:
    print("=" * 90)
    print("  W55 · 10 个喷口完整状态")
    print("=" * 90)

    recs = run_mission10_auto(1 / 150)
    s = summarize10(recs)
    print(f"\n  时长 {s['t_end']:.2f} s，峰值 {s['z_max']:.2f} m，"
          f"落地 vz {s['vz_land']:+.2f} m/s，"
          f"姿态 {s['theta_end_deg']:+.0f}°（共转 "
          f"{s['theta_total_deg']:.0f}°）")
    print(f"  水平 {s['x_end']:.1f} m，罐压 {s['p_end']:.1f} MPa，"
          f"耗气 {s['m_total']:.1f} kg")

    print(f"\n  【每个喷口的累计出气量】")
    print(f"  {'#':>3}{'名称':<10}{'轴':>4}{'出气量(kg)':>12}"
          f"{'占耗气':>9}{'状态':>8}")
    tot = s["m_total"]
    for m in NOZZLE_META:
        v = s["per_nozzle"][m["name"]]
        pct = v / tot * 100 if tot > 0 else 0
        state = "工作" if v > 0.01 else "待机"
        print(f"  {m['i']:>3}{m['name']:<10}{m['axis']:>4}"
              f"{v:>12.2f}{pct:>8.1f}%{state:>8}")

    print("\n" + "=" * 90)
    print(f"  ★ 10 个喷口里 {sum(1 for m in NOZZLE_META if s['per_nozzle'][m['name']] > 0.01)} "
          f"个工作、{sum(1 for m in NOZZLE_META if s['per_nozzle'][m['name']] <= 0.01)} 个待机")
    print("=" * 90)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
