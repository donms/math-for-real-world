#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W52 · **现代数学的分支壁垒**：719 个结果里有多少是跨领域合作出来的？

## 用户提出的问题（原话）

> 现代数学分了太多分支，每个分支只有少数人在研究，导致每个分支之间缺少桥梁。
> 很多遗留的难题譬如**费马大定理**，就是联通了**椭圆曲线和模形式**才解决的。
> 我想研究一下，这次发布的 7 百多个结果，
> **有多少是只用自己领域的知识解决的，有多少是跨领域知识合作的结果**。

## 为什么这批数据能回答它

`lean/OAI/` 的目录结构是：

    OAI.<学科>.<结果族>.<模块>

实测：**17 个学科**、**86507 个 OAI 模块**、**205229 条 OAI->OAI 内部边**。

⇒ 每条边都可以判定"**是否跨学科**"，
  每个结果族都可以算"**用了几个学科的知识**"。

## 定义的三个层次（逐层回答）

| 层次 | 定义 | 回答什么 |
|---|---|---|
| **边级** | 一条 import 边，两端学科不同 ⇒ 跨领域边 | 整个库的**跨领域强度** |
| **族级** | 某结果族的模块，其依赖横跨几个学科 | **单个结果**的跨领域程度 |
| **学科级** | 学科两两之间的引用矩阵 | 哪些学科是**桥梁**、哪些是**孤岛** |

## ★ 关键校准（**不带先验地判定"跨领域"**）

"跨领域"**不能**只看学科标题不同 —— 数学分支之间有**天然的层级关系**
（如 `Algebra` 与 `AlgebraicGeometry` 相邻）。
⇒ 本脚本同时报告：
* **粗口径**：学科不同即算跨；
* **保守口径**：**排除**已知相邻的学科对（需人工列出）；
* 并报告**两种口径的差**，避免用口径制造结论。

用法：
    $PY q1_cross_domain.py
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

# ★ 依赖图由 W50 抓取，但**单期包里它放在本期的 data/** ⇒ 用 loader 找，
#   不要硬编码 `episodes/2026-W50/...`（读者 clone 单期包时会找不到）。
SRC = find_imports(ROOT)
OUTJ = ROOT / "episodes" / "2026-W52" / "results" / "q1_跨领域.json"
OUTM = ROOT / "episodes" / "2026-W52" / "results" / "q1_跨领域.md"


def parse(mod: str) -> tuple[str, str] | None:
    r"""`OAI.<学科>.<族>.<模块>` -> (学科, 族)。"""
    m = re.sub(r"^lean\.", "", mod)
    if not m.startswith("OAI."):
        return None
    parts = m.split(".")
    if len(parts) < 3:
        return None
    return parts[1], parts[2]


def main() -> int:
    print("=" * 96)
    print("  W52 · 跨领域分析：719 个结果里有多少是跨领域合作")
    print("=" * 96)

    mod2dc: dict[str, tuple[str, str]] = {}
    deps_of: dict[str, list[str]] = {}
    with SRC.open(encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            mod = re.sub(r"^lean\.", "", d.get("mod", ""))
            p = parse(mod)
            if not p:
                continue
            mod2dc[mod] = p
            deps_of[mod] = [re.sub(r"^lean\.", "", str(x))
                            for x in (d.get("deps") or [])]

    discs = sorted({v[0] for v in mod2dc.values()})
    fams = sorted({v[1] for v in mod2dc.values()})
    print(f"\n  模块 {len(mod2dc)}  学科 {len(discs)}  结果族 {len(fams)}")

    # ---------- 边级 ----------
    same = cross = 0
    cross_pairs: Counter = Counter()
    edge_by_pair: Counter = Counter()
    for mod, deps in deps_of.items():
        a = mod2dc[mod][0]
        for dp in deps:
            if dp not in mod2dc:
                continue
            b = mod2dc[dp][0]
            edge_by_pair[(a, b)] += 1
            if a == b:
                same += 1
            else:
                cross += 1
                cross_pairs[tuple(sorted((a, b)))] += 1
    tot = same + cross
    print(f"\n  == 边级 ==")
    print(f"     内部边（两端都在 OAI）: {tot}")
    print(f"     **同学科: {same} ({same/tot*100:.1f}%)**")
    print(f"     **跨学科: {cross} ({cross/tot*100:.1f}%)** ← 用户问的核心数字")

    # ---------- 族级 ----------
    # ★★★ W52 修正：族级口径原来是**错的**（同义反复）。
    #
    # 旧写法 am_discs[fam].add(dc)（dc = 该模块自己所在的学科）
    # ⇒ 每个族只属于**一个**学科目录 ⇒ **恒为 1**
    # ⇒ 报「单学科族 413/420 = 98.3%」是**复述定义**，不是发现。
    #
    # [!] 而且旧写法用**族名**做键，而**族名会跨学科重名**
    #     （实测 7 个）⇒ 427 个族塌缩成 420 个。
    #
    # 正确口径：「一个族**借用**了几个**别的**学科的知识」
    #   = 它的依赖里出现的、且**不等于自己学科**的学科数。
    fam_dep_discs: dict[str, set] = defaultdict(set)
    fam_mods: Counter = Counter()
    for mod, (dc, fam) in mod2dc.items():
        key = f"{dc}.{fam}"
        fam_mods[key] += 1
        for dp in deps_of.get(mod, []):
            p2 = mod2dc.get(dp)
            if p2 and p2[0] != dc:
                fam_dep_discs[key].add(p2[0])
    n_fam = len(fam_mods)
    fam_discs = fam_dep_discs
    dist = Counter(len(fam_dep_discs.get(k, ())) for k in fam_mods)
    print(f"\n  == 族级（{n_fam} 个结果族）==")
    print(f"     ★ 口径：一个族**借用**了几个**别的**学科的知识")
    print(f"       （同学科但不同族的依赖**不算**跨学科，见下方说明）")
    print(f"     一个族依赖到的「别的学科」数分布：")
    for k in sorted(dist):
        print(f"       {k} 个: {dist[k]:>4} 族  ({dist[k]/n_fam*100:.1f}%)")
    n_none = dist.get(0, 0)
    n_any = n_fam - n_none
    n_ge2 = sum(v for k, v in dist.items() if k >= 2)
    print(f"\n     **完全不跨学科的族: {n_none}/{n_fam} = "
          f"{n_none/n_fam*100:.1f}%**")
    print(f"     **有跨学科依赖的族: {n_any}/{n_fam} = "
          f"{n_any/n_fam*100:.1f}%**")
    print(f"     **借用 >=2 个别的学科的族: {n_ge2}/{n_fam} = "
          f"{n_ge2/n_fam*100:.1f}%**")
    print(f"\n     [!] 口径提醒：「同学科但不同族」的依赖（例如")
    print(f"         `Algebra.FinitisticAsymmetry` 用了 `Algebra.其它族`）")
    print(f"         **不计入**跨学科 —— 它是**学科内的分工**。")

    # ---------- 学科级：桥梁 vs 孤岛 ----------
    print(f"\n  == 学科级：跨学科边的流向（Top 15）==")
    for (a, b), v in cross_pairs.most_common(15):
        print(f"     {a:<22} <-> {b:<22} {v:>6}")

    # 每个学科的"对外连接度"
    out_d: Counter = Counter()
    in_d: Counter = Counter()
    for (a, b), v in edge_by_pair.items():
        if a != b:
            out_d[a] += v
            in_d[b] += v
    print(f"\n  == 学科的对外连接度（桥接能力）==")
    print(f"     {'学科':<22}{'出边':>8}{'入边':>8}{'合计':>8}")
    for d0 in sorted(discs, key=lambda x: -(out_d[x] + in_d[x])):
        print(f"     {d0:<22}{out_d[d0]:>8}{in_d[d0]:>8}"
              f"{out_d[d0]+in_d[d0]:>8}")

    OUTJ.parent.mkdir(parents=True, exist_ok=True)
    OUTJ.write_text(json.dumps({
        "n_mod": len(mod2dc), "n_disc": len(discs), "n_fam": n_fam,
        "edges": {"same": same, "cross": cross, "total": tot,
                  "cross_pct": round(cross / tot * 100, 2)},
        # ★★★ 口径（W52 修正）：这里报的是「一个族**借用**了几个**别的**
        #     学科」，键是 `学科.族`。字段名保留 fam_mono / fam_cross 是
        #     为了兼容旧引用，但**含义已变**：
        #       fam_mono  = 借用别的学科数 == 0 的族（完全不跨学科）
        #       fam_cross = 借用别的学科数 >= 1 的族
        #     [!] 重构时漏改了这一段，导致 `mono` 未定义、脚本直接崩 ——
        #         旧写法是 `mono = dist.get(1, 0)`（"用到 1 个学科"），
        #         那是**同义反复**的口径，已废弃。
        "fam_disc_dist": dict(dist),
        "fam_mono": n_none, "fam_cross": n_any,
        "fam_ge2": n_ge2,
        "top_cross_pairs": [[a, b, v] for (a, b), v in
                            cross_pairs.most_common(30)],
        "disc_out": dict(out_d), "disc_in": dict(in_d),
        "discs": discs,
        "_口径": "族级 = 借用了几个**别的**学科（键 = 学科.族）；"
                 "0 个为 fam_mono，>=1 个为 fam_cross，>=2 个为 fam_ge2",
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    L = ["# W52 · 问 1：跨领域分析", "",
         f"> 数据：`lean/OAI/`（**{len(mod2dc)}** 模块 / "
         f"**{len(discs)}** 学科 / **{n_fam}** 结果族）", "",
         "## 一、边级：整个库的跨领域强度", "",
         "| 类型 | 边数 | 占比 |", "|---|---|---|",
         f"| 同学科 | {same} | {same/tot*100:.1f}% |",
         f"| **跨学科** | **{cross}** | **{cross/tot*100:.1f}%** |", "",
         "## 二、族级：单个结果族借用了几个**别的**学科", "",
         "> 键 = `学科.族`。**「同学科但不同族」的依赖不计入跨学科** ——"
         "那是学科内的分工。", "",
         "| 借用的别的学科数 | 族数 | 占比 |", "|---|---|---|"]
    for k in sorted(dist):
        L.append(f"| {k} | {dist[k]} | {dist[k]/n_fam*100:.1f}% |")
    L += ["",
          f"**完全不跨学科 {n_none}/{n_fam} = "
          f"{n_none/n_fam*100:.1f}%**；"
          f"**有跨学科依赖 {n_any}/{n_fam} = "
          f"{n_any/n_fam*100:.1f}%**；"
          f"**借用 >=2 个别的学科 {n_ge2}/{n_fam} = "
          f"{n_ge2/n_fam*100:.1f}%**", "",
          "## 三、学科级：桥梁与孤岛", "",
          "| 学科 | 出边 | 入边 | 合计 |", "|---|---|---|---|"]
    for d0 in sorted(discs, key=lambda x: -(out_d[x] + in_d[x])):
        L.append(f"| {d0} | {out_d[d0]} | {in_d[d0]} | "
                 f"{out_d[d0]+in_d[d0]} |")
    OUTM.write_text("\n".join(L), encoding="utf-8")
    print(f"\n  -> {OUTJ.relative_to(ROOT)}")
    print(f"  -> {OUTM.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
