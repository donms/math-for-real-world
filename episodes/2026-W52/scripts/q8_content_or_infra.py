#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W52 题 A 第 4 层 · 那 317 个"公共接口"是**数学内容**还是**基础设施**？

## 为什么这是最后一层、也是最关键的一层

前三层已确认：

1. **903** 条跨科跨族边（占内部边 0.44%）；
2. 它们**不是** `Basic`/`Defs` 这类显式基础设施（第 1 层）；
3. 被跨学科引用的 **317** 个模块**全部**被 ≥2 个学科共用（第 3 层）。

**但模块名里出现了 `Orthonormal` / `Tuples` / `Tape` / `Model` /
`Machines` / `Checkpoints` / `Rules`** —— 这些**看着像基础设施**。

⇒ 必须量化：**317 个"公共接口"里，多少是数学内容、多少是数据结构**？

**这个比例直接决定结论怎么写**：

| 若基础设施占多数 | 若数学内容占多数 |
|---|---|
| ⇒ 跨学科流动**大多在搬运数据结构**， | ⇒ 存在**实质的数学知识跨域借用**， |
| **不是**在搬定理 | 但与"费马大定理式"仍不同 |

## 判据：**名字分类**（可复核、可自证）

| 类 | 特征词（后缀/全名）| 含义 |
|---|---|---|
| **基础设施** | `Basic` `Defs` `Prelude` `Model` `Tape` `Stacks` `Machines` `Rules` `Checkpoints` `Tuples` `Config` `State` `Encoding` | 数据结构 / 机器 / 定义 |
| **数学内容** | 其余（含**具体数学对象或定理**名）| 数学结论 |

**自证要求**：列出两类各自的实例，供人核对该判断是否合理。

用法：
    $PY q8_content_or_infra.py
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

SRC = find_imports(ROOT)
OUTJ = ROOT / "episodes" / "2026-W52" / "results" / "q8_内容与基础设施.json"
OUTM = ROOT / "episodes" / "2026-W52" / "results" / "q8_内容与基础设施.md"

# 基础设施特征词（**按全名精确匹配**，避免"含 basic 就算是"的误判）
INFRA_EXACT = {
    "Basic", "Defs", "Def", "Prelude", "Init", "Common", "Util", "Utils",
    "Helpers", "Helper", "Lemmas", "Aux", "Misc", "Notation", "Tactics",
    "Instances", "Classes", "Class", "Core", "All", "Extra", "More",
    "Model", "Models", "Tape", "Tapes", "Stacks", "Stack", "Machines",
    "Machine", "Rules", "Rule", "Checkpoints", "Checkpoint", "Tuples",
    "Tuple", "Config", "Configs", "Configuration", "State", "States",
    "Encoding", "Encode", "Decode", "Syntax", "Semantics", "Types",
    "Type", "Structure", "Structures", "Ops", "Operations", "API",
    "Interface", "Interfaces", "Spec", "Specs", "Signature", "Signatures",
    "Schema", "Schemas", "Format", "Formats", "Labels", "Label",
    "Indices", "Index", "Bounds", "Range", "Ranges", "Sizes", "Size",
    "List", "Lists", "Map", "Maps", "Set", "Sets", "Finset", "Finsets",
}


def key3(mod: str):
    m = re.sub(r"^lean\.", "", mod)
    if not m.startswith("OAI."):
        return None
    p = m.split(".")
    return f"{p[1]}.{p[2]}" if len(p) >= 3 else None


def main() -> int:
    print("=" * 96)
    print("  W52 题 A 第 4 层 · 317 个公共接口：数学内容 还是 基础设施？")
    print("=" * 96)

    key_of: dict[str, str] = {}
    users: dict[str, set] = {}
    with SRC.open(encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            m = re.sub(r"^lean\.", "", d.get("mod", ""))
            k = key3(m)
            if not k:
                continue
            key_of[m] = k
            for x in (d.get("deps") or []):
                dp = re.sub(r"^lean\.", "", str(x))
                users.setdefault(dp, set()).add(k)

    cross = []
    for dp, us in users.items():
        if dp not in key_of:
            continue
        discs = {u.split(".", 1)[0] for u in us}
        if len(discs) >= 2:
            cross.append((dp, us, discs))

    print(f"\n  被跨学科引用的模块：{len(cross)}")

    infra, content = [], []
    for dp, us, discs in cross:
        leaf = dp.split(".")[-1]
        (infra if leaf in INFRA_EXACT else content).append((dp, len(us), discs))

    n = len(cross)
    print(f"\n  == ★ 分类结果 ==")
    print(f"     **基础设施**（数据结构/机器/定义）：{len(infra)}"
          f"  ({len(infra)/n*100:.1f}%)")
    print(f"     **数学内容**（具体数学对象/定理）：{len(content)}"
          f"  ({len(content)/n*100:.1f}%)")

    print(f"\n  == 基础设施实例（全部 {len(infra)} 个，列出）==")
    for dp, nu, discs in sorted(infra, key=lambda x: -x[1]):
        print(f"     {dp[:60]:<62} 用户{nu}  {'/'.join(sorted(discs))[:30]}")

    print(f"\n  == 数学内容实例（Top 20，按用户数）==")
    for dp, nu, discs in sorted(content, key=lambda x: -x[1])[:20]:
        print(f"     {dp[:60]:<62} 用户{nu}  {'/'.join(sorted(discs))[:30]}")

    OUTJ.parent.mkdir(parents=True, exist_ok=True)
    OUTJ.write_text(json.dumps({
        "n_cross": n, "n_infra": len(infra), "n_content": len(content),
        "infra": [{"m": d, "users": u, "discs": sorted(s)}
                  for d, u, s in sorted(infra, key=lambda x: -x[1])],
        "content_top": [{"m": d, "users": u, "discs": sorted(s)}
                        for d, u, s in sorted(content,
                                              key=lambda x: -x[1])[:60]],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    L = ["# W52 · 题 A 第 4 层：数学内容 vs 基础设施", "",
         f"被跨学科引用的模块 **{n}** 个。", "",
         "## 分类结果", "",
         "| 类型 | 模块数 | 占比 |", "|---|---|---|",
         f"| **基础设施**（数据结构/机器/定义）| {len(infra)} | "
         f"{len(infra)/n*100:.1f}% |",
         f"| **数学内容**（具体数学对象/定理）| {len(content)} | "
         f"{len(content)/n*100:.1f}% |", "",
         "## 基础设施实例（全部）", "",
         "| 模块 | 用户数 | 学科 |", "|---|---|---|"]
    for d, u, s in sorted(infra, key=lambda x: -x[1]):
        L.append(f"| `{d}` | {u} | {'/'.join(sorted(s))} |")
    L += ["", "## 数学内容实例（Top 20）", "",
          "| 模块 | 用户数 | 学科 |", "|---|---|---|"]
    for d, u, s in sorted(content, key=lambda x: -x[1])[:20]:
        L.append(f"| `{d}` | {u} | {'/'.join(sorted(s))} |")
    OUTM.write_text("\n".join(L), encoding="utf-8")
    print(f"\n  -> {OUTJ.relative_to(ROOT)}")
    print(f"  -> {OUTM.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
