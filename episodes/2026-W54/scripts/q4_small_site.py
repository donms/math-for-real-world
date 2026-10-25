#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W54 · 问题 4：**小地块会不会更难**（节点驱动成本模型 + 补缺口手段）。

## 对应模型文档

`models/04_小地块会不会更难.md` —— 该文档 §4.7 已**预先写下预期结论**。

## 题面的 6 个小问（本脚本逐条回答）

1. 把成本分解为**面积驱动**与**节点驱动**，并**说明每个科目的归类理由**；
2. 给出 **G(N)**（须体现**台阶性**）；
3. 算 **120 户 / 1.8 万㎡** 地块的**保本单价**与**相对本案溢价**；
4. 若业主**只接受 3.00 元/㎡·月** ⇒ 月缺口 / 年缺口；
5. **不涨价前提下**的补缺口手段，**各能补多少**；
6. **结论**：小地块矛盾会不会更多？主要形态？**何时失效**？

## ★ 关键工程决策：用本案标定

模型直接算会因「支出已含管理费与税金」而**重复计税** ⇒
用实测保本单价 **4.8940** 标定，**只报相对溢价**（见模型文档 §4.6）。

## ★ 用户决策（D4）

* 人员费用按 **50/50** 拆（**不细拆岗位**）；
* 节点 = **门岗 + 电梯 + 消防分区**（**不含监控点位**）；
* 第 4 问给**定量结论**（保本单价 + 溢价率）。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W54"
OUT = EP / "results"
OUT.mkdir(parents=True, exist_ok=True)

TAX = 0.0672            # 税金按收入计（问题 1 已证）
H_HH_CASE = 1867
A_CASE = 282289.39
A_RES_CASE = 276866.55
E_CASE = 1576960.74
P0 = 4.91               # 本案名义单价
P_STAR_CASE = 4.893987  # 本案保本单价（问题 3 已算）
I_PARK_CASE = 148500.00
I_COM_CASE = 73479.48

# 本案支出明细 + 节点占比（见模型文档 §4.3 的理由）
EXP: dict[str, tuple[float, float, str]] = {
    "人员费用": (1019116.76, 0.50,
             "混合：保洁/客服/绿化随面积；门岗/监控/管理岗随节点"),
    "公共设施维护费": (107790.00, 0.75, "电梯/水泵/消防设备台数驱动"),
    "清洁卫生费": (88085.83, 0.10, "★ 最典型的面积驱动项"),
    "绿化养护费": (36405.33, 0.75, "绿地面积固定，与户数弱相关"),
    "秩序维护费": (9400.00, 0.95, "★ 纯节点（出入口岗）"),
    "行政办公费": (22200.00, 0.90, "项目管理团队按小区配置"),
    "固定资产折旧": (3500.00, 1.00, "设备已按节点配置，纯节点"),
    "公众责任险费": (1100.00, 0.85, "按建筑规模投保，近节点"),
}
MGMT = 128409.79        # 管理费分摊（短期刚性 ⇒ 归节点侧）
A_HH = A_RES_CASE / H_HH_CASE     # 户均建面 ≈ 148.29 ㎡
N_SMALL = 120           # 题面：1.8 万㎡ / 148.29 ≈ 121 户，题面取 120
A_SMALL = 18000.0
P_ACCEPT = 3.00         # 题面：业主只接受 3.00 元/㎡·月


# ---------------- 节点函数 ----------------
def gates(n: float) -> float:
    r"""门岗数（台阶函数）。依据：用户实证（100 户 1 门岗）+ 行业惯例。"""
    if n <= 300:
        return 1.0
    if n <= 800:
        return 2.0
    if n <= 1500:
        return 3.0
    if n <= 2500:
        return 4.0
    return 4.0 + math.ceil((n - 2500) / 1000)


def elevators(n: float) -> float:
    r"""电梯台数：约 30 户 1 台，至少 2 台。"""
    return max(2.0, math.ceil(n / 30))


def fire_zones(n: float) -> float:
    r"""消防值班单元：≤500 户 1 个，之后每 1000 户 +1。"""
    return 1.0 if n <= 500 else 1.0 + (n - 500) / 1000


def nodes(n: float) -> float:
    return gates(n) + elevators(n) + fire_zones(n)


def main() -> int:
    print("=" * 96)
    print("  W54 · 问题 4：小地块会不会更难")
    print("=" * 96)

    # ---------------- 小问 1：两类成本 ----------------
    print("\n" + "=" * 96)
    print("  【小问 1】把成本分解为面积驱动与节点驱动（含归类理由）")
    print("=" * 96)
    print("  判据：**这一项的成本动因是「要照看的面积」，还是「要值守的设施」？**\n")
    print(f"  {'科目':<14}{'金额/月':>13}{'节点占比':>9}"
          f"{'节点部分':>13}{'面积部分':>13}  理由")
    node_direct = area_direct = 0.0
    rows1 = []
    for k, (v, share, why) in EXP.items():
        nv, av = v * share, v * (1 - share)
        node_direct += nv
        area_direct += av
        rows1.append({"科目": k, "金额": v, "节点占比": share,
                      "节点部分": nv, "面积部分": av, "理由": why})
        print(f"  {k:<14}{v:>13,.0f}{share:>9.2f}{nv:>13,.0f}"
              f"{av:>13,.0f}  {why}")
    print(f"  {'管理费分摊':<14}{MGMT:>13,.0f}{1.00:>9.2f}"
          f"{MGMT:>13,.0f}{0:>13,.0f}  总部提成，短期刚性")
    node_total = node_direct + MGMT
    total_side = node_total + area_direct
    print(f"  {'合计':<14}{node_total+area_direct:>13,.0f}"
          f"{node_total/total_side:>9.2f}{node_total:>13,.0f}"
          f"{area_direct:>13,.0f}")
    print(f"\n  ⇒ ★★ **节点驱动 {node_total:,.0f} 元/月"
          f"（占 {node_total/total_side*100:.1f}%）**")
    print(f"     **面积驱动 {area_direct:,.0f} 元/月"
          f"（占 {area_direct/total_side*100:.1f}%）**")
    print(f"\n  ★ 敏感项说明：只有「人员费用」的 50/50 是主观的，")
    print(f"     其余科目要么纯面积（清洁卫生 0.10）、要么纯节点（秩序维护 0.95）")
    print(f"     ⇒ 敏感性分析只需动「人员费用」的比例（见本脚本末节）")

    # ---------------- 小问 2：G(N) ----------------
    print("\n" + "=" * 96)
    print("  【小问 2】节点函数 G(N)（须体现台阶性）")
    print("=" * 96)
    print("  G(N) = g(N)[门岗] + e(N)[电梯] + f(N)[消防分区]")
    print("    g(N): ≤300→1, ≤800→2, ≤1500→3, ≤2500→4, 之后每 1000 户 +1")
    print("    e(N): max(2, ⌈N/30⌉)")
    print("    f(N): ≤500→1, 之后每 1000 户 +1\n")
    print(f"  {'户数':>7}{'门岗':>7}{'电梯':>8}{'消防':>8}{'节点合计':>10}"
          f"{'节点/户':>10}{'建面(㎡)':>12}")
    base_g = nodes(H_HH_CASE)
    for n in (60, 100, 120, 200, 300, 500, 800, 1200, 1867, 3000):
        g, e, f = gates(n), elevators(n), fire_zones(n)
        print(f"  {n:>7}{g:>7.1f}{e:>8.1f}{f:>8.2f}{g+e+f:>10.1f}"
              f"{(g+e+f)/n:>10.4f}{A_HH*n:>12,.0f}")
    print(f"\n  ⇒ ★★ **台阶性的后果**：")
    print(f"     · **台阶内部**（户数增但节点不变）⇒ **边际成本 = 0**")
    print(f"     · **台阶边界**（要加一个门岗）⇒ **一次跳一个整岗**")
    print(f"     ⇒ C(N) 是**分段线性、斜率为阶梯**的函数，")
    print(f"       比光滑的 N^α **剧烈得多**")
    print(f"  ⇒ 本案（{H_HH_CASE} 户）节点 **{base_g:.1f}** 个；"
          f"120 户地块节点 **{nodes(N_SMALL):.1f}** 个")
    print(f"     节点/户：本案 {base_g/H_HH_CASE:.4f} vs 120 户 "
          f"{nodes(N_SMALL)/N_SMALL:.4f}"
          f"（**放大 {nodes(N_SMALL)/N_SMALL/(base_g/H_HH_CASE):.2f} 倍**）")

    # ---------------- 单位化 + 标定 ----------------
    c_A = area_direct / A_CASE                 # 元/㎡·月
    c_N = node_total / base_g                  # 元/月·节点
    print(f"\n  -- 单位化 --")
    print(f"  c_A（单位面积成本）= {area_direct:,.2f} / {A_CASE:,.2f} = "
          f"**{c_A:.4f} 元/㎡·月**")
    print(f"  c_N（单位节点成本）= {node_total:,.2f} / {base_g:.1f} = "
          f"**{c_N:,.2f} 元/月·节点**")

    # 标定：让 C(1867)/(a·N) 与实测保本单价一致
    C0 = A_CASE * c_A + base_g * c_N
    raw0 = C0 / A_CASE
    kappa = P_STAR_CASE / raw0
    print(f"\n  -- ★ 标定（消除「支出已含税金」的重复计税）--")
    print(f"  模型原值 C(N0)/(a·N0) = {raw0:.4f}；实测保本单价 = "
          f"{P_STAR_CASE:.4f}")
    print(f"  ⇒ 标定系数 κ = **{kappa:.4f}**")

    def C(n: float) -> float:
        return A_HH * n * c_A + nodes(n) * c_N

    def p_star(n: float) -> float:
        r"""保本单价：收入需覆盖成本 + 税金（按收入计）。

        用标定后的成本，并**只报溢价**（见模型文档 §4.6）。
        """
        return kappa * C(n) / (A_HH * n)

    # ---------------- 小问 3：保本单价与溢价 ----------------
    print("\n" + "=" * 96)
    print("  【小问 3】120 户地块的保本单价与相对本案溢价")
    print("=" * 96)
    print(f"  {'户数':>7}{'建面(㎡)':>11}{'节点数':>8}{'月成本':>13}"
          f"{'保本单价':>11}{'相对本案溢价':>15}")
    curve = []
    for n in (60, 100, 120, 200, 300, 500, 800, 1200, 1867, 3000):
        ps = p_star(n)
        prem = ps / P_STAR_CASE - 1
        curve.append({"户数": n, "建面": A_HH * n, "节点数": nodes(n),
                      "月成本": C(n), "保本单价": ps, "溢价": prem})
        star = " ★" if n == N_SMALL else ""
        print(f"  {n:>7}{A_HH*n:>11,.0f}{nodes(n):>8.1f}{C(n):>13,.0f}"
              f"{ps:>11.3f}{prem*100:>14.1f}%{star}")
    ps120 = p_star(N_SMALL)
    prem120 = ps120 / P_STAR_CASE - 1
    print(f"\n  ⇒ ★★ **120 户地块：保本单价 {ps120:.3f} 元/㎡·月，"
          f"相对本案溢价 {prem120*100:+.1f}%**")
    print(f"     （本案保本单价 {P_STAR_CASE:.3f}，现行名义单价 {P0}）")

    # ---------------- 小问 4：缺口 ----------------
    print("\n" + "=" * 96)
    print("  【小问 4】若业主只接受 3.00 元/㎡·月，缺口多大")
    print("=" * 96)
    print(f"  接受单价 {P_ACCEPT:.2f}；保本单价 {ps120:.3f}")
    gap_u = ps120 - P_ACCEPT
    gap_m = gap_u * A_SMALL / kappa      # 名义月收入缺口（未含税金调整）
    print(f"  单位缺口 = {ps120:.3f} − {P_ACCEPT:.2f} = "
          f"**{gap_u:+.3f} 元/㎡·月**")
    print(f"  按月收入口径（不调税金）：{gap_u:+.3f} × {A_SMALL:,.0f} = "
          f"**{gap_u*A_SMALL:+,.2f} 元/月**")
    print(f"  ★ 但税金按收入计 ⇒ 实际需覆盖 {P_ACCEPT:.2f}×(1−{TAX}) 口径：")
    print(f"     实收净额 = {P_ACCEPT:.2f} × {A_SMALL:,.0f} × "
          f"(1−{TAX}) = {P_ACCEPT*A_SMALL*(1-TAX):,.2f} 元/月")
    print(f"     成本     = κ × C(120) = {kappa*C(N_SMALL):,.2f} 元/月")
    gap_real = P_ACCEPT * A_SMALL * (1 - TAX) - kappa * C(N_SMALL)
    print(f"     ⇒ **缺口 {gap_real:+,.2f} 元/月**"
          f"（年 **{gap_real*12/1e4:+,.1f} 万元**）")
    print(f"  ⇒ ★ 若只看表内数：按 {P_ACCEPT:.2f} 元收，"
          f"月亏 **{abs(gap_real):,.0f} 元**")

    # ---------------- 小问 5：补缺口手段 ----------------
    print("\n" + "=" * 96)
    print("  【小问 5】不涨价前提下的补缺口手段（各能补多少）")
    print("=" * 96)
    need = -gap_real
    print(f"  待补缺口：**{need:,.0f} 元/月**（年 {need*12/1e4:,.1f} 万元）\n")
    means = []

    # ① 减节点
    save1 = c_N * kappa        # 少一个节点省下的月成本（标定后）
    means.append({"手段": "① 减节点（如通道改无人值守 ⇒ 门岗 2→1）",
                  "月补": save1,
                  "依据": "用户实证：其小区 100 户已把 2 条通道改无人值守"})
    print(f"  ① **减节点**：单位节点成本 {c_N:,.0f} 元/月 × κ = "
          f"**{save1:,.0f} 元/月·节点**")
    print(f"     120 户地块门岗 2 个 ⇒ 若降到 1 个，可补 "
          f"**{save1:,.0f} 元/月**（占缺口 {save1/need*100:.1f}%）")

    # ② 提高车位/经营收入
    park_per_hh = I_PARK_CASE / H_HH_CASE
    save2 = park_per_hh * N_SMALL
    means.append({"手段": "② 提高车位/经营收入（按本案密度）",
                  "月补": save2,
                  "依据": f"本案车位收入密度 {park_per_hh:.1f} 元/户·月"})
    print(f"\n  ② **车位/经营收入**：本案密度 {park_per_hh:.1f} 元/户·月"
          f"（{I_PARK_CASE:,.0f} / {H_HH_CASE}）")
    print(f"     120 户 ⇒ **{save2:,.0f} 元/月**（占缺口 "
          f"{save2/need*100:.1f}%）")
    print(f"     ★ 但**小地块车位往往更少**（地块小、车位配比低）")
    print(f"       若按 0.5 倍计 ⇒ {save2*0.5:,.0f} 元/月")

    # ③ 连片打包
    n_pack = 8
    print(f"\n  ③ **连片打包**：把 {n_pack} 个 120 户小地块合并管理")
    print(f"     合并后总户数 = {N_SMALL*n_pack} 户 ⇒ 节点数 "
          f"{nodes(N_SMALL*n_pack):.1f}（vs 分散 {nodes(N_SMALL)*n_pack:.1f}）")
    save3 = (nodes(N_SMALL) * n_pack - nodes(N_SMALL * n_pack)) * c_N * kappa
    means.append({"手段": f"③ 连片打包（{n_pack} 个合并）", "月补": save3,
                  "依据": "上海杨浦 12 个小区打包成 11.2 万㎡，"
                        "物业费 0.18→0.80，超七成同意"})
    print(f"     ⇒ 节省 **{save3:,.0f} 元/月**（占缺口 "
          f"{save3/need*100:.1f}%）")
    print(f"     即每个地块分摊 **{save3/n_pack:,.0f} 元/月**")

    # ④ 降标
    # ★★ 我第一版错在哪（记下来）：
    #   我用了**本案全小区**的面积驱动成本 `area_direct`（1 022 466 元/月）
    #   去算 120 户地块的降标收益 ⇒ 得出「降标 20% 可补 122 490 元/月」，
    #   **而该地块的总成本才 107 755 元/月** ⇒ 补的比花的还多，明显失真。
    #   ⇒ 修法：**降标只作用在该地块自己的面积驱动成本上**：
    #          c_A × 该地块建面 × 降幅 × κ
    print("\n  ④ **降标**（降服务频次）：按**该地块自己的**面积成本压缩")
    small_area_cost = c_A * A_SMALL * kappa
    print(f"     该地块面积驱动成本 = {c_A:.4f} × {A_SMALL:,.0f} × "
          f"{kappa:.4f} = {small_area_cost:,.0f} 元/月")
    print(f"     ★ 不能用本案全小区的 {area_direct:,.0f} 元/月 —— 那是 "
          f"{H_HH_CASE} 户的")
    for r in (0.10, 0.20):
        save4 = small_area_cost * r
        means.append({"手段": f"④ 降标（该地块面积成本 -{r*100:.0f}%）",
                      "月补": save4,
                      "依据": f"该地块面积驱动成本 {small_area_cost:,.0f} "
                            f"元/月 × {r*100:.0f}%"})
        print(f"     -{r*100:.0f}% ⇒ **{save4:,.0f} 元/月**"
              f"（占缺口 {save4/need*100:.1f}%）")

    # 汇总
    print(f"\n  -- ★★ 手段汇总（按月补缺口能力）--")
    print(f"  {'手段':<44}{'月补(元)':>12}{'占缺口':>9}")
    for m in sorted(means, key=lambda x: -x["月补"]):
        print(f"  {m['手段'][:42]:<44}{m['月补']:>12,.0f}"
              f"{m['月补']/need*100:>8.1f}%")
    tot_all = sum(m["月补"] for m in means)
    print(f"  {'合计（全部手段叠加）':<44}{tot_all:>12,.0f}"
          f"{tot_all/need*100:>8.1f}%")
    print(f"\n  ⇒ ★ **单靠①减节点补不满；而①+③（打包）是最现实的组合**")
    print(f"     · ①（减 1 个门岗）{save1:,.0f} + ③（8 个打包分摊）"
          f"{save3/n_pack:,.0f} = **{save1+save3/n_pack:,.0f} 元/月**"
          f"（占缺口 {(save1+save3/n_pack)/need*100:.0f}%）")

    # ---------------- 小问 6：结论 ----------------
    print("\n" + "=" * 96)
    print("  【小问 6】结论：小地块的矛盾会不会更多")
    print("=" * 96)
    print(f"  **会，而且难点是结构性的 —— 不是「经营不好」，是「小到算不过账」。**\n")
    print(f"  ① 成本里 **{node_total/total_side*100:.0f}%** 是节点驱动"
          f"（门岗/消防/电梯），")
    print(f"     其最小单位是**「一个岗」「一个分区」「一台电梯」**，"
          f"**不是户数**；")
    print(f"  ② ⇒ **户均成本随户数下降而上升**，"
          f"且**保本单价随之上升**：")
    for c in curve:
        if c["户数"] in (120, 300, 1867):
            print(f"       {c['户数']:>5} 户 ⇒ 保本 "
                  f"{c['保本单价']:>6.3f}（溢价 {c['溢价']*100:>+6.1f}%）")
    print(f"  ③ 若业主只接受 {P_ACCEPT:.2f} 元 ⇒ **月亏 "
          f"{abs(gap_real):,.0f} 元（年 {abs(gap_real)*12/1e4:.0f} 万）**")
    print(f"  ④ ⇒ **出路只有四条**（按现实可行性排序）：")
    print(f"     (a) ★ **连片打包**（上海杨浦 12 个小区打包、物业费涨 4.4 倍、"
          f"超七成同意）")
    print(f"     (b) ★ **降标**（用户小区已在做：2 条通道改无人值守）")
    print(f"     (c) **涨价**（业主通常不接受 —— 本案诉求是降 51%）")
    print(f"     (d) **撤场**（极端情形）")
    print(f"  ⑤ ⇒ ★★ **所以「矛盾会不会更多」的答案是：会 —— 但主要形态是")
    print(f"     「降标」与「打包」，而不是简单的「撤场」。**")
    print(f"     而**「降标」本身就是投诉源**：")
    print(f"     服务差了 ⇒ 业主不满 ⇒ 拒缴 ⇒ 更差（上海虹桥镇那篇的标题就是")
    print(f"     「小区小→物业费低→服务差，恶性循环」）。")

    print(f"\n  ★★ **失效条件（结论在什么情况下不成立）**：")
    fails = [
        "单价能显著高于 3.00（高端定位、业主接受溢价）⇒ 结论不成立",
        "地块虽小但车位充足或有商业配套 ⇒ 收入侧能补缺口",
        "政府提供补贴或托底（上海老旧小区有政府投入）⇒ 结论不成立",
        "节点数能进一步压缩（无人化、远程值守）⇒ 缺口收窄",
        "多个小地块已被打包管理（共享管理班子）⇒ 退化为大项目问题",
    ]
    for i, f in enumerate(fails, 1):
        print(f"     {i}. {f}")
    print(f"\n  ★★ **与本案（问题 1–3）的呼应是本问最要紧的一层**：")
    print(f"     本案 1 867 户的保本收缴率已经 **99.67%**（问题 3）")
    print(f"     ⇒ 120 户的保本单价还要再高 **{prem120*100:.0f}%**")
    print(f"     ⇒ **它的保本收缴率只会更高** ⇒ **小地块更难，是同一机制的两个刻度。**")

    # ---------------- 敏感性（人员费用拆分比例） ----------------
    print("\n" + "=" * 96)
    print("  【敏感性】「人员费用」节点占比 0.30–0.70 对溢价的影响")
    print("=" * 96)
    print("  （这是本模型唯一主观的拆分；用户决策 D4-① 定为 0.50）")
    print("  ★ 本节的「溢价」是**同一拆分比例下 120 户 vs 本案**的比，")
    print("     因此**不需要标定系数**（标定会两边同时约掉）。\n")
    print(f"  {'人员节点占比':>13}{'节点成本占比':>13}{'本案保本(未标定)':>17}"
          f"{'120户保本(未标定)':>18}{'溢价':>9}")
    sens = []
    for pr in (0.30, 0.40, 0.50, 0.60, 0.70):
        nd = sum(v * (pr if k == "人员费用" else s)
                 for k, (v, s, _w) in EXP.items()) + MGMT
        ad = sum(v * (1 - (pr if k == "人员费用" else s))
                 for k, (v, s, _w) in EXP.items())
        ca2 = ad / A_CASE                 # 元/㎡·月
        cn2 = nd / base_g                 # 元/月·节点

        def C2(n: float) -> float:
            return A_HH * n * ca2 + nodes(n) * cn2

        raw_case = C2(H_HH_CASE) / A_CASE          # 本案的单位成本
        raw_120 = C2(N_SMALL) / (A_HH * N_SMALL)   # 120 户的单位成本
        prem2 = raw_120 / raw_case - 1
        sens.append({"人员节点占比": pr, "节点成本占比": nd / (nd + ad),
                     "本案保本_未标定": raw_case,
                     "120户保本_未标定": raw_120, "溢价": prem2})
        print(f"  {pr:>13.2f}{nd/(nd+ad):>13.3f}{raw_case:>17.4f}"
              f"{raw_120:>18.4f}{prem2*100:>8.1f}%")
    lo, hi = sens[0], sens[-1]
    print(f"\n  ⇒ ★ **溢价率对拆分比例敏感，但方向完全不变**：")
    print(f"     · 最保守（人员节点占比 {lo['人员节点占比']:.2f}，"
          f"节点成本占比 {lo['节点成本占比']*100:.1f}%）⇒ 溢价 "
          f"**{lo['溢价']*100:+.1f}%**")
    print(f"     · 用户决策（0.50）⇒ 溢价 **"
          f"{next(s['溢价'] for s in sens if s['人员节点占比']==0.50)*100:+.1f}%**")
    print(f"     · 最激进（{hi['人员节点占比']:.2f}）⇒ 溢价 "
          f"**{hi['溢价']*100:+.1f}%**")
    print(f"  ⇒ **「户数越小越难」在 0.30–0.70 全区间成立。**")

    # ---------------- 落盘 ----------------
    res = {
        "_来源": "问题 1–3 的定稿口径 + 题面给定的 120 户地块",
        "_用户决策": {"人员费用拆分": "50/50（D4-①）",
                   "节点口径": "门岗+电梯+消防分区（不含监控，D4-②）",
                   "结论形态": "定量（D4-③）"},
        "小问1_两类成本": {
            "科目": rows1, "节点驱动_月": node_total,
            "面积驱动_月": area_direct,
            "节点占比": node_total / total_side,
            "判据": "成本动因是「要照看的面积」还是「要值守的设施」",
        },
        "小问2_节点函数": {
            "G(N)": "g(N)+e(N)+f(N)",
            "g_门岗": "≤300→1, ≤800→2, ≤1500→3, ≤2500→4, 之后每1000户+1",
            "e_电梯": "max(2, ceil(N/30))",
            "f_消防": "≤500→1, 之后每1000户+1",
            "台阶性后果": ["台阶内部边际成本=0",
                       "台阶边界一次跳一个整岗"],
            "本案节点数": base_g, "120户节点数": nodes(N_SMALL),
        },
        "单位化与标定": {"c_A_元每m2月": c_A, "c_N_元每月每节点": c_N,
                    "模型原值": raw0, "实测保本单价": P_STAR_CASE,
                    "标定系数κ": kappa,
                    "_说明": "标定用于消除「支出已含税金」的重复计税；"
                           "只报相对溢价"},
        "小问3_保本单价曲线": curve,
        "小问3_120户": {"保本单价": ps120, "溢价": prem120},
        "小问4_缺口": {
            "接受单价": P_ACCEPT,
            "单位缺口": gap_u,
            "月缺口_实收净额口径": gap_real,
            "年缺口": gap_real * 12,
        },
        "小问5_补缺口手段": {
            "待补缺口_月": need, "手段": means,
            "合计": tot_all,
            "推荐组合": {"①减节点": save1, "③打包分摊": save3 / n_pack,
                     "合计": save1 + save3 / n_pack,
                     "占缺口": (save1 + save3 / n_pack) / need},
        },
        "小问6_结论": {
            "判断": "会更多，难点是结构性的（不是经营不好，是小到算不过账）",
            "主要形态": ["连片打包（上海杨浦案例）", "降标（用户小区已在做）",
                     "涨价（通常不被接受）", "撤场（极端情形）"],
            "关键呼应": f"本案保本收缴率 99.67%（问题 3）；"
                    f"120 户保本单价再高 {prem120*100:.0f}% "
                    f"⇒ 保本收缴率只会更高 —— 同一机制的两个刻度",
            "失效条件": fails,
        },
        "敏感性_人员费用拆分": sens,
        "_诚实性": [
            "科目拆分是估计（人员费用 50/50 最主观）⇒ 已做敏感性",
            "节点台阶来自行业惯例 + 单个实证（100 户 1 门岗），非统计",
            "标定用本案保本单价 ⇒ 只报相对溢价",
            "120 户的收入侧假设（车位/商业/单价）是题面给定的简化",
            "不外推到「所有小地块」",
        ],
    }
    p = OUT / "q4_小地块.json"
    p.write_text(json.dumps(res, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    print(f"\n  [落盘] {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
