"""Q3 – Q5：这一次有多特殊、极值外推、内外盘分解。

Q3：三次事件在深度/持续/恢复三个维度上的排位
Q4：超阈值法（POT）+ 广义帕累托分布（GPD），给 −30% 一个重现期与置信区间
Q5：美元金 vs 人民币金，把 3 个点的差拆成汇率与溢价
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import rcParams
from scipy import stats

import mkt

rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
rcParams["axes.unicode_minus"] = False

EP = Path(__file__).resolve().parents[1]
RES = EP / "results"
FIGS = RES / "figs"
FIGS.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(20261118)


# ---------------------------------------------------------------- Q3
def q3(dates, px, dd, eps) -> dict:
    # ★ 右删失：本次尚未结束，只观测到"已持续 240 天"，不能与已结束事件比恢复快慢
    rows = [{"start": e["start"], "depth": round(e["trough"] * 100, 2),
             "days": e["days"], "ongoing": e["end"] is None} for e in eps]
    depths = [r["depth"] for r in rows]
    cur = rows[-1]

    # 前两次的平均恢复速度（仅作外推假设，非预测）
    done = [r for r in rows if not r["ongoing"]]
    avg_rec = float(np.mean([r["days"] for r in done])) if done else None

    fig, ax = plt.subplots(1, 2, figsize=(12.6, 4.3), dpi=160,
                           gridspec_kw={"width_ratios": [1, 1.6]})
    labels = [r["start"][2:7] for r in rows]
    colors = ["#7fb069", "#569cd6", "#e8604a"]

    ax[0].bar(labels, [abs(r["depth"]) for r in rows], color=colors)
    ax[0].set_ylabel("最深回撤（%）")
    ax[0].set_title("深度：这次最深", fontsize=11)
    for i, r in enumerate(rows):
        ax[0].text(i, abs(r["depth"]) + 0.4, f"{abs(r['depth']):.1f}", ha="center", fontsize=10)
    ax[0].grid(alpha=.2, axis="y")

    # ★ 时间轴：前两条是完整记录，第三条终点未知（右删失），用箭头 + ≥
    for i, (r, c) in enumerate(zip(rows, colors)):
        y = len(rows) - 1 - i
        ax[1].plot([0, r["days"]], [y, y], color=c, lw=10, solid_capstyle="butt", alpha=.85)
        if r["ongoing"]:
            ax[1].annotate("", xy=(r["days"] + 55, y), xytext=(r["days"], y),
                           arrowprops=dict(arrowstyle="->", color=c, lw=2.6))
            ax[1].text(r["days"] + 62, y, "终点未知\n（≥" + str(r["days"]) + " 天）", va="center",
                       fontsize=10, color=c, fontweight="bold")
        else:
            ax[1].text(r["days"] + 10, y, f"{r['days']} 天", va="center", fontsize=10, color=c)
    ax[1].set_yticks(range(len(rows)))
    ax[1].set_yticklabels([r["start"] for r in rows][::-1])
    ax[1].set_xlabel("事件已持续天数")
    ax[1].set_xlim(0, 560)
    ax[1].set_ylim(-0.7, len(rows) - 0.3)
    ax[1].set_title("持续：前两次跑完了，这次还在跑（右删失）", fontsize=11)
    ax[1].grid(alpha=.2, axis="x")

    fig.tight_layout()
    fig.savefig(FIGS / "q3_special.png")

    return {"episodes": rows,
            "avg_completed_duration_days": round(avg_rec, 1) if avg_rec else None,
            "current_ongoing_days": cur["days"],
            "censoring": "本次为右删失：观测到 ≥" + str(cur["days"])
                         + " 天，终点未知，不与已结束事件比较快慢",
            "note": "已结束事件的持续时间只作描述，不是对本次的预测"}


# ---------------------------------------------------------------- Q4
def q4(eps: list[dict], years: float) -> dict:
    """超阈值法，但**样本单位是「事件峰」而不是「天」**。

    为什么不用天：
    一次回撤会连续几百天都超过阈值，把天当独立样本会让样本量虚增几十倍，
    且尾部形状被「回撤持续期内的深度堆积」污染 —— 拟合出 ξ<0（有上界）的假象，
    重现期被系统性低估 10-70 倍。
    """
    u = 0.05
    peaks = np.array([-e["trough"] for e in eps])      # 每次事件的最深值
    ex = peaks[peaks > u] - u
    n_ex = len(ex)
    lam_u = n_ex / years

    xi, loc, beta = stats.genpareto.fit(ex, floc=0)

    def return_period(d_pct: float) -> float:
        d = d_pct / 100.0
        if d <= u:
            return float("nan")
        p = stats.genpareto.sf(d - u, xi, loc=0, scale=beta)
        return 1.0 / (lam_u * p) if p > 0 else float("inf")

    # bootstrap
    B = 2000
    rp_boot, xi_boot = [], []
    for _ in range(B):
        smp = RNG.choice(ex, size=n_ex, replace=True)
        try:
            xb, _, bb = stats.genpareto.fit(smp, floc=0)
            p = stats.genpareto.sf(0.30 - u, xb, loc=0, scale=bb)
            rp_boot.append(1.0 / (lam_u * p) if p > 0 else np.inf)
            xi_boot.append(xb)
        except Exception:
            continue
    rp_boot = np.array([v for v in rp_boot if np.isfinite(v)])
    ci = (float(np.percentile(rp_boot, 5)), float(np.percentile(rp_boot, 95))) \
        if len(rp_boot) > 50 else (None, None)

    rp30 = return_period(30)

    # 图
    fig, ax = plt.subplots(1, 2, figsize=(12.6, 4.5), dpi=160)
    xs = np.sort(ex)
    ax[0].step(xs, 1 - np.arange(1, n_ex + 1) / n_ex, where="post",
               color="#569cd6", lw=2.2, label=f"经验（{n_ex} 次事件）")
    grid = np.linspace(0, xs.max() * 1.4, 200)
    ax[0].plot(grid, stats.genpareto.sf(grid, xi, loc=0, scale=beta),
               color="#e8604a", lw=2.2, label=f"GPD 拟合（ξ={xi:+.2f}）")
    ax[0].set_xlabel("事件最深回撤 − 阈值")
    ax[0].set_ylabel("超越概率")
    ax[0].set_yscale("log")
    ax[0].set_title(f"每个点是一次独立回撤事件（共 {n_ex} 次）", fontsize=11)
    ax[0].legend(frameon=False, fontsize=9)
    ax[0].grid(alpha=.25, which="both")

    ds = np.linspace(6, 45, 240)
    rps = [return_period(d) for d in ds]
    ax[1].plot(ds, rps, color="#d4a017", lw=2.4, label="模型")
    emp_x = [15, 20, 25, 30]
    emp_y = []
    for th in emp_x:
        n = sum(1 for p in peaks if p >= th / 100)
        emp_y.append(years / n if n else np.nan)
    ax[1].plot(emp_x, emp_y, "o", color="#569cd6", ms=8,
               label="经验（样本内计数）")
    ax[1].axvline(peaks.max() * 100, color="#e8604a", ls="--", lw=1.2,
                  label=f"已观测最深 {peaks.max()*100:.1f}%")
    ax[1].set_yscale("log")
    ax[1].set_xlabel("回撤深度（%）")
    ax[1].set_ylabel("重现期（年）")
    ax[1].set_title("模型与经验基本吻合；越深越不确定", fontsize=11)
    ax[1].legend(frameon=False, fontsize=9)
    ax[1].grid(alpha=.25, which="both")
    fig.tight_layout()
    fig.savefig(FIGS / "q4_evt.png")

    return {"threshold_pct": u * 100, "n_events": len(eps), "n_exceed": n_ex,
            "lambda_per_year": round(lam_u, 2),
            "xi": round(float(xi), 4), "beta": round(float(beta), 4),
            "xi_bootstrap_median": round(float(np.median(xi_boot)), 4) if xi_boot else None,
            "rp_30y_est": round(float(rp30), 2) if np.isfinite(rp30) else None,
            "rp_30y_ci90": [round(ci[0], 2), round(ci[1], 2)] if ci[0] else None,
            "observed_max_pct": round(float(peaks.max()) * 100, 2),
            "empirical": {f"{th}%": round(years / max(1, sum(1 for p in peaks if p >= th/100)), 1)
                          for th in (15, 20, 25, 30)},
            "unit_note": "样本单位为「事件峰」，不是「天」",
            "bootstrap_n": len(rp_boot)}


# ---------------------------------------------------------------- Q5
def q5(gold, cny_gold, fx) -> dict:
    g = mkt.to_dict(gold)
    c = mkt.to_dict(cny_gold)
    f = mkt.to_dict(fx)
    common = mkt.align(mkt.align(g, f), c)
    usd = [g[d] for d in common]
    fxr = [f[d] for d in common]
    cny_conv = [g[d] / mkt.OZ_TO_G * f[d] for d in common]
    cny_act = [c[d] for d in common]

    dd_usd = mkt.max_drawdown(usd)
    dd_conv = mkt.max_drawdown(cny_conv)
    dd_act = mkt.max_drawdown(cny_act)

    # 汇率贡献：固定金价、只让汇率变，看回撤差
    fx0 = fxr[0]
    cny_const_fx = [g[d] / mkt.OZ_TO_G * fx0 for d in common]     # 汇率不变
    dd_no_fx = mkt.max_drawdown(cny_const_fx)

    fig, ax = plt.subplots(1, 2, figsize=(12.6, 4.5), dpi=160)
    ax[0].plot(common, cny_conv, color="#d4a017", lw=1.5, label="GC=F ÷31.1 × 汇率")
    ax[0].plot(common, cny_act, color="#e8604a", lw=1.2, alpha=.8, label="上金所 Au99.99")
    ticks = [d for d in common if d.endswith("-01") and int(d[5:7]) == 1 and int(d[:4]) % 2 == 1]
    ax[0].set_xticks(ticks)
    ax[0].set_xticklabels([d[:4] for d in ticks])
    ax[0].set_ylabel("人民币金价（元/克）")
    ax[0].set_title("两个源互验：换算值贴着上金所", fontsize=11)
    ax[0].legend(frameon=False, fontsize=9)
    ax[0].grid(alpha=.22)

    names = ["美元金", "换算人民币金\n（汇率不变）", "换算人民币金\n（真实汇率）", "上金所\n现货"]
    vals = [dd_usd, dd_no_fx, dd_conv, dd_act]
    ax[1].bar(names, [abs(v) * 100 for v in vals],
              color=["#569cd6", "#8fb8d8", "#d4a017", "#e8604a"])
    ax[1].set_ylabel("最深回撤（%）")
    gap = abs(dd_act - dd_usd) * 100
    fx_c = abs(dd_conv - dd_no_fx) * 100
    pm_c = abs(dd_act - dd_conv) * 100
    ax[1].set_title(f"多跌的 {gap:.1f} 个点：汇率 {fx_c:.1f}、内盘溢价 {pm_c:.1f}", fontsize=11)
    for i, v in enumerate(vals):
        ax[1].text(i, abs(v) * 100 + 0.4, f"{abs(v)*100:.1f}%", ha="center", fontsize=9)
    ax[1].grid(alpha=.2, axis="y")
    fig.tight_layout()
    fig.savefig(FIGS / "q5_cny.png")

    return {"n_common_days": len(common),
            "dd_usd_pct": round(dd_usd * 100, 2),
            "dd_cny_const_fx_pct": round(dd_no_fx * 100, 2),
            "dd_cny_conv_pct": round(dd_conv * 100, 2),
            "dd_cny_actual_pct": round(dd_act * 100, 2),
            "fx_first": round(fxr[0], 4), "fx_last": round(fxr[-1], 4),
            "fx_contribution_pct": round((dd_conv - dd_no_fx) * 100, 2),
            "cross_validation_err_pct": round((cny_conv[-1] / cny_act[-1] - 1) * 100, 2)}


def main() -> int:
    gold = mkt.load_cached("gold_usd", mkt.yahoo, "GC=F")
    dates = [d for d, _ in gold]
    px = [v for _, v in gold]
    dd_arr = np.array(mkt.drawdown_series(px))
    eps = mkt.episodes(dates, px, -0.15, -0.05)

    r3 = q3(dates, px, dd_arr, eps)
    # Q4 用 −5% 口径的事件集（22 次），样本量才够拟合尾部
    eps_all = mkt.episodes(dates, px, -0.05, -0.02)
    r4 = q4(eps_all, len(px) / 252.0)
    r5 = q5(gold, mkt.load_cached("gold_cny", mkt.sge, "Au99.99"),
            mkt.load_cached("fx_usdcny", mkt.yahoo, "CNY=X"))

    (RES / "q3_special.json").write_text(json.dumps(r3, ensure_ascii=False, indent=2), encoding="utf-8")
    (RES / "q4_evt.json").write_text(json.dumps(r4, ensure_ascii=False, indent=2), encoding="utf-8")
    (RES / "q5_cny.json").write_text(json.dumps(r5, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[Q3] 三次事件：")
    for r in r3["episodes"]:
        print(f"   {r['start']}  深度 {r['depth']:+.1f}%  持续 {r['days']} 天  "
              f"{'仍在进行（删失）' if r['ongoing'] else '已结束'}")
    print(f"   已结束事件的平均持续 {r3['avg_completed_duration_days']} 天（只作描述）")
    print(f"[Q4] 事件峰 POT: {r4['n_events']} 次事件，超阈值 {r4['n_exceed']} 个，"
          f"λ={r4['lambda_per_year']}/年，ξ={r4['xi']:+.3f}")
    print(f"     经验重现期 {r4['empirical']}")
    print(f"   −30% 重现期 ≈ {r4['rp_30y_est']} 年，90% 区间 {r4['rp_30y_ci90']}")
    print(f"[Q5] 美元金 {r5['dd_usd_pct']}% / 汇率不变 {r5['dd_cny_const_fx_pct']}% / "
          f"真实汇率 {r5['dd_cny_conv_pct']}% / 上金所 {r5['dd_cny_actual_pct']}%")
    print(f"   汇率贡献 {r5['fx_contribution_pct']} 个点，互验误差 {r5['cross_validation_err_pct']}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
