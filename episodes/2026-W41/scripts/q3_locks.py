#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""Q3：瓶颈会搬家吗？—— 平陆运河三枢纽的串联排队与瓶颈识别。

## 模型

### 1. 单闸次循环时间与服务能力

船闸的一个"服务周期"（船由一侧到另一侧）由四段构成：

    T_cycle = T_进船 + T_关阀 + T_灌/泄水 + T_开阀 + T_出船

* **阀门启闭**：官方给出世界纪录 —— 开门 1 min、关门 0.5 min
  （常规船闸的 2–4 倍）。
* **灌/泄水时间**：与闸室体积、落差、省水率有关。
  省水船闸把水先存入储水池，**灌水时间比常规闸更长**（这是节水的代价）。
  该参数未公开 → 用**区间假设 + 敏感性**。
* **进出船时间**：与闸室容量、船型、编组有关。

单闸次通过量 q_b = 单次艘数 × 平均载货（吨）。

### 2. 三枢纽串联

船舶须**依次通过 3 座**，故单航次总过闸时间 = Σ T_cycle,i。
整条通道的能力由**最慢的一级**决定（串联系统的瓶颈律）：

    通过能力 = min_i( 单级日闸次能力_i × q_b )

### 3. 与分流的反馈

Q2 给出分流量 → 若分流量超过通道能力，则：
* 新通道出现待闸 → 广义成本上升 → 部分货**回流**老通道。
* 迭代到均衡：分流率依能力受限而下降。

### 4. 临界分流量

求使「新通道拥堵成本 = 节省的成本」的那个分流量 ——
超过它，新通道的拥堵会抵消掉它带来的缓解。

用法：
    $PY q3_locks.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"


def main() -> int:
    P = json.loads((RES / "q0_params.json").read_text(encoding="utf-8"))
    locks = P["平陆运河"]["三枢纽"]
    valve = P["平陆运河"]["阀门启闭"]

    print("=" * 84)
    print("  Q3 · 平陆运河三枢纽：串联排队与瓶颈识别")
    print("=" * 84)

    # ---------- 1. 单闸次循环时间 ----------
    print("\n【1】单闸次循环时间的构成\n")
    t_open, t_close = valve["开门_min"], valve["关门_min"]
    print(f"  阀门（世界纪录）：开门 {t_open:.1f} min、关门 {t_close:.1f} min")
    print(f"  另有：灌/泄水时间、船舶进出时间 —— **均未公开**，用区间假设\n")

    # 假设区间（分钟）：灌泄水与落差正相关；省水闸比常规闸更慢
    # 依据：落差越大，闸室体积与水头越大 → 时间越长
    def fill_min(drop_m: float, save_ratio: float) -> tuple[float, float]:
        r"""灌/泄水时间区间（min）。

        以"落差每米约 0.5–1.0 min"为基，省水闸因需先向储水池分水，
        乘 1.3–1.6 的系数。**这是假设**，论文必须标注。
        """
        base_lo, base_hi = drop_m * 0.5, drop_m * 1.0
        k = 1.3 + (save_ratio - 0.5) * 1.0        # 省水率越高越慢
        return base_lo * k, base_hi * k

    T_INOUT_LO, T_INOUT_HI = 20.0, 40.0          # 进出船合计（min）

    print(f"  {'枢纽':<6}{'落差m':>7}{'省水率':>7}{'灌泄水(min)':>16}"
          f"{'循环(min)':>16}{'日闸次':>10}")
    print("  " + "-" * 64)
    cycle = {}
    for name, v in locks.items():
        fl, fh = fill_min(v["落差_m"], v["省水率"])
        lo = t_open + t_close + fl + T_INOUT_LO
        hi = t_open + t_close + fh + T_INOUT_HI
        # 双线 → 两条闸室并行，日闸次翻倍
        d_lo = 24 * 60 / hi * v["线数"]
        d_hi = 24 * 60 / lo * v["线数"]
        cycle[name] = {"fl": (fl, fh), "cycle": (lo, hi),
                       "gates_day": (d_lo, d_hi), "落差": v["落差_m"]}
        print(f"  {name:<6}{v['落差_m']:>7.2f}{v['省水率']*100:>6.0f}%"
              f"{fl:>8.0f}–{fh:<6.0f}{lo:>8.0f}–{hi:<6.0f}"
              f"{d_lo:>4.0f}–{d_hi:<5.0f}")

    # ---------- 2. 串联：瓶颈律 ----------
    print("\n【2】串联系统：能力由最慢一级决定\n")
    # ⚠️ 官方表述是「**两个船闸同时**可满足 12 艘 5000 吨级的船舶通过」，
    #    故 **每闸室 6 艘**，不是 12 艘 —— 早期按 12 艘算使能力翻倍。
    VESSELS_PER_CHAMBER = 6
    TON_PER_VESSEL = 3000      # 按批复的 3000 吨级航道标准（保守于 5000）
    q_b = VESSELS_PER_CHAMBER * TON_PER_VESSEL
    print(f"  官方：「两个船闸**同时**可满足 12 艘 5000 吨级」")
    print(f"    ⚠️ 故**每闸室 6 艘**（早期误按 12 艘，使能力翻倍）")
    print(f"    单闸次可通过量 = {VESSELS_PER_CHAMBER} 艘 × "
          f"{TON_PER_VESSEL} 吨 = **{q_b:,} 吨/闸次**")
    print(f"\n  {'枢纽':<6}{'日闸次(保守)':>14}{'日通过(万吨)':>14}"
          f"{'年通过(亿吨)':>14}")
    print("  " + "-" * 52)
    caps = {}
    for name, c in cycle.items():
        g = c["gates_day"][0]                 # 保守：取慢的一侧
        day = g * q_b / 1e4
        year = day * 365 / 1e4
        caps[name] = year
        print(f"  {name:<6}{g:>14.0f}{day:>14.2f}{year:>14.3f}")

    bottleneck = min(caps, key=caps.get)
    cap_channel = caps[bottleneck]
    print(f"\n  ⇒ **瓶颈级：{bottleneck}**，通道年能力 "
          f"= {cap_channel:.3f} 亿吨/年")
    print(f"    （对照：批复 2035 年预测货运量 1 亿吨 → "
          f"能力{'充足' if cap_channel > 1 else '⚠️ 偏紧'}）")

    # ---------- 3. 与 Q2 分流的反馈 ----------
    print("\n【3】与分流的反馈：能力受限后货会回流\n")
    q2 = json.loads((RES / "q2_diversion.json").read_text(encoding="utf-8"))
    base_flow = 22355.46 / 1e4
    want = base_flow * q2["加权平均分流率"]
    print(f"  Q2 名义分流需求：{base_flow:.2f} 亿吨 × "
          f"{q2['加权平均分流率']*100:.1f}% = **{want:.2f} 亿吨**")
    print(f"  通道能力：{cap_channel:.3f} 亿吨")
    if want > cap_channel:
        print(f"  ⇒ 需求 **超过** 能力 {want-cap_channel:.2f} 亿吨 → "
              f"新通道将成为瓶颈，超出部分**被迫回流**老通道")
        actual = cap_channel
    else:
        print(f"  ⇒ 需求 **未超过** 能力，新通道不会成为瓶颈")
        actual = want
    print(f"  最终转移量：**{actual:.2f} 亿吨**"
          f"（长洲降幅 {actual/base_flow*100:.1f}%）")
    util = actual / cap_channel
    print(f"  新通道利用率：{util*100:.1f}%"
          f"{'  ⚠️ 接近饱和，待闸将快速上升' if util > 0.85 else ''}")

    # ---------- 4. 临界分流量 ----------
    print("\n【4】临界分流量：何时新通道的拥堵抵消其收益\n")
    # 思路：新通道拥堵产生的额外等待成本 = 它省下的成本差时，即为临界
    dc = abs(q2["成本差元每吨"])
    v = P["时间价值"]["基准"]
    W_scale = q2["等待时间天数"]["排除检修均值"]   # 借长洲实测等待尺度标定
    print(f"  新通道节省的广义成本 ΔC = {dc:.2f} 元/吨")
    print(f"  时间价值 v = {v} 元/吨·天")
    crit_wait = dc / v
    print(f"  ⇒ 临界等待时间 W* = ΔC / v = **{crit_wait:.1f} 天**")
    # 反推对应分流量：用服务能力与到达率的关系（近似）
    print(f"\n  即：当新通道的等待时间超过 **{crit_wait:.1f} 天**，")
    print(f"     它的成本优势被完全抵消，分流不再有经济意义。")
    print(f"\n  但**实际利用率只有 {util*100:.1f}%** "
          f"（转移 {actual:.2f} / 能力 {cap_channel:.2f} 亿吨），")
    print(f"  远未接近饱和 → **新通道的等待时间会远低于 {crit_wait:.1f} 天**。")
    print(f"\n  定量估计等待时间（借长洲实测的等待尺度 W_scale="
          f"{W_scale:.2f} 天做标定）：")
    print(f"  {'利用率ρ':>9}{'ρ/(1−ρ)':>10}{'估计等待(天)':>14}{'是否抵消优势':>13}")
    print("  " + "-" * 50)
    for rho in (0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 0.95):
        rel = rho / (1 - rho)
        W = W_scale * rel
        flag = "是" if W > crit_wait else "否"
        mark = "  ← 当前" if abs(rho - util) < 0.06 else ""
        print(f"  {rho:>9.2f}{rel:>10.2f}{W:>14.2f}{flag:>13}{mark}")

    # ---------- 5. 系统总成本随时间 ----------
    print("\n【5】系统总社会成本的时间演化（概念模型）\n")
    print("  三阶段：")
    print("    ① 2026-09 ~ 2026-12：**免费期 + 无拥堵** → 新通道成本优势最大")
    print("    ② 2027-01 起：**开始收费**（1.0 元/总吨·次 × 3 座）")
    print("       ⇒ 成本优势缩水，分流率下降")
    print("    ③ 货量增长 → 新通道利用率上升 → 待闸增加 → 优势进一步缩小")
    toll_per_ton = 1.0 * 3      # 元/吨（按总吨≈载重吨近似）
    print(f"\n  过闸费影响：{toll_per_ton:.1f} 元/吨 vs 节省 {dc:.1f} 元/吨")
    print(f"    ⇒ 收费后成本优势从 {dc:.1f} 降到 {dc-toll_per_ton:.1f} 元/吨"
          f"（降幅 {toll_per_ton/dc*100:.0f}%）")
    s_rec = q2["推荐情景"]["s"]
    th = q2["推荐情景"]["theta"]
    p_free = 1 / (1 + math.exp(th * (-dc + s_rec)))
    p_paid = 1 / (1 + math.exp(th * (-(dc - toll_per_ton) + s_rec)))
    print(f"    分流率：免费期 {p_free*100:.1f}% → 收费后 {p_paid*100:.1f}%"
          f"（降 {(p_free-p_paid)*100:.1f} 个百分点）")

    out = {
        "单闸循环": {k: {"落差m": v["落差"],
                         "灌泄水min": [round(v["fl"][0], 1), round(v["fl"][1], 1)],
                         "循环min": [round(v["cycle"][0], 1), round(v["cycle"][1], 1)],
                         "日闸次": [round(v["gates_day"][0], 1),
                                    round(v["gates_day"][1], 1)]}
                     for k, v in cycle.items()},
        "年能力亿吨": {k: round(v, 3) for k, v in caps.items()},
        "瓶颈级": bottleneck,
        "通道年能力亿吨": round(cap_channel, 3),
        "Q2名义需求亿吨": round(want, 3),
        "最终转移亿吨": round(actual, 3),
        "新通道利用率": round(util, 3),
        "临界等待天数": round(crit_wait, 2),
        "收费影响": {"过闸费元每吨": toll_per_ton,
                     "免费期分流率": round(p_free, 4),
                     "收费期分流率": round(p_paid, 4)},
    }
    (RES / "q3_locks.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  → results/q3_locks.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
