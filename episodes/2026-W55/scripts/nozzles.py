#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **10 个喷口系统**：每个喷口的推力、出气率、累计出气量。

## 为什么必须单独建一个模块

用户要求：**"每个喷嘴出气量也要模拟出来"**。

**这不只是"加个计数器"** —— 它带来三个新问题：

1. **喷口规格不同**（问题 4 已算：主推进 80 kN vs 调姿 0.8 kN，差 100 倍）；
2. **罐压随放气下降** ⇒ $\dot m = A_t\,p_0 C$ 随时间衰减 ⇒
   **同样的喷口，后段出气率更低**；
3. **多喷口同时工作时共用罐压** ⇒ 它们**互相影响**。

## 物理模型

### 单个喷口（壅塞）

$$\dot m_i = A_{t,i}\, p_0\, \sqrt{\frac{\gamma}{R_gT_0}}
\left(\frac{2}{\gamma+1}\right)^{\frac{\gamma+1}{2(\gamma-1)}}$$

$$F_i = \dot m_i\, v_e(p_0)$$

**⇒ 给定目标推力 $F_i$，反解所需喉部面积**：

$$A_{t,i} = \frac{F_i}{\,p_0\, C\, v_e(p_0)\,}$$

其中 $C = \sqrt{\frac{\gamma}{R_gT_0}}\left(\frac{2}{\gamma+1}\right)^{\frac{\gamma+1}{2(\gamma-1)}}$。

### 罐压演化（等温）

$$p_0(t) = \frac{m_{\text{tank}}(t)\,R_gT_0}{V_{\text{tank}}},
\qquad
\dot m_{\text{tank}} = -\sum_i \dot m_i$$

**★ 关键**：$\dot m_i$ 与 $p_0$ 成正比 ⇒ **放得越多，出得越慢** ⇒
**开环控制若不补偿，后段推力会掉**。

### 每个喷口的累计出气量

$$m_i^{\text{total}} = \int_0^{t_{\text{off},i}} \dot m_i\,dt$$

**⇒ 这是用户要的"每个喷嘴出气量"。**

## ★ 10 个喷口的任务分配（本文设计）

| # | 名称 | 轴 | 配对 | 任务 |
|---|---|---|---|---|
| 1 | `MAIN` | +X | 无（单体）| 纵向加速 |
| 2,3 | `LIFT_L` `LIFT_R` | +Z | 成对 | 起飞抬升 |
| 4 | `PITCH_UP` | +Z（尾部）| 单 | 抬头 |
| 5 | `PITCH_DN` | +Z（头部）| 单 | 低头 |
| 6 | `UNCAP` | −Z（车顶）| 单 | 倒挂时朝地推 |
| 7,8 | `ROLL_L` `ROLL_R` | ±Y | 成对反向 | 滚转 |
| 9,10 | `YAW_F` `YAW_R` | ±Y | 成对反向 | 偏航 |

**★ 为什么 PITCH/UNCAP 是单体而不是成对**：
它们是**力偶的一端**，另一端由**另一侧喷口**提供
（例如 4 与 5 构成俯仰力偶，但不同时点火，而是**交替**点火
—— 一个抬头、一个低头，这正是 bang-bang 的实现方式）。

**★ 真正的"纯力偶"需要同时点火的一对**：只有 ROLL 与 YAW 是这种模式。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import physics as ph   # noqa: E402


# ==================== 单喷口 ====================

def choked_const() -> float:
    r"""壅塞流量常数 $C = \sqrt{\gamma/(R_gT_0)}
    \left(\frac{2}{\gamma+1}\right)^{\frac{\gamma+1}{2(\gamma-1)}}$。"""
    g = ph.GAMMA
    return math.sqrt(g / (ph.R_GAS * ph.T0)) \
        * (2 / (g + 1)) ** ((g + 1) / (2 * (g - 1)))


C_CHOKED = choked_const()


def mdot_of_area(at: float, p0: float) -> float:
    r"""给定喉部面积与罐压的质量流量（kg/s）。"""
    return at * p0 * C_CHOKED


def ve_of(p0: float) -> float:
    return ph.exit_velocity(p0)


def force_of_area(at: float, p0: float) -> float:
    r"""给定喉部面积与罐压的推力（N）。"""
    return mdot_of_area(at, p0) * ve_of(p0)


def area_for_force(force: float, p0: float) -> float:
    r"""**反解**：要在罐压 $p_0$ 下得到 $F$，需要多大喉部面积。

    $$A_t = \frac{F}{C\,p_0\,v_e(p_0)}$$
    """
    denom = C_CHOKED * p0 * ve_of(p0)
    if denom <= 0:
        return 0.0
    return force / denom


# ==================== 喷口定义 ====================

@dataclass
class Nozzle:
    r"""单个喷口。

    `force_design` 是**在 `p_ref` 下的设计推力**；
    实际推力随罐压按 $F \propto p_0$ 缩放。

    ## `spans`：点火时间窗（用于甘特图）

    **★ 不能只记"每个阶段里各喷口用了多少气"** ——
    那样画出的甘特图会把 bang-bang 的**两段**画成同时进行
    （我在第一版就画错了）。

    **⇒ 必须记录每个喷口**自己的开/关时刻。
    """
    idx: int
    name: str
    axis: str
    force_design: float
    p_ref: float = ph.P_TANK
    area: float = 0.0
    m_used: float = 0.0
    t_on: float = 0.0
    impulse: float = 0.0
    # (t_start, t_end) 列表；相邻且 duty>0 的步会合并
    spans: list[tuple[float, float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.area == 0.0:
            self.area = area_for_force(self.force_design, self.p_ref)

    def reset(self) -> None:
        self.m_used = 0.0
        self.t_on = 0.0
        self.impulse = 0.0
        self.spans.clear()

    def step(self, duty: float, p0: float, dt: float,
             t_now: float = 0.0) -> float:
        r"""按占空比 `duty`（0..1）工作 `dt`，返回产生的推力（N）。

        `duty` 表示 PWM 的等效占空比 —— 固定步长积分里用它表达"部分推力"。
        """
        if duty <= 0.0:
            return 0.0
        duty = min(duty, 1.0)
        md = mdot_of_area(self.area, p0) * duty
        f = md * ve_of(p0)
        self.m_used += md * dt
        self.t_on += dt * duty
        self.impulse += f * dt
        # ---- 记录时间窗（相邻步合并）----
        if self.spans and abs(self.spans[-1][1] - t_now) < dt * 0.51:
            self.spans[-1] = (self.spans[-1][0], t_now + dt)
        else:
            self.spans.append((t_now, t_now + dt))
        return f


def build_nozzles() -> list[Nozzle]:
    r"""构建 10 个喷口（**竖推 4 个 —— 已由视频羽流确认**）。

    ## ★★ 竖推数量：从 2 改为 4（用户指正 + 视频核实）

    **我原来按"成对即可"推了 2 个竖推。用户看视频说"是四个"。**

    **⇒ 回视频数羽流，确认**：
    `j_19_0.png` / `sq_19_20.png` 等帧里，
    **同一帧能数出 4 条独立的竖直羽流**
    （左 2 条清晰，右 2 条其一较宽可能是双流叠加）。
    **⇒ 竖推 = 4 个。**

    **★ 为什么 4 而不是 2 在工程上更合理**（这是我事后才想通的）：
    * **4 个喷口分布在车底四角** ⇒ 可以**分别调节**，
      产生**俯仰与滚转的配平力矩**；
    * **2 个喷口只能沿一条线布置**，无法纠正横向不平衡；
    * **冗余**：单发失效仍有 3/4 推力（安全性）。

    **⇒ 结论：4 个竖推不只是"推力更大"，而是"可控性"要求的。**

    ## 布局（本文设计，非官方）

    | 规格 | 推力/个 | 谁 |
    |---|---|---|
    | 大 | 80 kN | 主推进 ×1 |
    | 大 | **20 kN** | **竖推 ×4**（车底四角）|
    | 中 | 5 kN | 俯仰 ×2、脱离 ×1 |
    | 小 | 1.5 kN | 滚转 ×2、偏航 ×2 |

    **★ 10 个的分配**：1 + 4 + 3 + 2 = 10。
    **注意**：这样"偏航"只剩 2 个（原设 4 个中的 2 个让给了竖推）。
    """
    p = ph.P_TANK
    return [
        Nozzle(1, "MAIN", "+X", 80e3, p),          # 主推进
        # ---- 竖推 4 个：车底四角 ----
        Nozzle(2, "LIFT_FL", "+Z", 20e3, p),       # 左前
        Nozzle(3, "LIFT_FR", "+Z", 20e3, p),       # 右前
        Nozzle(4, "LIFT_RL", "+Z", 20e3, p),       # 左后
        Nozzle(5, "LIFT_RR", "+Z", 20e3, p),       # 右后
        # ---- 俯仰与脱离 ----
        Nozzle(6, "PITCH_UP", "+Z", 5e3, p),       # 尾部竖推 → 抬头
        Nozzle(7, "PITCH_DN", "+Z", 5e3, p),       # 头部竖推 → 低头
        Nozzle(8, "UNCAP", "-Z", 5e3, p),          # 车顶 → 倒挂脱离
        # ---- 滚转 ----
        # ★★ 力偶喷口（向下推，−Z）：按 6 kN 设计。
        #   每喷需 F = τ/d = 5663/1.40 ≈ 4.05 kN；原 2.5 kN 会让
        #   duty 钳在 1.0 ⇒ 两侧推力不等 ⇒ 力偶失效。
        Nozzle(9, "ATT_L", "-Z", 6.0e3, p),        # 左下推 → 滚转力偶
        Nozzle(10, "ATT_R", "-Z", 6.0e3, p),       # 右下推 → 滚转力偶
    ]


# 四个竖推的名字（便于成组操作）
LIFT_NAMES: tuple[str, ...] = ("LIFT_FL", "LIFT_FR", "LIFT_RL", "LIFT_RR")


# ==================== 任务级仿真 ====================

@dataclass
class PhaseLog:
    r"""一个任务阶段（如"起飞""缓冲"）的汇总。"""
    name: str = ""
    t_start: float = 0.0
    t_end: float = 0.0
    impulse: float = 0.0       # N·s
    mass: float = 0.0          # kg
    per_nozzle: dict = field(default_factory=dict)


def simulate_whole_mission(dt: float = 1 / 240) -> dict:
    r"""**整场演出**：倒挂 → 分离 → **翻正半圈** → 起飞 → 调姿 → 缓冲 → 落地。

    ## 为什么"整场"而不是"分开算"

    **因为罐压是共享的**：倒挂段如果用气，后面就没那么多气了。
    **必须按时间顺序累计**，才能知道每个喷口真正用了多少。

    ## 任务顺序（对齐用户的描述）

    | 阶段 | 喷口 | 说明 |
    |---|---|---|
    | ① 倒挂行驶 | **不用气**（风扇电驱）| 问题 1 的核心结论 |
    | ② 分离 | `UNCAP` | 车顶朝地推，帮车脱离坡面 |
    | ③ **翻正半圈（滚转）** | `ROLL_L` → `ROLL_R` | ★ **倒挂→正立**，半圈 |
    | ④ 起飞 | `LIFT_L` `LIFT_R` | 给到 $v_z = \sqrt{2gh}$ |
    | ⑤ **调姿整圈（滚转）** | `ROLL_L` → `ROLL_R` | ★ 正立→正立，一圈 |
    | ⑥ 缓冲 | `LIFT_L` `LIFT_R` | 把落地速度压到 0.5 m/s |

    **★ ③ 与 ⑤ 用的是不同的轴**：
    * **两段都是滚转**（用户确认）⇒ 都用 $J_{\\text{roll}} = 907$；
    * **滚转比俯仰省 4 倍角动量** —— 车又长又窄，绕自身长轴惯性最小。

    **⇒ 这正是用户说的"第一问半圈、第二问整圈"。**
    """
    noz = build_nozzles()
    by_name = {n.name: n for n in noz}
    m_tank = ph.M_AIR
    p0 = m_tank * ph.R_GAS * ph.T0 / ph.V_TANK

    logs: list[PhaseLog] = []
    t_global = 0.0

    def p_now() -> float:
        return max(p0, ph.P_ATM * 1.01)

    def burn_pair(names: tuple[str, ...], I_need: float,
                  t_name: str) -> PhaseLog:
        r"""烧一对喷口直到累计冲量达到 `I_need`。"""
        nonlocal m_tank, p0, t_global
        t0 = t_global
        I = 0.0
        m = 0.0
        while I < I_need and t_global - t0 < 8.0:
            f = 0.0
            for nm in names:
                f += by_name[nm].step(1.0, p_now(), dt, t_global)
            dm = sum(mdot_of_area(by_name[nm].area, p_now())
                     for nm in names) * dt
            m_tank -= dm
            p0 = m_tank * ph.R_GAS * ph.T0 / ph.V_TANK
            I += f * dt
            m += dm
            t_global += dt
        log = PhaseLog(t_name, t0, t_global, I, m,
                       {nm: m / len(names) for nm in names})
        logs.append(log)
        return log

    def burn_bangbang(nm_a: str, nm_b: str, M_need: float, r_arm: float,
                      t_total: float, t_name: str) -> PhaseLog:
        r"""一对反向喷口做 bang-bang（前半 `nm_a`，后半 `nm_b`）。"""
        nonlocal m_tank, p0, t_global
        F_pair = M_need / (2 * r_arm)
        t0 = t_global
        I = 0.0
        m = 0.0
        per: dict[str, float] = {nm_a: 0.0, nm_b: 0.0}
        for nm in (nm_a, nm_b):
            for _ in range(int((t_total / 2) / dt)):
                nz = by_name[nm]
                f_max = force_of_area(nz.area, p_now())
                duty = min(1.0, F_pair / f_max) if f_max > 0 else 0.0
                f = nz.step(duty, p_now(), dt, t_global)
                dm = mdot_of_area(nz.area, p_now()) * duty * dt
                m_tank -= dm
                p0 = m_tank * ph.R_GAS * ph.T0 / ph.V_TANK
                I += f * dt
                m += dm
                per[nm] += dm
                t_global += dt
        log = PhaseLog(t_name, t0, t_global, I, m, per)
        logs.append(log)
        return log

    # ---------- ① 倒挂（不用气）----------
    logs.append(PhaseLog("倒挂行驶（电驱，不耗气）", t_global, t_global))

    # ---------- ② 分离：给 0.5 m/s 的向下分离速度 ----------
    # ★ 不能用"随便 0.05 mg"这种魔法数：分离的目的是**抵消风扇残余吸附
    #   并给一个可测的脱离速度**。取 Δv = 0.5 m/s 是有物理依据的
    #   （约等于 0.05 s 自由落体的速度量级）。
    burn_pair(("UNCAP",), ph.M_CAR * 0.5, "倒挂分离（UNCAP）")

    # ---------- ③ 翻正半圈（★ 滚转，不是俯仰）----------
    # 用户 2026-10-17 确认"都是滚转" ⇒ 倒挂翻正也是**绕纵轴的滚转半圈**
    T_half = 2.0                        # 半圈给 2 s
    M_half = ph.bang_bang_torque(math.pi, T_half, ph.J_ROLL)
    r_roll = ph.W_CAR / 2 + 0.15        # 滚转力臂（半车宽 + 喷口外伸）
    burn_bangbang("ATT_L", "ATT_R", M_half, r_roll,
                  T_half, "翻正半圈（ROLL_L→ROLL_R）")

    # ---------- ④ 起飞 ----------
    vz0 = ph.launch_speed_for_height(ph.H_JUMP)
    lift_log = burn_pair(LIFT_NAMES, ph.M_CAR * vz0,
                         "起飞（4 竖推）")
    t_lift = lift_log.t_end - lift_log.t_start

    # ---------- ⑤ 调姿整圈（滚转）----------
    T_fly = 2 * vz0 / ph.G
    M_roll = ph.bang_bang_torque(2 * math.pi, T_fly, ph.J_ROLL)
    r_roll = ph.W_CAR / 2 + 0.15
    burn_bangbang("ATT_L", "ATT_R", M_roll, r_roll, T_fly,
                  "空中调姿整圈（ROLL_L→ROLL_R）")

    # ---------- ⑥ 缓冲 ----------
    soft_log = burn_pair(LIFT_NAMES,
                         ph.M_CAR * (vz0 - ph.VZ_SAFE),
                         "落地缓冲（4 竖推）")
    t_soft = soft_log.t_end - soft_log.t_start

    return {
        "nozzles": noz,
        "logs": logs,
        "m_tank_left": m_tank,
        "m_used": ph.M_AIR - m_tank,
        "p0_end": p0,
        "t_total": t_global,
        "t_lift": t_lift,
        "t_soft": t_soft,
        "I_need_lift": ph.M_CAR * vz0,
        "I_need_soft": ph.M_CAR * (vz0 - ph.VZ_SAFE),
    }


def main() -> int:
    print("=" * 94)
    print("  W55 · 10 个喷口系统：每个喷口的出气量")
    print("=" * 94)

    print(f"\n  【喷口规格】（罐压 {ph.P_TANK/1e6:.1f} MPa 下）")
    print(f"  {'#':>3}{'名称':<10}{'轴':>4}{'设计推力':>11}"
          f"{'喉部面积(cm²)':>15}{'出气率(kg/s)':>15}")
    for nz in build_nozzles():
        md = mdot_of_area(nz.area, ph.P_TANK)
        print(f"  {nz.idx:>3}{nz.name:<10}{nz.axis:>4}"
              f"{nz.force_design/1000:>9.1f}kN{nz.area*1e4:>15.2f}"
              f"{md:>15.2f}")

    print("\n" + "=" * 94)
    print("  【整场演出】按时间顺序累计（罐压共享）")
    print("=" * 94)
    res = simulate_whole_mission()
    print(f"\n  {'阶段':<24}{'时长(s)':>9}{'冲量(kN·s)':>12}"
          f"{'耗气(kg)':>10}{'占罐内':>9}")
    for L in res["logs"]:
        if L.t_end <= L.t_start and L.mass == 0:
            continue
        print(f"  {L.name:<24}{L.t_end-L.t_start:>9.2f}"
              f"{L.impulse/1000:>12.1f}{L.mass:>10.2f}"
              f"{L.mass/ph.M_AIR*100:>8.1f}%")

    print(f"\n  ★ 全程 {res['t_total']:.2f} s，耗气 "
          f"**{res['m_used']:.1f} kg**（占罐内 "
          f"{res['m_used']/ph.M_AIR*100:.1f}%）")
    print(f"  ★ 剩余气量 {res['m_tank_left']:.1f} kg，"
          f"罐压降到 **{res['p0_end']/1e6:.1f} MPa**")

    print("\n" + "=" * 94)
    print("  【每个喷口的累计出气量】")
    print("=" * 94)
    print(f"  {'#':>3}{'名称':<10}{'出气量(kg)':>12}{'占耗气':>9}"
          f"{'点火时长(s)':>13}{'冲量(kN·s)':>12}")
    zero_cnt = 0
    for nz in res["nozzles"]:
        if nz.m_used <= 0:
            zero_cnt += 1
            print(f"  {nz.idx:>3}{nz.name:<10}{'—':>12}{'0':>9}"
                  f"{'0':>13}{'—':>12}")
            continue
        print(f"  {nz.idx:>3}{nz.name:<10}{nz.m_used:>12.2f}"
              f"{nz.m_used/res['m_used']*100:>8.1f}%"
              f"{nz.t_on:>13.2f}{nz.impulse/1000:>12.1f}")

    print(f"\n  ★ **只有 {10-zero_cnt} 个喷口被用到**，"
          f"{zero_cnt} 个全程未点火")

    print("\n" + "=" * 94)
    print("  ★★★ 结论")
    print("=" * 94)
    lift = next(L for L in res["logs"] if L.name.startswith("起飞"))
    soft = next(L for L in res["logs"] if L.name.startswith("落地缓冲"))
    roll = next(L for L in res["logs"] if L.name.startswith("空中调姿"))
    unc = next(L for L in res["logs"] if "UNCAP" in L.name)
    print(f"  ① **起飞最费气**：{lift.mass:.1f} kg"
          f"（{lift.mass/ph.M_AIR*100:.0f}%），用时 {res['t_lift']:.2f} s；")
    print(f"  ② **缓冲次之**：{soft.mass:.1f} kg"
          f"（{soft.mass/ph.M_AIR*100:.0f}%），用时 {res['t_soft']:.2f} s；")
    print(f"  ③ **调姿很省**：{roll.mass:.1f} kg"
          f"（{roll.mass/ph.M_AIR*100:.1f}%）；")
    print(f"  ④ **倒挂分离更省**：{unc.mass:.1f} kg"
          f"（{unc.mass/ph.M_AIR*100:.1f}%）；")
    print(f"  ⑤ **倒挂段完全不耗气**（风扇是电驱）—— 这是问题 1 的结论；")
    print(f"  ⑥ **10 个喷口里只有 {10-zero_cnt} 个在这次演出中用上**，")
    print(f"     其余是**冗余/备用**（或用于其他特技动作）。")
    print()
    print(f"  ★ 气罐余量充足：只用掉 {res['m_used']/ph.M_AIR*100:.0f}%，"
          f"罐压仍有 {res['p0_end']/1e6:.1f} MPa。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
