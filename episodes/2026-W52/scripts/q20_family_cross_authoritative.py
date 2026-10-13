#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W52 · **族级跨学科性的权威实现 v2**（第三次独立实现，用于定案）。

## 为什么要第三份

`q1` 的族级口径被我自己判为"同义反复"后改写，
结果与我的临时验算**不一致**（381 vs 372），而两者的**族集合完全相同**。
⇒ 说明差异在**代码路径**，不在定义。

**定义（唯一正确的那个）**：

> 一个族 $F$（键 = `学科.族`）的**跨学科借用集合**是
> $$\bigl\{\, d \;\bigm|\; \exists\, m \in F,\ \exists\, p \in \mathrm{deps}(m):\ d = \mathrm{disc}(p) \neq \mathrm{disc}(F) \,\bigr\}$$
> 即：**族里任一模块依赖到的、且学科不同于本族的**模块，其学科之集。

**关键点**：判据是 `disc(p) != disc(F)`，
**不是** `p 所在的族 != F` —— 后者会把"同学科跨族"也算进来。

## 本实现的特点（与 q1 不同，以便交叉验证）

* **两遍扫描**：第一遍只建 `模块 -> (学科,族)`，第二遍才处理依赖
  （q1 是单遍，`mod2dc` 在依赖被读到时可能还不完整）；
* **显式跳过未登记的模块**（`mod2dc` 里没有的依赖直接丢）；
* 并**同时输出两种口径**，便于核对差异来源。

用法：
    $PY q20_family_cross_authoritative.py
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
OUT = ROOT / "episodes" / "2026-W52" / "results" / "q20_族级跨学科.json"


def norm(x: str) -> str:
    return re.sub(r"^lean\.", "", str(x))


def main() -> int:
    print("=" * 96)
    print("  W52 · 族级跨学科性（第三份独立实现，定案）")
    print("=" * 96)

    # ---------- 第一遍：模块 -> (学科, 族) ----------
    mod2dc: dict[str, tuple[str, str]] = {}
    raw_deps: dict[str, list[str]] = {}
    with SRC.open(encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            m = norm(d.get("mod", ""))
            if not m.startswith("OAI."):
                continue
            p = m.split(".")
            if len(p) < 3:
                continue
            mod2dc[m] = (p[1], p[2])
            raw_deps[m] = [norm(x) for x in (d.get("deps") or [])]
    print(f"\n  登记的 OAI 模块：{len(mod2dc)}")

    # ---------- 第二遍：算族级跨学科集合 ----------
    fam_mods: Counter = Counter()
    # 口径 A：依赖到的**所有**学科（不限本族学科）—— 会把同学科跨族算进来
    fam_all_discs: dict[str, set] = defaultdict(set)
    # 口径 B：依赖到的、且**学科不同于本族**的学科 —— ★ 定义所在
    fam_other_discs: dict[str, set] = defaultdict(set)
    # 参考：依赖到的**别的族**（不限学科）—— q4 的"跨族"口径
    fam_other_fams: dict[str, set] = defaultdict(set)

    for m, ds in raw_deps.items():
        dc, fam = mod2dc[m]
        key = f"{dc}.{fam}"
        fam_mods[key] += 1
        for dp in ds:
            p2 = mod2dc.get(dp)
            if p2 is None:
                continue
            dc2, fam2 = p2
            key2 = f"{dc2}.{fam2}"
            if key2 == key:
                continue
            fam_all_discs[key].add(dc2)
            fam_other_fams[key].add(key2)
            if dc2 != dc:
                fam_other_discs[key].add(dc2)

    n = len(fam_mods)
    print(f"  结果族：{n}")
    for label, mp in (("A 依赖到的所有学科", fam_all_discs),
                      ("B 依赖到的**别的**学科（★ 定义）", fam_other_discs)):
        c = Counter(len(mp.get(k, ())) for k in fam_mods)
        nn = c.get(0, 0)
        print(f"\n  == {label} ==")
        for k in sorted(c):
            print(f"     {k} 个: {c[k]:>4} 族 ({c[k]/n*100:.1f}%)")
        print(f"     **完全不跨学科: {nn}/{n} = {nn/n*100:.1f}%**")
        print(f"     **有跨学科依赖: {n-nn}/{n} = {(n-nn)/n*100:.1f}%**")

    cB = Counter(len(fam_other_discs.get(k, ())) for k in fam_mods)
    n_none = cB.get(0, 0)
    n_ge1 = n - n_none
    n_ge2 = sum(v for k, v in cB.items() if k >= 2)
    cF = Counter(len(fam_other_fams.get(k, ())) for k in fam_mods)
    n_fam_none = cF.get(0, 0)

    print(f"\n  == ★ 定案数字（口径 B）==")
    print(f"     族总数                        : **{n}**")
    print(f"     完全不跨学科                  : **{n_none}**"
          f" ({n_none/n*100:.1f}%)")
    print(f"     有跨学科依赖（>=1 个别的学科）: **{n_ge1}**"
          f" ({n_ge1/n*100:.1f}%)")
    print(f"     借用 >=2 个别的学科           : **{n_ge2}**"
          f" ({n_ge2/n*100:.1f}%)")
    print(f"\n     参考（q4 的跨族口径）：完全没有跨族依赖的族 "
          f"**{n_fam_none}** ({n_fam_none/n*100:.1f}%)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "n_fam": n,
        "strict_other_disc_dist": dict(cB),
        "any_disc_dist": dict(Counter(len(fam_all_discs.get(k, ()))
                                      for k in fam_mods)),
        "cross_fam_dist": dict(cF),
        "n_none": n_none, "n_ge1": n_ge1, "n_ge2": n_ge2,
        "n_fam_none": n_fam_none,
        "_定义": "族 F 的跨学科借用集合 = {disc(p) | p in deps(m), m in F, "
                 "disc(p) != disc(F)}",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
