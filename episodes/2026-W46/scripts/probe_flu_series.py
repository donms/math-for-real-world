#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · 流感监测：**能否抽成连续时间序列**（决定这个题能不能做）。

## 为什么这一步是决定性的

调研 agent 给出的关键论据是一条序列：
> 第 31→38 周暴发疫情 = 0, 1, 2, 0, 0, **7, 34, 47** 起

**这条序列能不能程序化、可复现地抽出来，决定选题成立与否。**
抽样看一两期不算数 —— 要能**批量拿到多期**、并**结构化解析**。

## 本脚本

1. 抓 CDC 流感监测周报**列表页**，抽出所有周报链接（含期号/日期）；
2. 抓其中**若干期**正文；
3. 从正文里用正则提取：
   * **暴发疫情起数**（"报告…起"）
   * **甲型/乙型占比**
   * **A(H3N2) / A(H1N1)pdm09 占比**
4. 打印抽到的序列，并报告**成功率**。

判据：能稳定抽出 ≥8 期、且暴发疫情数形成序列 ⇒ **可用**。

用法：
    $PY probe_flu_series.py
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
                    "AppleWebKit/537.36 Chrome/120 Safari/537.36"}
LIST = "https://www.chinacdc.cn/jksj/jksj04_14249/"


def get(url: str, timeout: int = 40) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:                                            # noqa: BLE001
        return 0, b""


def text_of(html: str) -> str:
    """去标签取正文文本（够用即可）。"""
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = (t.replace("&nbsp;", " ").replace("&amp;", "&")
         .replace("&#39;", "'").replace("&quot;", '"'))
    return re.sub(r"\s+", " ", t)


def main() -> int:
    print("=" * 96)
    print("  W46 · 流感监测周报：序列可抽取性实测")
    print("=" * 96)

    st, body = get(LIST)
    html = body.decode("utf-8", "ignore")
    print(f"\n  列表页 {st}  {len(body)/1024:.1f}KB")
    # 抽周报链接：/202609/t20260926_xxxxxxx.html
    links = sorted(set(re.findall(
        r'href="([^"]*?/(20\d{4})/t(20\d{6})_\d+\.html)"', html)))
    print(f"  抽到链接 {len(links)} 条")
    uniq: dict[str, str] = {}
    for href, ym, d in links:
        full = href if href.startswith("http") else \
            ("https://www.chinacdc.cn" + href if href.startswith("/")
             else LIST + href)
        uniq[d] = full
    dates = sorted(uniq)
    print(f"  去重后 {len(dates)} 期，日期范围 {dates[0] if dates else '—'} "
          f"~ {dates[-1] if dates else '—'}")
    for d in dates[:3] + ["..."] + dates[-3:]:
        print(f"     {d}  {uniq.get(d, '')[:88]}")

    # ---- 逐期抽数 ----
    print(f"\n  ── 逐期抽取（最近 12 期）──")
    pats = {
        "outbreak": re.compile(r"(?:报告|共报告)\s*(\d+)\s*起"),
        "week": re.compile(r"第\s*(\d+)\s*周"),
        "a_pct": re.compile(r"甲型[^。]{0,40}?(\d+\.\d)\s*%"),
        "h3n2": re.compile(r"A\s*\(?\s*H3N2\s*\)?[^。]{0,40}?(\d+\.\d)\s*%"),
        "h1n1": re.compile(r"A\s*\(?\s*H1N1\s*\)?[^。]{0,40}?(\d+\.\d)\s*%"),
    }
    rows = []
    for d in dates[-12:]:
        st2, b2 = get(uniq[d])
        if st2 != 200 or not b2:
            print(f"     {d}  抓取失败 {st2}")
            continue
        t = text_of(b2.decode("utf-8", "ignore"))
        rec = {"date": d, "url": uniq[d]}
        for k, p in pats.items():
            m = p.search(t)
            rec[k] = m.group(1) if m else None
        rows.append(rec)
        hit = sum(1 for k in pats if rec.get(k))
        print(f"     {d}  {len(b2)/1024:>6.1f}KB  命中 {hit}/5  "
              f"周={rec['week']} 暴发={rec['outbreak']} "
              f"甲型={rec['a_pct']}% H3N2={rec['h3n2']}%")
        time.sleep(0.4)

    print(f"\n{'='*96}")
    got_out = [(r["date"], r["outbreak"]) for r in rows if r["outbreak"]]
    print(f"  抽到暴发疫情起数的期数: {len(got_out)} / {len(rows)}")
    if got_out:
        print("  序列（日期 -> 起数）：")
        for d, v in got_out:
            print(f"     {d}  {v}")
    print(f"\n  判据：≥8 期且形成序列 ⇒ 可用。"
          f"当前 {'✅ 可用' if len(got_out) >= 8 else '⚠️ 期数不足，需换抓取策略'}")

    p = (Path(__file__).resolve().parents[3] / "sourcing"
         / "w46_flu_probe.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"links": uniq, "rows": rows},
                            ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
