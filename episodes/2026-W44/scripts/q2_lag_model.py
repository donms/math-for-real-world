#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W44 · Q2 传导滞后与「最坏时刻」（决策 2 选 C：**结构化约束**）。

## 问题

出生人口下降到幼儿园关停/在园幼儿下降，中间有几年时滞？
**截至 2025，冲击兑现了多少？最坏时刻到了吗？**

## ★ 方法（决策 2-C：结构化约束，不做纯拟合）

样本极小：在园幼儿只有 2018–2025（8 点），且 $E_t$ 需要 $B_{t-5}$
⇒ **有效标定点只有 2021–2025（5 点）**。
纯 CCF / 无约束 ARDL 在这个样本量下会给出虚假的"最优滞后"。

⇒ 因此**不搜全滞后空间**，而是：
1. 用**机制**限定滞后区间：入园年龄 $3$ 年（下限）
   $\sim$ 入园年龄+退出时滞（上限）。公办园关停需经审批、合并、资产处置，
      经验上再加 $1\!-\!3$ 年 ⇒ 先验区间 $\tau\in[3,6]$。
2. **只在先验区间内**比较拟合优度，选最优 $\tau$，并报告**区间敏感性**。
3. 用**独立的第二个证据**（结构变化点检测）交叉验证 $\tau$ 的合理性。

## 「已兑现比例」的定义（★ 本问的核心构念）

设"峰值窗口"为 $W^\*$（三个出生队列之和最大的那一组），
"谷底窗口"为 $W_{\min}$（已出生里最小的那一组）。定义

$$\text{总落差}=1-\frac{\sum_{W_{\min}}B}{\sum_{W^\*}}B,\qquad
\text{已兑现}=1-\frac{E_t}{\max E},\qquad
\rho=\frac{\text{已兑现}}{\text{总落差}}$$

$\rho<1$ ⇒ **冲击尚未走完**。

## 产出

`results/q2_结果.md`、`results/q2_result.txt`

用法：
    $PY q2_lag_model.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
CLEAN = EP / "data" / "clean"
RES = EP / "results"

AGES = (3, 4, 5)
TAU_RANGE = (3, 4, 5, 6)          # 先验滞后区间（决策 2-C）


def load():
    kg, births, kcount = {}, {}, {}
    with (CLEAN / "kindergarten.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            y = int(r["年份"])
            if r["在园幼儿_万人"].strip():
                kg[y] = float(r["在园幼儿_万人"])
            if r["幼儿园数_万所"].strip():
                kcount[y] = float(r["幼儿园数_万所"])
    with (CLEAN / "births.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            births[int(r["年份"])] = float(r["出生人口_万人"])
    return kg, births, kcount


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    kg, births, kcount = load()
    out: list[str] = []
    P = out.append

    P("=" * 94)
    P("  W44 · Q2 传导滞后与『最坏时刻』")
    P("=" * 94)
    P("\n  方法：**结构化约束**（决策 2-C）")
    P(f"  先验滞后区间 τ ∈ {TAU_RANGE}（入园 3 年 + 退出时滞 0–3 年）")

    # ---------- 1. 两个序列的对齐诊断 ----------
    P("\n-- 1. 两条序列（出生 → 在园幼儿）--")
    P(f"  {'年份':<6}{'出生(万)':>10}{'在园幼儿(万)':>14}{'幼儿园数(万所)':>16}")
    for y in sorted(set(list(births) + list(kg))):
        b = f"{births[y]:.0f}" if y in births else "—"
        e = f"{kg[y]:.2f}" if y in kg else "—"
        k = f"{kcount[y]:.2f}" if y in kcount else "—"
        P(f"  {y:<6}{b:>10}{e:>14}{k:>16}")

    # ---------- 2. 峰值位置（结构性事实） ----------
    P("\n-- 2. ★ 峰值错位（结构性事实，不需要拟合）--")
    yb = max(births, key=births.get)
    ye = max(kg, key=kg.get)
    yk = max(kcount, key=kcount.get)
    P(f"  出生人口峰值年：      {yb}（{births[yb]:.0f} 万）")
    P(f"  在园幼儿峰值年：      {ye}（{kg[ye]:.2f} 万）")
    P(f"  幼儿园数峰值年：      {yk}（{kcount[yk]:.2f} 万所）")
    P(f"  ⇒ 出生→在园 滞后 **{ye-yb} 年**；出生→园数 滞后 **{yk-yb} 年**")
    P("  ⚠️ 注意：这是**峰值位置之差**，不是回归估计的滞后，")
    P("     但它是最稳健的证据（不依赖样本量）。")

    # ---------- 3. 结构化约束下比较 τ ----------
    P("\n-- 3. 结构化约束：在 τ ∈ [3,6] 内比较拟合优度 --")
    P("  模型：E_t = q · Σ_{a=3}^{5} B_{t-τ+?} —— 用『窗口起点滞后』τ 参数化，")
    P("        即 E_t ~ Σ_{j=0..2} B_{t-τ-j+3}")
    P("")
    P(f"  {'τ':>4}{'标定点':>8}{'q':>9}{'RMSE(万)':>12}{'最大误差(万)':>14}")
    results = []
    for tau in TAU_RANGE:
        ys, sb = [], []
        for y in sorted(kg):
            # 窗口：出生年 = y-3-extra .. 其中 extra 由 τ 决定
            extra = tau - 3
            yrs = [y - 3 - extra, y - 4 - extra, y - 5 - extra]
            if all(v in births for v in yrs):
                ys.append(y)
                sb.append(sum(births[v] for v in yrs))
        if len(ys) < 4:
            continue
        SB = np.array(sb)
        E = np.array([kg[y] for y in ys])
        q = float((SB @ E) / (SB @ SB))
        pred = q * SB
        rmse = float(np.sqrt(np.mean((pred - E) ** 2)))
        mx = float(np.max(np.abs(pred - E)))
        results.append({"tau": tau, "ys": ys, "q": q, "rmse": rmse,
                        "max": mx, "pred": pred.tolist(), "E": E.tolist()})
        P(f"  {tau:>4}{len(ys):>8}{q:>9.4f}{rmse:>12.2f}{mx:>14.2f}")
    if results:
        best = min(results, key=lambda r: r["rmse"])
        P(f"\n  ⇒ 先验区间内最优 τ = **{best['tau']}** 年"
          f"（RMSE {best['rmse']:.2f} 万）")
        P(f"     该 τ 对应的窗口起点 = 出生年 {(best['ys'][0]-3-(best['tau']-3))}"
          f" 起")

    # ---------- 4. 独立证据：结构变化点 ----------
    P("\n-- 4. 独立证据：幼儿园数由增转降的年份 --")
    ky = sorted(kcount)
    for i in range(1, len(ky)):
        d = kcount[ky[i]] - kcount[ky[i - 1]]
        if d < 0:
            P(f"  ★ 首次下降：{ky[i-1]} → {ky[i]}，"
              f"{kcount[ky[i-1]]:.2f} → {kcount[ky[i]]:.2f} 万所"
              f"（{d:+.2f} 万所）")
            break
    ky_kg = sorted(kg)
    for i in range(1, len(ky_kg)):
        if kg[ky_kg[i]] < kg[ky_kg[i - 1]]:
            P(f"  ★ 在园幼儿首次下降：{ky_kg[i-1]} → {ky_kg[i]}")
            break

    # ---------- 5. 「已兑现比例」 ----------
    P("\n-- 5. ★★ 核心构念：『已兑现比例』ρ --")
    # 峰值窗口 = 三个出生队列之和最大的窗口（限于已有数据的年份）
    wins = {}
    for t in sorted(kg):
        yrs = [t - a for a in AGES]
        if all(v in births for v in yrs):
            wins[t] = (sum(births[v] for v in yrs), yrs)
    t_peak = max(wins, key=lambda t: wins[t][0])
    sb_peak, yrs_peak = wins[t_peak]
    P(f"  峰值窗口：{t_peak} 年入园，对应出生 {yrs_peak}"
      f"，ΣB = {sb_peak:.0f} 万")

    # 谷底窗口 = 已出生队列里最小的窗口。用**估计出的滞后 τ** 把它翻译成
    # 「哪一年」：出生谷底年 + τ。这样窗口定义与 τ 自洽。
    byrs = sorted(births)
    lo3 = byrs[-3:]
    sb_trough = sum(births[v] for v in lo3)
    t_birth_trough = max(lo3)          # 出生谷底年
    tau_hat = best["tau"] if results else 3
    t_trough = t_birth_trough + tau_hat
    P(f"  谷底窗口：出生 {lo3}（ΣB = {sb_trough:.0f} 万，"
      f"出生谷底年 {t_birth_trough}）")
    P(f"  ⇒ 按 τ = {tau_hat} 年传导 ⇒ 在园幼儿谷底年 ≈ "
      f"**{t_trough}**（= {t_birth_trough} + {tau_hat}）")
    P(f"  ⇒ **总落差** = 1 − {sb_trough:.0f}/{sb_peak:.0f} = "
      f"**{1-sb_trough/sb_peak:.1%}**")

    E_now, E_pk = kg[2025], max(kg.values())
    realized = 1 - E_now / E_pk
    P(f"\n  已发生的在园幼儿降幅：{E_pk:.1f} → {E_now:.1f} 万"
      f" ⇒ **已兑现 {realized:.1%}**")
    rho = realized / (1 - sb_trough / sb_peak)
    P(f"  ⇒ **ρ = 已兑现 / 总落差 = {rho:.1%}**")
    P(f"  ⇒ 仍有 **{1-rho:.1%}** 的冲击**尚未兑现**")

    # 用 Q1 模型给出谷底年份的水平
    qfit = json.loads((CLEAN / "q1_fit.json").read_text(encoding="utf-8"))
    q = qfit["q"]
    E_trough = q * sb_trough
    P(f"\n  用 Q1 标定的 q = {q:.4f} 推算谷底：")
    P(f"    {t_trough} 年在园幼儿 ≈ **{E_trough:.0f} 万人**"
      f"（较 2025 的 {E_now:.1f} 万再降 {E_trough/E_now-1:+.1%}）")
    P(f"    较历史最高 {E_pk:.1f} 万降 {E_trough/E_pk-1:+.1%}")

    # 所需园数
    dens = E_now / kcount[2025]
    P(f"\n  按 2025 密度 {dens:.1f} 人/园：")
    P(f"    谷底需园 {E_trough/dens:.2f} 万所"
      f"，较 2025 的 {kcount[2025]:.2f} 万所再减 "
      f"**{kcount[2025]-E_trough/dens:.2f} 万所**")

    # ---------- 6. 结论 ----------
    P("\n-- 6. 结论 --")
    P(f"  ① 滞后：出生→在园峰值差 {ye-yb} 年，"
      f"结构化约束下最优 τ = {best['tau'] if results else 'NA'} 年")
    P(f"  ② 已兑现比例 ρ = **{rho:.1%}** ⇒ **冲击尚未走完**")
    P(f"  ③ 最坏时刻：在园幼儿谷底约在 **{t_trough} 年**"
      f"（出生谷底 {t_birth_trough} + 传导 {tau_hat} 年）")
    P("     ⚠️ 注意：出生谷底 = 2025（792 万）是**当前数据边界**，")
    P("        若 2026+ 出生继续下降，谷底会**继续后移**。")
    P("     ⇒ **最坏时刻尚未到来**")
    P("  ④ ⚠️ 局限：有效标定点仅 5 个；")
    P("     τ 的辨识依赖先验区间；ρ 的定义依赖『窗口』的选法。")

    (RES / "q2_result.txt").write_text("\n".join(out), encoding="utf-8")

    # ---------- markdown ----------
    md = ["# Q2 结果 · 传导滞后与『最坏时刻』", "",
          "> 脚本 `scripts/q2_lag_model.py`　｜　"
          "**决策记录 2-C：结构化约束**（不做无约束 CCF/ARDL）", "",
          "## 一、为什么用结构化约束", "",
          "在园幼儿只有 2018–2025（8 点），而 $E_t$ 需 $B_{t-5}$，"
          "⇒ **有效标定点只有 2021–2025（5 点）**。",
          "在这个样本量下，无约束地搜全滞后空间会给出**虚假的最优滞后**。",
          "⇒ 用机制把滞后限定在 $\\tau\\in[3,6]$：",
          "入园年龄 3 年（下限）+ 退出时滞 0–3 年（公办园关停需审批/合并/资产处置）。",
          "", "## 二、结构性事实（不依赖拟合）", "",
          "| 序列 | 峰值年 | 峰值 |", "|---|---|---|",
          f"| 出生人口 | **{yb}** | {births[yb]:.0f} 万 |",
          f"| 在园幼儿 | **{ye}** | {kg[ye]:.2f} 万 |",
          f"| 幼儿园数 | **{yk}** | {kcount[yk]:.2f} 万所 |", "",
          f"⇒ 出生 → 在园 滞后 **{ye-yb} 年**；出生 → 园数 滞后 **{yk-yb} 年**。",
          "这是**最稳健的证据**：只用到峰值位置，不依赖样本量。", "",
          "## 三、结构化约束下的滞后比较", "",
          "| $\\tau$（年）| 标定点 | $q$ | RMSE（万人）| 最大误差（万人）|",
          "|---|---|---|---|---|"]
    for r in results:
        md.append(f"| {r['tau']} | {len(r['ys'])} | {r['q']:.4f} | "
                  f"{r['rmse']:.2f} | {r['max']:.2f} |")
    if results:
        md += ["", f"⇒ 先验区间内最优 $\\tau$ = **{best['tau']} 年**。"]
    md += ["", "## 四、★ 核心构念：已兑现比例 $\\rho$", "",
           "$$\\rho=\\frac{\\text{已兑现降幅}}{\\text{总落差}}$$", "",
           "| 项 | 窗口 | $\\sum B$（万人）|", "|---|---|---|",
           f"| 峰值窗口 | {t_peak} 年入园（出生 {yrs_peak}）| "
           f"{sb_peak:.0f} |",
           f"| 谷底窗口 | {t_trough} 年入园（出生 {lo3}）| "
           f"{sb_trough:.0f} |", "",
           f"- **总落差** = {1-sb_trough/sb_peak:.1%}",
           f"- **已兑现**（{E_pk:.0f} → {E_now:.0f} 万）= {realized:.1%}",
           f"- ⇒ $\\rho$ = **{rho:.1%}**",
           f"- ⇒ 仍有 **{1-rho:.1%}** 冲击**尚未兑现**", "",
           "## 五、最坏时刻", "",
           f"- 出生谷底：**{t_birth_trough} 年**"
           f"（{births[t_birth_trough]:.0f} 万）",
           f"- 按传导滞后 $\\tau={tau_hat}$ 年 ⇒ 在园幼儿谷底 "
           f"**{t_trough} 年**",
           f"- 谷底在园幼儿 ≈ **{E_trough:.0f} 万人**（用 $q={q:.4f}$ 推算）",
           f"  （较 2025 再降 {E_trough/E_now-1:+.1%}，"
           f"较历史最高降 {E_trough/E_pk-1:+.1%}）",
           f"- 按 2025 密度，谷底所需幼儿园 ≈ **{E_trough/dens:.2f} 万所**",
           f"  ⇒ 较 2025 还需再减 **{kcount[2025]-E_trough/dens:.2f} 万所**", "",
           "> ⚠️ **谷底年是『移动靶』**："
           "$t_{谷底}=t_{出生谷底}+\\tau$。",
           f"> 当前数据边界内出生谷底是 **{t_birth_trough} 年**；",
           "> 若 2026 年及以后出生继续下降，谷底会**继续后移**。",
           "> 本结论只在『出生不再创新低』的前提下成立。", "",
           "## 六、结论", "",
           "**最坏时刻尚未到来。**", "",
           f"截至 2025 年，出生下降造成的冲击只兑现了约 "
           f"**{rho:.0%}**；剩余约 **{1-rho:.0%}** 将在 "
           f"{t_trough} 年前后集中体现。", "",
           "换句话说：**已经关掉的 6.29 万所不是终点，"
           "这条路才走了一半多一点。**", "",
           "## 七、⚠️ 诚实局限", "",
           "1. **有效标定点仅 5 个**，$\\tau$ 的辨识**依赖先验区间**。",
           f"   实测：$\\tau=3$ 时有 5 个标定点（RMSE "
           f"{results[0]['rmse']:.1f} 万），$\\tau=4$ 时只剩 "
           f"{len(results[1]['ys']) if len(results)>1 else 0} 个"
           f"（RMSE {results[1]['rmse']:.1f} 万）。",
           "   ⇒ 标定点数随 $\\tau$ 增大而减少，**模型无法在大 $\\tau$ 上被公平检验**，",
           "     故 $\\tau=3$ 的胜出**部分源于样本量优势而非纯粹的拟合优度**。",
           "   本报告因此同时给出**不依赖拟合**的峰值错位证据"
           "（出生→在园 4 年、出生→园数 5 年）作为对照。",
           "2. $\\rho$ 的定义依赖**窗口选法**（取连续 3 个出生队列之和）；",
           "   换一种窗口定义会得到不同的 $\\rho$，故 $\\rho$ 应读作"
           "**量级判断**（『约七成』）而非精确值。",
           "3. 未考虑**入园率的地区差异**与**人口迁移**；",
           "4. 「幼儿园数」是**存量**，关停还受政策、资产处置与"
           "补贴节奏影响，模型未显式刻画。", ""]

    (RES / "q2_结果.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (CLEAN / "q2_lag.json").write_text(json.dumps(
        {"tau_best": best["tau"] if results else None,
         "rho": rho, "realized": realized,
         "total_gap": 1 - sb_trough / sb_peak,
         "E_trough": E_trough, "t_trough": t_trough,
         "tau_table": [{k: v for k, v in r.items()
                        if k in ("tau", "q", "rmse", "max")}
                       for r in results]},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[ok] {RES/'q2_result.txt'}")
    print(f"[ok] {RES/'q2_结果.md'}")
    print(f"     tau_best = {best['tau'] if results else None}")
    print(f"     rho = {rho:.1%}  (realized {realized:.1%} / "
          f"total {1-sb_trough/sb_peak:.1%})")
    print(f"     trough ~ {t_trough}, E = {E_trough:.0f} 万人")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
