"""Q4：两套倾角怎么互补。

核心指标：**卫星在每个纬度带里待多久**（驻留时间占比）。

为什么用这个而不是"过境次数"
------------------------
掩星事件率正比于卫星在该纬度**停留的时间**（以及 GNSS 几何），
驻留时间分布直接决定"哪里的廓线更密"，比过境计数更贴近任务需求。

输出
----
    results/q4_revisit.json
    figs/q4_revisit.png
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

BANDS = np.arange(-90, 91, 5)
HOURS = 24.0
STEP = 20.0


def band_share(sat: dict) -> np.ndarray:
    """返回各纬度带的驻留时间占比。"""
    t0 = orbit.epoch_to_dt(sat)
    n = int(HOURS * 3600 / STEP)
    lats = np.empty(n)
    for k in range(n):
        la, _ = orbit.subpoint(sat, t0 + timedelta(seconds=k * STEP))
        lats[k] = la
    idx = np.clip(np.digitize(lats, BANDS) - 1, 0, len(BANDS) - 2)
    counts = np.bincount(idx, minlength=len(BANDS) - 1).astype(float)
    return counts / counts.sum()


def passes_per_day(sat: dict) -> int:
    t0 = orbit.epoch_to_dt(sat)
    n = int(HOURS * 3600 / STEP)
    lats = [orbit.subpoint(sat, t0 + timedelta(seconds=k * STEP))[0] for k in range(n)]
    return sum(1 for i in range(1, n) if lats[i - 1] < 0 <= lats[i])


def main() -> int:
    sats = orbit.fetch_tle()
    gA = [s for s in sats if s["inc"] < 60]
    gB = [s for s in sats if s["inc"] > 60]

    out = {"bands": (BANDS[:-1] + 2.5).tolist(), "groups": {}}
    curves = {}
    for name, grp, color in (("A · 50°", gA, "#569cd6"), ("B · 97.6°", gB, "#e8604a")):
        shares = np.mean([band_share(s) for s in grp], axis=0)
        curves[name] = shares
        out["groups"][name] = {
            "n_sats": len(grp),
            "inc": round(float(np.mean([s["inc"] for s in grp])), 3),
            "passes_per_day_per_sat": round(float(np.mean([passes_per_day(s) for s in grp])), 1),
            "share_mid": round(float(shares[(BANDS[:-1] >= 20) & (BANDS[:-1] < 50)].sum()), 3),
            "share_polar": round(float(shares[BANDS[:-1] >= 70].sum()), 3),
            "share_tropical": round(float(shares[BANDS[:-1] < 20].sum()), 3),
        }

    # 反事实：只用 B 组时，中低纬（<50°）的驻留占比是多少
    a_mid = out["groups"]["A · 50°"]["share_mid"] + out["groups"]["A · 50°"]["share_tropical"]
    b_mid = out["groups"]["B · 97.6°"]["share_mid"] + out["groups"]["B · 97.6°"]["share_tropical"]
    out["counterfactual"] = {
        "midlow_share_A": round(a_mid, 3), "midlow_share_B": round(b_mid, 3),
        "ratio": round(a_mid / b_mid, 2),
        "note": "同样的轨道时间，50° 轨道有更大比例待在中低纬",
    }

    (RES / "q4_revisit.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                        encoding="utf-8")

    fig, ax = plt.subplots(figsize=(10.6, 4.8), dpi=160)
    for name, shares in curves.items():
        color = "#569cd6" if name.startswith("A") else "#e8604a"
        ax.bar(BANDS[:-1] + 2.5, shares * 100, width=4.4, color=color, alpha=.72, label=name)
    ax.set_xlabel("纬度（°）")
    ax.set_ylabel("驻留时间占比（%）")
    ax.set_title("同样的时间，两种倾角把它花在不同纬度上", fontsize=12)
    ax.legend(frameon=False)
    ax.grid(alpha=.25, axis="y")
    fig.tight_layout()
    fig.savefig(FIGS / "q4_revisit.png")

    for k, v in out["groups"].items():
        print(f"[{k}] {v['n_sats']} 颗，倾角 {v['inc']}°")
        print(f"   每天过境 {v['passes_per_day_per_sat']} 次/星")
        print(f"   驻留占比：热带 {v['share_tropical']:.1%}  中纬 {v['share_mid']:.1%}  "
              f"高纬(≥70°) {v['share_polar']:.1%}")
    c = out["counterfactual"]
    print(f"\n[反事实] 中低纬驻留占比：50° 组 {c['midlow_share_A']:.1%} vs "
          f"97.6° 组 {c['midlow_share_B']:.1%}（{c['ratio']}×）")
    print(f"[图] {FIGS / 'q4_revisit.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
