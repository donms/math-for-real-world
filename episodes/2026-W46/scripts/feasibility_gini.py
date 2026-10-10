#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · 分配结构候选：**可行性硬验证**（不是评分，是能不能做）。

## 要回答的三个问题

1. **解释变量与中国 Gini 的年份能否对齐**（Gini 只有 20 个点，且不在连续年份）；
2. **有没有信号** —— 用最简单的相关/回归先看一眼
   （若连方向性都看不出来，这个题就不该做）；
3. **数据有没有明显异常**（跳变、口径断点）。

> 注意：这里只做**可行性探测**，不是正式建模。
> 正式建模要等用户选定题目后再做。

用法：
    $PY feasibility_gini.py
"""
from __future__ import annotations

import json
import ssl
import urllib.request
from pathlib import Path

import numpy as np

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"}

VARS = [
    ("SI.POV.GINI", "gini"),
    ("SP.URB.TOTL.IN.ZS", "urban"),
    ("SP.POP.65UP.TO.ZS", "aging"),
    ("SL.TLF.CACT.ZS", "lfp"),
    ("SL.EMP.WORK.ZS", "employee"),
    ("SL.EMP.SELF.ZS", "selfemp"),
    ("NV.IND.TOTL.ZS", "industry"),
    ("NV.AGR.TOTL.ZS", "agri"),
    ("SL.UEM.TOTL.ZS", "unemp"),
    ("NE.CON.PRVT.PC.KD", "cons_pc"),
    ("NY.GDP.PCAP.PP.KD", "gdppc"),
    ("IT.NET.USER.ZS", "internet"),
    ("BX.KLT.DINV.WD.GD.ZS", "fdi"),
    ("SI.DST.10TH.10", "top10"),
    ("SI.DST.FRST.10", "bot10"),
]
COUNTRIES = "CHN;USA;DEU;JPN;BRA;KOR;MEX;IDN;TUR;RUS;GBR;FRA;ITA;ESP;POL;THA"


def fetch(code: str, ctry: str) -> dict[tuple[str, int], float]:
    url = (f"https://api.worldbank.org/v2/country/{ctry}/indicator/{code}"
           f"?format=json&per_page=20000&date=1990:2025")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90, context=CTX) as r:
        d = json.loads(r.read().decode("utf-8", "ignore"))
    rows = d[1] if isinstance(d, list) and len(d) > 1 else []
    return {(x["countryiso3code"], int(x["date"])): float(x["value"])
            for x in rows if x.get("value") is not None}


def main() -> int:
    print("=" * 96)
    print("  W46 · 分配结构候选可行性硬验证")
    print("=" * 96)
    data: dict[str, dict[tuple[str, int], float]] = {}
    for code, key in VARS:
        try:
            data[key] = fetch(code, COUNTRIES)
            print(f"  [OK] {key:<10} {len(data[key]):>5} 点")
        except Exception as e:                                   # noqa: BLE001
            print(f"  [X ] {key:<10} {type(e).__name__}: {str(e)[:50]}")
            data[key] = {}

    # ---- 1) 中国的年份对齐 ----
    print(f"\n  ── 1) 中国：Gini 年份 vs 各解释变量覆盖 ──")
    gini_cn = {y: v for (c, y), v in data["gini"].items() if c == "CHN"}
    years = sorted(gini_cn)
    print(f"     Gini 年份 {years[0]}–{years[-1]}，共 {len(years)} 点")
    print(f"\n     {'变量':<10}{'覆盖 Gini 年份数':>18}   缺失年份")
    usable = []
    for code, key in VARS[1:]:
        d_cn = {y for (c, y), _ in data[key].items() if c == "CHN"}
        hit = [y for y in years if y in d_cn]
        miss = [y for y in years if y not in d_cn]
        flag = ""
        if len(hit) >= len(years) - 2:
            usable.append(key)
            flag = " ✅"
        print(f"     {key:<10}{len(hit):>10} / {len(years):<6}"
              f"{str(miss[:6]):<28}{flag}")

    # ---- 2) 信号粗看（中国，用能对齐的年份）----
    print(f"\n  ── 2) 信号粗看（中国，n = {len(years)}）──")
    g = np.array([gini_cn[y] for y in years], dtype=float)
    print(f"     Gini: {g[0]:.1f} ({years[0]}) → 峰 {g.max():.1f} "
          f"({years[int(g.argmax())]}) → {g[-1]:.1f} ({years[-1]})")
    print(f"\n     {'变量':<10}{'相关系数':>10}{'斜率(每单位)':>14}  方向")
    for key in usable:
        d_cn = {y: v for (c, y), v in data[key].items() if c == "CHN"}
        x = np.array([d_cn[y] for y in years], dtype=float)
        if x.std() == 0:
            continue
        r = float(np.corrcoef(x, g)[0, 1])
        b = float(np.polyfit(x, g, 1)[0])
        arrow = "同向" if r > 0.3 else ("反向" if r < -0.3 else "弱")
        print(f"     {key:<10}{r:>10.3f}{b:>14.4f}  {arrow}")

    # ---- 3) 倒 U 是否可检验 ----
    print(f"\n  ── 3) 倒 U（Kuznets）能否检验 ──")
    for cty in ("CHN", "USA", "BRA", "KOR"):
        gv = {y: v for (cc, y), v in data["gini"].items() if cc == cty}
        yv = {y: v for (cc, y), v in data["gdppc"].items() if cc == cty}
        common = sorted(set(gv) & set(yv))
        if len(common) < 8:
            print(f"     {cty}: 共同年份仅 {len(common)} ⇒ 不足以拟合")
            continue
        x = np.log([yv[y] for y in common])
        gv_ = np.array([gv[y] for y in common])
        c2 = np.polyfit(x, gv_, 2)
        peak = -c2[1] / (2 * c2[0]) if c2[0] != 0 else float("nan")
        shape = "倒U" if c2[0] < 0 else "U型"
        print(f"     {cty}: n={len(common):>2}  二次项 {c2[0]:>+7.2f}  "
              f"⇒ {shape}，拐点人均GDP≈{np.exp(peak):,.0f}（2017国际元）"
              if np.isfinite(peak) else f"     {cty}: n={len(common)}")

    # ---- 4) 异常检查 ----
    print(f"\n  ── 4) 数据异常（|相邻年变化| 过大）──")
    for cty in ("CHN", "USA", "BRA"):
        gv = {y: v for (cc, y), v in data["gini"].items() if cc == cty}
        ys = sorted(gv)
        jumps = [(ys[i - 1], ys[i], gv[ys[i]] - gv[ys[i - 1]])
                 for i in range(1, len(ys)) if abs(gv[ys[i]] - gv[ys[i - 1]]) > 3]
        print(f"     {cty}: {len(jumps)} 处年际跳变 >3 点 {jumps[:3]}")

    p = (Path(__file__).resolve().parents[3] / "sourcing"
         / "w46_feasibility.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "gini_years_chn": years,
        "gini_chn": {str(k): v for k, v in gini_cn.items()},
        "usable_vars": usable,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
