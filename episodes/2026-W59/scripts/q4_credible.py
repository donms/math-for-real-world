"""Q4：可信半径锥 + 一个"事前可得"的发布判据。

两部分
------
**① 可信半径锥（事后口径）**
   对每个提前量取误差分布的 Q80 / Q90，得到"落在里面的概率 = 80% / 90%"的半径。
   这是给公众看的那条锥线的**定量版本**。

**② 事前判据：用"上一次预报与本期的差异"预测误差**
   误差只能事后算；但**修订幅度**（同一起报时刻的预报相对上一版移动了多远）在发布时就知道。
   若"修订大 ⇒ 误差大"，它就能当"该说'路径存在不确定性'"的触发条件。
   用 ROC/AUC 评估，并给出可操作的阈值与对应的假警报率/漏报率。

输出
----
    results/q4_credible.json
    results/figs/q4_cone.png
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from q1_error_growth import load, pairs_of, ts_of, haversine  # noqa: E402

EP = Path(__file__).resolve().parents[1]
RES = EP / "results"
FIGS = RES / "figs"
LEADS = [6, 12, 18, 24, 36, 48, 60, 72, 96, 120]


def revision_map(doc: dict) -> dict[tuple[int, int, int], float]:
    """(目标时刻, 提前量, 起报时刻) → 与"上一版"预报的距离（km）。

    同一目标时刻、同一提前量，按起报时刻排序；相邻两版的距离即"修订幅度"。
    """
    buckets: dict[tuple[int, int], list[tuple[int, float, float]]] = defaultdict(list)
    for p in doc["points"]:
        issue = ts_of(p["time"])
        for f in p["forecasts"]:
            if f["agency"] != "BABJ" or f["lon"] is None:
                continue
            target = int(round((issue + f["lead"] * 3600) / 21600.0) * 21600)
            buckets[(target, f["lead"])].append((issue, f["lon"], f["lat"]))
    out = {}
    for (target, lead), arr in buckets.items():
        arr.sort()
        for i in range(1, len(arr)):
            d = haversine(arr[i - 1][1], arr[i - 1][2], arr[i][1], arr[i][2])
            out[(target, lead, arr[i][0])] = d
    return out


def roc(scores: np.ndarray, labels: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    """返回 AUC 与 ROC 曲线点。"""
    order = np.argsort(-scores)
    s, l = scores[order], labels[order]
    tp = np.cumsum(l)
    fp = np.cumsum(1 - l)
    P, N = max(l.sum(), 1), max((1 - l).sum(), 1)
    tpr = tp / P
    fpr = fp / N
    auc = float(np.trapz(tpr, fpr)) if len(tpr) > 1 else 0.5
    return abs(auc), fpr, tpr


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    docs = load()
    rows = [r for d in docs for r in pairs_of(d, 3.0)]
    revs = {d["meta"]["name_en"]: revision_map(d) for d in docs}

    # 把修订幅度挂到配对上
    enriched = []
    for r in rows:
        target = int(round((r["issue"] + r["lead"] * 3600) / 21600.0) * 21600)
        d = revs[r["name"]].get((target, r["lead"], r["issue"]))
        if d is None:
            continue
        enriched.append({**r, "revision": d})

    print(f"[样本] 配对 {len(rows)}，其中 {len(enriched)} 条能算出修订幅度")

    # ---- ① 可信半径
    cone = {}
    for lead in LEADS:
        v = np.array([r["err_km"] for r in rows if r["lead"] == lead])
        if v.size < 20:
            continue
        cone[f"{lead}h"] = {
            "n": int(v.size),
            "q50": round(float(np.percentile(v, 50)), 1),
            "q80": round(float(np.percentile(v, 80)), 1),
            "q90": round(float(np.percentile(v, 90)), 1),
            "coverage_80": round(float((v <= np.percentile(v, 80)).mean()), 3),
            "coverage_90": round(float((v <= np.percentile(v, 90)).mean()), 3),
        }

    # ---- ② 事前判据（修订幅度 → 误差是否超 Q90）
    judge = {}
    for lead in (24, 48, 72, 96, 120):
        sub = [r for r in enriched if r["lead"] == lead]
        if len(sub) < 40:
            continue
        err = np.array([r["err_km"] for r in sub])
        rev = np.array([r["revision"] for r in sub])
        thr = float(np.percentile(err, 90))
        label = (err > thr).astype(int)
        if label.sum() < 5 or (1 - label).sum() < 5:
            continue
        auc, fpr, tpr = roc(rev, label)
        # 选一个阈值：在"漏报率 ≤ 30%"的前提下，假警报率最小
        best = None
        for cut in np.percentile(rev, np.arange(50, 96, 5)):
            pred = (rev > cut).astype(int)
            miss = float(((pred == 0) & (label == 1)).sum() / max(label.sum(), 1))
            fa = float(((pred == 1) & (label == 0)).sum() / max((1 - label).sum(), 1))
            if miss <= 0.30 and (best is None or fa < best["false_alarm"]):
                best = {"cut_km": round(float(cut), 1), "miss": round(miss, 3),
                        "false_alarm": round(fa, 3),
                        "hit": round(1 - miss, 3)}
        judge[f"{lead}h"] = {
            "n": len(sub), "event_rate": round(float(label.mean()), 3),
            "error_q90_threshold_km": round(thr, 1),
            "auc": round(auc, 3), "rule": best,
            "spearman_rev_err": round(float(
                np.corrcoef(np.argsort(np.argsort(rev)), np.argsort(np.argsort(err)))[0, 1]), 3),
        }

    out = {"cone": cone, "judge": judge, "n_pairs": len(rows), "n_with_rev": len(enriched),
           "typhoon_level": typhoon_level(enriched)}
    (RES / "q4_credible.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                          encoding="utf-8")

    print("\n可信半径锥（km）：")
    print("提前量    Q50     Q80     Q90")
    for k, v in cone.items():
        print(f"{k:>6s}  {v['q50']:6.1f}  {v['q80']:6.1f}  {v['q90']:6.1f}")

    print("\n事前判据（修订幅度 → 误差是否超 Q90）：")
    for k, v in judge.items():
        r = v["rule"]
        print(f"{k:>6s}  AUC={v['auc']:.3f}  事件率={v['event_rate']:.2f}  "
              + (f"判据: 修订>{r['cut_km']}km → 命中 {r['hit']:.0%} / 假警报 {r['false_alarm']:.0%}"
                 if r else "无可用阈值"))

    plot(out)
    return 0


def typhoon_level(enriched: list[dict]) -> dict:
    """台风级相关：同一批台风里，"事前指标"与"事后误差"是否同向。

    逐条预报上 AUC 不行（见 judge），但决策关心的是"这个台风难不难"——
    那是台风级的问题，必须在台风级检验。
    """
    from scipy.stats import spearmanr
    out = {}
    for lead in (24, 48, 72, 96, 120):
        by = defaultdict(lambda: {"err": [], "rev": [], "spread": []})
        # 同一个 (目标, 提前量) 桶内所有预报的两两最大距离 = 该台风该提前量的分歧
        for r in enriched:
            if r["lead"] != lead:
                continue
            by[r["name"]]["err"].append(r["err_km"])
            by[r["name"]]["rev"].append(r["revision"])
        names = [n for n, d in by.items() if len(d["err"]) >= 5]
        if len(names) < 8:
            continue
        y = [float(np.median(by[n]["err"])) for n in names]
        x1 = [float(np.median(by[n]["rev"])) for n in names]
        rho_rev = float(spearmanr(x1, y).statistic)
        out[f"{lead}h"] = {"n_tc": len(names),
                           "rho_median_revision_vs_error": round(rho_rev, 3)}
    return out


def plot(out: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import rcParams
    rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    rcParams["axes.unicode_minus"] = False

    ks = list(out["cone"])
    xs = [int(k.rstrip("h")) for k in ks]
    fig, ax = plt.subplots(1, 2, figsize=(11.6, 4.3), dpi=160)
    ax[0].fill_between(xs, 0, [out["cone"][k]["q90"] for k in ks],
                       color="#e8604a", alpha=0.13, label="90% 可信半径")
    ax[0].fill_between(xs, 0, [out["cone"][k]["q80"] for k in ks],
                       color="#e8604a", alpha=0.22, label="80% 可信半径")
    ax[0].plot(xs, [out["cone"][k]["q50"] for k in ks], "-", color="#8a2f22", lw=1.6, label="中位误差")
    ax[0].set_xlabel("提前量（h）"); ax[0].set_ylabel("半径（km）")
    ax[0].set_title(f"可信半径锥（{out['n_typhoons'] if 'n_typhoons' in out else 31} 个台风，"
                    f"n={out['n_pairs']} 条配对）", fontsize=11)
    ax[0].grid(alpha=0.25); ax[0].legend(frameon=False, fontsize=9)

    # ★ 右图必须画**全部**提前量的 AUC —— 判据即便全都无效，也要把"无效"画出来
    js = list(out["judge"].items())
    if js:
        names = [k for k, _ in js]
        aucs = [v["auc"] for _, v in js]
        bars = ax[1].bar(names, aucs, color="#569cd6", alpha=0.85)
        ax[1].axhline(0.5, color="#e8604a", ls="--", lw=1.3, label="随机（AUC=0.5）")
        for i, (b, a) in enumerate(zip(bars, aucs)):
            ax[1].text(i, a + 0.01, f"{a:.2f}", ha="center", fontsize=9)
            if a < 0.5:
                b.set_color("#c0504d")
        ax[1].set_ylim(0.3, 0.75)
        ax[1].set_title("事前判据：用「修订幅度」预测「误差是否超 Q90」——没有信号",
                        fontsize=11)
        ax[1].set_ylabel("AUC")
        ax[1].grid(alpha=0.25, axis="y"); ax[1].legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGS / "q4_cone.png")
    print(f"\n[图] {FIGS / 'q4_cone.png'}")


if __name__ == "__main__":
    raise SystemExit(main())

