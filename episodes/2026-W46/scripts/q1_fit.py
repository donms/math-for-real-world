#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · Q1 拟合 + **实用可辨识性**（剖面似然）。

## 数据对齐（必须先说清，否则拟合无意义）

`ili_weekly.csv` 的周编号是 ISO `YYYYWW`。定义

$$\text{flat}(w) = (Y-2000)\times52 + (W-1)$$

作为模型时间 $t$（单位：周），$t=0$ 对应 2000 年第 1 周。
季节性项 $\Sigma(t)=1+\epsilon\cos\frac{2\pi(t-\theta)}{52}$
的周期是 52 周，相位 $\theta$ 由数据估计。

> ⚠️ ISO 周号每年重置，**不能**直接用 `YYYYWW` 做减法
> （200001→200101 数字跳 100 而实际只差 1 周）。
> 这个坑在 `health_check.py` 里已经踩过一次。

## 目标函数

残差**相对化**（给"份额"和"占比"同等的相对权重，避免被大数值主导）：

$$R(\Theta)=\sum_t\Bigl(\frac{\hat y_t-y_t}{\bar y}\Bigr)^2
+\lambda_z\sum_t\bigl(\hat z_t-z_t\bigr)^2$$

* $\hat y=\rho(I_1^{\text{tot}}+I_2^{\text{tot}})\cdot100$，观测 $y$=`ili`
* $\hat z=I_1^{\text{tot}}/(I_1^{\text{tot}}+I_2^{\text{tot}})$，
  观测 $z=$ `percent_a/(percent_a+percent_b)`
* 份额项按定义域在 [0,1]、最敏感 ⇒ 给权重 $\lambda_z$（默认 3.0）

## 可辨识性：**剖面似然**

对每个参数 $\theta_j$：固定它在一系列取值上，**重新优化其余全部参数**，
得到剖面 $R_j^\star(\theta_j)$。判据（$\chi^2_1$，95%）：

$$R_j^\star(\theta_j)-R^\star_{\min}<\Delta,\qquad \Delta=3.84$$

* **剖面有界**（两侧都能越过 $\Delta$）⇒ 该参数**可辨识**，报告区间；
* **剖面发散**（单侧一直贴着 $\Delta$ 以内）⇒ **不可辨识**，
  此时**不得报告点估计**，应降阶或固定该参数并说明。

用法：
    $PY q1_fit.py --fit                # 拟合
    $PY q1_fit.py --fit --profile      # 拟合 + 全部剖面
    $PY q1_fit.py --profile phi        # 只做某参数剖面
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402
from scipy.optimize import minimize      # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import q1_model as M                                        # noqa: E402

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
RES = ROOT / "results"
FIGS = RES / "figs"

# 待估参数（对数尺度，保证正）
FIT_NAMES = ["beta0", "phi", "eps", "theta", "gamma", "omega", "rho"]
# 固定量：初始种子（影响早期瞬态）
SEED = 1e-4
SPINUP_YEARS = 3.0            # 前 3 年丢弃（瞬态）
FIT_FROM_YEAR = 2005          # 拟合窗口起点
T0 = SPINUP_YEARS * 52.0

# ★ 性能开关（实测调出来的）
#   `SPAN_YEARS`：**积分只跑最近这一段**。2005–2026 有 1300+ 个积分子步，
#     而观测点只有 ~1100 个 ⇒ 单次 SSE 约 145ms，20 起点要 30 分钟。
#     截到最近 11 年（仍含 11 个完整流行季，足够估周期与相位）
#     可把积分步数降到约一半。
#   `MAX_STEP`：积分器最大步长。季节项周期 52 周，步长 ≤1 周仍充分解析。
SPAN_YEARS = 11
MAX_STEP = 1.0

# 参数边界（对数尺度）
BOUNDS = {"beta0": (0.3, 4.0), "phi": (0.6, 2.5), "eps": (0.0, 0.95),
          "theta": (0.0, 51.9), "gamma": (0.2, 4.0), "omega": (1e-4, 2.0),
          "rho": (0.05, 200.0)}
LAMBDA_Z = 3.0
CHI2_1_95 = 3.8415


def flat_week(w: int) -> int:
    return (w // 100 - 2000) * 52 + (w % 100 - 1)


def load_pairs():
    """返回 (t, y, z)，z 为可缺测（NaN）的 A 株份额。"""
    with open(CLEAN / "ili_weekly.csv", encoding="utf-8") as f:
        ili = list(csv.DictReader(f))
    cli = {}
    with open(CLEAN / "clinical_weekly.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                a, b = float(r["percent_a"]), float(r["percent_b"])
                if a + b > 0:
                    cli[flat_week(int(r["epiweek"]))] = a / (a + b)
            except Exception:                                    # noqa: BLE001
                continue
    t, y, z = [], [], []
    for r in ili:
        try:
            w = int(r["epiweek"])
            v = float(r["ili"])
        except Exception:                                        # noqa: BLE001
            continue
        ft = flat_week(w)
        if ft < FIT_FROM_YEAR - 2000:
            continue
        t.append(ft)
        y.append(v)
        z.append(cli.get(ft, np.nan))
    return np.array(t, float), np.array(y, float), np.array(z, float)


def to_theta(pv: dict) -> dict:
    d = dict(pv)
    d["seed"] = SEED
    return M.unpack(d)


def model_series(th: dict, tmax: float, n_out: int):
    # 用更粗的 max_step（见 MAX_STEP 说明）；只影响积分效率，不影响观测对齐，
    # 因为我们按返回的 t 做插值。
    t, y = M.simulate(th, tmax=tmax, n_out=n_out, max_step=MAX_STEP)
    It, I1, I2 = M.totals(y)
    return t, It * th["rho"] * 100.0, I1 / np.maximum(It, 1e-12)


def residuals(pv: dict, T: np.ndarray, Y: np.ndarray, Z: np.ndarray):
    th = to_theta(pv)
    tmax = float(T.max()) + 1.0
    # ⚠️ 输出点数别设太大：只需覆盖**周频观测**，
    #    每周 2 个点足够线性插值。实测把 n_out 设成 `tmax*4`（≈5552 点）
    #    时单次 SSE 要 **168ms**，60 个起点就 >10 分钟。
    n_out = int(tmax) + 1
    tm, yhat, zhat = model_series(th, tmax, n_out)
    yi = np.interp(T, tm, yhat)
    zi = np.interp(T, tm, zhat)
    ybar = max(float(np.mean(Y)), 1e-9)
    r1 = (yi - Y) / ybar
    m = np.isfinite(Z)
    r2 = (zi[m] - Z[m]) * np.sqrt(LAMBDA_Z)
    return np.concatenate([r1, r2])


def sse(pv_log: np.ndarray, T, Y, Z) -> float:
    pv = {}
    for i, nm in enumerate(FIT_NAMES):
        lo, hi = BOUNDS[nm]
        v = float(np.exp(pv_log[i])) if nm != "theta" else float(pv_log[i])
        pv[nm] = min(max(v, lo), hi)
    try:
        r = residuals(pv, T, Y, Z)
        if not np.all(np.isfinite(r)):
            return 1e12
        return float(np.dot(r, r))
    except Exception:                                            # noqa: BLE001
        return 1e12


def to_log(pv: dict) -> np.ndarray:
    return np.array([np.log(max(pv[nm], 1e-9)) if nm != "theta"
                     else pv[nm] for nm in FIT_NAMES])


def from_log(x: np.ndarray) -> dict:
    pv = {}
    for i, nm in enumerate(FIT_NAMES):
        lo, hi = BOUNDS[nm]
        v = float(x[i]) if nm == "theta" else float(np.exp(x[i]))
        pv[nm] = min(max(v, lo), hi)
    return pv


def multi_start_fit(T, Y, Z, n_start: int = 60, seed: int = 0):
    r"""多起点拟合。

    ⚠️⚠️ **优化器选择是这一节最大的教训**（W46 实测）：

    | 优化器 | 单起点评估次数 | 单起点耗时 | 备注 |
    |---|---|---|---|
    | `Nelder-Mead` / `Powell`（7 维，maxiter=600）| 数千次 | **>20 分钟** | 实测跑 23 分钟连第 1 个起点都没完 |
    | **`L-BFGS-B`**（数值梯度，maxfun=400）| **184 次** | **17 秒** | 快 **34 倍**，SSE 还更低 |

    ⇒ **对"光滑、低维、可数值求导"的目标函数，永远优先梯度法。**
    单纯形法（NM/Powell）在维数 ≥6 时评估次数会爆炸。
    """
    rng = np.random.default_rng(seed)
    base = {"beta0": 1.15, "phi": 1.18, "eps": 0.40, "theta": 4.0,
            "gamma": 1 / 1.8, "omega": 1 / 100.0, "rho": 3.0}
    lo = np.array([np.log(BOUNDS[n][0]) if n != "theta" else BOUNDS[n][0]
                   for n in FIT_NAMES])
    hi = np.array([np.log(BOUNDS[n][1]) if n != "theta" else BOUNDS[n][1]
                   for n in FIT_NAMES])
    best = (np.inf, None)
    t0 = time.time()
    for k in range(n_start):
        if k == 0:
            pv = dict(base)
        else:
            pv = {}
            for nm in FIT_NAMES:
                b_lo, b_hi = BOUNDS[nm]
                v = (base[nm] * float(np.exp(rng.normal(0, 0.6)))
                     if nm != "theta" else float(rng.uniform(0, 52)))
                pv[nm] = min(max(v, b_lo), b_hi)
        r = minimize(sse, to_log(pv), args=(T, Y, Z), method="L-BFGS-B",
                     bounds=list(zip(lo, hi)),
                     options={"maxiter": 200, "maxfun": 800})
        if r.fun < best[0]:
            best = (float(r.fun), from_log(r.x))
        print(f"     起点 {k+1}/{n_start}  SSE {r.fun:>10.2f}  "
              f"最优 {best[0]:>10.2f}  {time.time()-t0:.0f}s", flush=True)
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", action="store_true")
    ap.add_argument("--profile", nargs="?", const="ALL", default=None)
    ap.add_argument("--nstart", type=int, default=60)
    args = ap.parse_args()

    T, Y, Z = load_pairs()
    m = np.isfinite(Z)
    print("=" * 92)
    print("  W46 · Q1 拟合（双亚型季节性模型）")
    print("=" * 92)
    print(f"  拟合窗口：flat t ≥ {FIT_FROM_YEAR-2000} 周（{FIT_FROM_YEAR} 年起）")
    print(f"  ILI 观测 {len(T)} 点（t {T.min():.0f}–{T.max():.0f} 周）")
    print(f"  A 份额观测 {int(m.sum())} 点")
    print(f"  ybar = {Y.mean():.3f}   lambda_z = {LAMBDA_Z}")

    cache = RES / "q1_拟合.json"
    if args.fit or not cache.exists():
        print(f"\n  ── 多起点拟合（{args.nstart} 个起点，Nelder-Mead）──")
        sse_best, pv_best = multi_start_fit(T, Y, Z, args.nstart)
        print(f"\n  最优 SSE = {sse_best:.4f}")
        print(f"  参数：" + "  ".join(f"{k}={v:.4g}" for k, v in pv_best.items()))
        cache.write_text(json.dumps(
            {"sse": sse_best, "params": pv_best, "n_y": len(T),
             "n_z": int(m.sum()), "lambda_z": LAMBDA_Z,
             "fit_from_year": FIT_FROM_YEAR,
             "spinup_years": SPINUP_YEARS},
            ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        d = json.loads(cache.read_text(encoding="utf-8"))
        sse_best, pv_best = d["sse"], d["params"]
        print(f"\n  （复用 {cache.name}，SSE={sse_best:.4f}）")

    # ---- 拟合图 ----
    th = to_theta(pv_best)
    tm, yhat, zhat = model_series(th, float(T.max()) + 1, int(T.max()) * 4)
    fig, ax = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    ax[0].plot(T, Y, "o", ms=2, color="#7f8c8d", label="观测 ILI")
    ax[0].plot(tm, yhat, "-", lw=1.4, color="#c0392b", label="模型")
    ax[0].set_ylabel("ILI 占比 (%)")
    ax[0].legend(fontsize=9)
    ax[0].set_title(f"Q1 拟合（SSE={sse_best:.2f}）", fontsize=13)
    ax[0].grid(alpha=0.3)
    ax[1].plot(T[m], Z[m], "o", ms=2, color="#7f8c8d", label="观测 A 份额")
    ax[1].plot(tm, zhat, "-", lw=1.4, color="#2c6fbb", label="模型")
    ax[1].set_ylabel("A 株份额")
    ax[1].set_xlabel("model t（周，2000 年第 1 周 = 0）")
    ax[1].legend(fontsize=9)
    ax[1].grid(alpha=0.3)
    fig.tight_layout()
    f = FIGS / "q1_拟合.png"
    fig.savefig(f, dpi=150)
    plt.close(fig)
    print(f"  -> {f}")

    # ---- 剖面似然 ----
    if args.profile:
        which = FIT_NAMES if args.profile == "ALL" else [args.profile]
        # 全参数的对数尺度边界（供固定某参数时的约束优化复用）
        lo_all = np.array([np.log(BOUNDS[n][0]) if n != "theta"
                           else BOUNDS[n][0] for n in FIT_NAMES])
        hi_all = np.array([np.log(BOUNDS[n][1]) if n != "theta"
                           else BOUNDS[n][1] for n in FIT_NAMES])
        prof = {}
        for nm in which:
            if nm not in BOUNDS:
                continue
            lo, hi = BOUNDS[nm]
            v0 = pv_best[nm]
            # 在 v0 两侧按几何/线性步长扫
            if nm == "theta":
                grid = np.linspace(lo, hi, 25)
            else:
                grid = np.geomspace(max(lo, v0 / 6), min(hi, v0 * 6), 25)
            xs, ys = [], []
            for v in grid:
                fixed = dict(pv_best)
                fixed[nm] = float(v)
                x0 = to_log(fixed)
                # 固定该参数：用大权重惩罚偏离
                def obj(x, _nm=nm, _v=float(v)):
                    pv = from_log(x)
                    pen = ((pv[_nm] - _v) / max(abs(_v), 1e-6)) ** 2 * 1e6
                    return sse(x, T, Y, Z) + pen
                # 同 multi_start_fit：梯度法比单纯形法快一个数量级
                r = minimize(obj, x0, method="L-BFGS-B",
                             bounds=list(zip(lo_all, hi_all)),
                             options={"maxiter": 300, "maxfun": 900})
                xs.append(float(v))
                ys.append(float(sse(r.x, T, Y, Z)))
            prof[nm] = {"grid": xs, "sse": ys, "best": v0,
                        "delta": float(np.min(ys) - sse_best)}
            # 判据：剖面能否在两侧越过 Δ
            arr = np.array(ys) - sse_best
            below = arr < CHI2_1_95
            idx = np.where(below)[0]
            if len(idx) == 0:
                lo_ci = hi_ci = v0
            else:
                lo_ci, hi_ci = xs[idx[0]], xs[idx[-1]]
            left_bounded = (idx.size and idx[0] > 0)
            right_bounded = (idx.size and idx[-1] < len(xs) - 1)
            prof[nm].update({"ci": [lo_ci, hi_ci],
                             "left_bounded": bool(left_bounded),
                             "right_bounded": bool(right_bounded),
                             "identifiable": bool(left_bounded and right_bounded)})
            print(f"\n  ── 剖面 {nm} ──  最优 {v0:.4g}")
            print(f"     95% 区间 [{lo_ci:.4g}, {hi_ci:.4g}]")
            print(f"     两侧有界: 左 {left_bounded}  右 {right_bounded}"
                  f"  ⇒ {'可辨识' if (left_bounded and right_bounded) else '**不可辨识**'}")
        (RES / "q1_剖面.json").write_text(
            json.dumps(prof, ensure_ascii=False, indent=2), encoding="utf-8")
        # 剖面图
        n = len(prof)
        fig, axes = plt.subplots(1, n, figsize=(3.2 * n, 3.6))
        if n == 1:
            axes = [axes]
        for ax, (nm, d) in zip(axes, prof.items()):
            ax.plot(d["grid"], np.array(d["sse"]) - sse_best, "-o", ms=3)
            ax.axhline(CHI2_1_95, ls="--", color="r", lw=1)
            ax.axvline(d["best"], ls=":", color="k", lw=1)
            ax.set_title(f"{nm}\n{'可辨识' if d['identifiable'] else '不可辨识'}",
                         fontsize=10)
            ax.set_xlabel(nm)
            ax.grid(alpha=0.3)
        axes[0].set_ylabel(r"$R^\star-R^\star_{\min}$")
        fig.tight_layout()
        f2 = FIGS / "q1_剖面.png"
        fig.savefig(f2, dpi=150)
        plt.close(fig)
        print(f"\n  -> {f2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
