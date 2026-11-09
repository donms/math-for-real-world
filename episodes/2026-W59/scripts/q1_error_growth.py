"""Q1：台风路径预报误差随提前量怎么长。

输入  data/raw/*.json（fetch_typhoon.py 的产物）
输出  results/q1_error_growth.json
      results/figs/q1_error_growth.png

口径（写死在代码里，改动要同步改论文）
--------------------------------------
* 误差 = 预报位置与实况位置的**大圆距离**（haversine，R=6371 km）；
* 实况匹配 = 在 `issue + lead` 附近找**最近**的实况点，容差 3 h（另做 1/6 h 敏感性）；
* 只看 BABJ；
* 同一 (起报时刻, 提前量) 去重；
* 拟合在**每个提前量的中位数**上做（样本量差异大，不能直接对散点做最小二乘）；
* 参数区间用**按台风整群 bootstrap**（同一台风内部的点不独立）。
"""
from __future__ import annotations

import argparse
import json
import math
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit

EP = Path(__file__).resolve().parents[1]
RAW = EP / "data" / "raw"
RES = EP / "results"
FIGS = RES / "figs"

R_EARTH = 6371.0
TOL_H = 3.0            # 默认匹配容差（小时）
LEADS = [6, 12, 18, 24, 36, 48, 60, 72, 96, 120]


def ts_of(s: str) -> float:
    """`YYYYMMDDHHMM`（北京时间）→ epoch 秒。"""
    return time.mktime(time.strptime(s, "%Y%m%d%H%M"))


def haversine(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH * math.asin(min(1.0, math.sqrt(a)))


def load() -> list[dict]:
    out = []
    for p in sorted(RAW.glob("*.json")):
        if p.name == "index.json":
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        out.append(d)
    return out


def pairs_of(doc: dict, tol_h: float) -> list[dict]:
    """构造 (台风, 起报时刻, 提前量) → 误差 的配对样本。"""
    meta, pts = doc["meta"], doc["points"]
    act = sorted((ts_of(p["time"]), p["lon"], p["lat"], p["grade"], p["move_speed"])
                 for p in pts)
    if not act:
        return []
    ats = np.array([a[0] for a in act])

    seen, out = set(), []
    for p in pts:
        issue = ts_of(p["time"])
        for f in p["forecasts"]:
            if f["agency"] != "BABJ" or f["lon"] is None or f["lat"] is None:
                continue
            key = (issue, f["lead"])
            if key in seen:
                continue
            seen.add(key)
            target = issue + f["lead"] * 3600.0
            i = int(np.argmin(np.abs(ats - target)))
            dt_h = abs(ats[i] - target) / 3600.0
            if dt_h > tol_h:
                continue
            a = act[i]
            out.append({
                "name": meta["name_en"], "year": meta["year"], "id": meta["id"],
                "issue": issue, "lead": int(f["lead"]),
                "err_km": haversine(f["lon"], f["lat"], a[1], a[2]),
                "dt_h": round(dt_h, 2),
                "grade": a[3], "move_speed": a[4],
                "f_lon": f["lon"], "f_lat": f["lat"],
                "a_lon": a[1], "a_lat": a[2],
            })
    return out


def stats_by_lead(rows: list[dict]) -> list[dict]:
    by = defaultdict(list)
    for r in rows:
        by[r["lead"]].append(r["err_km"])
    out = []
    for lead in sorted(by):
        v = np.array(by[lead])
        out.append({
            "lead_h": lead, "n": int(v.size),
            "median": round(float(np.median(v)), 1),
            "mean": round(float(v.mean()), 1),
            "q25": round(float(np.percentile(v, 25)), 1),
            "q75": round(float(np.percentile(v, 75)), 1),
            "p90": round(float(np.percentile(v, 90)), 1),
        })
    return out


def fit_models(st: list[dict], rows: list[dict], n_boot: int = 1000) -> dict:
    """在"逐提前量中位数"上拟合线性/幂律；按台风整群 bootstrap 给区间。"""
    h = np.array([s["lead_h"] for s in st], float)
    y = np.array([s["median"] for s in st], float)
    w = np.array([s["n"] for s in st], float)
    w = w / w.sum()

    def f_lin(x, a, b):
        return a + b * x

    def f_pow(x, a, b):
        return a * np.power(x, b)

    def wls(f, p0):
        return curve_fit(f, h, y, p0=p0, sigma=1.0 / np.sqrt(w),
                         maxfev=20000, absolute_sigma=False)[0]

    p_lin, p_pow = wls(f_lin, [0, 1]), wls(f_pow, [5, 0.5])

    def aic(f, p):
        rss = float(np.sum(w * (f(h, *p) - y) ** 2))
        k = len(p)
        return len(h) * math.log(max(rss, 1e-12) / len(h)) + 2 * k

    # 整群 bootstrap：按台风重抽
    names = sorted({r["name"] for r in rows})
    byname = defaultdict(list)
    for r in rows:
        byname[r["name"]].append(r)
    rng = np.random.default_rng(20261030)
    boots = {"lin": [], "pow": []}
    for _ in range(n_boot):
        pick = rng.choice(names, size=len(names), replace=True)
        sample = [r for nm in pick for r in byname[nm]]
        s2 = stats_by_lead(sample)
        if len(s2) < 4:
            continue
        h2 = np.array([s["lead_h"] for s in s2], float)
        y2 = np.array([s["median"] for s in s2], float)
        try:
            pl, _ = curve_fit(f_lin, h2, y2, p0=p_lin, maxfev=8000)
            pp, _ = curve_fit(f_pow, h2, y2, p0=p_pow, maxfev=8000)
            boots["lin"].append(pl.tolist())
            boots["pow"].append(pp.tolist())
        except Exception:                            # noqa: BLE001, S110
            pass

    def ci(arr):
        if not arr:
            return None
        a = np.array(arr)
        return [[round(float(np.percentile(a[:, k], 2.5)), 3),
                 round(float(np.percentile(a[:, k], 97.5)), 3)] for k in range(a.shape[1])]

    return {
        "linear": {"params": [round(float(x), 3) for x in p_lin],
                   "ci95": ci(boots["lin"]), "aic": round(aic(f_lin, p_lin), 1),
                   "predict": [round(float(f_lin(x, *p_lin)), 1) for x in h]},
        "power": {"params": [round(float(x), 3) for x in p_pow],
                  "ci95": ci(boots["pow"]), "aic": round(aic(f_pow, p_pow), 1),
                  "predict": [round(float(f_pow(x, *p_pow)), 1) for x in h]},
        "n_boot": len(boots["lin"]),
    }


def sensitivity(docs: list[dict]) -> list[dict]:
    out = []
    for tol in (1.0, 3.0, 6.0):
        rows = [r for d in docs for r in pairs_of(d, tol)]
        st = {s["lead_h"]: s for s in stats_by_lead(rows)}
        out.append({
            "tol_h": tol, "n": len(rows),
            "median_24": st.get(24, {}).get("median"),
            "median_48": st.get(48, {}).get("median"),
            "median_72": st.get(72, {}).get("median"),
            "median_120": st.get(120, {}).get("median"),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol", type=float, default=TOL_H)
    ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args()

    RES.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    docs = load()
    rows = [r for d in docs for r in pairs_of(d, a.tol)]
    print(f"[样本] 台风 {len(docs)} 个，配对 {len(rows)} 条（容差 {a.tol} h）")
    if not rows:
        print("[!] 没有配对样本")
        return 1

    st = stats_by_lead(rows)
    print("\n提前量   n     中位    均值     P25     P75     P90")
    for s in st:
        print(f"{s['lead_h']:5d}h {s['n']:5d}  {s['median']:7.1f} {s['mean']:7.1f} "
              f"{s['q25']:7.1f} {s['q75']:7.1f} {s['p90']:7.1f}")

    fit = fit_models(st, rows, a.boot)
    print(f"\n线性  E = {fit['linear']['params'][0]} + {fit['linear']['params'][1]}·h"
          f"   AIC {fit['linear']['aic']}   区间 {fit['linear']['ci95']}")
    print(f"幂律  E = {fit['power']['params'][0]}·h^{fit['power']['params'][1]}"
          f"   AIC {fit['power']['aic']}   区间 {fit['power']['ci95']}")

    sen = sensitivity(docs)
    print("\n容差敏感性：")
    for s in sen:
        print(f"  {s['tol_h']:.0f} h → n={s['n']:5d}  24h {s['median_24']}  "
              f"48h {s['median_48']}  72h {s['median_72']}  120h {s['median_120']}")

    out = {"tol_h": a.tol, "n_pairs": len(rows), "n_typhoons": len(docs),
           "by_lead": st, "fit": fit, "sensitivity": sen}
    (RES / "q1_error_growth.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # 每个台风的逐提前量中位数（Q2/Q3 直接用）
    per = defaultdict(lambda: defaultdict(list))
    for r in rows:
        per[r["name"]][r["lead"]].append(r["err_km"])
    per_out = {nm: {str(k): round(float(np.median(v)), 1) for k, v in sorted(d.items())}
               for nm, d in per.items()}
    (RES / "q1_per_typhoon.json").write_text(
        json.dumps(per_out, ensure_ascii=False, indent=2), encoding="utf-8")

    # 图
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import rcParams
    rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    rcParams["axes.unicode_minus"] = False

    h = [s["lead_h"] for s in st]
    med = [s["median"] for s in st]
    lo = [s["q25"] for s in st]
    hi = [s["q75"] for s in st]
    fig, ax = plt.subplots(figsize=(8.2, 5.0), dpi=160)
    ax.fill_between(h, lo, hi, color="#569cd6", alpha=0.16, label="四分位区间")
    ax.plot(h, med, "o-", color="#e8604a", lw=2.2, ms=6, label="中位误差")
    ax.plot(h, fit["power"]["predict"], "--", color="#deac5c", lw=1.6,
            label=f"幂律拟合 E={fit['power']['params'][0]:.1f}·h^{fit['power']['params'][1]:.2f}")
    ax.plot(h, fit["linear"]["predict"], ":", color="#8a9bb0", lw=1.6, label="线性拟合")
    ax.set_xlabel("预报提前量（小时）")
    ax.set_ylabel("位置误差（km）")
    ax.set_title(f"台风路径预报误差随提前量的增长（2026 季 {len(docs)} 个台风，n={len(rows)}）")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIGS / "q1_error_growth.png")
    print(f"\n[图] {FIGS / 'q1_error_growth.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
