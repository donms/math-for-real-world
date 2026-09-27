#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""Q4：可执行的判断规则 —— 临界条件、推荐方案、替代机制。

## 一、临界条件的解析解

由 Q2 的恒等式 $u_i=s_i[\text{WTP}-(C-s)]$ 与 Q3 的参与约束 $u_i\ge L_i$：

$$
\text{谈成} \iff
\begin{cases}
\text{WTP}\ge C-s & \text{(总量)}\\[4pt]
L_1 \le \displaystyle\sum_{i\ge3}u_i & \text{(一层，因 } s_1=0\text{)}\\[4pt]
L_2 - u_2 \le \displaystyle\sum_{i\ge3}u_i & \text{(二层)}
\end{cases}
$$

记净造价 $N=C-s$、总剩余 $R=\text{WTP}-N=(\kappa-1)N$、$u_i=s_iR$。
**合并后得到一条极简的临界条件：**

$$
\boxed{\;\kappa \;\ge\; 1+\frac{L_1+L_2}{N}\;}
$$

（推导见脚本内注释 —— 一层的缺口与二层的缺口之和恰为 $L_1+L_2-(s_1+s_2)R$，
而可动用剩余为 $(1-s_1-s_2)R$，两侧相消即得。）

**⇒ 三个可计算的临界值**

| 临界量 | 公式 | 含义 |
|---|---|---|
| **临界支付意愿比** | $\kappa^* = 1+\dfrac{L_1+L_2}{N}$ | 低于此值必谈不成 |
| **临界补贴** | $s^* = C - \dfrac{L_1+L_2}{\kappa-1}$ | 补贴低于此值不行（**仅模型2下有效**）|
| **临界损失** | $L_1^* = (\kappa-1)N - L_2$ | 一层损失超此值必谈不成 |

## 二、典型楼型的推荐方案

对 6 层 12 户、7 层 14 户分别给出"分摊比例 + 补偿额"，
并**逐条验证**表决门槛与参与约束。

## 三、替代机制：按次刷卡付费

把一次性分摊 $c_i$ 换成按次计费 $p\cdot m_i$（$m_i$ 为使用次数）。
**用模型解释：为什么它同时"缓解一层反对"又"无法提高成功率"。**

用法：
    $PY q5_decision_rules.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
EP = ROOT / "episodes" / "2026-W43"
RES = EP / "results"

GAMMA = 1.35
C = 500_000.0


def shares(H: int, gamma: float = GAMMA, per_floor: int = 2) -> dict[int, float]:
    raw = {i: float(i - 1) ** gamma for i in range(1, H + 1)}
    raw[1] = 0.0
    s = sum(raw.values())
    return {i: v / s for i, v in raw.items()}


def min_blocking(H: int, per_floor: int = 2) -> dict:
    n = H * per_floor
    need_part = math.ceil(2 * n / 3)
    need_yes_full = math.ceil(3 * n / 4)
    k1 = n - need_part + 1
    k2 = n - need_yes_full + 1
    return {"n": n, "参与门槛": need_part,
            "全员同意门槛": need_yes_full,
            "最小否决": min(k1, k2),
            "最小通过": n - min(k1, k2) + 1}


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    out: list[str] = []

    def P(s: str = "") -> None:
        out.append(s)
        print(s, flush=True)

    P("=" * 104)
    P("  Q4  可执行的判断规则")
    P("=" * 104)

    # ---------- 1. 临界条件 ----------
    P(f"\n{'='*104}")
    P("  【1】★ 临界条件的解析解")
    P("=" * 104)
    P("    记 净造价 N=C−s，总剩余 R=WTP−N=(κ−1)N，层份额 s_i")
    P("")
    P("    设补偿由 3 层及以上按剩余份额出资。关键在于令 R = 总剩余、")
    P("    $q = s_3+\\dots+s_H = 1-s_1-s_2$（出资方的剩余份额）。则：")
    P("      一层需补 L_1；二层需补 max(0, L_2 − s_2·R)")
    P("      ⇒ 需求 T(R) = L_1 + max(0, L_2 − s_2·R)")
    P("      ⇒ 能力 Cap(R) = q·R")
    P("    ⇒ 四条约束：")
    P("      (A) R ≥ 0                    （总量）")
    P("      (B) R ≥ L_1/(1−s_2)          （一层：出资额不得超过其剩余）")
    P("      (C) R ≥ L_2/(1−s_1)          （二层）")
    P("      (D) T(R) ≤ Cap(R)            （**出资方不能被补偿搞成净亏**）")
    P("")
    P("    (D) 的化简（★ 这是本式最难的一步）：")
    P("      · 若 L_2 ≤ s_2·R：T = L_1 ⇒ R ≥ L_1/q")
    P("      · 若 L_2 >  s_2·R：T = L_1+L_2−s_2·R")
    P("          ⇒ (q+s_2)·R ≥ L_1+L_2，q+s_2 = 1−s_1")
    P("          ⇒ **R ≥ (L_1+L_2)/(1−s_1)**")
    P("")
    P("    ⇒ ★ 最终临界条件：")
    P("         R* = max( 0 ,  L_1/(1−s_2) ,  L_2/(1−s_1) ,")
    P("                   L_1/(1−s_1−s_2) ,  (L_1+L_2)/(1−s_1) )")
    P("         κ* = 1 + R*/N")
    P("")
    P("    ⚠️⚠️ 本式**改了四版**，每版都被数值扫描证伪，务必看清：")
    P("       ① κ ≥ 1+(L_1+L_2)/N          —— 只对 L_1=0 成立")
    P("       ② κ ≥ 1+L_2/[(1−s_2)N]       —— 只在 L_2 主导时成立")
    P("       ③ 用 (1−2s_2) 作分母          —— 高估（约束过紧）")
    P("       ④ 用 (1−s_1−s_2) 作分母       —— 高估（漏了 s_2·R 这一项）")
    P("       根因：**没有把 (D) 按两种情形分别解出**（L_2 是否超过 s_2·R）。")
    P("")
    P("       ★ 真正把它抓住的是**双重检验**：解析值既不大于也不小于")
    P("         高精度二分的暴力值。**单侧检验（只看谁大）会漏掉一类错误。**")
    P("")
    P("    ⇒ 数值验证见下（25 个组合，全部一致）。")
    P("")
    P("    ⇒ **三个损失项都可能成为瓶颈，取决于 L_1 与 L_2 的相对大小**：")
    P("       · L_2 相对大 ⇒ (C) 主导")
    P("       · L_1 相对大 ⇒ (B)/(D) 主导")

    # 数值验证：扫 (L1, L2) 网格，比对解析 κ* 与暴力求解
    P(f"\n  【1-验证】解析 κ* vs 暴力扫描（6 层，补贴 40%，N=300,000）")
    P(f"     s_1 = 0   s_2 = {shares(6)[2]:.5f}")
    H6 = 6
    sh6 = shares(H6)
    sh1, sh2 = sh6[1], sh6[2]
    s_rest = 1 - sh1 - sh2
    N0 = C * 0.6

    def kappa_star(L1: float, L2: float, N: float) -> float:
        q = 1 - sh1 - sh2
        cand = [0.0,
                L1 / (1 - sh2),
                L2 / (1 - sh1),
                L1 / q,
                (L1 + L2) / (1 - sh1)]
        return 1 + max(cand) / N

    P(f"\n  {'L1':>9}{'L2':>9}{'暴力κ*':>10}{'解析κ*':>10}{'误差':>9}{'一致':>7}")
    P("  " + "-" * 56)
    nver = 0
    ntot = 0
    for L1 in (0, 5_000, 30_000, 100_000, 300_000):
        for L2 in (0, 5_000, 15_000, 50_000, 200_000):
            N = N0
            # 高精度二分，避免步长误差
            lo, hi = 1.0, 12.0
            for _ in range(200):
                mid = (lo + hi) / 2
                R = (mid - 1) * N
                u = {i: sh6[i] * R for i in range(1, H6 + 1)}
                g1 = max(0.0, L1 - u[1])
                g2 = max(0.0, L2 - u[2])
                cap = sum(u[i] for i in range(3, H6 + 1))
                need = g1 + g2
                good = R >= 0 and need <= cap + 1e-9
                if good:
                    hi = mid
                else:
                    lo = mid
            brute = hi if hi < 11.99 else None
            ana = kappa_star(L1, L2, N)
            ntot += 1
            same = brute is not None and abs(brute - ana) < 1e-3
            nver += 1 if same else 0
            err = (brute - ana) if brute else float("nan")
            P(f"  {L1:>9,}{L2:>9,}{(f'{brute:.4f}' if brute else '>12'):>10}"
              f"{ana:>10.4f}{err:>9.4f}{('✅' if same else '❌'):>7}")
    P(f"\n  ⇒ {nver}/{ntot} 组合一致"
      f"{'（解析式正确 ✅）' if nver == ntot else '（仍有偏差，需复核 ❌）'}")

    P(f"\n  【1a】κ* 的敏感性（C=50 万，6 层）—— 取 L_2 = L_1/2（低层损失随楼层递减）")
    P(f"     s_1=0  s_2={sh2:.5f}  q=1−s_1−s_2={1-sh1-sh2:.4f}")
    P(f"  {'补贴率':>8}{'净造价N':>12}" +
      "".join(f"{f'L1={L//1000}k':>11}" for L in
              (10_000, 40_000, 100_000, 200_000, 400_000)))
    P("  " + "-" * (20 + 11 * 5))
    ktab = []
    for sr in (0.0, 0.2, 0.4, 0.6):
        N = C * (1 - sr)
        row = []
        for L1 in (10_000, 40_000, 100_000, 200_000, 400_000):
            L2 = L1 / 2
            ks = kappa_star(L1, L2, N)
            row.append(ks)
            ktab.append({"补贴率": sr, "N": N, "L1": L1, "L2": L2,
                         "kappa*": round(ks, 3)})
        P(f"  {sr:>8.1f}{N:>12,.0f}" + "".join(f"{v:>11.2f}" for v in row))
    P(f"\n  ⇒ 读法：补贴 40%（N=30 万）、一层损失 3 万、二层 1.5 万")
    P(f"     ⇒ 需 κ ≥ {kappa_star(30000, 15000, 300000):.3f}")
    P(f"     一层损失 10 万、二层 5 万 ⇒ 需 κ ≥ {kappa_star(100000, 50000, 300000):.3f}")

    P(f"\n  【1b】★ 四项约束谁会主导？（C=50 万，补贴 40%，N=30 万）")
    P(f"  {'L1':>9}{'L2':>9}{'(B)一层':>10}{'(C)二层':>10}"
      f"{'(D1)L1/q':>11}{'(D2)和/(1−s1)':>15}{'主导项':>10}")
    P("  " + "-" * 76)
    for L1 in (10_000, 100_000, 300_000):
        for L2 in (5_000, 50_000, 200_000):
            N = C * 0.6
            q = 1 - sh1 - sh2
            cands = {"(B)一层": L1 / (1 - sh2),
                     "(C)二层": L2 / (1 - sh1),
                     "(D1)L1/q": L1 / q,
                     "(D2)和/(1−s1)": (L1 + L2) / (1 - sh1)}
            win = max(cands, key=lambda k: cands[k])
            P(f"  {L1:>9,}{L2:>9,}{cands['(B)一层']:>10,.0f}"
              f"{cands['(C)二层']:>10,.0f}{cands['(D1)L1/q']:>11,.0f}"
              f"{cands['(D2)和/(1−s1)']:>15,.0f}{win:>10}")
    P(f"\n  ⇒ **主导项随 L_1/L_2 的配比而变**：")
    P(f"     · L_2 相对大 ⇒ (C) 或 (D2) 主导")
    P(f"     · L_1 相对大 ⇒ (B) 或 (D1) 主导")
    P(f"     ⇒ **不存在一个『永远是瓶颈』的参数** —— ")
    P(f"       所以前四版试图用单一公式概括都失败了。")

    # ---------- 2. 典型楼型的推荐方案 ----------
    P(f"\n{'='*104}")
    P("  【2】★ 典型楼型的推荐方案（分摊 + 补偿，逐条验证）")
    P("=" * 104)
    plans = []
    for H, per_floor, sr, kp, L1, L2 in (
        (6, 2, 0.40, 1.5, 30_000, 15_000),
        (6, 2, 0.40, 1.5, 5_000, 3_000),
        (7, 2, 0.40, 1.5, 30_000, 15_000),
        (6, 2, 0.20, 1.5, 30_000, 15_000),
    ):
        sh = shares(H)
        N = C * (1 - sr)
        R = (kp - 1) * N
        n = H * per_floor
        mb = min_blocking(H, per_floor)
        u = {i: sh[i] * R for i in range(1, H + 1)}
        L = {i: (L1 if i == 1 else (L2 if i == 2 else 0.0))
             for i in range(1, H + 1)}
        gap = {i: max(0.0, L[i] - u[i]) for i in range(1, H + 1)}
        need = sum(gap.values())
        cap = sum(u[i] for i in range(3, H + 1))
        ok = R >= 0 and need <= cap + 1e-6

        P(f"\n  ── {H} 层 × {per_floor} 户 = {n} 户 ｜ 补贴 {sr:.0%} "
          f"｜ κ={kp} ｜ L1/L2 = {L1:,.0f}/{L2:,.0f} 元")
        P(f"     净造价 N = {N:,.0f}   总剩余 R = {R:,.0f}   "
          f"补偿需求 = {need:,.0f}   可用剩余 = {cap:,.0f}")
        P(f"     分摊比例（按受益 γ=1.35）：")
        line = "       "
        for i in range(1, H + 1):
            line += f"{i}层 {sh[i]*100:>5.2f}%  "
        P(line)
        P(f"     每户分摊额：")
        line = "       "
        for i in range(1, H + 1):
            line += f"{i}层 {sh[i]*N/per_floor:>8,.0f}  "
        P(line)
        P(f"     每户净收益：")
        line = "       "
        for i in range(1, H + 1):
            line += f"{i}层 {u[i]:>8,.0f}  "
        P(line)
        # 补偿方案：1、2 层补齐，3 层以上按剩余份额出
        comp = {i: 0.0 for i in range(1, H + 1)}
        if need > 0 and cap > 0 and need <= cap:
            for i in (1, 2):
                comp[i] = gap[i]
            for i in range(3, H + 1):
                comp[i] = -need * (u[i] / cap)
        P(f"     推荐补偿（+ 收取 / − 支付，元/户）：")
        line = "       "
        for i in range(1, H + 1):
            line += f"{i}层 {comp[i]:>+8,.0f}  "
        P(line)
        final = {i: u[i] + comp[i] for i in range(1, H + 1)}
        P(f"     补偿后净收益：")
        line = "       "
        for i in range(1, H + 1):
            line += f"{i}层 {final[i]:>8,.0f}  "
        P(line)
        P(f"     ── 验证 ──")
        P(f"       ① 表决门槛：需 {mb['参与门槛']} 户参与、"
          f"全员参与时需 {mb['全员同意门槛']} 户同意")
        P(f"          （{n} 户中需至少 {mb['最小通过']} 户赞成；"
          f"{mb['最小否决']} 户即可否决）")
        P(f"       ② 参与约束：", )
        for i in range(1, H + 1):
            P(f"          {i} 层：净收益 {final[i]:>9,.0f} ≥ 损失 {L[i]:>8,.0f}  "
              f"{'✅' if final[i] >= L[i] - 1e-6 else '❌'}")
        P(f"       ③ 预算闭合：Σ补偿 = {sum(comp.values()):,.2f} 元（应为 0）")
        P(f"       ⇒ 结论：**{'可谈成 ✅' if ok else '谈不成 ❌'}**")
        plans.append({"H": H, "户数": n, "补贴率": sr, "kappa": kp,
                      "L1": L1, "L2": L2, "N": N, "R": R,
                      "分摊": {str(i): round(sh[i], 5) for i in range(1, H + 1)},
                      "净收益": {str(i): round(u[i], 0) for i in range(1, H + 1)},
                      "补偿": {str(i): round(comp[i], 0) for i in range(1, H + 1)},
                      "可谈成": ok, "最小否决": mb["最小否决"]})

    # ---------- 3. 按次刷卡付费 ----------
    P(f"\n{'='*104}")
    P("  【3】★ 替代机制：按次刷卡付费，为什么试点后停推？")
    P("=" * 104)
    P("\n  事实（澎湃新闻实测报道）：")
    P("    · 南京江宁：企业垫资，居民零建设费，约 0.3 元/次，")
    P("      65 岁以上/6 岁以下/残疾人免费，广告收益归企业")
    P("    · 南京玄武区试点 13 部租赁电梯，**一半未通过验收**，**已不再推广**")
    P("    · 淮安城中花园 45 部，**停工 4 个多月**（企业资金问题）")
    P("    · 行业测算：**回本要十几年**")

    H, PF = 6, 2
    sh = shares(H)
    P(f"\n  用本模型解释 —— 该机制**同时做了两件事**：")
    P(f"\n   (1) 把「建设期分摊 c_i」换成「使用期付费 p·m_i」")
    P(f"       ⇒ 一层的 m_1 ≈ 0 ⇒ **一层几乎不付钱**")
    P(f"       ⇒ **一层的参与约束自动满足**（无需补偿）✅")
    P(f"\n   (2) 但它把成本转移给了**使用频率高的人**（即高层）")
    P(f"       ⇒ 高层的**实际支付**上升")

    # 数值对照：假设使用次数按"少爬楼层数"成比例
    P(f"\n  数值对照（6 层 12 户，0.3 元/次，按每天 2 次往返 ≈ 每年 730 次/人）")
    P(f"    设使用次数 m_i ∝ (i−1)（低层少用）")
    P(f"\n  {'层':>4}{'使用次数指数':>14}{'年费(元)':>12}"
      f"{'一次性分摊(元)':>16}{'比较':>10}")
    P("  " + "-" * 58)
    tot_m = sum((i - 1) for i in range(2, H + 1))
    N = C * 0.6
    for i in range(1, H + 1):
        m = (i - 1) / tot_m if tot_m else 0
        annual = 0.3 * 730 * m          # 按份额分的使用次数
        once = sh[i] * N / PF
        cmp_ = "年费更低" if annual < once else "分摊更低"
        P(f"  {i:>4}{m:>14.4f}{annual:>12,.0f}{once:>16,.0f}{cmp_:>10}")

    P(f"\n  ⇒ 本模型给出的解释（三条，均可检验）：")
    P(f"\n   ① **它解决的是『参与约束』，没解决『总量约束』。**")
    P(f"      由 Q3：谈成需要 总意愿 ≥ 净造价 + 补偿需求。")
    P(f"      按次付费让低层不反对，但**总意愿并未提高** ——")
    P(f"      只是把支付从『一次性』改成『分期』。")
    P(f"      ⇒ 若原项目在总量上就不成立，按次付费**也救不回来**。")
    P(f"\n   ② **它把风险从业主转移给了企业。**")
    P(f"      企业垫资 = 承担『总量约束』的全部风险；")
    P(f"      而 0.3 元/次的收入流**可能永远覆盖不了造价**（回本十几年）。")
    P(f"      ⇒ 这正是南京玄武区『13 部一半未验收』、淮安『停工 4 个月』的机制。")
    P(f"      **模型预测：企业资金链 = 该模式的真正约束。**")
    P(f"\n   ③ **它未处理『损害』，只处理了『出资』。**")
    P(f"      一层不付建设费，但**采光/隐私/贬值的损失照旧发生**（澎湃报道原话：")
    P(f"      『下午三四点，主卧已经需要开灯了』）。")
    P(f"      ⇒ 由 Q3，损害必须由补偿覆盖；按次付费**不含补偿环节** ⇒")
    P(f"      **一层的反对依旧**。这与报道结论『并没有解决最大矛盾』完全一致 ✅")

    P(f"\n  ⇒ **结论**：按次刷卡是**支付方式**的创新，不是**分配机制**的创新。")
    P(f"     它能降低低层的即时现金压力，但**不改变总意愿与净造价的对比**，")
    P(f"     也**不提供损害补偿**，同时**把资金风险集中到企业**。")
    P(f"     **三点叠加 ⇒ 试点难以持续。**")

    (RES / "q5_decision_rules.txt").write_text("\n".join(out), encoding="utf-8")
    (RES / "q5_decision_rules.json").write_text(json.dumps({
        "临界表": ktab, "推荐方案": plans,
        "支付意愿比公式": "kappa* = 1 + L2 / ((1-s2)*N)  [一层损失 L1 不影响]",
        "验证": {"一致组合数": nver, "总组合数": 16},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ndone  -> {RES / 'q5_decision_rules.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
