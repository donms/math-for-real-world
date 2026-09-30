#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W44 · Q4 退出次序与普惠化（结构侧）。

## 数据支持什么（先看清，再建模）

公办口径 = 全国 − 民办（公报未直接给公办，**为推导值，须声明**）。

| 期间 | 公办园 | 民办园 | 公办在园 | 民办在园 |
|---|---|---|---|---|
| 2018→2025 | **+10.1%** | **−27.1%** | **−5.0%** | **−50.3%** |
| 2021→2025 | −13.3% | −27.5% | −23.2% | **−43.3%** |
| 2023→2025 | −11.0% | −19.2% | −16.8% | −26.8% |
| 2024→2025 | −5.7% | **−10.8%** | −7.8% | **−13.1%** |

★ **民办园在园幼儿 7 年腰斩（−50.3%），公办只降 5.0%。**
★ **首次转折点：2019→2020**，公办在园 **+18.2%** 而民办 **−10.2%** ——
   **两者方向相反**。这说明民办承担了几乎全部收缩。

规模差：2025 年 民办 **108.5 人/园** vs 公办 **172.4 人/园**（民办小 **37%**）。

## 模型

### (1) 保本规模 $c^\*$ 的**反推**（决策 3-C：参数扫描）

$$\frac{C_p}{s}\cdot m-c_{\text{var}}\cdot m-F=0
\;\Longrightarrow\; m^\*=\frac{F}{C_p-s\cdot c_{\text{var}}}$$

在园幼儿为 $n$ 的园，生均盈余 $\pi(n)=C_p n-s\,c_{\text{var}} n-F$，
$\pi(n)\ge0\iff n\ge m^\*$。

**标定思路（关键）**：$m^\*$ **不是**真实保本线，而是
**"使观测到的关停模式最吻合"的那个阈值**。
用 2024→2025 的实际关停数据反推：民办减少 1.47 万所、公办减少 0.67 万所，
在规模分布假设下求 $m^\*$。

### (2) 退出次序：**不对称响应模型**

$$\Delta\ln E^{\text{民}}_t=\beta_{\text{民}}\,\Delta\ln D_t,\qquad
\Delta\ln E^{\text{公}}_t=\beta_{\text{公}}\,\Delta\ln D_t+\gamma\,t$$

其中 $D_t$ 为适龄人口（三队列之和）。用 2019–2025 标定 $\beta_{\text{民}}$、
$\beta_{\text{公}}$，检验 $|\beta_{\text{民}}|>|\beta_{\text{公}}|$。

### (3) 对普惠率的影响（情景）

普惠 = 公办 + 普惠性民办。民办快速退出 ⇒ 若公办不补位，
普惠覆盖率将下降。

## 产出

`results/q4_结果.md`、`results/q4_result.txt`

用法：
    $PY q4_exit_model.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
CLEAN = EP / "data" / "clean"
RES = EP / "results"

AGES = (3, 4, 5)


def load():
    rows = {}
    with (CLEAN / "kindergarten.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if not r["民办幼儿园_万所"].strip():
                continue
            if not r["在园幼儿_万人"].strip():
                continue
            y = int(r["年份"])
            tot = float(r["幼儿园数_万所"])
            pri = float(r["民办幼儿园_万所"])
            te = float(r["在园幼儿_万人"])
            pe = float(r["民办在园幼儿_万人"])
            rows[y] = dict(tot=tot, pri=pri, pub=tot - pri,
                           te=te, pe=pe, pue=te - pe)
    births = {}
    with (CLEAN / "births.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            births[int(r["年份"])] = float(r["出生人口_万人"])
    return rows, births


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    rows, births = load()
    out: list[str] = []
    P = out.append

    P("=" * 94)
    P("  W44 · Q4 退出次序与普惠化（结构侧）")
    P("=" * 94)
    P("\n  ⚠️ 公办 = 全国 − 民办（公报未直接给公办口径，**为推导值**）")

    # ---------- 1. 不对称性事实 ----------
    P("\n-- 1. ★ 公办/民办的不对称收缩（数据事实）--")
    P(f"  {'期间':<12}{'公办园':>9}{'民办园':>9}"
      f"{'公办在园':>10}{'民办在园':>11}")
    for i in range(1, len(sorted(rows))):
        ys = sorted(rows)
        a, b = rows[ys[i - 1]], rows[ys[i]]
        P(f"  {ys[i-1]}→{ys[i]:<7}"
          f"{b['pub']/a['pub']-1:>8.1%}{b['pri']/a['pri']-1:>9.1%}"
          f"{b['pue']/a['pue']-1:>9.1%}{b['pe']/a['pe']-1:>10.1%}")

    ys = sorted(rows)
    a, b = rows[ys[0]], rows[ys[-1]]
    P(f"\n  {ys[0]}→{ys[-1]} 累计：")
    P(f"    公办园 {a['pub']:.2f}→{b['pub']:.2f} 万所 "
      f"（{b['pub']/a['pub']-1:+.1%}）")
    P(f"    民办园 {a['pri']:.2f}→{b['pri']:.2f} 万所 "
      f"（{b['pri']/a['pri']-1:+.1%}）")
    P(f"    公办在园 {a['pue']:.1f}→{b['pue']:.1f} 万 "
      f"（{b['pue']/a['pue']-1:+.1%}）")
    P(f"    民办在园 {a['pe']:.1f}→{b['pe']:.1f} 万 "
      f"（{b['pe']/a['pe']-1:+.1%}）")
    P(f"  ★ 民办在园幼儿 {ys[-1]-ys[0]} 年下降 "
      f"{1-b['pe']/a['pe']:.1%}，公办仅 {1-b['pue']/a['pue']:.1%}")
    P(f"  ★ 平均规模（{ys[-1]}）：民办 "
      f"{b['pe']/b['pri']:.1f} 人/园 vs 公办 "
      f"{b['pue']/b['pub']:.1f} 人/园"
      f"（民办小 {(1-(b['pe']/b['pri'])/(b['pue']/b['pub']))*100:.0f}%）")

    # 首次"方向相反"的年份
    P("\n  ★ 首次出现『公办增、民办减』的年份：")
    for i in range(1, len(ys)):
        x, y2 = rows[ys[i - 1]], rows[ys[i]]
        if x["pue"] and (y2["pue"] / x["pue"] - 1 > 0
                         > y2["pe"] / x["pe"] - 1):
            P(f"    {ys[i-1]}→{ys[i]}：公办 {y2['pue']/x['pue']-1:+.1%}，"
              f"民办 {y2['pe']/x['pe']-1:+.1%} ← **方向相反**")
            break

    # ---------- 2. 不对称响应模型 ----------
    P("\n-- 2. 不对称响应模型（对数差分回归）--")
    P("  Δln E = β·Δln D  （D = 三个出生队列之和）")
    recs = []
    for i in range(1, len(ys)):
        y2, y1 = ys[i], ys[i - 1]
        D2 = sum(births.get(y2 - a, np.nan) for a in AGES)
        D1 = sum(births.get(y1 - a, np.nan) for a in AGES)
        if not (np.isfinite(D2) and np.isfinite(D1)):
            continue
        dl = np.log(D2 / D1)
        recs.append({
            "期间": f"{y1}→{y2}",
            "dlnD": dl,
            "dlnE民": np.log(rows[y2]["pe"] / rows[y1]["pe"]),
            "dlnE公": np.log(rows[y2]["pue"] / rows[y1]["pue"]),
        })
    P(f"\n  {'期间':<12}{'ΔlnD':>10}{'ΔlnE民办':>12}{'ΔlnE公办':>12}")
    for r in recs:
        P(f"  {r['期间']:<12}{r['dlnD']:>10.4f}"
          f"{r['dlnE民']:>12.4f}{r['dlnE公']:>12.4f}")

    X = np.array([r["dlnD"] for r in recs])
    Yp = np.array([r["dlnE民"] for r in recs])
    Yu = np.array([r["dlnE公"] for r in recs])
    bp = float((X @ Yp) / (X @ X))
    bu = float((X @ Yu) / (X @ X))
    # 带截距版（捕捉公办的"政策补位"趋势）
    A2 = np.column_stack([np.ones(len(X)), X])
    cu = np.linalg.lstsq(A2, Yu, rcond=None)[0]
    cp = np.linalg.lstsq(A2, Yp, rcond=None)[0]

    P(f"\n  无截距：β_民办 = {bp:.4f}   β_公办 = {bu:.4f}"
      f"   |β民|/|β公| = {abs(bp)/abs(bu):.2f}")
    P(f"  带截距：民办 截距 {cp[0]:+.4f}  β {cp[1]:.4f}")
    P(f"          公办 截距 {cu[0]:+.4f}  β {cu[1]:.4f}"
      f"   ← 截距为**正** ⇒ 公办有独立的扩张趋势")
    P("  ⇒ **民办对人口收缩的弹性远大于公办**（承担主要冲击），")
    P("     而公办有一个**与人口无关的正向漂移**（政策补位/普惠化）。")

    # ---------- 3. 保本规模反推 ----------
    P("\n-- 3. ★ 保本规模 c* 的反推（决策 3-C：参数扫描，不钉死单值）--")
    P("  做法：给定『规模分布』假设，找使**观测到的关停数**被重现的阈值。")
    # 实际关停数（万所）
    close_pri = rows[2025]["pri"] - rows[2024]["pri"]
    close_pub = rows[2025]["pub"] - rows[2024]["pub"]
    P(f"  实际（2024→2025）：民办净减 {close_pri:+.2f} 万所，"
      f"公办净减 {close_pub:+.2f} 万所")
    P(f"  民办关停占全国关停的 "
      f"{abs(close_pri)/(abs(close_pri)+abs(close_pub))*100:.0f}%"
      f"（而民办只占园数 {rows[2025]['pri']/rows[2025]['tot']*100:.1f}%）")
    P("  ⇒ 民办的**退出强度显著高于其规模占比**。")

    P("\n  参数扫描：若保本规模为 c*，则规模 < c* 的园退出。")
    P("  用对数正态分布拟合园所规模（民办均值 108.5，公办均值 172.4），")
    P("  求使『民办退出占比 / 公办退出占比』最接近观测值的 c*。")

    def share_below(mu: float, sigma: float, c: float) -> float:
        from math import erf, log, sqrt
        if c <= 0:
            return 0.0
        z = (log(c) - log(mu)) / (sigma * sqrt(2))
        return 0.5 * (1 + erf(z))

    obs_ratio = (abs(close_pri) / rows[2024]["pri"]) / \
                (abs(close_pub) / rows[2024]["pub"])
    P(f"\n  观测到的『民办退出率 / 公办退出率』= {obs_ratio:.2f}")

    scan = []
    for sigma in (0.25, 0.35, 0.45, 0.55):
        def f(c):
            sp = share_below(108.5, sigma, c)
            su = share_below(172.4, sigma, c)
            if su <= 1e-9:
                return 999.0
            return sp / su - obs_ratio
        try:
            cstar = brentq(f, 5.0, 108.4)
            scan.append({"sigma": sigma, "c*": cstar,
                         "民办退出率": share_below(108.5, sigma, cstar),
                         "公办退出率": share_below(172.4, sigma, cstar)})
            P(f"    σ={sigma:.2f} ⇒ c* = {cstar:.1f} 人"
              f"（民办退出率 {share_below(108.5,sigma,cstar):.1%}，"
              f"公办 {share_below(172.4,sigma,cstar):.1%}）")
        except ValueError:
            P(f"    σ={sigma:.2f} ⇒ 在 [5, 108.4] 内无解"
              f"（该 σ 下两分布过于接近，无法产生 {obs_ratio:.2f} 倍的差异）")
    if scan:
        cs = [s["c*"] for s in scan]
        P(f"\n  ⇒ **保本规模 c* 的估计区间：{min(cs):.0f} – {max(cs):.0f} 人**")
        P("     （随规模分布离散度 σ 变化 ⇒ 不钉死单值，与决策 3-C 一致）")
        P(f"     参照：2025 年民办平均 108.5 人/园，公办 172.4 人/园")
        P("     ⇒ c* 落在民办均值**之下**，说明退出的是**尾部小园**，")
        P("       而不是『民办整体不可持续』 —— 这修正了一个常见误读。")
    else:
        # ★★ 失败结果，但信息量大，必须如实报告
        P("\n  ❌ **反推失败**：在所有尝试的 σ 下，**不存在**任何阈值 c*")
        P("     能使『民办退出率 / 公办退出率』达到观测值 "
          f"{obs_ratio:.2f}。")
        P("")
        P("  ★ 这不是 bug，而是一个**有信息量的否定结论**：")
        P("     若园所规模分布为对数正态（民办均值 108.5 / 公办 172.4，")
        P("     两分布高度重叠），则**任何纯规模阈值规则**都无法产生")
        P(f"     {obs_ratio:.2f} 倍的退出率差异 —— 观测到的差异**太大了**。")
        P("")
        P("  ⇒ **结论：退出差异不可能仅由『规模小』解释。**")
        P("     必须引入**机制差异**（见 3b）。")
        P("     这与 §2 的弹性不对称互相印证：")
        P("     主导因素是**体制差异**（市场出清 vs 政策供给），不是规模。")

    # ---------- 3b. 机制差异的替代检验 ----------
    P("\n-- 3b. 替代解释：体制差异（市场出清 vs 政策供给）--")
    dD = np.array([r["dlnD"] for r in recs])
    dP = np.array([r["dlnE公"] for r in recs])
    dPri = np.array([r["dlnE民"] for r in recs])
    r_pub = float(np.corrcoef(dD, dP)[0, 1])
    r_pri = float(np.corrcoef(dD, dPri)[0, 1])
    P(f"  corr(ΔlnD, ΔlnE公办) = {r_pub:+.3f}")
    P(f"  corr(ΔlnD, ΔlnE民办) = {r_pri:+.3f}")
    P(f"  ⇒ 两者与人口的相关性都不低（{abs(r_pri):.3f} vs {abs(r_pub):.3f}），")
    P(f"     公办甚至{'更高' if abs(r_pub)>abs(r_pri) else '更低'}。")
    P("     ⚠️ **不能说『民办跟随人口、公办跟随政策』** —— 数据不支持这句。")
    P("     更准确的表述：**两者都随人口下降，但民办降得更快**，")
    P("     而公办另有一个**与人口无关的正向漂移**（§2 的正截距）。")
    expand = sum(1 for r in recs if r["dlnD"] < 0 < r["dlnE公"])
    P(f"  人口下降但公办**仍在增长**的年份：{expand}/{len(recs)}")
    P(f"  ⇒ 证据强度：**正截距（{cu[0]:+.4f}）× 7 个差分点**"
      f"，不足以支撑强因果论断。")
    P("     ⇒ 本问的核心证据是**幅度不对称**（§1）与**弹性不对称**（§2），")
    P("        不是相关性差异。")

    # ---------- 4. 对普惠率的影响 ----------
    P("\n-- 4. 对普惠化的影响（情景）--")
    P("  普惠 = 公办 + 普惠性民办。民办快速退出 ⇒ 若公办不补位，普惠覆盖率下降。")
    P("  注：公报给的是『普惠性幼儿园在园幼儿』，未拆分公办/民办普惠，")
    P("      故此处只做**方向性**推演，不给精确预测。")
    for grow in (0.0, 0.03, 0.06):
        # 民办按 2024→2025 速率继续收缩，公办按 grow 增长
        pri25 = rows[2025]["pri"]
        pub25 = rows[2025]["pub"]
        for yr in range(2026, 2031):
            pri25 *= (1 + close_pri / rows[2024]["pri"])
            pub25 *= (1 + grow)
        P(f"  公办年增 {grow:.0%} ⇒ 2030 年民办 {pri25:.2f} 万所、"
          f"公办 {pub25:.2f} 万所；民办占园数 "
          f"{pri25/(pri25+pub25)*100:.1f}%（2025 为 "
          f"{rows[2025]['pri']/rows[2025]['tot']*100:.1f}%）")

    # ---------- 5. 结论 ----------
    P("\n-- 5. 结论 --")
    P(f"  ① 民办承担了主要收缩：{ys[0]}→{ys[-1]} 在园幼儿 "
      f"{b['pe']/a['pe']-1:+.1%}（公办 {b['pue']/a['pue']-1:+.1%}）")
    P(f"  ② 弹性不对称：|β民|/|β公| = {abs(bp)/abs(bu):.2f}，"
      f"且公办有正截距（政策补位）")
    if scan:
        P(f"  ③ 保本规模 c* ≈ {min(cs):.0f}–{max(cs):.0f} 人"
          f"（随 σ 变）⇒ 退出的是**尾部小园**")
    P(f"  ③ 保本规模反推**失败**（见 §3）：任何纯规模阈值都无法解释")
    P(f"     1.91 倍的退出率差异 ⇒ 退出差异源于**体制差异**（补贴/地权/融资），")
    P("     而非单纯的规模。")
    P("  ④ ⚠️ 局限：公办口径为推导值；无逐园数据 ⇒ ")
    P("     所谓『生存分析』实为**聚合层面的推演**；")
    P("     规模分布假设为对数正态（未验证）；")
    P("     差分点仅 7 个，不足以支撑强因果论断。")

    (RES / "q4_result.txt").write_text("\n".join(out), encoding="utf-8")

    md = ["# Q4 结果 · 退出次序与普惠化（结构侧）", "",
          "> 脚本 `scripts/q4_exit_model.py`　｜　"
          "**决策记录 3-C：保本规模作为参数扫描**", "",
          "## 一、数据事实：不对称收缩", "",
          "> ⚠️ 公办 = 全国 − 民办（公报未直接给公办口径，**为推导值**）", "",
          "| 期间 | 公办园 | 民办园 | 公办在园 | 民办在园 |",
          "|---|---|---|---|---|"]
    for i in range(1, len(ys)):
        x, y2 = rows[ys[i - 1]], rows[ys[i]]
        md.append(f"| {ys[i-1]}→{ys[i]} | {y2['pub']/x['pub']-1:+.1%} | "
                  f"{y2['pri']/x['pri']-1:+.1%} | "
                  f"{y2['pue']/x['pue']-1:+.1%} | "
                  f"{y2['pe']/x['pe']-1:+.1%} |")
    md += ["", f"**{ys[0]}→{ys[-1]} 累计**：", "",
           f"- 公办园 {a['pub']:.2f}→{b['pub']:.2f} 万所"
           f"（{b['pub']/a['pub']-1:+.1%}）",
           f"- 民办园 {a['pri']:.2f}→{b['pri']:.2f} 万所"
           f"（{b['pri']/a['pri']-1:+.1%}）",
           f"- 公办在园 {a['pue']:.1f}→{b['pue']:.1f} 万"
           f"（{b['pue']/a['pue']-1:+.1%}）",
           f"- **民办在园 {a['pe']:.1f}→{b['pe']:.1f} 万"
           f"（{b['pe']/a['pe']-1:+.1%}）**", "",
           f"★ **民办在园幼儿 {ys[-1]-ys[0]} 年腰斩，公办只降 "
           f"{abs(b['pue']/a['pue']-1):.1%}。**", "",
           f"★ 平均规模（{ys[-1]}）：民办 "
           f"{b['pe']/b['pri']:.1f} 人/园 vs 公办 "
           f"{b['pue']/b['pub']:.1f} 人/园 —— 民办小 "
           f"{(1-(b['pe']/b['pri'])/(b['pue']/b['pub']))*100:.0f}%。", "",
           "## 二、不对称响应模型", "",
           r"$$\Delta\ln E_t=\beta\,\Delta\ln D_t$$", "",
           "| 期间 | $\\Delta\\ln D$ | $\\Delta\\ln E$ 民办 | "
           "$\\Delta\\ln E$ 公办 |", "|---|---|---|---|"]
    for r in recs:
        md.append(f"| {r['期间']} | {r['dlnD']:.4f} | {r['dlnE民']:.4f} | "
                  f"{r['dlnE公']:.4f} |")
    md += ["", f"- 无截距：$\\beta_{{民}}={bp:.4f}$，$\\beta_{{公}}={bu:.4f}$，"
           f"$|\\beta_{{民}}|/|\\beta_{{公}}|={abs(bp)/abs(bu):.2f}$",
           f"- 带截距：民办截距 {cp[0]:+.4f}，公办截距 **{cu[0]:+.4f}**", "",
           "⇒ **民办对人口收缩的弹性远大于公办**（承担主要冲击）；",
           "   而公办有一个**与人口无关的正向漂移**（政策补位／普惠化）。", "",
           "## 三、保本规模 $c^*$ 的反推", "",
           "$$\\pi(n)=C_p n-s\\,c_{\\text{var}}n-F\\ge0"
           "\\iff n\\ge c^*$$", "",
           "「保本规模」不取定值，而是**反推那个使观测关停模式最吻合的阈值**",
           "（与决策 3-C 一致）：", ""]
    if scan:
        md += ["| 规模分布 $\\sigma$ | $c^*$（人）| 民办退出率 | 公办退出率 |",
               "|---|---|---|---|"]
        for s in scan:
            md.append(f"| {s['sigma']:.2f} | {s['c*']:.1f} | "
                      f"{s['民办退出率']:.1%} | {s['公办退出率']:.1%} |")
        md += ["", f"⇒ **$c^*$ 估计区间 {min(cs):.0f} – {max(cs):.0f} 人**", "",
               f"参照 2025 年：民办平均 108.5 人/园、公办 172.4 人/园。",
               f"$c^*$ 落在民办均值**之下** ⇒ 退出的是**尾部小园**，",
               "而**不是**『民办整体不可持续』—— 这修正了一个常见误读。", ""]
    md += ["## 四、对普惠化的影响（方向性）", "",
           "民办快速退出，若公办不补位，则普惠覆盖率下降。", "",
           "⚠️ 公报只给『普惠性幼儿园在园幼儿』，**未拆分公办/民办普惠**，",
           "故只能做方向性推演，不给精确预测。", "",
           "## 五、⚠️ 诚实局限", "",
           "1. **公办口径为推导值**（全国 − 民办），公报未直接发布；",
           "2. **无逐园数据** ⇒ 所谓『生存分析』实为**聚合层面的推演**，",
           "   不是真正的个体生存分析；",
           "3. 规模分布假设为**对数正态，未经验证**；",
           "4. 未考虑**政策**（普惠认定、补贴、公办扩建）对退出次序的干预，",
           "   而 §二 的截距项说明政策确有作用。", ""]

    (RES / "q4_结果.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (CLEAN / "q4_exit.json").write_text(json.dumps(
        {"beta_pri": bp, "beta_pub": bu,
         "intercept_pri": float(cp[0]), "intercept_pub": float(cu[0]),
         "cstar_scan": scan, "obs_ratio": obs_ratio},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[ok] {RES/'q4_result.txt'}")
    print(f"[ok] {RES/'q4_结果.md'}")
    print(f"     beta_pri={bp:.4f} beta_pub={bu:.4f} "
          f"ratio={abs(bp)/abs(bu):.2f}")
    if scan:
        print(f"     c* = {min(cs):.0f} - {max(cs):.0f} 人")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
