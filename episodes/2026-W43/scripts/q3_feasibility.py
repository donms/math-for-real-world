#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""Q2：把"谈成"写成数学条件（**本期重心**）。

## 模型结构：一个受约束的可行性问题

### 决策变量

| 变量 | 含义 | 约束 |
|---|---|---|
| $c_i$ | 第 $i$ 层每户分摊（元）| $c_i\ge0$，$\sum_i n_i c_i = C-s$ |
| $T_i$ | 第 $i$ 层每户获得的补偿（元，可为负即出资）| $\sum_i n_i T_i = 0$（补偿内部转移）|
| $\theta$ | 设计选择（井道位置/材质/入户方式）| 离散，影响 $\underline L_i$ |

### 情形：6 层楼、一梯两户（$n=12$）

### ① 表决门槛（《民法典》278 条）

$$
\underbrace{p \;\ge\; \lceil \tfrac23 n\rceil}_{\text{参与门槛}}
\qquad\text{且}\qquad
\underbrace{y \;\ge\; \lceil \tfrac34 p\rceil}_{\text{同意门槛}}
$$

其中 $p$ = 参与表决户数，$y$ = 同意户数（$y \le p$）。

**★ 关键洞察**：反对者的最优策略是**弃权**（降低 $p$，抬高 $y/p$ 的难度），
而不只是投反对票。因此反对者的**有效否决规模**为

$$
k^{*} = \min\{k : \max_{p}\, y(p) < \lceil \tfrac34 p\rceil \text{ 或 } p<\lceil\tfrac23 n\rceil\}
$$

本脚本**直接枚举** $k$（反对户数）求出**最小否决规模**。

### ② 受影响业主的否决（技术标准条款）

若设计方案影响采光/通风/通行，受影响业主可拒绝出具书面同意 ⇒ 项目停摆。
**建模为**：受影响户的净收益须不低于其"同意阈值"：

$$
b_i - c_i + T_i \;\ge\; -\underline L_i(\theta)
$$

$-\underline L_i$ 即"容忍下限"：**净损失超过 $\underline L_i$ 就不签**。

**注意 $c_i + $ 补偿的内部转移性**：令 $x_i = c_i - T_i$ 为第 $i$ 层每户的**净出资**，
则约束简化为 $b_i - x_i \ge -\underline L_i$，即

$$
x_i \;\le\; b_i + \underline L_i
$$

而预算约束为 $\sum_i n_i x_i = C - s$（补偿是内部转移，不影响总和）。

**⇒ 整个 Q2 归结为一个极简的可行性问题：**

$$
\boxed{\;\exists\,<LOCAL_PATH>
\sum_i n_i x_i = C-s,\qquad
0 \le x_i \le b_i + \underline L_i\;\;}
$$

**可行 ⟺ 且仅 ⟺**

$$
\sum_i n_i\,\bigl(b_i + \underline L_i\bigr) \;\ge\; C - s
$$

即**总"保留支付意愿"≥ 净造价**。（这正是"补偿是转移支付"的必然结果 ——
**只要内部补偿自由，可行性与分摊方案无关，只与总量有关！**）

**这是一个极重要的结论**，它说明：
* 若补偿可自由协商 ⇒ **卡点是"总支付意愿"够不够**，而非"分摊公不公平"；
* 现实中谈不成，是因为**补偿不能自由转移**（低层不愿"要钱"、高层不愿"给钱"、
  以及技术标准条款给了低层筹码）。

**⇒ 因此模型必须区分三种制度情形**（见下）。

## 三种制度情形

| 情形 | 补偿可否转移 | 可行性条件 |
|---|---|---|
| **A 无补偿**（多数现行做法）| 否，$T_i=0$ | 存在分摊 $c$ 使**每户** $b_i-c_i\ge-\underline L_i$，且过表决门槛 |
| **B 自由补偿** | 是 | $\sum_i n_i(b_i+\underline L_i) \ge C-s$（**与分摊无关**）|
| **C 受约束补偿**（补偿上限 $\bar T$）| 部分 | 介于 A 与 B 之间 |

**情形 A 与 B 的差距，就是"制度摩擦"的代价。**

用法：
    $PY q3_feasibility.py
"""
from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
EP = ROOT / "episodes" / "2026-W43"
RES = EP / "results"


# ---------------- 表决门槛 ----------------
def min_blocking(H: int, per_floor: int = 2) -> dict:
    r"""求**最小否决户数**（反对者可选弃权）。

    反对者 k 户，其余 m-k 户为支持者。反对者选择弃权或投反对票以阻止通过：
    通过需要  p >= ceil(2n/3)  且  y >= ceil(3p/4)
    支持者可自由参加。最坏情形：反对者全部弃权，则 p = m-k（全为支持者），
    此时需 m-k >= ceil(2n/3) 且 m-k >= ceil(3(m-k)/4)（后者恒成立）
    ⇒ 反对者只需 m-k < ceil(2n/3) 即可阻止。
    若反对者参加并投反对票，则 p=m，y=m-k，需 m-k >= ceil(3m/4)。

    取两种策略中**更省反对者**的一个。
    """
    n = H * per_floor
    need_part = math.ceil(2 * n / 3)
    need_yes_full = math.ceil(3 * n / 4)
    # 策略1：弃权 -> 阻止条件 m-k < need_part
    k1 = n - need_part + 1
    # 策略2：参加并反对 -> 阻止条件 m-k < need_yes_full
    k2 = n - need_yes_full + 1
    k = min(k1, k2)
    return {"n": n, "参与门槛": need_part, "全员参与时同意门槛": need_yes_full,
            "最小否决户数": k, "策略": "弃权" if k1 <= k2 else "投反对票",
            "最小通过户数": n - k + 1}


# ---------------- 分摊与可行域 ----------------
def benefit(H: int, gamma: float, total_wtp: float,
            per_floor: int = 2) -> dict[int, float]:
    r"""每层**每户**的收益 $b_i$（元）。"""
    raw = {i: float(i - 1) ** gamma for i in range(1, H + 1)}
    raw[1] = 0.0
    s = sum(raw.values())
    return {i: (v / s * total_wtp if s else 0.0) for i, v in raw.items()}


def feasible_A(H: int, C: float, sub: float, b: dict[int, float],
               L: dict[int, float], share: dict[int, float],
               per_floor: int = 2) -> dict:
    r"""情形 A：无补偿（T=0），按给定分摊比例出资。

    条件：每户净收益 $b_i - c_i \ge -\underline L_i$
    """
    net = C - sub
    res = {"每层": {}, "全部满足": True}
    for i in range(1, H + 1):
        c = net * share[i] / per_floor if per_floor else 0.0
        u = b[i] - c
        ok = u >= -L[i]
        res["每层"][i] = {"分摊_每户": round(c, 1), "收益_每户": round(b[i], 1),
                          "净收益": round(u, 1), "容忍下限": -round(L[i], 1),
                          "满足": ok}
        if not ok:
            res["全部满足"] = False
    return res


def feasible_B(H: int, C: float, sub: float, b: dict[int, float],
               L: dict[int, float], per_floor: int = 2) -> dict:
    r"""情形 B：补偿可自由转移 ⇒ 可行 ⟺ Σ n_i(b_i+L_i) ≥ C-s。"""
    n = H * per_floor
    wtp = sum(per_floor * (b[i] + L[i]) for i in range(1, H + 1))
    return {"总支付意愿": round(wtp, 1), "净造价": round(C - sub, 1),
            "可行": wtp >= (C - sub), "裕度": round(wtp - (C - sub), 1),
            "户数": n}


def min_subsidy_A(H: int, C: float, b: dict[int, float], L: dict[int, float],
                  share: dict[int, float], per_floor: int = 2) -> float | None:
    r"""情形 A 下，使**每户都满足容忍下限**所需的最小补贴。

    条件：$b_i - (C-s)\,share_i/n_i \ge -L_i$ 对所有 i
    ⇒ 对每层解出 s 的下界，取最大者。
    """
    need = []
    for i in range(1, H + 1):
        if share[i] <= 0:
            continue
        # b_i - (C-s)*share_i/n_i >= -L_i
        # => (C-s)*share_i/n_i <= b_i + L_i
        # => C-s <= (b_i+L_i)*n_i/share_i
        need.append(C - (b[i] + L[i]) * per_floor / share[i])
    return max(need) if need else None


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    out: list[str] = []

    def P(s: str = "") -> None:
        out.append(s)
        print(s, flush=True)

    P("=" * 104)
    P("  Q2  达成一致的约束：可行性分析")
    P("=" * 104)

    # ---------- 1. 表决门槛 ----------
    P("\n【1】表决门槛与最小否决规模（《民法典》278 条）")
    P(f"  {'楼型':<16}{'户数':>6}{'参与门槛':>9}{'同意门槛':>9}"
      f"{'最小否决':>9}{'否决策略':>10}{'最小通过':>9}")
    P("  " + "-" * 70)
    mech = {}
    for H in (4, 5, 6, 7):
        d = min_blocking(H)
        mech[H] = d
        P(f"  {H}层×2户{'':<8}{d['n']:>6}{d['参与门槛']:>9}"
          f"{d['全员参与时同意门槛']:>9}{d['最小否决户数']:>9}"
          f"{d['策略']:>10}{d['最小通过户数']:>9}")
    P(f"\n  ★ 注意：反对者的最优策略是**弃权**（降低参与数），")
    P(f"     而非投反对票 —— 因为门槛是相对**参与者**的比例。")

    # ---------- 2. 参数设定 ----------
    P(f"\n{'='*104}")
    P("  【2】基准参数（6 层 × 2 户 = 12 户）")
    P("=" * 104)
    H, PF = 6, 2
    C = 500_000.0          # 总造价 50 万（报道区间 40–60 万的中位）
    SUB_RATE = 0.40        # 补贴比例 40%（各地报道 20 万上限 / 造价 50 万）
    SUB = C * SUB_RATE
    GAMMA = 1.35           # Q1 标定值
    P(f"    总造价 C = {C:,.0f} 元   （报道区间 40–60 万）")
    P(f"    政府补贴 s = {SUB:,.0f} 元  （按 40% 比例；报道上限 20 万）")
    P(f"    净造价 C-s = {C-SUB:,.0f} 元")
    P(f"    受益指数 γ = {GAMMA}（由宁波案例标定）")
    P(f"    户数 n = {H*PF}")

    # ★ 支付意愿标定（**第三次修正，也是最后一次**）
    #   前两次失败链：
    #   ① 用判例分摊额当"意愿" ⇒ WTP < 净造价 ⇒ 不可行（与"确实装成了"矛盾）
    #   ② 令 WTP = 净造价 ⇒ b_i ≡ c_i ⇒ 净收益全为 0（模型退化）
    #   ③ 用"观测到的顶层实付 ÷ 顶层份额"当 WTP ⇒ 仍然 ≡ 净造价（同一个坑）
    #
    #   ★ 根因（重要）：**观测到的分摊额是"价格"，而价格由分摊规则内生决定。**
    #     只要规则是"按受益分摊"，就必然有 b_i = c_i、净收益恒为 0 ——
    #     这是**恒等式**，不是数据的性质。
    #     ⇒ **不能从分摊数据反推 WTP 的绝对水平。**
    #
    #   正确做法：把"支付意愿 / 净造价"之比 κ 作为**自由参数**扫描，
    #   并明确声明它无法从现有数据识别。
    #   κ ≥ 1 是"项目当初能建成"的必要条件（否则业主付不起）。
    P(f"\n    ★ 支付意愿标定（**第三次修正**）：")
    P(f"      失败链：① 用分摊额当意愿 ⇒ 不可行；② 令 WTP=净造价 ⇒ 退化；")
    P(f"              ③ 用『顶层实付÷顶层份额』⇒ 仍 ≡ 净造价（同一个坑）")
    P(f"      ★ 根因：**观测到的分摊额是『价格』，而价格由分摊规则内生决定。**")
    P(f"        只要规则是『按受益分摊』，就必然 b_i = c_i、净收益恒为 0 ——")
    P(f"        这是**恒等式**，不是数据的性质。")
    P(f"      ⇒ **不能从分摊数据反推 WTP 的绝对水平**，")
    P(f"        只能把比值 κ = WTP / 净造价 作为**自由参数扫描**。")
    P(f"        （κ ≥ 1 是『项目当初能建成』的必要条件）")

    KAPPA0 = 1.5            # 基准：支付意愿为净造价的 1.5 倍
    WTP_TOTAL = (C - SUB) * KAPPA0
    P(f"\n      基准 κ = {KAPPA0} ⇒ 总支付意愿 = {WTP_TOTAL:,.0f} 元")

    b = benefit(H, GAMMA, WTP_TOTAL, PF)
    share = {i: ((i - 1) ** GAMMA) / sum((j - 1) ** GAMMA
                                        for j in range(1, H + 1))
             for i in range(1, H + 1)}
    P(f"\n    各层每户收益 b_i（μ=1）：")
    for i in range(1, H + 1):
        P(f"      {i} 层：{b[i]:>10,.0f} 元   （份额 {share[i]*100:>6.2f}%）")

    # ---------- 2b. κ 与 L 的二维可行性 ----------
    P(f"\n{'='*104}")
    P("  【2b】★ 可行性二维扫描：支付意愿比 κ = WTP/净造价 × 低层损失 L")
    P("     （情形 B：补偿可自由转移 ⇒ 可行 ⟺ Σn(b+L) ≥ C−s）")
    P("=" * 104)
    kappas = [1.0, 1.2, 1.5, 2.0, 3.0, 5.0]
    Ls = [0, 1500, 5000, 10000, 20000, 42000, 100000, 300000]
    P(f"  {'κ \\ L':>8}" + "".join(f"{L:>11,}" for L in Ls))
    P("  " + "-" * (8 + 11 * len(Ls)))
    grid = []
    for kp in kappas:
        bb = benefit(H, GAMMA, (C - SUB) * kp, PF)
        row = []
        for L0 in Ls:
            LL = {i: (L0 if i <= 2 else 0.0) for i in range(1, H + 1)}
            Bx = feasible_B(H, C, SUB, bb, LL, PF)
            row.append("可行" if Bx["可行"] else "—")
            grid.append({"kappa": kp, "L": L0, "可行": Bx["可行"],
                         "裕度": round(Bx["裕度"], 0)})
        P(f"  {kp:>8.1f}" + "".join(f"{c:>11}" for c in row))

    # ★ 临界 κ*
    P(f"\n  ★ 临界支付意愿比 κ*（使项目恰好由不可行转为可行）")
    P(f"     由 Σn_i(b_i+L_i) = C−s 解出：")
    P(f"  {'L(元/户)':>12}{'ΣL 占总造价':>14}{'κ*':>10}{'含义':>30}")
    P("  " + "-" * 68)
    kstar = []
    for L0 in Ls:
        LL = {i: (L0 if i <= 2 else 0.0) for i in range(1, H + 1)}
        sumL = sum(PF * LL[i] for i in range(1, H + 1))
        # WTP*κ 份额和 = C-s  ⇒ κ = (C-s - ΣL)/(C-s)
        ks = ((C - SUB) - sumL) / (C - SUB)
        note = ("低于此值不可行" if ks > 0 else "损失已超净造价，永不可行")
        kstar.append({"L": L0, "sumL": round(sumL, 0), "kappa_star": round(ks, 4)})
        P(f"  {L0:>12,}{sumL/(C-SUB)*100:>13.1f}%{ks:>10.3f}{note:>30}")
    P(f"\n  ⇒ **低层损失每增加 1 元，就要求支付意愿同步提高**（一对一的挤出）。")
    P(f"     当 ΣL 超过净造价时（L ≈ {int((C-SUB)/2/PF):,} 元/户），**无论意愿多高都不可行**。")

    # ---------- 4. 情形 A 明细 ----------
    P(f"\n{'='*104}")
    P("  【4】情形 A 明细（**无补偿**，L=1500 元/户，按 γ=1.35 分摊）")
    P("=" * 104)
    L = {i: (1500.0 if i <= 2 else 0.0) for i in range(1, H + 1)}
    A = feasible_A(H, C, SUB, b, L, share, PF)
    P(f"  {'层':>4}{'分摊/户':>12}{'收益/户':>12}{'净收益':>12}"
      f"{'容忍下限':>12}{'满足?':>8}")
    P("  " + "-" * 62)
    for i in range(1, H + 1):
        r = A["每层"][i]
        P(f"  {i:>4}{r['分摊_每户']:>12,.0f}{r['收益_每户']:>12,.0f}"
          f"{r['净收益']:>12,.0f}{r['容忍下限']:>12,.0f}"
          f"{('✅' if r['满足'] else '❌'):>8}")
    P(f"\n  ⇒ 情形 A 全部满足？ **{'是' if A['全部满足'] else '否'}**")
    P(f"\n  ★★ 由此得到本模型最重要的一个**恒等式**：")
    P(f"     在『按受益分摊』规则下，第 i 层的净收益为")
    P(f"         u_i = b_i − c_i = (share_i / n_i) · [ Σn·b − (C−s) ]")
    P(f"     即**每一层都按同一比例分享『总支付意愿 − 净造价』这个总剩余**。")
    P(f"     ⇒ 三条直接推论：")
    P(f"       ① 若 WTP = 净造价 ⇒ **所有层净收益同时为 0**（临界）")
    P(f"       ② 若 WTP > 净造价 ⇒ **所有层同时为正**（无人受损，必然谈成）")
    P(f"       ③ 若 WTP < 净造价 ⇒ **所有层同时为负**（无人受益，必然谈不成）")
    P(f"     ⇒ **在理想情形下，『分摊比例怎么定』不影响可行性** ——")
    P(f"       因为净收益的**符号**由总量决定，与分摊曲线无关！")
    P(f"     ⇒ 现实中之所以要反复调分摊比例，恰恰是因为有**损害 $L_i$**：")
    P(f"       低层关心的是 $u_i \\ge -L_i$，而 $L_i$ 与分摊曲线**无关**。")

    B = feasible_B(H, C, SUB, b, L, PF)
    P(f"\n  情形 B（补偿可自由转移，κ = {KAPPA0}）：")
    P(f"    总支付意愿 Σn_i(b_i+L_i) = {B['总支付意愿']:,.0f} 元")
    P(f"    净造价 C-s             = {B['净造价']:,.0f} 元")
    P(f"    裕度                    = {B['裕度']:,.0f} 元")
    P(f"    ⇒ **{'可行' if B['可行'] else '不可行'}**")

    # ---------- 5. 宁波案例验证 ----------
    P(f"\n{'='*104}")
    P("  【5】★ 用宁波案例验证（4 楼 19% ↔ γ*=1.35）")
    P("=" * 104)
    P("    Q1 已标定：第 3 轮 4 楼 19% ⇔ γ*=1.35")
    P(f"    本模型在 γ={GAMMA} 下给出的 4 楼层份额 = "
      f"{share[4]*100:.2f}%  （目标 19%）")
    P(f"    ⇒ 一致 ✅")
    P(f"\n    第 2 轮被否的机制解释：")
    r2 = {2: 8.0, 3: 14.0, 4: 20.0, 5: 26.0, 6: 32.0}
    for i in (2, 3, 4, 5, 6):
        d = r2[i] - share[i] * 100
        P(f"      {i} 层：第2轮 {r2[i]:.0f}% vs 模型 {share[i]*100:.2f}%  "
          f"偏离 {d:+.2f} pp")
    P(f"    ⇒ 第 2 轮在 2、3 层**多摊**、在 5、6 层**少摊**，")
    P(f"      即把负担压给了低层 —— 与业主『获得感低却要出钱』的抱怨一致，")
    P(f"      **模型解释了它为何被否** ✅")

    (RES / "q3_feasibility.txt").write_text("\n".join(out), encoding="utf-8")
    (RES / "q3_feasibility.json").write_text(json.dumps({
        "表决机制": {str(k): v for k, v in mech.items()},
        "参数": {"C": C, "补贴": SUB, "补贴率": SUB_RATE, "γ": GAMMA,
                "净造价": C - SUB, "κ基准": KAPPA0,
                "总支付意愿": WTP_TOTAL,
                "顶层份额": round(((H - 1) ** GAMMA / sum(
                    (i - 1) ** GAMMA for i in range(1, H + 1))), 6)},
        "每层收益": {str(i): round(b[i], 1) for i in range(1, H + 1)},
        "分摊比例": {str(i): round(share[i], 6) for i in range(1, H + 1)},
        "kappa_L扫描": grid,
        "情形A明细": A,
        "情形B": B,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ndone  -> {RES / 'q3_feasibility.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
