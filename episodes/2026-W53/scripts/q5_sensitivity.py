#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W53 · **数据质量门槛的敏感性分析**（论文的稳健性一节）。

## 为什么必须做

本期有三类数据缺陷，每类都要设一个门槛，而**门槛的取值会影响结论**：

| 门槛 | 可选取值 | 影响 |
|---|---|---|
| **当天覆盖率** | 0% / 50% / 75% / 90% | 收紧 ⇒ 样本变少、精度下降；放松 ⇒ 纳入只覆盖部分小时的日子，日内形态失真 |
| **`speed = 0`** | 保留 / 剔除 | 保留 ⇒ 均速被拉低约 9 mph（**但周一与周中同等受影响**，配对差可能不变）|
| **link 集合** | 全部（101→125）/ 仅全程共有的 101 | 扩容前后"全网均值"组成不同；用配对法可自动抵消，用均值法不行 |

**⇒ 如果核心结论在不同门槛下都成立，它才是可信的。**

## 检验什么（三问的核心量）

1. **周一 vs 周二** 中位配对差（期望 ≈ 0）；
2. **工作日 vs 周末** 中位配对差（期望显著为负）；
3. ★ **逐小时：早高峰是否仍为"零线窗口"**（这是全题的题眼）。

用法：
    $PY q5_sensitivity.py
"""
from __future__ import annotations

import json
import math
import statistics as st
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
EP = ROOT / "episodes" / "2026-W53"
RAW = EP / "data" / "raw"
OUT = EP / "results" / "q5_门槛敏感性.json"

HOLIDAYS = {date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3),
            date(2026, 7, 4), date(2026, 9, 7)}
WD = ("Mon", "Tue", "Wed", "Thu", "Fri")
WE = ("Sat", "Sun")
MID = ("Tue", "Wed", "Thu")


def load_all():
    r"""一次性读完，缓存原始行，供不同门槛反复切片。"""
    rows = []
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
                try:
                    d = date.fromisoformat(ts[:10])
                    h = int(ts[11:13])
                    v = float(r.get("speed") or 0)
                except (ValueError, TypeError):
                    continue
                if d in HOLIDAYS:
                    continue
                rows.append((ts[:10], d.strftime("%a"), r.get("link_id"), h, v,
                             d.isocalendar()[:2]))
    return rows


def norm_coverage(rows):
    r"""★ **按"当天实际有多少 link 在报"归一化**的逐日覆盖率。

    ## 为什么不能用固定的 36000 作分母

    本数据集在 **2026-06 扩容**：5 月只有 **101** 条 link，6 月起 **125** 条。
    ⇒ 5 月的"满覆盖"只有 $101 \times 288 = 29088$ 行，覆盖率上限 **80.8%**。

    **若用固定分母 36000**：
    * 5 月的日子覆盖率恒为 0.81 ⇒ **整段被判"不合格"**；
    * 于是"覆盖率 >= 90%"这个门槛**实际等价于"只用 6 月以后的数据"**
      ⇒ **与季节完全混淆**（实测：门槛从 75% 抬到 90% 时，
      周一 vs 周二的中位差从 −0.052 变成 −0.210，
      看起来"周一效应出现了"，实则只是换了个季节窗口）。

    ⇒ **正确做法**：先算"当天有多少条 link 在报" $L_d$，
    再以 $L_d \times 288$ 为分母 —— 这样 101-link 时期的满覆盖也是 1.0。
    """
    links_day: dict[str, set] = defaultdict(set)
    n_day: dict[str, int] = defaultdict(int)
    for ds, _dw, lk, _h, _v, _wk in rows:
        links_day[ds].add(lk)
        n_day[ds] += 1
    return {ds: n_day[ds] / (len(links_day[ds]) * 288)
            for ds in n_day if links_day[ds]}


def wilcoxon_p(diffs):
    nz = [x for x in diffs if x != 0]
    n = len(nz)
    if n < 10:
        return 1.0
    order = sorted(range(n), key=lambda i: abs(nz[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(nz[order[j + 1]]) == abs(nz[order[i]]):
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    wp = sum(ranks[i] for i in range(n) if nz[i] > 0)
    mu = n * (n + 1) / 4
    sd = math.sqrt(n * (n + 1) * (2 * n + 1) / 24)
    z = (wp - mu) / sd if sd else 0.0
    return 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))


def cells_from(rows, cov, drop_zero, common_only, hours=None):
    r"""按门槛切片成 {(日, 星期, link, 小时): 均速}。"""
    keep = None
    if common_only:
        byw = defaultdict(set)
        for ds, _dw, lk, _h, _v, wk in rows:
            byw[wk].add(lk)
        keep = set.intersection(*byw.values()) if byw else set()
    acc: dict[tuple, list] = defaultdict(list)
    for ds, dw, lk, h, v, _wk in rows:
        if cov is not None and cov.get(ds, 0) < cov_threshold:
            continue
        if drop_zero and v <= 0:
            continue
        if not drop_zero and v < 0:
            continue
        if keep is not None and lk not in keep:
            continue
        if hours is not None and h not in hours:
            continue
        acc[(ds, dw, lk, h)].append(v)
    return {k: st.mean(v) for k, v in acc.items()}


def paired(cells, sel_a, sel_b):
    r"""按 (ISO周, link, 小时) 配对，返回 (中位差, p, n)。

    [!] 键必须含**周**与**小时**：`(日, 星期, link, 小时)` 里，
        去掉"日"后同一 (周, 星期, link, 小时) 只有一条记录，
        所以配对键取 (周, link, 小时) 即等价于"同日同时段同路段"。
    """
    A: dict[tuple, list] = defaultdict(list)
    B: dict[tuple, list] = defaultdict(list)
    for (ds, dw, lk, h), v in cells.items():
        d = date.fromisoformat(ds)
        key = (d.isocalendar()[:2], lk, h)
        if dw in sel_a:
            A[key].append(v)
        elif dw in sel_b:
            B[key].append(v)
    am = {k: st.mean(v) for k, v in A.items()}
    bm = {k: st.mean(v) for k, v in B.items()}
    com = sorted(set(am) & set(bm))
    if not com:
        return (None, None, 0)
    df = [am[k] - bm[k] for k in com]
    return (st.median(df), wilcoxon_p(df), len(com))


def main() -> int:
    W.require_raw()          # 缺原始数据时给可操作提示
    global cov_threshold
    print("=" * 96)
    print("  W53 · 数据质量门槛的敏感性分析")
    print("=" * 96)
    rows = load_all()
    print(f"\n  读入 {len(rows):,} 行（已剔假日）")
    cov = norm_coverage(rows)
    L = {ds: len({r[2] for r in rows if r[0] == ds}) for ds in cov}
    lo = min(L.values())
    hi = max(L.values())
    print(f"  逐日 link 数：最少 {lo} / 最多 {hi}"
          f"  ⇒ **归一化覆盖率**（分母 = 当天 link 数 x 288）")
    from collections import Counter as _C
    print(f"     link 数分布: {dict(_C(L.values()))}")
    cvals = sorted(cov.values())
    print(f"     归一化覆盖率：中位 {cvals[len(cvals)//2]:.3f}  "
          f"最低 {cvals[0]:.3f}")
    print(f"  ⇒ 归一化后 **{(sum(1 for v in cov.values() if v>=0.90))} 天** "
          f"达到 90%（原先按 36000 只有 "
          f"{sum(1 for ds in cov if cov[ds]>=0.90)} 天）")

    res = {"thresholds": {}, "core": {}, "hourly_peak": {}}

    # ---------- ① 门槛 × 两个核心对比 ----------
    print(f"\n  == ① 覆盖率门槛 x 核心结论 ==")
    print(f"     {'门槛':<8}{'天数':>6}{'周一vs周二':>14}{'p':>10}"
          f"{'工作日vs周末':>16}{'p':>10}")
    for thr in (0.0, 0.50, 0.75, 0.90):
        cov_threshold = thr
        good = {d for d, c in cov.items() if c >= thr}
        c = cells_from(rows, cov, True, True, hours=(7, 8, 9))
        c = {k: v for k, v in c.items() if k[0] in good}
        m1, p1, n1 = paired(c, ("Mon",), ("Tue",))
        m2, p2, n2 = paired(c, WD, WE)
        print(f"     {thr:>5.0%}  {len(good):>6}"
              f"{(f'{m1:+.3f}' if m1 is not None else '—'):>14}"
              f"{(f'{p1:.3f}' if p1 is not None else '—'):>10}"
              f"{(f'{m2:+.3f}' if m2 is not None else '—'):>16}"
              f"{(f'{p2:.1e}' if p2 is not None else '—'):>10}")
        res["thresholds"][f"{thr:.2f}"] = {
            "days": len(good), "mon_vs_tue": m1, "p1": p1, "n1": n1,
            "wd_vs_we": m2, "p2": p2, "n2": n2}

    # ---------- ② 剔 0 vs 含 0 ----------
    print(f"\n  == ② speed=0 的处置（覆盖率门槛 75%）==")
    cov_threshold = 0.75
    good = {d for d, c in cov.items() if c >= 0.75}
    for dz, lab in ((True, "剔 0（主口径）"), (False, "含 0")):
        c = cells_from(rows, cov, dz, True, hours=(7, 8, 9))
        c = {k: v for k, v in c.items() if k[0] in good}
        m1, p1, _ = paired(c, ("Mon",), ("Tue",))
        m2, p2, _ = paired(c, WD, WE)
        print(f"     {lab:<16} 周一vs周二 {m1:+.3f} (p={p1:.3f})  "
              f"工作日vs周末 {m2:+.3f} (p={p2:.1e})")
        res["core"][lab] = {"mon_vs_tue": m1, "wd_vs_we": m2}

    # ---------- ③ link 集合 ----------
    print(f"\n  == ③ link 集合（覆盖门槛 75%，剔 0）==")
    for co, lab in ((True, "仅全程共有的 101 条"), (False, "全部（含扩容的 24 条）")):
        c = cells_from(rows, cov, True, co, hours=(7, 8, 9))
        c = {k: v for k, v in c.items() if k[0] in good}
        m1, p1, _ = paired(c, ("Mon",), ("Tue",))
        m2, p2, _ = paired(c, WD, WE)
        print(f"     {lab:<26} 周一vs周二 {m1:+.3f} (p={p1:.3f})  "
              f"工作日vs周末 {m2:+.3f} (p={p2:.1e})")
        res["core"][lab] = {"mon_vs_tue": m1, "wd_vs_we": m2}

    # ---------- ④ ★ 题眼：早高峰是否仍为零线窗口 ----------
    print(f"\n  == ④ ★ 题眼检验：逐小时（周一 vs 周二至周四）==")
    c_all = cells_from(rows, cov, True, True)
    c_all = {k: v for k, v in c_all.items() if k[0] in good}
    print(f"     {'时':>3}{'中位差':>10}{'p':>10}  判定")
    peak_sig = []
    for h in range(24):
        ch = {k: v for k, v in c_all.items() if k[3] == h}
        m, p, n = paired(ch, ("Mon",), MID)
        if m is None:
            continue
        # 逐小时也做 Bonferroni（24 次）
        sig = p is not None and p < 0.05 / 24
        if sig:
            peak_sig.append(h)
        print(f"     {h:>3}{m:>+10.3f}{p:>10.2e}  "
              f"{'显著' if sig else '不显著'}")
    resid = [h for h in range(24) if h not in peak_sig]
    print(f"\n     显著的时段 {len(peak_sig)}/24")
    print(f"     **不显著的时段**：{resid}")
    early = [h for h in (7, 8, 9) if h in resid]
    print(f"     其中早高峰 7-9 时里不显著的：{early}"
          f"  ⇒ {'★ 题眼成立' if early else '题眼不成立'}")
    res["hourly_peak"] = {"sig_hours": peak_sig, "nonsig": resid,
                          "peak_nonsig": early}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    return 0


cov_threshold = 0.75
if __name__ == "__main__":
    raise SystemExit(main())
