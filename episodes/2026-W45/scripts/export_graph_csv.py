#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W45 · 把 SBOM 图导出成题面里承诺的四个 CSV（并做维护者层抓取）。

## 产出（题面 `01_题目.md` 引用）

| 文件 | 内容 |
|---|---|
| `data/clean/deps_nodes.csv` | 节点：node_id |
| `data/clean/deps_edges.csv` | 有向边：source,target（source 依赖 target）|
| `data/clean/deps_roots.csv` | 20 个被扫描仓库的根包 |
| `data/clean/maintainers.csv` | 维护者—包 二部关系（**仅 npm**）|

## 为什么要抓维护者

MemOS 事件的蠕虫机制是"偷令牌 → 以受害者名义发毒包"，
对应**维护者层**的边。npm registry 有 `maintainers` 字段（PyPI 没有）。
本脚本对图中**出现频次最高的 npm 包**抓维护者，构成第二层。

用法：
    $PY export_graph_csv.py [抓维护者的包数，默认 120]
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]                       # episodes/2026-W45
SRC = HERE.parents[3] / "sourcing" / "runs" / "sbom_graph.json"
OUT = ROOT / "data" / "clean"
OUT.mkdir(parents=True, exist_ok=True)

HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
        "Accept": "application/json"}


def is_npm(name: str) -> bool:
    """粗判是否 npm 包：排除 python/java/github 前缀与纯小写下划线名。"""
    if name.startswith(("com.github.", "pkg:", "golang.", "maven.", "nuget.")):
        return False
    if "@" in name.split("@")[0]:
        return True                     # 作用域包 @scope/name
    # python 包常见下划线；npm 也允许但少见
    head = name.split("@")[0]
    return "_" not in head and not head.endswith(".py")


def base_name(node_id: str) -> str:
    """`lodash@4.17.21` -> `lodash`（作用域包保留 @scope/）。"""
    if node_id.startswith("@"):
        parts = node_id.split("@")
        return "@" + parts[1] if len(parts) > 1 else node_id
    return node_id.split("@")[0]


def main() -> int:
    n_want = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    d = json.loads(SRC.read_text(encoding="utf-8"))
    nodes = list(d["nodes"])
    edges = [tuple(e) for e in d["edges"]]
    roots = list(d["roots"])

    print("=" * 88)
    print("  W45 · 导出图数据 + 抓维护者层")
    print("=" * 88)

    # ---- 1) 节点 / 边 / 根 ----
    with open(OUT / "deps_nodes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["node_id"])
        for x in sorted(nodes):
            w.writerow([x])
    with open(OUT / "deps_edges.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source", "target"])
        for a, b in sorted(edges):
            w.writerow([a, b])
    with open(OUT / "deps_roots.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["root"])
        for x in sorted(roots):
            w.writerow([x])
    print(f"  节点 {len(nodes)}  边 {len(edges)}  根 {len(roots)}")

    # ---- 2) 维护者层：挑"最值得关注"的 npm 包 ----
    # 排序依据：该包**被多少不同的包依赖**（入度），去重到包名
    indeg = Counter()
    nbrs = {}
    for a, b in edges:
        nbrs.setdefault(b, set()).add(a)
    for b, s in nbrs.items():
        indeg[base_name(b)] += len(s)
    cands = [p for p, _ in indeg.most_common(2000) if is_npm(p)][:n_want]
    print(f"\n  候选 npm 包 {len(cands)} 个（按被依赖数排序），开始抓 maintainers…")

    rows = []
    ok = 0
    for i, pkg in enumerate(cands, 1):
        url = "https://registry.npmjs.org/" + pkg.replace("/", "%2f")
        try:
            req = urllib.request.Request(url, headers=HDRS)
            with urllib.request.urlopen(req, timeout=20) as r:
                d2 = json.loads(r.read().decode("utf-8", "ignore"))
            ms = [m.get("name") for m in (d2.get("maintainers") or [])
                  if isinstance(m, dict) and m.get("name")]
            for m in ms:
                rows.append((m, pkg))
            ok += 1
            if i <= 12 or i % 25 == 0:
                print(f"    [{i:>3}/{len(cands)}] {pkg[:36]:<38}"
                      f"维护者 {len(ms)}")
        except Exception:                                        # noqa: BLE001
            if i <= 12:
                print(f"    [{i:>3}/{len(cands)}] {pkg[:36]:<38}抓取失败")
        if i % 20 == 0:
            time.sleep(0.3)

    with open(OUT / "maintainers.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["maintainer", "package"])
        for m, p in sorted(set(rows)):
            w.writerow([m, p])

    uniq_pkg = len({p for _, p in rows})
    uniq_m = len({m for m, _ in rows})
    print(f"\n  成功抓取 {ok}/{len(cands)} 个包")
    print(f"  维护者—包 关系 {len(set(rows))} 条 "
          f"（{uniq_m} 位维护者 / {uniq_pkg} 个包）")

    # 复用度：一个维护者管几个包
    per = Counter()
    for m, _ in set(rows):
        per[m] += 1
    multi = {m: c for m, c in per.items() if c > 1}
    print(f"  维护多个包的维护者：{len(multi)} / {uniq_m} "
          f"({len(multi)/max(1,uniq_m)*100:.1f}%)")
    top = sorted(per.items(), key=lambda kv: -kv[1])[:10]
    for m, c in top:
        pk = sorted({p for mm, p in set(rows) if mm == m})
        print(f"    {m[:26]:<28}{c:>3} 个  {pk[:4]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
