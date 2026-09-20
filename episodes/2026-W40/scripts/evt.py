#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W40 公共模块：数据加载 + 极值分析基础工具。

数据性质（**必须贯穿所有结论**）
--------------------------------
数据来自 Open-Meteo 的 **再分析/网格融合**产品，**不是站点实测**。
实测比对（见 `data/来源清单.md`）：

    气温：吐鲁番 网格 50.3℃  vs 新闻实测 49.8℃   → 差 +0.5℃，**可用**
    降水：恩平   网格 108.7mm vs 新闻实测 597.7mm → 只剩 18%，**绝对值不可用**

因此：
  · 气温的绝对量可以引用（误差 ±0.5℃ 量级）
  · 降水的**绝对量不可引用**，只做城市间相对比较、时间趋势、
    以及联合概率结构（copula 的依赖参数对边缘的量纲不敏感）
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
RESULTS = ROOT / "results"
FIGS = RESULTS / "figs"
for _d in (RESULTS, FIGS):
    _d.mkdir(parents=True, exist_ok=True)

CITY_FILE = DATA / "城市清单.json"

# 四组的含义（用于分组对比）
GROUPS = {
    "A": "基准大城市",
    "B": "今年降雨破纪录",
    "C": "今年高温破纪录",
    "D": "对照（今年不极端）",
}


def load_cities() -> list[dict]:
    """读城市清单（含经纬度与分组）。"""
    return json.loads(CITY_FILE.read_text(encoding="utf-8"))


def load_series(city: str) -> dict:
    """读单城逐日序列。

    返回 dict：
      dates  : 字符串日期数组（'YYYY-MM-DD'）
      tmax   : 日最高气温 (℃)，缺测为 nan
      precip : 日降水量 (mm)，缺测为 nan
      year   : 年份整数数组
    """
    p = RAW / f"{city}.csv"
    if not p.exists():
        raise FileNotFoundError(f"缺数据：{p}")
    txt = p.read_text(encoding="utf-8").strip().splitlines()
    hdr = txt[0].split(",")
    dates, tmax, precip = [], [], []
    for ln in txt[1:]:
        f = ln.split(",")
        if len(f) < 3:
            continue
        dates.append(f[0])
        tmax.append(float(f[1]) if f[1] else np.nan)
        precip.append(float(f[2]) if f[2] else np.nan)
    d = np.array(dates)
    return {"dates": d,
            "tmax": np.array(tmax, dtype=float),
            "precip": np.array(precip, dtype=float),
            "year": np.array([int(x[:4]) for x in d])}


def annual_max(x: np.ndarray, year: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """按年取最大值（区组极大值法 BM 的输入）。

    返回 (years, maxima)，按年份升序。
    ⚠️ 只保留**完整年**：某年缺测日数 > 5 则舍弃该年，
    否则年最大值会因缺测而偏低（这是极值分析里常见的隐性偏差）。
    """
    ys = sorted(set(year.tolist()))
    out_y, out_m = [], []
    for y in ys:
        m = year == y
        v = x[m]
        if np.isnan(v).sum() > 5:
            continue
        if np.isnan(v).all():
            continue
        out_y.append(y)
        out_m.append(np.nanmax(v))
    return np.array(out_y), np.array(out_m)


def exceedances(x: np.ndarray, thr: float) -> np.ndarray:
    """超阈值法的超出量（POT）：返回 (x - thr) for x > thr，去掉非正值。"""
    v = x[~np.isnan(x)]
    e = v[v > thr] - thr
    return e[e > 0]


def gev_fit(m: np.ndarray, with_trend: bool = False, n_tries: int = 6):
    """GEV 极大似然拟合，返回 (params, loglik, aic)。

    params = (mu, sigma, xi)；若 with_trend=True 则 params=(mu0, mu1, sigma, xi)，
    位置参数随时间线性漂移 μ(t) = μ0 + μ1·t（t 为 0..n-1 的年份序号）。
    用 scipy 的 genextreme（scipy 的参数化 c = -xi）。

    n_tries 控制多初值重启次数。**自助法里可调到 2**——
    实测 6 个初值让 9600 次自助拟合跑了一小时还没完；
    自助法只是给区间做对照（主结果是数值 Hessian），无需那么多次重启。
    """
    from scipy.stats import genextreme
    n = len(m)
    t = np.arange(n, dtype=float)

    def nll(p):
        if with_trend:
            mu0, mu1, sg, xi = p
            mu = mu0 + mu1 * t
        else:
            mu, sg, xi = p
            mu = np.full(n, mu)
        if sg <= 0 or not np.isfinite(sg):
            return 1e12
        if abs(xi) > 2.0:
            return 1e12
        ll = genextreme.logpdf(m, c=-xi, loc=mu, scale=sg)
        if not np.all(np.isfinite(ll)):
            return 1e12
        return -ll.sum()

    from scipy.optimize import minimize
    m0, s0 = float(np.mean(m)), float(np.std(m, ddof=1))
    if with_trend:
        x0 = np.array([m0, 0.0, s0, -0.1])
        bnds = [(m0 - 8 * s0, m0 + 8 * s0), (-2 * s0, 2 * s0),
                (1e-3 * s0, 6 * s0), (-0.8, 0.8)]
    else:
        x0 = np.array([m0, s0, -0.1])
        bnds = [(m0 - 8 * s0, m0 + 8 * s0), (1e-3 * s0, 6 * s0), (-0.8, 0.8)]

    best, bestv = None, np.inf
    for trial in range(max(1, n_tries)):
        if trial == 0:
            z = x0
        else:
            rng = np.random.default_rng(100 + trial)
            z = np.array([np.clip(x0[i] + rng.normal(0, 0.35 * abs(x0[i]) + 1e-6),
                                 bnds[i][0], bnds[i][1])
                          for i in range(len(x0))])
        try:
            r = minimize(nll, z, method="L-BFGS-B", bounds=bnds,
                         options={"maxiter": 3000})
            if r.fun < bestv:
                best, bestv = r.x, float(r.fun)
        except Exception:                            # noqa: BLE001
            continue
    if best is None:
        raise RuntimeError("GEV 拟合失败")
    k = len(best)
    aic = 2 * k + 2 * bestv
    return best, -bestv, aic


def gev_return_level(params, T: float, with_trend: bool = False, t_at: float = 0.0):
    """给定重现期 T（年），返回对应分位（重现水平）。

    重现期 T 对应年超越概率 p = 1/T，即分位 1-p。
    μ(t) 取 t_at 处的值（非平稳时用于指定年份）。
    """
    from scipy.stats import genextreme
    if with_trend:
        mu0, mu1, sg, xi = params
        mu = mu0 + mu1 * t_at
    else:
        mu, sg, xi = params
    return float(genextreme.ppf(1 - 1 / T, c=-xi, loc=mu, scale=sg))


def gev_return_period(params, x: float, with_trend: bool = False,
                      t_at: float = 0.0) -> float:
    """给定值 x，返回其重现期（年）。"""
    from scipy.stats import genextreme
    if with_trend:
        mu0, mu1, sg, xi = params
        mu = mu0 + mu1 * t_at
    else:
        mu, sg, xi = params
    p = float(genextreme.sf(x, c=-xi, loc=mu, scale=sg))
    return float("inf") if p <= 0 else 1.0 / p


def gpd_fit(e: np.ndarray):
    """GPD（超阈值）极大似然拟合，返回 (xi, beta, loglik, aic)。

    scipy 的 genpareto 参数化：c = xi，scale = beta。
    """
    from scipy.stats import genpareto
    from scipy.optimize import minimize
    n = len(e)
    if n < 10:
        raise RuntimeError(f"超阈值样本太少（{n}）")

    def nll(p):
        xi, beta = p
        if beta <= 0 or abs(xi) > 1.5:
            return 1e12
        ll = genpareto.logpdf(e, c=xi, scale=beta)
        if not np.all(np.isfinite(ll)):
            return 1e12
        return -ll.sum()

    x0 = np.array([0.0, float(np.mean(e))])
    bnds = [(-0.8, 0.8), (1e-6, 20 * max(float(np.mean(e)), 1e-6))]
    best, bestv = None, np.inf
    for trial in range(5):
        z = x0 if trial == 0 else np.array(
            [np.clip(x0[0] + np.random.default_rng(200 + trial).normal(0, 0.2),
                     bnds[0][0], bnds[0][1]),
             np.clip(x0[1] * (1 + np.random.default_rng(300 + trial).normal(0, 0.3)),
                     bnds[1][0], bnds[1][1])])
        try:
            r = minimize(nll, z, method="L-BFGS-B", bounds=bnds,
                         options={"maxiter": 3000})
            if r.fun < bestv:
                best, bestv = r.x, float(r.fun)
        except Exception:                            # noqa: BLE001
            continue
    if best is None:
        raise RuntimeError("GPD 拟合失败")
    return float(best[0]), float(best[1]), -bestv, 2 * 2 + 2 * bestv


def gpd_return_level(xi: float, beta: float, n_exc: int, n_years: float,
                     T: float) -> float:
    """由 GPD 推重现水平（超出量），再加回阈值。

    年超越率 ζ = n_exc / n_years；重现期 T 对应超出量分位 1 - 1/(T·ζ)。
    """
    from scipy.stats import genpareto
    zeta = n_exc / n_years
    p = 1 - 1.0 / (T * zeta)
    if p <= 0:
        return float("inf")
    if p >= 1:
        return 0.0
    return float(genpareto.ppf(p, c=xi, scale=beta))


def save_json(obj, name: str) -> Path:
    p = RESULTS / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def bootstrap_ci(fn, n_boot: int = 400, seed: int = 7, alpha: float = 0.05):
    """自助法置信区间：fn(rng) 应返回一个标量。

    极值分析的样本很稀少（85 年只有 85 个年最大值），
    点估计不可靠，**必须给区间**。
    """
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        try:
            v = fn(rng)
            if np.isfinite(v):
                vals.append(v)
        except Exception:                            # noqa: BLE001
            continue
    if len(vals) < 20:
        return None, None, len(vals)
    a = np.array(vals)
    return (float(np.quantile(a, alpha / 2)),
            float(np.quantile(a, 1 - alpha / 2)), len(a))
