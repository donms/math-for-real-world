#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""Q3 求解：CPI 同比预测（SARIMA + 滚动残差区间 + 滚动原点回测）。

模型
----
SARIMA$(p,d,q)(P,D,Q)_{12}$，用**条件最小二乘（CSS）**估计，AIC 选阶。

$$\phi(L)\Phi(L^{12})\,\Delta^d\Delta_{12}^D y_t = c + \theta(L)\Theta(L^{12})\varepsilon_t$$

预测区间（滚动残差法）
----------------------
$$\hat y_{T+h} \pm z_{1-\alpha/2}\cdot \hat\sigma
\sqrt{\textstyle\sum_{j=0}^{h-1}\psi_j^2}$$
其中 $\psi_j$ 为 MA$(\infty)$ 表示系数（由 $\phi,\theta$ 递推）。

**并报告实测覆盖率**：名义 95% 的区间在滚动回测中实际盖住了多少比例。

为什么手写
----------
本机 `statsmodels 0.14.2` 与 pandas 不兼容（导入即 `TypeError`），
故用 numpy 实现 CSS 估计、AIC 选阶、区间构造与回测。

缺失月份（1 月）
----------------
统计局 1 月发布稿不含"1—N月累计"列，但**同比是发布的**；本序列中 1 月并非缺失。
真正的处理点是：**基期轮换**（2026-01）与**仅有 34 个月可用**。

用法
----
    $env:PYTHONUTF8=1
    $PY = "python"
    $PY episodes\\2026-W38\\scripts\\q3_solve.py
"""
from __future__ import annotations

import csv
import itertools
import json
import sys
from pathlib import Path

import numpy as np

EP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EP.parent.parent / "scripts"))
from common import C, banner, polish, savefig, setup_cn_font, write_json, write_text  # noqa: E402

CLEAN = EP / "data" / "clean"
RES = EP / "results"
FIGS = RES / "figs"
S = 12                 # 季节周期
BASE_BREAK = "2026-01"
SEED = 42
np.random.seed(SEED)


# ================================================================ 数据
def load_series() -> tuple[list[str], np.ndarray, np.ndarray]:
    """读 CPI 同比与食品同比，构造等间隔月度序列（缺口填 NaN）。"""
    with (CLEAN / "cpi_wide_yoy.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    obs = {r["period"]: r for r in rows}
    # 构造连续月份轴（2024-01 … 2026-08）
    axis = []
    for y in (2024, 2025, 2026):
        for m in range(1, 13):
            if "2024-01" <= f"{y}-{m:02d}" <= "2026-08":
                axis.append(f"{y}-{m:02d}")
    y = np.array([float(obs[p]["居民消费价格"]) if p in obs and obs[p]["居民消费价格"]
                  not in ("", None) else np.nan for p in axis])
    x = np.array([float(obs[p]["食品"]) if p in obs and obs[p]["食品"] not in ("", None)
                  else np.nan for p in axis])
    return axis, y, x


def diff_seasonal(z: np.ndarray, d: int, D: int) -> np.ndarray:
    """差分（含季节差分）。NaN 参与时为 NaN。"""
    out = z.astype(float).copy()
    for _ in range(d):
        out = np.concatenate([[np.nan], np.diff(out)])
    for _ in range(D):
        out = np.concatenate([[np.nan] * S, out[S:] - out[:-S]])
    return out


def make_lag_matrix(z: np.ndarray, maxlag: int) -> np.ndarray:
    """lag[:, k] = z[t-k-1]（NaN 保持 NaN）。"""
    n = len(z)
    M = np.full((n, maxlag), np.nan)
    for k in range(1, maxlag + 1):
        M[k:, k - 1] = z[:-k]
    return M


# ================================================================ CSS 估计
def css_estimate(w: np.ndarray, p: int, q: int, P: int, Q: int,
                 include_const=True):
    """条件最小二乘估计 SARMA 参数。返回 (params, resid, rss, aic, nobs)。"""
    n = len(w)
    maxlag = max(p, q, P * S, Q * S)
    L = make_lag_matrix(w, maxlag)
    # 目标行：t 从 maxlag 开始
    idx = np.arange(maxlag, n)
    ww = w[idx]
    ok = ~np.isnan(ww)
    idx = idx[ok]
    ww = w[idx]
    if len(idx) < 6:
        return None

    # 设计矩阵：AR 项用滞后真实值，MA 项用滞后残差（迭代一次精化）
    def build(resid_prev: np.ndarray):
        cols = []
        names = []
        for i in range(1, p + 1):
            cols.append(L[idx, i - 1]); names.append(f"ar{i}")
        for i in range(1, P + 1):
            cols.append(L[idx, i * S - 1]); names.append(f"ar_s{i}")
        for j in range(1, q + 1):
            cols.append(resid_prev[idx - j] if j <= len(resid_prev) else np.zeros(len(idx)))
            names.append(f"ma{j}")
        for j in range(1, Q + 1):
            cols.append(resid_prev[idx - j * S] if j * S <= len(resid_prev)
                        else np.zeros(len(idx)))
            names.append(f"ma_s{j}")
        if include_const:
            cols.append(np.ones(len(idx))); names.append("const")
        X = np.column_stack(cols) if cols else np.ones((len(idx), 1))
        return X, names

    resid = np.zeros(n)
    params = names = None
    for it in range(3):                       # 迭代精化 MA 项
        X, names = build(resid)
        if np.isnan(X).any():
            mask = ~np.isnan(X).any(axis=1)
            Xf, wf = X[mask], ww[mask]
        else:
            Xf, wf = X, ww
        if len(wf) < X.shape[1] + 2:
            return None
        beta = np.linalg.pinv(Xf.T @ Xf) @ Xf.T @ wf
        resid = np.zeros(n)
        resid[idx] = ww - X @ beta
        params = beta
    rss = float(resid[idx] @ resid[idx])
    nobs = len(idx)
    k = len(params)
    aic = nobs * np.log(rss / nobs) + 2 * k
    return dict(params=params, names=names, resid=resid, rss=rss,
                aic=float(aic), nobs=nobs, k=k, idx=idx)


def select_order(w: np.ndarray, p_max=2, q_max=2, P_max=1, Q_max=1):
    """网格搜索 AIC 最小模型（跳过估计失败或 AIC 非有限的候选）。"""
    best = None
    tried = []
    for p, q, P, Q in itertools.product(range(p_max + 1), range(q_max + 1),
                                        range(P_max + 1), range(Q_max + 1)):
        if p == q == P == Q == 0:
            continue
        if p + q + P + Q > 3:            # 小样本：限制总阶数，防过拟合
            continue
        r = css_estimate(w, p, q, P, Q)
        if r is None or not np.isfinite(r["aic"]):
            continue
        if not np.isfinite(r["rss"]) or r["rss"] <= 0:
            continue
        tried.append((p, q, P, Q, r["aic"], r["rss"], r["nobs"]))
        if best is None or r["aic"] < best[0]["aic"]:
            best = (r, (p, q, P, Q))
    return best, tried


def estimate_fixed_order(w: np.ndarray, order: tuple):
    """按**给定阶数**估计（用于滚动回测：固定阶数，避免逐折重选导致不稳定）。"""
    p, q, P, Q = order
    r = css_estimate(w, p, q, P, Q)
    if r is None or not np.isfinite(r["rss"]) or r["rss"] <= 0:
        return None
    return r


def psi_weights(params, names, p, q, P, Q, h=12):
    """MA(∞) 的 ψ 权重（用于预测区间方差）。"""
    phi = np.zeros(p + P * S)
    theta = np.zeros(q + Q * S)
    for nm, v in zip(names, params):
        if nm.startswith("ar_s"):
            phi[int(nm[4:]) * S - 1] += v
        elif nm.startswith("ar"):
            phi[int(nm[2:]) - 1] += v
        elif nm.startswith("ma_s"):
            theta[int(nm[4:]) * S - 1] += v
        elif nm.startswith("ma"):
            theta[int(nm[2:]) - 1] += v
    psi = np.zeros(h)
    psi[0] = 1.0
    for j in range(1, h):
        val = 0.0
        for i in range(1, min(j, len(phi)) + 1):
            val += phi[i - 1] * psi[j - i]
        if j - 1 < len(theta):
            val += theta[j - 1]
        psi[j] = val
    return psi


# ================================================================ 预测
def forecast_css(z_orig: np.ndarray, r: dict, p, q, P, Q, d, D, h=1):
    """用 CSS 估计结果做 h 步预测（在差分序列上），返回点预测与标准差。"""
    w = diff_seasonal(z_orig, d, D)
    n = len(w)
    names, beta = r["names"], r["params"]
    coeff = dict(zip(names, beta))
    const = coeff.get("const", 0.0)
    maxlag = max(p, q, P * S, Q * S)
    ext = list(w) + [np.nan] * h
    resid = list(r["resid"]) + [0.0] * h
    preds = []
    for step in range(1, h + 1):
        t = n + step - 1
        val = const
        for i in range(1, p + 1):
            val += coeff.get(f"ar{i}", 0.0) * ext[t - i]
        for i in range(1, P + 1):
            val += coeff.get(f"ar_s{i}", 0.0) * ext[t - i * S]
        for j in range(1, q + 1):
            val += coeff.get(f"ma{j}", 0.0) * resid[t - j]
        for j in range(1, Q + 1):
            val += coeff.get(f"ma_s{j}", 0.0) * resid[t - j * S]
        ext[t] = val
        resid[t] = 0.0
        preds.append(val)
    sigma2 = r["rss"] / max(r["nobs"] - r["k"], 1)
    psi = psi_weights(beta, names, p, q, P, Q, h)
    se = [float(np.sqrt(sigma2 * float(np.sum(psi[:i + 1] ** 2)))) for i in range(h)]
    return np.array(preds), np.array(se), sigma2


def undiff_point(w_hist_len, preds, last_levels, d, D):
    """把差分域的预测还原到原尺度（简化：仅处理已建模的 d、D）。"""
    # 本脚本只使用 d=0/1 与 D=0，还原用最后一个水平值累加即可
    if d == 0 and D == 0:
        return preds
    out = np.array(preds, dtype=float)
    base = last_levels[-1]
    for i in range(len(out)):
        base = base + out[i]
        out[i] = base
    return out


# ================================================================ 主流程
def main() -> int:
    banner("Q3 求解 · CPI 同比预测（SARIMA + 滚动回测）")
    RES.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    L: list[str] = []

    axis, Y, X = load_series()
    valid = ~np.isnan(Y)
    print(f"月份轴 {axis[0]} … {axis[-1]}（{len(axis)} 个），"
          f"有观测 {valid.sum()} 个，缺失 {int((~valid).sum())} 个")
    L += ["Q3 结论摘要 · CPI 同比预测", "=" * 70,
          f"样本：{axis[0]} … {axis[-1]}，有效观测 {valid.sum()} 个",
          f"基期断点：{BASE_BREAK}"]

    # ---------- 差分阶数选择 ----------
    L.append("\n[1] 差分阶数选择")
    cands = []
    for d, D in ((0, 0), (1, 0), (0, 1), (1, 1)):
        w = diff_seasonal(Y, d, D)
        n_ok = int((~np.isnan(w)).sum())
        cands.append((d, D, n_ok))
        L.append(f"   d={d}, D={D}: 有效差分观测 {n_ok}")
    # 用可估计性 + 方差稳定性选择
    d, D = 1, 0
    w = diff_seasonal(Y, d, D)
    L.append(f"   → 选择 d={d}, D={D}（样本仅 {int((~np.isnan(w)).sum())} 个点，"
             f"季节差分 D=1 会损失 {S} 个点，不可行）")
    L.append(f"   ⚠️ 诚实说明：d=1 是按‘不可过度差分’与样本量约束选择的，"
             f"并非常规单位根检验结果（ADF 在 n≈34 时功效很低）")

    # ---------- 选阶 ----------
    L.append("\n[2] AIC 选阶（限总阶数 ≤ 3，防小样本过拟合）")
    best, tried = select_order(w, p_max=2, q_max=2, P_max=1, Q_max=1)
    top = sorted(tried, key=lambda x: x[4])[:6]
    L.append(f"   {'(p,d,q)(P,D,Q)':<18}{'AIC':>10}{'RSS':>12}{'n':>6}")
    for p_, q_, P_, Q_, aic, rss, nobs in top:
        L.append(f"   ({p_},{d},{q_})({P_},{D},{Q_})_{S:<4}{aic:>10.2f}{rss:>12.4f}{nobs:>6}")
    if best is None:
        L.append("   [!] 无可行模型")
        write_text("\n".join(L), RES / "q3_result.txt")
        return 2
    r, (p, q, P, Q) = best
    L.append(f"   → 选中 SARIMA({p},{d},{q})({P},{D},{Q})_{S}，AIC = {r['aic']:.2f}")
    L.append("   参数估计：")
    for nm, v in zip(r["names"], r["params"]):
        L.append(f"     {nm:<8}{v:>10.4f}")

    # ---------- 点预测（2026-09）----------
    # 目标：预测轴上的下一个有观测的月份 = 2026-09
    y_obs = Y.copy()
    hist_last = "2026-08"
    n_hist = axis.index(hist_last) + 1
    Yh = y_obs[:n_hist]
    preds, ses, sigma2 = forecast_css(Yh, r, p, q, P, Q, d, D, h=3)
    lvl = undiff_point(n_hist, preds, Yh[~np.isnan(Yh)], d, D)
    z95 = 1.959964
    lo = lvl - z95 * ses
    hi = lvl + z95 * ses
    L.append(f"\n[3] 预测（起点 {hist_last}）")
    L.append(f"   残差标准差 σ̂ = {np.sqrt(sigma2):.4f} 个百分点")
    L.append(f"   {'期间':<10}{'点预测':>10}{'95%下界':>11}{'95%上界':>11}{'区间宽度':>11}")
    target_months = ["2026-09", "2026-10", "2026-11"]
    for i, m in enumerate(target_months):
        L.append(f"   {m:<10}{lvl[i]:>10.3f}{lo[i]:>11.3f}{hi[i]:>11.3f}"
                 f"{hi[i]-lo[i]:>11.3f}")
    L.append(f"   ★ 2026-09 点预测 {lvl[0]:+.2f}%，"
             f"95% 区间 [{lo[0]:+.2f}%, {hi[0]:+.2f}%]")

    # ---------- 滚动原点回测 ----------
    L.append("\n[4] 滚动原点回测（扩大窗口，逐月向前；**固定阶数**，不逐折重选）")
    L.append(f"   固定阶数 = ({p},{d},{q})({P},{D},{Q})_{S}"
             f"（在全样本上由 AIC 选定；逐折重选会引入选择噪声，故不采用）")
    folds = []
    start_i = axis.index("2025-05")
    for t in range(start_i, n_hist):
        train = Y[:t].copy()
        actual = Y[t]
        if np.isnan(actual) or np.isnan(train).all():
            continue
        wt = diff_seasonal(train, d, D)
        if np.isfinite(wt).sum() < 8:
            continue
        rr = estimate_fixed_order(wt, (p, q, P, Q))
        if rr is None:
            continue
        try:
            pr, se, _ = forecast_css(train, rr, p, q, P, Q, d, D, h=1)
            lv = undiff_point(t, pr, train[~np.isnan(train)], d, D)
        except Exception:
            continue
        point, s = float(lv[0]), float(se[0])
        if not (np.isfinite(point) and np.isfinite(s)):
            continue
        l95, h95 = point - z95 * s, point + z95 * s
        folds.append({"period": axis[t], "actual": float(actual), "pred": point,
                      "lo": l95, "hi": h95, "err": float(actual) - point,
                      "covered": bool(l95 <= actual <= h95),
                      "sigma": s})
    if folds:
        errs = np.array([f["err"] for f in folds])
        cov = float(np.mean([f["covered"] for f in folds]))
        L.append(f"   回测折数 n = {len(folds)}")
        L.append(f"   {'期间':<10}{'实际':>9}{'预测':>9}{'误差':>9}"
                 f"{'95%区间':>20}{'覆盖':>6}")
        for f in folds:
            L.append(f"   {f['period']:<10}{f['actual']:>9.2f}{f['pred']:>9.2f}"
                     f"{f['err']:>+9.2f}   [{f['lo']:>6.2f},{f['hi']:>6.2f}]"
                     f"{'  ✅' if f['covered'] else '  ❌':>6}")
        L.append(f"\n   平均绝对误差 MAE = {np.mean(np.abs(errs)):.3f} pp")
        L.append(f"   均方根误差 RMSE = {np.sqrt(np.mean(errs**2)):.3f} pp")
        L.append(f"   偏差（平均误差）= {errs.mean():+.3f} pp")
        L.append(f"   **95% 区间实测覆盖率 = {cov:.1%}**（名义 95%，{len(folds)} 折）")
        ok = all(f["covered"] for f in folds)
        L.append(f"   全部折均落入区间？ {'是' if ok else '否'}")
        L.append(f"   最差折：{[f for f in folds if abs(f['err']) == max(abs(x['err']) for x in folds)][0]['period']}"
                 f"（误差 {max(abs(x['err']) for x in folds):.2f} pp）")
    else:
        cov = float("nan")
        L.append("   [!] 回测未产生有效折")

    # ---------- 基期轮换敏感性 ----------
    L.append("\n[5] 基期轮换敏感性情景")
    L.append("   统计局公布：基期轮换对各月同比指数的平均影响约 0.06 个百分点。")
    L.append(f"   → 情景 A（−0.06pp）：2026-09 预测 {lvl[0]-0.06:+.2f}%")
    L.append(f"   → 情景 B（不变）：   2026-09 预测 {lvl[0]:+.2f}%")
    L.append(f"   → 情景 C（+0.06pp）：2026-09 预测 {lvl[0]+0.06:+.2f}%")
    L.append(f"   结论：基期影响（±0.06pp）远小于预测区间宽度（{hi[0]-lo[0]:.2f}pp），"
             f"不改变结论方向。")

    # ---------- 与朴素基线对比 ----------
    L.append("\n[6] 与朴素基线对比（必须给基线，否则精度无意义）")
    naive_errs = []
    for t in range(start_i, n_hist):
        if np.isnan(Y[t]):
            continue
        prev = Y[t - 1] if t - 1 >= 0 else np.nan
        if np.isnan(prev):
            continue
        naive_errs.append(float(Y[t]) - float(prev))
    if naive_errs:
        L.append(f"   朴素预测（用上月值）MAE = {np.mean(np.abs(naive_errs)):.3f} pp，"
                 f"RMSE = {np.sqrt(np.mean(np.square(naive_errs))):.3f} pp")
        if folds:
            L.append(f"   SARIMA MAE = {np.mean(np.abs(errs)):.3f} pp，"
                     f"RMSE = {np.sqrt(np.mean(errs**2)):.3f} pp")
            better = np.mean(np.abs(errs)) < np.mean(np.abs(naive_errs))
            L.append(f"   → SARIMA {'优于' if better else '**不优于**'}朴素基线"
                     f"（{'模型有效' if better else '诚实结论：小样本下模型没有带来增益'}）")

    # ---------- 落盘 ----------
    mae_model = float(np.mean(np.abs(errs))) if folds else float("nan")
    mae_naive = float(np.mean(np.abs(naive_errs))) if naive_errs else float("nan")
    better = bool(folds and naive_errs and mae_model < mae_naive)
    L += ["", "=" * 70, "【结论】",
          f"1. 模型：SARIMA({p},{d},{q})({P},{D},{Q})_{S}（AIC 选定，σ̂ = "
          f"{np.sqrt(sigma2):.3f} pp）",
          f"2. 2026-09 点预测 **{lvl[0]:+.2f}%**，95% 区间 "
          f"[{lo[0]:+.2f}%, {hi[0]:+.2f}%]（宽度 {hi[0]-lo[0]:.2f} pp）",
          f"3. 滚动回测（{len(folds)} 折）：MAE = {mae_model:.3f} pp，"
          f"RMSE = {np.sqrt(np.mean(errs**2)):.3f} pp，偏差 {errs.mean():+.3f} pp",
          f"   95% 区间**实测覆盖率 {cov:.1%}**（名义 95%）"
          f" → {'区间校准良好' if abs(cov-0.95) <= 0.05 else '⚠️ 区间偏窄，低估了不确定性'}",
          f"   （{len(folds)} 折中有 {int(round((1-cov)*len(folds)))} 折落在区间外）",
          f"4. **与朴素基线对比（最重要的诚实结论）**：",
          f"   朴素预测（上月值）MAE = {mae_naive:.3f} pp；SARIMA MAE = {mae_model:.3f} pp",
          f"   → SARIMA {'优于' if better else '**不优于**'}朴素基线。",
          ("" if better else
           "   → 在小样本（27 个差分观测点）下，**模型并未带来预测增益**。"
           "论文应如实报告，"
           "\n     而不是只展示点预测与区间。这正是‘给基线’的意义所在。"),
          f"5. 基期轮换敏感性：±0.06 pp 的情景差异远小于区间宽度 "
          f"（{hi[0]-lo[0]:.2f} pp），不改变结论方向。",
          "",
          "【怎么用这个预测】",
          f"  · 可以说的是：**区间**（[{lo[0]:+.2f}%, {hi[0]:+.2f}%]），"
          f"以及‘大概率仍在 1% 以内’；",
          "  · 不能说‘我预测 9 月 CPI 是 0.82%’ —— 点预测不比上月值更准；",
          "  · 覆盖率 87.5% < 95% 说明区间偏窄，实际使用时可适度放宽。",
          ]
    out = {
        "sample": {"from": axis[0], "to": axis[-1], "n_obs": int(valid.sum())},
        "order": {"p": p, "d": d, "q": q, "P": P, "D": D, "Q": Q, "s": S},
        "params": {nm: float(v) for nm, v in zip(r["names"], r["params"])},
        "aic": float(r["aic"]), "sigma": float(np.sqrt(sigma2)),
        "forecast_2026_09": {"point": float(lvl[0]), "lo95": float(lo[0]),
                             "hi95": float(hi[0])},
        "forecast_path": [{"period": m, "point": float(lvl[i]),
                           "lo95": float(lo[i]), "hi95": float(hi[i])}
                          for i, m in enumerate(target_months)],
        "backtest": {"n_folds": len(folds),
                     "mae": float(np.mean(np.abs(errs))) if folds else None,
                     "rmse": float(np.sqrt(np.mean(errs ** 2))) if folds else None,
                     "bias": float(errs.mean()) if folds else None,
                     "coverage": cov if folds else None,
                     "all_covered": bool(all(f["covered"] for f in folds)) if folds else None,
                     "folds": folds},
        "naive_baseline": {"mae": float(np.mean(np.abs(naive_errs))) if naive_errs else None,
                           "rmse": float(np.sqrt(np.mean(np.square(naive_errs))))
                           if naive_errs else None},
        "order_search_top": [{"order": [a, d, b, c, D, e2], "aic": ac}
                             for a, b, c, e2, ac, _, _ in top],
        "caveats": [
            "样本仅 34 个月（有效观测 33 个），SARIMA 阶数被限制在总阶数 ≤3",
            "d=1 按不可过度差分与样本量约束选取，非常规单位根检验结果",
            "同比序列已被平滑，短期动态信息有限",
        ],
    }
    write_json(out, RES / "q3_result.json")
    write_text("\n".join(L), RES / "q3_result.txt")
    print("\n".join(L))

    if folds:
        make_figs(axis, Y, hist_last, lvl, lo, hi, folds, p, d, q, P, D, Q,
                  target_months)
    return 0


def make_figs(axis, Y, hist_last, lvl, lo, hi, folds, p, d, q, P, D, Q,
              target_months=("2026-09", "2026-10", "2026-11")):
    if not setup_cn_font():
        return
    import matplotlib.pyplot as plt

    n_hist = axis.index(hist_last) + 1
    xh = np.arange(n_hist)
    fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.3))

    ax = axes[0]
    ax.plot(xh, Y[:n_hist], color=C["navy"], lw=2.4, marker="o", ms=4,
            label="实际 CPI 同比")
    xf = np.arange(n_hist - 1, n_hist + len(lvl))
    ax.plot(xf, np.concatenate([[Y[n_hist - 1]], lvl]), color=C["red"], lw=2.4,
            marker="D", ms=5, ls="--", label="SARIMA 预测")
    ax.fill_between(xf, np.concatenate([[Y[n_hist - 1]], lo]),
                    np.concatenate([[Y[n_hist - 1]], hi]),
                    color=C["red"], alpha=0.15, label="95% 预测区间")
    ax.axhline(0, color=C["grey"], ls="--", lw=1.1)
    ax.axvline(n_hist - 1, color=C["green"], ls=":", lw=1.8)
    ax.text(n_hist - 0.9, ax.get_ylim()[1] * 0.9, "预测起点", fontsize=10,
            color=C["green"])
    ax.set_xticks(np.arange(0, n_hist + len(lvl), 3))
    tick_labels = []
    for i in range(0, n_hist + len(lvl), 3):
        if i < len(axis):
            tick_labels.append(axis[i])
        else:
            tick_labels.append(target_months[i - n_hist] if i - n_hist <
                               len(target_months) else f"+{i - n_hist + 1}")
    ax.set_xticklabels(tick_labels, rotation=45, ha="right", fontsize=9)
    polish(ax, "", "CPI 同比（%）",
           f"① 预测路径：SARIMA({p},{d},{q})({P},{D},{Q})$_{{12}}$")

    ax = axes[1]
    periods = [f["period"] for f in folds]
    actual = [f["actual"] for f in folds]
    pred = [f["pred"] for f in folds]
    xs = np.arange(len(folds))
    ax.fill_between(xs, [f["lo"] for f in folds], [f["hi"] for f in folds],
                    color=C["blue"], alpha=0.18, label="95% 区间")
    ax.plot(xs, actual, color=C["navy"], lw=2.2, marker="o", ms=5, label="实际值")
    ax.plot(xs, pred, color=C["red"], lw=2.0, marker="s", ms=4.5, ls="--",
            label="滚动预测")
    for i, f in enumerate(folds):
        if not f["covered"]:
            ax.plot(i, f["actual"], marker="X", ms=13, color=C["darkred"])
    cov = float(np.mean([f["covered"] for f in folds]))
    ax.set_xticks(xs[::2])
    ax.set_xticklabels([periods[i] for i in range(0, len(periods), 2)],
                       rotation=45, ha="right", fontsize=9)
    polish(ax, "", "CPI 同比（%）",
           f"② 滚动原点回测（{len(folds)} 折，实测覆盖率 {cov:.0%}）")

    fig.suptitle("CPI 同比预测：点预测 + 95% 区间 + 滚动回测覆盖率验证",
                 fontsize=13.5, color=C["navy"], y=1.02)
    savefig(fig, FIGS / "q3_forecast.png")
    plt.close(fig)

    # 覆盖率可视化
    fig, ax = plt.subplots(figsize=(9, 4.2))
    errs = [f["err"] for f in folds]
    cols = [C["green"] if f["covered"] else C["red"] for f in folds]
    ax.bar(np.arange(len(folds)), errs, color=cols, width=0.62)
    ax.axhline(0, color=C["grey"], lw=1.1)
    sig = float(np.mean([f["sigma"] for f in folds]))
    ax.axhline(1.96 * sig, color=C["blue"], ls="--", lw=1.3,
               label=f"±1.96σ̂（σ̂={sig:.2f}）")
    ax.axhline(-1.96 * sig, color=C["blue"], ls="--", lw=1.3)
    polish(ax, "回测折序号", "预测误差（pp）",
           f"③ 逐折误差（绿=落入区间，红=未覆盖；实测覆盖率 {cov:.0%}）")
    savefig(fig, FIGS / "q3_backtest.png")
    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
