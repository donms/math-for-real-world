"""Q3：一正一反两个案例——"真的难报"与"被误判为难报"。

* **正例（难）**：CHAN-HOM —— 生命期最强只有 TS、生成于 19.5°N，正好落在 Q2 找到的两个风险因子上；
* **反例（被误判）**：CHAMPI（蔷琵）—— SuperTY、生成于 10.5°N，媒体称"路径成悬念"。

两个量必须分开
--------------
1. **误差**：预报位置 vs 实况位置的距离（事后才知道）；
2. **分歧**：同一目标时刻、不同起报时刻的预报彼此最大距离（事前就能看到）。

输出
----
    results/q3_case.json
    results/figs/q3_case.png
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from q1_error_growth import load, pairs_of, ts_of, haversine  # noqa: E402
from q2_groups import features  # noqa: E402

EP = Path(__file__).resolve().parents[1]
RES = EP / "results"
FIGS = RES / "figs"

HARD = "CHAN-HOM"
EASY = "CHAMPI"
CASES = {HARD: "最难报（CHAN-HOM）", EASY: "蔷琵（被误判为难报）"}
LEADS = [6, 12, 18, 24, 36, 48, 60, 72, 96, 120]


def spread_by_lead(doc: dict) -> dict[int, list[float]]:
    """同一目标时刻、不同起报时刻的预报之间最大两两距离（km）。"""
    bucket: dict[tuple[int, int], list[tuple[float, float]]] = defaultdict(list)
    for p in doc["points"]:
        issue = ts_of(p["time"])
        for f in p["forecasts"]:
            if f["agency"] != "BABJ" or f["lon"] is None:
                continue
            target = int(round((issue + f["lead"] * 3600) / 21600.0) * 21600)
            bucket[(target, f["lead"])].append((f["lon"], f["lat"]))
    out: dict[int, list[float]] = defaultdict(list)
    for (_, lead), pts in bucket.items():
        if len(pts) < 2:
            continue
        out[lead].append(max(haversine(a[0], a[1], b[0], b[1])
                             for i, a in enumerate(pts) for b in pts[i + 1:]))
    return out


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    docs = load()
    by_name = {d["meta"]["name_en"]: d for d in docs}
    feat = {n: features(d) for n, d in by_name.items()}
    rows = [r for d in docs for r in pairs_of(d, 3.0)]

    per = defaultdict(lambda: defaultdict(list))
    for r in rows:
        per[r["name"]][r["lead"]].append(r["err_km"])
    med = {n: {l: float(np.median(v)) for l, v in d.items()} for n, d in per.items()}

    rank = {}
    for lead in LEADS:
        vals = sorted(med[n][lead] for n in med if lead in med[n])
        if len(vals) < 5:
            continue
        entry = {"season_median": round(float(np.median(vals)), 1), "n_tc": len(vals)}
        mu, sd = float(np.mean(vals)), float(np.std(vals, ddof=1))
        for nm in CASES:
            if nm not in med or lead not in med[nm]:
                continue
            x = med[nm][lead]
            entry[nm] = {
                "median": round(x, 1),
                "percentile": round(100.0 * sum(v <= x for v in vals) / len(vals), 0),
                "z": round((x - mu) / sd, 2) if sd > 0 else None,
                "n_pairs": len(per[nm][lead]),
            }
        rank[f"{lead}h"] = entry

    sp = {n: spread_by_lead(d) for n, d in by_name.items()}
    spread = {}
    for lead in LEADS:
        others = [np.median(v[lead]) for n, v in sp.items() if n not in CASES
                  and lead in v and len(v[lead]) >= 2]
        if len(others) < 5:
            continue
        e = {"season_median": round(float(np.median(others)), 1),
             "season_p90": round(float(np.percentile(others, 90)), 1), "n_tc": len(others)}
        for nm in CASES:
            if nm in sp and sp[nm].get(lead):
                v = float(np.median(sp[nm][lead]))
                e[nm] = {"median": round(v, 1),
                         "ratio": round(v / max(np.median(others), 1e-6), 2)}
        spread[f"{lead}h"] = e

    out = {"cases": CASES, "features": {n: feat[n] for n in CASES},
           "error_rank": rank, "spread": spread}
    (RES / "q3_case.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                      encoding="utf-8")

    print("案例特征：")
    for nm, lab in CASES.items():
        f = feat[nm]
        print(f"  {nm:9s} {lab}：最强 {f['max_grade']}({f['max_wind']} m/s)  "
              f"生成 {f['lat0']}°N  平均移速 {f['speed_mean']}  单步最大转角 {f['turn_step_max']}°")
    print("\n提前量   季节中位   " + "   ".join(f"{n}(分位)" for n in CASES))
    for k, v in rank.items():
        cells = []
        for n in CASES:
            cells.append(f"{v[n]['median']:7.1f} ({v[n]['percentile']:3.0f}%)" if n in v else "     —")
        print(f"{k:>6s}  {v['season_median']:8.1f}   " + "   ".join(cells))
    print("\n提前量   季节分歧中位   " + "   ".join(CASES))
    for k, v in spread.items():
        cells = [f"{v[n]['median']:6.1f}({v[n]['ratio']:.2f}×)" if n in v else "    —" for n in CASES]
        print(f"{k:>6s}  {v['season_median']:10.1f}   " + "   ".join(cells))

    plot(out)
    return 0


def plot(out: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import rcParams
    rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    rcParams["axes.unicode_minus"] = False

    docs = load()
    rows = [r for d in docs for r in pairs_of(d, 3.0)]
    per = defaultdict(lambda: defaultdict(list))
    for r in rows:
        per[r["name"]][r["lead"]].append(r["err_km"])

    leads, q25, q50, q75 = [], [], [], []
    series = {n: [] for n in CASES}
    for lead in LEADS:
        vals = [np.median(per[n][lead]) for n in per if lead in per[n]]
        if len(vals) < 5:
            continue
        leads.append(lead)
        q25.append(np.percentile(vals, 25)); q50.append(np.median(vals))
        q75.append(np.percentile(vals, 75))
        for n in CASES:
            series[n].append(np.median(per[n][lead]) if n in per and lead in per[n] else np.nan)

    colors = {HARD: "#e8604a", EASY: "#569cd6"}
    fig, ax = plt.subplots(1, 2, figsize=(12.4, 4.6), dpi=160)
    ax[0].fill_between(leads, q25, q75, color="#8a9bb0", alpha=0.16, label="同季四分位")
    ax[0].plot(leads, q50, "-", color="#8a9bb0", lw=1.5, label="同季中位")
    for n, lab in CASES.items():
        ax[0].plot(leads, series[n], "o-", color=colors[n], lw=2.2, ms=5, label=lab)
    ax[0].set_title("误差：真的难 vs 被误判为难", fontsize=12)
    ax[0].set_xlabel("提前量（h）"); ax[0].set_ylabel("中位误差（km）")
    ax[0].grid(alpha=0.25); ax[0].legend(frameon=False, fontsize=8.5)

    ks = list(out["spread"])
    xs = [int(k.rstrip("h")) for k in ks]
    ax[1].plot(xs, [out["spread"][k]["season_median"] for k in ks], "-",
               color="#8a9bb0", lw=1.5, label="同季中位")
    for n, lab in CASES.items():
        ys = [out["spread"][k].get(n, {}).get("median", np.nan) for k in ks]
        if any(not np.isnan(y) for y in ys):
            ax[1].plot(xs, ys, "o-", color=colors[n], lw=2.0, ms=5, label=lab)
    ax[1].set_title("预报分歧：同一目标时刻、不同起报时刻彼此的距离", fontsize=12)
    ax[1].set_xlabel("提前量（h）"); ax[1].set_ylabel("最大两两距离（km）")
    ax[1].grid(alpha=0.25); ax[1].legend(frameon=False, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(FIGS / "q3_case.png")
    print(f"\n[图] {FIGS / 'q3_case.png'}")


if __name__ == "__main__":
    raise SystemExit(main())
