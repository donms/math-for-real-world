#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W52 题 A 第 3 层（v2）· 跨学科被引模块：**专用还是共用**。

## v1 的两个问题（**记录以免重犯**）

| # | 问题 | 实情 |
|---|---|---|
| 1 | 我用「**族名**」当用户标识，而族名会**跨学科重名** | 实测约 700 个名字碰撞（如 `BooneHigman` 在 `GroupTheory` 与 `Computability` 下都有）|
| 2 | v1 的 `users` 键是**族名**而非 `(学科,族)` | 会把"两个不同学科的同名族"误并成一个用户 |

**v2 修法**：用户标识统一用 **`<学科>.<族>`**（即模块路径的前三段），
并**显式统计碰撞数**作为数据质量指标。

## 关键概念

被跨学科引用的模块，其「用户」有两种形态：

* **专用**：只被**一个** `(学科,族)` 用 ⇒ 是**一个项目的内部工具**；
* **共用**：被 **≥2 个** `(学科,族)` 用 ⇒ 是**公共接口**。

**且共用里要再分**：
* 被 ≥2 个**学科**的族共用 ⇒ **真正跨学科的公共接口**（费马大定理式）。

用法：
    $PY q7_shared_or_private.py
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
OUTJ = ROOT / "episodes" / "2026-W52" / "results" / "q7_专用与共用.json"
OUTM = ROOT / "episodes" / "2026-W52" / "results" / "q7_专用与共用.md"


def key3(mod: str) -> str | None:
    r"""`OAI.<学科>.<族>.<...>` -> `学科.族`（**唯一**的用户标识）。"""
    m = re.sub(r"^lean\.", "", mod)
    if not m.startswith("OAI."):
        return None
    p = m.split(".")
    return f"{p[1]}.{p[2]}" if len(p) >= 3 else None


def main() -> int:
    print("=" * 96)
    print("  W52 题 A 第 3 层 v2 · 跨学科被引模块：专用还是共用？")
    print("=" * 96)

    key_of: dict[str, str] = {}                      # 模块 -> 学科.族
    users: dict[str, set] = defaultdict(set)         # 被引模块 -> 用户集合
    fam_names: dict[str, set] = defaultdict(set)     # 族名 -> 学科集合
    with SRC.open(encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            k = key3(d.get("mod", ""))
            if not k:
                continue
            key_of[re.sub(r"^lean\.", "", d["mod"])] = k
            disc, fam = k.split(".", 1)
            fam_names[fam].add(disc)
            for x in (d.get("deps") or []):
                dp = re.sub(r"^lean\.", "", str(x))
                users[dp].add(k)

    collide = {f: v for f, v in fam_names.items() if len(v) >= 2}
    print(f"\n  模块 {len(key_of)}；被引模块 {len(users)}")
    print(f"  ★ 族名跨学科重名：{len(collide)} 个"
          f"  ← v1 的计数偏差来源")

    rows = []
    for dp, us in users.items():
        if dp not in key_of:
            continue
        own = key_of[dp]
        ud = {u.split(".", 1)[0] for u in us}
        if len(ud) < 2:                              # 不被跨学科引用
            continue
        rows.append({"module": dp, "own": own, "n_users": len(us),
                     "n_discs": len(ud), "discs": sorted(ud)})

    print(f"\n  被**跨学科**引用的模块：{len(rows)}")
    if not rows:
        return 0

    dist = Counter(r["n_users"] for r in rows)
    print(f"\n  == 被多少个『学科.族』用户使用 ==")
    for k in sorted(dist):
        print(f"     {k:>2} 个用户: {dist[k]:>4} 个模块 "
              f"({dist[k]/len(rows)*100:>5.1f}%)")

    private = [r for r in rows if r["n_users"] == 1]
    shared = [r for r in rows if r["n_users"] >= 2]
    truly = [r for r in shared if r["n_discs"] >= 2]
    print(f"\n  == ★ 专用 vs 共用 ==")
    print(f"     **专用**（1 个用户，同一族内部）：{len(private)}"
          f"  ({len(private)/len(rows)*100:.1f}%)")
    print(f"     **共用**（>=2 个用户）：{len(shared)}"
          f"  ({len(shared)/len(rows)*100:.1f}%)")
    print(f"       其中被 >=2 个**学科**的用户共用：{len(truly)}"
          f"  ← **真正跨学科的公共接口**")

    print(f"\n  == 共用模块 Top 12 ==")
    print(f"     {'模块':<54}{'用户':>5}{'学科':>5}  学科")
    for r in sorted(shared, key=lambda x: -x["n_users"])[:12]:
        print(f"     {r['module'][:52]:<54}{r['n_users']:>5}{r['n_discs']:>5}"
              f"  {','.join(r['discs'])[:34]}")

    OUTJ.parent.mkdir(parents=True, exist_ok=True)
    OUTJ.write_text(json.dumps({
        "n_cross_cited": len(rows), "user_dist": dict(dist),
        "private": len(private), "shared": len(shared),
        "truly_shared": len(truly),
        "fam_name_collisions": len(collide),
        "top_shared": [{"module": r["module"], "users": r["n_users"],
                        "discs": r["discs"]}
                       for r in sorted(shared,
                                       key=lambda x: -x["n_users"])[:40]],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    L = ["# W52 · 题 A 第 3 层：专用 vs 共用（v2）", "",
         f"被**跨学科**引用的模块：**{len(rows)}** 个", "",
         f"> v1 把用户标识写成「族名」，而**族名会跨学科重名**",
         f"> （实测 **{len(collide)}** 个），故 v2 改用 `<学科>.<族>`。", "",
         "## 被多少个用户使用", "",
         "| 用户数（学科.族）| 模块数 | 占比 |", "|---|---|---|"]
    for k in sorted(dist):
        L.append(f"| {k} | {dist[k]} | {dist[k]/len(rows)*100:.1f}% |")
    L += ["", "## ★ 专用 vs 共用", "",
          "| 类型 | 模块数 | 占比 | 含义 |", "|---|---|---|---|",
          f"| **专用**（1 个用户）| {len(private)} | "
          f"{len(private)/len(rows)*100:.1f}% | 同一族内部工具 |",
          f"| **共用**（>=2 个用户）| {len(shared)} | "
          f"{len(shared)/len(rows)*100:.1f}% | 公共接口 |",
          f"| 其中被 >=2 个**学科**共用 | {len(truly)} | "
          f"{len(truly)/len(rows)*100:.1f}% | **真正跨学科的公共接口** |",
          "", "## 共用模块 Top 12", "",
          "| 模块 | 用户数 | 学科数 | 学科 |", "|---|---|---|---|"]
    for r in sorted(shared, key=lambda x: -x["n_users"])[:12]:
        L.append(f"| `{r['module']}` | {r['n_users']} | {r['n_discs']} | "
                 f"{', '.join(r['discs'])} |")
    OUTM.write_text("\n".join(L), encoding="utf-8")
    print(f"\n  -> {OUTJ.relative_to(ROOT)}")
    print(f"  -> {OUTM.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
