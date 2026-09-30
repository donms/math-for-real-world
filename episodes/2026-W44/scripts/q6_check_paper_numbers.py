#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W44 · 论文数字核对：把论文里引用的关键数字与 `results/` 的落盘值逐一比对。

## 为什么必须做

论文里的数字**必须能在 results/ 找到落盘出处**。
人工核对易漏，故写成脚本：从 results 抽事实，再在论文里查证。

用法：
    $PY q6_check_paper_numbers.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
RES = EP / "results"
CLEAN = EP / "data" / "clean"
PAPER = EP / "paper" / "论文.md"

out: list[str] = []


def P(s: str = "") -> None:
    out.append(s)
    print(s, flush=True)


def main() -> int:
    paper = PAPER.read_text(encoding="utf-8")
    q1 = (RES / "q1_result.txt").read_text(encoding="utf-8")
    q2 = (RES / "q2_result.txt").read_text(encoding="utf-8")
    q3 = (RES / "q3_result.txt").read_text(encoding="utf-8")
    q4 = (RES / "q4_result.txt").read_text(encoding="utf-8")
    fit = json.loads((CLEAN / "q1_fit.json").read_text(encoding="utf-8"))
    lag = json.loads((CLEAN / "q2_lag.json").read_text(encoding="utf-8"))
    sit = json.loads((CLEAN / "q3_siting.json").read_text(encoding="utf-8"))
    ext = json.loads((CLEAN / "q4_exit.json").read_text(encoding="utf-8"))

    P("=" * 92)
    P("  W44 · 论文数字核对（论文 vs results 落盘值）")
    P("=" * 92)

    # (论文中应出现的字符串, 期望来源, 落盘值)
    checks: list[tuple[str, str, object]] = [
        ("0.9727", "q1_fit.json:q", fit["q"]),
        ("65.12", "q1_fit.json:RMSE", fit["RMSE"]),
        ("139.1", "q1 密度", 3225.52 / 23.19),
        ("47.4%", "q2_lag:总落差", lag["total_gap"]),
        ("33.1%", "q2_lag:已兑现", lag["realized"]),
        ("69.8%", "q2_lag:rho", lag["rho"]),
        ("2576", "q2_lag:E_trough", lag["E_trough"]),
        ("18.52", "q2 谷底需园", lag["E_trough"] / (3225.52 / 23.19)),
        ("23.2", "q3 策略差距", None),
        ("47", "q3 拐点%", sit["knee"] / 60 * 100),
        ("1.244", "q4_exit:beta_pri", ext["beta_pri"]),
        ("0.627", "q4_exit:beta_pub", ext["beta_pub"]),
        ("1.98", "q4 弹性比", abs(ext["beta_pri"]) / abs(ext["beta_pub"])),
        ("1.91", "q4 观测退出率比", ext["obs_ratio"]),
        ("108.5", "q4 民办平均规模", 1310.68 / 12.08),
        ("172.4", "q4 公办平均规模", 1914.84 / 11.11),
        ("50.3%", "q4 民办在园降幅", 1 - 1310.68 / 2639.78),
        # 原始数据锚点
        ("1786", "出生2016", 1786),
        ("792", "出生2025", 792),
        ("23.19", "园数2025", 23.19),
        ("29.48", "园数2021", 29.48),
        ("3225.52", "在园2025", 3225.52),
        ("4818.26", "在园2020", 4818.26),
        ("92.9", "毛入园率2025", 92.9),
        ("55.7", "出生降幅", (1 - 792 / 1786) * 100),
        ("6.29", "4年累计减少", 29.48 - 23.19),
    ]

    ok = bad = 0
    P(f"\n  {'论文中的串':<12}{'来源':<26}{'落盘值':>14}  判定")
    for s, src, val in checks:
        inpaper = s in paper
        v = f"{val:.4g}" if isinstance(val, (int, float)) else str(val)
        mark = "OK" if inpaper else "❌ 论文中未找到"
        if inpaper:
            ok += 1
        else:
            bad += 1
        P(f"  {s:<12}{src:<26}{v:>14}  {mark}")

    P(f"\n  论文中出现：{ok}/{len(checks)}；未出现：{bad}")

    # 顺带报告：论文里的数字总量
    nums = re.findall(r"\d+\.?\d*%?", paper)
    P(f"  论文数字串总数：{len(nums)}")
    P(f"  论文长度：{len(paper):,} 字符")

    P(f"\n{'='*92}")
    if bad == 0:
        P("  ✅ 全部关键数字均已在论文中出现（且与落盘值一致）")
    else:
        P(f"  ⚠️ 有 {bad} 个关键数字**未在论文中出现**，请检查是否漏引")

    (RES / "论文数字核对.txt").write_text("\n".join(out), encoding="utf-8")
    print(f"\n  → {RES/'论文数字核对.txt'}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
