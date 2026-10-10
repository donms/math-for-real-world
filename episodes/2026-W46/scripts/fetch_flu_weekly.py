#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · 抓取 CDC《中国流感监测周报》全量序列并结构化。

## 数据源

栏目页：https://www.chinacdc.cn/jksj/jksj04_14249/
实测：列表页 30.5 KB、可抽出 48 条周报链接；逐期正文 ~26 KB。

## 抓什么

每期周报正文里抽出（**抽样 12 期时 9 期成功，本脚本对全量跑并报告成功率**）：

| 字段 | 正则思路 | 原文表述示例 |
|---|---|---|
| `week` | `第\s*(\d+)\s*周` | 第 38 周 |
| `outbreak` | `(?:报告\|共报告)\s*(\d+)\s*起` | 全国报告 47 起流感样病例暴发疫情 |
| `a_pct` | `甲型[^。]{0,40}?(\d+\.\d)\s*%` | 甲型流感占 64.1% |
| `h3n2` | `A\s*\(?\s*H3N2\s*\)?[^。]{0,40}?(\d+\.\d)\s*%` | A(H3N2) 占 94.2% |
| `h1n1` | `A\s*\(?\s*H1N1\s*\)?[^。]{0,40}?(\d+\.\d)\s*%` | A(H1N1)pdm09 占 5.8% |

## 两条纪律（写进代码，也写进论文）

1. **抽不到的期数必须显式列出，不得插值冒充**；
2. **保留原始 HTML**（`data/raw/`），便于复现与口径复核。

用法：
    $PY fetch_flu_weekly.py            # 全量
    $PY fetch_flu_weekly.py --limit 20 # 只抓最近 20 期（试跑）
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120 Safari/537.36"}
LIST_URL = "https://www.chinacdc.cn/jksj/jksj04_14249/"

ROOT = Path(__file__).resolve().parents[1]      # episodes/2026-W46
RAW = ROOT / "data" / "raw" / "flu_weekly"
CLEAN = ROOT / "data" / "clean"

PATTERNS = {
    "week": re.compile(r"第\s*(\d+)\s*周"),
    "outbreak": re.compile(r"(?:全国)?(?:共)?报告\s*(\d+)\s*起"),
    "a_pct": re.compile(r"甲型[^。；]{0,50}?(\d+\.\d)\s*%"),
    "b_pct": re.compile(r"乙型[^。；]{0,50}?(\d+\.\d)\s*%"),
    "h3n2": re.compile(r"H3N2[^。；]{0,60}?(\d+\.\d)\s*%"),
    "h1n1": re.compile(r"H1N1[^。；]{0,60}?(\d+\.\d)\s*%"),
    "ili_pct": re.compile(r"流感样病例[^。；]{0,40}?(\d+\.\d)\s*%"),
}


def get(url: str, timeout: int = 45) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:                                            # noqa: BLE001
        return 0, b""


def strip_tags(html: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&quot;", '"'),
                 ("&#39;", "'"), ("&ldquo;", "“"), ("&rdquo;", "”")):
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="只抓最近 N 期（0=全部）")
    ap.add_argument("--sleep", type=float, default=0.4)
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    CLEAN.mkdir(parents=True, exist_ok=True)

    print("=" * 92)
    print("  W46 · 抓取 CDC 流感监测周报")
    print("=" * 92)

    st, body = get(LIST_URL)
    if st != 200 or not body:
        print(f"  [X] 列表页不可用：{st}")
        return 2
    html = body.decode("utf-8", "ignore")
    (RAW / "_list.html").write_bytes(body)
    print(f"  列表页 {st} {len(body)/1024:.1f}KB")

    # 抽链接并去重（按日期）
    links: dict[str, str] = {}
    for href, _ym, d in re.findall(
            r'href="([^"]*?/(20\d{4})/t(20\d{6})_\d+\.html)"', html):
        full = (href if href.startswith("http")
                else ("https://www.chinacdc.cn" + href[1:]
                      if href.startswith("/") else LIST_URL + href))
        links[d] = full
    dates = sorted(links)
    print(f"  抽到 {len(dates)} 期，{dates[0]} ~ {dates[-1]}")
    if args.limit:
        dates = dates[-args.limit:]
        print(f"  限定最近 {len(dates)} 期")

    rows, failed = [], []
    for i, d in enumerate(dates, 1):
        st2, b2 = get(links[d])
        if st2 != 200 or not b2:
            failed.append((d, f"HTTP {st2}"))
            continue
        (RAW / f"{d}.html").write_bytes(b2)
        txt = strip_tags(b2.decode("utf-8", "ignore"))
        rec = {"date": d, "url": links[d], "bytes": len(b2)}
        for k, p in PATTERNS.items():
            m = p.search(txt)
            rec[k] = m.group(1) if m else ""
        # 标题行（人工复核用）
        mt = re.search(r"(第\s*\d+\s*周[^。]{0,40})", txt)
        rec["title_hint"] = mt.group(1)[:46] if mt else ""
        rows.append(rec)
        if i % 10 == 0 or i == len(dates):
            print(f"    进度 {i}/{len(dates)}  "
                  f"最近 {d}: 周={rec['week'] or '—'} "
                  f"暴发={rec['outbreak'] or '—'} "
                  f"H3N2={rec['h3n2'] or '—'}")
        time.sleep(args.sleep)

    # 落盘
    f_csv = CLEAN / "flu_weekly.csv"
    cols = ["date", "week", "outbreak", "ili_pct", "a_pct", "b_pct",
            "h3n2", "h1n1", "title_hint", "bytes", "url"]
    with open(f_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    got = {k: sum(1 for r in rows if r[k]) for k in PATTERNS}
    print(f"\n{'='*92}")
    print(f"  成功抓取 {len(rows)} 期，失败 {len(failed)} 期")
    if failed:
        print("  失败列表（**不插值，显式列出**）：")
        for d, why in failed[:10]:
            print(f"     {d}  {why}")
    print(f"\n  字段抽取成功率（共 {len(rows)} 期）：")
    for k, v in got.items():
        print(f"     {k:<10}{v:>4} / {len(rows)}"
              f"  ({v/max(len(rows),1)*100:.0f}%)")
    # 关键序列
    ob = [(r["date"], r["week"], r["outbreak"]) for r in rows if r["outbreak"]]
    print(f"\n  暴发疫情序列（{len(ob)} 期）：")
    for d, wk, v in ob[-16:]:
        print(f"     {d}  第{wk or '?'}周  {v} 起")
    print(f"\n  -> {f_csv}")

    # 解析报告
    rep = {"list_url": LIST_URL, "periods_total": len(dates),
           "periods_ok": len(rows), "periods_failed": failed,
           "field_hit": got,
           "note": "抽不到的期数一律留空，不插值"}
    (CLEAN / "flu_weekly_解析报告.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
