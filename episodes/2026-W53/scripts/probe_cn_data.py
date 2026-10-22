#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W53 · 补探**国内交通数据源**（为画面第 2 屏提供准确依据）。

## 为什么要补做

第一轮探针里，国内门户的结果是：

| 源 | 结果 |
|---|---|
| 上海开放数据 | `HTTP 412 Precondition Failed` |
| 北京政务数据 | `SSL BAD_ECPOINT` |
| 广州开放数据 | DNS 失败 |
| **深圳开放数据** | **可达（4096 字节）** ← **但没细查里面有什么** |

⇒ 我只测到"能不能连上"，**没有测"里面有没有逐时段车速数据"**。
若直接说"国内找不到"，那是**未经核实的断言**。

## 本轮要回答的三个问题

1. 深圳开放数据里，**有没有**逐时段交通数据？
2. 国内是否**存在**同类数据（哪怕需要申请）？
3. 若存在，**为什么本集没有用它**？（诚实说明：是数据口径问题，不是国别偏好）

## ★ 判据

* `[OK]` 找到**逐时段（小时级或更细）**的路段/断面车速或流量；
* `[部分]` 找到交通数据但**粒度粗**（如年度 AADT）或**非速度**；
* `[X]` 不可达 / 无时间维度。

用法：
    $PY probe_cn_data.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
OUT = ROOT / "episodes" / "2026-W53" / "data" / "cn_probe.json"

# (名称, URL, 期望命中)
TRIALS = [
    # ---- 深圳开放数据（第一轮唯一可达的国内门户）----
    ("深圳 · 数据集列表 API",
     "https://opendata.sz.gov.cn/api/search/1.0/?keyword=%E4%BA%A4%E9%80%9A"
     "&page=1&pageSize=10", ("交通",)),
    ("深圳 · 数据目录",
     "https://opendata.sz.gov.cn/data/dataSet/toDataSetList",
     ("数据集", "dataSet")),
    ("深圳 · 首页", "https://opendata.sz.gov.cn/", ("数据",)),
    # ---- 其他国内门户（再试一次，可能是临时故障）----
    ("上海开放数据", "https://data.sh.gov.cn/", ("数据",)),
    ("北京公共数据开放平台", "https://data.beijing.gov.cn/", ("数据",)),
    ("广州开放数据", "https://data.gz.gov.cn/", ("数据",)),
    ("浙江公共数据平台", "https://data.zjzwfw.gov.cn/", ("数据",)),
    ("成都开放数据", "https://www.cddata.gov.cn/", ("数据",)),
    # ---- 交通运输部 / 地方交通委 ----
    ("交通运输部 · 数据", "https://www.mot.gov.cn/", ("交通",)),
    ("北京交通委 · 交通指数",
     "https://www.bjjtw.gov.cn/", ("交通",)),
    # ---- 学术 / 竞赛用公开集 ----
    ("UCI · PEMS 交通", "https://archive.ics.uci.edu/dataset/492/"
     "metro+interstate+traffic+volume", ("traffic",)),
]


def main() -> int:
    print("=" * 92)
    print("  W53 补探 · 国内交通数据源")
    print("=" * 92)
    from net_resolve import open_url
    rows = []
    for name, url, keys in TRIALS:
        t0 = time.time()
        try:
            r = open_url(url, timeout=30, tries=1)
            raw = r.read(20000)
            txt = raw.decode("utf-8", "ignore")
            hit = [k for k in keys if k.lower() in txt.lower()]
            has_time = bool(__import__("re").search(
                r"(hour|时间|时段|小时|速度|拥堵|指数|\d{4}-\d{2}-\d{2})",
                txt, __import__("re").I))
            print(f"  [OK ] {name:<26} {len(raw):>6} B  "
                  f"命中={hit}  时间/速度迹象={'有' if has_time else '无'}")
            rows.append({"name": name, "url": url, "verdict": "OK",
                         "bytes": len(raw), "keys_hit": hit,
                         "has_time": has_time})
        except Exception as e:                                       # noqa: BLE001
            print(f"  [X  ] {name:<26} {type(e).__name__:<20} "
                  f"{str(e)[:34]}")
            rows.append({"name": name, "url": url, "verdict": "X",
                         "error": f"{type(e).__name__}: {str(e)[:70]}"})
        _ = t0
    n_ok = sum(1 for r in rows if r["verdict"] == "OK")
    print(f"\n  == 汇总 ==")
    print(f"     可达 {n_ok} / {len(rows)}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"     -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
