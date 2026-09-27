#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""Q3：三类手段的敏感性 —— 什么最能提高"谈成"的概率。

## Q2 留下的结构给了 Q3 明确的靶子

Q2 已证明（在"按受益分摊"下）：

$$
u_i=\frac{s_i}{n_i}\bigl[\text{WTP}-(C-s)\bigr]
\qquad\Longrightarrow\qquad
\textbf{各层净收益的符号由总量决定，与分摊曲线无关}
$$

而低层的参与约束是 $u_i \ge -L_i$。于是 Q3 的问题可以**精确分解**：

| 手段 | 作用在哪 | 机理 |
|---|---|---|
| **① 分摊调整** | 改变 $s_i$ | ⚠️ Q2 已证：**不改变总剩余**（只在层间重分）|
| **② 货币补偿** | 改变 $T_i$ | ⚠️ 补偿是**内部转移** ⇒ **也不改变总剩余** |
| **③ 设计变更** | 降低 $L_i$ | ✅ **真正降低约束门槛** |
| **④ 补贴** | 降低 $C-s$ | ✅ **真正抬高总剩余** |

**⇒ 待检验的假说**：
**只有"降损"与"补贴"能改变可行性；分摊与补偿只能在"可谈成的项目"内部解决分配。**

这正是一个**可计算且反直觉**的结论 —— 公众与政策讨论几乎全部聚焦在"怎么分摊"。

## 三种"成功率"代理指标（对应题面 Q3 要求）

| 指标 | 定义 | 含义 |
|---|---|---|
| **P1 可行性** | $\text{WTP}\ge C-s$ | 项目在总量上是否成立 |
| **P2 参与性** | $\forall i:\ u_i\ge -L_i$ | 是否每户都愿签 |
| **P3 可谈成** | P1 ∧ P2 | 两个条件**同时**满足 |
| **P4 让步幅度** | $\max_i\bigl[(-L_i)-u_i\bigr]^+$ | 离"可谈成"还差多远 |

$$
\text{可谈成率} \;=\; \frac{\#\{\text{在参数网格上 P3 成立的组合}\}}{\#\{\text{总组合}\}}
$$

用法：
    $PY q4_mechanisms.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
EP = ROOT / "episodes" / "2026-W43"
RES = EP / "results"

H, PF = 6, 2
GAMMA = 1.35


def shares(H: int, gamma: float) -> dict[int, float]:
    raw = {i: float(i - 1) ** gamma for i in range(1, H + 1)}
    raw[1] = 0.0
    s = sum(raw.values())
    return {i: v / s for i, v in raw.items()}


S = shares(H, GAMMA)


def evaluate(C: float, sub_rate: float, kappa: float,
             L1: float, L2: float, comp: float = 0.0,
             gamma: float = GAMMA) -> dict:
    r"""给定参数，算 P1/P2/P3/P4 与各层明细。

    ## 补偿规则（**修正版**）

    初版让"每户等额收 comp、由 2 层以上按受益份额出资"，结果**出资方比不补偿还亏**
    （净收益 170k → 50k），导致"补偿"反而降低可谈成率 —— 那是规则设计的 bug，
    不是经济结论。

    **正确规则**：令第 $i$ 层在总剩余中的份额为 $w_i=s_i$（Σw=1），
    基准净收益 $u_i=w_i\cdot\text{Surplus}$。补偿的**目标**是把低层的缺口补齐，
    **出资**由 3 层及以上按其剩余份额承担，且**出资不超过其剩余**：

    $$
    \text{Need}=\sum_{i\in\text{低层}}\max\bigl(0,(-L_i)-u_i\bigr)
    \qquad
    \text{Cap}=\sum_{i\ge3}u_i
    $$

    可行 ⟺ $\text{Need}\le\text{Cap}$。
    ⇒ **补偿能把剩余从高层搬到低层，但搬不出剩余总额之外。**
    这与"补偿是内部转移、不创造价值"完全一致，且不再自相矛盾。
    """
    s_ = shares(H, gamma) if gamma != GAMMA else S
    net = C * (1 - sub_rate)
    wtp = net * kappa
    L = {i: (L1 if i == 1 else (L2 if i == 2 else 0.0))
         for i in range(1, H + 1)}
    # ⚠️⚠️ 约定与**约束方向**（此处曾连续出错，务必看清）
    #   L[i] = 第 i 层的损失**正幅值**（≥0）。
    #   参与约束：**净收益必须覆盖损失** ⇒  u_i ≥ L_i
    #   ⇒ 缺口 deficit_i = max(0, L_i − u_i)
    #
    #   曾经写错两次：
    #     ① max(0, −L−u)：恒为 0（因 u≥0 时 −L−u≤0）⇒ 处处"可行"
    #     ② u ≥ −L 这个式子本身：**恒成立**（u≥0 ⇒ u≥−L）
    #   根因：**把"损失"当成了负效用，而不是需要被补偿的负外部性。**
    #   正确含义是：低层要同意，其获得的净收益必须至少抵得上它的损失。
    surplus = wtp - net
    P1 = surplus >= 0

    # 基准净收益：按受益份额分剩余
    u_base = {i: s_[i] * surplus for i in range(1, H + 1)}

    # 缺口：deficit_i = max(0, L_i − u_i)
    gap = {i: max(0.0, L[i] - u_base[i]) for i in range(1, H + 1)}
    need_total = gap[1] + gap[2]
    cap_total = sum(u_base[i] for i in range(3, H + 1))

    # 补偿执行：把 low 层的缺口补齐（若剩余允许），由 3 层以上按剩余份额出资
    #   ★ comp 语义 = **允许动用的补偿总额上限**（0 = 不做补偿，None/∞ = 全额补齐）
    #     初版把 comp 当成"每户获偿额上限"，量级太小（2000 元）且与缺口无关，
    #     导致补偿永远无效 —— 那是参数语义错误，不是经济结论。
    u = dict(u_base)
    if need_total <= 0:
        comp_feasible = True                     # 无缺口，不需补偿
    elif comp >= need_total or comp < 0:
        if cap_total >= need_total:
            # 补齐两层缺口，出资方按剩余份额摊
            for i in (1, 2):
                u[i] = u_base[i] + gap[i]
            for i in range(3, H + 1):
                u[i] = u_base[i] - need_total * (u_base[i] / cap_total)
            comp_feasible = True
        else:
            comp_feasible = False                # 剩余不够补
    else:
        comp_feasible = False                    # 补偿额度不足

    viol = {i: max(0.0, L[i] - u[i]) for i in range(1, H + 1)}
    P2 = all(v <= 1e-6 for v in viol.values())
    P4 = max(viol.values())
    return {"净造价": net, "WTP": wtp, "总剩余": surplus,
            "补偿需求": need_total, "补偿能力": cap_total,
            "补偿可行": comp_feasible,
            "P1_可行": P1, "P2_参与": P2, "P3_可谈成": P1 and P2,
            "P4_最大缺口": P4,
            "每层": {i: {"受益份额": round(s_[i], 5),
                        "净收益_基准": round(u_base[i], 1),
                        "净收益_含补偿": round(u[i], 1),
                        "损失": -round(L[i], 1),
                        "缺口": round(viol[i], 1)} for i in range(1, H + 1)}}


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    out: list[str] = []

    def P(s: str = "") -> None:
        out.append(s)
        print(s, flush=True)

    C = 500_000.0
    SUB0 = 0.40
    L0_1, L0_2 = 1500.0, 1500.0        # 判例量级（梧州案 1500 元/户）

    P("=" * 104)
    P("  Q3  三类手段的敏感性：什么最能提高『谈成』的概率")
    P("=" * 104)
    P(f"\n  基准：造价 {C:,.0f}、补贴率 {SUB0:.0%}、"
      f"低层损失 1层/2层 = {L0_1:,.0f}/{L0_2:,.0f} 元每户")

    # ---------- 1. Q2 的验证：分摊与补偿不改总剩余 ----------
    P(f"\n{'='*104}")
    P("  【1】先验证 Q2 的结构性结论：分摊与补偿**不改变总剩余**")
    P("=" * 104)
    base = evaluate(C, SUB0, 1.5, L0_1, L0_2)
    P(f"    κ=1.5 时：净造价 {base['净造价']:,.0f}，"
      f"WTP {base['WTP']:,.0f}，总剩余 {base['总剩余']:,.0f}")
    P(f"\n    改变分摊曲线（γ 从 1.0 扫到 3.0），看总剩余是否变化：")
    P(f"  {'γ':>6}{'总剩余':>14}{'P3可谈成':>10}{'2层净收益':>14}"
      f"{'6层净收益':>14}")
    P("  " + "-" * 58)
    for g in (1.0, 1.35, 2.0, 2.5, 3.0):
        e = evaluate(C, SUB0, 1.5, L0_1, L0_2, gamma=g)
        P(f"  {g:>6.2f}{e['总剩余']:>14,.0f}"
          f"{('是' if e['P3_可谈成'] else '否'):>10}"
          f"{e['每层'][2]['净收益_基准']:>14,.0f}"
          f"{e['每层'][6]['净收益_基准']:>14,.0f}")
    P(f"\n    ⇒ 总剩余**恒为 {base['总剩余']:,.0f}**，与 γ 无关 ✅（验证 Q2）")
    P(f"      但层间净收益**差异巨大**（2 层 vs 6 层）⇒ 分摊只决定**分配**。")

    P(f"\n    再加补偿（每户 +2000 元，内部转移）：")
    P(f"  {'补偿':>10}{'总剩余':>14}{'P3可谈成':>10}{'一层缺口':>12}"
      f"{'二层缺口':>12}")
    P("  " + "-" * 58)
    for comp in (0, 1000, 2000, 5000):
        e = evaluate(C, SUB0, 1.5, L0_1, L0_2, comp=comp)
        P(f"  {comp:>10,}{e['总剩余']:>14,.0f}"
          f"{('是' if e['P3_可谈成'] else '否'):>10}"
          f"{e['每层'][1]['缺口']:>12,.0f}{e['每层'][2]['缺口']:>12,.0f}")
    P(f"\n    ⇒ 总剩余**仍恒为 {base['总剩余']:,.0f}** ⇒ **补偿也不创造价值**，")
    P(f"      只把剩余在层间搬动（缺口随之变化）。")

    # ---------- 2. 降损 vs 补偿：题面指定的反事实 ----------
    P(f"\n{'='*104}")
    P("  【2】★ 题面指定的反事实：『损失降 30%』 vs 『多补 2 万元』")
    P("=" * 104)
    P(f"    基准损失：一层 {L0_1:,.0f}、二层 {L0_2:,.0f} 元每户")
    P(f"    A 方案：改设计使损失下降 30%（L → {L0_1*0.7:,.0f}）")
    P(f"    B 方案：每户多加补偿 20,000 元（内部转移）")
    P(f"\n  {'方案':<26}{'总剩余':>14}{'P1':>6}{'P2':>6}{'P3':>6}"
      f"{'最大缺口':>12}")
    P("  " + "-" * 76)
    scen = []
    for name, kw in (
        ("基准（不动）", {}),
        ("A 损失降 30%", {"L1": L0_1 * 0.7, "L2": L0_2 * 0.7}),
        ("B 每户多补 2 万", {"comp": 20000.0}),
        ("A+B 同时", {"L1": L0_1 * 0.7, "L2": L0_2 * 0.7, "comp": 20000.0}),
    ):
        args = {"L1": L0_1, "L2": L0_2}
        args.update(kw)
        e = evaluate(C, SUB0, 1.5, **args)
        scen.append({"方案": name, **{k: e[k] for k in
                                      ("总剩余", "P1_可行", "P2_参与",
                                       "P3_可谈成", "P4_最大缺口")}})
        P(f"  {name:<26}{e['总剩余']:>14,.0f}"
          f"{('✓' if e['P1_可行'] else '✗'):>6}"
          f"{('✓' if e['P2_参与'] else '✗'):>6}"
          f"{('✓' if e['P3_可谈成'] else '✗'):>6}"
          f"{e['P4_最大缺口']:>12,.0f}")

    P(f"\n  ⇒ **在总剩余为正时，两个方案都能达成**（本项目基准下剩余充裕）。")
    P(f"     ⇒ 要看清差别，必须**把 κ 压到临界附近**（剩余很小）—— 见下一节。")

    # ---------- 3. 临界附近才见真章 ----------
    P(f"\n{'='*104}")
    P("  【3】★ 把 κ 压到临界：三类手段在『最难的楼』上的对比")
    P("=" * 104)
    P(f"    设定：损失较大（一层 5 万、二层 3 万），总剩余接近 0")
    LB1, LB2 = 50_000.0, 30_000.0
    P(f"\n  {'κ':>6}{'总剩余':>13}{'基准P3':>9}{'分摊最优化':>12}"
      f"{'补偿':>9}{'降损30%':>10}{'补贴+10pp':>11}")
    P("  " + "-" * 72)
    table = []
    for kp in (1.0, 1.1, 1.2, 1.3, 1.5, 2.0):
        e0 = evaluate(C, SUB0, kp, LB1, LB2)
        # 分摊最优化：在所有 γ 中找 P3 成立者
        best_gamma = None
        for g in [1.0 + 0.05 * k for k in range(0, 41)]:
            if evaluate(C, SUB0, kp, LB1, LB2, gamma=g)["P3_可谈成"]:
                best_gamma = g
                break
        eC = evaluate(C, SUB0, kp, LB1, LB2, comp=20000.0)
        eL = evaluate(C, SUB0, kp, LB1 * 0.7, LB2 * 0.7)
        eS = evaluate(C, SUB0 + 0.10, kp, LB1, LB2)
        row = {"kappa": kp, "剩余": e0["总剩余"],
               "基本": e0["P3_可谈成"],
               "分摊优化": best_gamma is not None,
               "最优γ": best_gamma,
               "补偿2万": eC["P3_可谈成"],
               "降损30%": eL["P3_可谈成"],
               "补贴+10pp": eS["P3_可谈成"]}
        table.append(row)
        mk = lambda b: "✓" if b else "✗"   # noqa: E731
        P(f"  {kp:>6.1f}{e0['总剩余']:>13,.0f}{mk(e0['P3_可谈成']):>9}"
          f"{mk(best_gamma is not None):>12}{mk(eC['P3_可谈成']):>9}"
          f"{mk(eL['P3_可谈成']):>10}{mk(eS['P3_可谈成']):>11}")

    # ---------- 3b. ★ 补贴的另一种建模：WTP 外生固定 ----------
    P(f"\n{'='*104}")
    P("  【3b】★ 补贴有效吗？—— 取决于 WTP 是否随净造价缩放")
    P("=" * 104)
    P("    【模型 1】WTP = κ·(C−s)（本脚本主模型）")
    P("      ⇒ 可行性条件可解析化为")
    P("           (κ−1)(C−s) ≥ 需补偿额")
    P("        而需补偿额 = L1 + max(0, L2 − s2·(κ−1)(C−s))")
    P("        ⇒ **补贴率 s 在两侧同时出现并抵消** ⇒ 补贴无效。")
    P("      ⚠️ 这是**模型假设的产物**：它假定了'业主愿付随净造价等比缩放'。")
    P("\n    【模型 2】WTP 外生固定（不随补贴变）")
    P("      ⇒ 补贴直接降低净造价 ⇒ 可行性单调改善。")
    P(f"\n  {'补贴率':>8}{'净造价':>12}{'剩余(模1)':>13}{'P3(模1)':>9}"
      f"{'剩余(模2)':>13}{'P3(模2)':>9}")
    P("  " + "-" * 68)
    for sr in (0.0, 0.2, 0.4, 0.6):
        e1 = evaluate(C, sr, 1.5, 30_000, 15_000)
        # 模型 2：把 WTP 固定为 sr=0.4 时的水平
        net0 = C * (1 - 0.4)
        fixed_wtp = net0 * 1.5
        net = C * (1 - sr)
        Lx = {1: 30_000.0, 2: 15_000.0}
        u1 = S[1] * (fixed_wtp - net)
        u2 = S[2] * (fixed_wtp - net)
        gap1 = max(0.0, Lx[1] - u1)
        gap2 = max(0.0, Lx[2] - u2)
        cap = sum(S[i] * (fixed_wtp - net) for i in range(3, H + 1))
        p3b = (fixed_wtp - net) >= 0 and gap1 + gap2 <= cap + 1e-9
        P(f"  {sr:>8.1f}{net:>12,.0f}{e1['总剩余']:>13,.0f}"
          f"{('✓' if e1['P3_可谈成'] else '✗'):>9}"
          f"{fixed_wtp-net:>13,.0f}{('✓' if p3b else '✗'):>9}")
    P(f"\n  ⇒ **两种模型给出相反结论** ⇒ 『补贴是否有效』在本模型中")
    P(f"     **不可识别**，取决于一个无法从数据验证的假设。")
    P(f"     必须在论文中如实声明（见诚实性声明）。")

    # ---------- 4. 成功率（参数网格上的可谈成比例） ----------
    P(f"\n{'='*104}")
    P("  【4】★ 各类手段的『可谈成率』（参数网格上的占比）")
    P("=" * 104)
    P("     网格须落在『可谈成 / 谈不成』的分界附近，否则无区分度。")
    # 网格须落在"可谈成 / 谈不成"的分界附近，否则无区分度。
    #   一层受益份额为 0 ⇒ 其缺口全靠他人剩余补：
    #       需  Σ_{i≥3}u_i  ≥  L1 + max(0, L2 − u2)
    #   本基准（C=50万，κ∈[1,3]，补贴率∈[0,0.6]）下，
    #   L1 超过 ~10 万即很难成立 ⇒ 网格取到 0–12 万。
    kappas = [1.0, 1.5, 2.0, 2.5, 3.0]
    Ls = [(0, 0), (5_000, 3_000), (20_000, 10_000), (50_000, 25_000),
          (90_000, 45_000), (120_000, 60_000)]
    subs = [0.0, 0.2, 0.4, 0.6]
    total = len(kappas) * len(Ls) * len(subs)

    def rate2(lam) -> float:
        ok = 0
        for kp in kappas:
            for (a, b) in Ls:
                for sr in subs:
                    kp2, a2, b2, sr2, comp = lam(kp, a, b, sr)
                    e = evaluate(C, sr2, kp2, a2, b2, comp=comp)
                    if e["P3_可谈成"]:
                        ok += 1
        return ok / total

    INF = float("inf")
    configs = [
        ("基准（无干预）", lambda kp, a, b, sr: (kp, a, b, sr, 0.0)),
        ("分摊最优化(扫γ)", None),
        ("补偿（全额补齐）", lambda kp, a, b, sr: (kp, a, b, sr, INF)),
        ("补偿（限 3 万/户）", lambda kp, a, b, sr: (kp, a, b, sr, 60_000.0)),
        ("降损 30%", lambda kp, a, b, sr: (kp, a * 0.7, b * 0.7, sr, 0.0)),
        ("降损 60%", lambda kp, a, b, sr: (kp, a * 0.4, b * 0.4, sr, 0.0)),
        ("补贴 +20pp", lambda kp, a, b, sr: (kp, a, b, min(1.0, sr + 0.20), 0.0)),
        ("降损30% + 全额补偿",
         lambda kp, a, b, sr: (kp, a * 0.7, b * 0.7, sr, INF)),
    ]
    P(f"\n    网格：κ×{len(kappas)} × (L1,L2)×{len(Ls)} × 补贴率×{len(subs)}"
      f" = {total} 个组合")
    P(f"\n  {'手段':<26}{'可谈成率':>10}{'相对基准':>12}")
    P("  " + "-" * 50)
    base_rate = rate2(configs[0][1])
    res_rate = []
    for name, lam in configs:
        if lam is None:
            ok = 0
            for kp in kappas:
                for (a, b) in Ls:
                    for sr in subs:
                        hit = False
                        for g in [1.0 + 0.1 * k for k in range(0, 21)]:
                            if evaluate(C, sr, kp, a, b, gamma=g)["P3_可谈成"]:
                                hit = True
                                break
                        if hit:
                            ok += 1
            r = ok / total
        else:
            r = rate2(lam)
        res_rate.append({"手段": name, "可谈成率": round(r, 4)})
        if base_rate > 0:
            lift = (r - base_rate) / base_rate * 100
            lifts = f"{lift:+.1f}%"
        else:
            lifts = "—" if r == 0 else "+∞"
        P(f"  {name:<26}{r:>10.1%}{lifts:>12}")

    P(f"\n  ⇒ 预期排序：**降损 > 补贴 > 补偿 > 分摊最优化**")
    P(f"     （降损降低门槛 L；补贴降低净造价；补偿与分摊只搬动剩余）")

    (RES / "q4_mechanisms.txt").write_text("\n".join(out), encoding="utf-8")
    (RES / "q4_mechanisms.json").write_text(json.dumps({
        "基准": {"C": C, "补贴率": SUB0, "γ": GAMMA,
                "L1": L0_1, "L2": L0_2},
        "反事实": scen,
        "临界对比": table,
        "可谈成率": res_rate,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ndone  -> {RES / 'q4_mechanisms.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
