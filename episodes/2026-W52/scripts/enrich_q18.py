#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W52 · 为配图补齐**组间中位数**（写入 `q18_显著性.json`）。

## 为什么需要

`q18_显著性.json` 目前只存了 p 值（`results` 里没有中位数），
而题 6 的配图需要**两组的模块数中位、被引次数中位**。

本脚本从 `q17_跨学科含金量.json` 取原始数组，算出中位数与均值，
**并入** `q18_显著性.json`（不覆盖既有字段）。

用法：
    $PY enrich_q18.py
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
R = ROOT / "episodes" / "2026-W52" / "results"
Q17 = R / "q17_跨学科含金量.json"
Q18 = R / "q18_显著性.json"


def main() -> int:
    print("=" * 88)
    print("  W52 · 补 q18 的组间中位数")
    print("=" * 88)

    q17 = json.loads(Q17.read_text(encoding="utf-8"))
    q18 = json.loads(Q18.read_text(encoding="utf-8"))
    rows = q17["rows"]

    for grp in ("cross", "mono"):
        ms = rows[grp]["mods"]
        ct = rows[grp]["cited"]
        add = {
            "mods_median": statistics.median(ms),
            "mods_mean": round(statistics.mean(ms), 1),
            "mods_max": max(ms),
            "cited_median": statistics.median(ct),
            "cited_mean": round(statistics.mean(ct), 1),
        }
        q18.setdefault("group_stats", {})[grp] = add
        print(f"\n  {grp}: n={len(ms)}")
        for k, v in add.items():
            print(f"     {k} = {v}")

    Q18.write_text(json.dumps(q18, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\n  -> {Q18.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
