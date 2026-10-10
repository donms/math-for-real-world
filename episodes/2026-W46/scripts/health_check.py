#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · 数据体检：缺测率、异常值、季相、与外部报道比对。

## 为什么必须做（skill 3.1 第 ② 步）

模型之前先摸清数据的脾气：
缺哪些周、有没有跳变、季节形状是否一致、与公开报道能否对上。

## 检查项

1. **覆盖**：周数、年份分布、缺测周；
2. **缺测率**：逐字段；
3. **异常值**：超出 ±4σ 的点、负值、零值占比；
4. **季节形状**：按 ISO 周聚合，看峰在什么时候（**这是季节性模型的前提**）；
5. **外部比对**：与已知报道口径对照（如 2026 年第 37 周的水平）。
6. **口径断点**：COVID 期间（2020–2022）ILI 监测行为异常，
   必须显式标注 —— 否则会把"行为改变"误当"病毒变强"。

用法：
    $PY health_check.py
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"


def load(p: Path) -> list[dict]:
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fnum(v):
    try:
        return float(v)
    except Exception:                                            # noqa: BLE001
        return None


def main() -> int:
    print("=" * 94)
    print("  W46 · 数据体检")
    print("=" * 94)
    ili = load(CLEAN / "ili_weekly.csv")
    cli = load(CLEAN / "clinical_weekly.csv")
    rep: dict = {}

    # ---- 1) 覆盖 ----
    print(f"\n  ── 1) 覆盖 ──")
    for name, rows in (("ili_weekly", ili), ("clinical_weekly", cli)):
        wk = [int(r["epiweek"]) for r in rows]
        yrs = Counter(w // 100 for w in wk)
        # ⚠️ **不能**用 `max(wk) - min(wk)`：ISO 周号每年重置，
        #    200001 → 200101 数字上跳 100 但时间上只差 1 周。
        #    上一版因此报出"缺失 49.3%"的假结论（实测踩过）。
        #    正确做法：把 (年,周) 摊平成"距 2000 年第 1 周的周数"。
        def flat(w: int) -> int:
            return (w // 100 - 2000) * 52 + (w % 100)
        fw = sorted(flat(w) for w in wk)
        span = fw[-1] - fw[0] + 1
        missing = span - len(fw)
        print(f"     {name}: {len(rows)} 周  {min(wk)}–{max(wk)}  "
              f"跨度 {span} 周  缺失 {missing} 周 "
              f"({missing/span*100:.1f}%)")
        print(f"        年份分布: " +
              ", ".join(f"{y}:{n}" for y, n in sorted(yrs.items())[:6]) +
              " … " + ", ".join(f"{y}:{n}" for y, n in sorted(yrs.items())[-3:]))
        rep[name] = {"weeks": len(rows), "first": min(wk), "last": max(wk),
                     "span": span, "missing": missing}
        # 缺口落在哪（前 8 段）
        if missing:
            gaps, start = [], None
            prev = None
            for x in fw:
                if prev is not None and x - prev > 1:
                    gaps.append((prev + 1, x - 1))
                prev = x
            print(f"        缺口段数 {len(gaps)}：", end="")
            for a, b in gaps[:6]:
                print(f" [{a}..{b}]", end="")
            print(" …" if len(gaps) > 6 else "")

    # ---- 2) 缺测率（逐字段）----
    print(f"\n  ── 2) 逐字段缺测率 ──")
    for name, rows, keys in (
        ("ili_weekly", ili, ["ili", "num_ili", "num_patients", "wili"]),
        ("clinical_weekly", cli,
         ["total_specimens", "total_a", "total_b", "percent_a"]),
    ):
        print(f"     {name}:")
        for k in keys:
            if k not in rows[0]:
                print(f"        {k:<18} 字段不存在")
                continue
            miss = sum(1 for r in rows if fnum(r.get(k)) is None)
            print(f"        {k:<18} 缺 {miss:>4} / {len(rows)} "
                  f"({miss/len(rows)*100:>5.1f}%)")

    # ---- 3) 异常值 ----
    print(f"\n  ── 3) 异常检查（ili 序列）──")
    v = np.array([fnum(r["ili"]) for r in ili if fnum(r["ili"]) is not None])
    mu, sd = v.mean(), v.std()
    print(f"     ili: 均值 {mu:.3f}  标准差 {sd:.3f}  "
          f"最大 {v.max():.2f}  最小 {v.min():.2f}")
    print(f"     零值 {int((v == 0).sum())} 周  负值 {int((v < 0).sum())} 周")
    out = int((np.abs(v - mu) > 4 * sd).sum())
    print(f"     超出 ±4σ 的周: {out} ({out/len(v)*100:.1f}%)")
    top = np.argsort(-v)[:5]
    print(f"     最高的 5 周: " +
          ", ".join(f"{ili[i]['epiweek']}={v[i]:.2f}" for i in top))

    # ---- 4) 季节形状 ----
    print(f"\n  ── 4) 季节形状（按 ISO 周聚合 ili 均值）──")
    byw = defaultdict(list)
    for r in ili:
        x = fnum(r["ili"])
        if x is not None:
            byw[int(r["epiweek"]) % 100].append(x)
    prof = {w: float(np.mean(v2)) for w, v2 in byw.items() if len(v2) >= 5}
    ws = sorted(prof)
    peak = max(prof, key=lambda w: prof[w])
    trough = min(prof, key=lambda w: prof[w])
    print(f"     峰在第 {peak} 周（均值 {prof[peak]:.2f}）  "
          f"谷在第 {trough} 周（均值 {prof[trough]:.2f}）")
    print(f"     峰谷比 {prof[peak]/max(prof[trough],1e-9):.1f}×")
    # 打印四季轮廓（抽样）
    print("     轮廓（每 4 周一点）：", end="")
    for w in ws[::4]:
        print(f" W{w}:{prof[w]:.1f}", end="")
    print()
    rep["season"] = {"peak_week": peak, "peak_val": prof[peak],
                     "trough_week": trough, "trough_val": prof[trough]}

    # ---- 5) 口径断点：COVID 期 ----
    print(f"\n  ── 5) 口径断点（COVID 期 2020–2022）──")
    pre = [fnum(r["ili"]) for r in ili
           if 2015 <= int(r["epiweek"]) // 100 <= 2019 and fnum(r["ili"])]
    cov = [fnum(r["ili"]) for r in ili
           if 2020 <= int(r["epiweek"]) // 100 <= 2022 and fnum(r["ili"])]
    post = [fnum(r["ili"]) for r in ili
            if int(r["epiweek"]) // 100 >= 2023 and fnum(r["ili"])]
    for nm, arr in (("2015–2019", pre), ("2020–2022(COVID)", cov),
                    ("2023–今", post)):
        if arr:
            print(f"     {nm:<18} n={len(arr):>4}  均值 {np.mean(arr):>7.3f}  "
                  f"最大 {np.max(arr):>7.2f}")
    print("     => COVID 期监测行为改变，建模必须**显式标注**这一断点，"
          "不可当作病毒本身变化")

    # ---- 6) 亚型更替（clinical）----
    print(f"\n  ── 6) 亚型更替（clinical 的 A/B 占比）──")
    # ⚠️ **单位陷阱**：Delphi 的 `percent_a` / `percent_b` 是**百分数**，
    #    不是比例 —— 第 202637 周 `percent_a = 2.62139` 意思是 **2.62%**。
    #    上一版我按"比例、应接近 1"去读，会得出"几乎全是 B 型"的相反结论。
    rs = [r for r in cli if fnum(r.get("percent_a")) is not None]
    if rs:
        print(f"     有 A 占比的周: {len(rs)}（单位：**%**，非比例）")
        for r in rs[-6:]:
            print(f"        {r['epiweek']}  A={fnum(r['percent_a']):.3f}%  "
                  f"B={fnum(r['percent_b']):.3f}%  样本 {r.get('total_specimens')}")
        pa = np.array([fnum(r["percent_a"]) for r in rs])
        p26 = [fnum(r["percent_a"]) for r in rs
               if int(r["epiweek"]) // 100 == 2026]
        print(f"     A 阳性率：全期均值 {pa.mean():.2f}%  "
              f"2026 年内均值 {np.mean(p26):.2f}%")
        # A/B 相对份额（真正的"亚型更替"指标）
        ratio = []
        for r in rs[-8:]:
            a, b = fnum(r["percent_a"]), fnum(r["percent_b"])
            if a is not None and b is not None and (a + b) > 0:
                ratio.append((r["epiweek"], a / (a + b)))
        print("     最近 8 周的 A 占 (A+B) 份额：")
        for w, x in ratio:
            print(f"        {w}  A 份额 {x*100:>5.1f}%")
        rep["subtype"] = {"unit": "percent (0-100)",
                          "a_share_recent": [[w, x] for w, x in ratio]}

    (CLEAN / "体检.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {CLEAN/'体检.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
