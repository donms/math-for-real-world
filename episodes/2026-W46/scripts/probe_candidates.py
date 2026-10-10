#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · 候选选题的数据源**实测**（不验证不上评分表）。

## 为什么必须实测这些

调研 agent 标了 ✅/⚠️/❌，但其中几个关键源它**没亲手验证**：
* CDC 流感监测周报（标 ✅）—— 要确认**能否程序化取到历史序列**；
* 交通运输部统计公报（标 ✅）—— 要确认是**结构化数据**还是只有正文；
* 农业农村部生猪专题（标 ✅）；
* 山东电力交易中心（标 ⚠️ SPA）；
* USGS 地震 API（标 ❌ 未测）—— **W45 实测它是 0 行**，今回再确认；
* FRED / Energy-Charts API（标 ❌ 未测）。

## 判据（与 W45 一致）

**能解析出 ≥N 行含数值的记录**才算可用；HTTP 200 但 0 行 ⇒ **不可用**。

用法：
    $PY probe_candidates.py
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
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36",
      "Accept": "text/html,application/json,*/*"}


def get(url: str, timeout: int = 40) -> tuple[int, bytes, str, float]:
    t0 = time.time()
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, r.read(), "", time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, b"", f"HTTP {e.code}", time.time() - t0
    except Exception as e:                                       # noqa: BLE001
        return 0, b"", f"{type(e).__name__}: {str(e)[:60]}", time.time() - t0


def show(name: str, url: str, mode: str = "raw", min_rows: int = 3) -> dict:
    st, body, err, el = get(url)
    n = 0
    note = ""
    if st == 200 and body:
        txt = body.decode("utf-8", "ignore")
        if mode == "json":
            try:
                d = json.loads(txt)
                n = len(d) if isinstance(d, list) else len(d.get("data", []) or [])
            except Exception:                                    # noqa: BLE001
                n = 0
        elif mode == "html":
            # 粗略：数"含数字的 <li>/<tr>/<a> 行"
            n = len(re.findall(r"20\d{2}[-/年]\d{1,2}", txt))
            note = f"{len(body)/1024:.0f}KB"
        else:
            n = 1
            note = f"{len(body)/1024:.0f}KB"
    ok = st == 200 and n >= min_rows
    print(f"  [{'OK ' if ok else 'X  '}] {name:<40} {st:>3} "
          f"{len(body)/1024:>8.1f}KB {el:>5.1f}s  命中 {n:<5}{note}  {err}")
    return {"name": name, "url": url, "status": st, "bytes": len(body),
            "hits": n, "ok": ok, "err": err}


def main() -> int:
    print("=" * 104)
    print("  W46 · 候选选题数据源实测（HTTP 200 但 0 行 ⇒ 不可用）")
    print("=" * 104)
    out = []

    print("\n  ── 候选 1：流感监测（CDC 周报）──")
    out.append(show("CDC 流感周报列表页",
                    "https://www.chinacdc.cn/jksj/jksj04_14249/", "html", 5))
    out.append(show("CDC 第 38 周周报正文",
                    "https://www.chinacdc.cn/jksj/jksj04_14249/202609/"
                    "t20260926_1841814.html", "html", 1))
    out.append(show("国家疾控局 秋冬季传染病通知",
                    "https://www.ndcpa.gov.cn/jbkzzx/yqxxxw/common/content/"
                    "content_2104754493620391936.html", "html", 1))
    out.append(show("WHO FluNet 接口",
                    "https://service.healthdata.gov/api/v1/datasets.json",
                    "json", 1))

    print("\n  ── 候选 2：公路养护 / 高速公路 ──")
    out.append(show("交通运输部 统计公报页",
                    "https://xxgk.mot.gov.cn/jigou/zhghs/202606/"
                    "t20260618_4207752.html", "html", 3))
    out.append(show("交通运输部 信息公开始页",
                    "https://xxgk.mot.gov.cn/", "html", 3))

    print("\n  ── 候选 3：电价 / 电力 ──")
    out.append(show("Energy-Charts 公开 API（德国电价）",
                    "https://api.energy-charts.info/price"
                    "?bzn=DE-LU&start=2026-09-01&end=2026-09-07", "json", 10))
    out.append(show("Energy-Charts 主页", "https://www.energy-charts.info/",
                    "html", 1))
    out.append(show("山东电力交易中心（预期 SPA）",
                    "https://pmos.sd.sgcc.com.cn/", "html", 1))

    print("\n  ── 候选 4：生猪（农业农村部）──")
    out.append(show("农业农村部 生猪专题",
                    "https://www.moa.gov.cn/ztzl/szcpxx/", "html", 3))
    out.append(show("农业农村部 生猪月度数据 2026",
                    "https://www.moa.gov.cn/ztzl/szcpxx/jdsj/2026/", "html", 3))

    print("\n  ── 候选 7：地震（再确认 W45 的 0 行）──")
    out.append(show("USGS FDSN count（纯计数接口）",
                    "https://earthquake.usgs.gov/fdsnws/event/1/count"
                    "?format=text&starttime=2026-01-01&minmagnitude=5",
                    "raw", 1))
    out.append(show("USGS query geojson",
                    "https://earthquake.usgs.gov/fdsnws/event/1/query"
                    "?format=geojson&starttime=2026-01-01&minmagnitude=5"
                    "&limit=50", "raw", 1))
    out.append(show("中国地震台网 正式测定目录",
                    "https://news.ceic.ac.cn/index.html", "html", 1))

    print("\n  ── 候选 5：汇率 / 宏观（FRED）──")
    out.append(show("FRED 系列列表（无 key 试）",
                    "https://fred.stlouisfed.org/graph/fredgraph.csv"
                    "?id=DEXCHUS", "raw", 5))

    ok = [r for r in out if r["ok"]]
    print(f"\n{'='*104}")
    print(f"  可用: {len(ok)} / {len(out)}")
    for r in ok:
        print(f"     OK  {r['name']}")
    print("  不可用：")
    for r in out:
        if not r["ok"]:
            why = r["err"] if r["err"] else f"仅 {r['hits']} 命中"
            print(f"     X   {r['name']:<40}{why}")

    p = (Path(__file__).resolve().parents[3] / "sourcing"
         / "w46_candidates_probe.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    print(f"\n  -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
