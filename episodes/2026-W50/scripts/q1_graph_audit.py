#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W50 · 问题 1：**依赖图体检**（图能不能用？）。

## 数据来源

`scripts/fetch_lean_imports.py` 流式解析 `openai/math` 的 tarball，
抽出每个 `.lean` 模块的 `import` 行 ⇒ `data/imports.jsonl`。

**实测规模**：读 **2352.6 MB**，得 **86924 个模块 / 248871 条依赖边**
（tarball 里共 147850 个 `.lean`，两次超时中断 ⇒ **结果不完整**，见下）。

## ★★★ 体检必查的五件事（**任何一条不过，后面的分析全部无效**）

| # | 检查 | 为什么致命 |
|---|---|---|
| **①** | **是不是 DAG**（无环）| `import` 理论上无环；**有环说明解析错误**（如把注释里的 import 抓了）|
| **②** | **外部依赖占比** | Lean 会 import `Mathlib.*` —— 那些模块**不在本仓库**，是"图外节点" |
| **③** | **悬空边比例** | 指向不存在模块的边 ⇒ 说明**解析不完整**或模块名拼写规则错 |
| **④** | **自环** | 文件 import 自己 ⇒ 解析错 |
| **⑤** | **覆盖是否偏斜** | 只抓到部分领域 ⇒ 结论不能推广 |

## [!] 关于"结果不完整"的处理原则

**不掩盖**。本脚本：

* 报告**覆盖率**（抓到的 `.lean` / 已知总数）；
* 把"不完整"作为**已知局限**写进后续所有结论；
* 并**验证子集自身的自洽性**（DAG 性、悬空率）——
  一个自洽的子图仍可用于结构分析，只是**规模结论要标注下限**。

## 落盘 `results/q1_图体检.json`

用法：
    $PY q1_graph_audit.py
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W50"
RES = EP / "results"
RES.mkdir(parents=True, exist_ok=True)
SRC = EP / "data" / "imports.jsonl"
STATE = EP / "data" / "fetch_state.json"

TOTAL_LEAN = 147850          # tarball 内实测的 .lean 文件数


def main() -> int:
    print("=" * 96)
    print("  W50 · 问题 1：依赖图体检")
    print("=" * 96)

    mods: dict[str, list[str]] = {}
    with SRC.open(encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            mods[d["mod"]] = d["deps"]
    print(f"\n  读入 {len(mods)} 个模块 / "
          f"{sum(len(v) for v in mods.values())} 条原始边")

    # 覆盖率
    cov = len(mods) / TOTAL_LEAN * 100
    st = {}
    if STATE.exists():
        st = json.loads(STATE.read_text(encoding="utf-8"))
    print(f"\n  ── 覆盖率（**已知局限**）──")
    print(f"    tarball 内 .lean 总数   {TOTAL_LEAN:>8}")
    print(f"    本次解析到              {len(mods):>8}")
    print(f"    **覆盖率              {cov:>7.1f}%**")
    print(f"    （读取 {st.get('bytes',0)/1e6:.0f} MB；"
          f"最后错误：{st.get('last_err','')[:40]}）")

    # ★ 模块命名：本脚本用 `lean.OAI.…`（tar 内路径去 .lean）
    #   而 Lean 内部 import 写 `OAI.…` ⇒ **两者差一个 `lean.` 前缀**，
    #   体检时必须识别这个口径差，否则悬空率会虚高到接近 100%。
    n_lean_prefix = sum(1 for m in mods if m.startswith("lean."))
    print(f"\n  ── 命名口径 ──")
    print(f"    模块名带 `lean.` 前缀：{n_lean_prefix}/{len(mods)}")
    norm = {m[5:] if m.startswith("lean.") else m: v for m, v in mods.items()}

    # 边分类
    nodes = set(norm)
    ext = Counter()      # 图外依赖（Mathlib 等）
    dang = Counter()     # 悬空（本仓库应有但没抓到）
    selfloop = 0
    internal = 0
    for m, deps in norm.items():
        for d in deps:
            if d == m:
                selfloop += 1
            elif d in nodes:
                internal += 1
            elif d.startswith(("Mathlib", "Batteries", "Std", "Lean",
                               "Init", "Lake", "Cli")):
                ext[d.split(".")[0]] += 1
            else:
                dang[d] += 1
    tot_edges = sum(len(v) for v in norm.values())
    print(f"\n  ── 边分类（{tot_edges} 条）──")
    print(f"    ① 内部边（两端都在图内） {internal:>8}  "
          f"{internal/tot_edges*100:>5.1f}%")
    print(f"    ② 外部依赖（Mathlib 等） {sum(ext.values()):>8}  "
          f"{sum(ext.values())/tot_edges*100:>5.1f}%")
    print(f"    ③ 悬空（应有未抓到）     {sum(dang.values()):>8}  "
          f"{sum(dang.values())/tot_edges*100:>5.1f}%")
    print(f"    ④ 自环                   {selfloop:>8}")
    print(f"\n    外部依赖构成：",
          {k: v for k, v in ext.most_common(6)})

    # ★ DAG 检验
    print(f"\n  ── ① DAG 检验（内部边构成的子图）──")
    adj = defaultdict(list)
    indeg = defaultdict(int)
    for m, deps in norm.items():
        for d in deps:
            if d in nodes and d != m:
                adj[d].append(m)          # d -> m（被依赖 -> 依赖者）
                indeg[m] += 1
    # Kahn 拓扑排序
    from collections import deque
    deg = {n: indeg.get(n, 0) for n in nodes}
    q = deque([n for n in nodes if deg[n] == 0])
    seen = 0
    while q:
        u = q.popleft()
        seen += 1
        for v in adj[u]:
            deg[v] -= 1
            if deg[v] == 0:
                q.append(v)
    is_dag = (seen == len(nodes))
    print(f"    拓扑排序访问 {seen}/{len(nodes)} 个节点")
    print(f"    **是 DAG：{is_dag}**"
          f"{'' if is_dag else '  <== 有环！解析可能有问题'}")
    if not is_dag:
        cyc = [n for n in nodes if deg[n] > 0]
        print(f"    环中节点 {len(cyc)} 个，样例：{cyc[:3]}")

    # 领域分布
    print(f"\n  ── ⑤ 领域覆盖 ──")
    dom = Counter()
    for m in nodes:
        p = m.split(".")
        dom[p[1] if len(p) > 1 and p[0] == "OAI" else "(非OAI)"] += 1
    for k, v in dom.most_common(14):
        print(f"    {k:<26}{v:>7}")

    # ★ 唯一游戏证据是否完整
    ug = [m for m in nodes if "UniqueGames" in m]
    print(f"\n  ── 唯一游戏模块收录情况 ──")
    print(f"    含 `UniqueGames` 的模块：**{len(ug)}**")
    for m in sorted(ug)[:8]:
        print(f"      {m}")

    out = {
        "模块数": len(mods), "原始边数": tot_edges,
        "tarball_lean总数": TOTAL_LEAN,
        "覆盖率pct": round(cov, 2),
        "读取MB": round(st.get("bytes", 0) / 1e6, 1),
        "最后错误": st.get("last_err", ""),
        "边分类": {"内部": internal,
                   "外部": sum(ext.values()),
                   "悬空": sum(dang.values()),
                   "自环": selfloop},
        "外部依赖构成": dict(ext.most_common(10)),
        "是DAG": bool(is_dag),
        "拓扑访问": f"{seen}/{len(nodes)}",
        "领域分布": dict(dom.most_common(30)),
        "唯一游戏模块数": len(ug),
        "_自查": [
            "覆盖率不完整 => 规模类结论只能报『下限』",
            "模块命名口径：脚本产 `lean.OAI.x`，Lean 内部写 `OAI.x`，差一个前缀",
            "外部依赖(Mathlib)是图外节点，不参与内部结构分析",
            "DAG 性若失败说明解析错（把注释/字符串里的 import 抓了）",
        ],
    }
    p = RES / "q1_图体检.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
