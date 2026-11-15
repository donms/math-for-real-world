"""Q1：倾角决定能覆盖到哪。

三件事
-----
1. 星下点最高纬度 ≈ 倾角（无侧视）；
2. 两组的地面轨迹形态：低倾角"掠过中低纬"，高倾角"扫过全球"；
3. 赤道处相邻轨迹的西移量 —— 这就是需要补的"缝"。

输出
----
    results/q1_coverage.json
    figs/q1_coverage.png
"""
from __future__ import annotations

import json
import math
from datetime import timedelta
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


def track(sat: dict, hours: float = 24.0, step_s: float = 30.0):
    """返回 (纬度数组, 经度数组, 时间数组)。"""
    t0 = orbit.epoch_to_dt(sat)
    n = int(hours * 3600 / step_s)
    lats, lons = [], []
    for k in range(n):
        dt = t0 + timedelta(seconds=k * step_s)
        la, lo = orbit.subpoint(sat, dt)
        lats.append(la)
        lons.append(lo)
    return np.array(lats), np.array(lons)


def equator_crossings(lats: np.ndarray, lons: np.ndarray):
    """升交点（由南向北穿过赤道）对应的经度。"""
    out = []
    for i in range(1, len(lats)):
        if lats[i - 1] < 0 <= lats[i]:
            out.append(lons[i])
    return out


def main() -> int:
    sats = orbit.fetch_tle()
    gA = [s for s in sats if s["inc"] < 60]
    gB = [s for s in sats if s["inc"] > 60]
    sA = max(gA, key=lambda s: s["alt"])       # 取高度接近的一组代表
    sB = gB[0]

    out = {"groups": {}}
    fig, axes = plt.subplots(1, 2, figsize=(13.6, 5.2), dpi=150)

    for ax, (name, sat, color) in zip(axes, (("A · 50°", sA, "#569cd6"),
                                             ("B · 97.6°", sB, "#e8604a"))):
        lat, lon = track(sat)
        # 经度断点（跨越 ±180°）分段画
        ax.plot(lon, lat, ".", ms=1.2, color=color, alpha=.75)
        ax.axhline(sat["inc"] if sat["inc"] <= 90 else 180 - sat["inc"],
                   color="#333", ls="--", lw=1.0)
        ax.axhline(-(sat["inc"] if sat["inc"] <= 90 else 180 - sat["inc"]),
                   color="#333", ls="--", lw=1.0)
        ax.set_xlim(-180, 180)
        ax.set_ylim(-90, 90)
        ax.set_xlabel("经度（°）")
        ax.set_ylabel("纬度（°）")
        ax.set_title(f"{name}：24 小时星下点轨迹（{sat['name']}）", fontsize=11)
        ax.grid(alpha=.25)

        cross = equator_crossings(lat, lon)
        d = np.abs(np.diff(cross))
        d = d[d < 180]
        out["groups"][name] = {
            "sat": sat["name"], "inc": round(sat["inc"], 3), "alt_km": round(sat["alt"], 1),
            "max_lat": round(float(np.max(np.abs(lat))), 2),
            "period_min": round(1440.0 / sat["n_revday"], 2),
            "revs_per_day": round(sat["n_revday"], 2),
            "equator_gap_deg": round(float(np.mean(d)), 2) if len(d) else None,
            "equator_gap_km": round(float(np.mean(d)) * 111.32, 0) if len(d) else None,
        }

    fig.suptitle("同一星座、两种倾角：覆盖形态完全不同", fontsize=13)
    fig.tight_layout()
    fig.savefig(FIGS / "q1_coverage.png")

    (RES / "q1_coverage.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    for k, v in out["groups"].items():
        print(f"[{k}] {v['sat']}")
        print(f"   倾角 {v['inc']}°  高度 {v['alt_km']} km  周期 {v['period_min']} min")
        print(f"   星下点最高纬度 {v['max_lat']}°")
        print(f"   赤道相邻轨迹 {v['equator_gap_deg']}° ≈ {v['equator_gap_km']:.0f} km")
    print(f"[图] {FIGS / 'q1_coverage.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
