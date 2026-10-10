#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 选题探源：**最低工资上调的连锁效应** 等候选方向的数据可达性实测。

## 为什么必须先跑这个（skill 1.3 铁律）

> **先探数据源，再评分。** 别信"这个数据应该有"——
> 实测 URL 能不能抓到、字段全不全、历史多长。
> **拿不到数据就换题**，绝不用「假设数据」硬撑。

## 本期候选（待实测）

* **A 最低工资标准上调**（2026-09 新闻）—— 阈值 + 连锁效应（加班费/社保/失业金）
* **B 出生人口"维持 800 万左右"** —— 但 W44 已做过幼儿园，**有撞车风险**
* **C 超长假期消费**（中秋国庆连休）—— 消费脉冲与错峰
* **D 舆情传播** —— 但 W45 刚做完图论级联，**结构高度重复**

## 本脚本做什么

对每个候选的**具体接口**逐个实测：HTTP 状态、字节数、
**能否解析出 ≥N 行含数值的记录**、并打印 3 行样本。

用法：
    $PY probe_w46.py
"""
from __future__ import annotations

import csv
import io
import json
import ssl
import sys
import time
import urllib.error
import urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120 Safari/537.36"}
TIMEOUT = 45

MIN_ROWS = 5          # 判据：至少能解析这么多行含数值的记录


def get(url: str, timeout: int = TIMEOUT) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, r.read(), ""
    except urllib.error.HTTPError as e:
        return e.code, b"", f"HTTP {e.code}"
    except Exception as e:                                       # noqa: BLE001
        return 0, b"", f"{type(e).__name__}: {e}"


def probe(name: str, url: str, parser=None) -> dict:
    t0 = time.time()
    st, body, err = get(url)
    el = time.time() - t0
    rec = {"name": name, "url": url, "status": st, "bytes": len(body),
           "sec": round(el, 1), "err": err, "rows": 0, "ok": False}
    if st != 200 or not body:
        print(f"  [X] {name:<38} {st} {len(body)}B {el:.1f}s  {err}")
        return rec
    if parser:
        try:
            rows, sample = parser(body)
            rec["rows"] = rows
            rec["ok"] = rows >= MIN_ROWS
            mark = "OK " if rec["ok"] else "行数不足"
            print(f"  [{mark}] {name:<36} {st} {len(body)/1024:>8.1f}KB "
                  f"{el:>5.1f}s  记录 {rows} 行")
            for s in sample[:3]:
                print(f"          {s}")
        except Exception as e:                                   # noqa: BLE001
            rec["err"] = f"parse: {type(e).__name__}: {e}"
            print(f"  [X] {name:<38} 解析失败 {rec['err'][:60]}")
    else:
        rec["ok"] = True
        print(f"  [OK] {name:<38} {st} {len(body)/1024:>8.1f}KB {el:>5.1f}s")
    return rec


# ---------- 各候选的解析器 ----------

def p_json_rows(body: bytes):
    """通用：JSON 数组 / {data:[...]} / [{...}]。"""
    d = json.loads(body.decode("utf-8", "ignore"))
    if isinstance(d, dict):
        for k in ("data", "rows", "list", "result", "records", "items"):
            if isinstance(d.get(k), list):
                d = d[k]
                break
        else:
            d = [d]
    if not isinstance(d, list):
        return 0, []
    num = [r for r in d if isinstance(r, dict)
           and any(isinstance(v, (int, float)) for v in r.values())]
    return len(num), [json.dumps(r, ensure_ascii=False)[:96] for r in num[:3]]


def p_wb(body: bytes):
    """World Bank v2：数组，[0] 是元信息。"""
    d = json.loads(body.decode("utf-8", "ignore"))
    rows = d[1] if isinstance(d, list) and len(d) > 1 else []
    rows = [r for r in rows if r.get("value") is not None]
    return len(rows), [f"{r.get('country',{}).get('value')} "
                       f"{r.get('date')} = {r.get('value')}" for r in rows[:3]]


def p_csv(body: bytes):
    txt = body.decode("utf-8-sig", "ignore")
    rows = list(csv.DictReader(io.StringIO(txt)))
    num = [r for r in rows if any(
        _isnum(v) for v in r.values() if v is not None)]
    return len(num), [json.dumps(r, ensure_ascii=False)[:96] for r in num[:3]]


def _isnum(v) -> bool:
    try:
        float(str(v).replace(",", "").replace("%", ""))
        return True
    except Exception:                                            # noqa: BLE001
        return False


def main() -> int:
    print("=" * 96)
    print("  W46 选题探源（先探数据，再评分）")
    print("=" * 96)
    out = []

    # ---- A 最低工资：国际可比（World Bank / ILO） ----
    print("\n  ── A 最低工资（国际可比口径）──")
    out.append(probe(
        "World Bank 最低工资(按PPP) SL.UEM.MINW.PP",
        "https://api.worldbank.org/v2/country/CHN;USA;DEU;JPN;BRA;IND/"
        "indicator/SL.UEM.MINW.PP?format=json&per_page=500&date=2000:2025",
        p_wb))
    out.append(probe(
        "World Bank 最低工资(名义) SL.UEM.MINW",
        "https://api.worldbank.org/v2/country/all/indicator/SL.UEM.MINW"
        "?format=json&per_page=2000&date=2015:2025", p_wb))

    # ---- 相关宏观（做"连锁效应"要有配套变量）----
    print("\n  ── A' 配套宏观变量（做连锁效应/阈值用）──")
    for code, label in (
        ("SI.POV.GINI", "基尼系数"),
        ("SL.TLF.CACT.ZS", "劳动参与率"),
        ("NE.CON.PRVT.PC.KD", "人均消费"),
        ("FP.CPI.TOTL", "CPI"),
        ("SL.UEM.TOTL.ZS", "失业率"),
        ("NY.GDP.PCAP.PP.KD", "人均GDP(PPP)"),
        ("SL.EMP.WORK.ZS", "雇员占比"),
    ):
        out.append(probe(
            f"World Bank {label} {code}",
            f"https://api.worldbank.org/v2/country/CHN;USA;DEU;JPN;BRA;KOR;"
            f"MEX;ZAF/indicator/{code}?format=json&per_page=2000&date=2000:2025",
            p_wb))

    # ---- B 出生人口（W44 撞车风险，仅作对照）----
    print("\n  ── B 出生人口（对照；W44 已做过幼儿园，撞车风险高）──")
    out.append(probe(
        "World Bank 出生率 SP.DYN.CBRT.IN",
        "https://api.worldbank.org/v2/country/CHN;JPN;KOR;SGP;ITA;ESP/"
        "indicator/SP.DYN.CBRT.IN?format=json&per_page=2000&date=1990:2025",
        p_wb))

    # ---- C 消费脉冲（做"假期脉冲"需要高频数据）----
    print("\n  ── C 消费/假期（高频数据可达性）──")
    out.append(probe(
        "World Bank 最终消费支出 NE.CON.TOTL.KD",
        "https://api.worldbank.org/v2/country/CHN;USA;JPN;KOR/indicator/"
        "NE.CON.TOTL.KD?format=json&per_page=2000&date=2000:2025", p_wb))

    # ---- D 其它可能有戏的结构 ----
    print("\n  ── D 其它候选结构（网络/阈值/排队）──")
    out.append(probe(
        "World Bank 城镇化率 SP.URB.TOTL.IN.ZS",
        "https://api.worldbank.org/v2/country/all/indicator/"
        "SP.URB.TOTL.IN.ZS?format=json&per_page=5000&date=2015:2025", p_wb))
    out.append(probe(
        "USGS 地震（对照，验证网络仍通）",
        "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson"
        "&starttime=2026-01-01&minmagnitude=5&limit=50", p_json_rows))

    ok = [r for r in out if r["ok"]]
    print(f"\n{'='*96}")
    print(f"  可用 {len(ok)} / {len(out)}")
    for r in ok:
        print(f"     OK  {r['name']}  {r['rows']} 行")
    bad = [r for r in out if not r["ok"]]
    if bad:
        print("  不可用 / 行数不足：")
        for r in bad:
            why = r["err"] or f"仅 {r['rows']} 行（阈值 {MIN_ROWS}）"
            print(f"     X   {r['name']}  {why[:56]}")
    # ⚠️ 路径层级：脚本在 `NewsMCM/episodes/2026-W46/scripts/` 下
    #    ⇒ parents[0]=scripts, [1]=2026-W46, [2]=episodes, [3]=NewsMCM
    #    上一版写成 parents[2] ⇒ 落到了 `episodes/sourcing/`（实测踩过）。
    out_p = (__import__("pathlib").Path(__file__).resolve().parents[3]
             / "sourcing" / "w46_probe.json")
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"\n  -> {out_p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
