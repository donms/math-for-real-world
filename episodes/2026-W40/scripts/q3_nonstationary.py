#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""问题 3：非平稳极值分析（时变 GEV + 似然比检验）。

按用户确认的方案（见 models/03_非平稳极值模型.md 决策记录）：
  · 位置参数线性趋势 μ(t)=μ₀+mu1t
  · 似然比检验 Λ=2(ℓ₁−ℓ₀)，**同时给两个判据**：
      χ²₁ 的 3.841（标准）与混合分布 ½χ²₀+½χ²₁ 的 2.706（更严谨，
      因为 H₀ 的 mu1=0 落在参数空间边界，Self & Liang 1987）
  · 前后 40 年分段对比作稳健性检查
  · **BH-FDR 多重检验校正**（16 城 × 2 变量 = 32 次检验，
     不校正则期望约 1.6 个假阳性）

产出：
  results/q3_nonstationary.json
  results/q3_summary.txt
  results/figs/q3_*.png
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evt import (FIGS, annual_max, gev_fit, gev_return_level,  # noqa: E402
                 load_cities, load_series, save_json)

import matplotlib                                              # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                # noqa: E402
from matplotlib import font_manager                            # noqa: E402

for _f in (r"<LOCAL_PATH>", r"<LOCAL_PATH>"):
    try:
        font_manager.fontManager.addfont(_f)
    except Exception:                                          # noqa: BLE001
        pass
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

CHI2_1_95 = 3.841      # 标准 χ²₁ 临界值
MIX_95 = 2.706         # ½χ²₀+½χ²₁ 的 95% 临界值（边界问题，更严谨）

# ⚠️ 自助法规模：曾设 300，结果跑了一小时还没完——
#    因为每城每变量要 300 次**时变** GEV 拟合（每次内部还有 6 个初值），
#    共 300×2×16 = 9600 次，而单次时变拟合比平稳拟合慢得多。
#    mu1 的区间**主结果是数值 Hessian**（观测信息矩阵，严谨且快），
#    自助法仅作对照，故规模降到 60 足够判断似然面是否对称。
N_BOOT = 60

# 自助法内层减少初值个数（60 次不需要那么多次重启）
_BOOT_TRIES = 2


def hessian_se(fn_nll, p_hat: np.ndarray, rel: float = 1e-4):
    """数值 Hessian 求标准误：SE = sqrt(diag(inv(H)))。

    H 为负对数似然的 Hessian（观测信息矩阵）。
    极值问题的似然面常不对称，故同时也会给自助法区间作对照。
    """
    n = len(p_hat)
    H = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            hi = rel * max(abs(p_hat[i]), 1e-3)
            hj = rel * max(abs(p_hat[j]), 1e-3)
            pp = p_hat.copy(); pp[i] += hi; pp[j] += hj
            pm = p_hat.copy(); pm[i] += hi; pm[j] -= hj
            mp = p_hat.copy(); mp[i] -= hi; mp[j] += hj
            mm = p_hat.copy(); mm[i] -= hi; mm[j] -= hj
            try:
                H[i, j] = (fn_nll(pp) - fn_nll(pm) - fn_nll(mp) + fn_nll(mm)) \
                    / (4 * hi * hj)
            except Exception:                                  # noqa: BLE001
                H[i, j] = np.nan
    try:
        cov = np.linalg.inv(H)
        d = np.diag(cov)
        return np.sqrt(np.where(d > 0, d, np.nan))
    except np.linalg.LinAlgError:
        return np.full(n, np.nan)


def analyze_var(x: np.ndarray, year: np.ndarray, label: str) -> dict:
    """对一个变量做非平稳分析。"""
    yrs, mx = annual_max(x, year)
    n = len(mx)
    out = {"n_years": int(n), "label": label,
           "year_first": int(yrs.min()), "year_last": int(yrs.max())}
    if n < 30:
        out["error"] = "年最大值太少"
        return out

    # ---------- H0：平稳 ----------
    try:
        p0, ll0, aic0 = gev_fit(mx, with_trend=False)
    except Exception as e:                                     # noqa: BLE001
        out["error"] = f"平稳拟合失败 {type(e).__name__}"
        return out

    # ---------- H1：时变 ----------
    try:
        p1, ll1, aic1 = gev_fit(mx, with_trend=True)
    except Exception as e:                                     # noqa: BLE001
        out["error"] = f"时变拟合失败 {type(e).__name__}"
        return out

    mu0, mu1, sg, xi = (float(v) for v in p1)
    lam = 2.0 * (ll1 - ll0)
    out.update({
        "mu1": mu1, "mu1_unit_per_year": mu1,
        "mu1_per_decade": mu1 * 10,
        "sigma": sg, "xi": xi, "mu0": mu0,
        "loglik_stat": float(ll0), "loglik_trend": float(ll1),
        "aic_stat": float(aic0), "aic_trend": float(aic1),
        "lr_stat": float(lam),
        "p_chi2": float(1 - __import__("scipy.stats", fromlist=["chi2"])
                        .chi2.cdf(lam, 1)),
        "sig_standard": bool(lam > CHI2_1_95),
        "sig_boundary": bool(lam > MIX_95),
        "aic_prefers_trend": bool(aic1 < aic0),
    })

    # ---------- mu1 的标准误（数值 Hessian + 自助法）----------
    t = np.arange(n, dtype=float)

    def nll_trend(p):
        m = p[0] + p[1] * t
        if p[2] <= 0 or abs(p[3]) > 2.0:
            return 1e12
        from scipy.stats import genextreme
        ll = genextreme.logpdf(mx, c=-p[3], loc=m, scale=p[2])
        return 1e12 if not np.all(np.isfinite(ll)) else -ll.sum()

    se = hessian_se(nll_trend, p1)
    out["mu1_se_hessian"] = float(se[1]) if np.isfinite(se[1]) else None

    rng = np.random.default_rng(9090)
    boots = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, n, n)
        try:
            pp, _, _ = gev_fit(mx[idx], with_trend=True, n_tries=_BOOT_TRIES)
            boots.append(float(pp[1]))
        except Exception:                                      # noqa: BLE001
            continue
    if len(boots) > 20:
        b = np.array(boots)
        out["mu1_ci_boot"] = [float(np.quantile(b, 0.025)),
                              float(np.quantile(b, 0.975))]
        out["mu1_n_boot"] = len(b)
    else:
        out["mu1_ci_boot"] = None
        out["mu1_n_boot"] = len(boots)

    # ---------- x50 随时间移动 + 等效重现期 ----------
    x50_start = gev_return_level(p1, 50, with_trend=True, t_at=0.0)
    x50_end = gev_return_level(p1, 50, with_trend=True, t_at=float(n - 1))
    out["x50_1940"] = float(x50_start)
    out["x50_2026"] = float(x50_end)
    out["x50_shift"] = float(x50_end - x50_start)
    out["x50_stat"] = float(gev_return_level(p0, 50))

    # 等效重现期：用末期分布去看「全期平稳拟合的 x50」是多少年一遇
    from scipy.stats import genextreme
    mu_end = mu0 + mu1 * (n - 1)
    p_exc = float(genextreme.sf(out["x50_stat"], c=-xi, loc=mu_end, scale=sg))
    out["T_equivalent_of_stat_x50"] = (1.0 / p_exc) if p_exc > 0 else None

    # ---------- 分段验证 ----------
    half = n // 2
    seg = {}
    for tag, mm, yy in (("first", mx[:half], yrs[:half]),
                        ("second", mx[half:], yrs[half:])):
        try:
            ps, _, _ = gev_fit(mm)
            seg[tag] = {"x50": float(gev_return_level(ps, 50)),
                        "xi": float(ps[2]),
                        "year_from": int(yy.min()), "year_to": int(yy.max())}
        except Exception:                                      # noqa: BLE001
            seg[tag] = None
    out["segments"] = seg
    if seg.get("first") and seg.get("second"):
        out["x50_shift_segmented"] = float(seg["second"]["x50"]
                                           - seg["first"]["x50"])
        out["x50_shift_predicted"] = float(mu1 * half)
    return out


def bh_fdr(pvals: list[float], alpha: float = 0.05):
    """Benjamini–Hochberg 校正。返回 (是否显著列表, 阈值)。"""
    m = len(pvals)
    if m == 0:
        return [], None
    order = np.argsort(pvals)
    thresh = alpha * (np.arange(1, m + 1)) / m
    passed = np.array(pvals)[order] <= thresh
    kmax = np.max(np.where(passed)[0]) if passed.any() else -1
    cutoff = thresh[kmax] if kmax >= 0 else 0.0
    sig = [bool(p <= cutoff) for p in pvals]
    return sig, float(cutoff)


def main() -> int:
    t0 = time.time()
    cities = load_cities()
    print(f"  {len(cities)} 城 × 2 变量 = {len(cities)*2} 次似然比检验")
    print(f"  判据：χ²₁ 临界 {CHI2_1_95}（标准） / "
          f"混合分布临界 {MIX_95}（边界修正）\n")

    out: dict = {}
    for i, c in enumerate(cities, 1):
        name = c["name"]
        try:
            s = load_series(name)
        except FileNotFoundError:
            continue
        rec = {"group": c["group"],
               "tmax": analyze_var(s["tmax"], s["year"], "tmax"),
               "precip": analyze_var(s["precip"], s["year"], "precip")}
        out[name] = rec
        tv, pv = rec["tmax"], rec["precip"]
        print(f"  [{i:>2}/{len(cities)}] {name:<8}{c['group']:<18}"
              f"气温 mu1={tv.get('mu1_per_decade', float('nan')):+6.3f}℃/10年 "
              f"Λ={tv.get('lr_stat', float('nan')):6.2f} "
              f"{'显著' if tv.get('sig_standard') else '不显著':<6}"
              f"| 降水 mu1={pv.get('mu1_per_decade', float('nan')):+7.2f}mm/10年 "
              f"Λ={pv.get('lr_stat', float('nan')):6.2f} "
              f"{'显著' if pv.get('sig_standard') else '不显著'}", flush=True)

    # ---------- BH-FDR 多重检验校正 ----------
    pv_list, keys = [], []
    for nm, r in out.items():
        for var in ("tmax", "precip"):
            p = r[var].get("p_chi2")
            if p is not None:
                pv_list.append(p)
                keys.append((nm, var))
    sig, cutoff = bh_fdr(pv_list, 0.05)
    for (nm, var), sv in zip(keys, sig):
        out[nm][var]["sig_fdr"] = sv
    n_sig_raw = sum(1 for p in pv_list if p <= 0.05)
    n_sig_fdr = sum(sig)

    save_json(out, "q3_nonstationary.json")

    # ---------- 汇总 ----------
    L = ["问题3 · 非平稳性检验汇总", "=" * 104, ""]
    L.append("【一】逐城趋势（mu1 为位置参数的线性漂移速率）")
    L.append(f"{'城市':<9}{'组':<19}{'气温mu1(℃/10年)':>16}{'Λ':>8}{'p':>8}"
             f"{'显著?':>7}{'降水mu1(mm/10年)':>18}{'Λ':>8}{'p':>8}{'显著?':>7}")
    L.append("-" * 104)
    for nm, r in out.items():
        tv, pv = r["tmax"], r["precip"]
        def g(d, k, f="{:.3f}"):
            v = d.get(k)
            return f.format(v) if isinstance(v, (int, float)) else "n/a"
        L.append(f"{nm:<9}{r['group']:<19}"
                 f"{g(tv,'mu1_per_decade','{:+.3f}'):>16}{g(tv,'lr_stat','{:.2f}'):>8}"
                 f"{g(tv,'p_chi2','{:.4f}'):>8}"
                 f"{('是' if tv.get('sig_standard') else '否'):>7}"
                 f"{g(pv,'mu1_per_decade','{:+.2f}'):>18}{g(pv,'lr_stat','{:.2f}'):>8}"
                 f"{g(pv,'p_chi2','{:.4f}'):>8}"
                 f"{('是' if pv.get('sig_standard') else '否'):>7}")

    L += ["", "【二】「五十年一遇」门槛的移动", "-" * 104]
    L.append(f"{'城市':<9}{'气温x50(1940)':>15}{'气温x50(2026)':>15}{'移动':>9}"
             f"{'降水x50移动':>13}{'等效重现期':>12}")
    for nm, r in out.items():
        tv, pv = r["tmax"], r["precip"]
        a = tv.get("x50_1940"); b = tv.get("x50_2026"); sh = tv.get("x50_shift")
        psh = pv.get("x50_shift")
        teq = tv.get("T_equivalent_of_stat_x50")
        L.append(f"{nm:<9}"
                 f"{(f'{a:.1f}' if a else 'n/a'):>15}"
                 f"{(f'{b:.1f}' if b else 'n/a'):>15}"
                 f"{(f'{sh:+.2f}' if sh is not None else 'n/a'):>9}"
                 f"{(f'{psh:+.1f}' if psh is not None else 'n/a'):>13}"
                 f"{(f'{teq:.1f}年' if teq else 'n/a'):>12}")

    L += ["", "【三】多重检验校正（BH-FDR, α=0.05）", "-" * 104,
          f"  检验总数：{len(pv_list)}",
          f"  未校正显著数（p≤0.05）：{n_sig_raw}",
          f"  FDR 校正后显著数：{n_sig_fdr}",
          f"  BH 阈值：{cutoff:.5f}" if cutoff else "  BH 阈值：无",
          ""]

    # 方向一致性
    tm = [r["tmax"].get("mu1_per_decade") for r in out.values()
          if r["tmax"].get("mu1_per_decade") is not None]
    pm = [r["precip"].get("mu1_per_decade") for r in out.values()
          if r["precip"].get("mu1_per_decade") is not None]
    L += ["【四】方向一致性（比显著性更强的证据）", "-" * 104,
          f"  气温 mu1 > 0 的城市：{sum(1 for v in tm if v > 0)}/{len(tm)}"
          f"  中位 {np.median(tm):+.3f} ℃/10年",
          f"  降水 mu1 > 0 的城市：{sum(1 for v in pm if v > 0)}/{len(pm)}"
          f"  中位 {np.median(pm):+.2f} mm/10年",
          ""]
    L += ["【五】分段验证（线性趋势 vs 前后半段实测移动）", "-" * 104]
    L.append(f"{'城市':<9}{'前段x50':>10}{'后段x50':>10}{'分段移动':>10}"
             f"{'趋势预测':>10}{'差异':>9}")
    for nm, r in out.items():
        tv = r["tmax"]
        sg = tv.get("segments") or {}
        f_, s_ = sg.get("first"), sg.get("second")
        if f_ and s_:
            pred = tv.get("x50_shift_predicted")
            act = tv.get("x50_shift_segmented")
            L.append(f"{nm:<9}{f_['x50']:>10.1f}{s_['x50']:>10.1f}"
                     f"{act:>10.2f}{(f'{pred:+.2f}' if pred else 'n/a'):>10}"
                     f"{(f'{act-pred:+.2f}' if pred else 'n/a'):>9}")

    L += ["", "【六】诚实性声明", "-" * 104,
          "  · 降水被网格平滑（实测 597.7mm → 网格 108.7mm，仅 18%），",
          "    其趋势估计会**衰减**，真实趋势可能更强 → 降水趋势视为下界",
          "  · 32 次检验存在多重比较问题，故同时报告 FDR 校正结果",
          "  · mu1 的似然面可能不对称，故同时给 Hessian 与自助法区间",
          ""]
    (FIGS.parent / "q3_summary.txt").write_text("\n".join(L), encoding="utf-8")

    # ---------- 图 ----------
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    for ax, var, unit, ttl in ((axes[0], "tmax", "℃/10年", "日最高气温"),
                               (axes[1], "precip", "mm/10年", "日降水量")):
        names = list(out)
        vals = [out[n][var].get("mu1_per_decade", 0.0) or 0.0 for n in names]
        sigs = [out[n][var].get("sig_standard", False) for n in names]
        cols = ["#c0392b" if s else "#95a5a6" for s in sigs]
        ax.barh(np.arange(len(names)), vals, color=cols)
        ax.axvline(0, color="k", lw=1)
        ax.set_yticks(np.arange(len(names)))
        ax.set_yticklabels(names, fontsize=8)
        ax.set_xlabel(f"位置参数趋势 mu1（{unit}）")
        ax.set_title(f"{ttl}：mu1 逐城对比\n（红=显著 p<0.05，灰=不显著）")
        ax.grid(alpha=0.3, axis="x")
    fig.tight_layout()
    fig.savefig(FIGS / "q3_trend.png", dpi=140)
    plt.close(fig)

    print(f"\n  用时 {time.time()-t0:.1f}s")
    print(f"  显著数：未校正 {n_sig_raw} → FDR 校正后 {n_sig_fdr}")
    print(f"  气温 mu1>0: {sum(1 for v in tm if v>0)}/{len(tm)}，"
          f"降水 mu1>0: {sum(1 for v in pm if v>0)}/{len(pm)}")
    print(f"  [结果] results/q3_nonstationary.json")
    print(f"  [汇总] results/q3_summary.txt")
    print(f"  [图表] results/figs/q3_trend.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
