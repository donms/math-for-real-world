#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W52 · `SumProduct` 对应哪篇论文？（**读源码的模块 docstring，不猜**）

## 线索

`OAI.Combinatorics.SumProduct.Alignment.*` 的源码里出现了：

* namespace `TorusLeibman`（**Leibman** 是幂零群动力系统的学者）
* `polynomialOrbit : (ι → Polynomial ℝ) → ℕ → UnitAddTorus ι`
* `IntegerHyperplane` / `splitCoordinates`
* `open AlignmentScales RationalPivotPlan`
* `import OAI.Geometry.NilpotentCharts.Main`

⇒ 内容像是"**多项式在环面上的轨道**"与"**整数超平面**"，
   而不是"和积问题"的字面意思。

## 做法

1. 取 `SumProduct` 里**带 docstring 的模块**（`/-! … -/` 块）；
2. 找 `CONTENTS.md` 里的相关结果描述；
3. 三者对齐。

用法：
    $PY q11_sumproduct_paper.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from load_imports import find_imports                           # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from net_resolve import open_url                                   # noqa: E402

SRC = find_imports(ROOT)
OUT = ROOT / "episodes" / "2026-W52" / "results" / "q11_SumProduct论文.json"
PREFIX = "OAI.Combinatorics.SumProduct"


def main() -> int:
    print("=" * 96)
    print("  W52 · SumProduct 对应哪篇论文")
    print("=" * 96)

    mods = []
    with SRC.open(encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            m = re.sub(r"^lean\.", "", d.get("mod", ""))
            if m.startswith(PREFIX):
                mods.append(m)
    mods.sort()
    print(f"\n  SumProduct 模块 {len(mods)}")

    # ---- 1. 找带 docstring（/-! … -/）的模块 ----
    print(f"\n  == 抓取模块级 docstring（前 1200 字符）==")
    found = []
    for m in mods:
        # 优先取"看起来像主模块"的
        leaf = m.split(".")[-1]
        if leaf not in ("Main", "Alignment", "Basic", "AllLevel01",
                        "AbelianMalcev01", "Admissible01", "Intro",
                        "Overview") and not leaf.endswith("Main"):
            continue
        url = ("https://raw.githubusercontent.com/openai/math/main/lean/"
               + m.replace(".", "/") + ".lean")
        try:
            t = open_url(url, timeout=60, tries=2).read().decode("utf-8",
                                                                 "ignore")
        except Exception:                                            # noqa: BLE001
            continue
        # 抓 /-! … -/ 块
        blocks = re.findall(r"/-!(.*?)-/", t, re.S)
        if not blocks:
            continue
        txt = "\n".join(blocks)[:1200]
        found.append({"module": m, "doc": txt})
        print(f"\n  ── {m}")
        for ln_ in txt.splitlines()[:22]:
            print(f"     {ln_.strip()[:104]}")

    if not found:
        print("     （没抓到模块级 docstring，试全部模块）")
        for m in mods[:40]:
            url = ("https://raw.githubusercontent.com/openai/math/main/lean/"
                   + m.replace(".", "/") + ".lean")
            try:
                t = open_url(url, timeout=45, tries=1).read().decode(
                    "utf-8", "ignore")
            except Exception:                                        # noqa: BLE001
                continue
            blocks = re.findall(r"/-!(.*?)-/", t, re.S)
            if blocks:
                print(f"\n  ── {m}")
                for ln_ in "\n".join(blocks)[:900].splitlines()[:18]:
                    print(f"     {ln_.strip()[:104]}")
                found.append({"module": m,
                              "doc": "\n".join(blocks)[:900]})
                if len(found) >= 4:
                    break

    # ---- 2. CONTENTS.md 里找 ----
    print(f"\n  == CONTENTS.md 里找相关结果 ==")
    try:
        c = open_url("https://raw.githubusercontent.com/openai/math/main/"
                     "CONTENTS.md", timeout=180,
                     tries=3).read().decode("utf-8", "ignore")
        res = re.findall(r"\*\*(\d{3})\.\s*(.+?)\*\*", c)
        for kw in ("nilpotent", "torus", "Leibman", "polynomial orbit",
                   "Weyl", "alignment", "sum-product", "sums and products"):
            hit = [(n, t) for n, t in res if kw.lower() in t.lower()]
            if hit:
                print(f"\n     「{kw}」命中 {len(hit)}:")
                for n, t in hit[:5]:
                    print(f"        [{n}] {t[:118]}")
    except Exception as e:                                           # noqa: BLE001
        print(f"     [X] {type(e).__name__}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"n_mods": len(mods), "docs": found},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
