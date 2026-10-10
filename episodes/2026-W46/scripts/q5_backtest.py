#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W46 · 发布前补做：**事后验证**（原稿引用的峰值之后，数据怎么走的）。

## 起因（用户提出）

> 「"流感三周从 7 起涨到 47 起"，加了两周的数据，有体现吗？」

**核对结果**：原稿引用的是**中国 CDC 周报的"暴发疫情起数"**，
而我更新的两周是**美国 Delphi 序列** —— **两个不同数据源**，
所以新增的美国数据**不影响** 7→47 这个锚点。

**但用户的问题指向了真问题**：中国周报**确实又出了两期**，
而原稿没体现。实测：

| 官方周 | 期号 | 暴发疫情 | A 型占比 | H3N2 占甲型 |
|---|---|---|---|---|
| 36 | 925 | 7 | 67.1% | 95.9% |
| 37 | 926 | 34 | 69.9% | 94.5% |
| **38** | **927** | **47** | 64.1% | **94.2%** ⟵ 原稿引用点 |
| **39** | **928** | **20** | 61.9% | **90.6%** |
| **40** | **929** | **10** | 63.2% | **86.9%** |

## 本脚本回答三个问题

| # | 问题 |
|---|---|
| **Q1** | 峰值（47 起）之后，序列怎么走的？ |
| **Q2** | "换人"（H3N2 占甲型上升）有没有继续？ |
| **Q3** | 这些新观察**与 W46 的核心论点一致，还是冲突**？ |

## 判读原则（**必须遵守**）

* **不声称"模型预测成功"** —— 原模型没有给出 9–10 月的**数值**预测，
  只给出了"**起爆 ≠ 病毒变强，季节在推**"这个定性判断；
* 因此只能说：**新数据与"季节解释"一致，而与"病毒变强"的解释不一致**
  —— 因为**病毒不会在两三周内自己回落 79%**；
* 报告**点位与区间**，不做因果断言。

## 落盘 `results/q5_事后验证.json`

用法：
    $PY q5_backtest.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W46"
RES = EP / "results"
FU = EP / "data" / "clean" / "flu_weekly.csv"


def main() -> int:
    print("=" * 94)
    print("  W46 · 事后验证（峰值之后的新观察）")
    print("=" * 94)

    rows = [r for r in csv.DictReader(FU.open(encoding="utf-8"))
            if r.get("outbreak") or r.get("h3n2")]
    print(f"\n  中国周报 {len(rows)} 期")

    # 只取有暴发数的期（构成主序列）
    ob = [(r["date"], int(r["week"]), int(r["outbreak"]))
          for r in rows if r.get("outbreak")]
    ob.sort(key=lambda x: x[1])
    print(f"\n  ── Q1：暴发疫情序列（{len(ob)} 期有数）──")
    print(f"     {'日期':<10}{'周':>4}{'起数':>6}   条形")
    for d, w, v in ob:
        print(f"     {d:<10}{w:>4}{v:>6}   {'#' * v}")

    peak = max(ob, key=lambda x: x[2])
    last = ob[-1]
    print(f"\n     峰值：第 {peak[1]} 周 **{peak[2]} 起**")
    print(f"     最新：第 {last[1]} 周 **{last[2]} 起**")
    drop = (last[2] - peak[2]) / peak[2] * 100
    print(f"     相对峰值：**{drop:+.1f}%**")

    # 峰值之后的窗口
    after = [x for x in ob if x[1] > peak[1]]
    print(f"\n     峰值之后的 {len(after)} 期："
          f"{[x[2] for x in after]}")

    # ── Q2：换人是否继续 ──
    print(f"\n  ── Q2：『换人』（H3N2 占甲型）是否继续 ──")
    print(f"     {'周':>4}{'A%':>7}{'B%':>7}{'H3N2%':>8}{'H1N1%':>8}")
    h3 = []
    for r in sorted(rows, key=lambda x: int(x["week"])):
        if not r.get("h3n2"):
            continue
        try:
            w = int(r["week"]); a = float(r["a_pct"]) if r.get("a_pct") else None
            b = float(r["b_pct"]) if r.get("b_pct") else None
            h = float(r["h3n2"]); n1 = float(r["h1n1"]) if r.get("h1n1") else None
        except ValueError:
            continue
        h3.append((w, a, b, h, n1))
        print(f"     {w:>4}{(a if a is not None else float('nan')):>7.1f}"
              f"{(b if b is not None else float('nan')):>7.1f}"
              f"{h:>8.1f}"
              f"{(n1 if n1 is not None else float('nan')):>8.1f}")
    # 峰值周 vs 最新周
    pw = peak[1]
    h_at_peak = next((x for x in h3 if x[0] == pw), None)
    h_last = h3[-1] if h3 else None
    if h_at_peak and h_last:
        print(f"\n     H3N2 占甲型：第 {h_at_peak[0]} 周 **{h_at_peak[3]:.1f}%**"
              f" -> 第 {h_last[0]} 周 **{h_last[3]:.1f}%**"
              f"（**{h_last[3]-h_at_peak[3]:+.1f} 个百分点**）")
        if h_at_peak[4] is not None and h_last[4] is not None:
            print(f"     H1N1 占甲型：{h_at_peak[4]:.1f}% -> {h_last[4]:.1f}%"
                  f"（**{h_last[4]-h_at_peak[4]:+.1f} pp**）")
        print(f"     ⇒ 『换人』**{'正在反向' if h_last[3] < h_at_peak[3] else '仍在继续'}**")

    # ── Q3：与核心论点的一致性 ──
    print(f"\n  ── Q3：与 W46 核心论点的一致性 ──")
    print(f"     W46 的定性判断：『起爆 ≠ 病毒变强，是季节在推』")
    print(f"     季节解释预期：秋季起爆后**会在 10 月回落**"
          f"（流感季峰在第 52 周，不是 9 月）")
    print(f"     实测：峰值后 {' -> '.join(str(x[2]) for x in [peak] + after)}"
          f"（**{drop:+.1f}%**）")
    ok = drop < -30
    print(f"\n     ⇒ 新观察与『季节解释』"
          f"{'**一致**' if ok else '**需要重新审视**'}；")
    print(f"       与『病毒变强』的解释**不一致** ——"
          f"病毒不会在两三周内自己回落 {abs(drop):.0f}%。")
    print(f"\n     [!] **不等于『模型预测成功』**：原模型没有给 9–10 月的"
          f"数值预测，只给了定性判断。")

    out = {
        "中国周报期数": len(rows),
        "暴发序列": [{"date": d, "week": w, "outbreak": v} for d, w, v in ob],
        "峰值": {"week": peak[1], "outbreak": peak[2]},
        "最新": {"week": last[1], "outbreak": last[2]},
        "相对峰值pct": round(drop, 1),
        "峰值之后": [{"week": x[1], "outbreak": x[2]} for x in after],
        "H3N2序列": [{"week": w, "a_pct": a, "b_pct": b, "h3n2": h, "h1n1": n1}
                     for w, a, b, h, n1 in h3],
        "换人是否反向": bool(h_at_peak and h_last and h_last[3] < h_at_peak[3]),
        "_口径": {
            "数据源": "中国 CDC 流感监测周报（第 925–929 期）",
            "周号": "**按报告自身标注的周号**（栏目页发布日期可能把两期挂同一天）",
            "指标": "全国共报告流感样病例暴发疫情起数",
        },
        "_判读纪律": [
            "不声称『模型预测成功』——原模型未给 9–10 月数值预测",
            "只能说：新数据与『季节解释』一致，与『病毒变强』不一致",
            "暴发疫情数受报告与聚集性判定影响，不是感染率",
        ],
    }
    p = RES / "q5_事后验证.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
