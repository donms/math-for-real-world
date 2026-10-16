#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W47 · 问题 4：分配效率评价与差别定价。

## 一、可用的求解器（复用第 1 问，已通过 `SO <= UE` 自检）

* **UE**：$\min_{q_T} Z=\int_0^{q_T}\!c_T+\int_0^{q_B}\!c_B$
  （一阶条件 $c_T=c_B$）
* **SO**：$\min_{q_T} q_Tc_T(q_T)+q_Bc_B(q_B)$（一阶条件：**边际**成本相等）

## 二、约束（本题与教科书双路径问题的根本不同）

1. **货车只能走大桥**（隧道全时段禁货）⇒ 固定负载 $Q^{\text{truck}}\cdot$PCE；
2. **桥隧小型客车同价（均 25 元）** ⇒ 收费在成本差中**抵消**
   ⇒ 观测分配**完全由时间驱动**。

## 三、效率度量

### 3.1 效率损失（总走行时间）
$$
\text{损失} = \frac{T_{\text{obs}}}{T_{\text{SO}}} - 1
$$

### 3.2 相对熵（分配"有多散"）
$$
D(\mathbf{q}\,\|\,\mathbf{p}) = \sum_k q_k \ln\frac{q_k}{p_k},
\qquad p_k = \frac{C_k}{\sum_j C_j}
$$
即"观测分配"相对"按能力比例分配"的偏离。

### 3.3 ★ 但要注意：**SO 与 UE 的相对位置在本案例中是反的**

教科书里 $q_T^{\text{SO}} < q_T^{\text{UE}}$（最优会让车辆**更多**走慢路）。
本案例**相反** —— 因为**货车把大桥堵住了**，
所以最优反而让**更多客车去隧道**。
⇒ **这是一个由"禁货"政策直接导致的结果**，必须讲清楚。

## 四、差别定价

允许桥隧收不同的费（$p_T, p_B$），问最优价差。

**但第 1 问已暴露一个硬伤**：观测分配**不是均衡**
（$c_{\text{桥}}-c_{\text{隧}}=+43$ min 却不转移）⇒
**在这个模型里"调价格"无法解释观测**，
只能回答**"若需求对价格为弹性、且路径成本可感知，最优价差是多少"**。
**这一限制必须写进结论。**

用法：
    $PY q4_pricing.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from w47_data import BRIDGE, OPENING, SHOCKS                    # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
RES.mkdir(parents=True, exist_ok=True)

BPR_A, BPR_B = 0.15, 4.0
PCE_TRUCK = 2.5
VOT = 30.0                      # 元/小时

CORRIDOR = {
    "大桥": {"L_km": 21.0 + 3.071 + 30.4, "v": 120, "cap": 4950},
    "隧道": {"L_km": 24.8, "v": 80, "cap": 4500},
}
for _p in CORRIDOR.values():
    _p["t0"] = _p["L_km"] / _p["v"] * 60.0


def c(k: str, q: float, toll: float = 25.0, vot: float = VOT) -> float:
    r"""广义成本 [分钟] = 走行时间 + 收费折算时间。"""
    p = CORRIDOR[k]
    return (p["t0"] * (1 + BPR_A * (max(q, 0.0) / p["cap"]) ** BPR_B)
            + toll / vot * 60.0)


def Cint(k: str, q: float, toll: float = 25.0, vot: float = VOT) -> float:
    r"""$\int_0^q c(w)\,dw$（UE 目标函数）。"""
    p = CORRIDOR[k]
    return (p["t0"] * (q + BPR_A * q ** (BPR_B + 1)
                       / ((BPR_B + 1) * p["cap"] ** BPR_B))
            + toll / vot * 60.0 * q)


def _ternary(f, lo: float, hi: float, iters: int = 300) -> float:
    for _ in range(iters):
        m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
        if f(m1) < f(m2):
            hi = m2
        else:
            lo = m1
    return (lo + hi) / 2


def solve(q_car: float, q_truck_pcu: float, toll_T: float = 25.0,
          toll_B: float = 25.0, vot: float = VOT) -> dict:
    r"""给定收费，求 UE 与 SO，并返回系统总时间。"""
    tk = q_truck_pcu

    def tot(qT: float) -> float:
        qB = q_car - qT
        return (qT * c("隧道", qT, toll_T, vot)
                + qB * c("大桥", qB + tk, toll_B, vot))

    def z_ue(qT: float) -> float:
        qB = q_car - qT
        return Cint("隧道", qT, toll_T, vot) + Cint("大桥", qB + tk, toll_B, vot)

    qT_ue = _ternary(z_ue, 0.0, q_car)
    qT_so = _ternary(tot, 0.0, q_car)
    t_ue, t_so = tot(qT_ue), tot(qT_so)
    return {"qT_ue": qT_ue, "qB_ue": q_car - qT_ue, "t_ue": t_ue,
            "qT_so": qT_so, "qB_so": q_car - qT_so, "t_so": t_so,
            "selfcheck": bool(t_so <= t_ue + 1e-6)}


def rel_entropy(qT: float, qB: float, tk: float) -> float:
    r"""相对熵 $D(\mathbf q\|\mathbf p)$，$\mathbf p$ 按能力比例。"""
    capT, capB = CORRIDOR["隧道"]["cap"], CORRIDOR["大桥"]["cap"]
    tot_cap = capT + capB
    pT, pB = capT / tot_cap, capB / tot_cap
    q_tot = qT + qB
    if q_tot <= 0:
        return 0.0
    aT, aB = qT / q_tot, qB / q_tot
    out = 0.0
    for a, pr in ((aT, pT), (aB, pB)):
        if a > 0:
            out += a * np.log(a / pr)
    return float(out)


def main() -> int:
    print("=" * 100)
    print("  W47 · 问题 4：分配效率评价与差别定价")
    print("=" * 100)

    qh = OPENING["最高小时_南向北"]
    phi = float(np.mean([d["货车"] / d["合计"] for d in BRIDGE.values()]))
    q_truck_h = qh * phi
    q_car_h = qh - q_truck_h
    tk = q_truck_h * PCE_TRUCK
    share_T = OPENING["隧道高峰占比"]
    print(f"\n  需求：通道单向高峰 {qh:,} 辆/h；货车占比 {phi:.2%}"
          f" ⇒ 货车 {q_truck_h:,.0f} 辆/h（{tk:,.0f} pcu/h，全部压大桥）、"
          f"客车 {q_car_h:,.0f} 辆/h")
    print(f"  约束：① 货车只能走大桥　② 桥隧小型客车同价（均 25 元）")

    # ── 基准解 ──
    r = solve(q_car_h, tk)
    qT_obs = qh * share_T
    qB_obs_car = qh * (1 - share_T) - q_truck_h

    def row(lab, qT, qB):
        qBp = qB + tk
        cT, cB = c("隧道", qT), c("大桥", qBp)
        tot = qT * cT + qB * cB
        return {"标签": lab, "客车隧": qT, "客车桥": qB,
                "隧道占比": qT / (qT + qB) if (qT + qB) else 0,
                "隧饱和": qT / CORRIDOR["隧道"]["cap"],
                "桥饱和": qBp / CORRIDOR["大桥"]["cap"],
                "c隧": cT, "c桥": cB, "总时间": tot,
                "熵": rel_entropy(qT, qB, tk)}

    rows = [row("UE（用户均衡）", r["qT_ue"], r["qB_ue"]),
            row("SO（系统最优）", r["qT_so"], r["qB_so"]),
            row("观测（高峰）", qT_obs, max(qB_obs_car, 0.0))]
    print(f"\n{'='*100}")
    print("  ── ① 三方对比 ──")
    print(f"     {'方案':<18}{'客车隧':>9}{'客车桥':>9}{'隧道占比':>10}"
          f"{'隧饱和':>9}{'桥饱和':>9}{'总时间':>12}{'相对熵':>10}")
    print("     " + "-" * 96)
    for x in rows:
        print(f"     {x['标签']:<18}{x['客车隧']:>9,.0f}{x['客车桥']:>9,.0f}"
              f"{x['隧道占比']:>10.1%}{x['隧饱和']:>9.3f}{x['桥饱和']:>9.3f}"
              f"{x['总时间']:>12,.0f}{x['熵']:>10.4f}")

    t_so = rows[1]["总时间"]
    print(f"\n     自检 SO <= UE：{r['selfcheck']}")
    print(f"     效率损失（相对 SO）："
          f"UE {(rows[0]['总时间']/t_so-1):+.2%}   "
          f"观测 {(rows[2]['总时间']/t_so-1):+.2%}")

    # ── ② 本案例中 SO 与 UE 的相对位置是"反的" ──
    print(f"\n{'='*100}")
    print("  ── ② ★ 一个必须讲清的反常现象 ──")
    print(f"     教科书：q_T^SO < q_T^UE（最优让车**更多**走慢路，以缓解快路拥堵）")
    print(f"     本案例：q_T^UE = {r['qT_ue']:,.0f}（隧道占比 "
          f"{r['qT_ue']/(r['qT_ue']+r['qB_ue']):.1%}）")
    print(f"             q_T^SO = {r['qT_so']:,.0f}（隧道占比 "
          f"{r['qT_so']/(r['qT_so']+r['qB_so']):.1%}）")
    direction = "SO < UE" if r["qT_so"] < r["qT_ue"] else "SO > UE"
    print(f"             ⇒ **{direction}**")
    print(f"     原因：**货车把大桥堵住了** —— 大桥的底载 {tk:,.0f} pcu/h"
          f"已占其能力的 {tk/CORRIDOR['大桥']['cap']:.1%}，")
    print("           所以『让客车留在桥上』不再是最优，反而应把客车**推向隧道**。")
    print("     => **这是『隧道全时段禁货』这一政策的直接后果。**")

    # ── ③ 差别定价 ──
    print(f"\n{'='*100}")
    print("  ── ③ 差别定价：最优价差是多少？──")
    base_qT = r["qT_so"]
    print("     先看『零诱增』下、以 SO 为目标的定价：")
    print(f"     {'隧道费':>8}{'大桥费':>8}{'价差':>8}{'UE隧道占比':>12}"
          f"{'UE总时间':>12}{'相对免费-免费':>15}")
    ref = solve(q_car_h, tk, 25.0, 25.0)
    best = None
    for dT in (0, 10, 15, 20, 25, 30, 35, 40, 50):
        s = solve(q_car_h, tk, float(dT), 25.0)
        ratio = s["t_ue"] / ref["t_ue"] - 1
        share = s["qT_ue"] / (s["qT_ue"] + s["qB_ue"])
        if best is None or s["t_ue"] < best[1]:
            best = (dT, s["t_ue"], share, ratio)
        print(f"     {dT:>8}{25:>8}{dT-25:>8}{share:>12.1%}"
              f"{s['t_ue']:>12,.0f}{ratio:>15.2%}")
    print(f"\n     ⇒ 最优隧道费 **{best[0]} 元**（大桥 25 元），"
          f"价差 **{best[0]-25:+d} 元**")
    print(f"       此时 UE 隧道占比 {best[2]:.1%}，总时间相对"
          f"『双 25 元』变化 {best[3]:+.2%}")

    # 反向：降低隧道费
    print(f"\n     反向（补贴隧道）：")
    print(f"     {'隧道费':>8}{'大桥费':>8}{'价差':>8}{'UE隧道占比':>12}"
          f"{'UE总时间':>12}")
    for dT in (25, 15, 10, 5, 0):
        s = solve(q_car_h, tk, float(dT), 25.0)
        share = s["qT_ue"] / (s["qT_ue"] + s["qB_ue"])
        print(f"     {dT:>8}{25:>8}{dT-25:>8}{share:>12.1%}"
              f"{s['t_ue']:>12,.0f}")

    # ── ④ 弹性：2020 免收通行费给出的量级 ──
    print(f"\n{'='*100}")
    print("  ── ④ 定价的可行性边界（需求弹性）──")
    v = SHOCKS["2020免收通行费"]["_验算"]
    frac = SHOCKS["2020免收通行费"]["占比"]
    print(f"     2020 免收 {frac:.2%} 天数的通行费 ⇒ 收入归一化后与 2019 年"
          f"相差 {v['相对偏差']:+.2%}")
    print(f"     ⇒ **价格从 25 元降到 0（降幅 100%）没有抬高长期需求水平**")
    print(f"       这说明：**该走廊的需求对价格不敏感**（至少在中长期）。")
    print("     => **推论**：靠调价来改变分配，主要作用于**路径选择**"
          f"（短期），而不是**总量**（长期）。")
    print("       本节的定价结论因此只适用于『重分配』，不适用于『抑制需求』。")

    # ── ⑤ 两项实际措施的评估 ──
    print(f"\n{'='*100}")
    print("  ── ⑤ 两项实际措施在模型中的对应 ──")
    div = OPENING["引流至隧道_万辆"]
    print(f"     措施 1「远端分流、近端管控」—— 官方日均引流 {div} 万辆跨境客车")
    print("       模型中对应：**非价格的信息/引导**，把客车从 UE 推向 SO 方向。")
    print(f"       官方引流 {div} 万辆/日；观测隧道 {OPENING['隧道_万辆']} 万辆/日")
    print(f"       ⇒ 引流占总分流需求的 "
          f"{div/OPENING['隧道_万辆']:.1%}")
    print(f"       而 SO 要求隧道客车占比 "
          f"{r['qT_so']/(r['qT_so']+r['qB_so']):.1%}（观测 {share_T:.0%}）")
    print("       => **引导方向与 SO 一致**，但**力度仍不足**")
    print(f"\n     措施 2「客货分离」（隧道全时段禁货）")
    print(f"       · 收益：隧道内车流同质，事故 −56%（官方数据）")
    print(f"       · 代价：**全部货车压在桥上** ⇒ 大桥底载 "
          f"{tk:,.0f} pcu/h = 其能力的 {tk/CORRIDOR['大桥']['cap']:.1%}")
    print(f"       · CA 结果：隧道高峰饱和度仅 0.48 ⇒ 隧道**仍有余量承接更多客车**")
    print("       => **禁货本身不是瓶颈来源，但『货车沉淀在大桥』改变了最优分配的方向**")

    out = {
        "需求": {"通道高峰": qh, "phi": round(phi, 4),
                 "货车_pcu_h": round(tk, 0), "客车_pcu_h": round(q_car_h, 0)},
        "三方对比": rows,
        "自检_SO_le_UE": r["selfcheck"],
        "反常现象": {
            "qT_ue": round(r["qT_ue"], 0), "qT_so": round(r["qT_so"], 0),
            "方向": direction,
            "_解释": "货车把大桥堵住（底载占其能力 "
                     f"{tk/CORRIDOR['大桥']['cap']:.1%}）⇒ "
                     "最优应把客车推向隧道，与教科书相反",
        },
        "差别定价": {"最优隧道费_元": best[0], "大桥费_元": 25,
                     "价差_元": best[0] - 25,
                     "此时UE隧道占比": round(best[2], 4),
                     "总时间变化": round(best[3], 4)},
        "弹性边界": {
            "2020免收天数占比": frac,
            "收入归一化偏差": v["相对偏差"],
            "_结论": "价格降 100% 未抬高长期需求 ⇒ 需求对价格不敏感；"
                     "定价只作用于路径选择，不作用于总量",
        },
        "_重大限制": ("第 1 问已证明**观测分配不是均衡**"
                      "（大桥成本高 43 min 却不转移）=> "
                      "本问的定价结论只在『若路径成本可感知』的前提下成立，"
                      "不能用来解释或预测观测。"),
    }
    p = RES / "q4_定价.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=float),
                 encoding="utf-8")
    print(f"\n  -> {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
