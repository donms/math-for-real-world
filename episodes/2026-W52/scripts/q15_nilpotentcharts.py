#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W52 · 深挖 `Geometry.NilpotentCharts`：**独立结果，还是专为该问题搭的脚手架？**

## 为什么这一问重要

前面的链条：

```
Combinatorics.SumProduct  --263 条边-->  Geometry.NilpotentCharts
（Hindman 猜想项目）                      （幂零群 / Malcev 基）
```

**已确认方向单向。**剩下一个关键问题：

| 若 `NilpotentCharts` 是… | 含义 |
|---|---|
| **独立的结果**（只被 `SumProduct` 用是巧合）| 那 263 条边是**真·跨领域借用** |
| **专为此项目搭的脚手架** | 那 263 条边是**一个项目内部的分层**，不是学科间的桥梁 |

## 判据（四条，逐层收紧）

| # | 判据 | 若"专为项目搭" | 若"独立结果" |
|---|---|---|---|
| 1 | **子族数** | 只有 1 个（专一）| 多个平行子族 |
| 2 | **入边来源** | 只来自 `SumProduct` | 来自多个不相关的族 |
| 3 | **它在 `formalization.yaml` 里吗** | 不在（不是主结果）| 在（自己是一个形式化条目）|
| 4 | **内部有没有自己的顶层定理** | 只有工具引理 | 有汇总性主定理 |

用法：
    $PY q15_nilpotentcharts.py
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
OUT = ROOT / "episodes" / "2026-W52" / "results" / "q15_NilpotentCharts.json"
RAW = "https://raw.githubusercontent.com/openai/math/main/lean/"
PREFIX = "OAI.Geometry.NilpotentCharts"


def main() -> int:
    print("=" * 96)
    print("  W52 · 深挖 Geometry.NilpotentCharts")
    print("=" * 96)

    mods: list[str] = []
    deps: dict[str, list[str]] = {}
    users_ext: Counter = Counter()      # 外部族 -> 引用次数
    users_mod: Counter = Counter()
    with SRC.open(encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            m = re.sub(r"^lean\.", "", d.get("mod", ""))
            ds = [re.sub(r"^lean\.", "", str(x))
                  for x in (d.get("deps") or [])]
            deps[m] = ds
            if m.startswith(PREFIX):
                mods.append(m)
            for dp in ds:
                if dp.startswith(PREFIX):
                    users_mod[dp] += 1
                    if not m.startswith(PREFIX):
                        p = m.split(".")
                        if len(p) >= 3:
                            users_ext[f"{p[1]}.{p[2]}"] += 1
    mods_set = set(mods)
    mods.sort()
    print(f"\n  模块数：{len(mods)}")

    # ---- 判据 1：子族数 ----
    sub = Counter(m[len(PREFIX) + 1:].split(".")[0]
                  for m in mods if len(m) > len(PREFIX) + 1)
    print(f"\n  [判据 1] 子族数：**{len(sub)}**")
    for k, v in sub.most_common():
        print(f"       {k:<30}{v:>4}")
    print(f"       ⇒ {'只有 1 个子族（专一）' if len(sub) == 1 else '多个平行子族'}")

    # ---- 判据 2：入边来源 ----
    print(f"\n  [判据 2] 谁在引用它（外部族）")
    for k, v in users_ext.most_common(10):
        print(f"       {k:<44}{v:>5}")
    print(f"       外部引用方族数：**{len(users_ext)}**")
    print(f"       ⇒ {'只被 1 个族用（疑似专为该项目）' if len(users_ext) <= 1 else f'被 {len(users_ext)} 个族用'}")

    # ---- 判据 3：在不在 formalization.yaml 里 ----
    print(f"\n  [判据 3] 它是不是一个**形式化条目**（在 formalization.yaml 里）")
    try:
        y = open_url("https://raw.githubusercontent.com/openai/math/main/"
                     "lean/formalization.yaml", timeout=120,
                     tries=3).read().decode("utf-8", "ignore")
        st = re.search(r"(?ms)^status:(.*?)(?=^\w|\Z)", y)
        files = re.findall(r"file:\s*(\S+)", st.group(1)) if st else []
        hits = [f for f in files if "NilpotentChart" in f]
        print(f"       status.main_results 里的 Lean 文件共 {len(files)} 个")
        print(f"       其中路径含 'NilpotentChart' 的：**{len(hits)}**")
        for h in hits[:6]:
            print(f"          {h}")
        # 也看 sources 的标题
        srcs = re.findall(r'(?m)^\s*-\s+title:\s*"(.+?)"', y)
        t_hits = [t for t in srcs if re.search(r"nilpotent|malcev|chart",
                                              t, re.I)]
        print(f"       sources 标题里含 nilpotent/malcev/chart 的：{len(t_hits)}")
        for t in t_hits[:5]:
            print(f"          {t}")
    except Exception as e:                                           # noqa: BLE001
        print(f"       [X] {type(e).__name__}: {str(e)[:50]}")

    # ---- 判据 4：内部顶层定理 ----
    indeg = Counter()
    outdeg = Counter()
    for m in mods:
        for dp in deps.get(m, []):
            if dp in mods_set:
                indeg[dp] += 1
                outdeg[m] += 1
    print(f"\n  [判据 4] 内部入度 Top 8（顶层候选）")
    print(f"       {'模块':<44}{'入度':>5}{'出度':>5}")
    for m, v in indeg.most_common(8):
        print(f"       {m[len(PREFIX)+1:]:<44}{v:>5}{outdeg[m]:>5}")

    print(f"\n  == 顶层模块的声明（找主定理）==")
    for m in [x for x, _v in indeg.most_common(3)]:
        url = RAW + m.replace(".", "/") + ".lean"
        try:
            t = open_url(url, timeout=45, tries=2).read().decode("utf-8",
                                                                 "ignore")
        except Exception:                                            # noqa: BLE001
            continue
        names = re.findall(r"(?m)^\s*(?:theorem|lemma)\s+([\w'.]+)", t)
        defs = re.findall(r"(?m)^\s*(?:def|abbrev|structure)\s+([\w'.]+)", t)
        print(f"\n       ── {m[len(PREFIX)+1:]}  （{len(t)} 字符）")
        print(f"          def/structure {len(defs)} 条: {defs[:8]}")
        print(f"          theorem/lemma {len(names)} 条（末 10）: {names[-10:]}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "n_mods": len(mods), "subfamilies": dict(sub),
        "ext_users": dict(users_ext),
        "indeg_top": [[m, v, outdeg[m]] for m, v in indeg.most_common(15)],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
