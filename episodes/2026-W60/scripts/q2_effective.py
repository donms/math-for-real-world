"""Q2 v2：兑现条件（修正版）。

★ 修正三处（2026-11-02 用户质疑后重查）
------------------------------
1. 带宽：征程 6P 是 **256-bit LPDDR5 ≈ 205 GB/s**（余凯访谈），不是我原假设的 102.4
2. 算术强度：Transformer GEMM 约 100–200 FLOPs/B（中科院计算所），
   但**有效**算术强度含片上复用，高于 DRAM 级 ⇒ 必须与实测利用率对账
3. 结论从"只能用到百分之几"改为"**实测 25%–40%** + 理论上界"

输出
----
    results/q2_effective.json
    figs/q2_effective.png
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

EP = Path(__file__).resolve().parents[1]
RES = EP / "results"
FIGS = RES / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

PEAK = 280.0             # 稠密 INT8 TOPS（② 560÷2，见 data/征程6P查证.md）
BW = 205.0               # GB/s（② 余凯访谈：256-bit LPDDR5，约 205 GB/s）
BW_RANGE = (160.0, 205.0, 256.0)

# 实测算力利用率（③ 行业报道区间）：与 roofline 对账
MEASURED_UTIL = (25.0, 40.0)
AI_POINTS = [100, 200, 400, 800, 1366, 2000]


def roof(ai: float, bw: float = BW) -> float:
    return min(PEAK, ai * bw / 1000.0)


def util(ai: float, bw: float = BW) -> float:
    return 100.0 * roof(ai, bw) / PEAK


def quant_snr(bits: int, outliers: bool = False, n: int = 200_000, seed: int = 7) -> float:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    if outliers:
        k = n // 100
        x[:k] = rng.normal(scale=10.0, size=k)
    amax = np.abs(x).max()
    step = 2 * amax / (2 ** bits)
    q = np.round(x / step) * step
    return 10 * math.log10(float(np.mean(x ** 2)) / max(float(np.mean((q - x) ** 2)), 1e-30))


def main() -> int:
    ridge = PEAK * 1000.0 / BW
    pts = [{"ai": a, "tops": round(roof(a), 1), "util_pct": round(util(a), 1)} for a in AI_POINTS]
    ai_for_util = {f"{u:.0f}%": round(u / 100.0 * PEAK * 1000.0 / BW, 0) for u in MEASURED_UTIL}
    sens = [{"bw": b, "ridge": round(PEAK * 1000.0 / b, 0),
             "util_at_400": round(util(400, b), 1)} for b in BW_RANGE]
    q = {"int8": round(quant_snr(8), 1), "int4": round(quant_snr(4), 1),
         "int8_outlier": round(quant_snr(8, True), 1),
         "int4_outlier": round(quant_snr(4, True), 1)}

    out = {
        "peak_tops": PEAK, "bw_gbps": BW,
        "ridge_ops_per_byte": round(ridge, 0),
        "points": pts,
        "measured_util_pct": list(MEASURED_UTIL),
        "ai_equivalent_of_measured": ai_for_util,
        "bw_sensitivity": sens,
        "quantization_snr_db": q,
        "note": "roofline 的 AI 是 DRAM 级；有效 AI 含片上复用，故实测利用率高于低 AI 段的屋顶线",
    }
    (RES / "q2_effective.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                           encoding="utf-8")

    print(f"[修正] 带宽 {BW:.0f} GB/s ⇒ 撞墙点 {ridge:.0f} ops/byte")
    for p in pts:
        print(f"   AI={p['ai']:>5} → {p['tops']:>6.1f} TOPS（{p['util_pct']:>4.1f}%）")
    print(f"[对账] 实测利用率 {MEASURED_UTIL[0]:.0f}%–{MEASURED_UTIL[1]:.0f}% "
          f"⇔ 有效算术强度 {ai_for_util}")
    print(f"[带宽敏感性] {[(s['bw'], s['ridge']) for s in sens]}")
    print(f"[量化] INT8 {q['int8']} / 4bit {q['int4']} dB（含离群：{q['int8_outlier']} / {q['int4_outlier']}）")

    plot(out)
    return 0


def plot(out: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import rcParams
    rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(1, 2, figsize=(13.2, 4.6), dpi=160)

    ai = np.logspace(1, 4, 300)
    got = np.minimum(PEAK, ai * BW / 1000.0)
    ax[0].loglog(ai, got, color="#e8604a", lw=2.4, label="本配置的屋顶线")
    ax[0].axhline(PEAK, color="#8a9bb0", ls="--", lw=1.2)
    ridge = out["ridge_ops_per_byte"]
    ax[0].axvline(ridge, color="#569cd6", ls=":", lw=1.4)
    ax[0].annotate(f"撞墙点 {ridge:,.0f}", (ridge, PEAK), textcoords="offset points",
                   xytext=(-150, -34), fontsize=9, color="#569cd6")
    lo, hi = out["measured_util_pct"]
    ax[0].axhspan(PEAK * lo / 100, PEAK * hi / 100, color="#7fb069", alpha=0.16)
    for p in out["points"]:
        ax[0].plot(p["ai"], p["tops"], "o", ms=4, color="#333")
    ax[0].set_xlabel("算术强度（ops / byte）")
    ax[0].set_ylabel("实际算力（TOPS）")
    ax[0].set_title("Roofline（205 GB/s）：撞墙点 1 366", fontsize=12)
    ax[0].grid(alpha=0.25, which="both")
    ax[0].legend(frameon=False, fontsize=8, loc="lower right")

    labels = ["AI=100", "AI=200", "AI=400", "AI=800", "AI=1366"]
    vals = [util(a) for a in (100, 200, 400, 800, 1366)]
    bars = ax[1].bar(labels, vals, color="#569cd6", width=0.6)
    ax[1].axhspan(lo, hi, color="#7fb069", alpha=0.25, label=f"实测区间 {lo:.0f}%–{hi:.0f}%")
    for b, v in zip(bars, vals):
        ax[1].text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.0f}%", ha="center", fontsize=9)
    ax[1].set_ylim(0, 105)
    ax[1].set_ylabel("占标称算力的比例")
    ax[1].set_title("不同算术强度下的利用率 vs 实测区间", fontsize=12)
    ax[1].grid(alpha=0.25, axis="y")
    ax[1].legend(frameon=False, fontsize=9)

    fig.tight_layout()
    fig.savefig(FIGS / "q2_effective.png")
    print(f"[图] {FIGS / 'q2_effective.png'}")


if __name__ == "__main__":
    raise SystemExit(main())
