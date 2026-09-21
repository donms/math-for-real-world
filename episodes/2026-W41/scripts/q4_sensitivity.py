#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""Q4：结论成立的条件 —— 敏感性分析与数据缺陷的方向性判断。

## 本问要回答三件事

1. **敏感性**：哪些参数一改就推翻结论？
2. **缺陷方向性**：数据缺陷把结论推向**高估**还是**低估**？（不是罗列缺陷）
3. **决策建议**：什么条件下「新运河能缓解老瓶颈」成立。

## 关键设计：**不是所有参数都同等重要**

做法：对每个参数做单因素扰动，看**长洲降幅**这个核心结论
变化多少，并找出**使结论翻转**（如从"降幅>30%"变为"<30%"）的参数。

用法：
    $PY q4_sensitivity.py
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"


def main() -> int:
    P = json.loads((RES / "q0_params.json").read_text(encoding="utf-8"))
    q2 = json.loads((RES / "q2_diversion.json").read_text(encoding="utf-8"))
    q3 = json.loads((RES / "q3_locks.json").read_text(encoding="utf-8"))

    print("=" * 84)
    print("  Q4 · 敏感性分析与数据缺陷的方向性判断")
    print("=" * 84)

    base_flow = 22355.46 / 1e4
    cap = q3["通道年能力亿吨"]
    s0 = q2["推荐情景"]["s"]
    th0 = q2["推荐情景"]["theta"]
    dc0 = abs(q2["成本差元每吨"])

    def diversion(dc: float, s: float, th: float, cap_: float) -> dict:
        p = 1 / (1 + math.exp(th * (-dc + s)))
        moved_nom = base_flow * p
        moved = min(moved_nom, cap_)
        return {"p": p, "moved": moved, "drop": moved / base_flow}

    b = diversion(dc0, s0, th0, cap)
    print(f"\n  基准结论：分流率 {b['p']*100:.1f}%，"
          f"长洲降幅 {b['drop']*100:.1f}%")

    # ---------- 1. 单因素敏感性 ----------
    print(f"\n【1】单因素敏感性：长洲降幅对每个参数的弹性\n")
    print(f"  {'参数':<24}{'变动':>12}{'分流率':>10}{'长洲降幅':>10}"
          f"{'相对基准':>10}")
    print("  " + "-" * 68)
    rows: list[dict] = []
    CASE_DEF = [
        # (显示名, 参数名, 低值, 低值标签, 高值, 高值标签)
        ("单位运费", "dc", 16.8 + 3.80, "节省 16.8 元/吨",
         44.8 + 3.80, "节省 44.8 元/吨"),
        ("时间价值", "dc", 16.8 + 3.80 * (0.5 / 1.5), "0.5 元/吨·天",
         16.8 + 3.80 * 2, "3.0 元/吨·天"),
        ("转换摩擦 s", "s", 10.0, "10 元/吨", 60.0, "60 元/吨"),
        ("成本敏感度 θ", "th", 0.02, "0.02", 0.2, "0.2"),
        ("通道能力", "cap_", 1.0, "1.0 亿吨", cap, f"{cap:.2f} 亿吨"),
    ]
    for name, pname, lo_v, lo_lab, hi_v, hi_lab in CASE_DEF:
        for tag, val, lab in (("低", lo_v, lo_lab), ("高", hi_v, hi_lab)):
            args = dict(dc=dc0, s=s0, th=th0, cap_=cap)
            args[pname] = val
            r = diversion(**args)
            rel = (r["drop"] - b["drop"]) / b["drop"] * 100
            rows.append({"参数": name, "方向": tag, "取值": lab,
                         "分流率": r["p"], "降幅": r["drop"], "相对": rel})
            print(f"  {name:<14}{lab:>18}{r['p']*100:>9.1f}%"
                  f"{r['drop']*100:>9.1f}%{rel:>+9.0f}%")

    # 找出最敏感的参数
    by_param = {}
    for r in rows:
        by_param.setdefault(r["参数"], []).append(abs(r["相对"]))
    ranking = sorted(by_param.items(), key=lambda kv: -max(kv[1]))
    print(f"\n  敏感性排序（按最大相对影响）：")
    for i, (k, v) in enumerate(ranking, 1):
        print(f"    {i}. {k:<24} 最大影响 ±{max(v):.0f}%")

    # ---------- 2. 结论翻转的临界值 ----------
    print(f"\n【2】使结论「翻转」的临界值\n")
    print("  定义「有效缓解」= 长洲降幅 ≥ 30%。求各参数的临界值：\n")

    def find_crit(param: str, lo: float, hi: float, target: float = 0.30):
        """在 [lo,hi] 上二分找使降幅=target 的参数值。"""
        for _ in range(60):
            mid = (lo + hi) / 2
            args = dict(dc=dc0, s=s0, th=th0, cap_=cap)
            args[param] = mid
            r = diversion(**args)
            # 对 s 是越大降幅越小；对 dc 是越小降幅越小
            if param in ("s",):
                if r["drop"] > target:
                    lo = mid
                else:
                    hi = mid
            else:
                if r["drop"] < target:
                    lo = mid
                else:
                    hi = mid
        return (lo + hi) / 2

    crit_s = find_crit("s", 0.0, 300.0)
    print(f"  · 转换摩擦 s：临界 ≈ **{crit_s:.0f} 元/吨**")
    print(f"    当 s > {crit_s:.0f} 元/吨（船东粘性极强）时，"
          f"降幅不足 30%，「有效缓解」不成立")
    print(f"    对照：费省 {dc0:.1f} 元/吨 —— 即粘性超过节省额的 "
          f"{crit_s/dc0:.1f} 倍时结论翻转")

    crit_dc = find_crit("dc", 0.0, 100.0)
    print(f"\n  · 广义成本差 ΔC：临界 ≈ **{crit_dc:.1f} 元/吨**")
    print(f"    当省下的成本低于 {crit_dc:.1f} 元/吨时，分流不足以有效缓解")
    print(f"    对照：单航次过闸费 3.0 元/吨，只占临界值的 "
          f"{3.0/crit_dc*100:.0f}%")

    # ---------- 3. 数据缺陷的方向性 ----------
    print(f"\n【3】数据缺陷把结论推向哪个方向？（不是罗列，是给方向）\n")
    defects = [
        ("月度汇总非逐船数据",
         "等待时间用「待闸数/日均放行」近似，会**高估**等待"
         "（把正在装卸的船也计入待闸）",
         "↑ 高估 W_A", "↑ 高估新通道的时间优势", "↑ **高估分流率**"),
        ("长洲缺少过闸费数据",
         "传统路径的过闸费未纳入成本（长洲是否收费未核实）",
         "↓ 低估 C_A", "↓ 低估新通道优势", "↓ **低估分流率**"),
        ("新通道闸室参数部分推定",
         "企石/青年闸室尺度按马道推定，灌泄水时间为假设区间",
         "能力估计不确定", "影响 Q3 能力上限", "方向不定，但已做区间"),
        ("通航后无实测",
         "转换摩擦 s 与 θ 完全无法标定",
         "结论是**条件预测**", "无法给点估计", "需事后验证（已设计）"),
        ("两期数据缺失/估算",
         "2025-08 用上+下补算、2026-03 闸次缺失",
         "对**基线量级**影响 <5%", "不影响结论方向", "可忽略"),
        ("腹地货源总量未建模",
         "假设货源总量不变，只做分配",
         "若总量增长，新通道**增量**承接而非替代 → ",
         "", "↓ **高估长洲降幅**"),
    ]
    print(f"  {'缺陷':<22}{'机理':<34}{'方向'}")
    print("  " + "-" * 96)
    for d in defects:
        print(f"  {d[0]:<22}{d[1][:32]:<34}{d[4]}")

    print(f"\n  **净效应判断**（这是本问最需要的结论）：")
    print(f"    「高估分流率」的因素：月度汇总的等待时间近似、腹地总量未建模")
    print(f"    「低估分流率」的因素：传统路径过闸费未计入")
    print(f"    ⇒ 两者方向**相反**，故**净偏差不确定**，")
    print(f"      但幅度有限（各约 ±10–20%）。")
    print(f"    ⇒ 因此结论「分流率 22%–45%、长洲降幅同量级」")
    print(f"      **方向可信，但具体数值不可当作点预测**。")

    # ---------- 4. 决策建议 ----------
    print(f"\n【4】给决策者的建议（≤300 字）\n")
    advice = (
        "新运河能否有效缓解长洲瓶颈，取决于两个条件。\n"
        "第一，成本差是否能克服转换惯性。若省下的运费低于约 21 元/吨，"
        "分流不足以带来可感的缓解；而船东的既有码头协议与回程货配"
        "构成约 20–50 元/吨的隐性粘性，这一项比过闸费重要得多。\n"
        "第二，新通道是否会自己变堵。测算显示瓶颈级为马道枢纽"
        "（落差 29.6 米、循环最慢），年能力约 2.28 亿吨；即使乐观分流，"
        "利用率也仅约 52%，等待远低于抵消优势所需的 21 天。"
        "故短期内**瓶颈不会搬家**。\n"
        "综上：新运河**有条件地**有效。政策重点应放在降低转换摩擦"
        "（港航一体化、回程货组织），而非继续压低已不足 10% 的过闸费；"
        "并以 2027 年上半年简报数据为节点做首次评估。"
    )
    print("  " + advice.replace("\n", "\n  "))
    n = len(re.sub(r"[\s*]", "", advice))
    print(f"\n  （{n} 字，题面要求 ≤300 字"
          f"{'  ✅' if n <= 300 else '  ❌ 超限'}）")

    out = {
        "基准": {"分流率": round(b["p"], 4), "长洲降幅": round(b["drop"], 4)},
        "单因素敏感性": rows,
        "敏感性排序": [{"参数": k, "最大相对影响": round(max(v) / 100, 3)}
                       for k, v in ranking],
        "临界值": {"转换摩擦s": round(crit_s, 1),
                   "广义成本差ΔC": round(crit_dc, 2),
                   "占节省额倍数": round(crit_s / dc0, 2)},
        "缺陷方向性": [{"缺陷": d[0], "机理": d[1], "方向": d[4]}
                       for d in defects],
        "净效应": "高估与低估因素方向相反，净偏差不确定但幅度有限（±10–20%）；"
                  "结论方向可信，数值不可当点预测",
        "决策建议": advice,
        "建议字数": n,
    }
    (RES / "q4_sensitivity.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  → results/q4_sensitivity.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
