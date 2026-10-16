#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W47 · 问题 1（续）：双通道**均衡分配**。

## 一、为什么必须用"全走廊"长度，而不是只看跨江段

第一版我只用跨江段算自由流时间，得到荒谬结果：
* 大桥 **1.54 min**（3.071 km @ 120）
* 隧道 **8.87 min**（11.825 km @ 80）
⇒ 隧道慢 7.33 min ⇒ 均衡会给出**隧道流量为 0**，与观测的 22% 矛盾。

**根因**：跨江段**长度口径不可比**。
隧道那 11.825 km 是**含两岸接线**的全长；大桥那 3.071 km 只是**桥体**。
拿"桥体"比"隧道+接线"必然荒谬。

**修法**：用**全走廊长度**
* 大桥路径 = 北接线 21 + 桥 3.071 + 南接线 30.4 ≈ **54.5 km** @ 120 km/h
* 隧道路径 = **24.8 km** @ 80 km/h

（接线长度取自公开路网资料，精度有限 ⇒ **必须做敏感性**。）

## 二、模型

$$
c_k(q) \;=\; t_k^{0}\Big[1+\alpha\big(\tfrac{q_k}{C_k}\big)^{\beta}\Big]
\;+\;\frac{p_k}{\text{VOT}}
$$

* 客车在两条路径间选择 ⇒ **用户均衡**（UE）：$c_B = c_T$；
* **货车只能走大桥**（隧道全时段禁货）⇒ 固定负载 $Q^{\text{truck}}$；
* 货车按 **PCE = 2.5** 折算（重型车折算系数，见《公路工程技术标准》）。

$$
q_B^{\text{pcu}} = q_B^{\text{car}} + 2.5\,Q^{\text{truck}},
\qquad q_T^{\text{pcu}} = q_T^{\text{car}}
$$

用法：
    $PY q1_equilibrium.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

sys.path.insert(0, str(Path(__file__).resolve().parent))
from w47_data import BRIDGE, OPENING                            # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
RES.mkdir(parents=True, exist_ok=True)

BPR_A, BPR_B = 0.15, 4.0
PCE_TRUCK = 2.5          # 货车折算系数（重型车，JTG B01-2014 常用值）
VOT_YUAN_PER_H = 30.0    # 时间价值（自驾，元/小时）—— 敏感性中扫描

# 全走廊长度（km）与设计速度
CORRIDOR = {
    "大桥": {"L_km": 21.0 + 3.071 + 30.4, "v_kmh": 120, "cap_pcu_h": 4950,
             "toll": 25.0, "truck_ok": True},
    "隧道": {"L_km": 24.8, "v_kmh": 80, "cap_pcu_h": 4500,
             "toll": 25.0, "truck_ok": False},
}
for k, v in CORRIDOR.items():
    v["t0_min"] = v["L_km"] / v["v_kmh"] * 60.0


def cost(k: str, q_pcu_h: float, vot: float = VOT_YUAN_PER_H) -> float:
    r"""广义成本 [分钟]：走行时间 + 收费折算时间。"""
    p = CORRIDOR[k]
    x = max(q_pcu_h, 0.0) / p["cap_pcu_h"]
    t = p["t0_min"] * (1 + BPR_A * x ** BPR_B)
    return t + p["toll"] / vot * 60.0


def equilibrium(total_car_pcu_h: float, truck_pcu_h: float,
                vot: float = VOT_YUAN_PER_H) -> dict:
    r"""求客车在两条路径间的用户均衡。

    货车固定在大桥 ⇒ 大桥的"底载"为 truck_pcu_h。
    """
    def gap(qT: float) -> float:
        qB = total_car_pcu_h - qT
        return cost("隧道", qT, vot) - cost("大桥", qB + truck_pcu_h, vot)

    # 边界检查
    if gap(0.0) >= 0:
        return {"qT": 0.0, "qB": total_car_pcu_h, "boundary": "隧道为 0"}
    if gap(total_car_pcu_h) <= 0:
        return {"qT": total_car_pcu_h, "qB": 0.0, "boundary": "大桥客车为 0"}
    qT = brentq(gap, 0.0, total_car_pcu_h, xtol=1e-6)
    return {"qT": qT, "qB": total_car_pcu_h - qT, "boundary": None}


def system_opt(total_car_pcu_h: float, truck_pcu_h: float,
               vot: float = VOT_YUAN_PER_H) -> dict:
    r"""系统最优：最小化**总走行时间**（分钟·辆）。"""
    def total(qT: float) -> float:
        qB = total_car_pcu_h - qT
        return (qT * cost("隧道", qT, vot)
                + qB * cost("大桥", qB + truck_pcu_h, vot))
    grid = np.linspace(0, total_car_pcu_h, 20001)
    vals = np.array([total(x) for x in grid])
    i = int(np.argmin(vals))
    return {"qT": float(grid[i]), "qB": float(total_car_pcu_h - grid[i]),
            "total_min": float(vals[i])}


def main() -> int:
    print("=" * 96)
    print("  W47 · 问题 1（续）：双通道均衡分配")
    print("=" * 96)

    print("\n  ── 全走廊参数（**注意：用全长，不用跨江段**）──")
    print(f"     {'路径':<8}{'全长(km)':>10}{'设计速度':>10}{'t0(min)':>10}"
          f"{'能力(pcu/h)':>13}{'收费(元)':>10}{'货车':>10}")
    for k, p in CORRIDOR.items():
        print(f"     {k:<8}{p['L_km']:>10.2f}{p['v_kmh']:>10}"
              f"{p['t0_min']:>10.2f}{p['cap_pcu_h']:>13,}{p['toll']:>10.0f}"
              f"{('可通行' if p['truck_ok'] else '禁行'):>10}")
    dt0 = CORRIDOR["隧道"]["t0_min"] - CORRIDOR["大桥"]["t0_min"]
    print(f"\n     ★ 自由流时间差：隧道 − 大桥 = {dt0:+.2f} min"
          f"（**隧道在自由流下快 {abs(dt0):.2f} min**）")
    print("       这与『只看跨江段』的结论**相反** —— 说明长度口径是决定性的。")

    # ── 用日间观测构造高峰小时需求 ──
    print(f"\n{'='*96}")
    print("  ── 需求构造（由日观测折算到高峰小时）──")
    qh = OPENING["最高小时_南向北"]
    print(f"     通道单向高峰小时 = {qh:,} 辆/h（口径：通道合计，见 q1_network.py）")
    share_T = OPENING["隧道高峰占比"]
    # 由官方"隧道承担约三成"给客车分流率的先验
    phi = float(np.mean([d["货车"] / d["合计"] for d in BRIDGE.values()]))
    print(f"     货车占比 φ = {phi:.2%}（实测均值）")
    # 通道总需求中货车按 φ 占比
    Q_truck_h = qh * phi
    Q_car_h = qh * (1 - phi)
    truck_pcu = Q_truck_h * PCE_TRUCK
    print(f"     按 φ 拆分：货车 {Q_truck_h:,.0f} 辆/h、客车 {Q_car_h:,.0f} 辆/h")
    print(f"     货车折算 {PCE_TRUCK} PCE ⇒ {truck_pcu:,.0f} pcu/h（**全部压在大桥**）")

    # ── 均衡与最优 ──
    print(f"\n{'='*96}")
    print("  ★ 用户均衡（UE）vs 系统最优（SO）vs 观测")
    eq = equilibrium(Q_car_h, truck_pcu)
    so = system_opt(Q_car_h, truck_pcu)
    qT_obs = qh * share_T
    qB_obs = qh * (1 - share_T)

    def line(lab, qT, qB):
        qBp = qB + truck_pcu
        sT, sB = qT / CORRIDOR["隧道"]["cap_pcu_h"], qBp / CORRIDOR["大桥"]["cap_pcu_h"]
        cT, cB = cost("隧道", qT), cost("大桥", qBp)
        return (f"     {lab:<16}{qT:>9,.0f}{qB:>9,.0f}"
                f"{qT/(qT+qB):>10.1%}{sT:>10.3f}{sB:>10.3f}"
                f"{cT:>10.2f}{cB:>10.2f}")

    print(f"     {'方案':<16}{'客车隧':>9}{'客车桥':>9}{'隧道占比':>10}"
          f"{'隧道饱和':>10}{'大桥饱和':>10}{'c隧(min)':>10}{'c桥(min)':>10}")
    print("     " + "-" * 94)
    print(line("用户均衡 UE", eq["qT"], eq["qB"]))
    print(line("系统最优 SO", so["qT"], so["qB"]))
    print(line("观测（高峰）", qT_obs, qB_obs))
    if eq["boundary"]:
        print(f"     [!] UE 落在边界：{eq['boundary']}")

    # ── 效率对比 ──
    print(f"\n  ── 效率对比（总走行时间，分钟·辆/h）──")
    def sys_time(qT, qB):
        return qT * cost("隧道", qT) + qB * cost("大桥", qB + truck_pcu)
    t_so = sys_time(so["qT"], so["qB"])
    t_eq = sys_time(eq["qT"], eq["qB"])
    t_obs = sys_time(qT_obs, qB_obs)
    print(f"     系统最优 SO ：{t_so:>12,.0f}")
    print(f"     用户均衡 UE ：{t_eq:>12,.0f}   相对 SO +{(t_eq/t_so-1):.2%}")
    print(f"     观测（高峰）：{t_obs:>12,.0f}   相对 SO +{(t_obs/t_so-1):.2%}")
    print(f"     ⇒ 观测分配相对系统最优的效率损失 **{(t_obs/t_so-1):.2%}**")

    # ── 敏感性：VOT 与接线长度 ──
    print(f"\n{'='*96}")
    print("  ── 敏感性 ──")
    print(f"     {'VOT(元/h)':>10}{'UE隧道占比':>12}{'UE隧道饱和':>12}")
    for vot in (10, 20, 30, 50, 80):
        e = equilibrium(Q_car_h, truck_pcu, vot)
        print(f"     {vot:>10}{e['qT']/(e['qT']+e['qB']):>12.1%}"
              f"{e['qT']/CORRIDOR['隧道']['cap_pcu_h']:>12.3f}")

    print(f"\n     {'接线扰动':<20}{'t0桥':>9}{'t0隧':>9}{'UE隧道占比':>12}")
    for lab, f in (("现状", 1.0), ("桥接线 +30%", 1.3), ("桥接线 −30%", 0.7)):
        t0 = CORRIDOR["大桥"]["t0_min"]
        CORRIDOR["大桥"]["t0_min"] = t0 * f
        e = equilibrium(Q_car_h, truck_pcu)
        print(f"     {lab:<20}{CORRIDOR['大桥']['t0_min']:>9.2f}"
              f"{CORRIDOR['隧道']['t0_min']:>9.2f}"
              f"{e['qT']/(e['qT']+e['qB']):>12.1%}")
        CORRIDOR["大桥"]["t0_min"] = t0

    out = {
        "走廊参数": {k: v for k, v in CORRIDOR.items()},
        "PCE_货车": PCE_TRUCK, "VOT_元每小时": VOT_YUAN_PER_H,
        "BPR": {"alpha": BPR_A, "beta": BPR_B},
        "需求_高峰小时": {"通道合计": qh, "货车": round(Q_truck_h, 0),
                          "客车": round(Q_car_h, 0),
                          "货车_pcu": round(truck_pcu, 0)},
        "结果": {
            "UE": {"客车隧道": round(eq["qT"], 0), "客车大桥": round(eq["qB"], 0),
                   "隧道占比": round(eq["qT"] / (eq["qT"] + eq["qB"]), 4),
                   "边界": eq["boundary"], "总时间": round(t_eq, 0)},
            "SO": {"客车隧道": round(so["qT"], 0), "客车大桥": round(so["qB"], 0),
                   "隧道占比": round(so["qT"] / (so["qT"] + so["qB"]), 4),
                   "总时间": round(t_so, 0)},
            "观测": {"客车隧道": round(qT_obs, 0), "客车大桥": round(qB_obs, 0),
                     "隧道占比": round(qT_obs / (qT_obs + qB_obs), 4),
                     "总时间": round(t_obs, 0)},
            "效率损失": {"UE_vs_SO": round(t_eq / t_so - 1, 4),
                         "观测_vs_SO": round(t_obs / t_so - 1, 4)},
        },
        "_口径说明": ("用**全走廊长度**（大桥 54.5 km / 隧道 24.8 km），"
                      "不用跨江段 —— 因为隧道长度含接线而大桥长度只是桥体，"
                      "直接比较会得出『隧道慢 7.33 min ⇒ 均衡流量为 0』的荒谬结论。"),
        "_假设": ["接线长度取自公开资料，精度有限 ⇒ 已做 ±30% 敏感性",
                  "货车 PCE = 2.5", f"VOT = {VOT_YUAN_PER_H} 元/h（已扫描）",
                  "桥隧收费相同（均 25 元）⇒ 收费项在成本差中抵消"],
    }
    p = RES / "q1_均衡.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=float),
                 encoding="utf-8")
    print(f"\n  -> {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
