#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""审计：**期目录脚本副本 vs 共享版**的漂移。

## 为什么需要

W46 踩过一个坑：它在 `episodes/2026-W46/scripts/` 里自带了一份
**陈旧** `tts_text.py`（W43 时代的**双向**数字转换设计），
而生成脚本写的是

    sys.path.insert(0, str(Path(__file__).resolve().parent))

⇒ **优先加载期目录副本** ⇒ W48 对**共享版**做的"单向改造"根本没生效
⇒ 成片字幕出现 `混为1谈` / `2个概念`（用户报告两次）。

**同一个坑我在 W50 修抖音时踩过一次**（缺 `tts_captions`），
只修了共享脚本，没意识到 W46 有副本。

## 本脚本检查什么

对每个 `episodes/2026-W*/scripts/*.py`：

1. **是否有同名共享脚本** `scripts/<name>.py`；
2. 若有，两者**内容是否一致**（`--check` 下按行 diff 摘要）；
3. 期目录脚本里的 **`sys.path.insert` 顺序**是否会让副本**遮蔽**共享版；
4. 期目录脚本是否 **import 了共享模块**（说明本可复用共享版）。

输出一张表 + 汇总，并按严重度排序：

* `[遮蔽]` 期目录有同名副本 **且** sys.path 把期目录排在前 ⇒ **高危**
* `[漂移]` 有同名共享脚本但内容不同
* `[本地]` 共享目录没有同名脚本（可能是该期专用逻辑，正常）

用法：
    $PY audit_script_drift.py            # 全期审计
    $PY audit_script_drift.py --ep 2026-W46
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SHARED = ROOT / "scripts"
EPS = ROOT / "episodes"


def h(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def path_order(src: str) -> list[str]:
    """抽取脚本里的 sys.path.insert 目标（按出现顺序）。"""
    out = []
    for m in re.finditer(r"sys\.path\.insert\(\s*0\s*,\s*([^\n]+?)\)", src):
        out.append(m.group(1).strip())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", default="")
    a = ap.parse_args()

    shared = {p.name: p for p in SHARED.glob("*.py")}
    print("=" * 100)
    print("  期目录脚本副本 vs 共享版 —— 漂移审计")
    print("=" * 100)
    print(f"  共享脚本 {len(shared)} 个")

    eps = sorted(p for p in EPS.glob("2026-W*") if p.is_dir())
    if a.ep:
        eps = [p for p in eps if p.name == a.ep]

    rows = []
    for ep in eps:
        sdir = ep / "scripts"
        if not sdir.is_dir():
            continue
        for f in sorted(sdir.glob("*.py")):
            name = f.name
            sh = shared.get(name)
            src = f.read_text(encoding="utf-8", errors="ignore")
            order = path_order(src)
            shadows = any("__file__" in o and "parent" in o for o in order)
            dup = sh is not None
            same = dup and h(f) == h(sh)
            # 是否 import 了共享模块
            imports = re.findall(r"(?m)^\s*(?:from|import)\s+([\w.]+)", src)
            rows.append({
                "ep": ep.name, "file": name,
                "dup": dup, "same": same, "shadows": shadows,
                "order": order, "imports": sorted(set(imports)),
                "lines": len(src.splitlines()),
                "sh_lines": len(sh.read_text(encoding="utf-8").splitlines())
                if sh else 0,
            })

    sev = {"遮蔽": [], "漂移": [], "一致": [], "本地": []}
    for r in rows:
        if r["dup"] and not r["same"] and r["shadows"]:
            sev["遮蔽"].append(r)
        elif r["dup"] and not r["same"]:
            sev["漂移"].append(r)
        elif r["dup"] and r["same"]:
            sev["一致"].append(r)
        else:
            sev["本地"].append(r)

    for key, title in (("遮蔽", "[遮蔽] 高危：期目录副本会**优先加载**，且与共享版不同"),
                       ("漂移", "[漂移] 有共享同名脚本，内容不同"),
                       ("一致", "[一致] 副本与共享版相同（可考虑删副本）"),
                       ("本地", "[本地] 共享目录无同名脚本（期专用逻辑，正常）")):
        lst = sev[key]
        print(f"\n  === {title} —— {len(lst)} 个 ===")
        if not lst:
            print("     （无）")
            continue
        for r in lst:
            print(f"     {r['ep']}/{r['file']}  "
                  f"{r['lines']} 行 vs 共享 {r['sh_lines']} 行"
                  if r["dup"] else
                  f"     {r['ep']}/{r['file']}  {r['lines']} 行")
            if r["order"]:
                print(f"        sys.path 顺序: {r['order'][:3]}")

    print(f"\n  === 汇总 ===")
    print(f"     遮蔽 {len(sev['遮蔽'])} | 漂移 {len(sev['漂移'])} | "
          f"一致 {len(sev['一致'])} | 本地 {len(sev['本地'])}")
    todo = sev["遮蔽"] + sev["漂移"]
    if todo:
        print(f"\n  [!] 需处理 {len(todo)} 个：")
        for r in todo:
            print(f"     {r['ep']}/scripts/{r['file']}")
            print(f"        -> 建议：删除副本，改从共享版 import"
                  f"（并在脚本里插 `sys.path.insert(0, <repo>/scripts)`）")
    else:
        print("\n  [OK] 未发现会遮蔽共享版的副本")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
