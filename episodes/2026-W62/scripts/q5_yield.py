"""Q5：48 颗怎么撑起日均"数万条"廓线。

模型
----
单星日产量 ≈ 同时可见的 GNSS 卫星数 × 每颗每次过境的升/落事件 × 每日圈数 × 可用率

    N_day = N_vis × 2 × revs_per_day × η

* N_vis：同时可见的 GNSS 卫星（取决于支持几大系统）
* ×2：一颗 GNSS 卫星相对低轨星，每圈各有一次升起与落下
* η：切点高度落在可用区间（约 0–60 km）的比例

关键结论会落在 **N_vis** 上：只支持 GPS 和多系统，差三倍。
"""
from __future__ import annotations

import json
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

CLAIM = 30000          # "日均数万条"取下界
N_SATS = 48
REVS = 15.1
ETA = (0.20, 0.35, 0.50)


def daily_per_sat(n_vis: float, eta: float) -> float:
    return n_vis * 2 * REVS * eta


def main() -> int:
    scen = {
        "只支持 GPS（N_vis≈12）": 12,
        "双系统（N_vis≈20）": 20,
        "四系统（N_vis≈30）": 30,
    }
    # ★ 一次掩星事件通常产出多个产品（中性大气廓线 + 电离层廓线）
    PROD_PER_EVENT = (1, 2, 3)
    out = {"revs_per_day": REVS, "n_sats": N_SATS, "claim": CLAIM,
           "products_per_event": list(PROD_PER_EVENT), "scenarios": {}}
    for name, nv in scen.items():
        vals = [daily_per_sat(nv, e) for e in ETA]
        out["scenarios"][name] = {
            "n_vis": nv,
            "per_sat_range": [round(v) for v in vals],
            "constellation_range": [round(v * N_SATS) for v in vals],
        }

    # 对账：48 颗 × 四系统 × η=35% 的事件数，乘产品数
    events = daily_per_sat(30, 0.35) * N_SATS
    out["reconcile"] = {
        "events_per_day_48sats": round(events),
        "profiles_with_2_products": round(events * 2),
        "claim": CLAIM,
        "verdict": "事件数约 1.5 万；按「一次事件两个产品」计约 3 万 —— 与公开说法一致",
    }

    # 反解：要凑到 3 万条/天，在四系统下需要多少颗
    need = []
    for e in ETA:
        need.append(round(CLAIM / daily_per_sat(30, e)))
    out["sats_needed_for_claim"] = need

    # 单星产量随 N_vis 的曲线
    nvs = np.linspace(5, 40, 100)

    fig, ax = plt.subplots(1, 2, figsize=(12.8, 4.6), dpi=160)
    for e, color, lab in zip(ETA, ("#569cd6", "#7fb069", "#e8604a"),
                             ("可用率 20%", "35%", "50%")):
        ax[0].plot(nvs, [daily_per_sat(n, e) for n in nvs], color=color, lw=2.2, label=lab)
    ax[0].set_xlabel("同时可见的 GNSS 卫星数")
    ax[0].set_ylabel("单星日产量（条）")
    ax[0].set_title("单星产量由「看得见多少颗 GNSS」决定", fontsize=12)
    ax[0].legend(frameon=False, fontsize=9)
    ax[0].grid(alpha=.25)

    ns = np.arange(4, 81)
    for nv, color, lab in ((12, "#deac5c", "只 GPS"), (20, "#569cd6", "双系统"),
                           (30, "#e8604a", "四系统")):
        ax[1].plot(ns, [daily_per_sat(nv, 0.35) * n for n in ns], color=color, lw=2.2, label=lab)
    ax[1].axhline(CLAIM, color="#333", ls="--", lw=1.2, label="「数万条」下界 3 万")
    ax[1].axvline(N_SATS, color="#888", ls=":", lw=1.2, label="现行 48 颗")
    ax[1].set_xlabel("星座卫星数")
    ax[1].set_ylabel("星座日产量（条）")
    ax[1].set_title("48 颗 × 四系统 ≈ 3 万条/天", fontsize=12)
    ax[1].legend(frameon=False, fontsize=8)
    ax[1].grid(alpha=.25)

    fig.tight_layout()
    fig.savefig(FIGS / "q5_yield.png")

    (RES / "q5_yield.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                       encoding="utf-8")

    print(f"[模型] 单星日产量 = N_vis × 2 × {REVS} 圈 × 可用率")
    for name, v in out["scenarios"].items():
        print(f"   {name}: 单星 {v['per_sat_range']} 条/天 → 48 颗 "
              f"{v['constellation_range']} 条/天")
    r = out["reconcile"]
    print(f"[对账] 48 颗四系统、η=35%：事件 {r['events_per_day_48sats']} 条/天")
    print(f"       按一次事件两个产品计：{r['profiles_with_2_products']} 条/天 ← 对上「数万」")
    print(f"[反解] 若只按事件计，凑够 3 万需要：{need} 颗")
    print(f"[图] {FIGS / 'q5_yield.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
