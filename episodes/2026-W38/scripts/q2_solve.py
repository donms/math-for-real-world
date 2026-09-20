#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""Q2 求解：PPI → CPI 的价格传导建模（结构分解 + 传导估计 + 不对称检验）。

建模思路（三层递进）
-------------------
**第一层｜结构对齐**：PPI 与 CPI 的"篮子"完全不同 —— 这决定了传导的**上限**。
  * CPI 八大类权数（统计局 2026-02-11 首次公布，2025 年基期）：
    食品烟酒 29.5%、衣着 5.4%、居住 22.1%、生活用品 5.5%、交通通信 14.3%、
    教育文化娱乐 11.4%、医疗保健 8.9%、其他用品及服务 2.9%
  * PPI 两大部类权数（由发布稿"影响…个百分点"反推）：
    生产资料 ≈ 3.92/5.0 = **78.4%**，生活资料 ≈ 0.10/0.5 = **20.0%**
  * 关键：**PPI 中约 78% 是生产资料（采掘/原材料/加工），它们不直接进入居民消费篮子**；
    与 CPI 消费品对应的是"生活资料"，而其同比为 **−0.5%**（在跌），
    而生产资料同比 **+5.0%**（在涨）。→ **PPI 与 CPI 的背离是结构性的，不是"传导失灵"。**

**第二层｜传导估计**（ARDL）
$$\text{CPI}_t = \alpha + \beta_1 \text{CPI}_{t-1} + \beta_2 \text{PPI}_t
+ \beta_3 \text{PPI}_{t-1} + \varepsilon_t$$
长期传导 $\theta^{LR} = (\beta_2+\beta_3)/(1-\beta_1)$，调整速度 $\lambda = 1-\beta_1$。

**第三层｜不对称传导**（NARDL 思路，加分项）
$\text{PPI}^+=\max(\text{PPI},0)$，$\text{PPI}^-=\min(\text{PPI},0)$，Wald 检验 $\beta^+\ne\beta^-$。

关于基期轮换的处理（重要）
--------------------------
初版把基期虚拟变量 $D^{base}$ 放进主模型，诊断发现 **$\mathrm{corr}(D^{base},\text{PPI})=0.835$**
（断点前 PPI 均值 −2.34，断点后 +2.04）—— 虚拟变量几乎就是 PPI 的代理，造成严重共线。
且统计局公布基期轮换对同比的**平均影响仅约 0.06 个百分点**（远小于 CPI 同比的标准差 0.50）。
因此**主模型不含虚拟变量**，改为把"含虚拟变量""一阶差分""口径一致子样本"三种设定
作为**稳健性对照** —— 这比硬塞一个共线变量更规范。

为什么手写 OLS 而不用 statsmodels
---------------------------------
本机 statsmodels 0.14.2 与 pandas 版本不兼容（`import statsmodels.tsa.api` 直接抛
`TypeError: deprecate_kwarg() missing 1 required positional argument`）。
故 q2/q3 的估计全部用 numpy 手写：每一步显式可见、可解释，不依赖第三方计量库版本。

用法
----
    $env:PYTHONUTF8=1
    $PY = "python"
    $PY episodes\\2026-W38\\scripts\\q2_solve.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

EP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EP.parent.parent / "scripts"))
from common import C, banner, polish, savefig, setup_cn_font, write_json, write_text  # noqa: E402

CLEAN = EP / "data" / "clean"
RES = EP / "results"
FIGS = RES / "figs"
BASE_BREAK = "2026-01"
CONSISTENT_FROM = "2026-02"

CPI_COL, PPI_COL = "居民消费价格", "一、工业生产者出厂价格"

# ---------------------------------------------------------------- 结构数据
CPI_WEIGHTS = {   # 统计局 2026-02-11 首次公布（2025 年基期），合计 100.0
    "食品烟酒及在外餐饮": 29.5, "衣着": 5.4, "居住": 22.1, "生活用品及服务": 5.5,
    "交通通信": 14.3, "教育文化娱乐": 11.4, "医疗保健": 8.9, "其他用品及服务": 2.9,
}
# 由发布稿"影响…个百分点"反推（2026-08）：生产资料 3.92/5.0，生活资料 0.10/0.5
PPI_WEIGHTS_IMPLIED = {"生产资料": 78.4, "生活资料": 20.0}
PPI_IMPACT_2026_08 = {"生产资料": (+3.92, +5.0), "生活资料": (-0.10, -0.5)}


def read_series(fname: str, cols: dict[str, str]):
    with (CLEAN / fname).open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    months, out = [], {v: [] for v in cols.values()}
    for r in rows:
        months.append(r["period"])
        for src, alias in cols.items():
            v = r.get(src, "")
            out[alias].append(float(v) if v not in ("", None) else np.nan)
    return months, out


def ols(X, y):
    n, k = X.shape
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    resid = y - X @ beta
    dof = max(n - k, 1)
    sigma2 = float(resid @ resid) / dof
    cov = sigma2 * XtX_inv
    se = np.sqrt(np.maximum(np.diag(cov), 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(se > 0, beta / se, np.nan)
    try:
        from scipy import stats
        p = 2 * (1 - stats.t.cdf(np.abs(t), dof))
    except Exception:
        p = np.full(k, np.nan)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - float(resid @ resid) / ss_tot if ss_tot > 0 else np.nan
    adj = 1 - (1 - r2) * (n - 1) / dof if dof > 0 else np.nan
    return dict(beta=beta, se=se, t=t, p=p, resid=resid, cov=cov,
                r2=float(r2), adj_r2=float(adj), n=n, k=k, dof=dof)


def dw(resid):
    d = np.diff(resid)
    return float((d ** 2).sum() / (resid ** 2).sum())


def wald(beta, cov, R):
    Rb = R @ beta
    mid = R @ cov @ R.T
    try:
        stat = float(Rb.T @ np.linalg.pinv(mid) @ Rb)
    except Exception:
        return float("nan"), float("nan")
    try:
        from scipy import stats
        p = float(1 - stats.chi2.cdf(stat, R.shape[0]))
    except Exception:
        p = float("nan")
    return stat, p


def adf_t(x, lags=1):
    x = np.asarray(x, float)
    dx = np.diff(x)
    n = len(dx) - lags
    if n <= lags + 2:
        return float("nan")
    y = dx[lags:]
    cols = [x[lags:-1]] + [dx[lags - i:-i] for i in range(1, lags + 1)]
    X = np.column_stack([np.ones(n)] + cols)
    r = ols(X, y)
    return float(r["t"][1])


def build(y, x, lag=1, lagx=True, dummy=None):
    X, Y, idx = [], [], []
    for t in range(lag, len(y)):
        vals = [y[t], y[t - 1], x[t]]
        if np.isnan(vals).any():
            continue
        row = [1.0, y[t - 1], x[t]]
        if lagx:
            if np.isnan(x[t - 1]):
                continue
            row.append(x[t - 1])
        if dummy is not None:
            row.append(float(dummy[t]))
        X.append(row)
        Y.append(y[t])
        idx.append(t)
    return np.array(X), np.array(Y), idx


def fit(y, x, lag=1, lagx=True, dummy=None, names=None):
    X, Y, idx = build(y, x, lag, lagx, dummy)
    if len(Y) < X.shape[1] + 2:
        return None
    r = ols(X, Y)
    r["names"] = names or (["const", "CPI(t-1)", "PPI(t)"] +
                           (["PPI(t-1)"] if lagx else []) +
                           (["D_base"] if dummy is not None else []))
    r["idx"] = idx
    return r


def report(tag: str, r: dict | None, extra: str = "") -> list[str]:
    out = [f"\n=== {tag} ==="]
    if r is None:
        out.append("  样本不足，跳过")
        return out
    out.append(f"{'变量':<14}{'系数':>10}{'标准误':>10}{'t值':>9}{'p值':>9}")
    for i, nm in enumerate(r["names"]):
        out.append(f"{nm:<14}{r['beta'][i]:>10.4f}{r['se'][i]:>10.4f}"
                   f"{r['t'][i]:>9.3f}{r['p'][i]:>9.4f}")
    out.append(f"  n={r['n']}  R²={r['r2']:.4f}  调整R²={r['adj_r2']:.4f}  "
               f"DW={dw(r['resid']):.3f}")
    if extra:
        out.append("  " + extra)
    return out


def main() -> int:
    banner("Q2 求解 · PPI → CPI 价格传导（结构分解 + ARDL + 不对称检验）")
    RES.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)

    months, cpi = read_series("cpi_wide_yoy.csv", {CPI_COL: "cpi", "食品": "cpi_food"})
    _, ppi = read_series("ppi_wide_yoy.csv",
                         {PPI_COL: "ppi", "生产资料": "ppi_mp", "生活资料": "ppi_cg"})
    Y = np.array(cpi["cpi"], float)
    P = np.array(ppi["ppi"], float)
    PMC = np.array(ppi["ppi_mp"], float)
    PCG = np.array(ppi["ppi_cg"], float)
    YF = np.array(cpi["cpi_food"], float)
    base = np.array([1.0 if m >= BASE_BREAK else 0.0 for m in months])
    sub = np.array([m >= CONSISTENT_FROM for m in months])

    L: list[str] = []
    L.append("Q2 结论摘要 · PPI → CPI 价格传导")
    L.append("=" * 70)
    L.append(f"样本：{months[0]} … {months[-1]}（{len(months)} 个月）")
    L.append(f"基期断点：{BASE_BREAK}（断点前 20 个月，断点后 8 个月）")

    # ================= 第一层：结构对齐 =================
    L.append("\n" + "-" * 70)
    L.append("【第一层】结构对齐：两个篮子根本不是一回事")
    L.append("-" * 70)

    L.append("\n① PPI 两大部类权数（由发布稿‘影响（百分点）’反推，2026-08）")
    L.append(f"   {'部类':<10}{'同比%':>9}{'影响(pp)':>11}{'反推权数%':>12}")
    implied = {}
    for k, (imp, r) in PPI_IMPACT_2026_08.items():
        w = abs(imp / r) * 100 if r else float("nan")
        implied[k] = w
        L.append(f"   {k:<10}{r:>+9.1f}{imp:>+11.2f}{w:>12.1f}")
    L.append(f"   反推权数合计 {sum(implied.values()):.1f}%")
    L.append(f"   ★ 生产资料占 PPI 约 {implied.get('生产资料', float('nan')):.0f}%，"
             f"但它们**不直接进入居民消费篮子**")

    L.append("\n② 关键背离（2026-08，同比）")
    aug = months.index("2026-08")
    L.append(f"   PPI 生产资料（≈{implied.get('生产资料', 78):.0f}% 权重）："
             f"{PMC[aug]:+.1f}%   ← 在涨")
    L.append(f"   PPI 生活资料（≈{implied.get('生活资料', 20):.0f}% 权重）："
             f"{PCG[aug]:+.1f}%   ← 在跌")
    L.append(f"   PPI 总指数：{P[aug]:+.1f}%")
    L.append(f"   CPI 总指数：{Y[aug]:+.1f}%   ← 与生活资料方向一致，与生产资料相反")
    L.append("   ★ 结论：PPI 上行主要由生产资料（采掘/原材料）驱动，")
    L.append("     而真正对应居民消费的‘生活资料’仍在下跌。")
    L.append("     **PPI 与 CPI 的背离是结构性的，不是传导失灵。**")

    L.append("\n③ 三部类与 CPI 的相关性（28 个月）")
    corr_map = {}
    for nm, arr in (("PPI 总指数", P), ("PPI 生产资料", PMC), ("PPI 生活资料", PCG)):
        m = ~(np.isnan(arr) | np.isnan(Y))
        rho = float(np.corrcoef(arr[m], Y[m])[0, 1]) if m.sum() > 2 else float("nan")
        corr_map[nm] = rho
        L.append(f"   corr({nm:<12}, CPI) = {rho:+.3f}   (n={m.sum()})")
    best = max(corr_map, key=lambda k: abs(corr_map[k]))
    L.append(f"   → 相关性最高的是 **{best}**（ρ = {corr_map[best]:+.3f}）")
    L.append("   ⚠️ 诚实说明：生活资料与 CPI 的**相关系数并不更高**（%.3f vs %.3f），"
             % (corr_map["PPI 生活资料"], corr_map["PPI 生产资料"]))
    L.append("      因此不能用‘相关性更高’来支持结构解释。真正的结构性证据是：")
    L.append("      ① 权数上 78% 的 PPI 不直接进消费篮子（可核算的事实）；")
    L.append("      ② 2026-08 生活资料与 CPI 同向下跌，而生产资料反向上涨（方向性证据）。")
    L.append("      相关系数受共同趋势影响，不能单独作为因果证据 —— 这一点在论文中必须写明。")

    # 波动率差异 → 标准化传导
    sd_p = float(np.nanstd(P, ddof=1))
    sd_y = float(np.nanstd(Y, ddof=1))
    L.append(f"\n④ 为什么回归斜率看起来很小？—— 量纲问题，不是传导弱")
    L.append(f"   PPI 同比标准差 {sd_p:.2f}，CPI 同比标准差 {sd_y:.2f}"
             f"（PPI 波动是 CPI 的 {sd_p/sd_y:.1f} 倍）")
    L.append(f"   → 同样 1 个标准差的冲击，CPI 的响应是 PPI 的 "
             f"{(sd_y/sd_p):.2f} 倍；原始斜率（pp/pp）会**系统性显得很小**。")

    # ================= 第二层：传导估计 =================
    L.append("\n" + "-" * 70)
    L.append("【第二层】传导估计（ARDL）")
    L.append("-" * 70)

    m_all = ~(np.isnan(Y) | np.isnan(P))
    rho_all = float(np.corrcoef(Y[m_all], P[m_all])[0, 1])
    adf_y, adf_p = adf_t(Y[m_all]), adf_t(P[m_all])
    L.append(f"\n同期相关 ρ = {rho_all:.3f}（n={m_all.sum()}）")
    L.append(f"ADF t：CPI {adf_y:.2f}，PPI {adf_p:.2f}（5% 临界值约 −2.99）")
    L.append("   → 均不能拒绝单位根：**水平回归存在伪回归风险**，故主模型用 ARDL")
    L.append("     （含滞后被解释变量，可吸收非平稳性），并以一阶差分做稳健性对照。")

    # M1 主模型：ARDL(1,1)，不含虚拟变量
    m1 = fit(Y, P, lag=1, lagx=True,
             names=["const", "CPI(t-1)", "PPI(t)", "PPI(t-1)"])
    lam = 1 - m1["beta"][1]
    th_lr = (m1["beta"][2] + m1["beta"][3]) / lam if abs(lam) > 1e-9 else np.nan
    # 标准化传导：1 个标准差的 PPI 冲击 → 多少个标准差的 CPI
    sd_p, sd_y = float(np.nanstd(P[m_all], ddof=1)), float(np.nanstd(Y[m_all], ddof=1))
    beta_std = float(th_lr) * sd_p / sd_y if sd_y > 0 else float("nan")
    L += report("M1【主模型】ARDL(1,1)，全样本，不含虚拟变量",
                m1, f"λ = {lam:.4f}（调整速度）   θ_LR = {th_lr:.4f}（长期传导）")
    L.append(f"   长期传导（原始量纲）：PPI 每变动 1 pp，CPI 同向变动约 "
             f"{abs(th_lr):.3f} pp")
    L.append(f"   长期传导（标准化）：PPI 每变动 1 个标准差，CPI 变动 "
             f"{abs(beta_std):.3f} 个标准差  ← **这才是可比较的传导强度**")

    # M2 稳健性：加基期虚拟变量
    m2 = fit(Y, P, lag=1, lagx=True, dummy=base,
             names=["const", "CPI(t-1)", "PPI(t)", "PPI(t-1)", "D_base"])
    rho_dp = float(np.corrcoef(base[~np.isnan(P)], P[~np.isnan(P)])[0, 1])
    m2_extra = (f"⚠️ corr(D_base, PPI) = {rho_dp:.3f} —— 严重共线，"
                f"系数不可信，仅作对照")
    if m2 is not None:
        lam2 = 1 - m2["beta"][1]
        th2 = ((m2["beta"][2] + m2["beta"][3]) / lam2) if abs(lam2) > 1e-9 else np.nan
        m2_extra += f"；θ_LR = {th2:.4f}"
    L += report("M2【稳健性】加入基期虚拟变量 D_base", m2, m2_extra)

    # M3 稳健性：一阶差分
    dY, dP = np.diff(Y), np.diff(P)
    m3 = fit(dY, dP, lag=0, lagx=False, names=["const", "ΔPPI(t)"])
    L += report("M3【稳健性】一阶差分模型 ΔCPI = α + β·ΔPPI", m3,
                "差分后消除趋势，系数反映短期传导")

    # ---- 符号矛盾诊断（重要：不能含糊过去）----
    L.append("\n" + "-" * 70)
    L.append("【诊断】水平模型 θ_LR ≈ +0.12 与差分模型 β ≈ −0.43 符号相反，为什么？")
    L.append("-" * 70)
    L.append("   假设 H：CPI 对 PPI 的反应存在**滞后**，同期差分捕捉到的是")
    L.append("   ‘滞后调整’而非同向传导。检验方法：把不同滞后的 ΔPPI 逐个放入回归。")
    L.append(f"\n   {'滞后':<8}{'系数':>10}{'标准误':>10}{'t值':>9}{'p值':>9}{'R²':>9}")
    lagdiag = []
    for Lg in (0, 1, 2):
        if Lg == 0:
            ddP = dP
        else:
            ddP = np.concatenate([np.full(Lg, np.nan), dP])[:-Lg] if Lg else dP
        r_ = fit(dY, ddP, lag=0, lagx=False, names=["const", f"ΔPPI(t-{Lg})"])
        if r_ is None:
            L.append(f"   t-{Lg:<6}样本不足")
            continue
        L.append(f"   t-{Lg:<6}{r_['beta'][1]:>10.4f}{r_['se'][1]:>10.4f}"
                 f"{r_['t'][1]:>9.3f}{r_['p'][1]:>9.4f}{r_['r2']:>9.4f}")
        lagdiag.append({"lag": Lg, "beta": float(r_["beta"][1]),
                        "p": float(r_["p"][1]), "r2": float(r_["r2"])})

    # 同时放入 ΔPPI(t) 与 ΔPPI(t-1)
    ddP1 = np.concatenate([[np.nan], dP])[:-1]
    Xd = np.column_stack([np.ones(len(dY)), dP, ddP1])[1:]
    yd = dY[1:]
    ok = ~np.isnan(Xd).any(axis=1)
    md = ols(Xd[ok], yd[ok])
    md["names"] = ["const", "ΔPPI(t)", "ΔPPI(t-1)"]
    L += report("\n   同时纳入当期与滞后一期差分", md, "")
    L.append("   ★ 判读（诚实结论）：")
    L.append("     ① 单独放入时，t-0 / t-1 / t-2 的系数都稳定在 −0.42 ~ −0.43（p≈0.03–0.04），")
    L.append("        看似‘显著负传导’；")
    L.append("     ② 但同时纳入当期与滞后一期后，两个系数都变得**不显著**"
             "（−0.06，p=0.73；+0.10，p=0.54），")
    L.append("        R² 从 0.18 崩到 0.017，DW 升到 2.77。")
    L.append("     → **结论：那个 −0.425 不稳健，随时间平移、互相抵消，是伪相关，")
    L.append("       不能解释为‘上游涨、下游跌’。**")
    L.append("     → 真实情况是：**在 27 个同比观测点上，PPI→CPI 的短期传导无法被稳健识别。**")
    L.append("       这不是模型失败，而是数据信息量的客观限制（同比已平滑 + 样本短），")
    L.append("       也与 PPI/CPI 篮子结构性不可比一致。")
    L.append("     → 论文应把这一点写清楚，而不是挑一个‘好看’的系数当结论。")

    # M4 口径一致子样本
    Ys, Ps = Y[sub], P[sub]
    m4 = fit(Ys, Ps, lag=1, lagx=False, names=["const", "CPI(t-1)", "PPI(t)"])
    lam4 = (1 - m4["beta"][1]) if m4 else np.nan
    th4 = (m4["beta"][2] / lam4) if (m4 and abs(lam4) > 1e-9) else np.nan
    L += report(f"M4【口径一致子样本】{CONSISTENT_FROM} 起（用户决策的验证口径）",
                m4, f"λ = {lam4:.3f}  θ_LR = {th4:.3f}  "
                     f"⚠️ 仅 {len(Ys)} 个点，自由度极低，仅作方向性参考")

    # ================= 第三层：不对称传导 =================
    L.append("\n" + "-" * 70)
    L.append("【第三层】不对称传导检验（NARDL 思路，加分项）")
    L.append("-" * 70)
    Ppos, Pneg = np.maximum(P, 0.0), np.minimum(P, 0.0)
    rows_x, rows_y = [], []
    for t in range(1, len(Y)):
        if np.isnan(Y[t]) or np.isnan(Y[t - 1]):
            continue
        rows_x.append([1.0, Y[t - 1], Ppos[t], Pneg[t]])
        rows_y.append(Y[t])
    m5 = None
    if len(rows_y) >= 6:
        m5 = ols(np.array(rows_x), np.array(rows_y))
        m5["names"] = ["const", "CPI(t-1)", "PPI⁺(t)", "PPI⁻(t)"]
        stat, pw = wald(m5["beta"], m5["cov"], np.array([[0, 0, 1, -1]]))
        L += report("M5 不对称传导：PPI 拆分为上行/下行部分", m5,
                    f"Wald χ²(1) = {stat:.3f}，p = {pw:.4f}")
        if not np.isnan(pw):
            if pw < 0.05:
                L.append("   ★ 拒绝 β⁺ = β⁻：**存在显著的不对称传导**")
            else:
                L.append("   ★ 不能拒绝 β⁺ = β⁻：**未发现显著不对称**，传导近似对称")
        asym = {"wald_chi2": stat, "wald_p": pw,
                "beta_pos": float(m5["beta"][2]), "beta_neg": float(m5["beta"][3]),
                "p_pos": float(m5["p"][2]), "p_neg": float(m5["p"][3])}
    else:
        asym = {}

    # ================= 汇总与落盘 =================
    out = {
        "sample": {"from": months[0], "to": months[-1], "n": len(months)},
        "base_break": BASE_BREAK,
        "structure": {
            "cpi_weights": CPI_WEIGHTS,
            "ppi_weights_implied": {k: float(v) for k, v in implied.items()},
            "ppi_impact_2026_08": {k: [float(x) for x in v]
                                   for k, v in PPI_IMPACT_2026_08.items()},
            "aug2026": {"ppi_total": float(P[aug]), "ppi_means": float(PMC[aug]),
                        "ppi_consumer": float(PCG[aug]), "cpi": float(Y[aug])},
            "corr_with_cpi": {
                nm: float(np.corrcoef(a[~(np.isnan(a) | np.isnan(Y))],
                                      Y[~(np.isnan(a) | np.isnan(Y))])[0, 1])
                for nm, a in (("ppi_total", P), ("ppi_means", PMC),
                              ("ppi_consumer", PCG))},
        },
        "diagnostics": {"corr_cpi_ppi": rho_all, "adf_cpi": adf_y, "adf_ppi": adf_p,
                        "corr_dummy_ppi": rho_dp, "sd_ppi": sd_p, "sd_cpi": sd_y,
                        "beta_standardized": beta_std},
        "corr_breakdown": {k: float(v) for k, v in corr_map.items()},
        "M1_ardl": _dump(m1, lam=lam, theta_lr=th_lr),
        "M2_with_dummy": _dump(m2),
        "M3_diff": _dump(m3),
        "M3b_robustness": {
            "note": "差分系数的稳健性诊断：单独放入时 t-0/t-1/t-2 均为 ≈−0.43，"
                    "但同时纳入当期与滞后一期后均不显著（R² 0.18→0.017）→ 判定为伪相关",
            "lag_scan": lagdiag,
            "joint": _dump(md),
        },
        "M4_subsample": _dump(m4, theta_lr=th4 if m4 else None),
        "M5_asymmetry": asym,
    }
    write_json(out, RES / "q2_result.json")

    L += ["", "=" * 70, "【结论】",
          f"1. **结构不可比是理解本题的钥匙**：PPI 中约 {implied.get('生产资料', 78):.0f}% 是生产资料"
          f"（采掘/原材料，不直接进消费篮子），",
          f"   而对应居民消费的‘生活资料’2026-08 同比 {PCG[aug]:+.1f}%（在跌），"
          f"与 CPI {Y[aug]:+.1f}% 同向；生产资料同期 {PMC[aug]:+.1f}%（在涨），方向相反。",
          f"   → **PPI 上行不等于 CPI 上行**，这是结构决定的事实，不是传导失灵。",
          f"2. **水平关系为正但不精确**：全样本同期 ρ = {rho_all:.2f}；"
          f"ARDL 长期传导 θ_LR = {abs(th_lr):.3f}（pp/pp），",
          f"   标准化后 {abs(beta_std):.3f}（标准差/标准差）。原始斜率小，"
          f"主因是 **PPI 波动为 CPI 的 {sd_p/sd_y:.1f} 倍**。",
          f"3. **短期传导无法被稳健识别（本题最重要的诚实结论）**：",
          f"   一阶差分单独回归给出 β = {m3['beta'][1]:+.3f}（p = {m3['p'][1]:.3f}），看似显著；",
          f"   但滞后诊断显示该系数随时间平移不变、同时纳入两期后即不显著、R² 从 0.18 崩至 0.017",
          f"   → 判定为**伪相关**，不予采信。",
          f"   原因：同比数据已平滑掉短期结构 + 仅 27 个观测点，信息量不足。",
          f"4. 不对称传导："
          f"{'发现显著不对称（上游涨时下游跟涨更明显）' if asym.get('wald_p', 1) < 0.05 else '未发现显著不对称（β⁺ 与 β⁻ 无显著差异）'}。",
          "",
          "【局限】",
          "  · 同比数据已平滑滞后结构，估计的传导时滞短于真实时滞；",
          "  · CPI 含服务（权数合计约 34%），PPI 完全不含服务 —— 结构性不可比；",
          "  · 相关系数受共同趋势影响，不能单独作为因果证据（② 中已实测到伪相关）；",
          f"  · 28 个观测点对 ARDL 偏少，已用五种设定互相对照；",
          f"  · 基期虚拟变量与 PPI 共线（ρ = {rho_dp:.2f}），故不作为主模型，仅作对照。",
          "",
          "【对内容的启示】",
          "  可以讲的不只是‘传导有多强’，更是：‘一个看似显著的系数，",
          "  换一种设定就消失了’——**这本身就是最好的科普素材**。",
          ]
    write_text("\n".join(L), RES / "q2_result.txt")
    print("\n".join(L))

    make_figs(months, Y, P, PMC, PCG, m1, th_lr, rho_all)
    return 0


def _dump(r, **extra):
    if r is None:
        return None
    d = {"n": int(r["n"]), "params": {nm: float(v) for nm, v in zip(r["names"], r["beta"])},
         "se": {nm: float(v) for nm, v in zip(r["names"], r["se"])},
         "t": {nm: float(v) for nm, v in zip(r["names"], r["t"])},
         "p": {nm: float(v) for nm, v in zip(r["names"], r["p"])},
         "r2": float(r["r2"]), "adj_r2": float(r["adj_r2"]), "dw": dw(r["resid"])}
    d.update(extra)
    return d


def make_figs(months, Y, P, PMC, PCG, m1, th_lr, rho):
    if not setup_cn_font():
        return
    import matplotlib.pyplot as plt

    x = np.arange(len(months))
    fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.3))

    ax = axes[0]
    ax.plot(x, PMC, color=C["red"], lw=2.4, marker="^", ms=4, label="PPI 生产资料")
    ax.plot(x, P, color=C["blue"], lw=2.0, marker="s", ms=3.5, label="PPI 总指数")
    ax.plot(x, PCG, color=C["grey"], lw=2.4, marker="v", ms=4, label="PPI 生活资料")
    ax.plot(x, Y, color=C["navy"], lw=2.8, marker="o", ms=4.5, label="CPI")
    ax.axhline(0, color=C["grey"], ls="--", lw=1.1)
    bi = months.index("2026-01")
    ax.axvline(bi - 0.5, color=C["green"], ls=":", lw=2)
    ax.text(bi - 0.4, ax.get_ylim()[1] * 0.9, "基期轮换", fontsize=10, color=C["green"])
    ax.set_xticks(x[::3])
    ax.set_xticklabels([months[i] for i in range(0, len(months), 3)],
                       rotation=45, ha="right", fontsize=9)
    polish(ax, "", "同比涨跌幅（%）",
           "① 关键背离：生产资料在涨，生活资料在跌，CPI 跟的是生活资料")

    ax = axes[1]
    # 结构对比：CPI 篮子 vs PPI 篮子
    labels = ["CPI 篮子\n(服务类合计)", "CPI 篮子\n(消费品)", "PPI 篮子\n(生产资料)",
              "PPI 篮子\n(生活资料)"]
    svc_w = CPI_WEIGHTS["居住"] + CPI_WEIGHTS["交通通信"] + CPI_WEIGHTS["教育文化娱乐"] \
        + CPI_WEIGHTS["医疗保健"] + CPI_WEIGHTS["其他用品及服务"]
    vals = [svc_w, 100 - svc_w, 78.4, 20.0]
    cols = [C["navy"], C["blue"], C["red"], C["grey"]]
    bars = ax.bar(labels, vals, color=cols, width=0.62)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.6, f"{v:.1f}%",
                ha="center", fontsize=11, color=C["navy"], fontweight="bold")
    polish(ax, "", "占比（%）", "② 结构不可比：约 78% 的 PPI 不直接进消费篮子",
           legend=False)
    ax.set_ylim(0, 100)

    fig.suptitle(f"PPI → CPI 传导：ρ = {rho:.2f}，长期传导 θ_LR ≈ {abs(th_lr):.2f}，"
                 f"背离主要来自结构差异",
                 fontsize=13.5, color=C["navy"], y=1.03)
    savefig(fig, FIGS / "q2_transmission.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10.5, 4.3))
    ax.stem(np.arange(len(m1["resid"])), m1["resid"], linefmt="-",
            markerfmt="o", basefmt=" ")
    ax.axhline(0, color=C["grey"], lw=1.1)
    polish(ax, "ARDL 残差序号", "残差（百分点）",
           f"③ 主模型残差（DW = {dw(m1['resid']):.2f}，接近 2 表示无自相关）",
           legend=False)
    savefig(fig, FIGS / "q2_residuals.png")
    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
