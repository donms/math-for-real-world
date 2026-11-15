"""Q3：太阳同步 —— 怎么"锁"住地方时。

推导链
-----
1. 地球扁率让轨道面进动：Ω̇ = -3/2 · J2 · (Re/p)² · n · cos i
2. 太阳同步要求：Ω̇ = +2π/365.2422 天（每年转一圈，跟着太阳走）
3. 解出倾角—高度关系 i(h)
4. 用实测高度对账，再用实测倾角反推"每年漂多少"

输出
----
    results/q3_sso.json
    figs/q3_sso.png
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import rcParams

import orbit

rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
rcParams["axes.unicode_minus"] = False

EP = Path(__file__).resolve().parents[1]
RES = EP / "results"
FIGS = RES / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

TARGET = 2 * math.pi / 365.2422 / orbit.DAY      # rad/s


def sso_inc(alt_km: float) -> float:
    """给定高度，解太阳同步所需倾角（度）。"""
    a = orbit.RE + alt_km
    n = math.sqrt(orbit.MU / a ** 3)
    cos_i = -TARGET / (1.5 * orbit.J2 * (orbit.RE / a) ** 2 * n)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos_i))))


def raan_rate(alt_km: float, inc_deg: float) -> float:
    """给定高度与倾角，升交点进动速率（rad/s）。"""
    a = orbit.RE + alt_km
    n = math.sqrt(orbit.MU / a ** 3)
    return -1.5 * orbit.J2 * (orbit.RE / a) ** 2 * n * math.cos(math.radians(inc_deg))


def main() -> int:
    sats = orbit.fetch_tle()
    gB = [s for s in sats if s["inc"] > 60]

    alts = np.linspace(300, 900, 200)
    incs = [sso_inc(h) for h in alts]

    rows = []
    for s in gB:
        th = sso_inc(s["alt"])
        rows.append({"name": s["name"], "alt": round(s["alt"], 1),
                     "inc_meas": round(s["inc"], 3), "inc_theory": round(th, 3),
                     "delta_deg": round(s["inc"] - th, 3)})

    mean_alt = float(np.mean([s["alt"] for s in gB]))
    mean_inc = float(np.mean([s["inc"] for s in gB]))
    th = sso_inc(mean_alt)
    d = mean_inc - th

    # 0.09° 的偏差 → 地方时漂移
    dr = raan_rate(mean_alt, mean_inc) - raan_rate(mean_alt, th)     # rad/s
    deg_per_day = math.degrees(dr) * orbit.DAY
    min_per_day = deg_per_day / 360.0 * 24 * 60
    out = {
        "mean_alt_km": round(mean_alt, 1), "mean_inc_meas": round(mean_inc, 3),
        "inc_theory": round(th, 3), "delta_deg": round(d, 3),
        "raan_extra_deg_per_day": round(deg_per_day, 4),
        "local_time_drift_min_per_day": round(min_per_day, 3),
        "local_time_drift_min_per_year": round(min_per_day * 365.2422, 1),
        "per_sat": rows,
    }
    (RES / "q3_sso.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                     encoding="utf-8")

    fig, ax = plt.subplots(1, 2, figsize=(12.6, 4.6), dpi=160)

    ax[0].plot(alts, incs, color="#569cd6", lw=2.2, label="太阳同步所需倾角")
    ax[0].scatter([mean_alt], [mean_inc], color="#e8604a", zorder=5, s=60,
                  label=f"实测（{mean_inc:.3f}°）")
    ax[0].scatter([mean_alt], [th], color="#333", zorder=5, s=40, marker="x",
                  label=f"理论（{th:.3f}°）")
    ax[0].set_xlabel("轨道高度（km）")
    ax[0].set_ylabel("倾角（°）")
    ax[0].set_title("太阳同步：高度决定倾角", fontsize=12)
    ax[0].legend(frameon=False, fontsize=9)
    ax[0].grid(alpha=.25)

    # 右：地方时漂移随倾角偏差
    dd = np.linspace(-0.3, 0.3, 121)
    drift = [(math.degrees(raan_rate(mean_alt, mean_inc + x) - raan_rate(mean_alt, th))
              * orbit.DAY) / 360 * 24 * 60 for x in dd]
    ax[1].plot(dd, drift, color="#7fb069", lw=2.2)
    ax[1].axvline(d, color="#e8604a", ls="--", lw=1.2, label=f"实测偏差 {d:+.3f}°")
    ax[1].axhline(0, color="#888", lw=.8)
    ax[1].set_xlabel("倾角相对太阳同步值的偏差（°）")
    ax[1].set_ylabel("地方时漂移（分钟/天）")
    ax[1].set_title("偏离 1°，地方时就锁不住了", fontsize=12)
    ax[1].legend(frameon=False, fontsize=9)
    ax[1].grid(alpha=.25)

    fig.tight_layout()
    fig.savefig(FIGS / "q3_sso.png")

    print(f"[太阳同步] 平均高度 {mean_alt:.1f} km → 理论倾角 {th:.3f}°")
    print(f"[实测]     {mean_inc:.3f}°，比理论高 {d:+.3f}°")
    print(f"[代价]     每年 {(math.degrees(raan_rate(mean_alt, mean_inc)) - math.degrees(TARGET)) * orbit.DAY:.3f} °/天 的多余进动")
    print(f"           地方时漂 {min_per_day:+.3f} 分钟/天 = {min_per_day*365.2422:+.1f} 分钟/年")
    print(f"[图] {FIGS / 'q3_sso.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
