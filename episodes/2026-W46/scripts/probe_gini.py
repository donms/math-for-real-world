#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · 分配类指标（Gini / 份额）的中国数据点核查。

## 为什么单查这一项

`probe_wb.py` 显示 Gini 一类的**数据点只有 455**（其它指标 ~700），
说明**年份有缺口**（Gini 不是每年都测）。
而"分配结构 + 归因分解"这个方向能否成立，
**完全取决于中国与主要国家在关键年份有没有数据**。

⇒ 必须把**逐年的点**拉出来看，而不是只看"455 点"。

用法：
    $PY probe_gini.py
"""
from __future__ import annotations

import json
import ssl
import urllib.request
from pathlib import Path

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"}

CODES = [("SI.POV.GINI", "Gini"),
         ("SI.DST.10TH.10", "最高10%"),
         ("SI.DST.FRST.10", "最低10%"),
         ("SI.DST.05TH.20", "最高5%")]
FOCUS = ["CHN", "USA", "DEU", "JPN", "BRA", "KOR", "MEX", "ZAF", "IND", "IDN",
         "TUR", "RUS", "GBR", "FRA", "ITA", "ESP", "POL", "THA", "VNM", "EGY"]


def fetch(code: str, ctry: str) -> dict[tuple[str, int], float]:
    r"""返回 **{(国家码, 年份): 值}**。

    ⚠️ 这里必须**按国/年正确索引**：上一版把返回的扁平字典
    `{(country,year): value}` 当成"国家 -> {年: 值}"去用，
    于是每个国家都取到 `float`，全部误报"无数据"
    —— 这是本轮**第二个探针 bug**（第一个是 WB 的 `[1]`）。
    ⇒ **探针自己的数据模型也要先自检一遍**：
      随便挑一个已知国家，确认能取到值，再往下判。
    """
    url = (f"https://api.worldbank.org/v2/country/{ctry}/indicator/{code}"
           f"?format=json&per_page=20000&date=1990:2025")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
        d = json.loads(r.read().decode("utf-8", "ignore"))
    rows = d[1] if isinstance(d, list) and len(d) > 1 else []
    return {(x["countryiso3code"], int(x["date"])): float(x["value"])
            for x in rows if x.get("value") is not None}


def by_country(flat: dict[tuple[str, int], float],
               c: str) -> dict[int, float]:
    return {y: v for (cc, y), v in flat.items() if cc == c}


def main() -> int:
    print("=" * 100)
    print("  W46 · 分配类指标逐年覆盖（Gini 一族）")
    print("=" * 100)
    data: dict[str, dict[tuple[str, int], float]] = {}
    for code, label in CODES:
        data[label] = fetch(code, ";".join(FOCUS))
        print(f"\n  ── {label}（{code}）──")
        for c in FOCUS:
            vv = by_country(data[label], c)
            yrs = sorted(vv)
            if not yrs:
                print(f"     {c:<5} 无数据")
                continue
            recent = [y for y in yrs if y >= 2016]
            print(f"     {c:<5} {len(yrs):>3} 点  {yrs[0]}–{yrs[-1]}  "
                  f"近10年 {len(recent):>2} 点   最新 {yrs[-1]}={vv[yrs[-1]]:.1f}")

    # 关键判据：中国 + 近 10 年点数
    print(f"\n{'='*100}")
    print("  ── 判据：能否支撑『分配结构 + 归因分解』──")
    need = ["CHN", "USA", "DEU", "JPN", "BRA", "KOR"]
    gini = data["Gini"]
    ok_ctry = [c for c in need if len(by_country(gini, c)) >= 8]
    print(f"     重点国家（{', '.join(need)}）中 Gini ≥8 点：{ok_ctry}")
    all_ctry = [c for c in FOCUS if len(by_country(gini, c)) >= 8]
    print(f"     全体 20 国里 Gini ≥8 点：{len(all_ctry)} 国 -> {all_ctry}")
    chn = by_country(gini, "CHN")
    print(f"     中国 Gini 年份：{sorted(chn)}")
    if chn:
        print("     中国 Gini 值：" +
              ", ".join(f"{y}={chn[y]:.1f}" for y in sorted(chn)))

    p = (Path(__file__).resolve().parents[3] / "sourcing"
         / "w46_gini_coverage.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(
        {k: {f"{c}|{y}": v for (c, y), v in sorted(vv.items())}
         for k, vv in data.items()},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
