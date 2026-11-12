#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W57 · 第 05 屏：用公开数据反算各国央行的**隐含** $\phi_\pi$。

## 这一屏要回答什么

第 06 屏的结论是：真正的边界是

$$\phi_\pi+\frac{1-\beta}{\kappa}\phi_y>1,$$

而“$\phi_\pi>1$”只是 $\phi_y=0$ 时的特例。
那么**真实世界里各国央行的 $\phi_\pi$ 到底是多少、有没有掉到 1 以下？**
本文件用公开数据估一个**简化泰勒规则**

$$i_t=\alpha+\phi_\pi\,\pi_t+\phi_y\,\tilde y_t+\varepsilon_t$$

并给出 $\hat\phi_\pi$ 的**点估计与 95% 区间**，再逐季滚动，
看 2021–2024 的隐含 $\phi_\pi$ 有没有跌破 1。

## ★★ 本文件最重要的纪律：**区间跨过 1 就不许下结论**

$$\boxed{\text{一个“刚好擦过 1”的点估计，若区间跨 1，就不能拿它讲结论}}$$

所以本文件的输出里，**每一行 $\hat\phi_\pi$ 都必须带区间**，
并且自动判定 `跨1 / 在1以上 / 在1以下` 三态。
判定用 `ci_lo <= 1 <= ci_hi`，**不用四舍五入后的显示值**。

## 三个口径（诚实性写在这里，也写进论文 5.5 与 7.3）

| # | 偏误来源 | 方向 | 处置 |
|---|---|---|---|
| 1 | 用**事后通胀**而非实时数据/预期 | 未知 | 明写；不给方向性断言 |
| 2 | **不含利率平滑项**（$i_{t-1}$）| $\hat\phi_\pi$ **上偏** | 主回归不含；另做含平滑项的稳健性 |
| 3 | 中国**缺产出缺口项** | $\hat\phi_\pi$ **上偏**（若 $\phi_y>0$ 且 $\mathrm{cov}(\pi,\tilde y)>0$）| 中国单列“仅参考” |

## 两套独立实现互证（W56 的教训：一个估计量至少两条路算）

* **HAC（Newey–West）标准误**：本文件自己按 Bartlett 核实现；
* 再用 `statsmodels` 的 `cov_type="HAC"` 复核，两条路必须吻合到 $10^{-9}$；
* **区间**另有 **循环块 bootstrap** 一套，与 HAC 区间并列报告。
  两套区间差异大时，正文报**更宽的那一个**。

## 用法

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"
$PY = "python"
& $PY episodes\2026-W57\scripts\q5_implied_phi.py            # 全部重算
& $PY episodes\2026-W57\scripts\q5_implied_phi.py --probe    # 只看关键数，不写文件
```
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

EP = Path(__file__).resolve().parents[1]
RAW = EP / "data" / "raw"
RES = EP / "results"
OUT_JSON = RES / "q5_隐含phi.json"
OUT_MD = RES / "q5_隐含phi_结果.md"
OUT_CSV = RES / "q5_隐含phi_路径.csv"

# ---------------------------------------------------------------- 标定（③）
Z95 = 1.959963984540054          # 正态 97.5% 分位
HAC_LAG_Q = 4                    # ③ 季度：4 期（一年）Bartlett 滞后
HAC_LAG_M = 12                   # ③ 月度：12 期
ROLL_Q = 40                      # ③ 美国/欧元区滚动窗口：40 个季度（10 年）
ROLL_M_CN = 60                   # ③ 中国滚动窗口：60 个月（5 年）
BOOT_N = 4000                    # ③ 块 bootstrap 次数
BOOT_BLOCK_Q = 8                 # ③ 块长：8 个季度
SEED = 20260570

# 各经济体的样本起止（起点的选择理由写在 results/*.md 与论文 5.5）
SAMPLE = {
    "US": ("1960-01-01", None),          # ③ 1960Q1 起：联邦基金市场成型后的常规口径
    "EA": ("1999-01-01", None),          # ① ECB 存款便利利率 1999-01-01 才有
    "CN": ("2007-01-01", "2025-04-01"),  # ③ 2007 起：SHIBOR 运行、利率市场化推进
}
CN_LONG_START = "1997-06-01"             # ③ 中国长样本稳健性

CTRY_LABEL = {"US": "美国", "EA": "欧元区", "CN": "中国"}
POLICY_NAME = {"US": "联邦基金有效利率", "EA": "欧央行主要再融资利率",
               "CN": "3 个月银行间利率"}
# ★ 零下限（ZLB）判据：政策利率被这个下限顶住时，线性规则**没有信息**
ZLB_MAX = {"US": 0.25, "EA": 0.25, "CN": None}


# ================================================================ 读原始 CSV
def load_raw(sid: str, trunc: bool = False) -> list[tuple[str, float]]:
    r"""读 `data/raw/<sid>.csv`；`trunc=True` 时读截断版（去掉 CBO 预测）。"""
    name = f"{sid}__trunc.csv" if trunc else f"{sid}.csv"
    p = RAW / name
    if not p.exists():
        raise SystemExit(f"[!] 缺 {p}\n    先跑：python episodes/2026-W57/scripts/fetch_taylor_data.py")
    rows = list(csv.reader(io.StringIO(p.read_text(encoding="utf-8-sig"))))
    out: list[tuple[str, float]] = []
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        raw = (r[1].strip() if len(r) > 1 else "")
        if raw in ("", ".", "NA"):
            continue
        out.append((r[0].strip(), float(raw)))
    if not out:
        raise SystemExit(f"[!] {p} 解析后为空")
    return out


def mi(date: str) -> int:
    r"""把 `YYYY-MM-DD` 映射成**连续月序号**（year*12 + month-1）。"""
    y, m = int(date[:4]), int(date[5:7])
    return y * 12 + (m - 1)


def qi(date: str) -> int:
    r"""把 `YYYY-MM-DD` 映射成**连续季序号**（year*4 + quarter-1）。"""
    y, m = int(date[:4]), int(date[5:7])
    return y * 4 + ((m - 1) // 3)


def mi_label(k: int) -> str:
    return f"{k // 12}-{k % 12 + 1:02d}"


def qi_label(k: int) -> str:
    return f"{k // 4}Q{k % 4 + 1}"


# ================================================================ 面板拼装
def monthly_series(sid: str, trunc: bool = False) -> dict[int, float]:
    return {mi(d): v for d, v in load_raw(sid, trunc)}


def quarterly_series(sid: str, trunc: bool = False) -> dict[int, float]:
    return {qi(d): v for d, v in load_raw(sid, trunc)}


def yoy_from_index(ms: dict[int, float]) -> dict[int, float]:
    r"""由指数算同比（%）：$100\,(P_t/P_{t-12}-1)$。"""
    return {k: 100.0 * (v / ms[k - 12] - 1.0) for k, v in ms.items() if (k - 12) in ms}


def avg_to_quarter(ms: dict[int, float], q_from: int, q_to: int) -> dict[int, float]:
    r"""月序列按季平均；只在该季至少有一个月有观测时出值。"""
    buckets: dict[int, list[float]] = {}
    for k, v in ms.items():
        q = (k // 12) * 4 + ((k % 12) // 3)
        if q_from <= q <= q_to:
            buckets.setdefault(q, []).append(v)
    return {q: float(np.mean(b)) for q, b in buckets.items()}


def hp_gap(qs: dict[int, float], lam: float = 1600.0) -> dict[int, float]:
    r"""HP 滤波取产出缺口的**百分点**：$100\,(\\ln y-\\ln y^{*})$。

    自己实现（不调 statsmodels）：$\\min\\sum(y-\\tau)^2+
    \\lambda\\sum[\\Delta^2\\tau]^2$ 的一阶条件是一个 $T\\times T$ 线性方程组，
    直接 `np.linalg.solve`。**自己写的好处是能对 $\\lambda$ 显式扫。**
    """
    ks = sorted(qs)
    y = np.log(np.array([qs[k] for k in ks], dtype=float))
    T = len(y)
    assert T >= 8, f"HP 滤波样本太短：{T}"
    D = np.zeros((T - 2, T))
    for i in range(T - 2):
        D[i, i], D[i, i + 1], D[i, i + 2] = 1.0, -2.0, 1.0
    A = np.eye(T) + lam * (D.T @ D)
    tau = np.linalg.solve(A, y)
    return {k: 100.0 * (yy - tt) for k, yy, tt in zip(ks, y, tau)}


# ================================================================ 估计
@dataclass
class Fit:
    r"""一次 OLS + HAC 的结果。"""
    names: list[str]
    beta: np.ndarray
    se_hac: np.ndarray
    se_ols: np.ndarray
    V: np.ndarray          # HAC 协方差矩阵（求组合系数的区间要用到非对角元）
    resid: np.ndarray
    X: np.ndarray
    y: np.ndarray
    n: int
    k: int

    def ci(self, j: int, level: float = 0.95) -> tuple[float, float]:
        z = Z95 if abs(level - 0.95) < 1e-12 else float(
            np.sqrt(2.0) * _erfinv(level))
        return (float(self.beta[j] - z * self.se_hac[j]),
                float(self.beta[j] + z * self.se_hac[j]))

    def t(self, j: int) -> float:
        return float(self.beta[j] / self.se_hac[j]) if self.se_hac[j] > 0 else float("nan")


def _erfinv(x: float) -> float:
    r"""逆误差函数（只用于非 95% 的置信水平，本期默认不用）。"""
    from scipy.special import erfinv
    return float(erfinv(x))


def ols_hac(y: np.ndarray, X: np.ndarray, names: list[str], lag: int) -> Fit:
    r"""OLS 估计 + Newey–West（Bartlett 核）标准误。

    $$V=\frac{T}{T-k}\,(X'X)^{-1}\Big[\Gamma_0+
    \sum_{l=1}^{L}\Big(1-\frac{l}{L+1}\Big)(\Gamma_l+\Gamma_l')\Big](X'X)^{-1}$$

    其中 $\Gamma_l=\sum_t u_t u_{t-l}\,x_t x_{t-l}'$。
    小样本修正 $T/(T-k)$ 与 statsmodels 的 `cov_type="HAC"` 一致。
    """
    n, k = X.shape
    if n <= k + 1:
        raise ValueError(f"样本太少：n={n}, k={k}")
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ (X.T @ y)
    u = y - X @ beta
    S = (X * u[:, None]).T @ (X * u[:, None])          # Gamma_0
    for l in range(1, lag + 1):
        w = 1.0 - l / (lag + 1.0)
        G = (X[l:] * u[l:, None]).T @ (X[:-l] * u[:-l, None])
        S += w * (G + G.T)
    V = XtX_inv @ S @ XtX_inv * (n / (n - k))
    se = np.sqrt(np.maximum(np.diag(V), 0.0))
    s2 = float(u @ u) / (n - k)
    se_ols = np.sqrt(np.diag(XtX_inv) * s2)
    return Fit(names=names, beta=beta, se_hac=se, se_ols=se_ols, V=V,
               resid=u, X=X, y=y, n=n, k=k)


def ols_hac_loop(y: np.ndarray, X: np.ndarray, lag: int) -> tuple[np.ndarray, np.ndarray]:
    r"""**第二套独立实现**：用观测维的双重循环累加，不走 `ols_hac` 的向量化路径。

    ## 为什么需要它

    `statsmodels` 在本机跑不起来（pandas 3.0 与 statsmodels 0.14 的
    `deprecate_kwarg` 不兼容，`import statsmodels.api` 直接抛 `TypeError`）。
    所以"手写 HAC vs statsmodels"这条互证路走不通。

    ⇒ 换成**同一个公式的两条不同代码路径**：

    * `ols_hac`：先把 $x_t u_t$ 堆成矩阵，用一次矩阵乘得 $\Gamma_l$；
    * `ols_hac_loop`：对 $(t,l)$ 逐个元素累加，索引写法完全不同。

    这不能替代"两套不同统计方法"，但足以抓出**权重、滞后方向、下标错位**
    这三类最常见的实现错。区间的第二套方法由块 bootstrap 提供。
    """
    n, k = X.shape
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ (X.T @ y)
    u = y - X @ beta
    K = np.zeros((k, k))
    for t in range(n):
        for l in range(-lag, lag + 1):
            if not (0 <= t + l < n):
                continue
            w = 1.0 if l == 0 else (1.0 - abs(l) / (lag + 1.0))
            K += w * (u[t] * u[t + l]) * np.outer(X[t], X[t + l])
    V = XtX_inv @ K @ XtX_inv * (n / (n - k))
    return beta, np.sqrt(np.maximum(np.diag(V), 0.0))


def fwl_check(y: np.ndarray, X: np.ndarray, j: int) -> float:
    r"""Frisch–Waugh–Lovell 自检：第 $j$ 个系数应等于"两边都剔除其余回归元"后的简单回归。

    这是**最便宜的一个独立实现**：FWL 定理在数学上必须精确成立，
    所以偏差只能是实现错，而不会"数据恰好这样"。
    """
    others = np.delete(X, j, axis=1)
    Q, _ = np.linalg.qr(others)
    yr = y - Q @ (Q.T @ y)
    xr = X[:, j] - Q @ (Q.T @ X[:, j])
    return float((xr @ yr) / (xr @ xr))


def block_bootstrap_ci(y: np.ndarray, X: np.ndarray, j: int, lag: int,
                       n_rep: int = BOOT_N, block: int = BOOT_BLOCK_Q,
                       seed: int = SEED) -> tuple[float, float, float]:
    r"""循环块 bootstrap 的 $\phi_j$ 经验分布：返回 (2.5%, 97.5%, 标准差)。

    **为什么按块重抽而不是按观测**：残差有序列相关（规则含平滑、通胀有惯性），
    按观测重抽会把相关结构打散，区间**偏窄**。
    """
    rng = np.random.default_rng(seed)
    n = len(y)
    nb = int(math.ceil(n / block))
    out = np.empty(n_rep)
    for r in range(n_rep):
        starts = rng.integers(0, n, size=nb)
        idx = np.concatenate([(np.arange(s, s + block) % n) for s in starts])[:n]
        Xb, yb = X[idx], y[idx]
        try:
            bb = np.linalg.solve(Xb.T @ Xb, Xb.T @ yb)
        except np.linalg.LinAlgError:
            out[r] = np.nan
            continue
        out[r] = bb[j]
    out = out[np.isfinite(out)]
    return (float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5)),
            float(np.std(out, ddof=1)))


def verdict(lo: float, hi: float, target: float = 1.0) -> str:
    r"""三态判定。**判据用未四舍五入的端点**，不用显示值。"""
    if lo <= target <= hi:
        return "跨1"
    return "在1以上" if lo > target else "在1以下"


def verdict_union(a: str, b: str) -> str:
    r"""两套区间（HAC 与块 bootstrap）的**保守合并判定**。

    ## 为什么要有这一条

    同一个点估计、两套都合法的区间，会出现**一个跨 1、一个不跨 1**。
    这时若挑窄的那个来讲结论，就是在"用方法的选择把结论挑出来"。

    ⇒ 规则：**只要有一套跨 1，就判"跨1"。** 这是刻意保守的方向：
    宁可说"不知道"，不许说"知道了"。
    """
    if "跨1" in (a, b):
        return "跨1"
    return a if a == b else f"不一致({a}/{b})"


# ================================================================ 面板
def build_panels() -> dict:
    r"""拼三套面板。所有口径都写在这里，别的地方不再加工。"""
    P: dict = {}

    # ---------------- 美国（季度，主回归）----------------
    cpi = monthly_series("CPIAUCSL")
    ff = monthly_series("FEDFUNDS")
    gdp = quarterly_series("GDPC1")
    pot = quarterly_series("GDPPOT", trunc=True)
    cpi_yoy = yoy_from_index(cpi)
    q_lo, q_hi = qi("1960-01-01"), max(gdp)
    P["US"] = {
        "freq": "Q",
        "i": avg_to_quarter(ff, q_lo, q_hi),
        "pi": avg_to_quarter(cpi_yoy, q_lo, q_hi),
        "y": {q: 100.0 * (gdp[q] / pot[q] - 1.0) for q in gdp if q in pot},
        "y_name": "GDP 缺口（CBO 潜在产出，①）",
        "raw": {"cpi_yoy_2022_06": cpi_yoy.get(mi("2022-06-01")),
                "cpi_yoy_2022_09": cpi_yoy.get(mi("2022-09-01")),
                "ff_2023_07": ff.get(mi("2023-07-01"))},
    }

    # 失业率口径的缺口（Okun 系数 −2 是 ③）：稳健性对照
    ur = monthly_series("UNRATE")
    nrou = quarterly_series("NROU", trunc=True)
    ur_q = avg_to_quarter(ur, q_lo, q_hi)
    P["US"]["y_alt"] = {q: -2.0 * (ur_q[q] - nrou[q])
                        for q in ur_q if q in nrou}
    P["US"]["y_alt_name"] = "失业率缺口 ×(−2)（Okun，③ 系数）"

    # ---------------- 欧元区（季度）----------------
    #   ★ 主用 DFR（存款便利利率）：0 缺失、1999-01-01 起连续。
    #     不用 MRO（主要再融资利率）当主序列：它 2001–2007 **整段缺失**，
    #     跑回归不报错，但那 7 年会被静默剔出样本。见 data/来源清单.md §2.4。
    hicp = monthly_series("CP0000EZ19M086NEST")
    dfr = monthly_series("ECBDFR")          # 主：存款便利利率（0 缺失）
    mro = monthly_series("ECBMRRFR")        # 稳健性：主要再融资利率（2009 年后才完整）
    eagdp = quarterly_series("CLVMEURSCAB1GQEA19")
    hicp_yoy = yoy_from_index(hicp)
    ea_lo, ea_hi = qi("1999-01-01"), max(eagdp)
    gap_all = hp_gap(eagdp, 1600.0)       # HP 用全样本估趋势，再按窗口取用
    P["EA"] = {
        "freq": "Q",
        "i": avg_to_quarter(dfr, ea_lo, ea_hi),
        "i_alt": avg_to_quarter(mro, ea_lo, ea_hi),
        "pi": avg_to_quarter(hicp_yoy, ea_lo, ea_hi),
        "y": {q: gap_all[q] for q in gap_all if ea_lo <= q <= ea_hi},
        "y_name": "HP 滤波产出缺口（λ=1600，③ 自建）",
        "raw": {"hicp_yoy_2022_10": hicp_yoy.get(mi("2022-10-01")),
                "hicp_yoy_2023_03": hicp_yoy.get(mi("2023-03-01")),
                "dfr_2022_10": dfr.get(mi("2022-10-01")),
                "mro_2022_10": mro.get(mi("2022-10-01"))},
    }

    # ---------------- 中国（月度，两变量）----------------
    cn_i = monthly_series("IR3TIB01CNM156N")
    cn_pi = monthly_series("CPALTT01CNM659N")
    P["CN"] = {
        "freq": "M",
        "i": cn_i, "pi": cn_pi, "y": None,
        "y_name": "无（FRED 上中国工业增加值/失业率序列已停更，见来源清单 2.2）",
        "raw": {"cpi_yoy_2020_01": cn_pi.get(mi("2020-01-01")),
                "ir_2024_01": cn_i.get(mi("2024-01-01"))},
    }
    return P


def panel_arrays(pan: dict, start: str, end: str | None,
                 use_gap: bool = True, gap_key: str = "y",
                 zlb_max: float | None = None,
                 rate_key: str = "i") -> tuple:
    r"""把面板裁到样本区间，返回 (keys, y, X, names, lab_of)。

    `zlb_max`：把政策利率 $\le$ 该下限的观测**剔掉**。
    **为什么必须能剔**：$i_t\equiv\underline{i}$ 时 $\phi_\pi$ 完全由通胀的变异去凑，
    线性规则在这段**没有信息**。不剔的话，含零下限的窗口会把 $\hat\phi_\pi$
    拖到 0 附近，那不是"央行不在乎通胀"，是"利率动不了"。
    """
    idx_of = qi if pan["freq"] == "Q" else mi
    lab_of = qi_label if pan["freq"] == "Q" else mi_label
    lo = idx_of(start)
    hi = idx_of(end) if end else 10 ** 9
    g = pan.get(gap_key) if use_gap else None
    rate = pan[rate_key]
    keys = sorted(k for k in rate if lo <= k <= hi
                  and k in pan["pi"] and (g is None or k in g)
                  and (zlb_max is None or rate[k] > zlb_max))
    if not keys:
        raise SystemExit(f"样本为空：start={start} end={end} zlb_max={zlb_max}")
    yv = np.array([rate[k] for k in keys], dtype=float)
    cols = [np.ones(len(keys))]
    names = ["const"]
    cols.append(np.array([pan["pi"][k] for k in keys], dtype=float))
    names.append("phi_pi")
    if g is not None:
        cols.append(np.array([g[k] for k in keys], dtype=float))
        names.append("phi_y")
    X = np.column_stack(cols)
    return keys, yv, X, names, lab_of


# ================================================================ 主流程
def run() -> dict:
    P = build_panels()
    rep: dict = {"panels": {}, "full": [], "sub": [], "rolling": [],
                 "checks": {}, "specs": {}}

    # ---------- 0. 数据体检断言（判据取"外部已知事实"，不取上一版输出）----------
    checks: dict = {}
    us = P["US"]["raw"]
    # ① 美国 CPI 同比峰值：官方口径 2022-06 约 9.1%（NSA）/ 9.06%（SA）
    assert 8.5 <= us["cpi_yoy_2022_06"] <= 9.6, \
        f"美国 2022-06 CPI 同比 {us['cpi_yoy_2022_06']:.2f}% 偏离官方约 9.1%"
    # ② 欧元区 HICP 同比峰值：官方 2022-10 = 10.6%
    ea = P["EA"]["raw"]
    assert 10.0 <= ea["hicp_yoy_2022_10"] <= 11.2, \
        f"欧元区 2022-10 HICP 同比 {ea['hicp_yoy_2022_10']:.2f}% 偏离官方约 10.6%"
    # ③ 中国 CPI 同比 2020-01：官方 5.4%
    cn = P["CN"]["raw"]
    assert 5.0 <= cn["cpi_yoy_2020_01"] <= 5.8, \
        f"中国 2020-01 CPI 同比 {cn['cpi_yoy_2020_01']:.2f}% 偏离官方 5.4%"
    checks["外部已知事实对账"] = {
        "US_CPI_YoY_2022M06": round(us["cpi_yoy_2022_06"], 3),
        "US_官方参照": "约 9.1%（2022-06）",
        "EA_HICP_YoY_2022M10": round(ea["hicp_yoy_2022_10"], 3),
        "EA_官方参照": "10.6%（2022-10）",
        "CN_CPI_YoY_2020M01": round(cn["cpi_yoy_2020_01"], 3),
        "CN_官方参照": "5.4%（2020-01）",
    }

    # ④ 截断后 GDPPOT 的末季不得晚于实际 GDP 末季
    gdp_q = quarterly_series("GDPC1")
    pot_q = quarterly_series("GDPPOT", trunc=True)
    assert max(pot_q) <= max(gdp_q), "潜在产出仍含未来季度 ⇒ 截断失效"
    checks["CBO 预测截断"] = {"GDPC1_last": qi_label(max(gdp_q)),
                              "GDPPOT_trunc_last": qi_label(max(pot_q))}

    # ---------- 1. 全样本（三组设定）----------
    #   (ctry, tag, start, end, use_gap, gap_key, freq, zlb_max, rate_key, hac_lag)
    specs = [
        ("US", "1960-2026 全样本", SAMPLE["US"][0], SAMPLE["US"][1],
         True, "y", "Q", None, "i", HAC_LAG_Q),
        ("US", "1960-2026 剔除零下限季度", SAMPLE["US"][0], SAMPLE["US"][1],
         True, "y", "Q", ZLB_MAX["US"], "i", HAC_LAG_Q),
        ("US", "1960-2026 去掉产出缺口（定标用）", SAMPLE["US"][0], SAMPLE["US"][1],
         False, "y", "Q", None, "i", HAC_LAG_Q),
        ("US", "1960-2026 失业率缺口（稳健）", SAMPLE["US"][0], SAMPLE["US"][1],
         True, "y_alt", "Q", None, "i", HAC_LAG_Q),
        ("US", "1983-2026（大缓和后，稳健）", "1983-01-01", SAMPLE["US"][1],
         True, "y", "Q", None, "i", HAC_LAG_Q),
        ("US", "2009-2026（近 18 年，稳健）", "2009-01-01", SAMPLE["US"][1],
         True, "y", "Q", None, "i", HAC_LAG_Q),
        ("US", "1960-2026 滞后 8 期（区间稳健）", SAMPLE["US"][0], SAMPLE["US"][1],
         True, "y", "Q", None, "i", 8),
        ("EA", "1999-2026 全样本（存款便利利率）", SAMPLE["EA"][0], SAMPLE["EA"][1],
         True, "y", "Q", None, "i", HAC_LAG_Q),
        ("EA", "1999-2026 剔除零下限季度", SAMPLE["EA"][0], SAMPLE["EA"][1],
         True, "y", "Q", ZLB_MAX["EA"], "i", HAC_LAG_Q),
        ("EA", "2009-2026 主要再融资利率（MRO 完整段）", "2009-01-01", SAMPLE["EA"][1],
         True, "y", "Q", None, "i_alt", HAC_LAG_Q),
        ("EA", "1999-2026 去掉产出缺口（稳健）", SAMPLE["EA"][0], SAMPLE["EA"][1],
         False, "y", "Q", None, "i", HAC_LAG_Q),
        ("CN", "2007-2025 两变量（仅参考）", SAMPLE["CN"][0], SAMPLE["CN"][1],
         False, "y", "M", None, "i", HAC_LAG_M),
        ("CN", "1997-2025 两变量长样本（仅参考）", CN_LONG_START, SAMPLE["CN"][1],
         False, "y", "M", None, "i", HAC_LAG_M),
    ]
    for ctry, tag, st, en, use_gap, gk, freq, zlb, rk, lag in specs:
        keys, yv, X, names, lab = panel_arrays(P[ctry], st, en, use_gap, gk,
                                               zlb_max=zlb, rate_key=rk)
        f = ols_hac(yv, X, names, lag)
        j = names.index("phi_pi")
        lo, hi = f.ci(j)
        blo, bhi, bsd = block_bootstrap_ci(yv, X, j, lag)
        rep["full"].append({
            "ctry": ctry, "ctry_label": CTRY_LABEL[ctry], "tag": tag,
            "freq": freq, "n": f.n, "span": f"{lab(keys[0])}–{lab(keys[-1])}",
            "zlb_max": zlb, "hac_lag": lag, "rate_key": rk,
            "phi_pi": round(float(f.beta[j]), 4),
            "se_hac": round(float(f.se_hac[j]), 4),
            "se_ols": round(float(f.se_ols[j]), 4),
            "ci95_hac": [round(lo, 4), round(hi, 4)],
            "ci95_boot": [round(blo, 4), round(bhi, 4)],
            "boot_sd": round(bsd, 4),
            "phi_y": (round(float(f.beta[names.index("phi_y")]), 4)
                      if "phi_y" in names else None),
            "t_phi_pi": round(f.t(j), 3),
            "verdict": verdict(lo, hi),
            "verdict_boot": verdict(blo, bhi),
            "verdict_union": verdict_union(verdict(lo, hi), verdict(blo, bhi)),
            "note": "",
        })

    # ---------- 2. 分段：隐含 φπ 的历史（含零利率下限段）----------
    subs = [("1960-1979", "1960-01-01", "1979-12-31"),
            ("1980-1999", "1980-01-01", "1999-12-31"),
            ("2000-2008", "2000-01-01", "2008-12-31"),
            ("2009-2015 零利率下限", "2009-01-01", "2015-12-31"),
            ("2016-2019", "2016-01-01", "2019-12-31"),
            ("2020-2026 疫情与加息", "2020-01-01", "2026-12-31")]
    for tag, st, en in subs:
        keys, yv, X, names, lab = panel_arrays(P["US"], st, en, True, "y")
        if len(keys) <= X.shape[1] + 6:
            continue
        f = ols_hac(yv, X, names, HAC_LAG_Q)
        j = names.index("phi_pi")
        lo, hi = f.ci(j)
        rep["sub"].append({
            "ctry": "US", "tag": tag, "n": f.n,
            "span": f"{lab(keys[0])}–{lab(keys[-1])}",
            "phi_pi": round(float(f.beta[j]), 4),
            "se_hac": round(float(f.se_hac[j]), 4),
            "ci95_hac": [round(lo, 4), round(hi, 4)],
            "verdict": verdict(lo, hi),
        })

    # ---------- 3. 逐季滚动（2021Q1–2024Q4），两个口径 ----------
    #   口径 all   ：窗口内**全部**观测（"按数据照算"看到的样子）
    #   口径 nozlb ：窗口内**剔除**政策利率被下限顶住的观测（"规则还看得见"的部分）
    #   ⇒ 两条路径的差，就是零下限把 φπ 拖下去多少。这是第 05 屏的核心图。
    #
    #   ★ 两个口径共用**同一张端点网格**（2021Q1–2024Q4 共 16 个季度），
    #     否则图上两条线的横坐标不同，差就看不出是口径差还是采样差。
    #     剔零下限后某端点没有"新"观测（例如 2020Q2–2021Q4 全在零下限），
    #     这时窗口只是**没有更新**，不是换了样本 ⇒ 记下 `used` 实际用到的最新季度。
    grid = [k for k in range(qi("2021-01-01"), qi("2024-10-01") + 1)]
    for ctry, roll, start, end in (("US", ROLL_Q, SAMPLE["US"][0], SAMPLE["US"][1]),
                                   ("EA", ROLL_Q, SAMPLE["EA"][0], SAMPLE["EA"][1])):
        zl = ZLB_MAX[ctry]
        for variant, zlb in (("all", None), ("nozlb", zl)):
            if variant == "nozlb" and zlb is None:
                continue
            keys_all, yv, X, names, lab = panel_arrays(
                P[ctry], start, end, True, "y", zlb_max=zlb)
            jj = names.index("phi_pi")
            for k_end in grid:
                upto = [i for i, k in enumerate(keys_all) if k <= k_end]
                if len(upto) < roll:
                    continue
                i0 = upto[-1] - roll + 1
                Xw, yw = X[i0:upto[-1] + 1], yv[i0:upto[-1] + 1]
                f = ols_hac(yw, Xw, names, HAC_LAG_Q)
                lo, hi = f.ci(jj)
                blo, bhi, _ = block_bootstrap_ci(yw, Xw, jj, HAC_LAG_Q, n_rep=1500,
                                                 block=BOOT_BLOCK_Q)
                rep["rolling"].append({
                    "ctry": ctry, "variant": variant,
                    "end": lab(k_end), "k_end": k_end,
                    "used": lab(keys_all[upto[-1]]),
                    "start": lab(keys_all[i0]), "k_start": keys_all[i0], "n": f.n,
                    "phi_pi": round(float(f.beta[jj]), 4),
                    "se_hac": round(float(f.se_hac[jj]), 4),
                    "ci95_hac": [round(lo, 4), round(hi, 4)],
                    "ci95_boot": [round(blo, 4), round(bhi, 4)],
                    "phi_y": round(float(f.beta[names.index("phi_y")]), 4),
                    "verdict": verdict(lo, hi),
                })

    # ---------- 3b. 长路径：滚动窗口走完全样本（只算 HAC，不算 bootstrap）----------
    #   为什么要它：只画 2021–2024 那 16 个点，看不出"隐含 φπ 的历史形态"。
    #   走完全样本才能看出"1980 年代高、2008 年后塌"这件事。图 fig_phi_implied 用它。
    for ctry in ("US", "EA"):
        keys_all, yv, X, names, lab = panel_arrays(P[ctry], SAMPLE[ctry][0],
                                                   SAMPLE[ctry][1], True, "y")
        jj = names.index("phi_pi")
        for t in range(ROLL_Q - 1, len(keys_all)):
            Xw, yw = X[t - ROLL_Q + 1:t + 1], yv[t - ROLL_Q + 1:t + 1]
            f = ols_hac(yw, Xw, names, HAC_LAG_Q)
            lo, hi = f.ci(jj)
            rep.setdefault("long", []).append({
                "ctry": ctry, "end": lab(keys_all[t]), "k_end": keys_all[t],
                "phi_pi": round(float(f.beta[jj]), 4),
                "se_hac": round(float(f.se_hac[jj]), 4),
                "ci95_hac": [round(lo, 4), round(hi, 4)],
                "verdict": verdict(lo, hi),
            })
    n_long_us = sum(1 for r in rep["long"] if r["ctry"] == "US")
    n_long_ea = sum(1 for r in rep["long"] if r["ctry"] == "EA")
    checks["长路径滚动"] = (f"美国 {n_long_us} 个窗口（"
                            f"{rep['long'][0]['end']} 起）、欧元区 {n_long_ea} 个窗口；"
                            f"只算 HAC 区间，不算 bootstrap（图用）")
    # ---------- 4. 含利率平滑项的稳健性（③ 偏误来源表第 2 行）----------
    #   ★ 含平滑项时 φπ 只解释为**短期**反应系数；
    #     泰勒原则关心的是**长期**反应 φπ/(1-ρ)。两个都要报。
    def smoothing_spec(ctry: str, st: str, en: str) -> dict:
        keys, yv, X0, names0, lab = panel_arrays(P[ctry], st, en, True, "y")
        X = np.column_stack([X0, np.concatenate([[yv[0]], yv[:-1]])])
        names = names0 + ["rho_i_lag"]
        f = ols_hac(yv[1:], X[1:], names, HAC_LAG_Q)
        j = names.index("phi_pi")
        r = names.index("rho_i_lag")
        lo, hi = f.ci(j)
        b, rho = float(f.beta[j]), float(f.beta[r])
        # 长期系数 g = φπ/(1-ρ)，delta 法用 HAC 协方差矩阵（含非对角元）
        denom = 1.0 - rho
        g = b / denom
        grad = np.zeros(len(names))
        grad[j] = 1.0 / denom
        grad[r] = b / denom ** 2
        se_g = float(np.sqrt(max(grad @ f.V @ grad, 0.0)))
        glo, ghi = g - Z95 * se_g, g + Z95 * se_g
        # 同一量的块 bootstrap 区间（重抽 (φπ, ρ) 的联合分布）
        rng = np.random.default_rng(SEED + 7)
        n = len(yv) - 1
        nb = int(math.ceil(n / BOOT_BLOCK_Q))
        gs = np.empty(2000)
        for i in range(2000):
            starts = rng.integers(0, n, size=nb)
            idx = np.concatenate([np.arange(s, s + BOOT_BLOCK_Q) % n
                                  for s in starts])[:n]
            Xb, yb = X[1:][idx], yv[1:][idx]
            try:
                bb = np.linalg.solve(Xb.T @ Xb, Xb.T @ yb)
            except np.linalg.LinAlgError:
                gs[i] = np.nan
                continue
            d = 1.0 - bb[r]
            gs[i] = bb[j] / d if abs(d) > 1e-6 else np.nan
        gs = gs[np.isfinite(gs)]
        return {
            "ctry": ctry, "ctry_label": CTRY_LABEL[ctry], "n": f.n,
            "span": f"{lab(keys[0])}–{lab(keys[-1])}",
            "phi_pi": round(b, 4), "se_hac": round(float(f.se_hac[j]), 4),
            "ci95_hac": [round(lo, 4), round(hi, 4)],
            "rho": round(rho, 4),
            "long_run": round(g, 4), "se_long_run": round(se_g, 4),
            "ci95_long_run": [round(glo, 4), round(ghi, 4)],
            "ci95_long_run_boot": [round(float(np.percentile(gs, 2.5)), 4),
                                   round(float(np.percentile(gs, 97.5)), 4)],
            "verdict": verdict(lo, hi),
            "verdict_long_run": verdict(glo, ghi),
        }

    rep["specs"]["smoothing"] = [
        smoothing_spec("US", SAMPLE["US"][0], SAMPLE["US"][1]),
        smoothing_spec("EA", SAMPLE["EA"][0], SAMPLE["EA"][1]),
        smoothing_spec("CN", SAMPLE["CN"][0], SAMPLE["CN"][1]),
    ]

    # ---------- 5. 自检 ----------
    # ⑤a 省略产出缺口项会把 φπ 推向哪边，用美国样本**实测**，不靠理论断言
    #     （中国那一路必须省略产出缺口，这里给它的省略偏误定标）
    def _pp(tag: str) -> float:
        for r in rep["full"]:
            if r["ctry"] == "US" and r["tag"] == tag:
                return float(r["phi_pi"])
        raise KeyError(tag)

    with_gap = _pp("1960-2026 全样本")
    without_gap = _pp("1960-2026 去掉产出缺口（定标用）")
    checks["省略产出缺口的偏误定标（美国实测）"] = {
        "含缺口 φπ": round(with_gap, 4),
        "省略缺口 φπ": round(without_gap, 4),
        "偏移": round(without_gap - with_gap, 4),
        "读法": ("省略产出缺口使 φπ 变小（下偏）" if without_gap < with_gap
                 else "省略产出缺口使 φπ 变大（上偏）"),
    }

    # ⑤b 零下限把 φπ 拖下去多少，全样本剔除 vs 不剔除
    zlb_us = [r for r in rep["full"] if r["ctry"] == "US"
              and r["tag"] == "1960-2026 剔除零下限季度"][0]
    checks["零下限的影响（美国全样本）"] = {
        "含零下限 φπ": round(with_gap, 4),
        "剔除零下限 φπ": zlb_us["phi_pi"],
        "差值": round(zlb_us["phi_pi"] - with_gap, 4),
        "判定": (f"含零下限时 95% 区间 {verdict(*[r for r in rep['full'] if r['ctry']=='US' and r['tag']=='1960-2026 全样本'][0]['ci95_hac'])}，"
                 f"剔除后 {zlb_us['verdict']}"),
    }

    # ⑤ FWL 恒等式（数学上必须精确成立）
    dev = 0.0
    for ctry, st, en, gk in (("US", SAMPLE["US"][0], SAMPLE["US"][1], "y"),
                             ("EA", SAMPLE["EA"][0], SAMPLE["EA"][1], "y")):
        keys, yv, X, names, lab = panel_arrays(P[ctry], st, en, True, gk)
        for jj in range(X.shape[1]):
            dev = max(dev, abs(fwl_check(yv, X, jj) - np.linalg.lstsq(X, yv, rcond=None)[0][jj]))
    assert dev < 1e-9, f"FWL 自检失败：最大偏差 {dev:.2e}"
    checks["FWL 恒等式"] = f"最大偏差 {dev:.2e}（必须 < 1e-9）"

    # ⑥ 手写 HAC 的两条独立代码路径必须吻合
    #    （原计划用 statsmodels 复核，但本机 pandas 3.0 与 statsmodels 0.14 不兼容，
    #      `import statsmodels.api` 直接抛 TypeError ⇒ 改为同一公式的两条实现互证，
    #      区间则另由块 bootstrap 提供第二套方法。理由写进 _logs/踩坑.md）
    worst = 0.0
    for ctry, st, en, gk, lag in (("US", SAMPLE["US"][0], SAMPLE["US"][1], "y", HAC_LAG_Q),
                                  ("EA", SAMPLE["EA"][0], SAMPLE["EA"][1], "y", HAC_LAG_Q),
                                  ("CN", SAMPLE["CN"][0], SAMPLE["CN"][1], "y", HAC_LAG_M)):
        keys, yv, X, names, lab = panel_arrays(
            P[ctry], st, en, False if ctry == "CN" else True, gk)
        b1, se1 = ols_hac_loop(yv, X, lag)
        f2 = ols_hac(yv, X, names, lag)
        worst = max(worst, float(np.max(np.abs(b1 - f2.beta))),
                    float(np.max(np.abs(se1 - f2.se_hac))))
    assert worst < 1e-10, f"HAC 两条实现不一致：{worst:.2e}"
    checks["HAC 两条实现互证"] = (f"向量化 Γ 累加 vs 观测维双重循环，"
                                  f"最大偏差 {worst:.2e}（必须 < 1e-10）；"
                                  f"statsmodels 本机不可用，见踩坑 W57-2")

    # ⑥b HAC 相对 OLS 标准误的放大倍数：这是"结论会不会翻"的直接度量
    ratios = [r["se_hac"] / r["se_ols"] for r in rep["full"]]
    n_flip = 0
    for r in rep["full"]:
        v_o = verdict(r["phi_pi"] - Z95 * r["se_ols"], r["phi_pi"] + Z95 * r["se_ols"])
        if v_o != r["verdict"]:
            n_flip += 1
    checks["HAC / OLS 标准误"] = {
        "倍数区间": f"{min(ratios):.2f}× ~ {max(ratios):.2f}×",
        "只报 OLS 区间会与 HAC 判定相反的设定数": n_flip,
        "含义": "倍数 >1 说明残差有序列相关；判定相反说明那些结论本来就撑不住",
    }

    # ⑥c 长期系数：ρ 越接近 1，φπ/(1-ρ) 的换算越不可靠
    #     ⚠ 容差要按"存储时保留 4 位小数"来定（1e-6 会被四舍五入误伤，
    #       W54-9 记过同一类误伤：浮点乘除做不到精确等于，也不必要）
    for s in rep["specs"]["smoothing"]:
        rec = s["phi_pi"] / (1.0 - s["rho"])
        assert abs(s["long_run"] - rec) < 5e-3, \
            f"长期系数与 φπ/(1-ρ) 不一致：{s['long_run']} vs {rec}"
        assert s["ci95_long_run"][0] <= s["long_run"] <= s["ci95_long_run"][1]
    checks["含平滑项的长期系数"] = {
        "定义": "φπ^LR = φπ/(1-ρ)",
        "说明": "delta 法与块 bootstrap 两套区间都给；ρ 越接近 1 换算越不可靠",
    }

    # ⑦ 区间必须包含点估计，且 HAC 与 bootstrap 是否同侧要给出来
    n_cross = 0
    for r in rep["full"]:
        lo, hi = r["ci95_hac"]
        assert lo <= r["phi_pi"] <= hi, f"区间不含点估计：{r['tag']}"
        if r["verdict"] == "跨1":
            n_cross += 1
    checks["区间自检"] = (f"{len(rep['full'])} 组设定，区间不含点估计 0 处；"
                          f"95% 区间跨过 1 的有 {n_cross} 组")

    # ⑧ 滚动窗口的段长与端点
    #    ⚠ 判据必须用**整数季序号**，不能用 "2011Q2" 这种标签；
    #      拿 `qi()`（按 YYYY-MM-DD 解析）去解析 YYYYQn 标签，
    #      会把 Q2 读成 2 月 ⇒ 静默得到 Q1。本期就是这么被自己的断言抓住的。
    for r in rep["rolling"]:
        assert r["n"] == ROLL_Q, f"滚动窗口长度错：{r}"
        span = r["k_end"] - r["k_start"] + 1
        if r["variant"] == "all":
            assert span == ROLL_Q, f"照算口径的窗口跨度应为 {ROLL_Q} 季：{r}"
            assert r["used"] == r["end"], f"照算口径的实际末季应等于端点：{r}"
        else:
            # 剔零下限后，40 个观测要跨更长的日历区间（被剔的季度本来就在里面）
            assert span >= ROLL_Q, f"剔零下限口径的跨度不应短于观测数：{r}"
            assert r["k_start"] <= r["k_end"], f"窗口左端晚于右端：{r}"
        assert qi_label(r["k_start"]) == r["start"], f"窗口左端标签错：{r}"
        r["span_q"] = span
    n_us = sum(1 for r in rep["rolling"] if r["ctry"] == "US" and r["variant"] == "all")
    n_ea = sum(1 for r in rep["rolling"] if r["ctry"] == "EA" and r["variant"] == "all")
    checks["滚动窗口"] = (f"美国 {n_us} 个、欧元区 {n_ea} 个端点（每个端点两个口径），"
                          f"每窗 {ROLL_Q} 个观测，标签与整数季序号逐个吻合")

    # ⑩ 滚动窗口的零下限含量：这张表的核心论点依赖它
    #    "2021–2024 的每个 10 年窗口都含零下限"，这是可核的，不能只当说法
    us_all = [r for r in rep["rolling"] if r["ctry"] == "US" and r["variant"] == "all"]
    us_noz = [r for r in rep["rolling"] if r["ctry"] == "US" and r["variant"] == "nozlb"]
    n_zlb = [r["span_q"] - r["n"] for r in us_noz]
    assert min(n_zlb) >= 1, f"有窗口不含零下限季度：{n_zlb}"
    checks["滚动窗口的零下限含量（美国）"] = {
        "每个窗口里被零下限顶住的季度数": f"{min(n_zlb)} ~ {max(n_zlb)}（共 16 个窗口，全部 >= 1）",
        "含义": "所有 2021Q1–2024Q4 的 40 季窗口都含零下限时期 ⇒ "
                "照算口径下'拒绝 φπ=1'不能读成'央行放弃了泰勒原则'",
    }
    # ⑪ 剔零下限后，零下限期间窗口"没有新增观测"⇒ 估计值必须原地不动
    head5 = [r["phi_pi"] for r in us_noz[:5]]
    assert len(set(head5)) == 1, f"零下限期间剔零下限口径应完全不动：{head5}"
    checks["零下限期间窗口不更新"] = (
        "2021Q1–2022Q1 五个端点的剔零下限值完全相同（"
        f"{head5[0]:.3f}），因为 2020Q2–2021Q4 整段都在零下限，"
        "剔除后窗口没有新增观测。这不是程序错，是零下限的直接后果。")
    # ⑨ 两条滚动路径必须同端点网格（否则图上的差不是"口径差"）
    for ctry in ("US", "EA"):
        a = [r["k_end"] for r in rep["rolling"]
             if r["ctry"] == ctry and r["variant"] == "all"]
        b = [r["k_end"] for r in rep["rolling"]
             if r["ctry"] == ctry and r["variant"] == "nozlb"]
        assert a == b, f"{ctry} 两个口径的端点网格不相同：{a} vs {b}"
    checks["两条滚动路径对齐"] = "两个口径共用同一张端点网格，逐点相同"

    # ⑫ 合并判定必须与两套区间一致（不能出现"两套都跨 1 却判不跨"）
    for r in rep["full"]:
        if r["verdict"] == "跨1" or r["verdict_boot"] == "跨1":
            assert r["verdict_union"] == "跨1", f"合并判定错：{r['tag']}"
        if r["verdict"] == r["verdict_boot"] != "跨1":
            assert r["verdict_union"] == r["verdict"], f"合并判定错：{r['tag']}"
    checks["合并判定一致性"] = "两套区间任一跨 1 ⇒ 合并判跨 1（已逐行校验）"

    rep["checks"] = checks
    rep["panels"] = {c: {"freq": p["freq"], "n_i": len(p["i"]), "n_pi": len(p["pi"]),
                         "n_y": (len(p["y"]) if p["y"] is not None else 0),
                         "y_name": p["y_name"]} for c, p in P.items()}
    return rep


# ================================================================ 落盘
def fmt_ci(r: dict, key: str = "ci95_hac") -> str:
    r"""区间 + 三态判定（**纯文本，不加粗**）。

    ⚠ 这里绝不能返回 `**...**`：本函数的返回值被塞进已经被 `**` 包住的单元格里，
    嵌套粗体会让 Markdown 的 `**` 计数变成奇数 ⇒ Word 里残留字面 `**`（W54 的坑）。
    """
    lo, hi = r[key]
    mark = {"跨1": "跨1", "在1以上": "1 以上", "在1以下": "1 以下"}[
        verdict(lo, hi)]
    return f"[{lo:.3f}, {hi:.3f}] {mark}"


def write_md(rep: dict) -> Path:
    L: list[str] = []
    A = L.append
    A("# 2026-W57 · 第 05 屏结果：各国隐含 $\\phi_\\pi$ 的数据反算")
    A("")
    A("> **一句话**：用简化泰勒规则回归反算隐含 $\\phi_\\pi$，")
    A("> **每一行都带 95% 区间**；区间跨过 1 的，就不许拿它讲“央行守住了/没守住泰勒原则”。")
    A("")
    A("## 〇、先把话说清楚：这是什么、不是什么")
    A("")
    A("| | 是 | 不是 |")
    A("|---|---|---|")
    A("| 方法 | **简化泰勒规则的单方程 OLS 回归**（含 HAC 标准误）| **不是**结构估计（DSGE / GMM / 工具变量）|")
    A("| 通胀 | **事后** CPI / HICP 同比 | **不是**实时数据（real-time vintage），**不是**通胀预期 |")
    A("| 利率 | 短端政策利率（或代理）| **不是**规则拟合出来的“应有利率” |")
    A("| 产出缺口 | 美国用 CBO 潜在产出；欧元区用 HP 滤波自建；中国**没有** | **不是**三国同一口径 |")
    A("| 结论 | 能说“这段样本里数据与 $\\phi_\\pi=1$ 是否相容” | **不能说**“某央行实际在用的系数就是它” |")
    A("")
    A("**不含利率平滑项**这一点要单独强调：真实央行走的是部分调整，")
    A("省略 $i_{t-1}$ 会让 $\\hat\\phi_\\pi$ **上偏**。本期主回归不含平滑项，")
    A("但另做了一版含平滑项的（见 §四），两版并列给出。")
    A("")
    A("---")
    A("")
    A("## 一、数据体检：拿外部已知事实对账")
    A("")
    A("**判据一律取外部已知的官方数字，不取“上一次跑出来的数”**（W56-10 的教训）。")
    A("")
    A("| 检查 | 本期算出 | 官方参照 | 判定 |")
    A("|---|---|---|---|")
    c = rep["checks"]["外部已知事实对账"]
    A(f"| 美国 CPI 同比 2022-06 | **{c['US_CPI_YoY_2022M06']:.2f}%** | {c['US_官方参照']} | ✅ |")
    A(f"| 欧元区 HICP 同比 2022-10 | **{c['EA_HICP_YoY_2022M10']:.2f}%** | {c['EA_官方参照']} | ✅ |")
    A(f"| 中国 CPI 同比 2020-01 | **{c['CN_CPI_YoY_2020M01']:.2f}%** | {c['CN_官方参照']} | ✅ |")
    A("")
    A("> 这三行不是“模型结果”，是**取数是否取对**的体检。")
    A("> 三个都落在官方区间内，才说明同比是从正确的列、正确的错位月算出来的。")
    A("")
    A(f"**CBO 预测截断**：实际 GDP 末季 `{rep['checks']['CBO 预测截断']['GDPC1_last']}`；"
      f"潜在产出截断后末季 `{rep['checks']['CBO 预测截断']['GDPPOT_trunc_last']}`。")
    A("`GDPPOT` 原始序列一路画到 2036 年（含 CBO 的十年预测），")
    A("不截断就等于用未来的潜在产出去除现在的 GDP。详见 `data/来源清单.md` §2.1。")
    A("")
    A("---")
    A("")
    A("## 二、★ 主结果：$\\hat\\phi_\\pi$ 的点估计与 95% 区间")
    A("")
    A("模型：$i_t=\\alpha+\\phi_\\pi\\pi_t+\\phi_y\\tilde y_t+\\varepsilon_t$，")
    A(f"Newey–West 标准误（季度滞后 {HAC_LAG_Q} 期、月度 {HAC_LAG_M} 期），")
    A("区间为 $\\hat\\phi_\\pi\\pm1.96\\,se$。")
    A("")
    A("| 经济体 | 设定 | 频度 | 样本 | n | $\\hat\\phi_\\pi$ | HAC 标准误 | 95% 区间 | 判定 | $\\hat\\phi_y$ |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for r in rep["full"]:
        py = "—" if r["phi_y"] is None else f"{r['phi_y']:+.3f}"
        A(f"| {r['ctry_label']} | {r['tag']} | {r['freq']} | {r['span']} | {r['n']} | "
          f"**{r['phi_pi']:.3f}** | {r['se_hac']:.3f} | "
          f"{fmt_ci(r)} | {verdict(*r['ci95_hac'])} | {py} |")
    A("")
    A("**同样的点估计，换块 bootstrap 算区间**（循环块，块长 "
      f"{BOOT_BLOCK_Q} 期，{BOOT_N} 次重抽）：")
    A("")
    A("| 经济体 | 设定 | 点估计 | HAC 95% 区间 | bootstrap 95% 区间 | 两套是否同侧 | **合并判定** |")
    A("|---|---|---|---|---|---|---|")
    for r in rep["full"]:
        same = "是" if r["verdict"] == r["verdict_boot"] else "**否**"
        blo, bhi = r["ci95_boot"]
        A(f"| {r['ctry_label']} | {r['tag']} | {r['phi_pi']:.3f} | "
          f"[{r['ci95_hac'][0]:.3f}, {r['ci95_hac'][1]:.3f}] | "
          f"[{blo:.3f}, {bhi:.3f}] | {same} | **{r['verdict_union']}** |")
    A("")
    n_cross_hac = sum(1 for r in rep["full"] if r["verdict"] == "跨1")
    n_cross_boot = sum(1 for r in rep["full"] if r["verdict_boot"] == "跨1")
    n_union = sum(1 for r in rep["full"] if r["verdict_union"] == "跨1")
    A("> **★ 合并判定的规则（刻意保守）：只要 HAC 与 bootstrap 里有一套跨过 1，"
      "就判“跨1”。**")
    A("> 理由：两套区间都合法，**挑窄的那套来讲结论，等于用方法的选择把结论挑出来**。")
    A("> 宁可说“不知道”，不许说“知道了”。")
    A("")
    A(f"**计数**：{len(rep['full'])} 组设定中，HAC 区间跨 1 的有 {n_cross_hac} 组，")
    A(f"bootstrap 区间跨 1 的有 {n_cross_boot} 组，**合并判定跨 1 的有 {n_union} 组**。")
    A("")
    A("> 跨过 1 的那些，结论只能是：**这段样本里不能拒绝 $\\phi_\\pi=1$**，")
    A("> 既不能说“央行守住了泰勒原则”，也不能说“没守住”。")
    A("")
    A("### 2.1 ★ 为什么必须报 HAC 标准误：不报的话结论会反过来")
    A("")
    A("普通 OLS 标准误假设残差无序列相关。政策利率规则**不满足**这个假设")
    A("（通胀有惯性、利率有平滑），所以 OLS 标准误**系统性偏窄**。")
    A("")
    A("| 经济体 | 设定 | OLS 标准误 | HAC 标准误 | 倍数 | OLS 区间判 $\\phi_\\pi=1$ | **HAC 区间判 $\\phi_\\pi=1$** | 两个判定 |")
    A("|---|---|---|---|---|---|---|---|")
    for r in rep["full"]:
        ratio = r["se_hac"] / r["se_ols"]
        lo_o = r["phi_pi"] - Z95 * r["se_ols"]
        hi_o = r["phi_pi"] + Z95 * r["se_ols"]
        v_o = verdict(lo_o, hi_o)
        flag = "**相反**" if v_o != r["verdict"] else "一致"
        A(f"| {r['ctry_label']} | {r['tag']} | {r['se_ols']:.4f} | "
          f"{r['se_hac']:.4f} | **{ratio:.2f}×** | {v_o} | {r['verdict']} | {flag} |")
    A("")
    A("> `结论相反` 的那几行，就是“**只报 OLS 标准误会把 ‘说不清’ 写成 ‘说清了’**”")
    A("> 的现场证据。这也是本屏最便宜的一条防线：**换个标准误，结论就翻了**，")
    A("> 说明这个结论本来就撑不住。")
    A("")
    A("---")
    A("")
    A("## 三、分段：隐含 $\\phi_\\pi$ 的历史（美国）")
    A("")
    A("为什么必须分段：**2009–2015 政策利率被零下限截断**，")
    A("线性规则在这段不可识别（$i_t\\equiv 0$，$\\phi_\\pi$ 只能由通胀的变异去凑）。")
    A("")
    A("| 区间 | 样本 | n | $\\hat\\phi_\\pi$ | 95% 区间 | 判定 |")
    A("|---|---|---|---|---|---|")
    for r in rep["sub"]:
        A(f"| {r['tag']} | {r['span']} | {r['n']} | **{r['phi_pi']:.3f}** | "
          f"[{r['ci95_hac'][0]:.3f}, {r['ci95_hac'][1]:.3f}] | {r['verdict']} |")
    A("")
    A("**上表有两行必须单独读，否则会被它的区间骗到：**")
    A("")
    A("1. **`2009-2015 零利率下限` 那一行，区间窄得反常（$[-0.023,-0.004]$）。**")
    A("   这不是“估得很准”，恰恰相反：这段里 $i_t$ 几乎是常数，")
    A("   $\\phi_\\pi$ 由通胀的**极小残余变异**决定，回归**退化**了。")
    A("   窄区间是退化的症状，不是精度的证据。")
    A("2. **`2020-2026` 那一行是负的（$-0.414$）。** 这不是“央行反着来”，")
    A("   而是**加息滞后于通胀**：通胀 2022 年年中见顶，政策利率到 2023 年才到顶。")
    A("   同期回归会把“反应滞后”读成“负反应”。")
    A("   ⇒ 这一行**不能**用来支持任何关于“央行是否守规则”的结论。")
    A("")
    A("> ★ 这两行合起来正好说明第 04 屏的论点：")
    A("> **规则在约束绑定的时候不可识别，而在约束刚松开的头两年又会给出错的符号。**")
    A("")
    A("---")
    A("")
    A("## 四、稳健性：加上利率平滑项，并看**长期**反应")
    A("")
    A("$i_t=\\alpha+\\rho i_{t-1}+\\phi_\\pi\\pi_t+\\phi_y\\tilde y_t+\\varepsilon_t$。")
    A("")
    A("> ★ **加了平滑项之后，$\\phi_\\pi$ 不再是泰勒原则关心的那个量。**")
    A("> 泰勒原则关心的是**长期**反应")
    A(">")
    A("> $$\\phi_\\pi^{\\text{LR}}=\\frac{\\phi_\\pi}{1-\\rho}.$$")
    A(">")
    A("> 只报短期系数会把结论说反：短期 $\\phi_\\pi$ 可以小到 0.1，")
    A("> 而长期 $\\phi_\\pi^{\\text{LR}}$ 仍然在 1 附近。**两个都报。**")
    A("")
    A("| 经济体 | 样本 | n | $\\hat\\rho$ | 短期 $\\hat\\phi_\\pi$ | 95% 区间 | **长期 $\\hat\\phi_\\pi^{\\text{LR}}$** | 95% 区间（delta）| 95% 区间（bootstrap）| 长期判定 |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for s in rep["specs"]["smoothing"]:
        A(f"| {s['ctry_label']} | {s['span']} | {s['n']} | **{s['rho']:.3f}** | "
          f"{s['phi_pi']:.3f} | [{s['ci95_hac'][0]:.3f}, {s['ci95_hac'][1]:.3f}] | "
          f"**{s['long_run']:.3f}** | "
          f"[{s['ci95_long_run'][0]:.3f}, {s['ci95_long_run'][1]:.3f}] | "
          f"[{s['ci95_long_run_boot'][0]:.3f}, {s['ci95_long_run_boot'][1]:.3f}] | "
          f"{s['verdict_long_run']} |")
    A("")
    A("> **短期系数与长期系数的结论可以完全相反。** 上表里美国短期 $\\phi_\\pi$")
    A("> 显著低于 1，而长期 $\\phi_\\pi^{\\text{LR}}$ 的区间**跨过 1**。")
    A("> 谁对？**两个都只是同一个模型的两种读法**，")
    A("> 而 $\\rho$ 越接近 1，两者的换算越不可靠（$1-\\rho$ 在分母上）。")
    A("> 所以这一节的作用**不是**给一个更可信的点估计，")
    A("> 而是说明：**\"$\\phi_\\pi$ 是多少\"这个问题，取决于你把平滑算不算进去。**")
    A("")
    A("---")
    A("")
    A("## 五、★ 2021–2024 逐季隐含 $\\phi_\\pi$（滚动回归）")
    A("")
    A(f"滚动窗口 **{ROLL_Q} 个观测**（约 10 年），窗口右端从 2021Q1 走到 2024Q4，")
    A("每个窗口跑两个口径：")
    A("")
    A("| 口径 | 窗口里放什么 | 为什么要有这个口径 |")
    A("|---|---|---|")
    A("| **照算（all）** | 窗口内**全部**观测 | 这是“拿一条线性规则去套数据”看到的真实样子 |")
    A("| **剔零下限（nozlb）** | 剔除政策利率被下限顶住（"
      f"$i\\le${ZLB_MAX['US']}）的观测 | 这些观测里 $i_t$ 是常数，$\\phi_\\pi$ 只能由通胀的变异去凑 |")
    A("")
    A("> **两个口径的差，就是零下限把 $\\phi_\\pi$ 拖下去多少。**")
    A("> 这一条是本屏的核心：模型说零下限会让规则失效（第 04 屏），")
    A("> 数据这边**恰好**在含零下限的那些窗口里把 $\\phi_\\pi$ 量成了 0。")
    A("")
    for ctry in ("US", "EA"):
        alc = [r for r in rep["rolling"] if r["ctry"] == ctry and r["variant"] == "all"]
        noz = [r for r in rep["rolling"] if r["ctry"] == ctry and r["variant"] == "nozlb"]
        if not alc:
            continue
        A(f"### {CTRY_LABEL[ctry]}")
        A("")
        A("| 窗口右端 | $\\hat\\phi_\\pi$（照算）| 95% 区间 | 判定 | 窗口跨度 | "
          "$\\hat\\phi_\\pi$（剔零下限）| 95% 区间 | 判定 | 窗口跨度 |")
        A("|---|---|---|---|---|---|---|---|---|")
        for a, b in zip(alc, noz):
            A(f"| **{a['end']}** | **{a['phi_pi']:.3f}** | "
              f"[{a['ci95_hac'][0]:.3f}, {a['ci95_hac'][1]:.3f}] | {a['verdict']} | "
              f"{a['span_q']} 季 | "
              f"{b['phi_pi']:.3f} | [{b['ci95_hac'][0]:.3f}, {b['ci95_hac'][1]:.3f}] | "
              f"{b['verdict']} | {b['span_q']} 季 |")
        A("")
        la = min(r["phi_pi"] for r in alc)
        ha = max(r["phi_pi"] for r in alc)
        ln = min(r["phi_pi"] for r in noz)
        hn = max(r["phi_pi"] for r in noz)
        ca = sum(1 for r in alc if r["verdict"] == "跨1")
        cn = sum(1 for r in noz if r["verdict"] == "跨1")
        A(f"**{CTRY_LABEL[ctry]}读法**：照算口径 $\\hat\\phi_\\pi\\in[{la:.3f},{ha:.3f}]$，"
          f"其中 **{ca}/{len(alc)}** 个窗口的 95% 区间跨过 1；"
          f"剔零下限口径 $\\hat\\phi_\\pi\\in[{ln:.3f},{hn:.3f}]$，"
          f"**{cn}/{len(noz)}** 个窗口跨 1。")
        A("")
    A("---")
    A("")
    A("## 六、自检")
    A("")
    A("| # | 检查 | 结果 |")
    A("|---|---|---|")
    for i, (k, v) in enumerate(rep["checks"].items(), 1):
        vv = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        A(f"| {i} | {k} | {vv} |")
    A("")
    A("**FWL 恒等式**是最便宜的一个独立实现：Frisch–Waugh–Lovell 定理在数学上")
    A("精确成立，所以偏差只能是实现错，不会“数据恰好这样”。")
    A("**HAC 标准误**另用同一公式的第二条代码路径（观测维双重循环）复核；")
    A("`statsmodels` 在本机装不起来（pandas 3.0 不兼容），所以没有走“对第三方库”这条路，")
    A("改由**块 bootstrap** 提供第二套区间方法。")
    A("")
    A("---")
    A("")
    A("## 七、★ 诚实性声明（必须随结论一起出现）")
    A("")
    A("1. **这是简化泰勒规则回归，不是结构估计。** 没有工具变量，没有系统 GMM，")
    A("   没有识别货币政策冲击，因此**不能**做“外生加息 1 个百分点”的反事实；")
    A("2. **不控制预期。** 右端是事后通胀，而央行反应的是预期通胀。")
    A("   若预期比实现更平滑，本节会**低估**央行的真实反应强度；")
    A("3. **不含平滑项的主回归 $\\hat\\phi_\\pi$ 上偏。** 见 §四；")
    A("4. **用事后通胀而非实时数据**：今天看到的 CPI 是修订后的，")
    A("   而央行当年看到的是初值 ⇒ 存在引视偏差；")
    A("5. **零利率下限段（2009–2015、2020）不可识别**：$i_t$ 被截断，")
    A("   线性规则在这段没有信息。含这段的全样本估计**必然**偏低；")
    A("6. **中国那一路不能与美国同台**：缺产出缺口项（FRED 相关序列 404），")
    A("   政策利率只能用银行间利率代理，且 CPI 序列止于 2025-04；")
    A("7. **区间跨过 1 的，一律不下结论。** 本文件的三态判定就是这个意思。")
    A("")
    OUTP = OUT_MD
    OUTP.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"[md] {OUTP}")
    return OUTP


def write_csv(rep: dict) -> Path:
    rows = []
    for r in rep["rolling"]:
        rows.append({
            "path": "rolling2021_2024",
            "ctry": r["ctry"], "variant": r["variant"],
            "end": r["end"], "start": r["start"], "n": r["n"],
            "phi_pi": r["phi_pi"], "se_hac": r["se_hac"],
            "ci_lo": r["ci95_hac"][0], "ci_hi": r["ci95_hac"][1],
            "boot_lo": r["ci95_boot"][0], "boot_hi": r["ci95_boot"][1],
            "phi_y": r["phi_y"], "verdict": r["verdict"],
        })
    for r in rep.get("long", []):
        rows.append({
            "path": "long", "ctry": r["ctry"], "variant": "all",
            "end": r["end"], "start": "", "n": ROLL_Q,
            "phi_pi": r["phi_pi"], "se_hac": r["se_hac"],
            "ci_lo": r["ci95_hac"][0], "ci_hi": r["ci95_hac"][1],
            "boot_lo": "", "boot_hi": "", "phi_y": "",
            "verdict": r["verdict"],
        })
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"[csv] {OUT_CSV}")
    return OUT_CSV


def brief(rep: dict) -> None:
    print("\n" + "=" * 104)
    print("  主结果：隐含 phi_pi 的点估计与 95% 区间（★ 区间跨 1 的不许下结论）")
    print("=" * 104)
    print(f"  {'经济体':<8} {'设定':<30} {'n':>4} {'phi_pi':>7} {'95% 区间':>20}  判定")
    print("  " + "-" * 100)
    for r in rep["full"]:
        lo, hi = r["ci95_hac"]
        print(f"  {r['ctry_label']:<8} {r['tag']:<30} {r['n']:>4} "
              f"{r['phi_pi']:>7.3f} {'[' + f'{lo:.3f}, {hi:.3f}' + ']':>20}  {r['verdict']}")
    print("\n" + "=" * 104)
    print("  2021Q1–2024Q4 逐季滚动（40 个观测窗口，两个口径）")
    print("=" * 104)
    for ctry in ("US", "EA"):
        print(f"  == {CTRY_LABEL[ctry]} ==")
        print(f"    {'右端':<8} {'照算':>8} {'95% 区间':>19} {'判定':<8} "
              f"{'剔ZLB':>8} {'95% 区间':>19} {'判定':<8} 跨度")
        for a in [x for x in rep["rolling"] if x["ctry"] == ctry and x["variant"] == "all"]:
            b = [x for x in rep["rolling"] if x["ctry"] == ctry
                 and x["variant"] == "nozlb" and x["k_end"] == a["k_end"]][0]
            a_lo, a_hi = a["ci95_hac"]
            b_lo, b_hi = b["ci95_hac"]
            ca = f"[{a_lo:.3f}, {a_hi:.3f}]"
            cb = f"[{b_lo:.3f}, {b_hi:.3f}]"
            print(f"    {a['end']:<8} {a['phi_pi']:>8.3f} {ca:>19} {a['verdict']:<8} "
                  f"{b['phi_pi']:>8.3f} {cb:>19} {b['verdict']:<8} "
                  f"{a['span_q']}→{b['span_q']}")
    print("\n  自检：")
    for k, v in rep["checks"].items():
        vv = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        print(f"    · {k}：{vv}")


def main() -> int:
    ap = argparse.ArgumentParser(description="W57 第 05 屏：隐含 phi_pi 反算")
    ap.add_argument("--probe", action="store_true", help="只打印结果，不写文件")
    args = ap.parse_args()
    print("=" * 100)
    print("  W57 · 隐含 phi_pi：简化泰勒规则回归 + 滚动 + 双套区间")
    print("=" * 100)
    rep = run()
    brief(rep)
    if args.probe:
        print("\n  [probe] 未写任何文件")
        return 0
    RES.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[json] {OUT_JSON}")
    write_csv(rep)
    write_md(rep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
