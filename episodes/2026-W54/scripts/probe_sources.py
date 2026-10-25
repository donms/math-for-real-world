#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W54 探针 · **三条数据路线的可达性与粒度实测**。

> skill 铁律 1：**先探数据源，再评分。别信"这个数据应该有"。**

## 三条路

| 路 | 想拿什么 | 用来干什么 |
|---|---|---|
| **A** | 近年成交**地块的建面与户数** | 标定 `成本(N) = C_floor + k·N^α` 里的规模参数 |
| **B** | **上市物企**的公开财务与在管面积 | 用行业数据交叉验证"小项目不赚钱" |
| **C** | 已**撤场案例**的规模（户数/建面） | 看撤场是否集中在特定规模区间 |

## 本脚本只做一件事：**打印每个端点的真实状态**

不猜、不推断可达性 —— 逐个请求，把 HTTP 码/字节数/是否含 JSON 打出来。
**不可达的也要记下来**（写进来源清单的"被拒用的数字及理由"）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from net_resolve import open_url                                  # noqa: E402

OUT = ROOT / "episodes" / "2026-W54" / "data"
OUT.mkdir(parents=True, exist_ok=True)

ENDPOINTS: list[tuple[str, str, str]] = [
    # ---------- 路 A：土地与地块 ----------
    ("A", "自然资源部", "https://www.mnr.gov.cn/"),
    ("A", "中国土地市场网", "https://www.landchina.com/"),
    ("A", "上海规资局", "https://ghzyj.sh.gov.cn/"),
    ("A", "苏州自然资源局", "http://zrzy.jiangsu.gov.cn/sz/"),
    ("A", "中指研究院", "https://www.cih-index.com/"),
    ("A", "克而瑞", "https://www.cricchina.com/"),
    ("A", "贝壳研究院", "https://research.ke.com/"),
    ("A", "链家新房", "https://newhouse.lianjia.com/"),
    ("A", "房天下", "https://www.fang.com/"),
    ("A", "好地网", "https://www.keyland.com.cn/"),
    # ---------- 路 B：上市物企 ----------
    ("B", "HKEX 披露易", "https://www.hkexnews.hk/"),
    ("B", "HKEX 标题搜索 API",
     "https://www1.hkexnews.hk/search/titleSearchServlet.do"
     "?sortDir=0&sortByOptions=DateTime&category=0&market=SEHK"
     "&stockId=-1&documentType=-1&fromDate=20260101&toDate=20261231"
     "&title=&searchType=1&t1code=40000&t2Gcode=-2&t2code=40100"
     "&rowRange=100&lang=zh"),
    ("B", "东方财富 数据中心", "https://datacenter-web.eastmoney.com/api/data/v1/get"
     "?reportName=RPT_HKF10_FN_MAININDICATOR&columns=ALL&pageSize=5"),
    ("B", "东方财富 板块列表",
     "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=100&po=1"
     "&fs=b:BK0479&fields=f12,f14,f20,f21"),
    ("B", "同花顺 港股", "https://basic.10jqka.com.cn/HK6098/"),
    ("B", "新浪港股行情", "https://hq.sinajs.cn/list=hk06098"),
    ("B", "腾讯行情", "https://qt.gtimg.cn/q=hk06098"),
    ("B", "中物研协", "https://www.zgwy.org.cn/"),
    ("B", "乐居财经 物业", "https://www.lejucaijing.com/"),
    # ---------- 路 C：撤场案例 ----------
    ("C", "证券时报", "https://www.stcn.com/"),
    ("C", "澎湃新闻", "https://www.thepaper.cn/"),
    ("C", "观点网", "https://www.guandian.cn/"),
    ("C", "中国物业管理协会", "http://www.ecpmi.org.cn/"),
    ("C", "百度新闻搜索",
     "https://www.baidu.com/s?wd=%E7%89%A9%E4%B8%9A%E6%92%A4%E5%9C%BA"),
]


def probe(kind: str, name: str, url: str) -> dict:
    rec = {"路": kind, "名称": name, "url": url}
    try:
        r = open_url(url, timeout=20, tries=1)
        raw = r.read(6000)
        t = raw.decode("utf-8", "ignore")
        rec["状态"] = "OK"
        rec["字节"] = len(raw)
        rec["像JSON"] = t.lstrip()[:1] in "{[" or "json" in \
            r.headers.get("Content-Type", "").lower()
        rec["片段"] = t[:100].replace("\n", " ")
    except Exception as e:                                        # noqa: BLE001
        rec["状态"] = f"{type(e).__name__}"
        rec["错误"] = str(e)[:70]
    return rec


def main() -> int:
    print("=" * 100)
    print("  W54 探针 · 三条数据路线的可达性实测")
    print("=" * 100)
    recs: list[dict] = []
    cur = ""
    for kind, name, url in ENDPOINTS:
        if kind != cur:
            cur = kind
            label = {"A": "路 A · 土地与地块",
                     "B": "路 B · 上市物企",
                     "C": "路 C · 撤场案例"}[kind]
            print(f"\n-- {label} --")
        rec = probe(kind, name, url)
        recs.append(rec)
        if rec["状态"] == "OK":
            print(f"  [OK ] {name:<16}{rec['字节']:>6}B "
                  f"{'JSON' if rec['像JSON'] else 'HTML'}  "
                  f"{rec['片段'][:52]!r}")
        else:
            print(f"  [X  ] {name:<16}{rec['状态']:<18}"
                  f"{rec.get('错误', '')[:44]}")

    print(f"\n{'='*100}")
    print("  汇总")
    print(f"{'='*100}")
    for kind, label in (("A", "土地与地块"), ("B", "上市物企"),
                        ("C", "撤场案例")):
        rs = [r for r in recs if r["路"] == kind]
        ok = [r for r in rs if r["状态"] == "OK"]
        print(f"  {label:<12} 可达 {len(ok)}/{len(rs)}")
        for r in ok:
            print(f"      ✓ {r['名称']}")
        miss = [r for r in rs if r["状态"] != "OK"]
        if miss:
            print(f"      不可达："
                  + "、".join(f"{r['名称']}({r['状态']})" for r in miss))

    (OUT / "probe_数据源.json").write_text(
        json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  [落盘] {OUT / 'probe_数据源.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
