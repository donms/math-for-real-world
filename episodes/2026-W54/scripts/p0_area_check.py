#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W54 探针 P0 · **面积口径判别**（我先前把面积读大了 10 倍）。

## 我错在哪

我把表内「可售建筑面积（㎡）」读成：
住宅 **2 768 666.55** ㎡、合计 **2 822 289.39** ㎡
（= 276.9 万 ㎡ / 282.2 万 ㎡）。

**而用户原话第一句就是：「在苏州，有这么一个改善小区…」，
文章里写的是「一个管着近 1900 户、`28 万平方米`的品牌物业项目」。**

**⇒ 28 万 ㎡，不是 282 万 ㎡。** 我多读了一个数量级。

## 判别：哪个口径能让**四个独立约束同时成立**

| # | 约束 | 来源 |
|---|---|---|
| **A** | 户均建面落在合理区间（120–180 ㎡）| 中国改善型住宅常识 |
| **B** | 面积 × 单价 = 月收入 | 表内收入表 |
| **C** | 物业费月收入 × 12 ≈ 作者说的年收入量级 | 文章 |
| **D** | 单位成本 < 单价（否则利润不可能为正）| 表内支出表 |

**本脚本把两个口径并排算出来，看哪个过全部四条。**
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W54"
OUT = EP / "results"
OUT.mkdir(parents=True, exist_ok=True)

H_HH = 1867
R_RES, R_COM = 4.91, 13.55
INC_RES_T, INC_COM_T, INC_SUB_T = 1359414.76, 73479.48, 1432894.24
INC_PARK_T, INC_ALL_T = 148500, 1583994.24
EXP_ALL_T = 1576960.74
PROFIT_T = 4433.50
YEAR_EXP_T = 18105578.47

# 作者/文章口径
ARTICLE_AREA_WAN = 28.0          # 28 万 ㎡
ARTICLE_INC_WAN = 1900.0         # 一年收近 1900 万
ARTICLE_INC_WAN_LO = 1900.0
ARTICLE_PROFIT = 50000.0         # 一年利润 5 万

CANDS = {
    "口径 ①（我原先误读）：面积 x1000 倍": {
        "A_RES": 2768666.55, "A_COM": 5422.84, "A_TOT": 2822289.39,
    },
    "口径 ②（面积/10）：28 万 ㎡ 级": {
        "A_RES": 276866.655, "A_COM": 5422.84, "A_TOT": 282228.939,
    },
    "口径 ③（面积/10，商业也/10）": {
        "A_RES": 276866.655, "A_COM": 542.284, "A_TOT": 277408.939,
    },
}


def check(nm: str, c: dict) -> dict:
    a_res, a_com, a_tot = c["A_RES"], c["A_COM"], c["A_TOT"]
    print(f"\n{'='*88}\n  {nm}\n{'='*88}")
    print(f"  住宅 {a_res:>14,.3f} ㎡｜商业 {a_com:>10,.3f} ㎡"
          f"｜合计 {a_tot:>14,.3f} ㎡ = {a_tot/1e4:,.2f} 万 ㎡")

    # A 户均建面
    per_hh = a_res / H_HH
    okA = 100 <= per_hh <= 200
    print(f"\n  [A] 户均建面 = {a_res:,.3f} / {H_HH} = **{per_hh:,.1f} ㎡**"
          f"  ⇒ {'✓ 合理（100–200）' if okA else '✗ 不合理'}")

    # B 面积 × 单价 = 月收入
    calc_res = a_res * R_RES
    calc_com = a_com * R_COM
    calc_sub = calc_res + calc_com
    okB = (abs(calc_res - INC_RES_T) < 1.0
           and abs(calc_com - INC_COM_T) < 1.0
           and abs(calc_sub - INC_SUB_T) < 2.0)
    print(f"  [B] 面积 × 单价：")
    print(f"        住宅 {a_res:,.3f} × {R_RES} = {calc_res:>16,.2f}"
          f"   表写 {INC_RES_T:>14,.2f}  "
          f"{'✓' if abs(calc_res-INC_RES_T)<1 else f'✗ 差 {calc_res-INC_RES_T:+,.2f}'}")
    print(f"        商业 {a_com:,.3f} × {R_COM} = {calc_com:>16,.2f}"
          f"   表写 {INC_COM_T:>14,.2f}  "
          f"{'✓' if abs(calc_com-INC_COM_T)<1 else f'✗ 差 {calc_com-INC_COM_T:+,.2f}'}")
    print(f"        小计 {calc_sub:>30,.2f}   表写 {INC_SUB_T:>14,.2f}  "
          f"{'✓' if abs(calc_sub-INC_SUB_T)<2 else f'✗ 差 {calc_sub-INC_SUB_T:+,.2f}'}")
    print(f"        ⇒ 三项全中：{'✓ 口径成立' if okB else '✗ 口径不成立'}")

    # C 年收入量级
    inc_all = INC_SUB_T + INC_PARK_T     # 用表值（与面积无关）
    yr_wan = inc_all * 12 / 1e4
    okC = abs(yr_wan - ARTICLE_INC_WAN) / ARTICLE_INC_WAN < 0.15
    print(f"  [C] 年收入 = {inc_all:,.2f} × 12 = {yr_wan:,.1f} 万元"
          f"   文章说「近 {ARTICLE_INC_WAN:,.0f} 万」  "
          f"{'✓' if okC else '✗'}")

    # D 单位成本 vs 单价
    unit_cost = EXP_ALL_T / a_tot
    # ★ 判据修正：支出表里**已含管理费与税金**，且**收入不只物业费**。
    #   所以正确的比较对象是"单位总收入"，而不是"住宅单价 4.91"。
    unit_inc = INC_ALL_T / a_tot
    unit_inc_fee = INC_SUB_T / a_tot
    okD = unit_cost < unit_inc
    print(f"  [D] 单位成本 = {EXP_ALL_T:,.2f} / {a_tot:,.3f} = "
          f"**{unit_cost:,.4f} 元/㎡·月**")
    print(f"        单位总收入（含停车）= {unit_inc:,.4f}；"
          f"单位物业费收入 = {unit_inc_fee:,.4f}")
    print(f"        vs 住宅单价 {R_RES} ⇒ "
          f"成本是单价 {unit_cost/R_RES*100:,.1f}%")
    print(f"        ⇒ {'✓ 成本 < 单位总收入（利润可正）' if okD else '✗ 成本 > 单位总收入 —— 不可能'}")
    print(f"        ★ 但【物业费单项】{'亏损' if unit_inc_fee < unit_cost else '有盈余'}："
          f"每月 {INC_SUB_T - EXP_ALL_T:+,.2f} 元"
          f"（{INC_SUB_T:,.2f} − {EXP_ALL_T:,.2f}）")
    print(f"          必须靠停车费 {INC_PARK_T:,.2f} 补贴 ⇒ "
          f"补完剩 {INC_SUB_T + INC_PARK_T - EXP_ALL_T:+,.2f} 元"
          f"（表给利润 {PROFIT_T:,.2f}）")

    # 面积口径下的一致性
    print(f"  [附] 住宅+商业 = {a_res+a_com:,.3f} vs 表内合计 {a_tot:,.3f}"
          f"  ⇒ 差 {a_tot-(a_res+a_com):+,.3f}")
    return {"口径": nm, "A_户均建面": per_hh, "A_pass": okA,
            "B_pass": okB, "C_pass": okC, "D_pass": okD,
            "单位成本": unit_cost,
            "全部通过": okA and okB and okC and okD}


def main() -> int:
    print("=" * 88)
    print("  W54 探针 P0 · 面积口径判别（找哪个口径能让四条约束同时成立）")
    print("=" * 88)
    print(f"  户数 {H_HH}｜住宅单价 {R_RES}｜商业单价 {R_COM}")
    print(f"  文章口径：面积 **{ARTICLE_AREA_WAN:.0f} 万 ㎡**、"
          f"年收入近 **{ARTICLE_INC_WAN:.0f} 万**、"
          f"年利润 **{ARTICLE_PROFIT:,.0f} 元**")
    rows = [check(nm, c) for nm, c in CANDS.items()]

    print(f"\n{'='*88}\n  判别汇总\n{'='*88}")
    print(f"  {'口径':<34}{'户均㎡':>9}{'A':>4}{'B':>4}{'C':>4}{'D':>4}"
          f"{'单位成本':>11}  结论")
    for r in rows:
        print(f"  {r['口径']:<34}{r['A_户均建面']:>9,.1f}"
              f"{'✓' if r['A_pass'] else '✗':>4}"
              f"{'✓' if r['B_pass'] else '✗':>4}"
              f"{'✓' if r['C_pass'] else '✗':>4}"
              f"{'✓' if r['D_pass'] else '✗':>4}"
              f"{r['单位成本']:>11,.4f}"
              f"  {'★ 全通过' if r['全部通过'] else '不通过'}")

    win = [r for r in rows if r["全部通过"]]
    print()
    if win:
        print(f"  ⇒ **{win[0]['口径']}** 是唯一让四条约束同时成立的口径。")
        print(f"     户均建面 {win[0]['A_户均建面']:,.1f} ㎡，"
              f"单位成本 {win[0]['单位成本']:,.2f} 元/㎡·月")
        print(f"     单位成本 / 单价 = "
              f"{win[0]['单位成本']/R_RES*100:,.1f}%")
    else:
        print("  ⇒ **没有任何口径全通过** ⇒ 表内还有别的量级问题，需人工核对原图。")

    print("\n  ★★ 我为什么会读错（值得记进踩坑）：")
    print("     表内面积写成 2768666.55 —— **没有千分位分隔**，")
    print("     我按「6 位整数 + 2 位小数」直接读成了 276 万 ㎡。")
    print("     而**文章里就写着「28 万平方米」**，我却没拿它去交叉验证，")
    print("     直到自己算出「单位成本 0.56 元/㎡·月 < 单价 4.91」这个")
    print("     **物理上不可能**的结果，才发现量级错了。")
    print("     ⇒ **教训：算出一个反常识的数时，先怀疑自己的输入，")
    print("       而不是去构造解释。**")

    out = {"判别": rows, "文章口径": {
        "面积_万㎡": ARTICLE_AREA_WAN, "年收入_万元": ARTICLE_INC_WAN,
        "年利润_元": ARTICLE_PROFIT},
        "胜出口径": win[0] if win else None}
    (OUT / "p0_面积口径判别.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  [落盘] {OUT / 'p0_面积口径判别.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
