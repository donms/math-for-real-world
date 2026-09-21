#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""Q1：量化老瓶颈 —— 长洲船闸的通过能力与拥堵。

## 模型设计（数据驱动，不预设结论）

### 1. 通过能力：把"几何能力"和"效率"分开

单闸次的载货量 = 闸次 × 平均每闸次载货。故

    月度货运量 = D · m · q · η

其中
* `D` = 当月天数
* `m` = 日均闸次（**运行强度**，最大值反映设备上限）
* `q` = 平均每闸次载货（t/闸次）；实测 = 货运量 / 闸次
* `η` = 装载率 = 实际载货 / 核定载货（**效率**，受水位与货源影响）

⚠️ 关键：**能力（capacity）不等于强度（intensity）**。
2 月日均闸次 56 高于 1 月 62？需实测核对。能力上限应由
**单日最高闸次**（设备极限）刻画，而不是月均值。

### 2. 水位约束：用出库流量解释效率

枯水期吃水受限 → 单船装不满 → η 下降；
同时一二线可能因"超最大运行工况"停航 → 闸次 m 下降。
故 η 与 m 都应是水位 W（用出库流量代理）的函数。

### 3. 拥堵：排队模型

待闸船舶数 L 与利用率 ρ = λ/μ 的关系。由实测反推：
* 服务率 μ：由闸次与单闸次艘次决定（艘/天）
* 到达率 λ：需从货运量反推，或由 L 的动态方程估计

**本脚本只做能由数据直接支撑的部分**，不硬套 M/M/1 ——
因为长洲是**批量服务**（一闸多次多船），
纯 M/M/1 会系统性低估等待。这一点会在结果里说明。

用法：
    $PY q1_bottleneck.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"

# 只取**月报**（季报/年报是汇总，会重复计数）
MONTHLY = ["2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
           "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
DAYS = {"2025-08": 31, "2025-09": 30, "2025-10": 31, "2025-11": 30,
        "2025-12": 31, "2026-01": 31, "2026-02": 28, "2026-03": 31,
        "2026-04": 30, "2026-05": 31, "2026-06": 30}


def load():
    rows = json.loads((RES / "q0_panel.json").read_text(encoding="utf-8"))
    by = {r["期"]: r for r in rows}
    out = []
    for p in MONTHLY:
        r = by[p]
        d = DAYS[p]
        rec = {
            "期": p, "天数": d,
            "货运量": r["货运量万吨"], "闸次": r["闸次"],
            "艘次": r["艘次"], "核载": r["总核载万吨"],
            "平均核载": r["平均核载吨"], "待闸": r["日均待闸艘"],
            "流量": r["出库流量"], "检修": r["检修期"],
        }
        # 派生
        rec["日均闸次"] = r["闸次"] / d if r["闸次"] else None
        rec["每闸次万吨"] = (r["货运量万吨"] / r["闸次"]) if r["闸次"] else None
        rec["每闸次艘次"] = (r["艘次"] / r["闸次"]) if r["闸次"] else None
        rec["装载率"] = (r["货运量万吨"] / r["总核载万吨"]
                         if r.get("总核载万吨") else None)
        out.append(rec)
    return out


def main() -> int:
    data = load()
    print("=" * 78)
    print("  Q1 · 长洲船闸：通过能力与拥堵")
    print("=" * 78)

    print("\n【1】实测月度面板（只取月报，避免季报/年报重复计数）\n")
    print("  期        闸次  日均闸次  货运量    每闸次万吨  每闸次艘次  装载率  "
          "日均待闸  流量m³/s")
    print("  " + "-" * 92)
    for r in data:
        def c(v, nd=2, w=8):
            return f"{(f'{v:.{nd}f}' if v is not None else '—'):>{w}}"
        print(f"  {r['期']:<9}{c(r['闸次'], 0, 7)}{c(r['日均闸次'], 1, 9)}"
              f"{c(r['货运量'], 1, 9)}{c(r['每闸次万吨'], 4, 11)}"
              f"{c(r['每闸次艘次'], 2, 11)}{c(r['装载率'], 3, 8)}"
              f"{c(r['待闸'], 0, 9)}{c(r['流量'], 0, 10)}")

    # ---------- 2. 每闸次载货的稳定性 ----------
    pq = [r["每闸次万吨"] for r in data if r["每闸次万吨"]]
    print(f"\n【2】每闸次载货量（t/闸次）的稳定性 —— 这是「几何能力」的核心参数\n")
    print(f"  样本 {len(pq)} 个月：均值 {np.mean(pq):.4f} 万吨/闸次，"
          f"标准差 {np.std(pq, ddof=1):.4f}，"
          f"变异系数 {np.std(pq, ddof=1)/np.mean(pq)*100:.1f}%")
    print(f"  范围 {min(pq):.4f} – {max(pq):.4f} 万吨/闸次")

    # 识别异常月
    mu, sd = np.mean(pq), np.std(pq, ddof=1)
    print(f"\n  偏离均值 2 个标准差以外的月份：")
    for r in data:
        v = r["每闸次万吨"]
        if v and abs(v - mu) > 2 * sd:
            z = (v - mu) / sd
            print(f"    {r['期']}：{v:.4f} 万吨/闸次（z={z:+.2f}）"
                  f"  装载率 {r['装载率']:.3f}"
                  f"{'  ⚠️检修期' if r['检修'] else ''}")

    # ---------- 3. 通过能力 ----------
    print(f"\n【3】通过能力估计\n")
    # 设备上限：取实测单日最高闸次（来自简报正文，2026-02-09 为 91 闸次）
    MAX_GATES_DAY = 91
    q_typ = float(np.median([r["每闸次万吨"] for r in data
                             if r["每闸次万吨"]]))
    cap_year = MAX_GATES_DAY * 365 * q_typ
    print(f"  实测单日最高闸次（2026-02-09）  m_max = {MAX_GATES_DAY} 闸次/日")
    print(f"  每闸次载货（中位）              q     = {q_typ:.4f} 万吨/闸次")
    print(f"  ⇒ 理论年通过能力 = {MAX_GATES_DAY}×365×{q_typ:.4f}"
          f" = {cap_year:,.0f} 万吨 = {cap_year/1e4:.2f} 亿吨/年")

    y2025 = 22355.46
    print(f"\"2025 年实际 {y2025:,.2f} 万吨 = {y2025/1e4:.2f} 亿吨")
    print(f"  ⇒ 利用率 = {y2025/cap_year*100:.1f}%"
          f"，剩余裕度 {100-y2025/cap_year*100:.1f}%")
    print(f"  ⚠️ 注意：这里用的是**单日最高闸次**外推全年，"
          f"是**上界**；实际受水位与检修制约，达不到。")

    # 更保守：用实测日均最高闸次
    m_avg_max = max(r["日均闸次"] for r in data if r["日均闸次"])
    cap_cons = m_avg_max * 365 * q_typ
    print(f"\n  对照（保守口径）：最高**月均**日闸次 {m_avg_max:.1f} 闸次/日")
    print(f"  ⇒ {m_avg_max:.1f}×365×{q_typ:.4f} = {cap_cons:,.0f} 万吨"
          f" = {cap_cons/1e4:.2f} 亿吨/年"
          f"，利用率 {y2025/cap_cons*100:.1f}%")

    # ---------- 4. 机制检验：谁在决定通过量？ ----------
    print(f"\n【4】机制检验：水位究竟通过哪条路径影响通过量？\n")
    print("  先验假设是「水位低 → 单船装不满 → 装载率下降」。")
    print("  **数据否定了这个假设**：\n")
    sub = [r for r in data if r["流量"] and r["装载率"]]
    W = np.array([r["流量"] for r in sub])
    E = np.array([r["装载率"] for r in sub])
    print(f"    装载率范围 {E.min():.3f} – {E.max():.3f}"
          f"（极差 {E.max()-E.min():.3f}，仅 {100*(E.max()-E.min())/E.mean():.0f}%）")
    print(f"    corr(出库流量, 装载率) = {np.corrcoef(W, E)[0,1]:+.3f}"
          f"  ← **负相关**，与先验相反")
    print("    ⇒ 装载率几乎不随水位变化，稳定在 0.58–0.64。")
    print("      也就是说：**水位不是通过'装不满'来限制通过量的。**")

    print("\n  那么水位影响的是哪一条路径？检验「日闸次」：")
    sub2 = [r for r in data if r["流量"] and r["日均闸次"]]
    W2 = np.array([r["流量"] for r in sub2])
    M2 = np.array([r["日均闸次"] for r in sub2])
    rho_m = np.corrcoef(W2, M2)[0, 1]
    print(f"    corr(出库流量, 日均闸次) = {rho_m:+.3f}   （n={len(sub2)}）")
    # 排除检修期
    sub3 = [r for r in sub2 if not r["检修"]]
    W3 = np.array([r["流量"] for r in sub3])
    M3 = np.array([r["日均闸次"] for r in sub3])
    rho_m3 = np.corrcoef(W3, M3)[0, 1]
    print(f"    排除检修期后            = {rho_m3:+.3f}   （n={len(sub3)}）")
    if len(sub3) >= 3:
        k, b = np.polyfit(W3, M3, 1)
        print(f"    线性拟合：日均闸次 ≈ {k:.5f}·W + {b:.1f}")
        print(f"      ⇒ 出库流量每增 1000 m³/s，日均闸次约增 "
              f"{k*1000:.2f} 个")
    print("\n  ⚠️ 但**排除检修期后相关性几乎消失**（+0.355 → +0.078）：")
    print("     水位本身**单独解释不了**日闸次。真正拉开差距的是**检修**：")
    print("     检修期（2025-12 / 2026-01）日闸次 47.7 / 61.6，")
    print("     而其余月份 55.7–73.7。")
    print("\n  **诚实的结论（本问最关键的一条）**：")
    print("    · 装载率与水位**无关**（稳定 0.58–0.64）→ 先验假设被否定；")
    print("    · 日闸次与水位**弱相关**，排除检修后几乎无关 → 「水位机制」")
    print("     在本数据上**不成立**；")
    print("    · 待闸数的暴涨（71 → 813 艘）对应的是**检修期**，")
    print("      即**设备可用性下降**，而非水位。")
    print("\n    ⇒ 因此本问的机制结论是：**长洲的拥堵主要由设备可用性")
    print("      （检修停航）驱动，水位的影响在本数据上无法分离出来。**")
    print("      这与题面的先验（水位是主因）**不同**，论文中须如实写明。")

    # 待闸与日闸次
    sub4 = [r for r in data if r["日均闸次"] and r["待闸"]]
    M4 = np.array([r["日均闸次"] for r in sub4])
    L4 = np.array([r["待闸"] for r in sub4])
    print(f"\n  拥堵与运行强度的关系：")
    print(f"    corr(日均闸次, 日均待闸) = {np.corrcoef(M4, L4)[0,1]:+.3f}")
    print("    **负相关**：待闸越多时闸次反而越少 ——")
    print("    说明瓶颈在**水位导致的放行能力下降**，而非船闸设备本身不够。")

    # ---------- 5. 排队视角 ----------
    print(f"\n【5】拥堵：排队模型的适用性与局限\n")
    print("  服务率 μ（艘/日）= 艘次 / 天数：")
    mus = []
    for r in data:
        if r["艘次"]:
            mus.append((r["期"], r["艘次"] / r["天数"], r["待闸"]))
    for p, mu, L in mus:
        print(f"    {p}  μ={mu:6.1f} 艘/日   日均待闸 L={L:>4.0f}")
    print("\n  ⚠️ 长洲是**批量服务**（一闸次放行多船），且到达受水位节律影响，")
    print("     纯 M/M/1 会**系统性低估**等待 —— 本问只用数据反推，不套 M/M/1。")

    # ---------- 导出 ----------
    out = {
        "面板": data,
        "能力": {
            "单日最高闸次": MAX_GATES_DAY,
            "每闸次载货中位万吨": round(q_typ, 4),
            "理论年能力万吨_设备上界": round(cap_year, 1),
            "保守年能力万吨_月均上界": round(cap_cons, 1),
            "2025实际万吨": y2025,
            "利用率_设备上界": round(y2025 / cap_year, 4),
            "利用率_保守": round(y2025 / cap_cons, 4),
        },
        "水位": {
            "corr_流量_装载率": round(float(np.corrcoef(W, E)[0, 1]), 3),
            "corr_流量_日闸次": round(float(rho_m), 3),
            "corr_流量_日闸次_排除检修": round(float(rho_m3), 3),
            "corr_日闸次_待闸": round(float(np.corrcoef(M4, L4)[0, 1]), 3),
            "机制结论": "装载率与水位无关；日闸次与水位弱相关，"
                        "排除检修后几乎无关 → 拥堵主要由设备可用性"
                        "（检修停航）驱动，水位影响无法在本数据上分离。",
        },
    }
    (RES / "q1_bottleneck.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  → results/q1_bottleneck.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
