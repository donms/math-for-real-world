#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W53 诊断 · **逐日覆盖率**（找出数据有洞的日子）。

## 为什么必须查

体检报"每天行数 中位 35,913，**最小 1,253**"——
后者只有正常量的 **3.5%**。若这种日子进了分析，
它会把该天的均值算得极不稳定（甚至只反映少数几条路段）。

## 判据

正常一天 = **125 条 link x 288 点 = 36,000 行**。
定义覆盖率 $c_d = n_d / 36000$。

| $c_d$ | 判定 |
|---|---|
| >= 0.90 | 完整 |
| 0.50 – 0.90 | 部分缺失（可用，但要标注）|
| < 0.50 | **不可用**（须剔除或重取）|

用法：
    $PY q0b_coverage.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
RAW = ROOT / "episodes" / "2026-W53" / "data" / "raw"
OUT = ROOT / "episodes" / "2026-W53" / "results" / "q0b_覆盖率.json"

EXPECT = 36000          # 125 link x 288 点


def main() -> int:
    print("=" * 92)
    print("  W53 诊断 · 逐日覆盖率")
    print("=" * 92)
    n_day: Counter = Counter()
    links_day: dict[str, set] = defaultdict(set)
    hours_day: dict[str, set] = defaultdict(set)
    for p in sorted(RAW.glob("speed_*.jsonl")):
        with p.open(encoding="utf-8") as f:
            for ln in f:
                try:
                    r = json.loads(ln)
                except Exception:                                    # noqa: BLE001
                    continue
                ts = r.get("data_as_of") or ""
                if not ts.startswith("2026"):
                    continue
                d = ts[:10]
                n_day[d] += 1
                links_day[d].add(r.get("link_id"))
                try:
                    hours_day[d].add(int(ts[11:13]))
                except ValueError:
                    pass

    days = sorted(n_day)
    print(f"\n  覆盖 {len(days)} 天 ｜ 总行 {sum(n_day.values()):,}")
    bad, part, ok = [], [], []
    for d in days:
        c = n_day[d] / EXPECT
        rec = {"d": d, "n": n_day[d], "cov": round(c, 3),
               "links": len(links_day[d]), "hours": len(hours_day[d])}
        if c < 0.50:
            bad.append(rec)
        elif c < 0.90:
            part.append(rec)
        else:
            ok.append(rec)

    print(f"\n  == 分级 ==")
    print(f"     完整 (>=90%)      : {len(ok)} 天")
    print(f"     部分 (50-90%)     : {len(part)} 天")
    print(f"     **不可用 (<50%)** : {len(bad)} 天")

    if part:
        print(f"\n  == 部分缺失的日子 ==")
        print(f"     {'日期':<12}{'星期':<6}{'行数':>9}{'覆盖':>8}"
              f"{'link数':>8}{'小时数':>8}")
        for r in part:
            dt = date.fromisoformat(r["d"])
            print(f"     {r['d']:<12}{dt.strftime('%a'):<6}{r['n']:>9,}"
                  f"{r['cov']*100:>7.1f}%{r['links']:>8}{r['hours']:>8}")
    if bad:
        print(f"\n  == ★ 不可用的日子（覆盖率 < 50%）==")
        print(f"     {'日期':<12}{'星期':<6}{'行数':>9}{'覆盖':>8}"
              f"{'link数':>8}{'小时数':>8}")
        for r in bad:
            dt = date.fromisoformat(r["d"])
            print(f"     {r['d']:<12}{dt.strftime('%a'):<6}{r['n']:>9,}"
                  f"{r['cov']*100:>7.1f}%{r['links']:>8}{r['hours']:>8}")

    # 哪些周含不可用日
    if bad:
        wks = sorted({(date.fromisoformat(r["d"]).isocalendar()[:2])
                      for r in bad})
        print(f"\n     受影响周: "
              f"{', '.join(f'{y}-W{w:02d}' for y, w in wks)}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "days": len(days), "expect_per_day": EXPECT,
        "n_ok": len(ok), "n_partial": len(part), "n_bad": len(bad),
        "partial": part, "bad": bad,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
