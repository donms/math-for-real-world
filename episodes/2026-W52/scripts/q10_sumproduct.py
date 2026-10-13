#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W52 · 深挖 `Combinatorics.SumProduct`：**它到底是数学结果还是工具箱？**

## 为什么要查

`SumProduct` 是 903 条跨科跨族边里**最大的一对**的一半（263 条边，占 29%）。
但它的子模块名里出现了大量**通用词**：

    Alignment.AbelianMalcev01 / Admissible01 / AffineCoefficient01 /
    AffineOrbit01 / AlignmentMass01 / AllLevel01..08

而另一端的 `Geometry.NilpotentCharts` 是具体的数学对象
（`Adjoint` / `Filtrations` / `Exponential` / `CentralSubspaces`）。

**⇒ 两种可能，含义完全不同：**

| 可能 | 含义 | 对结论的影响 |
|---|---|---|
| **通用工具箱** | "和积问题"的工具被**别的领域借用** | 那 263 条边**不算数学桥梁** ⇒ 桥梁数进一步下降 |
| **一个具体研究项目** | 某个作者在做"幂零群上的和积" | 是真跨领域，但**只是一个项目** |

## 做法（**读源码，不猜名字**）

1. 列出 `SumProduct` 的**全部模块与子族**；
2. 取 **5 个代表模块的源码头部**（docstring 会说明它在做什么数学）；
3. 查它 **import 了哪些外部库与哪些 OAI 族**；
4. 查它在 `preprints/` / `CONTENTS.md` 里对应哪篇论文。

用法：
    $PY q10_sumproduct.py
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

sys.path.insert(0, str(ROOT / "scripts"))
from net_resolve import open_url                                   # noqa: E402

SRC = find_imports(ROOT)
OUT = ROOT / "episodes" / "2026-W52" / "results" / "q10_SumProduct.json"
PREFIX = "OAI.Combinatorics.SumProduct"


def main() -> int:
    print("=" * 96)
    print("  W52 · 深挖 Combinatorics.SumProduct")
    print("=" * 96)

    # ---- 1. 模块清单与子族 ----
    mods = []
    deps: dict[str, list[str]] = {}
    with SRC.open(encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            m = re.sub(r"^lean\.", "", d.get("mod", ""))
            if not m.startswith(PREFIX):
                continue
            mods.append(m)
            deps[m] = [re.sub(r"^lean\.", "", str(x))
                       for x in (d.get("deps") or [])]
    print(f"\n  模块数：{len(mods)}")

    sub = Counter(m[len(PREFIX) + 1:].split(".")[0]
                  for m in mods if len(m) > len(PREFIX) + 1)
    print(f"  子族（{len(sub)} 个）：")
    for k, v in sub.most_common():
        print(f"     {k:<34}{v:>4}")

    # ---- 2. 它依赖哪些外部库 / 哪些 OAI 族 ----
    ext = Counter()
    oai_targets = Counter()
    for m in mods:
        for dp in deps[m]:
            if dp.startswith("OAI."):
                p = dp.split(".")
                if len(p) >= 3:
                    oai_targets[f"{p[1]}.{p[2]}"] += 1
            else:
                ext[dp.split(".")[0]] += 1
    print(f"\n  == 依赖的外部库（Top 10）==")
    for k, v in ext.most_common(10):
        print(f"     {k:<34}{v:>6}")
    print(f"\n  == 依赖的 OAI 族（Top 10）==")
    for k, v in oai_targets.most_common(10):
        print(f"     {k:<44}{v:>6}")

    # ---- 3. 读 5 个代表模块的源码头部 ----
    print(f"\n  == 代表模块的源码头部（docstring 会说明在做什么数学）==")
    picks = []
    for want in ("Alignment.AllLevel01", "Alignment.Admissible01",
                 "Alignment.AffineOrbit01", ""):
        for m in mods:
            if want and m.endswith(want):
                picks.append(m)
                break
        if not want:
            picks.append(sorted(mods)[0])
    seen = set()
    heads = []
    for m in picks:
        if m in seen:
            continue
        seen.add(m)
        url = ("https://raw.githubusercontent.com/openai/math/main/lean/"
               + m.replace(".", "/") + ".lean")
        try:
            t = open_url(url, timeout=60, tries=2).read().decode("utf-8",
                                                                 "ignore")
        except Exception as e:                                       # noqa: BLE001
            print(f"\n  [{m}]\n     [X] {type(e).__name__}")
            continue
        head = t[:1400]
        heads.append({"module": m, "head": head, "chars": len(t)})
        print(f"\n  ── {m}  （{len(t)} 字符）")
        for ln_ in head.splitlines()[:26]:
            print(f"     {ln_[:104]}")

    # ---- 4. 它对应哪篇论文 ----
    print(f"\n  == 在 preprints/ 里找对应论文 ==")
    try:
        d = json.loads(open_url(
            "https://api.github.com/repos/openai/math/contents/preprints",
            timeout=120, tries=3).read().decode("utf-8", "ignore"))
        names = [it["name"] for it in d if it["type"] == "dir"]
        for kw in ("Sum-Product", "SumProduct", "sum-product", "Nilpotent",
                   "Alignment"):
            hit = [n for n in names if kw.lower() in n.lower()]
            if hit:
                print(f"     「{kw}」命中 {len(hit)}:")
                for h in hit[:6]:
                    print(f"        {h}")
    except Exception as e:                                           # noqa: BLE001
        print(f"     [X] {type(e).__name__}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "n_mods": len(mods), "subfamilies": dict(sub),
        "ext_libs": dict(ext), "oai_targets": dict(oai_targets),
        "heads": heads,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
