#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W52 · **跨学科结果的"含金量"**：用可观测代理指标做对照检验。

## 用户的问题

> 「我还想了解一下这七百多个结果里，**跨学科的结果的含金量如何**」

## ⚠️ 先说清楚：什么叫"含金量"

"含金量"**不是一个可以直接测量的量**。本脚本**不评价数学价值**
（那需要领域专家），而是用**四个可观测的代理指标**做**组间对照**：

| # | 代理指标 | 数据来源 | 含义 |
|---|---|---|---|
| **1** | **有没有被形式化** | `formalization.yaml` 的 173 条 `sources` | 团队是否认为它值得投入形式化成本 |
| **2** | **规模（模块数）** | `imports.jsonl` | 投入的工程量 |
| **3** | **是否被别的族引用** | 依赖图 | 有没有被下游使用 |
| **4** | **是否进 `main_results`** | `status.main_results` 的 200 条 | 是否被当作"主结果" |

**对照分组**（按"族用到的学科数"分）：

* **组 A**：跨学科族（用到 ≥2 个学科）= 7 个
* **组 B**：单学科族（用到 1 个学科）= 413 个

## ⚠️ 必须声明的三个局限（**写进结论**）

1. **组 A 只有 7 个** ⇒ 统计功效极低，只能报**描述性对比**，不能做显著性检验；
2. **"跨学科"是目录标注**，不是内容判定（见 q9 的四层解剖）；
3. **这四个指标都是"团队行为"的代理，不是"数学价值"的度量**
   —— 形式化投入多，可能只说明团队觉得它容易形式化。

用法：
    $PY q17_cross_quality.py
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
OUTJ = ROOT / "episodes" / "2026-W52" / "results" / "q17_跨学科含金量.json"
OUTM = ROOT / "episodes" / "2026-W52" / "results" / "q17_跨学科含金量.md"


def key3(mod: str) -> str | None:
    r"""`OAI.<学科>.<族>.<...>` -> `学科.族`（**字符串**，唯一用户标识）。"""
    m = re.sub(r"^lean\.", "", mod)
    if not m.startswith("OAI."):
        return None
    p = m.split(".")
    return f"{p[1]}.{p[2]}" if len(p) >= 3 else None


def main() -> int:
    print("=" * 96)
    print("  W52 · 跨学科结果的「含金量」：四指标组间对照")
    print("=" * 96)

    # ---------- 读图 ----------
    fam_mods: Counter = Counter()
    fam_deps_discs: dict[str, set] = defaultdict(set)   # 族 **用到** 的学科
    fam_own_disc: dict[str, str] = {}
    deps: dict[str, list[str]] = {}
    with SRC.open(encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            m = re.sub(r"^lean\.", "", d.get("mod", ""))
            k = key3(m)
            if not k:
                continue
            fam_mods[k] += 1
            fam_own_disc[k] = k.split(".", 1)[0]
            deps[m] = [re.sub(r"^lean\.", "", str(x))
                       for x in (d.get("deps") or [])]

    # ★★ 跨学科性必须看**依赖方向**：
    #    族自己所在的目录永远只有 1 个学科；
    #    "跨学科"指的是**它用了几个别的学科的知识**。
    #    [!] 第一版写成"统计族自己的模块里出现过几个学科" ⇒ 恒为 1 ⇒ 跨学科族 0 个。
    for m, ds in deps.items():
        k = key3(m)
        if not k:
            continue
        for dp in ds:
            k2 = key3(dp)
            if k2 and k2 != k:
                fam_deps_discs[k].add(k2.split(".", 1)[0])

    # 跨族被引
    fam_cited: Counter = Counter()
    for m, ds in deps.items():
        k = key3(m)
        if not k:
            continue
        for dp in ds:
            k2 = key3(dp)
            if k2 and k2 != k:
                fam_cited[k2] += 1

    # ---------- 形式化集合 ----------
    print(f"\n  读 formalization.yaml …")
    y = open_url("https://raw.githubusercontent.com/openai/math/main/"
                 "lean/formalization.yaml", timeout=120,
                 tries=3).read().decode("utf-8", "ignore")
    srcs = re.findall(r'(?m)^\s*-\s+title:\s*"(.+?)"\s*\n\s*authors:.*?\n'
                      r'\s*id:\s*(\.\./preprints/[^\s]+)', y, re.S | re.M)
    form_titles = [t for t, _i in srcs]
    print(f"     sources {len(srcs)} 条")
    st = re.search(r"(?ms)^status:(.*?)(?=^\w|\Z)", y)
    main_files = re.findall(r"file:\s*(\S+)", st.group(1)) if st else []
    # main_results 的 Lean 文件 -> 族
    main_fams = set()
    for fp in main_files:
        p = fp.replace(".lean", "").split("/")
        if len(p) >= 3:
            main_fams.add(f"{p[1]}.{p[2]}")
    print(f"     main_results 文件 {len(main_files)} 个"
          f" -> 涉及 {len(main_fams)} 个族")

    # ---------- 分组 ----------
    cross = {k for k, v in fam_deps_discs.items() if len(v) >= 2}
    mono = {k for k in fam_mods if len(fam_deps_discs.get(k, ())) <= 1}
    print(f"\n  == 分组 ==")
    print(f"     跨学科族（>=2 学科）：**{len(cross)}**")
    print(f"     单学科族：**{len(mono)}**")

    # formalization.yaml 的 id 指向 preprints 目录名 -> 无法直接映射族名
    # 故改用**族名出现在 title 里**做弱匹配，并如实说明这是弱判据
    def has_formal(k: str) -> bool:
        fam = k.split(".", 1)[1]
        return any(fam.lower() in t.lower().replace("-", "").replace(" ", "")
                   for t in form_titles)

    rows = {}
    for grp, ks in (("cross", cross), ("mono", mono)):
        ms = [fam_mods[k] for k in sorted(ks)]
        cited = [fam_cited.get(k, 0) for k in sorted(ks)]
        nr = [k for k in sorted(ks) if has_formal(k)]
        nm = [k for k in sorted(ks) if k in main_fams]
        rows[grp] = {
            "n": len(ks), "mods": ms, "cited": cited,
            "formal": len(nr), "main": len(nm),
            "formal_list": nr, "main_list": nm,
        }
        import statistics
        print(f"\n  == 组 {grp}（{len(ks)} 个族）==")
        print(f"     模块数：中位 {statistics.median(ms):.0f}  均值 "
              f"{sum(ms)/len(ms):.1f}  最大 {max(ms)}")
        print(f"     被同类跨族引用次数：中位 {statistics.median(cited):.0f}  "
              f"均值 {sum(cited)/len(cited):.1f}")
        print(f"     命中 formalization.yaml 标题：{len(nr)}"
              f"  ({len(nr)/len(ks)*100:.0f}%)")
        print(f"     进 main_results：{len(nm)}"
              f"  ({len(nm)/len(ks)*100:.0f}%)")

    # ---------- 跨学科族的**逐个列出**（只有 7 个，全列）----------
    print(f"\n  == 跨学科族逐个列出（共 {len(cross)} 个）==")
    print(f"     {'族':<44}{'学科':>4}{'模块':>6}{'被跨族引':>8}  在 main_results")
    detail = []
    for k in sorted(cross, key=lambda x: -fam_mods[x]):
        d = {"family": k, "discs": sorted(fam_deps_discs[k]),
             "mods": fam_mods[k], "cited": fam_cited.get(k, 0),
             "main": k in main_fams, "formal": has_formal(k)}
        detail.append(d)
        print(f"     {k[:42]:<44}{len(d['discs']):>4}{d['mods']:>6}"
              f"{d['cited']:>8}  {'是' if d['main'] else '否'}")
    print(f"\n     学科组合：")
    for d in detail:
        print(f"       {d['family'][:40]:<42} {' + '.join(d['discs'])}")

    OUTJ.parent.mkdir(parents=True, exist_ok=True)
    OUTJ.write_text(json.dumps({"rows": rows, "cross_detail": detail},
                              ensure_ascii=False, indent=2), encoding="utf-8")

    L = ["# W52 · 跨学科结果的「含金量」：四指标组间对照", "",
         "> [!] **本文件不评价数学价值**（那需要领域专家）。",
         "> 它用**四个可观测的代理指标**做组间对照。", "",
         "## 分组", "",
         f"| 组 | 定义 | 族数 |", "|---|---|---|",
         f"| **A 跨学科族** | 用到 >=2 个学科 | **{len(cross)}** |",
         f"| **B 单学科族** | 只看 1 个学科 | **{len(mono)}** |", "",
         "## 四指标对照", "",
         "| 指标 | A 跨学科 | B 单学科 |", "|---|---|---|",
         f"| 模块数（中位）| "
         f"{sorted(rows['cross']['mods'])[len(cross)//2]} | "
         f"{sorted(rows['mono']['mods'])[len(mono)//2]} |",
         f"| 被跨族引用次数（中位）| "
         f"{sorted(rows['cross']['cited'])[len(cross)//2]} | "
         f"{sorted(rows['mono']['cited'])[len(mono)//2]} |",
         f"| 命中 formalization 标题 | {rows['cross']['formal']}/{len(cross)}"
         f" ({rows['cross']['formal']/len(cross)*100:.0f}%) | "
         f"{rows['mono']['formal']}/{len(mono)}"
         f" ({rows['mono']['formal']/len(mono)*100:.0f}%) |",
         f"| 进 main_results | {rows['cross']['main']}/{len(cross)}"
         f" ({rows['cross']['main']/len(cross)*100:.0f}%) | "
         f"{rows['mono']['main']}/{len(mono)}"
         f" ({rows['mono']['main']/len(mono)*100:.0f}%) |", "",
         "## ★ 跨学科族逐个列出（只有 7 个，全部列出）", "",
         "| 族 | 学科组合 | 模块数 | 被跨族引用 | 进 main_results |",
         "|---|---|---|---|---|"]
    for d in detail:
        L.append(f"| `{d['family']}` | {' + '.join(d['discs'])} | "
                 f"{d['mods']} | {d['cited']} | "
                 f"{'是' if d['main'] else '否'} |")
    L += ["", "## [!] 三个必须随结论出现的局限", "",
          f"1. **组 A 只有 {len(cross)} 个族** ⇒ 统计功效极低，"
          f"**只能报描述性对比，不能做显著性检验**；",
          "2. **「跨学科」是目录标注**，不是内容判定"
          "（见 `q9_桥梁四层解剖.md`）；",
          "3. **这四个指标都是「团队行为」的代理，不是「数学价值」的度量**"
          " —— 形式化投入多，也可能只说明团队觉得它**容易**形式化。"]
    OUTM.write_text("\n".join(L), encoding="utf-8")
    print(f"\n  -> {OUTJ.relative_to(ROOT)}")
    print(f"  -> {OUTM.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
