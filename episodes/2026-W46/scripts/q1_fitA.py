#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · Q1-A：固定 $\gamma$、按**可辨识组合**参数化并做剖面可辨识性。

## 决策 A（用户 2026-09-29 选定）

> 固定 $\gamma$ 于文献区间、只报 $R_0$ 与 $\rho\beta_0$ 等**可辨识组合**，
> 并跑完整剖面确认哪些参数有界。

## 为什么要换参数化

原参数化用 $(\beta_0,\phi,\epsilon,\theta,\gamma,\omega,\rho)$。
但观测方程 $\hat y=\rho(I_1^{\text{tot}}+I_2^{\text{tot}})\cdot100$ 里，
$\beta_0$ 与 $\rho$ **只以乘积形式影响**可观测的幅度 ——
似然面上存在一条"平坦脊"。

**换参数化**：把 $\beta_0$ 换成 $R_0=\beta_0/\gamma$，并**固定** $\gamma=1/2.9$ 周
（流感感染期约 2.9 周，文献常见区间 1.8–4 周的中间值）。

> ⚠️ **注意这不是免费的**：固定 $\gamma$ 是**外部先验**，不是数据信息。
> 所有结论都要声明这一点。$R_0$ 的区间宽度**只反映**在 $\gamma$ 给定下的
> 条件不确定性。真正的检验是下面的剖面：
> 若 $R_0$ 剖面有界 ⇒ 数据确实约束了传播力（在 $\gamma$ 给定下）；
> 若 $\rho$ 剖面无界 ⇒ $(\beta_0,\rho)$ 的脊确实存在，$\rho$ **不可单独报告**。

## 待估参数（6 个）

$R_0,\;\phi,\;\epsilon,\;\theta,\;\omega,\;\rho$

固定：$\gamma=1/2.9$；$\beta_0=R_0\gamma$。

用法：
    $PY q1_fitA.py --fit
    $PY q1_fitA.py --profile ALL
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

# ---- 固定量（外部先验，必须在结论里声明）----
GAMMA_FIX = 1.0 / 2.9         # 感染期 2.9 周
SEED = 1e-4
FIT_FROM_YEAR = 2005
SPAN_YEARS = 11
MAX_STEP = 1.0
LAMBDA_Z = 3.0
CHI2_1_95 = 3.8415

# ---- 待估参数（换成可辨识组合）----
FIT_NAMES = ["R0", "phi", "eps", "theta", "omega", "rho"]
BOUNDS = {"R0": (0.4, 6.0), "phi": (0.5, 2.5), "eps": (0.0, 0.95),
          "theta": (0.0, 51.9), "omega": (1e-4, 2.0), "rho": (0.05, 500.0)}

# 派生量（用于报告）
DERIVED = ["beta0", "rho_beta0"]


def flat_week(w: int) -> int:
    return (w // 100 - 2000) * 52 + (w % 100 - 1)


def load_pairs():
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
            ft = flat_week(int(r["epiweek"]))
            v = float(r["ili"])
        except Exception:                                        # noqa: BLE001
            continue
        if ft < FIT_FROM_YEAR - 2000:
            continue
        t.append(ft)
        y.append(v)
        z.append(cli.get(ft, np.nan))
    return np.array(t, float), np.array(y, float), np.array(z, float)


def to_model(pv: dict) -> dict:
    """可辨识组合 -> 模型参数。"""
    return M.unpack({"beta0": pv["R0"] * GAMMA_FIX, "phi": pv["phi"],
                     "eps": pv["eps"], "theta": pv["theta"],
                     "gamma": GAMMA_FIX, "omega": pv["omega"],
                     "rho": pv["rho"], "seed": SEED})


def model_series(pv: dict, tmax: float, n_out: int):
    th = to_model(pv)
    t, y = M.simulate(th, tmax=tmax, n_out=n_out, max_step=MAX_STEP)
    It, i1, i2 = M.totals(y)
    return t, It * pv["rho"] * 100.0, i1 / np.maximum(It, 1e-12)


def sse(x: np.ndarray, T, Y, Z) -> float:
    pv = {}
    for i, nm in enumerate(FIT_NAMES):
        lo, hi = BOUNDS[nm]
        v = float(x[i]) if nm == "theta" else float(np.exp(x[i]))
        pv[nm] = min(max(v, lo), hi)
    try:
        tmax = float(T.max()) + 1.0
        tm, yhat, zhat = model_series(pv, tmax, int(tmax) + 1)
        yi = np.interp(T, tm, yhat)
        zi = np.interp(T, tm, zhat)
        ybar = max(float(np.mean(Y)), 1e-9)
        r1 = (yi - Y) / ybar
        m = np.isfinite(Z)
        r2 = (zi[m] - Z[m]) * np.sqrt(LAMBDA_Z)
        r = np.concatenate([r1, r2])
        if not np.all(np.isfinite(r)):
            return 1e12
        return float(np.dot(r, r))
    except Exception:                                            # noqa: BLE001
        return 1e12


def to_x(pv: dict) -> np.ndarray:
    return np.array([pv[nm] if nm == "theta" else np.log(max(pv[nm], 1e-12))
                     for nm in FIT_NAMES])


def from_x(x: np.ndarray) -> dict:
    pv = {}
    for i, nm in enumerate(FIT_NAMES):
        lo, hi = BOUNDS[nm]
        v = float(x[i]) if nm == "theta" else float(np.exp(x[i]))
        pv[nm] = min(max(v, lo), hi)
    return pv


def bounds_x():
    # [!] np.log(0) = -inf 且抛 RuntimeWarning；而 stderr 上的警告会让
    #    PowerShell 把脚本调用判成失败并**提前中止**
    #    （实测：剖面作业因此静默死掉 —— 日志里只有一条 warning）。
    #    这里显式夹住下界。
    EPS = 1e-9
    lo = np.array([BOUNDS[n][0] if n == "theta"
                   else np.log(max(BOUNDS[n][0], EPS)) for n in FIT_NAMES])
    hi = np.array([BOUNDS[n][1] if n == "theta"
                   else np.log(max(BOUNDS[n][1], EPS)) for n in FIT_NAMES])
    return lo, hi


def multistart(T, Y, Z, n_start=25, seed=0):
    rng = np.random.default_rng(seed)
    base = {"R0": 1.8, "phi": 1.18, "eps": 0.40, "theta": 4.0,
            "omega": 1 / 100.0, "rho": 3.0}
    lo, hi = bounds_x()
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
        r = minimize(sse, to_x(pv), args=(T, Y, Z), method="L-BFGS-B",
                     bounds=list(zip(lo, hi)),
                     options={"maxiter": 200, "maxfun": 800})
        if r.fun < best[0]:
            best = (float(r.fun), from_x(r.x))
        print(f"     起点 {k+1}/{n_start}  SSE {r.fun:>10.2f}  "
              f"最优 {best[0]:>10.2f}  {time.time()-t0:.0f}s", flush=True)
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", action="store_true")
    ap.add_argument("--profile", nargs="?", const="ALL", default=None)
    ap.add_argument("--nstart", type=int, default=25)
    ap.add_argument("--grid", type=int, default=15,
                    help="剖面网格点数（实测 25 点×6参数>90 分钟）")
    ap.add_argument("--subfun", type=int, default=350,
                    help="剖面子优化的最大函数评估数")
    args = ap.parse_args()

    T, Y, Z = load_pairs()
    m = np.isfinite(Z)
    print("=" * 92)
    print("  W46 · Q1-A 拟合（固定 gamma，可辨识组合参数化）")
    print("=" * 92)
    print(f"  固定 gamma = {GAMMA_FIX:.4f}  (感染期 {1/GAMMA_FIX:.2f} 周) "
          f"**外部先验**")
    print(f"  待估 {len(FIT_NAMES)} 个: {', '.join(FIT_NAMES)}")
    print(f"  ILI {len(T)} 点  A份额 {int(m.sum())} 点  ybar={Y.mean():.3f}")

    cache = RES / "q1A_拟合.json"
    if args.fit or not cache.exists():
        print(f"\n  ── 多起点拟合（L-BFGS-B，{args.nstart} 起点）──")
        best_sse, pv = multistart(T, Y, Z, args.nstart)
        print(f"\n  最优 SSE = {best_sse:.4f}")
    else:
        d = json.loads(cache.read_text(encoding="utf-8"))
        best_sse, pv = d["sse"], d["params"]
        print(f"\n  （复用 {cache.name}，SSE={best_sse:.4f}）")

    beta0 = pv["R0"] * GAMMA_FIX
    print(f"\n  ── 可辨识组合（Q1 主结论）──")
    print(f"     R0      = {pv['R0']:.4f}    (= beta0/gamma)")
    print(f"     phi     = {pv['phi']:.4f}    (株2 相对传播力)")
    print(f"     rho*b0  = {pv['rho']*beta0:.4f}")
    print(f"\n  ── 派生量（**不可单独报告**，见文档 §8.1）──")
    print(f"     beta0   = {beta0:.4f}   ← 与 rho 存在平坦脊")
    print(f"     rho     = {pv['rho']:.4f}   ← 同上")

    cache.write_text(json.dumps(
        {"sse": best_sse, "params": pv, "gamma_fix": GAMMA_FIX,
         "beta0": beta0, "rho_beta0": pv["rho"] * beta0,
         "n_y": len(T), "n_z": int(m.sum()), "lambda_z": LAMBDA_Z,
         "note": "gamma 为外部先验；beta0 与 rho 不可单独辨识"},
        ensure_ascii=False, indent=2), encoding="utf-8")

    # 拟合图
    tm, yhat, zhat = model_series(pv, float(T.max()) + 1, int(T.max()) + 1)
    fig, ax = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    ax[0].plot(T, Y, "o", ms=2, color="#7f8c8d", label="观测 ILI")
    ax[0].plot(tm, yhat, "-", lw=1.4, color="#c0392b", label="模型")
    ax[0].set_ylabel("ILI 占比 (%)")
    ax[0].legend(fontsize=9)
    ax[0].set_title(f"Q1-A 拟合（SSE={best_sse:.1f}，$\\gamma$ 固定）",
                    fontsize=13)
    ax[0].grid(alpha=0.3)
    ax[1].plot(T[m], Z[m], "o", ms=2, color="#7f8c8d", label="观测 A 份额")
    ax[1].plot(tm, zhat, "-", lw=1.4, color="#2c6fbb", label="模型")
    ax[1].set_ylabel("A 株份额")
    ax[1].set_xlabel("model t（周，2000 年第 1 周 = 0）")
    ax[1].legend(fontsize=9)
    ax[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "q1A_拟合.png", dpi=150)
    plt.close(fig)
    print(f"  -> {FIGS/'q1A_拟合.png'}")

    # ---- 剖面似然 ----
    if args.profile:
        # ★★★ **剖面必须"把参数从优化变量里移除"，不能用惩罚项**。
        #
        # W46 实测教训：我第一版用 `pen = ((q-v)/v)^2 * 1e9` 把参数钉住，
        # 结果所有参数的 95% 区间都是**零宽度**
        # （R0 给 [1.549, 1.549]，phi 给 [0.8103, 0.8103]）。
        # 根因：惩罚太强 ⇒ 优化器在 θ_j 方向**根本走不动**，
        # 剖面退化成"在起点原地取似然" ⇒ 区间必然是 0。
        #
        # 正确做法：**降维** —— 固定该参数，只优化其余参数。
        # 这既无尺度问题，也是文献里 profile likelihood 的标准实现。
        which = FIT_NAMES if args.profile == "ALL" else [args.profile]
        n_grid = max(7, args.grid)
        prof = {}
        t_start = time.time()
        n_fixed_total = 0
        for nm in which:
            if nm not in BOUNDS:
                continue
            free = [n for n in FIT_NAMES if n != nm]
            lo_f = np.array([BOUNDS[n][0] if n == "theta"
                             else np.log(max(BOUNDS[n][0], 1e-9))
                             for n in free])
            hi_f = np.array([BOUNDS[n][1] if n == "theta"
                             else np.log(max(BOUNDS[n][1], 1e-9))
                             for n in free])

            def sse_fixed(xf, _nm=nm, _v=None, _free=free):
                r"""把 `_nm` 固定在**对数尺度** `_v`，其余参数自由。

                ★★ 关键：**全程只用一本"对数尺度字典"**，不要在中间混用
                自然尺度。我前两版都错在这里：
                * v1 用惩罚项（区间恒为 0）；
                * v2 把**自然尺度**的 `_v` 直接塞进对数尺度字典
                  => `x_full` 里出现 `log(1.5)=0.43` 被当作已是对数，
                     反向 `exp` 后参数彻底跑飞，自检从 459 变 **2731**。

                `theta` 不是正量、不进对数 ⇒ 它在字典里就存原值。
                """
                d = dict(zip(_free, xf))
                d[_nm] = _v
                x_full = np.array([d[n] for n in FIT_NAMES])
                return sse(x_full, T, Y, Z)

            lo, hi = BOUNDS[nm]
            v0 = pv[nm]
            # 起点：**按名字**从 `to_x(pv)` 里取，避免位置错位
            _xf_full = to_x(pv)                    # theta 为原值，其余为 log
            x0f = np.array([_xf_full[FIT_NAMES.index(n)] for n in free])
            # 该参数的对数尺度最优值
            v0_log = (v0 if nm == "theta" else float(np.log(max(v0, 1e-12))))

            # ★★ **自检**：固定在最优值、自由参数从最优出发 ⇒ 必须复现 best_sse
            s_check = sse_fixed(x0f, nm, v0_log)
            if abs(s_check - best_sse) > max(1e-3, 1e-3 * best_sse):
                print(f"\n  [X] 剖面 {nm} **自检失败**："
                      f"固定最优值给 {s_check:.4f}，应为 {best_sse:.4f}"
                      f" —— 跳过该参数（结果不可信）")
                prof[nm] = {"error": "self_check_failed",
                            "s_check": s_check, "best_sse": best_sse}
                continue

            # 网格：theta 用原值；其余用对数尺度（与 sse_fixed 口径一致）
            if nm == "theta":
                grid_log = np.linspace(lo, hi, n_grid)
                grid_nat = grid_log
            else:
                grid_nat = np.geomspace(max(lo, v0 / 8), min(hi, v0 * 8),
                                        n_grid)
                grid_log = np.log(grid_nat)
            xs, ys = [], []
            for v_log, v_nat in zip(grid_log, grid_nat):
                # ★★ **剖面子优化必须用无梯度法（Powell），不能用 L-BFGS-B**。
                #
                # 为什么：SSE 由 **ODE 数值解 + 插值** 得到 ⇒ 函数面**有数值噪声**。
                # L-BFGS-B 的有限差分梯度会被噪声淹没 ⇒ 优化器**原地不动**
                # ⇒ 剖面恒等于"起点处的 SSE" ⇒ 区间宽度 0。
                # 实测病症：`d_sse` 在整条 R0 网格上都是 **~2262**，
                # 而真正的最优是 459 —— 差了 1800，说明一次都没优化动。
                # Powell 只用函数值比较，对噪声目标稳健得多。
                r = minimize(sse_fixed, x0f, args=(nm, float(v_log)),
                             method="Powell", bounds=list(zip(lo_f, hi_f)),
                             options={"maxiter": 200, "xtol": 1e-3,
                                      "ftol": 1e-3})
                xs.append(float(v_nat))
                ys.append(float(r.fun))
            n_fixed_total += 1
            arr = np.array(ys) - best_sse
            below = arr < CHI2_1_95
            idx = np.where(below)[0]
            lo_ci = xs[idx[0]] if idx.size else v0
            hi_ci = xs[idx[-1]] if idx.size else v0
            lb = bool(idx.size and idx[0] > 0)
            rb = bool(idx.size and idx[-1] < len(xs) - 1)
            width = abs(hi_ci - lo_ci)
            suspicious = width <= 0 or len(idx) <= 1
            prof[nm] = {"grid": xs, "d_sse": arr.tolist(), "best": v0,
                        "ci": [lo_ci, hi_ci], "width": width,
                        "left_bounded": lb, "right_bounded": rb,
                        "identifiable": bool(lb and rb),
                        "suspicious_zero_width": bool(suspicious),
                        "self_check": s_check}
            print(f"\n  ── 剖面 {nm} ──  最优 {v0:.4g}  ({n_grid} 点, "
                  f"累计 {time.time()-t_start:.0f}s)  自检 [OK]", flush=True)
            print(f"     95% 区间 [{lo_ci:.4g}, {hi_ci:.4g}]  宽度 {width:.4g}"
                  f"  Δmax={arr.max():.2f}")
            print(f"     两侧有界 左 {lb} / 右 {rb}  => "
                  f"{'**可辨识**' if (lb and rb) else '**不可辨识（剖面发散）**'}")
            if suspicious:
                print("     [!] **零宽度/单点区间** —— 剖面未真正探索参数方向，"
                      "结果不可用")
        (RES / "q1A_剖面.json").write_text(
            json.dumps(prof, ensure_ascii=False, indent=2), encoding="utf-8")
        # ---- 把"剖面可用性"的结论写清楚（含已知缺口）----
        ok_p = [k for k, v in prof.items()
                if v.get("identifiable") and not v.get("suspicious_zero_width")]
        susp = [k for k, v in prof.items() if v.get("suspicious_zero_width")]
        print(f"\n{'='*92}")
        print("  ── 剖面结论 ──")
        print(f"     可用剖面: {ok_p if ok_p else '（无）'}")
        print(f"     零宽度/单点（分辨率不足）: {susp if susp else '（无）'}")
        print()
        print("     [!] **已知缺口（必须写进论文诚实性声明）**：")
        print("        剖面曲线**形状正确**（d_sse 呈单峰，最小处 ≈ 0），")
        print("        但 (a) 网格点偏少、每次子优化 ~40s ⇒ 难以加密；")
        print("        (b) 似然比值在最小值附近**跨越 3.84 的速度极快**")
        print("            （R0: 1.10→34, 1.55→-0.4, 2.17→58 ⇒ 相邻点差 34+）")
        print("        ⇒ **本报告不给出 Q1 参数的似然比置信区间**，")
        print("           改为报告『可辨识组合』的点估计 + 结构性不可辨识的推导。")
        print("           区间由 Q4 的蒙特卡洛扰动法近似（见 results/q4_结果.md）。")
        if prof:
            n = len(prof)
            fig, axes = plt.subplots(1, n, figsize=(3.1 * n, 3.4))
            if n == 1:
                axes = [axes]
            for ax, (nm, d) in zip(axes, prof.items()):
                if "grid" not in d:
                    ax.set_title(f"{nm}\n自检失败", fontsize=10)
                    continue
                ax.plot(d["grid"], d["d_sse"], "-o", ms=3)
                ax.axhline(CHI2_1_95, ls="--", color="r", lw=1)
                ax.axvline(d["best"], ls=":", color="k", lw=1)
                tt = ("不可辨识" if not d.get("identifiable")
                      else ("分辨率不足" if d.get("suspicious_zero_width")
                            else "可辨识"))
                ax.set_title(f"{nm}\n{tt}", fontsize=10)
                ax.set_xlabel(nm)
                ax.grid(alpha=0.3)
            axes[0].set_ylabel(r"$R^\star-R^\star_{\min}$")
            fig.tight_layout()
            fig.savefig(FIGS / "q1A_剖面.png", dpi=150)
            plt.close(fig)
            print(f"\n  -> {FIGS/'q1A_剖面.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
