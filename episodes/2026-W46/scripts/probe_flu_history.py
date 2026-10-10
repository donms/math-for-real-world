#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · CDC 流感周报：**能否取到更长的历史**（决定建模范围）。

## 为什么要探这个

`fetch_flu_weekly.py` 实测：栏目页**只有 14 期**（2024-07-23 ~ 2026-09-26），
而不是调研所说的"11 页约 130 期"。
**这是决定性的**：若只有最近 12 期，就
* 建不了**季节性**项（没有一个完整冬春流行季）；
* 只能做"最近这波上升段"，做不了"秋冬季同比"。

⇒ 必须先把"能取多长历史"这件事查清楚，再谈建模范围。
**取不到就在选题卡/题面里如实降级，不假装有。**

## 本脚本试哪些入口

1. 栏目页的**分页参数**（`index.html` / `index_1.html` / `?page=N`）；
2. CDC 站的**站内搜索**；
3. 常见的历年栏目路径（`jksj04_14249/2025/`、`/2024/` 等）；
4. 周报 PDF 附件的直链模式；
5. 国家流感中心 CNIC 的英文周报（ivdc.chinacdc.cn）。

用法：
    $PY probe_flu_history.py
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
BASE = "https://www.chinacdc.cn/jksj/jksj04_14249/"

CANDS = [
    ("栏目页 第1页", BASE),
    ("index.html", BASE + "index.html"),
    ("index_1.html", BASE + "index_1.html"),
    ("index_2.html", BASE + "index_2.html"),
    ("?page=2", BASE + "?page=2"),
    ("2025 目录", BASE + "2025/"),
    ("2024 目录", BASE + "2024/"),
    ("2023 目录", BASE + "2023/"),
    ("CDC 站内搜索 流感周报",
     "https://www.chinacdc.cn/was5/web/search?channelid=274943"
     "&searchword=%E6%B5%81%E6%84%9F%E7%9B%91%E6%B5%8B%E5%91%A8%E6%8A%A5"),
    ("CNIC 英文周报(中国流感中心)",
     "https://ivdc.chinacdc.cn/cnic/en/Surveillance/WeeklyReport/"),
    ("CDC 健康数据 栏目",
     "https://www.chinacdc.cn/jksj/"),
]


def get(url: str, timeout: int = 35) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, r.read(), ""
    except urllib.error.HTTPError as e:
        return e.code, b"", f"HTTP {e.code}"
    except Exception as e:                                       # noqa: BLE001
        return 0, b"", f"{type(e).__name__}: {str(e)[:50]}"


def main() -> int:
    print("=" * 100)
    print("  W46 · 流感周报历史可及性探测")
    print("=" * 100)
    out = []
    for name, url in CANDS:
        st, body, err = get(url)
        n_link = 0
        n_date = 0
        if st == 200 and body:
            h = body.decode("utf-8", "ignore")
            n_link = len(set(re.findall(r"/t(20\d{6})_\d+\.html", h)))
            n_date = len(re.findall(r"20\d{2}[-/年]\d{1,2}", h))
        has = n_link > 0
        print(f"  [{'OK ' if has else 'X  '}] {name:<26} {st:>3} "
              f"{len(body)/1024:>7.1f}KB  周报链接 {n_link:>3}  日期串 {n_date:>4}"
              f"  {err}")
        out.append({"name": name, "url": url, "status": st,
                    "bytes": len(body), "links": n_link, "err": err})
        time.sleep(0.3)

    print(f"\n{'='*100}")
    best = max(out, key=lambda r: r["links"])
    print(f"  链接最多的入口：{best['name']}  {best['links']} 条")
    print("  ── 判定 ──")
    if best["links"] <= 20:
        print("     ⇒ **只能拿到最近约 12–14 期**（不足一个完整流行季的两倍）")
        print("     ⇒ 建模范围必须降级：")
        print("        · 不做季节性项（无完整冬春季可比）")
        print("        · 主分析锁定『最近这波起爆段』")
        print("        · 若要更长序列，需换源（CNIC / WHO FluNet / 文献附表）")
    else:
        print(f"     ⇒ 可取 {best['links']} 期，足够做季节性")

    p = (Path(__file__).resolve().parents[3] / "sourcing"
         / "w46_flu_history.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    print(f"\n  -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
