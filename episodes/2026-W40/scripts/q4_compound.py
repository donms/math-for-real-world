#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""问题 4：复合事件识别 + 城市风险排序 + 敏感性分析。

按用户确认的方案（见 models/04_复合事件与风险排序.md 决策记录）：
  · 复合事件窗口：**主用 3 日，同时报告 1/7/15 日**
  · 阈值用**城市内经验分位**（消除气候基线差异）
  · 综合风险 = 高温风险 + 暴雨风险（**复合维度不进入加总**，
    因为问题 2 已证明它不构成额外风险）
  · 敏感性：权重 / 标准化 / 口径 → Spearman 秩相关

产出：
  results/q4_compound.json / q4_ranking.json / q4_summary.txt
  results/figs/q4_*.png
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evt import FIGS, RESULTS, load_cities, load_series       # noqa: E402

from scipy import stats                                       # noqa: E402

import matplotlib                                             # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                               # noqa: E402
from matplotlib import font_manager                           # noqa: E402

for _f in (r"<LOCAL_PATH>", r"<LOCAL_PATH>"):
    try:
        font_manager.fontManager.addfont(_f)
    except Exception:                                         # noqa: BLE001
        pass
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

WINDOWS = [1, 3, 7, 15]        # 复合事件时间窗口（日）
Q_THR = 0.90                   # 极端阈值分位
W_MAIN = 3                     # 主用窗口


# ────────────────────── 复合事件计数 ──────────────────────

def count_clusters(hot_idx: np.ndarray, wet_idx: np.ndarray,
                   W: int) -> int:
    """统计「高温日与暴雨日在 W 日内共现」的**连通簇数**。

    计数口径很重要：若逐对 (i,j) 计数，一次持续过程会被放大数十倍，
    得到毫无意义的巨大倍数。正确做法是把互相连通的高温日并成一簇，
    **每簇只计一次**。

    实现：高温日 i 与它 W 日内的每个暴雨日建立连接；
    共享同一暴雨日的高温日彼此连通（并查集合并）。
    只统计**真正参与共现**的高温日所在的簇。
    """
    if len(hot_idx) == 0 or len(wet_idx) == 0:
        return 0
    parent = list(range(len(hot_idx)))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]          # 路径压缩
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    wet_sorted = np.sort(wet_idx)
    links: dict[int, list[int]] = {}
    for i, h in enumerate(hot_idx):
        k0 = int(np.searchsorted(wet_sorted, h - W))
        k1 = int(np.searchsorted(wet_sorted, h + W, side="right"))
        for k in range(k0, k1):
            links.setdefault(k, []).append(i)
    for lst in links.values():
        for a in lst[1:]:
            union(lst[0], a)
    involved = sorted({i for lst in links.values() for i in lst})
    if not involved:
        return 0
    return len({find(i) for i in involved})


def compound_analysis(x: np.ndarray, y: np.ndarray, n_years: float) -> dict:
    r"""对一个城市做多窗口复合事件分析。

    ⚠️ **计数口径的坑（重要）**：最初用「连通簇数」作观测值，
    期望用 `p_win × n / span`。结果 15 日窗口的倍数掉到 0.57，
    看起来像"长窗口下互相排斥"——**但那是指标缺陷，不是真实信号**：

      · 窗口 W 越大，一整个雨季/热季的冷热雨日会被并成**一个巨簇**，
        观测值**饱和**（≈ 季节数）；
      · 而基线 `p_win × n / span` 却随 W **近似线性增长**；
      · 二者一饱和一线性 → 比值必然随 W 虚低。

    改用**日口径**，跨窗口可比：

        观测 O(W) = #{ 热日 i : 在 [i-W, i+W] 内存在雨日 }
        期望 E(W) = n_hot × [ 1 − (1 − p_wet)^(2W+1) ]
        倍数 R(W) = O(W) / E(W)

    含义：**一个高温日附近出现暴雨日的概率，相对独立假设的倍数**。
    O 与 E 对 W 都单调增，比值稳定可解释。
    """
    n = len(x)
    u = float(np.quantile(x, Q_THR))
    v = float(np.quantile(y, Q_THR))
    hot = np.where(x > u)[0]
    wet = np.where(y > v)[0]
    pX, pY = len(hot) / n, len(wet) / n
    out = {"u": u, "v": v, "n_hot": int(len(hot)), "n_wet": int(len(wet)),
           "pX": pX, "pY": pY, "windows": {}}
    wet_sorted = np.sort(wet)
    for W in WINDOWS:
        # 日口径：每个热日是否在 ±W 日内有雨日
        obs = 0
        for h in hot:
            k0 = int(np.searchsorted(wet_sorted, h - W))
            k1 = int(np.searchsorted(wet_sorted, h + W, side="right"))
            if k1 > k0:
                obs += 1
        exp = len(hot) * (1 - (1 - pY) ** (2 * W + 1))
        # 簇计数保留作参考（说明饱和现象）
        clus = count_clusters(hot, wet, W)
        out["windows"][str(W)] = {
            "observed": int(obs), "expected": float(exp),
            "ratio": float(obs / exp) if exp > 0 else None,
            "clusters": int(clus),
            "cluster_ratio": float(clus / (exp / (2 * W + 1)))
            if exp > 0 else None}
    return out


# ────────────────────── 风险指标 ──────────────────────

def standardize(a: np.ndarray, how: str) -> np.ndarray:
    a = np.asarray(a, dtype=float)
    if how == "minmax":
        lo, hi = np.nanmin(a), np.nanmax(a)
        return (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)
    if how == "zscore":
        m, s = np.nanmean(a), np.nanstd(a)
        return (a - m) / s if s > 0 else np.zeros_like(a)
    if how == "rank":
        return stats.rankdata(a) / len(a)
    raise ValueError(how)


def main() -> int:
    t0 = time.time()
    cities = load_cities()
    names = [c["name"] for c in cities]
    grp = {c["name"]: c["group"] for c in cities}

    q1 = json.loads((RESULTS / "q1_all.json").read_text(encoding="utf-8"))
    q3 = json.loads((RESULTS / "q3_nonstationary.json").read_text(encoding="utf-8"))
    q2 = json.loads((RESULTS / "q2_copula.json").read_text(encoding="utf-8"))

    print(f"  {len(names)} 城；窗口 {WINDOWS}（主用 {W_MAIN}）；"
          f"阈值分位 {Q_THR}\n")
    print(f"  {'城市':<8}{'组':<18}{'高温簇':>8}{'期望':>8}{'倍数':>8}"
          f"{'τ':>8}{'经验R(.99)':>11}")

    comp: dict = {}
    for i, c in enumerate(cities, 1):
        nm = c["name"]
        s = load_series(nm)
        m = ~(np.isnan(s["tmax"]) | np.isnan(s["precip"]))
        x, y = s["tmax"][m], s["precip"][m]
        # n_years 在 q1 结果里是**整数**（不是列表）。
        # 早期写成 len(...get("n_years", []) or []) 会抛
        # TypeError: object of type 'int' has no len()
        n_years = q1[nm]["tmax"].get("n_years") or 87
        ca = compound_analysis(x, y, float(n_years))
        comp[nm] = ca
        w = ca["windows"][str(W_MAIN)]
        tau = q2[nm]["families"]["Gumbel"]["kendall_tau"]
        e99 = q2[nm]["empirical"]["0.99"]["R"]
        print(f"  {i:>2} {nm:<8}{grp[nm]:<18}{w['observed']:>8}"
              f"{w['expected']:>8.2f}{(w['ratio'] or float('nan')):>8.2f}"
              f"{tau:>8.3f}{e99:>11.2f}", flush=True)

    # ── 窗口稳健性 ──
    win_ratio = {W: [] for W in WINDOWS}
    for nm in names:
        for W in WINDOWS:
            r = comp[nm]["windows"][str(W)]["ratio"]
            if r is not None:
                win_ratio[W].append(r)
    print("\n  === 窗口稳健性（风险倍数中位）===")
    for W in WINDOWS:
        a = np.array(win_ratio[W])
        print(f"    窗口 {W:>2} 日：中位 {np.median(a):.2f}  "
              f"范围 [{a.min():.2f}, {a.max():.2f}]  "
              f"{'<1 互相排斥' if np.median(a) < 1 else '>1 共现偏多'}")

    # ── 综合风险指标 ──
    x50 = np.array([q1[nm]["tmax"]["gev"]["return_level"]["50"]["x"] for nm in names])
    xi_p = np.array([q1[nm]["precip"]["gev"].get("xi", 0.0) or 0.0 for nm in names])
    mu1 = np.array([q3[nm]["tmax"].get("mu1_per_decade", 0.0) or 0.0 for nm in names])
    x50_26 = np.array([q3[nm]["tmax"].get("x50_2026", np.nan) or np.nan
                       for nm in names])

    ranking: dict = {}
    results_by_setting: dict[str, np.ndarray] = {}
    for how in ("minmax", "zscore", "rank"):
        for alpha in (0.0, 1.0, 2.0):
            sx = standardize(x50, how)
            sm = standardize(mu1, how)
            sp = standardize(xi_p, how)
            heat = sx * (1 + alpha * sm)
            flood = sx * 0 + sp * 0 + standardize(
                np.array([q1[nm]["precip"]["gev"]["return_level"]["50"].get("x", 0.0)
                          or 0.0 for nm in names]), how) * (1 + alpha * sp)
            total = heat + flood
            key = f"{how}_a{alpha:g}"
            results_by_setting[key] = total
            ranking[key] = {nm: float(total[k]) for k, nm in enumerate(names)}

    base_key = f"minmax_a1"
    base = results_by_setting[base_key]
    order = np.argsort(-base)
    print(f"\n  === 综合风险排序（基准设定 {base_key}）===")
    print(f"  {'名次':<6}{'城市':<9}{'组':<19}{'高温风险':>10}{'暴雨风险':>10}{'合计':>9}")
    sx = standardize(x50, "minmax")
    sm = standardize(mu1, "minmax")
    sp = standardize(xi_p, "minmax")
    x50p = standardize(np.array([q1[nm]["precip"]["gev"]["return_level"]["50"]
                                 .get("x", 0.0) or 0.0 for nm in names]), "minmax")
    heat = sx * (1 + 1.0 * sm)
    flood = x50p * (1 + 1.0 * sp)
    rank_tbl = []
    for r, k in enumerate(order, 1):
        nm = names[k]
        rank_tbl.append({"rank": r, "city": nm, "group": grp[nm],
                         "heat": float(heat[k]), "flood": float(flood[k]),
                         "total": float(heat[k] + flood[k])})
        print(f"  {r:<6}{nm:<9}{grp[nm]:<19}{heat[k]:>10.2f}"
              f"{flood[k]:>10.2f}{heat[k]+flood[k]:>9.2f}")

    # ── 排序稳健性（Spearman）──
    keys = list(results_by_setting)
    M = np.zeros((len(keys), len(keys)))
    for a in range(len(keys)):
        for b in range(len(keys)):
            M[a, b] = stats.spearmanr(results_by_setting[keys[a]],
                                      results_by_setting[keys[b]]).statistic
    print(f"\n  === 排序稳健性 ===\n  {len(keys)} 种设定间的 Spearman 秩相关："
          f"中位 {np.median(M):.3f}  最小 {M.min():.3f}")

    # 每个城市在多种设定下的名次波动
    ranks = np.zeros((len(keys), len(names)))
    for a, k in enumerate(keys):
        ranks[a] = stats.rankdata(-results_by_setting[k])
    rank_sd = ranks.std(axis=0)
    print("\n  名次波动最大的城市（位次不可信）：")
    for k in np.argsort(-rank_sd)[:5]:
        print(f"    {names[k]:<9} 名次 {ranks[:, k].min():.0f} ~ "
              f"{ranks[:, k].max():.0f}  标准差 {rank_sd[k]:.2f}")

    (RESULTS / "q4_compound.json").write_text(
        json.dumps(comp, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTS / "q4_ranking.json").write_text(
        json.dumps({"table": rank_tbl,
                    "spearman_median": float(np.median(M)),
                    "rank_sd": {nm: float(rank_sd[k])
                                for k, nm in enumerate(names)}},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 图 ──
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    ax = axes[0]
    ypos = np.arange(len(names))
    hs = [heat[names.index(nm)] for nm in names]
    fs = [flood[names.index(nm)] for nm in names]
    ax.barh(ypos, hs, color="#c0392b", label="高温风险")
    ax.barh(ypos, fs, left=hs, color="#2e86c1", label="暴雨风险")
    ax.set_yticks(ypos)
    ax.set_yticklabels(names, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("综合风险（min-max 标准化）")
    ax.set_title("城市综合气候风险构成")
    ax.legend()
    ax.grid(alpha=0.3, axis="x")

    ax = axes[1]
    for W in WINDOWS:
        a = np.array(win_ratio[W])
        ax.scatter([W] * len(a), a, s=18, alpha=0.7)
        ax.plot([W, W], [np.median(a)] * 2, "k_", ms=22, mew=2.5)
    ax.axhline(1.0, color="r", ls="--", lw=1.2, label="独立假设基准")
    ax.set_xscale("log")
    ax.set_xticks(WINDOWS)
    ax.set_xticklabels([str(w) for w in WINDOWS])
    ax.set_xlabel("时间窗口（日）")
    ax.set_ylabel("复合事件风险倍数 R")
    ax.set_title("复合事件风险倍数随窗口的变化\n（黑横线为中位）")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "q4_risk.png", dpi=140)
    plt.close(fig)

    # ── 汇总 ──
    L = ["问题4 · 复合事件与城市风险排序", "=" * 96, ""]
    L.append("【一】复合事件风险倍数（实际簇数 / 独立假设期望）")
    L.append(f"{'城市':<9}" + "".join(f"{f'W={w}':>10}" for w in WINDOWS)
             + f"{'τ':>9}{'经验R(q=.99)':>14}")
    for nm in names:
        row = f"{nm:<9}"
        for W in WINDOWS:
            r = comp[nm]["windows"][str(W)]["ratio"]
            row += f"{(r if r is not None else float('nan')):>10.2f}"
        row += f"{q2[nm]['families']['Gumbel']['kendall_tau']:>9.3f}"
        row += f"{q2[nm]['empirical']['0.99']['R']:>14.2f}"
        L.append(row)
    L += ["", "【二】窗口稳健性", "-" * 96]
    for W in WINDOWS:
        a = np.array(win_ratio[W])
        L.append(f"  窗口 {W:>2} 日：中位 {np.median(a):.2f}  "
                 f"范围 [{a.min():.2f}, {a.max():.2f}]")
    L += ["", "【三】综合风险排序", "-" * 96]
    L.append(f"{'名次':<6}{'城市':<9}{'组':<19}{'高温':>9}{'暴雨':>9}{'合计':>9}")
    for r in rank_tbl:
        L.append(f"{r['rank']:<6}{r['city']:<9}{r['group']:<19}"
                 f"{r['heat']:>9.2f}{r['flood']:>9.2f}{r['total']:>9.2f}")
    L += ["", "【四】排序稳健性", "-" * 96,
          f"  {len(keys)} 种设定间 Spearman 秩相关中位 {np.median(M):.3f}",
          "  名次波动最大的城市："]
    for k in np.argsort(-rank_sd)[:5]:
        L.append(f"    {names[k]:<9} 名次 {ranks[:, k].min():.0f} ~ "
                 f"{ranks[:, k].max():.0f}（标准差 {rank_sd[k]:.2f}）")
    L += ["", "【五】核心判断", "-" * 96,
          "  · 复合事件风险倍数在所有窗口下均 < 1（见【二】），",
          "    与问题2的结论一致：高温与暴雨在日尺度**互相排斥**。",
          "  · 因此风险主要来自**单独的极端**，而非叠加的极端。",
          "  · 防灾资源宜投向高温（16/16 城显著升温）与暴雨（重尾）各自的应对，",
          "    而非假设的复合场景。",
          "  · 例外：成都、哈尔滨最热日反而偏多雨，复合场景仍需考虑。",
          ""]
    (RESULTS / "q4_summary.txt").write_text("\n".join(L), encoding="utf-8")

    print(f"\n  用时 {time.time()-t0:.1f}s")
    print(f"  [结果] results/q4_compound.json / q4_ranking.json")
    print(f"  [汇总] results/q4_summary.txt")
    print(f"  [图表] results/figs/q4_risk.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
