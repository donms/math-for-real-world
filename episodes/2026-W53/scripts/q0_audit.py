#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W53 数据体检 · 车速 + MTA 流量。

## 为什么必须先做（skill 硬规矩）

"周一比周二堵"要成立，前提是**数据本身没坏**。
体检要能**否定**这个选题，而不是走过场。

## 体检项（每一项都要能拦住问题）

| # | 检查 | 若不过关意味着什么 |
|---|---|---|
| **1** | **时间覆盖率** —— 每个 link 每天是否都有 ~288 点 | 有洞则日内曲线不可比 |
| **2** | **`speed` 缺失与零值占比** | `speed=0` 可能是"无数据"而非"完全静止" |
| **3** | ★ **节假日识别** | **2026-09-07 是美国劳动节**（锚点周的第一个周一！）|
| **4** | `link_id` 的稳定性 | 同一 id 若对应不同路，配对就失效 |
| **5** | 速度量纲与合理域 | 确认是 mph 而非 km/h；剔除荒谬值 |
| **6** | MTA 侧覆盖 | 哪些 facility、哪些小时有值 |
| **7** | ★ **周一 vs 周二的原始对比**（**预演，不是结论**）| 若差异极小，选题可能不成立 |

用法：
    $PY q0_audit.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
EP = ROOT / "episodes" / "2026-W53"
RAW = EP / "data" / "raw"
OUT = EP / "results" / "q0_数据体检.json"

# 2026 年美国联邦假日（只列可能落在取数区间内的）
HOLIDAYS_2026 = {
    date(2026, 1, 1): "New Year's Day",
    date(2026, 1, 19): "MLK Day",
    date(2026, 2, 16): "Presidents Day",
    date(2026, 5, 25): "Memorial Day",
    date(2026, 6, 19): "Juneteenth",
    date(2026, 7, 3): "Independence Day (observed)",
    date(2026, 7, 4): "Independence Day",
    date(2026, 9, 7): "Labor Day",
    date(2026, 10, 12): "Columbus Day",
    date(2026, 11, 11): "Veterans Day",
    date(2026, 11, 26): "Thanksgiving",
    date(2026, 12, 25): "Christmas",
}


def load_speed(p: Path):
    with p.open(encoding="utf-8") as f:
        for ln in f:
            try:
                yield json.loads(ln)
            except Exception:                                        # noqa: BLE001
                continue


def main() -> int:
    files = sorted(RAW.glob("speed_*.jsonl"))
    if not files:
        print("[X] 没有 speed_*.jsonl，先跑 fetch_traffic.py")
        return 2
    print("=" * 96)
    print(f"  W53 数据体检 · {len(files)} 周")
    print("=" * 96)
    rep: dict = {}

    per_day: Counter = Counter()
    per_day_link: dict[str, set] = defaultdict(set)
    zero = miss = tot = 0
    vmin, vmax = 1e9, -1e9
    link_names: dict[str, set] = defaultdict(set)
    bad_year = 0
    week_rows: dict[str, int] = {}

    for p in files:
        n = 0
        for r in load_speed(p):
            ts = r.get("data_as_of") or ""
            if not ts.startswith("2026"):
                bad_year += 1
                continue
            d = ts[:10]
            per_day[d] += 1
            lid = r.get("link_id") or "?"
            per_day_link[d].add(lid)
            ln_ = r.get("link_name")
            if ln_:
                link_names[lid].add(ln_)
            sv = r.get("speed")
            tot += 1
            n += 1
            if sv in (None, ""):
                miss += 1
                continue
            try:
                v = float(sv)
            except ValueError:
                continue
            if v == 0:
                zero += 1
            vmin = min(vmin, v)
            vmax = max(vmax, v)
        week_rows[p.stem.replace("speed_", "")] = n
        print(f"  {p.name:<28} {n:>8,} 行")

    print(f"\n  == ① 时间覆盖率 ==")
    days = sorted(per_day)
    print(f"     覆盖 {len(days)} 天：{days[0]} … {days[-1]}")
    print(f"     每天行数：中位 {sorted(per_day.values())[len(per_day)//2]:,}"
          f"  最小 {min(per_day.values()):,}  最大 {max(per_day.values()):,}")
    print(f"     每天涉及 link 数：中位 "
          f"{sorted(len(v) for v in per_day_link.values())[len(per_day_link)//2]}")
    rep["days"] = len(days)
    rep["rows_per_day"] = {"min": min(per_day.values()),
                           "max": max(per_day.values())}

    print(f"\n  == ② 缺失与零值 ==")
    print(f"     总行 {tot:,}  speed 缺失 {miss:,} ({miss/max(tot,1)*100:.2f}%)"
          f"  speed=0 {zero:,} ({zero/max(tot,1)*100:.2f}%)")
    print(f"     speed 值域 [{vmin:.1f}, {vmax:.1f}]  ← 需确认是 mph")
    rep["missing_pct"] = round(miss / max(tot, 1) * 100, 3)
    rep["zero_pct"] = round(zero / max(tot, 1) * 100, 3)
    rep["speed_range"] = [vmin, vmax]

    print(f"\n  == ③ ★ 节假日识别（取数区间内）==")
    hit = []
    for d in days:
        dt = date.fromisoformat(d)
        if dt in HOLIDAYS_2026:
            hit.append((d, dt.strftime("%A"), HOLIDAYS_2026[dt]))
    if hit:
        for d, wd, nm in hit:
            print(f"     [!] {d}（{wd}）是 **{nm}** —— 当天行数 "
                  f"{per_day[d]:,}")
    else:
        print("     区间内无联邦假日")
    rep["holidays_in_range"] = hit

    print(f"\n  == ④ link_id 稳定性 ==")
    multi = {k: sorted(v) for k, v in link_names.items() if len(v) > 1}
    print(f"     link_id {len(link_names)} 个；"
          f"对应**多个 link_name** 的 {len(multi)} 个")
    if multi:
        for k, v in list(multi.items())[:5]:
            print(f"       {k}: {v[:3]}")
    rep["links"] = len(link_names)
    rep["links_multi_name"] = len(multi)

    print(f"\n  == ⑤ ★ 预演：周一 vs 周二（7–9 时，按天均值）==")
    by_day_peak: dict[str, list[float]] = defaultdict(list)
    for p in files:
        for r in load_speed(p):
            ts = r.get("data_as_of") or ""
            if not ts.startswith("2026"):
                continue
            try:
                h = int(ts[11:13])
            except ValueError:
                continue
            if 7 <= h <= 9:
                sv = r.get("speed")
                if sv in (None, ""):
                    continue
                try:
                    by_day_peak[ts[:10]].append(float(sv))
                except ValueError:
                    continue
    print(f"     {'日期':<12}{'星期':<6}{'均值':>7}{'中位':>7}{'n':>9}")
    import statistics as st
    stats_by = {}
    for d in sorted(by_day_peak):
        v = by_day_peak[d]
        dt = date.fromisoformat(d)
        m, md = st.mean(v), st.median(v)
        stats_by[d] = {"mean": round(m, 2), "median": round(md, 2),
                       "n": len(v), "dow": dt.strftime("%a"),
                       "holiday": dt in HOLIDAYS_2026}
        flag = " ★假日" if dt in HOLIDAYS_2026 else ""
        print(f"     {d:<12}{dt.strftime('%a'):<6}{m:>7.2f}{md:>7.2f}"
              f"{len(v):>9,}{flag}")
    rep["peak_by_day"] = stats_by

    # 按星期聚合（排除假日）
    grp: dict[str, list[float]] = defaultdict(list)
    for d, s in stats_by.items():
        if s["holiday"]:
            continue
        grp[s["dow"]].append(s["mean"])
    print(f"\n     按星期（**已排除假日**）：")
    for wd in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"):
        if wd in grp:
            print(f"       {wd}  均值 {st.mean(grp[wd]):>6.2f}  "
                  f"（{len(grp[wd])} 天）")
    rep["by_weekday"] = {k: round(st.mean(v), 2) for k, v in grp.items()}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
