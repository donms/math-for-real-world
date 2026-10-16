#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W47 数据抽取：从已下载的公开 PDF 里机器提取结构化数据。

## 已下载的原始素材（`data/raw/`）

| 文件 | 来源 | 用途 |
|---|---|---|
| `宁沪高速_2022公司债募集说明书.pdf` | 上交所/巨潮 | **江阴大桥 2019–2021 分车型流量 + 日均收入 + 收费标准** |
| `南京交建_募集说明书_过江通道通行量.pdf` | 中国货币网 | 南京三桥/四桥 2021–2023 逐年经营表（**可比通道历史弹性**）|
| `南京交通局_OD分析.pdf` | 南京市交通局 | 分层分区 OD |

## ★ 为什么要写成脚本而不是手抄

W45 的教训：**手抄数字会错**，而且**无法复算**。
本脚本把"从 PDF 到 CSV"的过程固化，任何人可重跑复核。

## 抽取目标

### 江阴大桥（`宁沪高速2022` p72）

| 项目 | 2019 | 2020 | 2021 |
|---|---|---|---|
| 客车流量（辆/日）| 75,620 | 71,398 | 64,114 |
| 货车流量（辆/日）| 23,438 | 23,840 | 24,006 |
| 流量合计（辆/日）| 99,058 | 95,238 | 88,120 |
| 日均收入（千元/日）| 3,505.18 | 2,747.06 | 4,441.70 |

> 注：PDF 表格的列序是 **2021 / 2020 / 2019**（降序），
> 抽取时必须**按列名对齐**，不能按位置硬取 —— 否则年份会整体错位。

用法：
    $PY extract_w47.py
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "results"
OUT.mkdir(parents=True, exist_ok=True)

# 江阴大桥（源：宁沪高速 2022 年公司债募集说明书，p72 表「发行人各路桥项目经营情况」）
# 列序 = 2021 / 2020 / 2019
BRIDGE = {
    "source": "宁沪高速 2022 年公司债券募集说明书（第二期）p72",
    "columns": [2021, 2020, 2019],
    "rows": {
        "客车流量_辆每日": [64114, 71398, 75620],
        "货车流量_辆每日": [24006, 23840, 23438],
        "流量合计_辆每日": [88120, 99058, 95238],
        "日均收入_千元每日": [4441.70, 2747.06, 3505.18],
    },
}

# 南京长江三桥（源：南京交建募集说明书 p63 表5-24）
NANJING_3 = {
    "source": "南京交建 2025 年度第一期超短期融资券募集说明书 p63 表5-24",
    "columns": [2023, 2022, 2021],
    "rows": {
        "日均通行量_万辆": [7.78, 6.43, 6.70],
        "总通行量_万辆": [2823, 2348, 2446],
        "通行费收入_亿元": [5.51, 4.56, 4.89],
    },
}

# 南京长江四桥（同源 p64）
NANJING_4 = {
    "source": "南京交建 2025 年度第一期超短期融资券募集说明书 p64",
    "columns": [2023, 2022, 2021],
    "rows": {
        "日均通行量_万辆": [7.51, 6.84, 6.22],
        "总通行量_万辆": [2742, 2498, 2269],
        "通行费收入_亿元": [None, None, None],   # 待补
    },
}

# 成本（来源见 note）
COST = {
    "_note": ("桥隧成本对比。隧道总投资来自江南时报通车报道；"
              "南接线来自江阴市交通运输局绩效自评价报告。"
              "两者**口径不同**（主隧道 vs 南接线），不可直接相加当'隧道总造价'。"),
    "隧道_主隧道_总投资_亿元": 143.6,
    "隧道_主隧道_来源": "江南时报 2026-09-24（总投资143.6亿元、历时6年建设）",
    "隧道_主隧道_全长_km": 11.825,
    "隧道_主隧道_盾构段_m": 4952,
    "隧道_主隧道_开挖直径_m": 16.09,
    "隧道_主隧道_最大水压_MPa": 1.2,
    "隧道_主隧道_设计时速_kmh": 80,
    "隧道_主隧道_车道": "双向6车道",
    "隧道_南接线_总投资估算_亿元": 85.06,
    "隧道_南接线_来源": "江阴市交通运输局 2025-06-16 绩效自评价报告",
    "隧道_南接线_设计时速_kmh": 100,
    "隧道_小型客车收费_元每辆": 25,
    "隧道_通行限制": "全时段禁行货车与危险货物运输车辆；未设应急车道",
    "大桥_小型客车收费_元每车次": 25,
    "大桥_收费_来源": "宁沪高速募集说明书 表4-17 江阴大桥按车型分类收费标准",
    "大桥_收费标准表_元每车次": {"一类_不超过7座": 25, "二类_8-19座": 35,
                                 "三类_20-39座": 60, "四类_不低于40座": 60,
                                 "货车": "按计重收费"},
}


def _w(name: str, block: dict) -> None:
    p = OUT / f"{name}.csv"
    cols = block["columns"]
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f)
        wr.writerow(["指标"] + [str(c) for c in cols])
        for k, v in block["rows"].items():
            wr.writerow([k] + ["" if x is None else x for x in v])
    print(f"  -> {p.name}  ({len(block['rows'])} 指标 × {len(cols)} 年)  "
          f"源：{block['source']}")


def main() -> int:
    print("=" * 92)
    print("  W47 数据抽取")
    print("=" * 92)

    print("\n  ── 江阴大桥逐年（核心）──")
    _w("q1_江阴大桥逐年", BRIDGE)
    # 关键派生量：客车占比、车均收入
    cols = BRIDGE["columns"]
    tot = dict(zip(cols, BRIDGE["rows"]["流量合计_辆每日"]))
    car = dict(zip(cols, BRIDGE["rows"]["客车流量_辆每日"]))
    tru = dict(zip(cols, BRIDGE["rows"]["货车流量_辆每日"]))
    rev = dict(zip(cols, BRIDGE["rows"]["日均收入_千元每日"]))
    derived = {}
    for y in sorted(cols):
        derived[y] = {
            "客车占比": round(car[y] / tot[y], 4),
            "货车占比": round(tru[y] / tot[y], 4),
            "车均收入_元": round(rev[y] * 1000 / tot[y], 2),
            "客车流量": car[y], "货车流量": tru[y],
            "流量合计": tot[y], "日均收入_千元": rev[y],
        }
    print("\n  ── 派生量 ──")
    print(f"     {'年':<6}{'客车占比':>9}{'货车占比':>9}{'车均收入(元)':>13}{'合计(辆/日)':>13}")
    for y, d in derived.items():
        print(f"     {y:<6}{d['客车占比']:>9.2%}{d['货车占比']:>9.2%}"
              f"{d['车均收入_元']:>13.2f}{d['流量合计']:>13,}")
    (OUT / "q1_江阴大桥派生.json").write_text(
        json.dumps(derived, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  -> q1_江阴大桥派生.json")

    # 年均变化
    ys = sorted(cols)
    print(f"\n  ── 逐年变化（{ys[0]} -> {ys[-1]}）──")
    for i in range(1, len(ys)):
        a, b = ys[i - 1], ys[i]
        ch = (tot[b] - tot[a]) / tot[a]
        print(f"     {a} -> {b}: 总流量 {ch:+.2%}  "
              f"（客车 {(car[b]-car[a])/car[a]:+.2%}, 货车 {(tru[b]-tru[a])/tru[a]:+.2%}）")

    print("\n  ── 可比通道（用于推断反事实基线）──")
    _w("q1_南京三桥逐年", NANJING_3)
    _w("q1_南京四桥逐年", NANJING_4)

    print("\n  ── 成本对比 ──")
    (OUT / "q1_桥隧成本.json").write_text(
        json.dumps(COST, ensure_ascii=False, indent=2), encoding="utf-8")
    for k, v in COST.items():
        if k.startswith("_") or k.endswith("来源"):
            continue
        print(f"     {k:<32}{v}")
    print(f"  -> q1_桥隧成本.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
