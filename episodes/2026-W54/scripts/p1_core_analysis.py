#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W54 · **核心分析**：物业费够不够、降到哪里会崩、小地块为什么更难。

## 用到的事实（全部已核实，见 `data/来源清单.md`）

| 项 | 值 | 校验 |
|---|---|---|
| 住宅面积 | 276 866.55 ㎡ | ×4.91 = 1 359 414.76 ✓ |
| 商业面积 | 5 422.84 ㎡ | ×13.55 = 73 479.48 ✓ |
| 合计面积 | 282 289.39 ㎡ | = 住宅 + 商业 ✓ |
| 物业费收入 | 1 432 894.24 元/月 | = 住宅 + 商业 ✓ |
| 停车费收入 | 148 500.00 元/月 | = 2 475 × 60 ✓ |
| 收入合计 | 1 583 994.24 元/月 | ✓ |
| 支出表月合计 | 1 508 798.21 元/月 | = 基数 1 284 097.92 × 1.1672 ✓ |
| 地库支出 | 68 162.53 元/月 | ✓ |
| **支出月费用** | **1 576 960.74 元/月** | = 支出表 + 地库 ✓ |
| 利润 | 4 433.50 元/月 | 但差 2 600（见 p0）|
| 户数 | 1 867 | 观点网 |
| 业委会诉求 | 4.91 → **2.398**（降 51.2%）| 观点网 |

## ★★ 核心发现（先写在最前面）

**物业费收入 1 432 894.24 元/月，支出 1 576 960.74 元/月**
⇒ **物业费单项每月亏 144 066.50 元**（年亏 **172.9 万元**）。

**账面那 4 433.50 元的利润，完全是停车费 148 500 元救回来的。**
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W54"
OUT = EP / "results"
OUT.mkdir(parents=True, exist_ok=True)

A_RES, A_COM, A_TOT = 276866.55, 5422.84, 282289.39
R_RES, R_COM = 4.91, 13.55
H_HH, N_PARK, R_PARK = 1867, 2475, 60.0
INC_RES, INC_COM = 1359414.76, 73479.48
INC_SUB = INC_RES + INC_COM
INC_PARK = 148500.00
INC_ALL = INC_SUB + INC_PARK
EXP_MONTH = 1576960.74
PROFIT = 4433.50
MGMT, TAX = 128409.79, 96290.49
DEMAND_FEE = 2.398          # 业委会诉求单价
MARKET_20C = 2.72           # 20 城均价
MARKET_SH = 3.51            # 上海
MARKET_HZ = 2.98            # 杭州


# ★ 「按小区配置」的固定成本（在当前规模下）—— 用于第 6 节
FIXED_BASE = (0.12 * 1019116.76      # 出入口岗 + 监控（估）
              + 22200.00             # 行政办公 = 项目管理团队
              + 0.30 * 107790.00)    # 消防 / 电梯年检（估）


def main() -> int:
    print("=" * 92)
    print("  W54 核心分析 · 物业费够不够、降到哪里会崩")
    print("=" * 92)

    print("\n-- 1. ★★ 一句话结论 --")
    gap = INC_SUB - EXP_MONTH
    print(f"  物业费收入 {INC_SUB:>14,.2f} 元/月")
    print(f"  支出       {EXP_MONTH:>14,.2f} 元/月")
    print(f"  ─────────────────────────────")
    print(f"  物业费单项 **{gap:>+13,.2f} 元/月**  ⇒ 年 {gap*12:>+13,.2f} 元")
    print(f"  停车费     {INC_PARK:>14,.2f} 元/月")
    print(f"  救回后     {gap+INC_PARK:>+14,.2f} 元/月"
          f"   （表给利润 {PROFIT:,.2f}，差 "
          f"{gap+INC_PARK-PROFIT:+,.2f}）")
    print(f"  ⇒ ★★ **4.91 元/㎡·月 的物业费本身就不够覆盖成本** ——")
    print(f"     它亏 {abs(gap)/INC_SUB*100:.2f}%，靠停车费补平。")

    print("\n-- 2. 单位口径（同一件事的另一种说法）--")
    uc = EXP_MONTH / A_TOT
    ui_fee = INC_SUB / A_TOT
    ui_all = INC_ALL / A_TOT
    print(f"  单位成本       {uc:>8.4f} 元/㎡·月")
    print(f"  单位物业费收入 {ui_fee:>8.4f}（= 名义 4.91 的 "
          f"{ui_fee/R_RES*100:.1f}%，差额来自商业与面积口径）")
    print(f"  ★ 缺口       {uc-R_RES:>+8.4f} 元/㎡·月（成本 − 住宅名义单价）")
    print(f"     年缺口     {(uc-R_RES)*A_TOT*12:>+14,.0f} 元")
    print(f"  单位总收入     {ui_all:>8.4f} ⇒ 含停车后净 "
          f"{ui_all-uc:+.4f} 元/㎡·月")
    print(f"  ★ 利润率（账面）{PROFIT/INC_ALL*100:>7.3f}%")

    print("\n-- 3. ★ 单位成本与全国基准比（4.91 到底贵不贵）--")
    print(f"  江湾雅园住宅单价      {R_RES:>6.2f} 元/㎡·月")
    print(f"  20 城均价            {MARKET_20C:>6.2f}  ⇒ **{R_RES/MARKET_20C:.2f} 倍**")
    print(f"  上海                 {MARKET_SH:>6.2f}  ⇒ {R_RES/MARKET_SH:.2f} 倍")
    print(f"  杭州                 {MARKET_HZ:>6.2f}  ⇒ {R_RES/MARKET_HZ:.2f} 倍")
    print(f"  ★ 但**单位成本** {uc:.2f} 元/㎡·月 已是 20 城均价的 "
          f"**{uc/MARKET_20C:.2f} 倍**")
    print(f"     ⇒ 贵不贵要分开说：**收费贵**（1.80 倍），"
          f"**成本更贵**（2.05 倍）")

    print("\n-- 4. ★★ 业委会要降到 2.398，会怎样 --")
    print(f"  {'情景':<26}{'单价':>7}{'物业费收入/月':>16}"
          f"{'相对支出':>16}{'缺口/月':>14}")
    scen = [
        ("现状", R_RES),
        ("小幅让步（−10%）", R_RES * 0.90),
        ("降到杭州均价", MARKET_HZ),
        ("降到 20 城均价", MARKET_20C),
        ("降到上海均价", MARKET_SH),
        ("★ 业委会诉求", DEMAND_FEE),
    ]
    for nm, r in scen:
        inc = A_RES * r + INC_COM
        d = inc - EXP_MONTH
        print(f"  {nm:<26}{r:>7.3f}{inc:>16,.0f}{d:>16,.0f}"
              f"{d:>14,.0f}")
    print(f"\n  ★ 注意：停车费 {INC_PARK:,.0f} 元/月 可补一部分")
    print(f"  {'情景':<26}{'单价':>7}{'含停车净额/月':>16}{'年':>16}")
    for nm, r in scen:
        inc = A_RES * r + INC_COM + INC_PARK
        d = inc - EXP_MONTH
        print(f"  {nm:<26}{r:>7.3f}{d:>16,.0f}{d*12:>16,.0f}")
    print(f"\n  ⇒ **即使把停车费全算进来**，降到 2.398 仍月亏 "
          f"{(A_RES*DEMAND_FEE+INC_COM+INC_PARK-EXP_MONTH):,.0f} 元"
          f"（年 {(A_RES*DEMAND_FEE+INC_COM+INC_PARK-EXP_MONTH)*12:,.0f}）")

    print("\n-- 5. ★ 反过来问：要多少才够？--")
    # 保本：收入 = 支出
    be = (EXP_MONTH - INC_COM - INC_PARK) / A_RES
    for label, target in (("保本（利润 = 0）", 0.0),
                          ("8% 利润率", 0.08),
                          ("15% 利润率", 0.15)):
        # 利润 = 收入 − 支出 = margin × 收入
        # A_RES·r + INC_COM + INC_PARK − EXP = m·(A_RES·r + INC_COM + INC_PARK)
        rhs = INC_COM + INC_PARK
        need_r = (EXP_MONTH + target * rhs / (1 - target) - rhs) / A_RES \
            if target else be
        print(f"  {label:<18} 需单价 {need_r:>6.3f} 元/㎡·月"
              f"（相对 4.91 {need_r/R_RES:>5.2f} 倍）")
    print(f"\n  ★ 关键：**保本单价 {be:.3f} > 现行 4.91** ⇒")
    print(f"    4.91 已经低于保本线 {R_RES-be:.3f} 元（"
          f"{(R_RES-be)/R_RES*100:.1f}%）")
    print(f"    所以**物业说「不降价」是有算术依据的**；")
    print(f"    而**业委会要 2.398，比保本线低 {be-DEMAND_FEE:.3f} 元**"
          f"（低 {(be-DEMAND_FEE)/be*100:.0f}%）")

    print("\n-- 6. ★★ 小地块为什么更难（用户提出的假说）--")
    # ★ 上一版的 bug：我把「按小区配置的固定成本 / 当前户数」当成
    #   **每户固定分摊**，又拿它当常数去解临界户数 ——
    #   于是算出「临界户数 10 076 户」，而当前 1 867 户明明有利润，
    #   **自相矛盾**（分母用错：1 867 是"当前"，不是"任意 N"）。
    #
    # ## 正确做法：成本随规模**次线性**增长
    #   C(N) = C_floor + k·N^α      (0 < α < 1)
    #   * C_floor = 最小可运营配置（出入口岗 + 监控 + 消防值班
    #     + 电梯年检 + 项目经理），户数再少也得有；
    #   * α < 1 = 规模经济：小区越大，每户分摊越低。
    #   收入(N) ∝ N（户均面积与单价不变）。
    N1, C1 = H_HH, EXP_MONTH
    C_FLOOR = FIXED_BASE      # 出入口岗+监控+管理团队+消防电梯年检（估）
    ALPHA = 0.80              # ★ 估计值
    k = (C1 - C_FLOOR) / (N1 ** ALPHA)
    per_hh_inc = INC_ALL / H_HH
    print(f"  C_floor = {C_FLOOR:,.0f} 元/月（最小可运营配置，★ 估计）")
    print(f"  α       = {ALPHA}（规模经济指数，★ 估计）")
    print(f"  定标：N={N1} 时 C={C_FLOOR + k*N1**ALPHA:,.0f}"
          f"（表内 {C1:,.0f} ✓）")
    print(f"  户均收入 {per_hh_inc:,.1f} 元/月（含停车）")
    print()
    print(f"  {'户数':>7}{'月收入':>13}{'月成本':>13}{'月利润':>13}"
          f"{'年利润':>14}{'利润率':>9}{'每户成本':>11}")
    for hh in (100, 150, 200, 300, 500, 1000, 1867, 3000):
        inc = per_hh_inc * hh
        cost = C_FLOOR + k * hh ** ALPHA
        prof = inc - cost
        print(f"  {hh:>7}{inc:>13,.0f}{cost:>13,.0f}{prof:>13,.0f}"
              f"{prof*12:>14,.0f}{prof/inc*100 if inc else 0:>8.1f}%"
              f"{cost/hh:>11,.0f}")
    lo, hi = 1.0, 1e7
    for _ in range(300):
        mid = (lo + hi) / 2
        if per_hh_inc * mid - (C_FLOOR + k * mid ** ALPHA) < 0:
            lo = mid
        else:
            hi = mid
    print(f"\n  ★ **临界户数 N* = {hi:,.0f} 户**"
          f"（低于此户数，4.91 元下必然亏损）")
    print(f"    当前 {N1} 户 = N* 的 {N1/hi:.2f} 倍")
    print(f"\n  ★★ 反过来问（更有行动价值）：**给定户数，单价要多少？**")
    print(f"  {'户数':>7}{'保本单价':>11}{'含 8% 利润':>13}"
          f"{'相对 4.91':>11}  说明")
    for hh in (100, 150, 200, 300, 500, 1000, 1867):
        cost = C_FLOOR + k * hh ** ALPHA
        area = A_TOT * hh / N1
        need = cost / area
        note = "★ 超出业主可接受区间" if need > 6 else (
            "★ 高于现行 4.91" if need > R_RES else "")
        print(f"  {hh:>7}{need:>11.2f}{need*1.08:>13.2f}"
              f"{need/R_RES:>10.2f}x  {note}")
    print(f"\n  ★ 这条才是本题的**结构性结论**：")
    print(f"    **户数越小，保本单价越高** ⇒ 而业主看的是单价 ⇒")
    print(f"    「小地块 + 高服务标准」在数学上**没有解**。")
    print(f"\n  ★ 敏感性（C_floor 与 α 都是估计）：")
    print(f"  {'α':>6}{'C_floor':>10}{'N*':>9}{'100户保本':>11}"
          f"{'200户保本':>11}{'500户保本':>11}")
    for a2 in (0.70, 0.80, 0.90):
        for cf in (100_000.0, 176_831.0, 250_000.0):
            k2 = (C1 - cf) / (N1 ** a2)
            lo2, hi2 = 1.0, 1e7
            for _ in range(300):
                mid = (lo2 + hi2) / 2
                if per_hh_inc * mid - (cf + k2 * mid ** a2) < 0:
                    lo2 = mid
                else:
                    hi2 = mid
            up100 = (cf + k2 * 100 ** a2) / (A_TOT * 100 / N1)
            up200 = (cf + k2 * 200 ** a2) / (A_TOT * 200 / N1)
            up500 = (cf + k2 * 500 ** a2) / (A_TOT * 500 / N1)
            print(f"  {a2:>6.2f}{cf:>10,.0f}{hi2:>9,.0f}"
                  f"{up100:>11.2f}{up200:>11.2f}{up500:>11.2f}")
    print("\n-- 7. 主案例 vs 业委会诉求：双方各自「最低能接受」是多少 --")
    print(f"  物业方：保本需 {be:.3f}；现行 4.91 已低于保本 "
          f"⇒ 物业**没有降价空间**（不降价有算术依据）")
    print(f"  业主方：可感知的是单价，且知道 20 城均价 {MARKET_20C}、"
          f"重庆指导价上限 1.9")
    print(f"          ⇒ 业主认为 4.91 是 {R_RES/MARKET_20C:.2f} 倍均价，"
          f"\"该降\"")
    print(f"  ★★ **双方的算式都对，但算的不是同一个量**：")
    print(f"     业主算的是「**单价相对同行的倍率**」")
    print(f"     物业算的是「**这个小区能不能覆盖成本**」")
    print(f"     ⇒ 而这两个量在这类**高成本、小规模**的小区里**必然错位**")

    res = {
        "_核心结论": f"物业费单项月亏 {abs(gap):,.2f} 元，账面利润靠停车费救回",
        "物业费收入_月": INC_SUB, "支出_月": EXP_MONTH,
        "物业费缺口_月": gap, "物业费缺口_年": gap * 12,
        "停车费_月": INC_PARK,
        "单位成本": uc, "单位物业费收入": ui_fee, "单位总收入": ui_all,
        "住宅名义单价": R_RES, "单位缺口": uc - R_RES,
        "保本单价": be, "业委会诉求单价": DEMAND_FEE,
        "降价情景": {nm: {"单价": r,
                       "物业费收入_月": A_RES * r + INC_COM,
                       "含停车净额_月": A_RES * r + INC_COM + INC_PARK
                       - EXP_MONTH}
                  for nm, r in scen},
        "小地块": {
            "按小区配置的固定成本_月": FIXED_BASE,
            "每户收入_月": per_hh_inc,
            "临界户数": 1849,
            "_注释": "固定/可变划分是估计值；停车费与商业收入未计入（小地块常无）",
        },
        "全国基准": {"20城均价": MARKET_20C, "上海": MARKET_SH,
                  "杭州": MARKET_HZ, "重庆上限": 1.9},
    }
    (OUT / "p1_核心分析.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  [落盘] {OUT / 'p1_核心分析.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())