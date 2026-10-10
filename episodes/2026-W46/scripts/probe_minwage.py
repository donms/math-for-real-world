#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · 最低工资数据：**替代源实测**（World Bank 那条是空的）。

## 已实测结论

World Bank 的两个最低工资指标都**返回 0 行**：
* `SL.UEM.MINW.PP`（按 PPP 的最低工资）
* `SL.UEM.MINW`（名义最低工资）

⇒ 我原本最看好的"最低工资阈值 + 连锁效应"方向，
**用 WB 这条路走不通**，必须找替代源，或换题。

## 本脚本测什么

1. **ILO STAT**（`rplumber.ilo.org`）—— 最低工资的权威源
2. **OECD**（`stats.oecd.org` / `sdmx.oecd.org`）
3. **中国国家统计局**（`data.stats.gov.cn` 的年度数据接口）——
   W45 实测 403，再确认一次
4. **人社部**（最低工资标准公告页）—— 是否有结构化数据
5. **World Bank 的其它工资类指标** —— 看看有没有能替代的

用法：
    $PY probe_minwage.py
"""
from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120 Safari/537.36",
      "Accept": "application/json, text/plain, */*"}


def get(url: str, timeout: int = 40) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, r.read(), ""
    except urllib.error.HTTPError as e:
        return e.code, b"", f"HTTP {e.code}"
    except Exception as e:                                       # noqa: BLE001
        return 0, b"", f"{type(e).__name__}: {str(e)[:70]}"


def show(name: str, url: str, want_rows: bool = True) -> dict:
    t0 = time.time()
    st, body, err = get(url)
    el = time.time() - t0
    rows = 0
    sample = ""
    if st == 200 and body:
        try:
            d = json.loads(body.decode("utf-8", "ignore"))
            if isinstance(d, list):
                rows = len(d)
            elif isinstance(d, dict):
                for k in ("data", "rows", "value", "observations", "results"):
                    if isinstance(d.get(k), list):
                        rows = len(d[k])
                        sample = json.dumps(d[k][:1], ensure_ascii=False)[:100]
                        break
                else:
                    rows = 1
                    sample = json.dumps(d, ensure_ascii=False)[:100]
        except Exception:                                        # noqa: BLE001
            rows = -1          # 非 JSON
    tag = "OK " if (st == 200 and (rows >= 5 or not want_rows)) else "X  "
    print(f"  [{tag}] {name:<40} {st:>3} {len(body)/1024:>8.1f}KB "
          f"{el:>5.1f}s  行 {rows}")
    if sample:
        print(f"           {sample}")
    if err:
        print(f"           {err}")
    return {"name": name, "url": url, "status": st, "bytes": len(body),
            "rows": rows, "err": err}


def main() -> int:
    print("=" * 100)
    print("  W46 · 最低工资替代源实测")
    print("=" * 100)
    out = []

    print("\n  ── 1) ILO STAT（最低工资权威源）──")
    out.append(show("ILO 最低工资 (EAR_INEE_NOC_NB)",
                    "https://rplumber.ilo.org/data/indicator/"
                    "?id=EAR_INEE_NOC_NB&format=json&ref_area=CHN,USA,DEU"))
    out.append(show("ILO 最低工资 (EAR_4MTH_SEX_ECO_CUR_NB)",
                    "https://rplumber.ilo.org/data/indicator/"
                    "?id=EAR_4MTH_SEX_ECO_CUR_NB&format=json&ref_area=CHN"))
    out.append(show("ILO 平均月收入 (EAR_4MTH_SEX_ECO_CUR_NB_A)",
                    "https://rplumber.ilo.org/data/indicator/"
                    "?id=EAR_4MTH_SEX_ECO_CUR_NB_A&format=json&ref_area=CHN"))

    print("\n  ── 2) OECD（SDMX / 旧接口）──")
    out.append(show("OECD SDMX 最低工资",
                    "https://sdmx.oecd.org/public/rest/data/"
                    "OECD.ELS.SAE,DSD_LMS@DF_LMS_MINWAGE,1.0/"
                    ".A....?format=jsondata&startPeriod=2000"))
    out.append(show("OECD stats 最低工资(旧)",
                    "https://stats.oecd.org/SDMX-JSON/data/"
                    "MINWAGE/MINWAGE/all?json-lang=en"))

    print("\n  ── 3) 中国国家统计局（再确认）──")
    out.append(show("统计局 年度数据 接口",
                    "https://data.stats.gov.cn/easyquery.htm?m=QueryData"
                    "&dbcode=hgnd&rowcode=zb&colcode=sj&wds=[]&dfwds=[]"))
    out.append(show("统计局 首页（连通性）", "https://data.stats.gov.cn/"))

    print("\n  ── 4) World Bank 其它工资/劳动类指标（找替代）──")
    for code, label in (
        ("SL.EMP.TOTL.SP.ZS", "就业人口比"),
        ("NV.IND.TOTL.ZS", "工业增加值占比"),
        ("GC.XPN.TOTL.GD.ZS", "政府支出占GDP"),
        ("SI.DST.10TH.10", "收入最高10%份额"),
        ("SI.DST.FRST.10", "收入最低10%份额"),
        ("SL.TLF.ACTI.1524.ZS", "青年劳动参与率"),
    ):
        out.append(show(
            f"WB {label} {code}",
            f"https://api.worldbank.org/v2/country/CHN;USA;DEU;JPN;BRA;KOR;"
            f"MEX;ZAF;IND;IDN/indicator/{code}"
            f"?format=json&per_page=2000&date=2000:2025"))

    ok = [r for r in out if r["status"] == 200 and r["rows"] >= 5]
    print(f"\n{'='*100}")
    print(f"  可用（≥5 行）: {len(ok)} / {len(out)}")
    for r in ok:
        print(f"     OK  {r['name']}  {r['rows']} 行")
    p = (Path(__file__).resolve().parents[3] / "sourcing"
         / "w46_probe_minwage.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    print(f"\n  -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
