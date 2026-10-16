#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W47 选题探源：**江阴靖江长江隧道**（新过江通道）的数据可得性实测。

## 已确认的热点事实（2026-09）

* **2026-09-24** 通车。北接 G2 京沪高速靖江枢纽，南在徐霞客枢纽接 G4221 沪武高速，
  **双向 6 车道**；与江阴大桥构成 **"一桥一隧"双向十二车道**格局。
* **客货分离**：隧道**全时段禁货车**（客车专用）；大桥保持客货混行。
* 来源：中国江苏网 2026-09-23、央视 2026-09-25。

## 已拿到的**核心量化数字**（江苏省国资委 2026-09-29）

| 指标 | 值 |
|---|---|
| 中秋期间过江通道**日均断面流量** | **13.47 万辆** |
| 其中 江阴大桥 | **10.55 万辆** |
| 其中 隧道 | **2.92 万辆** |
| 2024 同期 江阴大桥 | 12.44 万辆 ⇒ **下降 15.2%** |
| 通道总流量 | **增长 8.24%** |
| 南向北 / 北向南 最高小时流量 | **7696 / 7121 辆**（较 2024 同期 +63.6% / +47.4%）|
| 隧道承担高峰流量 | **约三成** |
| 通行效率提升 / 拥堵里程下降 | **+35% / −75%** |
| 事故 | 通道日均 **7 起**（大桥 6、隧道 1），2024 同期 **16 起** ⇒ **−56%** |
| 引流 | 日均 **1.64 万辆**跨境客车被引至隧道 |
| 毗邻公交 | 3 条线路、日均 **210 班次**、累计近万人次、**较开通前翻倍** |

## ⚠️ 但这里有一个**必须写进论文的口径陷阱**

官方口径的比较是：
> **2026 中秋（桥+隧）** vs **2024 中秋（只有桥）**

这**同时**包含两个效应：
1. **分流**（桥 → 隧）；
2. **诱增/趋势增长**（多了 8.24% 的总流量）。

⇒ **不能把"大桥 −15.2%"直接当成隧道的分流贡献** ——
必须把"趋势增长"与"分流"分开，否则会高估隧道的分流效果。
**这正是可做数学建模的地方。**

## 本脚本探什么

按 skill W47-1 的规矩（**先探数据源再评分**），逐个实测：
1. **江苏宁沪高速（600377）** 年报/公告 —— 含路段**车流量与通行费收入**分项；
2. **上交所 / 巨潮资讯** 公告接口；
3. **江苏省交通运输厅** 统计公报；
4. **交通运输部** 统计公报（w45 实测可达）；
5. 长江过江通道的其它公开统计。

用法：
    $PY probe_w47.py
"""
from __future__ import annotations

import json
import re
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
      "Accept": "text/html,application/json,*/*"}
TIMEOUT = 40
ROOT = Path(__file__).resolve().parents[1]


def get(url: str, timeout: int = TIMEOUT):
    req = urllib.request.Request(url, headers=UA)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, r.read(), "", time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, b"", f"HTTP {e.code}", time.time() - t0
    except Exception as e:                                       # noqa: BLE001
        return 0, b"", f"{type(e).__name__}: {str(e)[:52]}", time.time() - t0


def show(name: str, url: str, kind: str = "html", pat: str | None = None):
    st, body, err, el = get(url)
    hits = 0
    note = ""
    if st == 200 and body:
        txt = body.decode("utf-8", "ignore")
        note = f"{len(body)/1024:.0f}KB"
        if pat:
            hits = len(re.findall(pat, txt))
        else:
            hits = 1
    ok = st == 200 and hits > 0
    print(f"  [{'OK ' if ok else 'X  '}] {name:<38} {st:>3} "
          f"{len(body)/1024:>8.1f}KB {el:>5.1f}s  命中 {hits:<5}{note} {err}")
    return {"name": name, "url": url, "status": st, "kb": round(len(body)/1024, 1),
            "hits": hits, "sec": round(el, 1), "ok": ok, "err": err}


CANDS = [
    # ── A 高速公路运营商（**最有希望：年报按路段披露车流量与收入**）──
    ("A 上市公司", "宁沪高速 600377 上交所公告页",
     "https://www.sse.com.cn/assortment/stock/list/info/company/"
     "index.shtml?COMPANY_CODE=600377", "html", r"600377"),
    ("A 上市公司", "上交所 公告检索(宁沪高速)",
     "https://query.sse.com.cn/security/stock/queryCompanyBulletinNew.do"
     "?jsonCallBack=cb&isPagination=true&productId=600377&keyWord="
     "&reportType2=&reportType=ALL&beginDate=2024-01-01"
     "&endDate=2026-12-31&pageHelp.pageSize=25&pageHelp.pageNo=1",
     "json", r"bulletin"),
    ("A 上市公司", "巨潮资讯 公告检索 API",
     "http://www.cninfo.com.cn/new/hisAnnouncement/query", "json", None),
    ("A 上市公司", "宁沪高速 官网 投资者关系",
     "https://www.jsexpressway.com/", "html", None),
    # ── B 交通主管部门 ──
    ("B 交通主管", "交通运输部 统计公报(w45 实测可达)",
     "https://xxgk.mot.gov.cn/jigou/zhghs/202606/t20260618_4207752.html",
     "html", r"高速公路|过江|长江"),
    ("B 交通主管", "江苏省交通运输厅",
     "https://jtyst.jiangsu.gov.cn/", "html", None),
    ("B 交通主管", "江苏省交通运输厅 统计栏目",
     "https://jtyst.jiangsu.gov.cn/col/col13760/index.html", "html", None),
    ("B 交通主管", "江苏交控(控股股东)官网",
     "https://www.jsjtkj.com/", "html", None),
    # ── C 长江过江通道专项数据 ──
    ("C 过江通道", "江苏省国资委 该篇原文(已抓)",
     "https://jsgzw.jiangsu.gov.cn/art/2026/9/29/art_11787_11836651.html",
     "html", r"万辆"),
    ("C 过江通道", "江苏交控 新闻栏目",
     "https://www.jsjtkj.com/xwzx/", "html", None),
    ("C 过江通道", "长江航务管理局 统计数据",
     "https://www.cjhy.gov.cn/", "html", None),
    # ── D 宏观/区域（World Bank 等已证可用，作对照）──
    ("D 宏观", "World Bank 中国货运量(对照)",
     "https://api.worldbank.org/v2/country/CHN/indicator/"
     "IS.SHP.GOOD.TU?format=json&per_page=100&date=2000:2024", "json",
     r'"value"'),
    ("D 宏观", "World Bank 中国公路里程(对照)",
     "https://api.worldbank.org/v2/country/CHN/indicator/"
     "IS.ROD.TOTL.KM?format=json&per_page=100&date=2000:2024", "json",
     r'"value"'),
]


def main() -> int:
    print("=" * 100)
    print("  W47 选题探源 · 江阴靖江长江隧道（新过江通道）")
    print("=" * 100)
    out = []
    cur = None
    for grp, name, url, kind, pat in CANDS:
        if grp != cur:
            print(f"\n  ── {grp} ──")
            cur = grp
        out.append({**show(name, url, kind, pat), "group": grp})

    ok = [r for r in out if r["ok"]]
    print(f"\n{'='*100}")
    print(f"  可用 {len(ok)} / {len(out)}")
    for r in ok:
        print(f"     [OK] {r['group']:<10} {r['name']}")
    print("  不可用：")
    for r in out:
        if not r["ok"]:
            print(f"     [X ] {r['group']:<10} {r['name']:<38}"
                  f"{r['err'] or f'仅 {r[chr(104)+chr(105)+chr(116)+chr(115)]} 命中'}")

    p = ROOT / "sourcing" / "w47_probe.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
