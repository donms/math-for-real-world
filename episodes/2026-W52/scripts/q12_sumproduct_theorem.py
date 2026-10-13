#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W52 · 找 `SumProduct` 里的**定理陈述**（一锤定音）。

## 前几轮的线索

* `CONTENTS.md` 命中 **`[164] Hindman's finite sums and products conjecture`**；
* namespace 有 `TorusLeibman`、`IntegerHyperplane`、`ConstructedWordPlan`；
* 用到 `polynomialOrbit : (ι → Polynomial ℝ) → ℕ → UnitAddTorus ι`；
* `import OAI.Geometry.NilpotentCharts.Main`（跨学科那一半）。

## 做法

在 259 个模块里搜 **`theorem`/`lemma` 的陈述**，
优先取名字含 `main` / `hindman` / `sumProduct` / `dichotomy` 的，
打印**完整陈述**（不带证明）。

用法：
    $PY q12_sumproduct_theorem.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from load_imports import find_imports                           # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from net_resolve import open_url                                   # noqa: E402

SRC = find_imports(ROOT)
OUT = ROOT / "episodes" / "2026-W52" / "results" / "q12_SumProduct定理.json"
PREFIX = "OAI.Combinatorics.SumProduct"
RAW = "https://raw.githubusercontent.com/openai/math/main/lean/"

KEY = re.compile(r"(?:theorem|lemma)\s+(\w*(?:main|hindman|sumProduct|"
                 r"dichotomy|exist|alignment)\w*)", re.I)


def fetch(m: str):
    url = RAW + m.replace(".", "/") + ".lean"
    try:
        return m, open_url(url, timeout=45, tries=2).read().decode(
            "utf-8", "ignore")
    except Exception:                                                # noqa: BLE001
        return m, ""


def main() -> int:
    print("=" * 96)
    print("  W52 · 找 SumProduct 的定理陈述")
    print("=" * 96)

    mods = []
    with SRC.open(encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            m = re.sub(r"^lean\.", "", d.get("mod", ""))
            if m.startswith(PREFIX):
                mods.append(m)
    mods.sort()
    # 优先取名字"像主结果"的
    pri = sorted(mods, key=lambda m: (
        0 if re.search(r"(Main|Dichotomy|Hindman|SumProduct)", m) else 1,
        m))
    print(f"\n  模块 {len(mods)}，优先抓前 {min(len(pri), 60)} 个")

    hits = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for m, t in ex.map(fetch, pri[:60]):
            if not t:
                continue
            for mm in KEY.finditer(t):
                # 取该声明的完整陈述（到 `:= by` 或 `:=` 前）
                a = mm.start()
                seg = t[a:a + 1500]
                cut = re.search(r":=\s*(?:by|\n)", seg)
                stmt = seg[:cut.start()] if cut else seg[:700]
                hits.append({"module": m, "name": mm.group(1),
                             "stmt": re.sub(r"\s+", " ", stmt)[:700]})
                break
            if len(hits) >= 40:
                break

    print(f"\n  抓到 {len(hits)} 条候选定理")
    # 去重（同名的取最短的，通常是陈述最干净的）
    by = {}
    for h in hits:
        k = h["name"]
        if k not in by or len(h["stmt"]) < len(by[k]["stmt"]):
            by[k] = h
    sel = list(by.values())
    sel.sort(key=lambda x: len(x["stmt"]))
    print(f"\n  == 候选定理陈述（短到长，前 12）==")
    for h in sel[:12]:
        print(f"\n  ── {h['module'].split('.')[-1]} :: {h['name']}")
        print(f"     {h['stmt'][:400]}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(sel, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
