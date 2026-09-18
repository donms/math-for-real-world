#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W39 · Q1：三类悬架的控制权限刻画（不含数值求解，只做结构性区分）。

本脚本产出 Q1 的核心表：各架构的**可控量集合**与**约束集**，
以及频域上的**可实现区间**（传递率曲线族）。

与 Q2/Q3 的分工：
* Q1 回答"**允许做什么**"（结构问题，不依赖参数取值）
* Q2 回答"**能做到多好**"（性能上界，依赖参数）
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from model import (ARCHS, arch_spec, default_params, freqresp,  # noqa: E402
                   natural_freqs, road_psd_accel)

RESULTS = ROOT / "results"
FIGS = RESULTS / "figs"
RESULTS.mkdir(parents=True, exist_ok=True)
FIGS.mkdir(parents=True, exist_ok=True)

# 各架构的控制权限：结构性描述（**不依赖具体参数取值**）
AUTHORITY = [
    {
        "架构": "被动",
        "执行机构": "定阻尼减振器 + 螺旋弹簧",
        "可控物理量": "无",
        "约束集": "—",
        "能否注入能量": "否",
        "数学本质": "常数参数，无可控自由度",
        "新增自由度": "（基准）",
    },
    {
        "架构": "云辇-C",
        "执行机构": "电磁阀可调阻尼（CDC）",
        "可控物理量": "阻尼 c(t)",
        "约束集": "c ∈ [c_min, c_max]，且 F·Δż ≥ 0（只耗散）",
        "能否注入能量": "否",
        "数学本质": "半主动：耗散特性可调",
        "新增自由度": "阻尼可在线改变（1 维）",
    },
    {
        "架构": "云辇-A",
        "执行机构": "空气弹簧 + CDC",
        "可控物理量": "阻尼 c(t) + 刚度 k(t) + 车身高度",
        "约束集": "c 同 C；刚度/高度为**慢自由度**（升降速率约 10 mm/s，"
                  "等效带宽 0.1–0.2 Hz）",
        "能否注入能量": "**是**（高度通道做功，但带宽极低）",
        "数学本质": "半主动阻尼 + **带速率限幅的慢变主动通道**",
        "新增自由度": "阻尼 + 刚度 + 平衡位置（慢）",
    },
    {
        "架构": "云辇-M",
        "执行机构": "磁流变阻尼（MR）",
        "可控物理量": "阻尼 c(t)",
        "约束集": "同 C（耗散型），但**力域与带宽更大**",
        "能否注入能量": "否",
        "数学本质": "半主动（高带宽高力域版）",
        "新增自由度": "与 C **同一权限层级**，仅执行器指标不同",
    },
    {
        "架构": "云辇-X",
        "执行机构": "全主动作动器",
        "可控物理量": "主动力 F(t)（任意）",
        "约束集": "仅受力上限与带宽限制，**可注入能量**",
        "能否注入能量": "**是**",
        "数学本质": "全主动：无源性约束被解除",
        "新增自由度": "主动力（2 维：幅值+方向）",
    },
]


def transmissibility(p: dict, c, f: np.ndarray, which: int = 0) -> np.ndarray:
    """传递率 = |输出/路面加速度输入|，用于画频域可实现区间。"""
    H = freqresp(p, c, f)
    return np.abs(H[which, :])


def main() -> int:
    p = default_params()
    fb, fw = natural_freqs(p)
    print(f"固有频率 车身 {fb:.2f} Hz / 车轮 {fw:.1f} Hz\n")

    # ---------- Q1 表 ----------
    out_csv = RESULTS / "q1_authority.csv"
    with out_csv.open("w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(AUTHORITY[0].keys()))
        w.writeheader()
        w.writerows(AUTHORITY)
    print(f"[表] {out_csv}")
    for r in AUTHORITY:
        print(f"  {r['架构']:<8} 可控={r['可控物理量']:<28} 注入能量={r['能否注入能量']}")

    # ---------- 频域可实现区间 ----------
    f = np.logspace(np.log10(0.1), np.log10(30), 400)
    cs = np.geomspace(p["c_min"], p["c_max"], 25)
    curves = {float(c): transmissibility(p, c, f).tolist() for c in cs}

    # 记录关键频点的可实现区间宽度（体现"控制权限带来的自由度"）
    key_f = [0.5, 1.0, fb, 2.0, 5.0, fw, 15.0]
    band = []
    for fk in key_f:
        i = int(np.argmin(np.abs(f - fk)))
        vals = [curves[float(c)][i] for c in cs]
        band.append({"f_Hz": float(f[i]), "min": float(min(vals)),
                     "max": float(max(vals)),
                     "ratio_max_min": float(max(vals) / max(min(vals), 1e-12))})
    print("\n[频域可实现区间]（阻尼可调带来的传递率变化幅度）")
    print(f"  {'频率(Hz)':>9}{'最小':>10}{'最大':>10}{'最大/最小':>11}")
    for b in band:
        tag = "  ← 车身固有频率" if abs(b["f_Hz"] - fb) < 0.05 else (
            "  ← 车轮固有频率" if abs(b["f_Hz"] - fw) < 0.5 else "")
        print(f"  {b['f_Hz']:>9.2f}{b['min']:>10.4f}{b['max']:>10.4f}"
              f"{b['ratio_max_min']:>11.3f}{tag}")

    out = {"freqs": f.tolist(), "curves": curves, "bands": band,
           "f_body": fb, "f_wheel": fw, "authority": AUTHORITY,
           "c_values": [float(c) for c in cs]}
    (RESULTS / "q1_results.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[结果] {RESULTS / 'q1_results.json'}")

    # ---------- 结论 ----------
    r_low = band[0]["ratio_max_min"]
    r_body = next(b for b in band if abs(b["f_Hz"] - fb) < 0.05)["ratio_max_min"]
    r_wheel = next(b for b in band if abs(b["f_Hz"] - fw) < 0.5)["ratio_max_min"]
    print(f"\n=== Q1 结论 ===")
    print(f"  阻尼可调在低频段({band[0]['f_Hz']:.1f}Hz)带来 {r_low:.2f}× 的传递率变化")
    print(f"  在车身固有频率({fb:.2f}Hz)附近 {r_body:.2f}×")
    print(f"  在车轮固有频率({fw:.1f}Hz)附近 {r_wheel:.2f}×")
    print("  → 可调阻尼的作用集中在**固有频率附近**，这正是它相对被动悬架的全部自由度")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
