#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W52 · 用**图的入度/出度**找 `SumProduct` 的**顶层定理**。

## 为什么要换方法

前面直接搜 `theorem`/`lemma` 抓到的都是**中间引理**
（`integerCoord_exists`、`exists_norm_ge`…）—— 它们是**脚手架**，
不是主结果。

## 图论判据

在 `SumProduct` 的**内部依赖子图**里：

| 角色 | 图特征 | 含义 |
|---|---|---|
| **顶层结果** | **出度低、入度高** | 汇总性的主定理 |
| **底层脚手架** | 出度高、入度低 | 基础定义与工具引理 |

⇒ 找**入度最高**的模块，它的定理名最接近主结果。

## 并回答用户的问题

> "SumProduct 看名字应该是个工具类的"

**判据**：
* 若它是**工具库** ⇒ 会被**多个不同的族**引用（不只 `NilpotentCharts`）；
* 若它是**一个具体研究项目** ⇒ 只与**一个**外部族耦合，且内部高度自洽。

用法：
    $PY q13_sumproduct_toplevel.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from load_imports import find_imports                           # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from net_resolve import open_url                                   # noqa: E402

SRC = find_imports(ROOT)
OUT = ROOT / "episodes" / "2026-W52" / "results" / "q13_SumProduct顶层.json"
PREFIX = "OAI.Combinatorics.SumProduct"
RAW = "https://raw.githubusercontent.com/openai/math/main/lean/"


def main() -> int:
    print("=" * 96)
    print("  W52 · 用图论找 SumProduct 的顶层定理")
    print("=" * 96)

    mods: list[str] = []
    deps: dict[str, list[str]] = {}
    users: Counter = Counter()
    ext_users: Counter = Counter()          # 外部族 -> 引用 SumProduct 的模块数
    with SRC.open(encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            m = re.sub(r"^lean\.", "", d.get("mod", ""))
            ds = [re.sub(r"^lean\.", "", str(x)) for x in (d.get("deps") or [])]
            deps[m] = ds
            if m.startswith(PREFIX):
                mods.append(m)
            for dp in ds:
                if dp.startswith(PREFIX):
                    users[dp] += 1
                    if not m.startswith(PREFIX):
                        p = m.split(".")
                        if len(p) >= 3:
                            ext_users[f"{p[1]}.{p[2]}"] += 1
    mods_set = set(mods)
    print(f"\n  SumProduct 模块 {len(mods)}")

    # ---- 用户的问题：它是工具库吗？----
    print(f"\n  == ★ 谁在引用它（判『工具库』还是『一个项目』）==")
    for k, v in ext_users.most_common(10):
        print(f"     {k:<44}{v:>5}")
    print(f"     外部引用方族数：**{len(ext_users)}**")
    print(f"     ⇒ 若只有 1 个 ⇒ 它是**一个项目的内部依赖**，不是通用工具库")

    # ---- 内部图：入度 Top ----
    indeg = Counter()
    outdeg = Counter()
    for m in mods:
        for dp in deps[m]:
            if dp in mods_set:
                indeg[dp] += 1
                outdeg[m] += 1
    print(f"\n  == SumProduct 内部：入度 Top 12（= 顶层结果候选）==")
    print(f"     {'模块':<58}{'入度':>5}{'出度':>5}")
    for m, v in indeg.most_common(12):
        print(f"     {m[len(PREFIX)+1:]:<58}{v:>5}{outdeg[m]:>5}")

    print(f"\n  == 出度 Top 8（= 底层脚手架）==")
    for m, v in outdeg.most_common(8):
        print(f"     {m[len(PREFIX)+1:]:<58}{indeg[m]:>5}{v:>5}")

    # ---- 抓顶层模块的定理 ----
    print(f"\n  == 顶层候选模块的定理 ==")
    tops = [m for m, _v in indeg.most_common(4)]
    got = []
    for m in tops:
        url = RAW + m.replace(".", "/") + ".lean"
        try:
            t = open_url(url, timeout=45, tries=2).read().decode("utf-8",
                                                                 "ignore")
        except Exception:                                            # noqa: BLE001
            continue
        names = re.findall(r"(?m)^\s*(?:theorem|lemma)\s+([\w'.]+)", t)
        print(f"\n  ── {m[len(PREFIX)+1:]}  （{len(t)} 字符，{len(names)} 条声明）")
        for n in names[-12:]:
            print(f"       · {n}")
        got.append({"module": m, "decls": names})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "n_mods": len(mods),
        "ext_users": dict(ext_users),
        "indeg_top": [[m, v, outdeg[m]] for m, v in indeg.most_common(20)],
        "outdeg_top": [[m, indeg[m], v] for m, v in outdeg.most_common(20)],
        "top_decls": got,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
