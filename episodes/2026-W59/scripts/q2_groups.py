"""Q2：什么样的台风更难报。

四个分组维度
------------
1. **是否转向**：全生命期移向角累计绝对变化 > 阈值（默认 90°；敏感性 45/135）；
2. **强度**：按生命期最大等级分「弱（TD/TS/STS）」「强（TY/STY/SuperTY）」；
3. **生成纬度**：<15°N / 15–25°N / >25°N（用第一个实况点）；
4. **平均移速**：<15 / 15–25 / >25 km/h。

统计
----
* 每个 (维度, 组, 提前量) 报：台风数、配对数、中位误差、**按台风整群 bootstrap 的 95% 区间**；
* 组间差异报**中位比**（如"转向组 72h 误差是直行组的 1.4 倍"）及其区间；
* 样本少的分组只报描述，不下"显著"结论。

输出
----
    results/q2_groups.json
    results/figs/q2_groups.png
    results/figs/q2_turn_dist.png
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from q1_error_growth import load, pairs_of, ts_of  # noqa: E402

EP = Path(__file__).resolve().parents[1]
RES = EP / "results"
FIGS = RES / "figs"

COMPASS = {
    "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5, "E": 90, "ESE": 112.5,
    "SE": 135, "SSE": 157.5, "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5,
    "W": 270, "WNW": 292.5, "NW": 315, "NNW": 337.5,
}
LEADS = [24, 48, 72, 96, 120]
WEAK = {"TD", "TS", "STS"}


def turn_deg(pts: list[dict]) -> float:
    """移向角累计绝对变化（度）。'0'（静止）不计。"""
    ang = [COMPASS[p["move_dir"]] for p in pts if p.get("move_dir") in COMPASS]
    tot = 0.0
    for a, b in zip(ang, ang[1:]):
        d = (b - a + 180) % 360 - 180
        tot += abs(d)
    return tot


def step_max_deg(pts: list[dict]) -> float:
    """单步（6h）最大移向变化——衡量"急转"，比全程累计更能分开两类路径。"""
    ang = [COMPASS[p["move_dir"]] for p in pts if p.get("move_dir") in COMPASS]
    best = 0.0
    for a, b in zip(ang, ang[1:]):
        d = abs((b - a + 180) % 360 - 180)
        best = max(best, d)
    return best


def features(doc: dict) -> dict:
    pts = doc["points"]
    winds = [p["wind"] for p in pts if p.get("wind") is not None]
    sp = [p["move_speed"] for p in pts if p.get("move_speed") is not None]
    grades = [p["grade"] for p in pts if p.get("grade")]
    return {
        "name": doc["meta"]["name_en"],
        "name_cn": doc["meta"]["name_cn"],
        "turn": round(turn_deg(pts), 1),
        "turn_step_max": round(step_max_deg(pts), 1),
        "max_wind": max(winds) if winds else None,
        "max_grade": max(grades, key=lambda g: list(COMPASS).index(g) if False else
                         ["TD", "TS", "STS", "TY", "STY", "SuperTY"].index(g))
        if grades else None,
        "weak": all(g in WEAK for g in grades) if grades else None,
        "lat0": pts[0]["lat"] if pts else None,
        "speed_mean": round(float(np.mean(sp)), 1) if sp else None,
    }


def boot_median(vals: list[float], groups: list[str], n_boot: int = 2000,
                rng=None) -> tuple[float, float, float]:
    """按台风整群 bootstrap 的中位数区间。"""
    rng = rng or np.random.default_rng(7)
    if not vals:
        return (float("nan"),) * 3
    v = np.array(vals)
    med = float(np.median(v))
    names = sorted(set(groups))
    if len(names) < 2:
        return med, med, med
    by = defaultdict(list)
    for g, x in zip(groups, vals):
        by[g].append(x)
    boots = []
    for _ in range(n_boot):
        pick = rng.choice(names, size=len(names), replace=True)
        s = [x for g in pick for x in by[g]]
        boots.append(np.median(s))
    return med, float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    docs = load()
    rows = [r for d in docs for r in pairs_of(d, 3.0)]
    feat = {d["meta"]["name_en"]: features(d) for d in docs}

    print(f"[样本] 台风 {len(docs)}，配对 {len(rows)}")
    turns = sorted((f["turn"], f["name"]) for f in feat.values())
    print("[转向角分布] 最小 %.0f° / 中位 %.0f° / 最大 %.0f°"
          % (turns[0][0], np.median([t[0] for t in turns]), turns[-1][0]))

    rng = np.random.default_rng(20261030)
    out = {"n_typhoons": len(docs), "n_pairs": len(rows), "features": feat,
           "dims": {}}

    for thr in (45, 90, 135):
        key = f"turn_{thr}"
        def g(r, thr=thr):
            return "转向" if feat[r["name"]]["turn"] > thr else "直行"
        out["dims"][key] = summarize(rows, g, rng)
        n_t = sum(1 for f in feat.values() if f["turn"] > thr)
        print(f"[{key}] 转向 {n_t} 个 / 直行 {len(feat)-n_t} 个")

    out["dims"]["strength"] = summarize(
        rows, lambda r: "强（TY+）" if not feat[r["name"]]["weak"] else "弱（≤STS）", rng)
    out["dims"]["lat0"] = summarize(
        rows, lambda r: "低纬 <15°" if feat[r["name"]]["lat0"] < 15 else
        ("中纬 15–25°" if feat[r["name"]]["lat0"] <= 25 else "高纬 >25°"), rng)
    out["dims"]["turnstep"] = summarize(
        rows, lambda r: "急转（单步>40°）" if feat[r["name"]]["turn_step_max"] > 40 else "平稳",
        rng)
    out["dims"]["speed"] = summarize(
        rows, lambda r: "慢 <15" if feat[r["name"]]["speed_mean"] < 15 else
        ("中 15–25" if feat[r["name"]]["speed_mean"] <= 25 else "快 >25"), rng)

    out["corr"] = correlations(rows, feat, rng)

    (RES / "q2_groups.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    print("\n[结果] 各维度 72h 中位误差：")
    for k, d in out["dims"].items():
        line = "  ".join(f"{g}={v['72h']['median']:.0f}km(n={v['72h']['n_tc']})"
                         for g, v in d.items() if v.get("72h"))
        print(f"  {k:12s} {line}")

    plot(out)
    return 0


def summarize(rows: list[dict], group_fn, rng) -> dict:
    by = defaultdict(lambda: defaultdict(list))   # group -> lead -> [(err, name)]
    for r in rows:
        if r["lead"] in LEADS:
            by[group_fn(r)][r["lead"]].append((r["err_km"], r["name"]))
    res = {}
    for g, leads in by.items():
        res[g] = {}
        for lead, items in leads.items():
            vals = [x for x, _ in items]
            names = [n for _, n in items]
            med, lo, hi = boot_median(vals, names, rng=rng)
            res[g][f"{lead}h"] = {
                "median": round(med, 1), "ci": [round(lo, 1), round(hi, 1)],
                "n_pairs": len(vals), "n_tc": len(set(names)),
            }
    return res


def correlations(rows: list[dict], feat: dict, rng) -> dict:
    """每个特征 vs 「该台风 72h 中位误差」的 Spearman 相关（按台风 bootstrap 区间）。"""
    from scipy.stats import spearmanr
    per = defaultdict(lambda: defaultdict(list))
    for r in rows:
        per[r["name"]][r["lead"]].append(r["err_km"])
    names = [n for n in per if 72 in per[n]]
    y = [float(np.median(per[n][72])) for n in names]
    keys = ["turn", "turn_step_max", "max_wind", "lat0", "speed_mean"]
    out = {}
    for k in keys:
        x = [feat[n][k] for n in names]
        if any(v is None for v in x):
            continue
        rho = float(spearmanr(x, y).statistic)
        boots = []
        for _ in range(1000):
            idx = rng.integers(0, len(names), len(names))
            xi = [x[i] for i in idx]; yi = [y[i] for i in idx]
            try:
                boots.append(float(spearmanr(xi, yi).statistic))
            except Exception:
                pass
        out[k] = {"spearman": round(rho, 3),
                  "ci": [round(float(np.percentile(boots, 2.5)), 3),
                         round(float(np.percentile(boots, 97.5)), 3)],
                  "n": len(names)}
    return out


def plot(out: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import rcParams
    rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    rcParams["axes.unicode_minus"] = False

    dims = [("turnstep", "急转（单步转角 >40°）"), ("strength", "强度（生命期最强等级）"),
            ("lat0", "生成纬度"), ("speed", "平均移速")]
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.6), dpi=160)
    for ax, (key, title) in zip(axes.ravel(), dims):
        for g, leads in out["dims"][key].items():
            xs, ys, lo, hi = [], [], [], []
            for lead in LEADS:
                d = leads.get(f"{lead}h")
                if not d:
                    continue
                xs.append(lead); ys.append(d["median"])
                lo.append(d["ci"][0]); hi.append(d["ci"][1])
            if not xs:
                continue
            n0 = next((leads[f"{l}h"]["n_tc"] for l in LEADS if f"{l}h" in leads), "?")
            ax.plot(xs, ys, "o-", lw=1.8, ms=5, label=f"{g}（{n0}）")
            ax.fill_between(xs, lo, hi, alpha=0.13)
        ax.set_title(title, fontsize=12)
        ax.set_xlabel("提前量（h）")
        ax.set_ylabel("中位误差（km）")
        ax.grid(alpha=0.25)
        ax.legend(frameon=False, fontsize=9)
    fig.suptitle("台风路径预报误差：分维度对照（括号内为台风数）", fontsize=13)
    fig.tight_layout()
    fig.savefig(FIGS / "q2_groups.png")
    print(f"[图] {FIGS / 'q2_groups.png'}")

    turns = [f["turn"] for f in out["features"].values()]
    fig2, ax2 = plt.subplots(figsize=(7.4, 3.6), dpi=160)
    ax2.hist(turns, bins=14, color="#569cd6", alpha=0.8)
    for thr, c in ((45, "#8a9bb0"), (90, "#e8604a"), (135, "#deac5c")):
        ax2.axvline(thr, color=c, ls="--", lw=1.4)
        ax2.text(thr, ax2.get_ylim()[1] * 0.9, f" {thr}°", color=c, fontsize=9)
    ax2.set_xlabel("全生命期移向角累计绝对变化（度）")
    ax2.set_ylabel("台风数")
    ax2.set_title("转向判定阈值的选择依据")
    fig2.tight_layout()
    fig2.savefig(FIGS / "q2_turn_dist.png")
    print(f"[图] {FIGS / 'q2_turn_dist.png'}")


if __name__ == "__main__":
    raise SystemExit(main())
