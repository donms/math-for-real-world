"""Q1 + Q2：回撤定义与十年三次的账本。

Q1：画出十年的水下曲线（回撤随时间）
Q2：带滞回的事件切分 + 阈值敏感性
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams

import mkt

rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
rcParams["axes.unicode_minus"] = False

EP = Path(__file__).resolve().parents[1]
RES = EP / "results"
FIGS = RES / "figs"
FIGS.mkdir(parents=True, exist_ok=True)


def main() -> int:
    gold = mkt.load_cached("gold_usd", mkt.yahoo, "GC=F")
    dates = [d for d, _ in gold]
    px = [v for _, v in gold]
    dd = mkt.drawdown_series(px)

    # --- Q1 水下曲线 ---
    import numpy as np
    x = np.arange(len(px))

    fig, ax = plt.subplots(2, 1, figsize=(13.2, 6.4), dpi=160,
                           gridspec_kw={"height_ratios": [1.15, 1]}, sharex=True)
    ax[0].plot(x, px, color="#d4a017", lw=1.8)
    hi = max(range(len(px)), key=lambda i: px[i])
    ax[0].scatter([hi], [px[hi]], color="#e8604a", zorder=5, s=50)
    ax[0].annotate(f"历史最高 {px[hi]:.0f}\n{dates[hi]}", (hi, px[hi]),
                   textcoords="offset points", xytext=(-160, 12), fontsize=10,
                   color="#e8604a", fontweight="bold")
    ax[0].set_ylabel("金价（美元/盎司）")
    ax[0].set_title("金价与它的水下曲线（GC=F，2016-11 → 2026-11）", fontsize=13)
    ax[0].grid(alpha=.22)

    ax[1].fill_between(x, [v * 100 for v in dd], 0, color="#569cd6", alpha=.55)
    ax[1].plot(x, [v * 100 for v in dd], color="#569cd6", lw=1.2)
    ax[1].set_ylabel("回撤（%）")
    ax[1].set_xlabel("交易日序号")
    ax[1].grid(alpha=.22)

    # ★ 元旦休市，用「每年第一个交易日」当年刻度
    ticks, seen = [], set()
    for i, d in enumerate(dates):
        y = d[:4]
        if y not in seen:
            seen.add(y)
            if int(y) % 2 == 1:      # 隔年标，避免拥挤
                ticks.append(i)
    ax[1].set_xticks(ticks)
    ax[1].set_xticklabels([dates[i][:4] for i in ticks])
    ax[0].set_xticks(ticks)
    fig.tight_layout()
    fig.savefig(FIGS / "q1_underwater.png")

    # --- Q2 事件 + 阈值敏感性 ---
    base = mkt.episodes(dates, px, -0.15, -0.05)
    sens = {}
    for th in (-0.10, -0.15, -0.20):
        eps = mkt.episodes(dates, px, th, th / 3)
        sens[f"{th:.2f}"] = {"n": len(eps),
                             "depths": [round(e["trough"] * 100, 1) for e in eps]}

    # ★ 按「事件发生后第几天」对齐，才能比较形状与恢复速度
    from datetime import date
    fig, ax = plt.subplots(figsize=(11.0, 4.9), dpi=160)
    for e, c in zip(base, ("#7fb069", "#569cd6", "#e8604a")):
        d0 = date.fromisoformat(e["start"])
        offs, vals = [], []
        for i in range(e["start_i"], e["end_i"] + 1):
            offs.append((date.fromisoformat(dates[i]) - d0).days)
            vals.append(dd[i] * 100)
        label = (f"{e['start']}　最深 {e['trough']*100:.1f}%"
                 f"　{'仍在进行' if e['end'] is None else str(e['days'])+' 天结束'}")
        ax.plot(offs, vals, color=c, lw=2.4, label=label)
        ax.scatter([(date.fromisoformat(e["trough_d"]) - d0).days],
                   [e["trough"] * 100], color=c, zorder=5, s=50)
    ax.axhline(-15, color="#888", ls=":", lw=1.2)
    ax.text(5, -14.4, "开事件阈值 −15%", fontsize=9, color="#666")
    ax.set_xlabel("事件发生后的天数")
    ax.set_ylabel("回撤（%）")
    ax.set_title("三次深回撤叠在一起：最深的这次，还没结束", fontsize=13)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    ax.grid(alpha=.22)
    fig.tight_layout()
    fig.savefig(FIGS / "q2_episodes.png")

    out = {"n_days": len(px), "span": [dates[0], dates[-1]],
           "ath": {"px": round(max(px), 1), "date": dates[hi]},
           "current": {"px": round(px[-1], 1), "dd": round(dd[-1] * 100, 2)},
           "episodes": [{"start": e["start"], "trough_pct": round(e["trough"] * 100, 2),
                         "trough_date": e["trough_d"], "days": e["days"],
                         "end": e["end"]} for e in base],
           "threshold_sensitivity": sens}
    (RES / "q12_drawdown.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                           encoding="utf-8")

    print(f"[Q1] {len(px)} 个交易日，{dates[0]} → {dates[-1]}")
    print(f"     历史最高 {max(px):.1f} @ {dates[hi]}；当前 {px[-1]:.1f}，回撤 {dd[-1]*100:.1f}%")
    print(f"[Q2] 阈值 −15%：{len(base)} 次")
    for k, v in sens.items():
        print(f"     阈值 {k}: {v['n']} 次，深度 {v['depths']}")
    print(f"[图] {FIGS/'q1_underwater.png'}")
    print(f"[图] {FIGS/'q2_episodes.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
