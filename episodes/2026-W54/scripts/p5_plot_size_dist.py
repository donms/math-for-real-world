#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W54 · **地块规模的横截面分布 + 时间趋势**（合并两批数据，按公告季度分组）。

## 为什么必须按「公告季度」而不是「挂牌起始」

* 第一批（`fetch_jiangsu_land.py`）**从最新往回翻** ⇒ 样本严重偏向最近两个月；
* 第二批（`fetch_jiangsu_stratified.py`）**按季度分层** ⇒ 时间上均匀；
* 两批的「挂牌起始时间」都**不是公告发布时间** ⇒ 直接按它分组会错。

**⇒ 统一用 `data/公告日期.json`（公告发布日期）分季度。**

## ★★ 三条必须先声明的口径与偏差

| # | 项 | 说明 |
|---|---|---|
| **1** | **样本非随机** | 只覆盖江苏省内已抓到的区划；**不是普查、不可外推全国** |
| **2** | **两批混合** | 第一批有"最近两个月偏多"的残留 ⇒ **趋势只用分层批次** |
| **3** | **户数靠假设** | 户数 = 建筑面积 ÷ 户均建面，故对户均建面做 **5 档敏感性** |
"""
from __future__ import annotations

import json
import random
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W54"
JSONL = EP / "data" / "江苏宗地.jsonl"
DATES = EP / "data" / "公告日期.json"
OUT = EP / "results"
OUT.mkdir(parents=True, exist_ok=True)

PER_HH = [110, 120, 130, 140, 150]


def main() -> int:
    rows = []
    for ln in JSONL.open(encoding="utf-8"):
        try:
            rows.append(json.loads(ln))
        except Exception:                                         # noqa: BLE001
            continue
    rows = [r for r in rows if r.get("建筑面积_m2")]
    dates: dict[str, str] = {}
    if DATES.exists():
        dates = json.loads(DATES.read_text(encoding="utf-8"))

    def quarter(r: dict) -> str:
        r"""优先用**公告发布日期**（`data/公告日期.json`）；
        没有则回退到抓取时记录的 `季度` 字段（分层批次已写）。

        ★ 为什么要回退：`公告日期.json` 需逐个公告回查（慢），
        而分层批次的记录**本来就带 `季度`**（查询区间即季度）
        ⇒ 不必等映射建完就能出趋势。
        """
        ds = dates.get(str(r.get("公告ID")), "") or ""
        if len(ds) >= 7 and ds[:4].isdigit():
            return f"{ds[:4]}Q{(int(ds[5:7])-1)//3+1}"
        q = str(r.get("季度") or "")
        if len(q) == 6 and q[4] == "Q" and q[:4].isdigit():
            return q
        return "未知"

    for r in rows:
        r["_季度"] = quarter(r)
        r["_批次"] = r.get("采集批次") or "第一批"

    print("=" * 96)
    print("  W54 · 地块规模：横截面分布 + 时间趋势")
    print("=" * 96)
    print(f"  样本 **{len(rows)} 宗住宅用地**（江苏省自然资源厅出让公告）")
    regs = sorted({r["地区"] for r in rows})
    print(f"  覆盖 {len(regs)} 个区划：{'、'.join(regs)}")
    b1 = sum(1 for r in rows if r["_批次"] == "第一批")
    print(f"  批次：第一批 {b1} 宗｜分层-季度 {len(rows)-b1} 宗")

    # ---------------- 横截面 ----------------
    areas = sorted(r["建筑面积_m2"] for r in rows)
    print(f"\n{'='*96}")
    print("  一、横截面分布（全部样本）")
    print(f"{'='*96}")
    print(f"  建筑面积（㎡）：最小 {areas[0]:,.0f}｜P25 "
          f"{areas[len(areas)//4]:,.0f}｜**中位 {st.median(areas):,.0f}**"
          f"｜P75 {areas[3*len(areas)//4]:,.0f}｜最大 {areas[-1]:,.0f}")
    print(f"\n  {'档位(㎡)':<20}{'宗数':>6}{'占比':>9}  直方图")
    BINS = [(0, 10000), (10000, 26000), (26000, 50000),
            (50000, 100000), (100000, 10**9)]
    dist = []
    for lo, hi in BINS:
        c = sum(1 for a in areas if lo <= a < hi)
        lbl = f"{lo:,}–{hi:,}" if hi < 10**9 else f"{lo:,}+"
        dist.append({"档位": lbl, "宗数": c, "占比": c / len(areas)})
        print(f"  {lbl:<20}{c:>6}{c/len(areas)*100:>8.1f}%  "
              f"{'#' * max(1, round(c / len(areas) * 40))}")

    print(f"\n  -- 反推户数（户均建面 5 档敏感性）--")
    print(f"  {'户均建面':>8}{'≤200户宗数':>12}{'占比':>9}"
          f"{'≤100户宗数':>12}{'占比':>9}")
    sens = []
    for p in PER_HH:
        hh = [a / p for a in areas]
        n200 = sum(1 for x in hh if x <= 200)
        n100 = sum(1 for x in hh if x <= 100)
        sens.append({"户均建面": p, "≤200户": n200,
                     "≤200占比": n200 / len(hh),
                     "≤100户": n100, "≤100占比": n100 / len(hh)})
        print(f"  {p:>8}{n200:>12}{n200/len(hh)*100:>8.1f}%"
              f"{n100:>12}{n100/len(hh)*100:>8.1f}%")

    print(f"\n  -- 户数分档（130 ㎡/户）--")
    hh = sorted(a / 130 for a in areas)
    for lo, hi in ((0, 100), (100, 200), (200, 500), (500, 10**9)):
        c = sum(1 for x in hh if lo <= x < hi)
        lbl = f"{lo}-{hi} 户" if hi < 10**9 else f"{lo}+ 户"
        print(f"  {lbl:<14}{c:>5}{c/len(hh)*100:>8.1f}%  "
              f"{'#' * max(1, round(c / len(hh) * 40))}")

    # ---------------- 时间趋势 ----------------
    print(f"\n{'='*96}")
    print("  二、时间趋势（★ 只用分层批次 —— 第一批有「最近两个月偏多」的偏差）")
    print(f"{'='*96}")
    strat = [r for r in rows
             if r["_批次"] == "分层-季度" and r["_季度"] != "未知"]
    print(f"  分层批次可用样本 **{len(strat)} 宗**")
    trend = None
    if len(strat) < 20:
        print("  样本不足（<20）⇒ **暂不出趋势结论**，待抓取完成")
    else:
        byq: dict[str, list[float]] = defaultdict(list)
        for r in strat:
            byq[r["_季度"]].append(r["建筑面积_m2"])
        print(f"\n  {'季度':<9}{'宗数':>6}{'中位建面㎡':>13}{'P25':>11}"
              f"{'≤5万㎡占比':>12}{'≤200户占比':>13}")
        for q in sorted(byq):
            v = sorted(byq[q])
            lo5 = sum(1 for x in v if x < 50000) / len(v)
            lo200 = sum(1 for x in v if x / 130 <= 200) / len(v)
            print(f"  {q:<9}{len(v):>6}{st.median(v):>13,.0f}"
                  f"{v[len(v)//4]:>11,.0f}{lo5*100:>11.1f}%"
                  f"{lo200*100:>12.1f}%")
        qs = sorted(byq)
        if len(qs) >= 4:
            h = len(qs) // 2
            e = [x for q in qs[:h] for x in byq[q]]
            l = [x for q in qs[h:] for x in byq[q]]
            print(f"\n  -- 前 {h} 个季度 vs 后 {len(qs)-h} 个季度 --")
            print(f"     前（{qs[0]}…{qs[h-1]}）n={len(e)}  中位 "
                  f"{st.median(e):,.0f} ㎡")
            print(f"     后（{qs[h]}…{qs[-1]}）n={len(l)}  中位 "
                  f"{st.median(l):,.0f} ㎡")
            chg = (st.median(l) - st.median(e)) / st.median(e)
            print(f"     ⇒ 变化 **{chg*100:+.1f}%**"
                  f"（{'变小' if chg < 0 else '变大'}）")
            random.seed(20261016)
            d = []
            for _ in range(3000):
                a = [random.choice(e) for _ in e]
                b = [random.choice(l) for _ in l]
                d.append(st.median(b) - st.median(a))
            d.sort()
            lo2, hi2 = d[75], d[2925]
            print(f"     bootstrap 95% 区间：**[{lo2:+,.0f}, {hi2:+,.0f}] ㎡**")
            if lo2 < 0 < hi2:
                print("     ⇒ ★ 跨 0，**方向不稳** ⇒ 不能断言趋势")
            else:
                print(f"     ⇒ 方向稳定（{'变小' if hi2 < 0 else '变大'}）")
            trend = {"前": {"季度": [qs[0], qs[h-1]], "n": len(e),
                          "中位": st.median(e)},
                     "后": {"季度": [qs[h], qs[-1]], "n": len(l),
                          "中位": st.median(l)},
                     "变化率": chg, "bootstrap95": [lo2, hi2],
                     "方向稳定": not (lo2 < 0 < hi2)}

    res = {
        "_样本": len(rows), "_地区": regs,
        "_批次": {"第一批": b1, "分层": len(rows) - b1},
        "_来源": "江苏省自然资源厅 tdsc_getDkxx.action",
        "_口径": "建筑面积取自公告原值；户数=建筑面积÷户均建面（假设）；"
               "季度来自公告发布日期（data/公告日期.json）",
        "横截面": {"最小": areas[0], "P25": areas[len(areas)//4],
                 "中位": st.median(areas),
                 "P75": areas[3*len(areas)//4],
                 "最大": areas[-1], "分档": dist},
        "敏感性_户均建面": sens,
        "趋势": trend,
        "_偏差声明": [
            "样本非随机，仅江苏省已抓区划，不可外推全国",
            "第一批从最新往回翻 ⇒ 有「最近两个月偏多」残留；趋势只用分层批次",
            "户数依赖户均建面假设 ⇒ 已做 5 档敏感性",
        ],
    }
    (OUT / "p5_地块规模分布.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  [落盘] {OUT / 'p5_地块规模分布.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
