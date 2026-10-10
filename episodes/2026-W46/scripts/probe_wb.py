#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · World Bank 指标批量可用性实测（**修正版**）。

## 上一版的 bug（必须记住）

`probe_minwage.py` 里我用通用计数器数 JSON 的"行数"，
而 **World Bank v2 的返回结构是 `[meta, data]`**：
顶层 list 有 **2** 个元素 ⇒ 我把"2 行"当成了结果，
于是所有 WB 指标都报"行 2、不足 5 行"，**全是假报**。
（`probe_w46.py` 里写了 `p_wb` 取 `[1]`，是对的；
`probe_minwage.py` 里图省事用了通用计数器，就错了。）

⇒ **教训：探针的"行数判据"必须按**每个源的实际结构**写，
   不能用通用计数器糊过去** —— 否则会把"有数据"误报成"没数据"
   （这次差点让我错杀一整批可用指标）。

## 本脚本

对一批 WB 指标逐个取 `[1]`，只报**真实数据行数**，
并打印所属国家数与年份范围 —— 这才是判断"能不能支撑建模"的依据。

用法：
    $PY probe_wb.py
"""
from __future__ import annotations

import json
import ssl
import time
import urllib.request
from pathlib import Path

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"}

# 与"工资/收入/就业/分配"相关 + 本期可能用到的结构
INDICATORS = [
    ("SI.POV.GINI", "基尼系数"),
    ("SI.DST.10TH.10", "收入最高10%份额"),
    ("SI.DST.FRST.10", "收入最低10%份额"),
    ("SI.DST.05TH.20", "最高5%份额"),
    ("SL.TLF.CACT.ZS", "劳动参与率"),
    ("SL.TLF.ACTI.1524.ZS", "青年劳动参与率"),
    ("SL.UEM.TOTL.ZS", "失业率"),
    ("SL.UEM.1524.ZS", "青年失业率"),
    ("SL.EMP.WORK.ZS", "雇员占比（受雇者/总就业）"),
    ("SL.EMP.SELF.ZS", "自雇占比"),
    ("SL.EMP.TOTL.SP.ZS", "就业人口比"),
    ("NE.CON.PRVT.PC.KD", "人均家庭消费"),
    ("NE.CON.TOTL.KD", "最终消费支出"),
    ("FP.CPI.TOTL", "CPI"),
    ("NY.GDP.PCAP.PP.KD", "人均GDP(PPP)"),
    ("SP.URB.TOTL.IN.ZS", "城镇化率"),
    ("SP.DYN.CBRT.IN", "出生率"),
    ("SP.POP.65UP.TO.ZS", "65岁以上占比"),
    ("IT.NET.USER.ZS", "互联网普及率"),
    ("GC.XPN.TOTL.GD.ZS", "政府支出占GDP"),
    ("NV.IND.TOTL.ZS", "工业增加值占比"),
    ("NV.AGR.TOTL.ZS", "农业增加值占比"),
    ("BX.KLT.DINV.WD.GD.ZS", "FDI净流入占GDP"),
    ("EN.GHG.CO2.PC.CE.AR5", "人均CO2"),
]

COUNTRIES = ("CHN;USA;DEU;JPN;BRA;KOR;MEX;ZAF;IND;IDN;TUR;RUS;"
             "GBR;FRA;ITA;ESP;POL;THA;VNM;EGY")
DATE = "1990:2025"


def fetch(code: str) -> dict:
    url = (f"https://api.worldbank.org/v2/country/{COUNTRIES}/indicator/"
           f"{code}?format=json&per_page=20000&date={DATE}")
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
            d = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as e:                                       # noqa: BLE001
        return {"code": code, "rows": 0, "err": f"{type(e).__name__}: {e}",
                "sec": round(time.time() - t0, 1)}
    rows = d[1] if isinstance(d, list) and len(d) > 1 else []
    rows = [x for x in rows if x.get("value") is not None]
    if not rows:
        return {"code": code, "rows": 0, "err": "无数据点",
                "sec": round(time.time() - t0, 1)}
    return {
        "code": code, "rows": len(rows),
        "countries": len({x["countryiso3code"] for x in rows}),
        "years": (min(x["date"] for x in rows), max(x["date"] for x in rows)),
        "latest_chn": next((f"{x['date']}={x['value']:.4g}"
                            for x in sorted(rows, key=lambda z: -int(z["date"]))
                            if x["countryiso3code"] == "CHN"), "—"),
        "sec": round(time.time() - t0, 1), "err": "",
    }


def main() -> int:
    print("=" * 100)
    print("  W46 · World Bank 指标可用性（**取 [1]，只数真实数据点**）")
    print("=" * 100)
    print(f"\n  {'指标':<34}{'数据点':>7}{'国家':>5}{'年份范围':>14}"
          f"{'中国最新':>18}{'秒':>6}")
    good, bad = [], []
    for code, label in INDICATORS:
        r = fetch(code)
        if r["rows"] >= 20 and r.get("countries", 0) >= 5:
            good.append((code, label, r))
            print(f"  {label:<34}{r['rows']:>7}{r['countries']:>5}"
                  f"{r['years'][0]+'-'+r['years'][1]:>14}"
                  f"{r['latest_chn']:>18}{r['sec']:>6.1f}")
        else:
            bad.append((code, label, r))
            why = r["err"] or f"仅 {r['rows']} 点"
            print(f"  {label:<34}{r['rows']:>7}{'—':>5}{'—':>14}"
                  f"{why:>18}{r['sec']:>6.1f}")
    print(f"\n{'='*100}")
    print(f"  可用（≥20 数据点且 ≥5 国）: {len(good)} / {len(INDICATORS)}")
    for c, l, r in good:
        print(f"     OK  {l:<32}{c:<26}{r['rows']:>6} 点 / {r['countries']} 国")
    if bad:
        print("  不可用：")
        for c, l, r in bad:
            print(f"     X   {l:<32}{c:<26}{r['err'] or str(r['rows'])+' 点'}")
    p = (Path(__file__).resolve().parents[3] / "sourcing"
         / "w46_wb_indicators.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([{"code": c, "label": l, **r}
                             for c, l, r in good + bad],
                            ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
