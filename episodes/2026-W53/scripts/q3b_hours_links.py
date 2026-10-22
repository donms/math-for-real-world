#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W53 问 3b · **再找机制**：周一效应是否藏在「特定小时」或「特定路段」里？

## 为什么还要找

问 3 否掉了两个候选机制：

* **极端日过度出现** ⇒ 否（周一占 25%，p=0.62–0.80）；
* **周一更不稳定** ⇒ 否（变异系数 Mon 9.0% = Wed 9.0%）。

但"总体中位差 = 0"**不等于**"处处为 0"。可能性有二：

| # | 假设 | 检验方式 |
|---|---|---|
| **A** | **小时错位**：周一在某些小时更差、另一些更好，**早高峰 7–9 的平均把两者抵消了** | 逐小时做配对检验（0–23 时）|
| **B** | **路段集中**：少数路段的周一效应很强，被 98 条路的整体中位稀释 | 逐 link 效应分布 + 集中度 |

**若 A 成立**，那"体感"就有真实基础 —— 通勤者只在特定几小时出门。

## ★ 纪律

逐小时做 **24 次**检验 ⇒ **必须做多重比较校正**（Bonferroni，α=0.05/24）。
否则"找到一个显著"的概率被抬到很高。

用法：
    $PY q3b_hours_links.py
"""
from __future__ import annotations

import json
import math
import random
import statistics as st
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
EP = ROOT / "episodes" / "2026-W53"
RAW = EP / "data" / "raw"
OUT = EP / "results" / "q3b_小时与路段.json"

HOLIDAYS = {date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3),
            date(2026, 9, 7)}
MID = ("Tue", "Wed", "Thu")


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


def boot_ci(vals, by_link, n_boot=300, seed=20261013):
    links = list(by_link)
    if not links:
        return (0.0, 0.0)
    rng = random.Random(seed)
    meds = []
    for _ in range(n_boot):
        pick = [links[rng.randrange(len(links))] for _ in range(len(links))]
        v = [x for lk in pick for x in by_link[lk]]
        if v:
            meds.append(st.median(v))
    meds.sort()
    return (meds[int(0.025 * len(meds))], meds[int(0.975 * len(meds)) - 1])


def load():
    r"""{(周, dow, link, hour): 均速}，全部 24 小时。"""
    acc: dict[tuple, list[float]] = defaultdict(list)
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
                except ValueError:
                    continue
                if d in HOLIDAYS:
                    continue
                sv = r.get("speed")
                if sv in (None, ""):
                    continue
                try:
                    v = float(sv)
                except ValueError:
                    continue
                if v <= 0:
                    continue
                wk = d.isocalendar()[:2]
                acc[(wk, d.strftime("%a"), r.get("link_id"), h)].append(v)
    return {k: st.mean(v) for k, v in acc.items()}


def main() -> int:
    W.require_raw()          # 缺原始数据时给可操作提示
    print("=" * 96)
    print("  W53 问 3b · 周一效应藏在哪个小时 / 哪条路段")
    print("=" * 96)
    cells = load()
    print(f"\n  单元 {len(cells):,}")

    # ---------- A. 逐小时配对 ----------
    print(f"\n  == A. 逐小时配对（周一 vs 周二至周四）==")
    ALPHA = 0.05 / 24
    print(f"     Bonferroni 校正：α = 0.05/24 = {ALPHA:.5f}")
    print(f"     {'时':>3}{'周一':>8}{'周中':>8}{'中位差':>9}{'相对':>8}"
          f"{'p':>10}  判定")
    hour_rows = []
    sig_n = 0
    for h in range(24):
        A = {k[:1] + k[2:]: v for k, v in cells.items()
             if k[3] == h and k[1] == "Mon"}
        B = {k[:1] + k[2:]: v for k, v in cells.items()
             if k[3] == h and k[1] in MID}
        # 周中有 3 天 ⇒ 先按 (周, link) 平均
        Bacc: dict[tuple, list[float]] = defaultdict(list)
        for k, v in cells.items():
            if k[3] == h and k[1] in MID:
                Bacc[(k[0], k[2])].append(v)
        Bm = {k: st.mean(v) for k, v in Bacc.items()}
        Am = {}
        Aacc: dict[tuple, list[float]] = defaultdict(list)
        for k, v in cells.items():
            if k[3] == h and k[1] == "Mon":
                Aacc[(k[0], k[2])].append(v)
        Am = {k: st.mean(v) for k, v in Aacc.items()}
        common = sorted(set(Am) & set(Bm))
        if len(common) < 30:
            continue
        df = [Am[k] - Bm[k] for k in common]
        ma = st.mean([Am[k] for k in common])
        mb = st.mean([Bm[k] for k in common])
        med = st.median(df)
        p = wilcoxon_p(df)
        rel = med / mb * 100 if mb else 0
        mark = "★显著" if p < ALPHA else ""
        if p < ALPHA:
            sig_n += 1
        print(f"     {h:>3}{ma:>8.2f}{mb:>8.2f}{med:>+9.3f}{rel:>+7.2f}%"
              f"{p:>10.2e}  {mark}")
        hour_rows.append({"h": h, "mon": round(ma, 3),
                          "mid": round(mb, 3), "median_diff": round(med, 4),
                          "rel_pct": round(rel, 2), "p": p,
                          "n": len(common)})
    print(f"\n     24 个检验中显著 {sig_n} 个"
          f"（随机预期约 {24*ALPHA:.1f} 个）")

    # ---------- B. 逐 link 效应分布 ----------
    print(f"\n  == B. 逐 link 的周一效应（早高峰 7–9）==")
    PEAK = (7, 8, 9)
    Aacc: dict[tuple, list[float]] = defaultdict(list)
    Bacc2: dict[tuple, list[float]] = defaultdict(list)
    for k, v in cells.items():
        if k[3] not in PEAK:
            continue
        if k[1] == "Mon":
            Aacc[(k[0], k[2])].append(v)
        elif k[1] in MID:
            Bacc2[(k[0], k[2])].append(v)
    Am = {k: st.mean(v) for k, v in Aacc.items()}
    Bm = {k: st.mean(v) for k, v in Bacc2.items()}
    common = sorted(set(Am) & set(Bm))
    eff: dict[str, list[float]] = defaultdict(list)
    for k in common:
        eff[str(k[1])].append(Am[k] - Bm[k])
    per_link = {k: st.median(v) for k, v in eff.items() if len(v) >= 5}
    vals = sorted(per_link.values())
    print(f"     可比 link {len(per_link)} 条（每条至少 5 个配对周）")
    print(f"     效应分布：P10 {vals[int(.1*len(vals))]:+.3f}  "
          f"P25 {vals[int(.25*len(vals))]:+.3f}  中位 "
          f"{st.median(vals):+.3f}  P75 {vals[int(.75*len(vals))]:+.3f}  "
          f"P90 {vals[int(.9*len(vals))]:+.3f}")
    neg = sum(1 for v in vals if v < 0)
    print(f"     周一更慢的 link：{neg}/{len(vals)} = {neg/len(vals)*100:.1f}%"
          f"（若无效应当约 50%）")
    print(f"\n     最差 5 条（周一最慢）：")
    for lk, v in sorted(per_link.items(), key=lambda x: x[1])[:5]:
        print(f"       link {lk:<10} {v:+.3f} mph")
    print(f"     最好 5 条（周一最快）：")
    for lk, v in sorted(per_link.items(), key=lambda x: -x[1])[:5]:
        print(f"       link {lk:<10} {v:+.3f} mph")

    # ---------- C. 集中度：效应是否被少数 link 放大 ----------
    tot_neg = sum(v for v in vals if v < 0)
    top5_neg = sum(sorted(vals)[:5])
    print(f"\n  == C. 负向效应的集中度 ==")
    print(f"     所有负效应之和 {tot_neg:.1f} mph")
    print(f"     最差 5 条贡献 {top5_neg:.1f} mph = "
          f"{top5_neg/tot_neg*100 if tot_neg else 0:.0f}%")
    print(f"     ⇒ {'少数路段主导' if tot_neg and top5_neg/tot_neg > 0.3 else '效应分散，无明显主导者'}")

    # ---------- D. ★★ 季节分层的逐小时效应 ----------
    #   [!] 为什么必须做：问 1（11 周，全在暑假）给出 +0.2%，
    #       而全量 18 周（含 5–6 月学期）的逐小时表给出 16 个显著的
    #       **周一更快** ⇒ 强烈提示"季节"是混杂因子。
    print(f"\n  == D. ★★ 季节分层的逐小时效应（周一 vs 周中）==")
    SEASONS = [("暑假前（学期中）", date(2026, 5, 11), date(2026, 6, 15)),
               ("暑假中", date(2026, 6, 22), date(2026, 8, 31)),
               ("暑假后（已开学）", date(2026, 9, 7), date(2026, 9, 30))]
    seas_out: dict[str, dict] = {}
    print(f"     {'时段':<10}" + "".join(f"{nm[:8]:>12}" for nm, _a, _b in SEASONS))
    for label, hrs in (("00–06 时", range(0, 7)),
                       ("07–09 时（早高峰）", range(7, 10)),
                       ("10–12 时", range(10, 13)),
                       ("13–17 时", range(13, 18)),
                       ("18–23 时", range(18, 24))):
        line = f"     {label:<10}"
        for nm, a, b in SEASONS:
            A: dict[tuple, list[float]] = defaultdict(list)
            B: dict[tuple, list[float]] = defaultdict(list)
            for k, v in cells.items():
                if k[3] not in hrs:
                    continue
                # k[0] 是 (ISO年, ISO周) ⇒ 用所在周的周一近似定位季节
                y, wk = k[0]
                # 由 ISO 周反推周一日期
                try:
                    mon_d = date.fromisocalendar(y, wk, 1)
                except ValueError:
                    continue
                if not (a <= mon_d <= b):
                    continue
                if k[1] == "Mon":
                    A[(k[0], k[2])].append(v)
                elif k[1] in MID:
                    B[(k[0], k[2])].append(v)
            Am2 = {k: st.mean(v) for k, v in A.items()}
            Bm2 = {k: st.mean(v) for k, v in B.items()}
            com = sorted(set(Am2) & set(Bm2))
            if len(com) < 30:
                line += f"{'—':>12}"
                continue
            df = [Am2[k] - Bm2[k] for k in com]
            med = st.median(df)
            p = wilcoxon_p(df)
            mark = "*" if p < 0.00208 else " "
            line += f"{med:>+11.3f}{mark}"
            seas_out.setdefault(nm, {})[label] = {
                "median_diff": round(med, 4), "p": p, "n": len(com)}
        print(line)
    print(f"     （* = p < 0.00208，Bonferroni 校正后显著）")

    # ---------- E. 春节分层：周一 vs 周二（早高峰）----------
    print(f"\n  == E. 各季节的「周一 vs 周二」早高峰（与问 1 对齐）==")
    for nm, a, b in SEASONS:
        A: dict[tuple, list[float]] = defaultdict(list)
        B: dict[tuple, list[float]] = defaultdict(list)
        for k, v in cells.items():
            if k[3] not in (7, 8, 9):
                continue
            y, wk = k[0]
            try:
                mon_d = date.fromisocalendar(y, wk, 1)
            except ValueError:
                continue
            if not (a <= mon_d <= b):
                continue
            if k[1] == "Mon":
                A[(k[0], k[2])].append(v)
            elif k[1] == "Tue":
                B[(k[0], k[2])].append(v)
        Am3 = {k: st.mean(v) for k, v in A.items()}
        Bm3 = {k: st.mean(v) for k, v in B.items()}
        com = sorted(set(Am3) & set(Bm3))
        if len(com) < 30:
            print(f"     {nm:<20} 样本不足")
            continue
        df = [Am3[k] - Bm3[k] for k in com]
        print(f"     {nm:<20} n={len(com):>5}  中位差 "
              f"{st.median(df):+.3f} mph  "
              f"({st.median(df)/st.mean([Bm3[k] for k in com])*100:+.1f}%)  "
              f"p={wilcoxon_p(df):.2e}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "hourly": hour_rows, "alpha_bonferroni": ALPHA,
        "sig_hours": sig_n,
        "per_link": {k: round(v, 4) for k, v in per_link.items()},
        "neg_share_pct": round(neg / len(vals) * 100, 1) if vals else None,
        "concentration_top5_pct": round(top5_neg / tot_neg * 100, 1)
                                  if tot_neg else None,
        "_注": ("逐小时 24 次检验已做 Bonferroni 校正；"
                "配对键 = (ISO周, link)，周中取 Tue–Thu 均值。"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
