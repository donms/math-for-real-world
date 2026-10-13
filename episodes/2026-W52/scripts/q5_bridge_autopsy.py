#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W52 题 A · **桥梁案例解剖**：903 条跨科跨族边，究竟是不是真桥梁？

## 为什么要做这一步

问 4 的结论"只有 0.44% 是跨科跨族的桥梁"依赖一个隐含假设：

> 学科目录的差异 = 数学内容上的跨领域借用。

**这个假设必须验证。** 可能的反例：

| 反例 | 表现 | 若是这样，结论怎么变 |
|---|---|---|
| **共享基础设施** | 被引模块叫 `Basic` / `Defs` / `Prelude` | 不算桥梁，结论**更强** |
| **组织错位** | 模块只是被**放错目录**了 | 桥梁数被**高估** |
| **真借用** | 被引模块名含**具体数学对象**（如 `ModularForm`）| 真桥梁，结论站得住 |

## 判据：**看被引模块的名字**

模块名是**最强的免费证据** —— 它直接告诉你在借用什么：

* `OAI.<学科>.<族>.Basic` / `.Defs` / `.Prelude`
  ⇒ **基础设施**（不是数学内容）
* `OAI.<学科>.<族>.<具体定理名>`
  ⇒ **具体结果**（可能是真桥梁）

## 本脚本

1. 把 903 条边按**被引模块名的"通用性"**分层；
2. 列出 Top 被引的**具体模块**（不是学科对）；
3. 抽出 **10 条代表边**，附两端模块名，供人读源码复核。

用法：
    $PY q5_bridge_autopsy.py
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
OUTJ = ROOT / "episodes" / "2026-W52" / "results" / "q5_桥梁解剖.json"
OUTM = ROOT / "episodes" / "2026-W52" / "results" / "q5_桥梁解剖.md"

# "通用基础设施"模块名（借的是底座，不是数学内容）
GENERIC = {
    "Basic", "Defs", "Def", "Prelude", "Init", "Common", "Util", "Utils",
    "Helpers", "Helper", "Lemmas", "Lemma", "Aux", "Auxiliary", "Misc",
    "Notation", "Tactics", "Tactic", "Instances", "Instance", "Classes",
    "Class", "API", "Core", "Main", "All", "Extra", "More", "ExtraLemmas",
}


def parse(mod: str):
    m = re.sub(r"^lean\.", "", mod)
    if not m.startswith("OAI."):
        return None
    p = m.split(".")
    return (p[1], p[2], p[-1]) if len(p) >= 4 else (p[1], p[2], "") if len(p) >= 3 else None


def main() -> int:
    print("=" * 96)
    print("  W52 题 A · 桥梁案例解剖")
    print("=" * 96)

    mod2dc: dict[str, tuple[str, str, str]] = {}
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

    # ---- 跨科跨族边 ----
    cross = []
    for m, ds in deps.items():
        d1, f1, _l1 = mod2dc[m]
        for dp in ds:
            if dp not in mod2dc:
                continue
            d2, f2, l2 = mod2dc[dp]
            if d1 != d2 and f1 != f2:
                cross.append((m, dp, d1, d2, f1, f2, l2))
    print(f"\n  跨科跨族边：{len(cross)}")

    # ---- 按被引模块名的"通用性"分层 ----
    layer = Counter()
    for _m, _dp, _d1, _d2, _f1, _f2, leaf in cross:
        layer["generic" if leaf in GENERIC else "specific"] += 1
    tot = len(cross)
    print(f"\n  == 按被引模块名分层 ==")
    print(f"     通用基础设施（Basic/Defs/…）：{layer['generic']}"
          f"  ({layer['generic']/tot*100:.1f}%)")
    print(f"     具体模块（含具体数学对象）：{layer['specific']}"
          f"  ({layer['specific']/tot*100:.1f}%)")

    # ---- 最常被引的**具体模块** ----
    tgt = Counter(dp for _m, dp, *_r in cross)
    print(f"\n  == 被引最多的具体目标模块（Top 16）==")
    print(f"     {'模块':<58}{'次数':>5}  通用?")
    for dp, v in tgt.most_common(16):
        leaf = dp.split(".")[-1]
        g = "通用" if leaf in GENERIC else "具体"
        print(f"     {dp[:56]:<58}{v:>5}  {g}")

    # ---- 被引族（跨科）的分布 ----
    fam_t = Counter(f"{d2}/{f2}" for _m, _dp, _d1, d2, _f1, f2, _l in cross)
    print(f"\n  == 被引的『跨学科目标族』Top 12 ==")
    for k, v in fam_t.most_common(12):
        print(f"     {k[:60]:<62}{v:>5}")

    # ---- 抽 10 条代表边（优先"具体模块"）----
    spec = [c for c in cross if c[6] not in GENERIC]
    spec.sort(key=lambda c: -len(c[1]))
    print(f"\n  == 代表边抽样（具体模块，供读源码复核）==")
    for i, (m, dp, d1, d2, f1, f2, leaf) in enumerate(spec[:10], 1):
        print(f"\n     [{i}] {d1}/{f1}  ->  {d2}/{f2}")
        print(f"         引用方: {m}")
        print(f"         被引用: {dp}")

    OUTJ.parent.mkdir(parents=True, exist_ok=True)
    OUTJ.write_text(json.dumps({
        "n_cross": tot, "layers": dict(layer),
        "top_targets": [[k, v] for k, v in tgt.most_common(40)],
        "top_fams": [[k, v] for k, v in fam_t.most_common(30)],
        "samples": [{"from": m, "to": dp, "d1": d1, "d2": d2,
                     "f1": f1, "f2": f2} for m, dp, d1, d2, f1, f2, _l
                    in spec[:10]],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    L = ["# W52 · 题 A：桥梁案例解剖", "",
         f"跨科跨族边共 **{tot}** 条。", "",
         "## 一、按被引模块名分层（**名字就是证据**）", "",
         "| 层次 | 边数 | 占比 | 是否算桥梁 |", "|---|---|---|---|",
         f"| 通用基础设施（`Basic`/`Defs`/…）| {layer['generic']} | "
         f"{layer['generic']/tot*100:.1f}% | **否 —— 借的是底座** |",
         f"| 具体模块（含具体数学对象）| {layer['specific']} | "
         f"{layer['specific']/tot*100:.1f}% | 可能是真桥梁 |", "",
         "## 二、被引最多的目标模块", "",
         "| 模块 | 次数 | 通用? |", "|---|---|---|"]
    for dp, v in tgt.most_common(16):
        leaf = dp.split(".")[-1]
        L.append(f"| `{dp}` | {v} | "
                 f"{'通用' if leaf in GENERIC else '具体'} |")
    L += ["", "## 三、代表边（供读源码复核）", ""]
    for i, (m, dp, d1, d2, f1, f2, _l) in enumerate(spec[:10], 1):
        L += [f"### 样本 {i}：`{d1}/{f1}` -> `{d2}/{f2}`", "",
              f"- **引用方**：`{m}`", f"- **被引用**：`{dp}`", ""]
    OUTM.write_text("\n".join(L), encoding="utf-8")
    print(f"\n  -> {OUTJ.relative_to(ROOT)}")
    print(f"  -> {OUTM.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
