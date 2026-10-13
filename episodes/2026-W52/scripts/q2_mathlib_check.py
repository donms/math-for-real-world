#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W52 问 2 · **反驳检验**：孤立是真的，还是"通过 mathlib 间接连通"？

## 为什么必须做这个检验

问 1 发现 OAI 内部边里 **99.6% 是同学科**、**98.3% 的族只用 1 个学科**。
一个立刻的反驳是：

> "那又怎样？所有模块都 import **mathlib**，
>  mathlib 里有全部数学分支 ⇒ 它们**间接**都用了跨领域知识。"

**如果不排除这个解释，问 1 的结论就站不住。**
本脚本专门检验它。

## 检验设计

对每个**学科**，算它的**依赖闭包**，然后看闭包里出现哪些学科：

| 量 | 含义 |
|---|---|
| `direct_cross` | 直接的跨学科边数 |
| `closure_cross` | **闭包**（含 mathlib 中转）里涉及的学科数 |
| `via_mathlib` | 只**经由 mathlib 路径**才能到达的学科 |

* 若 `via_mathlib` 很大 ⇒ **反驳成立**，孤立是假象；
* 若 `via_mathlib` 很小 ⇒ **孤立是真的**（mathlib 是共享底座，
  但不构成"学科间的桥梁"）。

## ★ 关键区分（**这是本检验的核心**）

「**共享底座**」≠「**互相引用**」：

* 两个学科都用 mathlib 的集合论 —— 这叫**共享底座**；
* 椭圆曲线的结果引用了模形式的**具体定理** —— 这叫**桥梁**。

费马大定理需要的是**后者**。本脚本用"**除 mathlib 之外的跨学科路径**"
来度量后者。

用法：
    $PY q2_mathlib_check.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from load_imports import find_imports                           # noqa: E402

SRC = find_imports(ROOT)
OUT = ROOT / "episodes" / "2026-W52" / "results" / "q2_mathlib检验.json"


def parse(mod: str):
    m = re.sub(r"^lean\.", "", mod)
    if not m.startswith("OAI."):
        return None
    p = m.split(".")
    return (p[1], p[2]) if len(p) >= 3 else None


def main() -> int:
    print("=" * 96)
    print("  W52 问 2 · 反驳检验：孤立是真的，还是 mathlib 连通了？")
    print("=" * 96)

    mod2dc: dict[str, tuple[str, str]] = {}
    deps: dict[str, list[str]] = {}
    with SRC.open(encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            mod = re.sub(r"^lean\.", "", d.get("mod", ""))
            p = parse(mod)
            if not p:
                continue
            mod2dc[mod] = p
            deps[mod] = [re.sub(r"^lean\.", "", str(x))
                         for x in (d.get("deps") or [])]

    discs = sorted({v[0] for v in mod2dc.values()})
    print(f"\n  OAI 模块 {len(mod2dc)} / 学科 {len(discs)}")

    # ---------- 每个学科的依赖闭包 ----------
    print(f"\n  == 各学科的依赖闭包（BFS，含所有外部模块）==")
    print(f"     {'学科':<22}{'闭包模块':>10}{'OAI模块':>9}"
          f"{'外部模块':>10}{'闭包内学科':>11}")
    rows = {}
    for d0 in discs:
        seeds = [m for m, v in mod2dc.items() if v[0] == d0]
        seen: set[str] = set()
        stack = list(seeds)
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            stack.extend(deps.get(x, []))
        oai_in = {x for x in seen if x in mod2dc}
        ext_in = seen - oai_in
        disc_in = {mod2dc[x][0] for x in oai_in}
        rows[d0] = {"closure": len(seen), "oai": len(oai_in),
                    "ext": len(ext_in), "discs": sorted(disc_in),
                    "n_disc": len(disc_in)}
        print(f"     {d0:<22}{len(seen):>10}{len(oai_in):>9}"
              f"{len(ext_in):>10}{len(disc_in):>11}")

    # ---------- 关键：**去掉 mathlib 后**还剩多少跨学科路径 ----------
    print(f"\n  == ★ 关键检验：剔除 mathlib 后，跨学科连通还剩多少 ==")
    ML = re.compile(r"^(Mathlib|Batteries|Std|Init|Lean|Aesop|Qq|ProofWidgets)\b")

    print(f"     {'学科':<22}{'含mathlib可达学科':>18}"
          f"{'剔除后可达学科':>16}{'差（靠 mathlib 才通的）':>24}")
    summary = {}
    for d0 in discs:
        # 闭包 A：全部
        seeds = [m for m, v in mod2dc.items() if v[0] == d0]
        def closure(skip_ml: bool) -> set[str]:
            seen: set[str] = set()
            stack = list(seeds)
            while stack:
                x = stack.pop()
                if x in seen:
                    continue
                seen.add(x)
                for y in deps.get(x, []):
                    if skip_ml and ML.match(y):
                        continue
                    stack.append(y)
            return seen
        full = {mod2dc[x][0] for x in closure(False) if x in mod2dc}
        nomin = {mod2dc[x][0] for x in closure(True) if x in mod2dc}
        only_ml = full - nomin
        summary[d0] = {"with_ml": sorted(full), "without_ml": sorted(nomin),
                       "only_via_ml": sorted(only_ml)}
        print(f"     {d0:<22}{len(full):>18}{len(nomin):>16}"
              f"{len(only_ml):>24}")

    # ---------- 结论 ----------
    n_only = sum(1 for d, v in summary.items() if not v["only_via_ml"])
    print(f"\n  == 结论 ==")
    tot_via = sum(len(v["only_via_ml"]) for v in summary.values())
    print(f"     总共 {len(discs)} 个学科")
    print(f"     **剔除 mathlib 后，可达学科数下降的学科："
          f"{len(discs)-n_only} 个**")
    print(f"     **完全不受影响的学科（本就只靠自己）：{n_only} 个**")
    print(f"     所有学科合计『仅靠 mathlib 才能到达』的学科次数：{tot_via}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": rows, "mathlib_check": summary},
                              ensure_ascii=False, indent=2), encoding="utf-8")

    L = ["# W52 · 问 2：mathlib 反驳检验", "",
         "## 为什么必须做", "",
         "问 1 说「99.6% 的内部边是同学科」。一个立刻的反驳：",
         "",
         "> 所有模块都 import mathlib，mathlib 覆盖全部数学分支",
         "> ⇒ 它们**间接**都用了跨领域知识。",
         "",
         "**若不排除这个解释，问 1 的结论不成立。**", "",
         "## ★ 关键区分：共享底座 ≠ 互相引用", "",
         "| | 含义 | 费马大定理需要的是？ |",
         "|---|---|---|",
         "| **共享底座** | 两个学科都用 mathlib 的集合论 | ❌ 不需要 |",
         "| **桥梁** | 椭圆曲线引用模形式的**具体定理** | ✅ 正是它 |",
         "",
         "## 检验结果", "",
         "| 学科 | 含 mathlib 可达学科数 | 剔除后 | "
         "仅靠 mathlib 才通的 |", "|---|---|---|---|"]
    for d0 in discs:
        v = summary[d0]
        L.append(f"| {d0} | {len(v['with_ml'])} | {len(v['without_ml'])} | "
                 f"{len(v['only_via_ml'])} |")
    OUT.write_text(json.dumps({"rows": rows, "mathlib_check": summary},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT.parent / "q2_mathlib检验.md").write_text("\n".join(L), encoding="utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
