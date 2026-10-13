#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W50 - 定向补取：Unique Games 与 Computability 的声明。

## 为什么不用 API 列目录

初版走 git trees 递归 API 拿文件清单，**跑了 21.7 分钟只占 29 MB**
=> 卡在**网络重试**（该递归响应本身大到会 IncompleteRead）。

## 解法：**用已有的 import 图当"文件清单"**

`imports.jsonl` 里已经有 86924 个**模块全名**，
而 Lean 模块名到路径的映射是确定的：

    lean.OAI.Computability.UniqueGames.Theorem
        => lean/OAI/Computability/UniqueGames/Theorem.lean

=> **不需要列目录，直接算路径**，用 `raw.githubusercontent.com` 取。

用法：
    $PY fetch_ug_decls.py
    $PY fetch_ug_decls.py --filter Computability
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W50"
DATA = EP / "data"

DECL_RE = re.compile(
    r"^[ \t]*(?:@\[[^\]]*\][ \t]*)*"
    r"(?:(?:private|protected|noncomputable|unsafe|partial)[ \t]+)*"
    r"(theorem|lemma)[ \t]+"
    r"([A-Za-z_\u00c0-\u024f\u0370-\u03ff\u1e00-\u1eff'"
    r"\u2070-\u209f\u2100-\u214f][A-Za-z0-9_'!\?\u00c0-\u024f"
    r"\u0370-\u03ff\u1e00-\u1eff\u2070-\u209f\u2100-\u214f]*)",
    re.M)


def raw(mod: str, tries: int = 5) -> str | None:
    r"""按模块名取源文件（模块名 -> 路径是确定映射）。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    from net_resolve import open_url
    path = mod.replace(".", "/") + ".lean"
    url = f"https://raw.githubusercontent.com/openai/math/main/{path}"
    for i in range(tries):
        try:
            b = open_url(url, timeout=45, tries=1).read()
            if b:
                return b.decode("utf-8", "ignore")
        except Exception:                                        # noqa: BLE001
            time.sleep(1 + i)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--filter", default="UniqueGames",
                    help="模块名包含此串")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    print("=" * 94)
    print(f"  W50 - 定向补取声明（filter={args.filter}）")
    print("=" * 94)

    mods = []
    with (DATA / "imports.jsonl").open(encoding="utf-8") as f:
        for ln in f:
            m = json.loads(ln)["mod"]
            if args.filter in m:
                mods.append(m)
    mods = sorted(set(mods))
    print(f"\n  待取模块 {len(mods)} 个")

    outp = DATA / (args.out or f"decls_{args.filter.lower()}.jsonl")
    done = set()
    if outp.exists():
        with outp.open(encoding="utf-8") as f:
            for ln in f:
                try:
                    done.add(json.loads(ln)["mod"])
                except Exception:                                # noqa: BLE001
                    pass
        print(f"  [续跑] 已有 {len(done)} 个")

    pending = []

    def flush():
        if not pending:
            return
        with outp.open("a", encoding="utf-8") as fa:
            for d in pending:
                fa.write(json.dumps(d, ensure_ascii=False) + "\n")
        pending.clear()

    n_new = n_fail = th_all = lm_all = 0
    t0 = time.time()
    for i, mod in enumerate(mods, 1):
        if mod in done:
            continue
        txt = raw(mod)
        if txt is None:
            n_fail += 1
            continue
        decls = [[m.group(1), m.group(2),
                  txt[:m.start()].count("\n") + 1]
                 for m in DECL_RE.finditer(txt)]
        th = sum(1 for d in decls if d[0] == "theorem")
        lm = len(decls) - th
        th_all += th
        lm_all += lm
        pending.append({"mod": mod, "decls": decls,
                        "n_theorem": th, "n_lemma": lm})
        n_new += 1
        if len(pending) >= 40:
            flush()
            print(f"    {i:>4}/{len(mods)}  新抽 {n_new:>4}  失败 {n_fail:>3}"
                  f"  th {th_all}/lm {lm_all}  {time.time()-t0:>5.0f}s")
    flush()
    print(f"\n  {'='*88}")
    print(f"  目标 {len(mods)}  新抽 {n_new}  失败 {n_fail}")
    print(f"  **theorem {th_all}  /  lemma {lm_all}  合计 "
          f"{th_all+lm_all}**")
    print(f"  -> {outp.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
