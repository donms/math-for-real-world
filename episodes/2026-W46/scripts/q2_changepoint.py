#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · Q2：把"起爆"写成数学对象，并给出**区间**。

## 选题要求（01_题目.md 问题 2）

1. 把"起爆点"写成**可操作的数学定义**；
2. 用**变点检测**给出起爆点的**估计区间**（不是单个日期）；
3. 报告结论对以下选择的**敏感性**：变点模型族、先验、数据预处理；
4. 在中国暴发疫情序列上重复，说明**样本量差异如何影响区间宽度**。

## 本脚本的三层设计

### 第 0 层：为什么不能直接对原始 `ili` 做变点

`ili` 有**极强的年周期**（`health_check.py` 实测峰在第 52 周、谷在第 31 周，
峰谷比 4.5×）。若直接对原始序列找变点，
**检测到的一定是"季节上升段"**，而不是"起爆"。
=> 必须先**去季节**，再在残差上找"增长率转正"的变点。

> 这正是分析报告 §2.1 的核心洞察：
> **起爆发生在第 35–38 周（季节谷底爬升段），
> 它不是季节峰本身，而是叠加在季节上升期上的额外加速。**
> 两层必须分开，否则会把"季节正常上升"误判成"疫情失控"。

### 第 1 层：去季节（两条路线，互为敏感性对照）

* **A 路线 · 季节基线**：按 ISO 周聚合出季节轮廓 $\bar y_w$，
  取比值 $r_t=y_t/\bar y_{w(t)}$，再取对数；
* **B 路线 · STL 式分解**：用 52 周滑动中位数作趋势、
  残差减去按周中位数 —— 不依赖"全年同形"假设。

### 第 2 层：变点检测（两个模型族，互为敏感性对照）

* **族 I · 分段常数增长率（Bayes，网格后验）**：
  $\log r_t\sim N(\mu_t,\sigma^2)$，$\mu_t=\mu_1\,(t<\tau)+\mu_2\,(t\ge\tau)$。
  对 $\tau$ 做**网格后验**（用解析的边缘似然），直接得到 $\tau$ 的后验区间。
  这是"变点检测"，不含趋势。
* **族 II · 分段线性（含斜率变化）**：
  允许"增长率由 0 变为正"，即断点前后斜率不同，
  更贴近"起爆 = 增长率转正"的字面定义。

### 第 3 层：中国短序列对比

同一套流程跑中国 14 期暴发疫情数（$n$ 极小），
报告区间宽度，量化"样本量如何影响可辨识性"。

用法：
    $PY q2_changepoint.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
RES = ROOT / "results"
FIGS = RES / "figs"
RES.mkdir(parents=True, exist_ok=True)
FIGS.mkdir(parents=True, exist_ok=True)

# 关注的窗口：2026 年第 20–38 周（起爆发生在这里）
WIN_YEAR = 2026
WIN_W0, WIN_W1 = 20, 38


def flat_week(w: int) -> int:
    return (w // 100 - 2000) * 52 + (w % 100 - 1)


def load_ili():
    with open(CLEAN / "ili_weekly.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    wk = np.array([int(r["epiweek"]) for r in rows])
    y = np.array([float(r["ili"]) for r in rows])
    return wk, y


# ----------------------------------------------------------- 去季节
def deseason_A(wk: np.ndarray, y: np.ndarray):
    """A 路线：按 ISO 周的季节轮廓，取比值。"""
    woy = wk % 100
    prof = {}
    for w in np.unique(woy):
        m = woy == w
        if m.sum() >= 5:
            prof[w] = float(np.median(y[m]))
    base = np.array([prof.get(w, np.nan) for w in woy])
    with np.errstate(divide="ignore", invalid="ignore"):
        r = y / base
    return r, base, prof


def deseason_B(wk: np.ndarray, y: np.ndarray, win: int = 52):
    """B 路线：52 周滑动中位数作趋势，残差再去按周中位数。"""
    n = len(y)
    trend = np.full(n, np.nan)
    h = win // 2
    for i in range(n):
        a, b = max(0, i - h), min(n, i + h + 1)
        trend[i] = np.median(y[a:b])
    with np.errstate(divide="ignore", invalid="ignore"):
        r0 = y / trend
    woy = wk % 100
    adj = np.ones(n)
    for w in np.unique(woy):
        m = woy == w
        if m.sum() >= 5:
            adj[m] = np.median(r0[m])
    return r0 / adj, trend


# --------------------------------------------------- 族 I：分段常数均值
def logmarg_const(x: np.ndarray, tau: int, mu0: float = 0.0,
                  kappa0: float = 1.0, alpha0: float = 1.0,
                  beta0: float = 1.0):
    r"""分段常数均值的**对数边缘似然**（Normal-Inverse-Gamma 共轭）。

    * **前段**（$t<\tau$）：均值**固定**为 $\mu_0=0$
      —— 即"起爆前增长率无系统性偏离"，只估方差；
    * **后段**（$t\ge\tau$）：均值待估（用 NIG 先验积分掉）。

    这正是"**起爆 = 前段平、后段涨**"的模型化。

    > ⚠️ 修过一个笔误：上一版这里写了 `a*np.log(b) ... if False else _f(...)`
    > 的死代码分支，既不可读也容易出错 —— 现在两段各用一个明确的函数。
    """
    from scipy.special import gammaln
    n = len(x)
    if tau < 3 or tau > n - 3:
        return -np.inf

    # --- 前段：均值固定为 mu0，方差 ~ InvGamma(alpha0, beta0) ---
    s1 = x[:tau]
    m1 = len(s1)
    ss1 = float(((s1 - mu0) ** 2).sum())
    a1 = alpha0 + m1 / 2.0
    b1 = beta0 + ss1 / 2.0
    ll1 = gammaln(a1) - gammaln(alpha0) + alpha0 * np.log(beta0) - a1 * np.log(b1)

    # --- 后段：均值与方差都待估（NIG 共轭，解析积分）---
    s2 = x[tau:]
    m2 = len(s2)
    if m2 < 2:
        return -np.inf
    sbar = float(s2.mean())
    kn = kappa0 + m2
    mu_n = (kappa0 * mu0 + m2 * sbar) / kn
    a2 = alpha0 + m2 / 2.0
    b2 = (beta0 + 0.5 * float(((s2 - sbar) ** 2).sum())
          + 0.5 * kappa0 * m2 / kn * (sbar - mu0) ** 2)
    ll2 = (0.5 * np.log(kappa0 / kn) + gammaln(a2) - gammaln(alpha0)
           + alpha0 * np.log(beta0) - a2 * np.log(b2))
    return float(ll1 + ll2)


def posterior_tau_const(x: np.ndarray, prior: str = "uniform",
                        **kw) -> tuple[np.ndarray, np.ndarray]:
    """返回 (tau 网格, 归一化后验)。"""
    n = len(x)
    taus = np.arange(3, n - 2)
    lp = np.array([logmarg_const(x, int(t), **kw) for t in taus])
    if prior == "uniform":
        lpri = np.zeros(len(taus))
    elif prior == "edge":          # 偏向两端（更保守的"变点在中间"假设）
        c = (taus - taus.mean()) / max(taus.std(), 1e-9)
        lpri = 0.5 * c ** 2
    else:
        lpri = np.zeros(len(taus))
    lp = lp + lpri
    lp = lp - lp.max()
    p = np.exp(lp)
    s = p.sum()
    return taus, (p / s if s > 0 else p)


# --------------------------------------------------- 族 II：分段线性
def fit_piecewise_linear(x: np.ndarray, tau: int):
    """两段各自的 OLS 斜率与残差平方和。"""
    n = len(x)
    tt = np.arange(n, dtype=float)
    rss, slopes = 0.0, []
    for a, b in ((0, tau), (tau, n)):
        if b - a < 3:
            return np.inf, []
        A = np.vstack([np.ones(b - a), tt[a:b]]).T
        coef, res, *_ = np.linalg.lstsq(A, x[a:b], rcond=None)
        rss += float(res[0]) if res.size else float(
            ((x[a:b] - A @ coef) ** 2).sum())
        slopes.append(float(coef[1]))
    return rss, slopes


def posterior_tau_linear(x: np.ndarray, sigma2: float | None = None):
    n = len(x)
    if sigma2 is None:
        A = np.vstack([np.ones(n), np.arange(n, dtype=float)]).T
        coef, *_ = np.linalg.lstsq(A, x, rcond=None)
        sigma2 = float(((x - A @ coef) ** 2).mean()) + 1e-9
    taus = np.arange(3, n - 2)
    lp = np.zeros(len(taus))
    for i, t in enumerate(taus):
        rss, _ = fit_piecewise_linear(x, int(t))
        # 高斯似然（sigma2 视为已知，取全序列估计）
        lp[i] = -0.5 * rss / sigma2
    lp -= lp.max()
    p = np.exp(lp)
    return taus, p / max(p.sum(), 1e-300)


# ----------------------------------------------------------- 工具
def hdi(taus: np.ndarray, p: np.ndarray, mass: float = 0.95):
    """最高后验密度区间。"""
    o = np.argsort(-p)
    ts, ps = taus[o], p[o]
    c = np.cumsum(ps)
    k = int(np.searchsorted(c, mass)) + 1
    sel = np.sort(ts[:k])
    return int(sel[0]), int(sel[-1])


def main() -> int:
    print("=" * 94)
    print("  W46 · Q2 变点检测：把『起爆』写成可检验的对象")
    print("=" * 94)
    wk, y = load_ili()
    rep: dict = {}

    # ---- 去季节 ----
    rA, base, prof = deseason_A(wk, y)
    rB, trend = deseason_B(wk, y)
    okA = np.isfinite(rA) & (rA > 0)
    print(f"\n  ── 去季节 ──")
    print(f"     A 路线（按周比值）：可用点 {int(okA.sum())} / {len(y)}")
    print(f"     B 路线（52周滑动中位数）：可用点 "
          f"{int((np.isfinite(rB) & (rB > 0)).sum())}")

    # ---- 关注窗口 ----
    sel = (wk // 100 == WIN_YEAR) & (wk % 100 >= WIN_W0) & (wk % 100 <= WIN_W1)
    idx = np.where(sel & okA)[0]
    wsel = wk[idx]
    xA = np.log(rA[idx])
    xB = np.log(rB[idx][np.isfinite(rB[idx]) & (rB[idx] > 0)]) \
        if (np.isfinite(rB[idx]) & (rB[idx] > 0)).sum() == len(idx) else None
    print(f"\n  ── 关注窗口：{WIN_YEAR} 年第 {WIN_W0}–{WIN_W1} 周，"
          f"n = {len(idx)} ──")
    print(f"     周次: {', '.join(str(w % 100) for w in wsel)}")
    print(f"     原始 ili: {', '.join(f'{v:.2f}' for v in y[idx])}")
    print(f"     去季节 log r: {', '.join(f'{v:+.2f}' for v in xA)}")

    # ---- 族 I ----
    print(f"\n  ══ 族 I · 分段常数增长率（Bayes 网格后验）══")
    res_I = {}
    for tag, x, pri in (("A/uniform", xA, "uniform"),
                        ("A/edge", xA, "edge")):
        taus, p = posterior_tau_const(x, prior=pri)
        lo, hi = hdi(taus, p)
        # `taus` 是"窗口内下标"，用 wsel 映射回真实周次
        wl = int(wsel[lo]) if lo < len(wsel) else -1
        wh = int(wsel[hi]) if hi < len(wsel) else -1
        pk = int(taus[np.argmax(p)])
        wpk = int(wsel[pk]) if pk < len(wsel) else -1
        print(f"     {tag:<12} 众数 第{wpk % 100}周   95% HDI "
              f"第{wl % 100}–{wh % 100} 周  （宽度 {wh-wl} 周）")
        res_I[tag] = {"mode_week": wpk % 100, "hdi": [wl % 100, wh % 100],
                      "width_weeks": int(wh - wl)}
    if xB is not None:
        taus, p = posterior_tau_const(xB, prior="uniform")
        lo, hi = hdi(taus, p)
        pk = int(taus[np.argmax(p)])
        print(f"     {'B/uniform':<12} 众数 第{wsel[pk] % 100}周   95% HDI "
              f"第{wsel[lo] % 100}–{wsel[hi] % 100} 周"
              f"  （宽度 {wsel[hi]-wsel[lo]} 周）")
        res_I["B/uniform"] = {"mode_week": int(wsel[pk] % 100),
                              "hdi": [int(wsel[lo] % 100),
                                      int(wsel[hi] % 100)],
                              "width_weeks": int(wsel[hi] - wsel[lo])}
    rep["family_I"] = res_I

    # ---- 族 II ----
    print(f"\n  ══ 族 II · 分段线性（斜率变化）══")
    taus2, p2 = posterior_tau_linear(xA)
    lo2, hi2 = hdi(taus2, p2)
    pk2 = int(taus2[np.argmax(p2)])
    _, sl = fit_piecewise_linear(xA, pk2)
    print(f"     众数 第{wsel[pk2] % 100}周   95% HDI "
          f"第{wsel[lo2] % 100}–{wsel[hi2] % 100} 周"
          f"  （宽度 {wsel[hi2]-wsel[lo2]} 周）")
    print(f"     断点前后斜率: {sl[0]:+.3f} / {sl[1]:+.3f} (log/周)")
    print(f"     => 斜率由 {'负/平' if sl[0] <= 0.05 else '正'} 转为 "
          f"{'正' if sl[1] > 0.05 else '非正'}"
          f"  {'**符合起爆定义**' if (sl[0] <= 0.05 and sl[1] > 0.05) else '不符合'}")
    rep["family_II"] = {"mode_week": int(wsel[pk2] % 100),
                        "hdi": [int(wsel[lo2] % 100), int(wsel[hi2] % 100)],
                        "width_weeks": int(wsel[hi2] - wsel[lo2]),
                        "slopes": [float(s) for s in sl]}

    # ---- 中国短序列 ----
    print(f"\n  ══ 中国暴发疫情序列（短样本对比）══")
    with open(CLEAN / "flu_weekly.csv", encoding="utf-8") as f:
        cn = [r for r in csv.DictReader(f) if r.get("outbreak")]
    cw = np.array([int(r["week"]) for r in cn], float)
    cv = np.array([float(r["outbreak"]) for r in cn], float)
    print(f"     n = {len(cn)} 期   周次 {cw.astype(int).tolist()}")
    print(f"     起数 {cv.astype(int).tolist()}")
    # 用 log(1+y) 避免 log(0)；注意 0/1 起时 log 几乎无信息
    xc = np.log1p(cv)
    try:
        tausc, pc = posterior_tau_const(xc, prior="uniform")
        loc, hic = hdi(tausc, pc)
        pkc = int(tausc[np.argmax(pc)])
        print(f"     变点众数 第{int(cw[pkc])}周   95% HDI "
              f"第{int(cw[loc])}–{int(cw[hic])} 周"
              f"  （宽度 {int(cw[hic]-cw[loc])} 周）")
        print(f"     => 长序列宽度 {res_I['A/uniform']['width_weeks']} 周 vs "
              f"短序列 {int(cw[hic]-cw[loc])} 周"
              f"  = {int(cw[hic]-cw[loc])/max(res_I['A/uniform']['width_weeks'],1):.1f} 倍")
        rep["china_short"] = {"n": len(cn),
                              "mode_week": int(cw[pkc]),
                              "hdi": [int(cw[loc]), int(cw[hic])],
                              "width_weeks": int(cw[hic] - cw[loc])}
    except Exception as e:                                       # noqa: BLE001
        print(f"     短序列变点检测失败（样本过小）：{type(e).__name__}: {e}")
        rep["china_short"] = {"n": len(cn), "error": str(e)[:80]}

    # ---- 图 ----
    # 贴合 16:9 幻灯片
    fig, ax = plt.subplots(3, 1, figsize=(12, 8))
    taus, p = posterior_tau_const(xA, prior="uniform")
    ax[0].plot(wsel % 100, y[idx], "o-", color="#c0392b", ms=4)
    ax[0].set_ylabel("ili (%)")
    ax[0].set_title(f"Q2 起爆点检测：{WIN_YEAR} 年第 {WIN_W0}–{WIN_W1} 周",
                    fontsize=13)
    ax[0].grid(alpha=0.3)
    ax[1].plot(wsel % 100, xA, "o-", color="#2c6fbb", ms=4, label="去季节 log r")
    if xB is not None:
        ax[1].plot(wsel % 100, xB, "s--", color="#27ae60", ms=3,
                   label="B 路线")
    ax[1].axvline(res_I["A/uniform"]["mode_week"], color="r", ls=":",
                  label="族 I 众数")
    ax[1].axvspan(res_I["A/uniform"]["hdi"][0], res_I["A/uniform"]["hdi"][1],
                  color="r", alpha=0.12, label="族 I 95% HDI")
    ax[1].set_ylabel("去季节 log 比值")
    ax[1].legend(fontsize=8)
    ax[1].grid(alpha=0.3)
    pm = p / p.max()
    # ★★ 横轴要用**真实周次**，不能用窗口内索引。
    #    我第一版写 `wsel[[t - taus[0] for t in taus]]` ——
    #    把索引又当成下标去索引 `wsel`，结果横轴变成 2×10^5 量级
    #    （图上显示 `+2.026e5`），刻度完全无意义。
    #    `taus` 本身就是**窗口内下标**，直接映射即可：`wsel[taus]`。
    ax[2].bar(wsel[taus] % 100, pm, color="#8e44ad", alpha=0.7, width=0.8)
    ax[2].set_ylabel("后验（归一化）")
    ax[2].set_xlabel("周次")
    ax[2].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "q2_变点.png", dpi=150)
    plt.close(fig)
    print(f"\n  -> {FIGS/'q2_变点.png'}")

    (RES / "q2_变点.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  -> {RES/'q2_变点.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
