#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W54 · 用**用户核对确认的面积**重算（定稿口径）。

## 用户 2026-10-14 的核对结果

| # | 我问的 | 用户答 |
|---|---|---|
| 1 | 面积 | **276866.55 / 282289.39 / 5422.84** ⇒ **我先前多读了一位**（写成了 2768666.55 / 2822289.39）|
| 2 | 支出列单位 | **就是元** |
| 3 | 第 9 项 | 项目看不清，**金额是 1284097.92**，正好是第 10 项（管理费 10%）的 10 倍 |
| 4 | 利润单位 | 没写，**就是收入与支出的差** |

## 由「3」得到的关键推论

用户说 **1 284 097.92 正好是 128 409.79 的 10 倍** ⇒
**1 284 097.92 是「管理费的计算基数」**（管理费 = 基数 × 10%）。

而它又出现在「合计」行 ⇒
**「合计」行 = 前 8 项之和 + 第 9 项**，且第 9 项可能是**汇总行**而非明细项。

⇒ 本脚本把三种可能的读法都算出来，看哪一种让**全部恒等式**成立。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W54"
OUT = EP / "results"
OUT.mkdir(parents=True, exist_ok=True)

# ===== 用户确认的面积（㎡）=====
A_RES, A_COM, A_TOT = 276866.55, 5422.84, 282289.39
R_RES, R_COM = 4.91, 13.55
H_HH, N_PARK, R_PARK = 1867, 2475, 60.0

# ===== 表内数值（元/月）=====
INC_RES_T, INC_COM_T, INC_SUB_T = 1359414.76, 73479.48, 1432894.24
INC_PARK_T, INC_ALL_T = 148500.00, 1583994.24
PROFIT_T = 4433.50

EXP8 = {
    "人员费用": 1019116.76, "公共设施维护费": 107790.00,
    "清洁卫生费": 88085.83, "绿化养护费": 36405.33,
    "秩序维护费": 9400.00, "行政办公费": 22200.00,
    "固定资产折旧": 3500.00, "公众责任险费": 1100.00,
}
BASE_T = 1284097.92          # 用户核对的"合计"行 = 管理费基数的 10 倍
MGMT_T = 128409.79
TAX_T = 96290.49
MONTH_T = 1508798.21
YEAR_T = 18105578.47
MONTH_PAY_T = 1576960.74     # 利润行的"支出月费用"
GARAGE = {"能耗": 43333.33, "管理费": 14850.00, "税金": 9979.20,
          "总计": 68162.53}


def main() -> int:
    print("=" * 90)
    print("  W54 · 用确认面积重算（定稿口径）")
    print("=" * 90)

    # ---------- 1. 收入列：现在应当精确吻合 ----------
    print("\n-- 1. 收入列自洽性（用确认面积）--")
    calc_res = A_RES * R_RES
    calc_com = A_COM * R_COM
    print(f"  住宅 {A_RES:>12,.2f} × {R_RES} = {calc_res:>14,.2f}"
          f"   表写 {INC_RES_T:>14,.2f}"
          f"  {'✓' if abs(calc_res-INC_RES_T) < 1 else f'✗ 差 {calc_res-INC_RES_T:+,.2f}'}")
    print(f"  商业 {A_COM:>12,.2f} × {R_COM} = {calc_com:>14,.2f}"
          f"   表写 {INC_COM_T:>14,.2f}"
          f"  {'✓' if abs(calc_com-INC_COM_T) < 1 else f'✗ 差 {calc_com-INC_COM_T:+,.2f}'}")
    print(f"  小计 {calc_res+calc_com:>28,.2f}"
          f"   表写 {INC_SUB_T:>14,.2f}"
          f"  {'✓' if abs(calc_res+calc_com-INC_SUB_T) < 2 else '✗'}")
    print(f"  面积校验 {A_RES:,.2f} + {A_COM:,.2f} = {A_RES+A_COM:,.2f}"
          f"   表写 {A_TOT:,.2f}"
          f"  {'✓' if abs(A_RES+A_COM-A_TOT) < 0.01 else f'✗ 差 {A_TOT-A_RES-A_COM:+,.2f}'}")

    # ---------- 2. 支出表：三种读法 ----------
    s8 = sum(EXP8.values())
    print(f"\n-- 2. 支出表读法判别（1..8 项之和 = {s8:,.2f}）--")
    print(f"  用户说第 9 项金额 = {BASE_T:,.2f}（= 管理费 × 10）")
    readings = {
        "读法 A：合计行 = 1..8 的和（第 9 项是同值汇总行）":
            ("base", s8),
        "读法 B：合计行 = 第 9 项独立项（与 1..8 相加）":
            ("sum", s8 + BASE_T),
        "读法 C：合计行 = 基数，1..8 是它的明细（有重复列示）":
            ("base", BASE_T),
    }
    print(f"  {'读法':<52}{'基数':>15}{'管理费(10%)':>14}"
          f"{'税金':>13}{'月合计':>15}")
    for nm, (_, base) in readings.items():
        mg = base * 0.10
        tx = base * 0.0672
        print(f"  {nm:<52}{base:>15,.2f}{mg:>14,.2f}{tx:>13,.2f}"
              f"{base+mg+tx:>15,.2f}")

    # 用表值反推，判定哪一种是表内实际用的
    print(f"\n  表内实际值：基数 {BASE_T:,.2f}｜管理费 {MGMT_T:,.2f}"
          f"｜税金 {TAX_T:,.2f}｜月合计 {MONTH_T:,.2f}")
    print(f"  校验管理费 = 基数 × 10%：{BASE_T*0.10:,.2f} vs {MGMT_T:,.2f}"
          f"  {'✓' if abs(BASE_T*0.10-MGMT_T) < 0.5 else '✗'}")
    print(f"  校验月合计 = 基数+管理费+税金："
          f"{BASE_T+MGMT_T+TAX_T:,.2f} vs {MONTH_T:,.2f}"
          f"  {'✓' if abs(BASE_T+MGMT_T+TAX_T-MONTH_T) < 0.5 else '✗'}")
    print(f"  ★ 税金 {TAX_T:,.2f} 对不上 6.72%："
          f"基数×6.72% = {BASE_T*0.0672:,.2f}（差 {TAX_T-BASE_T*0.0672:+,.2f}）")
    print(f"    但对得上**物业费收入**×6.72%：{INC_SUB_T*0.0672:,.2f}"
          f"  {'✓' if abs(INC_SUB_T*0.0672-TAX_T) < 0.5 else '✗'}")
    print(f"    ⇒ ★★ **税金按收入计，管理费按成本基数计** —— 两者基数不同")

    # ---------- 3. 支出月费用（利润行）的构成 ----------
    print(f"\n-- 3. 利润行的「支出月费用」= {MONTH_PAY_T:,.2f} 是怎么来的 --")
    print(f"  支出表月合计      {MONTH_T:>14,.2f}")
    print(f"  地库总计          {GARAGE['总计']:>14,.2f}")
    print(f"  两者之和          {MONTH_T+GARAGE['总计']:>14,.2f}"
          f"  {'✓ 与利润行一致' if abs(MONTH_T+GARAGE['总计']-MONTH_PAY_T) < 0.5 else '✗'}")
    print(f"  而利润行写        {MONTH_PAY_T:>14,.2f}"
          f"  ⇒ 差 {MONTH_PAY_T-(MONTH_T+GARAGE['总计']):+,.2f}")
    print(f"  ★ 即：**地库支出是加在支出表之外的**（或表内另有 68 162.53 的项目）")

    # ---------- 4. 利润恒等式 ----------
    print(f"\n-- 4. 利润恒等式 --")
    print(f"  收入 {INC_ALL_T:,.2f} − 支出 {MONTH_PAY_T:,.2f} = "
          f"**{INC_ALL_T-MONTH_PAY_T:,.2f}**")
    print(f"  表给利润 {PROFIT_T:,.2f}"
          f"  ⇒ 差 {INC_ALL_T-MONTH_PAY_T-PROFIT_T:+,.2f} 元/月"
          f"（年 {(INC_ALL_T-MONTH_PAY_T-PROFIT_T)*12:+,.2f}）")
    print(f"  ★ 用户说利润「就是收入与支出的差」⇒ 那么差额 "
          f"{INC_ALL_T-MONTH_PAY_T-PROFIT_T:+,.2f} 无处安放，")
    print(f"    除非 收入 或 支出 中有一个我读错。")
    # 反推：若利润是差，则支出应为多少
    print(f"  反推：若利润 = {PROFIT_T:,.2f}，则支出应 = "
          f"{INC_ALL_T-PROFIT_T:,.2f}（表写 {MONTH_PAY_T:,.2f}）")

    # ---------- 5. ★★ 单位经济学（这才是本题的核心） ----------
    print(f"\n-- 5. ★★ 单位经济学（用确认面积）--")
    unit_inc_fee = INC_SUB_T / A_TOT
    unit_inc_all = INC_ALL_T / A_TOT
    unit_cost = MONTH_PAY_T / A_TOT
    print(f"  收费面积 {A_TOT:,.2f} ㎡｜户数 {H_HH}")
    print(f"  户均建面 {A_RES/H_HH:,.1f} ㎡（住宅口径）")
    print(f"  每户年物业费 {INC_SUB_T*12/H_HH:,.0f} 元 ⇒ 月 "
          f"{INC_SUB_T/H_HH:,.1f} 元")
    print()
    print(f"  单位物业费收入 {unit_inc_fee:>8.4f} 元/㎡·月")
    print(f"  单位总收入     {unit_inc_all:>8.4f} 元/㎡·月")
    print(f"  单位成本       {unit_cost:>8.4f} 元/㎡·月")
    print(f"  ⇒ ★ **物业费单项**：{unit_inc_fee-unit_cost:+.4f} 元/㎡·月"
          f"（占收费 {(unit_inc_fee-unit_cost)/unit_inc_fee*100:+.2f}%）")
    print(f"     **含停车后**：  {unit_inc_all-unit_cost:+.4f} 元/㎡·月"
          f"（占收入 {(unit_inc_all-unit_cost)/unit_inc_all*100:+.2f}%）")
    print()
    print(f"  ★ 与住宅单价 4.91 比较：成本是单价的 "
          f"{unit_cost/R_RES*100:,.1f}%")
    print(f"  ★ 单位缺口（成本 − 住宅单价）= {unit_cost-R_RES:+.4f} 元/㎡·月")
    print(f"     × 282 289.39 ㎡ × 12 = 年缺口 "
          f"{(unit_cost-R_RES)*A_TOT*12:+,.0f} 元")

    print(f"\n-- 6. 业态贡献（关键：谁在补贴谁）--")
    direct = MONTH_PAY_T - MGMT_T - TAX_T          # 扣除分摊项后的直接成本
    print(f"  支出月费用 {MONTH_PAY_T:,.2f} − 管理费 {MGMT_T:,.2f}"
          f" − 税金 {TAX_T:,.2f} = 直接成本 {direct:,.2f}")
    # 按面积分摊直接成本；地库单独
    d_garage = GARAGE["总计"] - GARAGE["管理费"] - GARAGE["税金"]
    d_rest = direct - d_garage
    share_res = A_RES / A_TOT
    print(f"  地库直接成本（能耗）{d_garage:,.2f}；其余 {d_rest:,.2f}")
    rows = [
        ("住宅", INC_RES_T, d_rest * share_res),
        ("商业", INC_COM_T, d_rest * (A_COM / A_TOT)),
        ("地库", INC_PARK_T, d_garage),
    ]
    print(f"  {'业态':<6}{'收入/月':>14}{'直接成本/月':>14}"
          f"{'净贡献/月':>14}{'净贡献/年':>16}{'占收入':>9}")
    tot = 0.0
    for nm, i, c in rows:
        net = i - c
        tot += net
        print(f"  {nm:<6}{i:>14,.0f}{c:>14,.0f}{net:>14,.0f}"
              f"{net*12:>16,.0f}{net/i*100 if i else 0:>8.1f}%")
    print(f"  {'合计':<6}{sum(r[1] for r in rows):>14,.0f}"
          f"{sum(r[2] for r in rows):>14,.0f}{tot:>14,.0f}"
          f"{tot*12:>16,.0f}")
    print(f"  再扣管理费+税金 {MGMT_T+TAX_T:,.0f} ⇒ "
          f"**{tot-MGMT_T-TAX_T:,.0f} 元/月**"
          f"（表给利润 {PROFIT_T:,.0f}）")
    print()
    print(f"  ★★ 核心发现：**住宅物业费 {INC_RES_T:,.0f} 元/月，"
          f"分摊直接成本 {d_rest*share_res:,.0f}**")
    print(f"     ⇒ 住宅净贡献 {INC_RES_T-d_rest*share_res:+,.0f} 元/月")

    res = {
        "_口径": "面积用用户核对值；支出列单位为元",
        "面积": {"住宅": A_RES, "商业": A_COM, "合计": A_TOT},
        "收入_元每月": {"住宅物业费": INC_RES_T, "商业物业费": INC_COM_T,
                    "物业费小计": INC_SUB_T, "停车费": INC_PARK_T,
                    "合计": INC_ALL_T},
        "收入自洽": {"住宅": abs(calc_res - INC_RES_T) < 1,
                 "商业": abs(calc_com - INC_COM_T) < 1,
                 "面积": abs(A_RES + A_COM - A_TOT) < 0.01},
        "单位": {"物业费收入": unit_inc_fee, "总收入": unit_inc_all,
               "成本": unit_cost,
               "物业费净额": unit_inc_fee - unit_cost,
               "含停车净额": unit_inc_all - unit_cost,
               "住宅单价": R_RES},
        "户均": {"建面": A_RES / H_HH,
               "年物业费": INC_SUB_T * 12 / H_HH,
               "月物业费": INC_SUB_T / H_HH},
        "利润恒等式差额": INC_ALL_T - MONTH_PAY_T - PROFIT_T,
        "_遗留不一致": [
            f"利润：{INC_ALL_T:,.2f} − {MONTH_PAY_T:,.2f} = "
            f"{INC_ALL_T-MONTH_PAY_T:,.2f}，表给 {PROFIT_T}",
            f"税金基数：{BASE_T}×6.72% = {BASE_T*0.0672:,.2f}，"
            f"表给 {TAX_T}（等于物业费收入×6.72%）",
            f"支出月合计 {MONTH_T} + 地库 {GARAGE['总计']} = "
            f"{MONTH_T+GARAGE['总计']:,.2f} = 利润行支出 {MONTH_PAY_T}",
        ],
    }
    (OUT / "p0_定稿口径.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  [落盘] {OUT / 'p0_定稿口径.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
