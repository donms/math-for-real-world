#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第 ④ 步收尾：把 clean/ 下的长表整理成建模用的宽表。

处理内容
--------
1. **统一指标命名**（PPI 的"其它/其他"混用）
2. **标记基期断点**：2026-01 起基期轮换，`regime` 列区分 pre/post
3. **输出宽表**：`cpi_wide.csv`（行=期间，列=指标，值=同比），供 qN_solve.py 直接读
4. **标注口径一致的子样本**：2026-02 起（用户决策：Q2 只用该子样本）

用法
----
    $env:PYTHONUTF8=1
    $PY = "python"
    $PY episodes\\2026-W38\\scripts\\clean_data.py
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

EP = Path(__file__).resolve().parent.parent
CLEAN = EP / "data" / "clean"
BASE_BREAK = "2026-01"          # 基期轮换生效月
CONSISTENT_FROM = "2026-02"     # 口径一致的子样本起点（用户决策）

# 命名归一（PPI 官方发布稿在不同月份用字不一致，实测）
RENAME = {
    "其它工业原材料及半成品类": "其他工业原材料及半成品类",
}

# 只保留用于建模/分析的指标（去掉过渡性汇总行，避免重复计数）
DROP = {"按类别分", "其中", ""}


def load(name: str) -> list[dict]:
    p = CLEAN / name
    if not p.exists():
        print(f"[!] 缺少 {p}")
        return []
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm_item(x: str) -> str:
    x = re.sub(r"\s+", "", x or "")
    x = re.sub(r"^其中[:：]", "", x)
    x = re.sub(r"^其中", "", x)
    return RENAME.get(x, x)


def to_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def make_wide(rows: list[dict], out_name: str) -> tuple[list[str], list[str]]:
    """长表 → 宽表（同比）。同时输出环比宽表。"""
    items, months = set(), set()
    d_yoy: dict[tuple, float] = {}
    d_mom: dict[tuple, float] = {}
    for r in rows:
        it = norm_item(r["item"])
        if it in DROP:
            continue
        per = r["period"]
        items.add(it)
        months.add(per)
        y, m = to_float(r.get("yoy")), to_float(r.get("mom"))
        if y is not None:
            d_yoy[(per, it)] = y
        if m is not None:
            d_mom[(per, it)] = m

    months = sorted(months)
    # 大类优先、细项随后，便于阅读
    def order(it: str) -> tuple:
        m = re.match(r"^([一二三四五六七八])、", it)
        return (0, m.group(1), it) if m else (1, it, it)

    items = sorted(items, key=order)

    for vals, suffix in ((d_yoy, "yoy"), (d_mom, "mom")):
        p = CLEAN / out_name.replace(".csv", f"_{suffix}.csv")
        with p.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["period", "regime"] + items)
            for per in months:
                regime = "pre_base_rotation" if per < BASE_BREAK else "post_base_rotation"
                w.writerow([per, regime] +
                           ["" if vals.get((per, it)) is None else vals[(per, it)]
                            for it in items])
        print(f"[wide] {p.name}  {len(months)} 行 × {len(items)} 列")
    return months, items


def main() -> int:
    print("=" * 66)
    print("第④步 收尾：清洗与宽表生成")
    print("=" * 66)

    cpi = load("cpi_monthly.csv")
    ppi = load("ppi_monthly.csv")
    if not cpi:
        return 2

    print(f"\n输入：CPI {len(cpi)} 行，PPI {len(ppi)} 行")

    # 命名归一检查
    fixed = 0
    for rows in (cpi, ppi):
        for r in rows:
            old = r["item"]
            new = norm_item(old)
            if new != old:
                r["item"] = new
                fixed += 1
    print(f"命名归一：{fixed} 行（其它/其他 等）")

    print()
    m1, i1 = make_wide(cpi, "cpi_wide.csv")
    if ppi:
        m2, i2 = make_wide(ppi, "ppi_wide.csv")

    # 输出口径说明
    info = CLEAN / "README_口径说明.md"
    info.write_text(f"""# 清洗后数据说明

| 文件 | 内容 |
|---|---|
| `cpi_monthly.csv` | CPI 长表（period, item, mom, yoy, ytd） |
| `ppi_monthly.csv` | PPI 长表 |
| `cpi_wide_yoy.csv` | CPI 同比宽表（行=期间，列=指标）← **建模主用** |
| `cpi_wide_mom.csv` | CPI 环比宽表 |
| `ppi_wide_yoy.csv` | PPI 同比宽表 |
| `ppi_wide_mom.csv` | PPI 环比宽表 |

## 口径要点

1. **基期轮换**：`{BASE_BREAK}` 起 CPI 基期由 2020 年改为 2025 年，调查分类目录、
   代表规格品、调查网点与分类权数均调整。宽表中的 `regime` 列标记
   `pre_base_rotation` / `post_base_rotation`。
2. **口径一致的子样本**：`{CONSISTENT_FROM}` 起（**用户决策**，Q2 只用该子样本）。
3. **1 月缺累计值**：1 月发布稿不含"1—N月累计"列，故 `ytd` 为 NaN（非数据缺失）。
4. **命名归一**：PPI 的"其它工业原材料及半成品类"统一为"其他工业原材料及半成品类"。
5. **部分指标仅近期有值**：基期轮换后新增/调整的分类（如"一、食品烟酒及在外餐饮"、
   "小汽车"、"交通工具用能源"），老月份无对应行。

覆盖期间：{m1[0]} … {m1[-1]}（{len(m1)} 个月）
""", encoding="utf-8")
    print(f"[doc ] {info.name}")

    # 子样本检查
    sub = [m for m in m1 if m >= CONSISTENT_FROM]
    print(f"\n口径一致子样本（>={CONSISTENT_FROM}）：{len(sub)} 个月 -> {sub}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
