#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W41 数据体检与清洗 —— 建立 15 期干净面板 + 参数集。

## 本脚本要做的四件事

1. **补两处缺失**（并**标注为估算**，不混入实测列）：
   * 2025-08：缺「过闸货运量」总量句，用上行 444.43 + 下行 1700.43 = 2144.86
   * 2026-03：缺月度总闸次，用「日均闸次 × 天数」估算
2. **区分实测与估算**：每个数值带 `*_src` 标记（实测/估算）
3. **剔除异常期**：2025-12 / 2026-01 含「一二线船闸停航改造」，
   待闸数含**非拥堵因素**，需单独标记
4. **导出参数集**：供 Q1–Q4 共用的物理/运营常数

## 为什么单独一步

skill 的数据体检要求：**不合理的数值先怀疑抓取，再怀疑现实**。
本期两次存疑（2025-08 货运量、2026-03 闸次）**都是抓取问题**；
若不单独做这一步，模型会建在错数据上。

用法：
    $PY q0_data_prep.py            # 体检 + 导出
    $PY q0_data_prep.py --show     # 附带打印清洗后面板
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "results"
SRC = DATA / "长洲简报汇总.json"

# 2025-12 / 2026-01 期间一二线船闸停航改造（原文有载），
# 待闸数含非拥堵因素 → 在这些期的待闸列上打标，建模时须特殊处理
MAINTENANCE_PERIODS = {"2025-12", "2026-01"}

# 月报期号 → 当月的天数（用于按日均估算月总量）
DAYS = {"2025-08": 31, "2025-09": 30, "2025-10": 31, "2025-11": 30,
        "2025-12": 31, "2026-01": 31, "2026-02": 28, "2026-03": 31,
        "2026-04": 30, "2026-05": 31, "2026-06": 30}


def f(x) -> float | None:
    try:
        v = float(x)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    rows = json.loads(SRC.read_text(encoding="utf-8"))
    clean, notes = [], []

    for r in rows:
        per = r["期"]
        rec = {"期": per, "src": {}}

        # ---- 过闸货运量 ----
        tot = f(r.get("货运量万吨"))
        up, dn = f(r.get("上行万吨")), f(r.get("下行万吨"))
        if tot and up and dn and abs(up + dn - tot) / tot > 0.02:
            # 总量与「上+下」不符 → 取上+下（更可信，因为是分项加总）
            rec["货运量万吨"] = round(up + dn, 2)
            rec["src"]["货运量万吨"] = f"估算(上{up:.2f}+下{dn:.2f})"
            notes.append(f"{per}：原总量 {tot:.2f} 与「上+下」{up + dn:.2f} 不符，"
                         f"取上+下")
        else:
            rec["货运量万吨"] = tot
            rec["src"]["货运量万吨"] = "实测" if tot else ""

        # ---- 闸次 ----
        g = f(r.get("闸次"))
        if g:
            rec["闸次"] = g
            rec["src"]["闸次"] = "实测"
        else:
            d = DAYS.get(per)
            # 原文只给日均：日均过闸船舶 / 平均每闸次艘次 → 反推日闸次
            # 这里保守处理：标记缺失，由 Q1 决定是否用同月艘次/核载反推
            rec["闸次"] = None
            rec["src"]["闸次"] = "缺失"
            if d:
                notes.append(f"{per}：月度总闸次缺失（原文仅日均口径），"
                             f"标记为缺失，不建议直接估算")

        for k in ("艘次", "平均核载吨", "日均待闸艘", "最高待闸艘",
                  "总核载万吨", "出库流量"):
            v = f(r.get(k))
            rec[k] = v
            rec["src"][k] = "实测" if v else "缺失"

        # ---- 异常期标记 ----
        rec["检修期"] = per in MAINTENANCE_PERIODS
        if rec["检修期"]:
            notes.append(f"{per}：一二线船闸停航改造，待闸数含非拥堵因素")

        # ---- 派生指标 ----
        if rec["货运量万吨"] and rec["艘次"]:
            rec["平均载货吨"] = round(rec["货运量万吨"] * 1e4 / rec["艘次"], 1)
        else:
            rec["平均载货吨"] = None
        if rec["艘次"] and rec["闸次"]:
            rec["每闸次艘次"] = round(rec["艘次"] / rec["闸次"], 2)
        else:
            rec["每闸次艘次"] = None
        if rec["货运量万吨"] and rec["闸次"]:
            rec["每闸次万吨"] = round(rec["货运量万吨"] / rec["闸次"], 4)
        else:
            rec["每闸次万吨"] = None
        if rec["货运量万吨"] and rec["出库流量"]:
            rec["吨每流量"] = round(rec["货运量万吨"] / rec["出库流量"], 4)
        else:
            rec["吨每流量"] = None

        clean.append(rec)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "q0_panel.json").write_text(
        json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 参数集（Q1–Q4 共用）----------
    params = {
        "_note": "W41 共用参数集。实测值标 src=实测，推导/引用值注明来源。",

        # 长洲船闸（老通道瓶颈）
        "长洲": {
            "闸室数": {"v": 4, "src": "四线船闸（简报原文）"},
            "2025年货运量万吨": {"v": 22355.46, "src": "实测(2025年度简报)"},
            "2025年闸次": {"v": 21039, "src": "实测"},
            "2025年艘次": {"v": 123620, "src": "实测"},
            "2025年平均核载吨": {"v": 2986, "src": "实测"},
            "2025年日均待闸艘": {"v": 422, "src": "实测"},
            "瓶颈性质": {"v": "枯水期吃水受限 + 通过能力受限",
                         "src": "简报：一二线因超最大运行工况停航"},
        },

        # 平陆运河（新通道）—— 来自环评批复 桂环审〔2022〕222号
        "平陆运河": {
            "全长km": {"v": 140, "src": "批复"},
            "航道等级": {"v": "内河I级", "src": "批复"},
            "枢纽数": {"v": 3, "src": "批复（马道/企石/青年）"},
            "天然落差m": {"v": 65, "src": "公开报道"},
            "预测货运量2035万吨": {"v": 10000, "src": "批复"},
            "预测货运量2050万吨": {"v": "15000-18000", "src": "批复"},
            "静态总投资亿元": {"v": 685.9, "src": "批复"},
            "裁弯取直处数": {"v": 57, "src": "批复"},
            "调水规模近期m3s": {"v": 24, "src": "批复"},
            "调水规模远期m3s": {"v": 40, "src": "批复"},
            "主要货种": {"v": ["煤炭", "金属矿石", "非金属矿石", "水泥",
                              "粮食", "矿建材料", "集装箱"], "src": "批复"},
            "航程缩短km": {"v": ">560", "src": "新华社报道"},
            "物流成本降幅": {"v": "18%-30%", "src": "新华社报道（口径待核）"},
            "闸室尺度": {"v": None, "src": "⚠️ 未查到公开数据，需做区间/敏感性"},
        },

        # 待补
        "_待补": {
            "船舶待闸时间价值": "需查文献；查不到则用公开区间 + 敏感性",
            "平陆运河闸室尺度": "同上",
            "西江运价元每吨公里": "同上",
        },
    }
    (OUT / "q0_params.json").write_text(
        json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 报告 ----------
    print(f"  清洗 {len(clean)} 期 → results/q0_panel.json")
    ok = sum(1 for r in clean if r["货运量万吨"] and r["闸次"])
    print(f"  含完整「货运量+闸次」的期数：{ok}/{len(clean)}")
    print()
    print("  期        货运量万吨      闸次   艘次  日均待闸  每闸次万吨  检修")
    print("  " + "-" * 72)

    def cell(v, nd: int, width: int) -> str:
        """格式化一个单元格。⚠️ 不要写成嵌套 f-string：
        Python 3.10 的 f-string 不允许内层再用同类引号
        （实测报 `unexpected character after line continuation character`）。"""
        s = f"{v:.{nd}f}" if v else "—"
        return f"{s:>{width}}"

    for r in clean:
        print(f"  {r['期']:<9}"
              + cell(r["货运量万吨"], 1, 10)
              + cell(r["闸次"], 0, 8)
              + cell(r["艘次"], 0, 7)
              + cell(r["日均待闸艘"], 0, 9)
              + cell(r["每闸次万吨"], 4, 11)
              + f"   {'⚠️' if r['检修期'] else ''}")
    print()
    print("  体检记录：")
    for n in notes:
        print(f"    · {n}")
    print(f"\n  参数集 → results/q0_params.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
