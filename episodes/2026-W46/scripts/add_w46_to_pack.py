#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""把 W46 登记进 `make_github_pack.py` 的 `BLURBS` 与 `ENTRIES`。

## 为什么需要

`TITLES` / `BLURBS` / `ENTRIES` 三者分工不同：

| 常量 | 作用 | W46 现状 |
|---|---|---|
| `TITLES` | 频道 README 的期次表标题 | 已有 |
| `BLURBS` | 每期的 `what` / `find` / `tools`（README 简介）| **缺** |
| `ENTRIES` | **复现入口**（读者 clone 后第一个该跑的脚本）| **缺** |

缺 `BLURBS` ⇒ 频道 README 里该期没有简介；
缺 `ENTRIES` ⇒ 期 README 的复现入口会**用 glob 取"第一个"**，
可能取到校验脚本（W40 就取到过 `check_sub_width.py`，读者照抄跑不起来）。

## W46 的复现入口为什么选 `scripts/q1_model.py`

它是**建模型**那一步：自己就能跑通（实测守恒漂移 3.00e-15），
并产出 `results/figs/q1_正演.png`。
后续链条是 `q1_fit.py` → `q2_changepoint.py` → `q3_rt_filter.py`
→ `q4_scenario.py` → `q5_backtest.py`。

用法：
    $PY add_w46_to_pack.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET = ROOT / "scripts" / "make_github_pack.py"

BLURB = '''    "2026-W46": {
        "what": "2026 年 9 月 26 日，中国疾控中心第 38 周周报报告流感暴发疫情"
                "**47 起**，而三周前只有 **7 起**；同一份周报里 A(H3N2) 占甲型"
                "**94.2%**，七周前的结论还是「以 B 型为主」。"
                "「起爆」和「换人」同时发生，很自然会问：是不是病毒变强了？",
        "find": "**把「你看到的增长率」和「病毒真正的传播力」拆开，答案与直觉相反。**"
                "观测增长率在第 29 周就显著转正，而粒子滤波估出的 $R_t$ 直到"
                "第 36 周才越过 1 —— 因为流感季节性极强（峰在第 52 周、"
                "谷在第 31 周，峰谷比 **4.5 倍**），季节上升期即使 $R_t<1$ "
                "病例数照样涨。文中用**变点检测**定出起爆带（众数第 29 周、"
                "95% 区间第 24-33 周），再用 **3000 粒子滤波**在线估 $R_t$，"
                "两法互验相关系数 **0.903**。另有一个必须避开的坑："
                "2020-2022 是**新冠期的观测口径断点** —— 不处理会凭空造出"
                "**+48%** 的传播力假尖峰。发布前又补做了**事后验证**："
                "第 38 周峰值之后，第 39/40 周回落到 **20 起 / 10 起**"
                "（相对峰值 -79%），H3N2 占甲型也从 94.2% 降到 **86.9%** "
                "（H1N1 升到 13.1%）⇒ 与「季节在推」一致、与「病毒变强」不一致；"
                "但**不等于模型预测成功**（模型只给定性判断，未给 9-10 月数值预测）。",
        "tools": "结构变点检测（块自助区间）· 粒子滤波状态空间模型 · "
                 "季节性分解 · 双亚型竞争动力学（12 维严格守恒）· "
                 "剖面似然与可辨识性 · 蒙特卡洛情景分析 · "
                 "发布前事后验证（流感季口径）",
    },
'''

ENTRY = ('    "2026-W46": "scripts/q1_model.py",\n')


def main() -> int:
    s = TARGET.read_text(encoding="utf-8")

    # ① BLURBS：插在 W48 之前（保持期次顺序）
    if '"2026-W46": {' in s:
        print("  [跳过] BLURBS 已有 W46")
    else:
        anchor = '    "2026-W48": {'
        if anchor not in s:
            print("  [X] 找不到 BLURBS 锚点")
            return 1
        s = s.replace(anchor, BLURB + anchor, 1)
        print("  BLURBS 已加 W46")

    # ② ENTRIES：插在 W48 之前
    if '"2026-W46": "scripts/' in s:
        print("  [跳过] ENTRIES 已有 W46")
    else:
        anchor = '    "2026-W48": "scripts/tissue_optics.py",\n'
        if anchor not in s:
            print("  [X] 找不到 ENTRIES 锚点")
            return 1
        s = s.replace(anchor, ENTRY + anchor, 1)
        print("  ENTRIES 已加 W46")

    TARGET.write_text(s, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
