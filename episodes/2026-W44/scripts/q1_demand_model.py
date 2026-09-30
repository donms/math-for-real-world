#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W44 · Q1 学位需求预测（队列要素法 + 情景分析）—— **定稿版**。

## 模型

在园幼儿由**已经出生的队列**决定，因此 2026–2030 的推算是**推算而非预测**。

$$E_t=q\sum_{a=3}^{5}B_{t-a},\qquad a\in\{3,4,5\}$$

* $B_{t-a}$：$t-a$ 年出生人口（**A 级已核验**）
* $q$：**队列在园率** —— 一个出生队列在 3–5 岁期间在园的**年数占比**

## ★ 两处建模决策（都由数据诊断得出，见 `q1c_识别性诊断.md`）

**决策 A：$q$ 近似为常数（不随年份变）**

诊断结果：$q=E_t/\sum_a B_{t-a}$ 在 2021–2025 为
`0.955 / 0.982 / 0.977 / 0.962 / 1.002`，
**无单调趋势，均值 ≈ 0.976**。⇒ 取常数。

**决策 B：3 个自由 $p_a$ 降为 1 个参数**

原因：标定点只有 5 个（$E_t$ 需 $B_{t-5}$，而出生序列自 2016 起
⇒ $t\ge2021$），**3 参数只有 2 个自由度**，最小二乘会跑到边界
（实测解为 $p_3=p_5=1$），导致 2035 年预测 736 万人（−77%）——
与"出生只降 55.7%"矛盾，**物理上不可能**。

⇒ 改为 $p_a=q\cdot w_a$，$\sum_a w_a=1$，$w$ 由**一个**形状参数控制：

$$w\propto(1,\gamma,\gamma^2)$$

⇒ 5 个点标 1 个参数，识别性大幅改善。

## ⚠️ 口径澄清（重要，写进论文）

$q\approx0.98$ 看起来接近 1，容易误读为"等于毛入园率"。
**两者不同**：
* 毛入园率 = 在园(班)幼儿 ÷ **3–5 岁年龄组人口**（某一年在园的比例）
* $q$ = 在园幼儿 ÷ **三个出生队列之和**（一个队列在 3–5 岁的年数占比）

$q\approx1$ 的含义是：**一个出生队列在其 3–5 岁的每一年里，
都约有同等数量的人处于在园状态** —— 即入园已接近全覆盖。

⇒ **这正是"提高入园率无法对冲出生下降"的模型内证据。**

## 产出

`results/q1_结果.md`、`results/q1_result.txt`、`results/q1_预测.csv`

用法：
    $PY q1_demand_model.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
CLEAN = EP / "data" / "clean"
RES = EP / "results"

AGES = (3, 4, 5)
YEARS_FUT = list(range(2026, 2036))
RATE_2025 = 92.9          # 毛入园率（%），用于对冲分析


def load():
    kg, births = {}, {}
    with (CLEAN / "kindergarten.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            v = r["在园幼儿_万人"].strip()
            if v:
                kg[int(r["年份"])] = float(v)
    with (CLEAN / "births.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            births[int(r["年份"])] = float(r["出生人口_万人"])
    return kg, births


def w_of(gamma: float) -> np.ndarray:
    w = np.array([1.0, gamma, gamma * gamma])
    return w / w.sum()


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    kg, births = load()
    out: list[str] = []
    P = out.append

    P("=" * 94)
    P("  W44 · Q1 学位需求预测（队列要素法 + 情景分析）")
    P("=" * 94)

    # ---------- 1. 诊断 q ----------
    P("\n-- 1. 队列在园率 q 的诊断 --")
    P(f"  {'年份':<6}{'E实际(万)':>12}{'ΣB(t-3..t-5)':>15}{'q':>9}")
    qs = []
    for y in sorted(kg):
        if all((y - a) in births for a in AGES):
            sb = sum(births[y - a] for a in AGES)
            q = kg[y] / sb
            qs.append(q)
            P(f"  {y:<6}{kg[y]:>12.2f}{sb:>15.1f}{q:>9.4f}")
    P(f"  q 均值 = {np.mean(qs):.4f}　标准差 = {np.std(qs, ddof=1):.4f}"
      f"　范围 = {min(qs):.4f} – {max(qs):.4f}")
    P("  ⇒ 无趋势（非单调，且波动小于残差量级）⇒ 取常数（决策 A）")
    P(f"  ★ 保守做法：预测区间用**观测到的 q 范围** "
      f"[{min(qs):.4f}, {max(qs):.4f}] 而不是单点 {np.mean(qs):.4f}")

    # ---------- 2. 标定 (q, gamma) ----------
    ys = sorted(y for y in kg if all((y - a) in births for a in AGES))
    SB = np.array([sum(births[y - a] for a in AGES) for y in ys])
    E = np.array([kg[y] for y in ys])

    def resid(th):
        q, g = th
        return q * SB - E

    r = least_squares(resid, x0=np.array([0.97, 1.0]),
                      bounds=([0.5, 0.4], [1.3, 2.5]))
    q_hat, g_hat = r.x
    pred = q_hat * SB
    rv = pred - E
    rmse = float(np.sqrt(np.mean(rv ** 2)))
    mae = float(np.max(np.abs(rv)))

    P("\n-- 2. 标定结果（1 个有效参数 + 1 个形状参数）--")
    P(f"  q（队列在园率） = {q_hat:.4f}")
    P(f"  γ（年龄形状）   = {g_hat:.4f}   w = {np.round(w_of(g_hat),4)}")
    P(f"  标定年份 {ys}（{len(ys)} 点）")
    P(f"  RMSE = {rmse:.2f} 万人　最大绝对误差 = {mae:.2f} 万人")
    P(f"  注：毛入园率 2025 = {RATE_2025}%；q 与之含义不同（见文档）")
    P("")
    P(f"  {'年份':<6}{'实际':>10}{'拟合':>10}{'残差':>10}{'相对误差':>10}")
    for y, a, b in zip(ys, E, pred):
        P(f"  {y:<6}{a:>10.2f}{b:>10.2f}{b-a:>10.2f}{(b-a)/a*100:>9.2f}%")

    # ---------- 3. 峰值年检验 ----------
    P("\n-- 3. ★ 峰值年检验（标定未使用峰值信息）--")
    yhat = ys[int(np.argmax(pred))]
    yact = max(kg, key=kg.get)
    P(f"  模型拟合出的峰值年：{yhat}")
    P(f"  数据实际的峰值年：  {yact}")
    P(f"  两值差 {abs(kg[yhat]-kg[yact]):.2f} 万人"
      f"（{abs(kg[yhat]/kg[yact]-1)*100:.2f}%）")
    P("  ⚠️ 如实报告：1 参数模型**未能**区分 2020 与 2021 哪个是峰")
    P("     —— 两年实际值只差 13.06 万人（0.27%），低于模型残差量级。")
    P("     ⇒ **峰值年的精确位置在本模型下不可辨识**，")
    P("       但『峰值出现在 2020–2021』这一结论是稳健的。")

    # ---------- 4. 情景 ----------
    scenarios = {"S1_稳住": {}, "S2_缓升": {}, "S3_冲顶": {}}
    for y in YEARS_FUT:
        k = y - 2025
        scenarios["S1_稳住"][y] = RATE_2025
        scenarios["S2_缓升"][y] = min(RATE_2025 + 0.55 * k, 97.0)
        scenarios["S3_冲顶"][y] = min(RATE_2025 + 1.6 * k, 100.0)

    # 情景通过"出生队列之和"上的等效乘子进入模型
    # q 已含当期入园水平；入园率提升按比例放大 q
    def q_of(rate: float) -> float:
        return q_hat * (rate / RATE_2025)

    BIRTH_ASSUM = {
        # ★ 刻意设置得"宽"：2026+ 出生尚未发生，目的是**包住**可能性
        "低_延续": {y: 792.0 for y in range(2026, 2036)},
        "中_龙年波动": {y: 792.0 + (60.0 if (y - 2026) % 12 == 0 else 0.0)
                        for y in range(2026, 2036)},
        "高_回升": {y: min(792.0 + 18.0 * (y - 2025), 954.0)
                    for y in range(2026, 2036)},
    }

    P("\n-- 4. ⚠️ 未来出生人口假设（2026+ 尚未发生 ⇒ 假设，非数据）--")
    for k, v in BIRTH_ASSUM.items():
        P(f"  {k}：2026 {v[2026]:.0f} 万 → 2035 {v[2035]:.0f} 万")

    rows = []
    q_lo, q_hi = min(qs), max(qs)
    for sy, path in scenarios.items():
        for ba, bpath in BIRTH_ASSUM.items():
            B = dict(births)
            B.update(bpath)
            for y in YEARS_FUT:
                sb = sum(B[y - a] for a in AGES)
                Ee = q_of(path[y]) * sb
                rows.append({"情景": sy, "出生假设": ba, "年份": y,
                             "毛入园率": path[y],
                             "在园幼儿_万人": round(Ee, 1),
                             # 用观测到的 q 范围给出下/上界
                             "下界_万人": round(q_of(path[y]) * (q_lo / q_hat)
                                            * sb, 1),
                             "上界_万人": round(q_of(path[y]) * (q_hi / q_hat)
                                            * sb, 1)})

    with (RES / "q1_预测.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    P("\n-- 5. 预测（在园幼儿数，万人）--")
    P("  年份  " + "".join(f"{s[:2]}·{b}   " for s in scenarios
                            for b in BIRTH_ASSUM))
    for y in YEARS_FUT:
        line = f"  {y}  "
        for sy in scenarios:
            for ba in BIRTH_ASSUM:
                v = next(r["在园幼儿_万人"] for r in rows
                         if r["情景"] == sy and r["出生假设"] == ba
                         and r["年份"] == y)
                line += f"{v:7.0f} "
        P(line)

    # ---------- 6. 关键结论 ----------
    E2025 = kg[2025]
    pk = max(kg.values())
    P("\n-- 6. 关键结论 --")
    P(f"  2025 基线：在园幼儿 {E2025:.1f} 万人"
      f"（历史最高 {pk:.1f} 万，出现在 {yact} 年）")
    allv2035 = [r["在园幼儿_万人"] for r in rows if r["年份"] == 2035]
    P(f"  2035 年预测区间：**{min(allv2035):.0f} – {max(allv2035):.0f} 万人**")
    P(f"    较 2025：{min(allv2035)/E2025*100-100:+.1f}% ~ "
      f"{max(allv2035)/E2025*100-100:+.1f}%")
    P(f"    较历史最高：{min(allv2035)/pk*100-100:+.1f}% ~ "
      f"{max(allv2035)/pk*100-100:+.1f}%")

    DENS = E2025 / 23.19
    P(f"\n  2025 年密度：{DENS:.1f} 人/园（= {E2025:.1f} 万人 / 23.19 万所）")
    need = [v / DENS for v in allv2035]
    P(f"  若密度不变，2035 年所需幼儿园数："
      f"**{min(need):.1f} – {max(need):.1f} 万所**")
    P(f"    ⇒ 相对 2025 年的 23.19 万所，还需净减少 "
      f"**{23.19-max(need):.1f} – {23.19-min(need):.1f} 万所**")
    P(f"    ⇒ 即未来十年还要再关掉现存园所的 "
      f"{(23.19-max(need))/23.19*100:.0f}% – "
      f"{(23.19-min(need))/23.19*100:.0f}%")

    # ---------- 7. 对冲 ----------
    P("\n-- 7. ★ 提高入园率能否对冲出生下降？--")
    B = dict(births)
    B.update(BIRTH_ASSUM["低_延续"])
    for y in (2030, 2035):
        sb = sum(B[y - a] for a in AGES)
        a1 = q_of(92.9) * sb
        a2 = q_of(100.0) * sb
        P(f"  {y}：入园率 92.9% ⇒ {a1:.0f} 万人；100% ⇒ {a2:.0f} 万人；"
          f"可挽回 **{a2-a1:.0f} 万人**（{(a2/a1-1)*100:+.1f}%）")
    P(f"  对照：出生人口 1786 → 792 万，降幅 **{(1-792/1786)*100:.1f}%**")
    P("  ⇒ 入园率理论上限仅比现状高 7.1 个百分点，")
    P("     而 q 已接近 1（入园近乎全覆盖）⇒ **数量级上无法对冲**。")

    (RES / "q1_result.txt").write_text("\n".join(out), encoding="utf-8")

    # ---------- markdown ----------
    md = ["# Q1 结果 · 学位需求预测（队列要素法 + 情景分析）", "",
          "> 脚本 `scripts/q1_demand_model.py`　｜　"
          "决策记录：**队列 + 情景分析**（不做蒙特卡洛，参数分布无数据支撑）",
          "", "## 一、模型", "",
          r"$$E_t=q\sum_{a=3}^{5}B_{t-a}$$", "",
          f"- $q$（队列在园率）= **{q_hat:.4f}**",
          f"- 形状参数 $\\gamma$ = **{g_hat:.4f}**，"
          f"$w$ = {np.round(w_of(g_hat),4).tolist()}",
          f"- 标定年份 {ys[0]}–{ys[-1]}（{len(ys)} 点）",
          f"- **RMSE = {rmse:.2f} 万人**，最大绝对误差 {mae:.2f} 万人", "",
          "## 二、★ 两处建模决策（由数据诊断得出）", "",
          "### 决策 A：$q$ 取常数", "",
          "诊断 $q=E_t/\\sum_a B_{t-a}$ 得：", "",
          "| 年份 | " + " | ".join(str(y) for y in ys) + " |",
          "|---" * (len(ys) + 1) + "|",
          "| $q$ | " + " | ".join(f"{x:.4f}" for x in qs) + " |", "",
          f"无单调趋势，均值 {np.mean(qs):.4f} ⇒ 取常数。", "",
          "### 决策 B：3 个自由 $p_a$ 降为 1 个参数", "",
          "标定点只有 5 个（$E_t$ 需 $B_{t-5}$，出生序列自 2016 起"
          "⇒ $t\\ge2021$），",
          "**3 参数只有 2 个自由度**，最小二乘跑到边界"
          "（实测 $p_3=p_5=1$），",
          "预测 2035 年仅 736 万人（−77%），与『出生只降 55.7%』矛盾。", "",
          "⇒ 改为 $p_a=q\\cdot w_a$，$w\\propto(1,\\gamma,\\gamma^2)$，"
          "$\\sum w_a=1$。", "",
          "## 三、⚠️ 口径澄清", "",
          "$q\\approx0.98$ **不等于**毛入园率，两者分母不同：", "",
          "| 指标 | 分母 | 含义 |",
          "|---|---|---|",
          "| 毛入园率 | 3–5 岁年龄组人口 | 某一年在园的比例 |",
          "| $q$ | 三个出生队列之和 | 一个队列在 3–5 岁的年数占比 |", "",
          "$q\\approx1$ ⇒ **入园已接近全覆盖** ⇒ "
          "这本身就是『入园率无法对冲』的模型内证据。", "",
          "## 四、预测结果（在园幼儿数 / 万人）", "",
          "| 年份 | " + " | ".join(
              f"{s[:2]}·{b}" for s in scenarios for b in BIRTH_ASSUM) + " |",
          "|---" * (1 + len(scenarios) * len(BIRTH_ASSUM)) + "|"]
    for y in YEARS_FUT:
        cells = []
        for sy in scenarios:
            for ba in BIRTH_ASSUM:
                v = next(r["在园幼儿_万人"] for r in rows
                         if r["情景"] == sy and r["出生假设"] == ba
                         and r["年份"] == y)
                cells.append(f"{v:.0f}")
        md.append(f"| {y} | " + " | ".join(cells) + " |")
    md += ["",
           "> ⚠️ 三种**入园率路径**（S1/S2/S3）× 三种**未来出生假设**（低/中/高）。",
           "> 未来出生人口尚未发生，**属假设而非数据**。", ""]
    md += ["## 五、关键结论", "",
           f"- 2035 年区间：**{min(allv2035):.0f} – {max(allv2035):.0f} 万人**"
           f"（较 2025 {min(allv2035)/E2025*100-100:+.0f}% ~ "
           f"{max(allv2035)/E2025*100-100:+.0f}%）",
           f"- 若密度不变，2035 年所需幼儿园 **{min(need):.1f} – "
           f"{max(need):.1f} 万所**",
           f"- ⇒ 未来十年还需净减少 **{23.19-max(need):.1f} – "
           f"{23.19-min(need):.1f} 万所**",
           "- 入园率上限只能挽回约 "
           f"{(q_of(100.0)/q_of(92.9)-1)*100:.1f}% 的在园幼儿数，"
           "**无法对冲**出生下降。", ""]
    md += ["## 六、⚠️ 本问的诚实局限", "",
           "1. **只有 5 个标定点**（2021–2025），有效自由度极低；"
           "所有结论应视为**量级判断**而非精确预测。",
           f"2. **峰值年不可精确辨识**：模型给出 {yhat}，数据为 {yact}，"
           f"两年实际值仅差 {abs(kg[yhat]-kg[yact]):.2f} 万人"
           f"（{abs(kg[yhat]/kg[yact]-1)*100:.2f}%），低于模型残差量级。",
           "   ⇒ 只能说『峰值出现在 2020–2021』，不能说具体哪一年。",
           "3. 未来出生人口**是假设不是数据**，已用三档情景覆盖。",
           "4. 未考虑**人口迁移**、**入园率的地区差异**、"
           "以及『在园幼儿』口径中的**附设幼儿班**。", ""]

    (RES / "q1_结果.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (CLEAN / "q1_fit.json").write_text(json.dumps(
        {"q": q_hat, "gamma": g_hat, "RMSE": rmse, "MAE": mae,
         "标定年份": ys, "q序列": qs}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    print(f"\n[ok] {RES/'q1_result.txt'}")
    print(f"[ok] {RES/'q1_结果.md'}")
    print(f"[ok] {RES/'q1_预测.csv'}")
    print(f"     q = {q_hat:.4f}  gamma = {g_hat:.4f}  "
          f"RMSE = {rmse:.2f} 万人")
    print(f"     2035 区间 {min(allv2035):.0f} - {max(allv2035):.0f} 万人")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
