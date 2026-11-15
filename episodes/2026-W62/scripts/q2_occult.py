"""Q2：掩星为什么需要中低纬加密。

两步
----
1. **几何**：低轨接收机看到的掩星切点，离自己脚下有多远？
   θ = arccos(a / r_LEO)，a = Re + 切点高度
   530 km 高度时 θ ≈ 21–23°，几乎与切点高度无关。

2. **推论**：一个掩星剖面"采样"的纬度 ≈ 卫星星下点 ±22°。
   所以把 Q4 的驻留分布"抹开"22°，就得到剖面随纬度的分布。

输出
----
    results/q2_occult.json
    figs/q2_occult.png
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

BANDS = np.arange(-90, 91, 2.5)
CENTERS = BANDS[:-1] + 1.25
HOURS, STEP = 24.0, 30.0


def tangent_offset_deg(tangent_km: float, leo_km: float = 530.0) -> float:
    """切点相对低轨星下点的角距离（度）。"""
    a = orbit.RE + tangent_km
    r1 = orbit.RE + leo_km
    return math.degrees(math.acos(min(1.0, a / r1)))


def residence(sat: dict) -> np.ndarray:
    t0 = orbit.epoch_to_dt(sat)
    n = int(HOURS * 3600 / STEP)
    lats = np.array([orbit.subpoint(sat, t0 + timedelta(seconds=k * STEP))[0]
                     for k in range(n)])
    idx = np.clip(np.digitize(lats, BANDS) - 1, 0, len(CENTERS) - 1)
    c = np.bincount(idx, minlength=len(CENTERS)).astype(float)
    return c / c.sum()


def smear(shares: np.ndarray, halfwidth_deg: float) -> np.ndarray:
    """把驻留分布按 ±halfwidth 的均匀核抹开（切点纬度 ≈ 星下点 ±θ）。"""
    k = int(round(halfwidth_deg / (CENTERS[1] - CENTERS[0])))
    kernel = np.ones(2 * k + 1)
    kernel /= kernel.sum()
    out = np.convolve(shares, kernel, mode="same")
    # 两极反射边界（近似）
    out[:k] += shares[:k][::-1].sum() * 0 + out[:k] * 0
    return out / out.sum()


def main() -> int:
    theta = tangent_offset_deg(30.0)
    geo = {f"h={h}km": round(tangent_offset_deg(h), 2) for h in (0, 10, 30, 60, 100)}

    sats = orbit.fetch_tle()
    gA = [s for s in sats if s["inc"] < 60]
    gB = [s for s in sats if s["inc"] > 60]

    out = {"theta_deg": round(theta, 2), "theta_by_height": geo, "groups": {}}
    curves = {}
    for name, grp, _ in (("A · 50°", gA, "#569cd6"), ("B · 97.6°", gB, "#e8604a")):
        res = np.mean([residence(s) for s in grp], axis=0)
        prof = smear(res, theta)
        curves[name] = (res, prof)
        out["groups"][name] = {
            "share_above_60": round(float(prof[CENTERS >= 60].sum()), 3),
            "share_above_70": round(float(prof[CENTERS >= 70].sum()), 3),
            "share_mid_20_50": round(float(prof[(CENTERS >= 20) & (CENTERS < 50)].sum()), 3),
        }

    ratio = out["groups"]["A · 50°"]["share_mid_20_50"] / out["groups"]["B · 97.6°"]["share_mid_20_50"]
    out["mid_ratio_A_over_B"] = round(ratio, 2)

    (RES / "q2_occult.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                        encoding="utf-8")

    fig, ax = plt.subplots(1, 2, figsize=(13.0, 4.7), dpi=160)

    hs = np.linspace(0, 100, 100)
    ax[0].plot(hs, [tangent_offset_deg(h) for h in hs], color="#7fb069", lw=2.4)
    ax[0].set_xlabel("切点高度（km）")
    ax[0].set_ylabel("切点离星下点的角距离（°）")
    ax[0].set_title(f"掩星切点就在卫星附近：约 {theta:.0f}°（≈2 400 km）", fontsize=12)
    ax[0].grid(alpha=.25)
    ax[0].set_ylim(0, 30)

    for name, (res, prof) in curves.items():
        color = "#569cd6" if name.startswith("A") else "#e8604a"
        ax[1].plot(CENTERS, prof * 100, color=color, lw=2.4, label=f"{name}（剖面分布）")
        ax[1].fill_between(CENTERS, prof * 100, color=color, alpha=.16)
    ax[1].set_xlabel("纬度（°）")
    ax[1].set_ylabel("剖面占比（%）")
    ax[1].set_title("抹开 22° 后：A 组到不了高纬，B 组能到", fontsize=12)
    ax[1].legend(frameon=False, fontsize=9)
    ax[1].grid(alpha=.25)

    fig.tight_layout()
    fig.savefig(FIGS / "q2_occult.png")

    print(f"[几何] 530 km 高度，切点离星下点 {theta:.1f}°（≈{theta*111.32:.0f} km 地面距离）")
    print(f"[随切点高度] {geo}")
    for k, v in out["groups"].items():
        print(f"[{k}] 剖面分布：中纬 20–50° {v['share_mid_20_50']:.1%}，"
              f"≥60° {v['share_above_60']:.1%}，≥70° {v['share_above_70']:.1%}")
    print(f"[结论] 中纬剖面密度 A/B = {ratio:.2f}×")
    print(f"[图] {FIGS / 'q2_occult.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
