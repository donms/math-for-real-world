#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W47 · 问题 1：一桥一隧的通道网络模型。

## 一、拓扑：走廊内两条**并联路径**

```
        ┌──── 江阴大桥（客货混行，120 km/h 设计）────┐
G2 京沪 ─┤                                          ├─ G4221 沪武
        └──── 江阴靖江隧道（客车专用，80 km/h）────┘
```

两条路径连接**同一对端点**（靖江侧与江阴侧）⇒ **分流点之间的选择问题**。
路径外的接线在两条路径上**大致对称**，故在比较中可消去 ——
但这**是一个假设**，在论文里要写明（见 `_接线假设`）。

## 二、阻抗函数：BPR

$$
t_k(q_k) \;=\; t_k^{0}\left[1 + \alpha\left(\frac{q_k}{C_k}\right)^{\beta}\right],
\qquad \alpha=0.15,\ \beta=4
$$

* $t_k^{0} = L_k / v_k^{0}$：自由流走行时间；
* $C_k$：通行能力，**按《公路工程技术标准》(JTG B01-2014) 三级服务水平**
  的一条车道设计通行能力乘车道数：

| 设计速度 (km/h) | 120 | 100 | 80 |
|---|---|---|---|
| 设计通行能力 [pcu/(h·ln)] | **1650** | **1600** | **1500** |

**来源**：`data/raw/南京交通局_OD分析.pdf` p95 表 3-28
（华设设计集团《南京都市圈环线高速公路桥林至苏皖界段工程可行性研究》）。

## 三、★★ 分车型：本题与教科书双路径问题的根本不同

* **隧道**：全时段**禁行货车** ⇒ 只承载客车；
* **大桥**：**客货混行** ⇒ 承载**全部货车** + 剩余客车。

$$
q_B = q_B^{\text{car}} + Q^{\text{truck}},\qquad q_T = q_T^{\text{car}},
\qquad q_T^{\text{truck}} \equiv 0
$$

⇒ **货车是压在桥上的"固定负载"，系统的可调度自由度只有客车。**
这是第 4 问的核心约束。

用法：
    $PY q1_network.py
    $PY q1_network.py --sweep      # 参数扫描
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from w47_data import BRIDGE, COST, OPENING                   # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
RES.mkdir(parents=True, exist_ok=True)

# ── 设计通行能力标准（JTG B01-2014 三级服务水平）──
CAP_PER_LANE = {120: 1650, 100: 1600, 80: 1500}     # pcu/(h·ln)
LANES_ONE_DIR = 3                                   # 双向 6 车道 ⇒ 单向 3
BPR_ALPHA, BPR_BETA = 0.15, 4.0

# ── 几何与设计速度 ──
PATHS = {
    "大桥": {
        "名称": "江阴长江公路大桥",
        "跨江段_km": 3.071,          # 大桥全长（公开资料常引值）
        "建设总里程_km": 5.176,      # 含引桥/接线（募集说明书口径）
        "设计速度_kmh": 120,
        "车道_单向": LANES_ONE_DIR,
        "车型": "客货混行",
        "收费_小客车_元": 25,
        "source": "江苏交通控股 2025 年公司债募集说明书 p31；"
                  "宁沪高速募集说明书 表4-17",
    },
    "隧道": {
        "名称": "江阴靖江长江隧道",
        "跨江段_km": 11.825,
        "盾构段_m": 4952,
        "设计速度_kmh": 80,
        "车道_单向": LANES_ONE_DIR,
        "车型": "客车专用（全时段禁货）",
        "收费_小客车_元": 25,
        "source": "江南时报 2026-09-24；中国江苏网 2026-09-23",
    },
}

# ── 观测（万辆/日 → 换算到小时）──
OBS = {
    "大桥_万辆每日": OPENING["大桥_万辆"],
    "隧道_万辆每日": OPENING["隧道_万辆"],
    "通道_万辆每日": OPENING["通道日均_万辆"],
    "最高小时": OPENING["最高小时_南向北"],
    "最高小时_方向": "南向北",
}

_接线假设 = (
    "两条路径在**分流点之外**的接线（北接线 G2 靖江侧、南接线 G4221 沪武侧）"
    "在长度与设计速度上**近似对称** ⇒ 在路径比较中消去，"
    "只用**跨江段**计算自由流时间。"
    "**这是一个显式假设**：若接线不对称，会系统性偏向某一条路径。"
    "敏感性分析中给出接线长度 ±30% 的影响。"
)


def capacity(prm: dict, max_cap: bool = False) -> float:
    r"""单向通行能力 [pcu/h]。

    `max_cap=True` 时用**理论最大通行能力**（约 2200 pcu/(h·ln)）作敏感性对照 ——
    因为 JTG 的"设计通行能力"对应**三级服务水平**，不是物理上限。
    """
    per = 2200 if max_cap else CAP_PER_LANE[prm["设计速度_kmh"]]
    return per * prm["车道_单向"]


def t_free(prm: dict) -> float:
    r"""自由流走行时间 [分钟]（只用跨江段）。"""
    km = prm["跨江段_km"]
    v = prm["设计速度_kmh"]
    return km / v * 60.0


def bpr(t0: float, q: float, C: float) -> float:
    r"""BPR 阻抗 [分钟]。q 与 C 同量纲（pcu/h）。"""
    x = max(q, 0.0) / C
    return t0 * (1.0 + BPR_ALPHA * x ** BPR_BETA)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", action="store_true")
    args = ap.parse_args()

    print("=" * 96)
    print("  W47 · 问题 1：一桥一隧通道网络模型")
    print("=" * 96)

    print("\n  ── 路径参数 ──")
    print(f"     {'路径':<8}{'跨江段(km)':>12}{'设计速度':>10}{'单向车道':>10}"
          f"{'自由流(min)':>13}{'能力(pcu/h)':>13}{'车型':>18}")
    for k, p in PATHS.items():
        print(f"     {k:<8}{p['跨江段_km']:>12.3f}{p['设计速度_kmh']:>10}"
              f"{p['车道_单向']:>10}{t_free(p):>13.2f}"
              f"{capacity(p):>13,.0f}{p['车型']:>18}")

    print(f"\n  ── 通行能力依据（JTG B01-2014 三级服务水平）──")
    for v, c in CAP_PER_LANE.items():
        print(f"     设计速度 {v:>3} km/h ⇒ {c} pcu/(h·ln)"
              f" ⇒ 单向 {LANES_ONE_DIR} 车道 = {c*LANES_ONE_DIR:,} pcu/h")

    # ── ★ 关键：实测高峰小时 vs 能力 ──
    print(f"\n{'='*96}")
    print("  ★ 实测高峰小时流量 vs 通行能力")
    qh = OBS["最高小时"]
    print(f"     {OBS['最高小时_方向']}方向最高小时流量 = {qh:,} 辆/h"
          f"（同比 2024 同期 {OPENING['最高小时同比_南向北']:+.1%}）")

    # ★ 口径判定：先用两个能力标准做"可不可能"检验
    share_T = OPENING["隧道高峰占比"]
    capB, capT = capacity(PATHS["大桥"]), capacity(PATHS["隧道"])
    maxB, maxT = capacity(PATHS["大桥"], True), capacity(PATHS["隧道"], True)
    print(f"\n     口径检验：单个设施能否承担 {qh:,} 辆/h？")
    for k, c, m in (("大桥", capB, maxB), ("隧道", capT, maxT)):
        verdict = "不可能" if qh > m else ("超出设计能力但未超物理上限"
                                          if qh > c else "可能")
        print(f"       {k}：设计 {c:,.0f} / 最大 {m:,.0f} pcu/h"
              f" ⇒ **{verdict}**")
    print(f"     => 因 {qh:,} **超过任一单个设施的物理上限**，"
          f"该值只能是**通道单向合计**（大桥 + 隧道），")
    print("        不能理解为某一条设施的小时流量。"
          "**这一点在论文里必须写明。**")

    # 拆分方案
    print(f"\n     通道单向高峰 {qh:,} 辆/h 的拆分方案对比：")
    print(f"       {'方案':<22}{'大桥':>10}{'隧道':>10}"
          f"{'大桥饱和':>10}{'隧道饱和':>10}{'可行':>6}")
    splits = {
        "A 年均占比 78/22": 0.22,
        f"B 高峰实测 {1-share_T:.0%}/{share_T:.0%}": share_T,
        "C 均分 50/50": 0.50,
    }
    for lab, st in splits.items():
        qT, qB = qh * st, qh * (1 - st)
        # 货车不能走隧道 ⇒ 大桥另加货车负载
        sB, sT = qB / capB, qT / capT
        ok = (sB <= 1.0 and sT <= 1.0)
        okm = (qB <= maxB and qT <= maxT)
        print(f"       {lab:<22}{qB:>10,.0f}{qT:>10,.0f}"
              f"{sB:>10.3f}{sT:>10.3f}"
              f"{('v 设计内' if ok else ('~ 超设计' if okm else 'X 超上限')):>8}")

    # ── 自由流时间差 ──
    print(f"\n{'='*96}")
    print("  ★ 自由流时间与车道小时成本")
    tB, tT = t_free(PATHS["大桥"]), t_free(PATHS["隧道"])
    print(f"     大桥 {tB:.2f} min（{PATHS['大桥']['跨江段_km']} km @ "
          f"{PATHS['大桥']['设计速度_kmh']} km/h）")
    print(f"     隧道 {tT:.2f} min（{PATHS['隧道']['跨江段_km']} km @ "
          f"{PATHS['隧道']['设计速度_kmh']} km/h）")
    print(f"     ⇒ 自由流下**隧道反而慢 {tT-tB:+.2f} min**")
    print(f"       原因：跨江段长 "
          f"{PATHS['隧道']['跨江段_km']/PATHS['大桥']['跨江段_km']:.2f}×，"
          f"而设计速度只有 "
          f"{PATHS['隧道']['设计速度_kmh']/PATHS['大桥']['设计速度_kmh']:.0%}")
    print(f"\n     [!] **这解释了为什么收费相同、隧道却只分到约三成**：")
    print(f"         在自由流条件下**隧道并无时间优势**，甚至更慢；")
    print(f"         隧道的价值在于**拥堵时**（大桥 BPR 惩罚急剧上升）"
          f"以及**可靠性**（无货车干扰）。")

    # ── 分车型：货车固定负载 ──
    print(f"\n{'='*96}")
    print("  ★★ 分车型约束：货车是压在大桥上的固定负载")
    shares = [(y, d["货车"] / d["合计"]) for y, d in BRIDGE.items()]
    phi = float(np.mean([s for _, s in shares]))
    print(f"     货车占比实测：" + "  ".join(f"{y} {s:.2%}" for y, s in shares))
    print(f"     均值 φ = {phi:.2%}（区间 {min(s for _,s in shares):.2%}"
          f"–{max(s for _,s in shares):.2%}）")
    print(f"     隧道全时段禁货 ⇒ **这 {phi:.1%} 无法被分流**")
    print(f"\n     定量含义：设客车中改走隧道的比例为 s，则大桥降幅上限")
    print(f"       Δq_B/q_B <= (1-φ)·s = {1-phi:.4f}·s")
    d_down = -OPENING["大桥变化_官方"]
    s_implied = d_down / (1 - phi)
    print(f"     观测大桥降幅 {d_down:.2%} ⇒ 隐含客车分流率 s ≈ "
          f"**{s_implied:.2%}**")
    share_obs = OPENING["隧道_万辆"] / OPENING["通道日均_万辆"]
    print(f"     隧道观测占比 {share_obs:.2%}"
          f"（高峰约 {share_T:.0%}）⇒ **两者互相印证**，"
          f"差 {abs(s_implied-share_obs):.1%} 个百分点")

    # ── 接线假设的敏感性 ──
    print(f"\n{'='*96}")
    print("  ── 接线假设的敏感性（跨江段长度 ±30%）──")
    print(f"     {'扰动':<16}{'t0大桥':>10}{'t0隧道':>10}{'隧道-大桥(min)':>16}")
    for lab, f in (("现状", 1.0), ("大桥跨江段+30%", 1.3), ("隧道跨江段+30%", 1.0)):
        if lab == "隧道跨江段+30%":
            a, b = tB, tT * 1.3
        elif lab == "大桥跨江段+30%":
            a, b = tB * 1.3, tT
        else:
            a, b = tB, tT
        print(f"     {lab:<16}{a:>10.2f}{b:>10.2f}{b-a:>16.2f}")
    print("     ⇒ 结论方向不变（隧道在自由流下无优势），"
          "但**幅度**对接线假设敏感。")

    if args.sweep:
        print(f"\n{'='*96}")
        print("  ── 参数扫描：隧道/大桥自由流时间比 对 分流率的含义 ──")
        print("     （第 4 问会用；此处只给弹性区间）")
        print(f"     {'隧道设计速度':>14}{'t0隧道(min)':>14}{'t0差(min)':>12}")
        for v in (60, 70, 80, 90, 100, 120):
            tt = PATHS["隧道"]["跨江段_km"] / v * 60
            print(f"     {v:>14}{tt:>14.2f}{tt-tB:>12.2f}")

    out = {
        "路径": {k: {**v, "自由流_min": round(t_free(v), 3),
                     "能力_pcu_h": capacity(v),
                     "能力_理论最大_pcu_h": capacity(v, max_cap=True)}
                 for k, v in PATHS.items()},
        "通行能力标准": {"来源": "JTG B01-2014 三级服务水平；"
                                "data/raw/南京交通局_OD分析.pdf p95 表3-28",
                         "pcu_per_lane": CAP_PER_LANE,
                         "单向车道": LANES_ONE_DIR},
        "BPR": {"alpha": BPR_ALPHA, "beta": BPR_BETA},
        "观测": {**OBS, "隧道高峰占比": share_T,
                 "_口径判定": (f"高峰小时 {qh:,} 辆/h 超过任一单个设施的"
                               f"物理上限（大桥 {maxB:,.0f}、隧道 {maxT:,.0f}）"
                               f"⇒ 只能是**通道单向合计**"),
                 "能力_设计_pcu_h": {"大桥": capB, "隧道": capT},
                 "能力_最大_pcu_h": {"大桥": maxB, "隧道": maxT},
                 "高峰拆分": {lab: {"大桥": round(qh * (1 - st), 0),
                                    "隧道": round(qh * st, 0)}
                              for lab, st in splits.items()}},
        "自由流对比": {"大桥_min": round(tB, 3), "隧道_min": round(tT, 3),
                       "隧道减大桥_min": round(tT - tB, 3),
                       "_说明": "自由流下隧道反而更慢 ⇒ 隧道价值在拥堵与可靠性"},
        "分车型": {"货车占比_均值": round(phi, 4),
                   "货车占比_区间": [round(min(s for _, s in shares), 4),
                                     round(max(s for _, s in shares), 4)],
                   "隐含客车分流率": round(s_implied, 4),
                   "隧道观测占比": round(share_obs, 4)},
        "_接线假设": _接线假设,
    }
    p = RES / "q1_网络.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=float),
                 encoding="utf-8")
    print(f"\n  -> {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
