#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · Q3：用粒子滤波估计时变传播力 $R_t$。

## 选题要求（01_题目.md 问题 3）

1. 建立**状态空间模型**：观测方程 + 状态演化方程；
2. 用**粒子滤波**在线估计 $R_t$，给出**逐周区间**；
3. 说明如何处理**口径断点**（2020–2022）；
   **并演示**直接跨越会得到什么错误结论；
4. 用**两套方法互相验证**，报告分歧最大的周并分析原因。

## 模型

### 状态演化（$R_t$ 在对数尺度上做随机游走）

$$\log R_t=\log R_{t-1}+\eta_t,\qquad \eta_t\sim N(0,\sigma_\eta^2)$$

### 观测（Wallinga–Lipsitch 型的世代时间近似）

用**感染更新方程**把 $R_t$ 与观测病例数联系起来：

$$y_t\;\propto\;\mu_t=R_t\sum_{s\ge1}w_s\,y_{t-s},\qquad w_s=\text{世代时间分布}$$

本报告取**离散伽马型世代时间**（均值 2.9 周、标准差 1.5 周 —— 与 Q1 固定的
$1/\gamma=2.9$ 周一致，保证两问可比）。

> **为什么用这个观测方程而不是直接套 SIR**：
> $R_t$ 的**定义**就是"一个病例在其感染期内产生的二代病例数"，
> 更新方程是它的直接实现，不需要假设人群混合结构，
> 因此在"只看数据估传播力"这个任务上比 ODE 更稳健。

### 粒子滤波（SIR 重采样，系统重采样法）

* $N_p$ 个粒子，每个携带 $\log R_t$；
* 权重 $\propto N(y_t\,|\,c\,\mu_t,\sigma_{obs}^2)$；
* 有效样本数 $N_{eff}<N_p/2$ 时做**系统重采样**；
* 输出**加权分位数**作为逐周区间。

## 三件事

1. 在长序列上估 $R_t$ 并给区间；
2. **口径断点演示**：一段脚本"故意不处理"断点，展示 $R_t$ 的假尖峰；
3. **方法互验**：与"滑动窗口 EpiEstim 型"估计对照，找分歧最大的周。

用法：
    $PY q3_rt_filter.py
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

# 世代时间（与 Q1 的 1/gamma = 2.9 周一致）
GT_MEAN, GT_SD, GT_MAX = 2.9, 1.5, 10
SIGMA_ETA = 0.12          # log R 每周随机游走步长
NPART = 3000
SEED = 20260929


def flat_week(w: int) -> int:
    return (w // 100 - 2000) * 52 + (w % 100 - 1)


def load_ili():
    with open(CLEAN / "ili_weekly.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    wk = np.array([int(r["epiweek"]) for r in rows])
    y = np.array([float(r["ili"]) for r in rows])
    return wk, y


def gt_weights(mean=GT_MEAN, sd=GT_SD, kmax=GT_MAX):
    r"""离散伽马型世代时间分布（归一化到和为 1）。"""
    from scipy.stats import gamma as gdist
    k = np.arange(1, kmax + 1)
    shape = (mean / sd) ** 2
    scale = sd ** 2 / mean
    w = gdist.pdf(k, shape, scale=scale)
    return w / w.sum()


def particle_filter(y, w, sigma_eta=SIGMA_ETA, npart=NPART, seed=SEED,
                    logR0=0.0, sigma_obs=None):
    r"""返回 (logR 后验分位数, 预测均值, Neff 序列)。

    状态：$\log R_t$；观测：$y_t = c\,\mu_t + \varepsilon$，
    $\mu_t=R_t\sum_s w_s y_{t-s}$，其中 $c$ 为尺度（用 $y$ 的量级设定）。
    """
    rng = np.random.default_rng(seed)
    n = len(y)
    if sigma_obs is None:
        sigma_obs = max(float(np.std(y)) * 0.5, 1e-6)
    # 尺度 c：使预测与观测同量级（用前半段的均值比）
    k = len(w)
    # 前 k 个点没有完整历史：用其自身作初始化
    yhist = np.concatenate([np.full(k, y[:k].mean()), y])
    c = 1.0                    # mu 已经用 y 的历史构造，故 c=1

    logR = np.full(npart, logR0) + rng.normal(0, sigma_eta, npart)
    wts = np.full(npart, 1.0 / npart)
    qs = np.zeros((3, n))
    pred = np.zeros(n)
    neff_s = np.zeros(n)

    for t in range(n):
        # 演化
        logR = logR + rng.normal(0, sigma_eta, npart)
        # 观测预测：用**平滑过的历史**避免用当前观测
        hist = yhist[t + k - 1::-1][:k] if t + k - 1 >= k - 1 else \
            np.full(k, y[:max(t, 1)].mean())
        if len(hist) < k:
            hist = np.concatenate([hist, np.full(k - len(hist), hist.mean())])
        R = np.exp(logR)
        mu = R * float(np.dot(w, hist))
        mu = np.maximum(mu, 1e-9)
        # 权重
        ll = -0.5 * ((y[t] - c * mu) / sigma_obs) ** 2
        ll -= ll.max()
        wts = wts * np.exp(ll)
        s = wts.sum()
        if not np.isfinite(s) or s <= 0:
            wts = np.full(npart, 1.0 / npart)
        else:
            wts /= s
        neff = 1.0 / float((wts ** 2).sum())
        neff_s[t] = neff
        # 加权分位数
        order = np.argsort(logR)
        lr, ww = logR[order], wts[order]
        cw = np.cumsum(ww)
        qs[:, t] = np.interp([0.025, 0.5, 0.975], cw, lr)
        pred[t] = float(np.dot(wts, c * mu))
        # 系统重采样
        if neff < npart / 2:
            pos = (rng.random() + np.arange(npart)) / npart
            idx = np.searchsorted(cw, pos)
            idx = np.clip(idx, 0, npart - 1)
            logR = logR[order][idx]
            wts = np.full(npart, 1.0 / npart)
    return qs, pred, neff_s


def sliding_window_rt(y, w, win=5, lam=1.0):
    r"""滑动窗口 EpiEstim 型估计（**互为验证的第二套方法**）。

    $\hat R_t=\dfrac{\sum_{s=t-win+1}^{t}y_s}
    {\sum_{s=t-win+1}^{t}\sum_{u}w_u\,y_{s-u}}$（加 $\lambda$ 平滑）
    """
    n = len(y)
    k = len(w)
    out = np.full(n, np.nan)
    for t in range(n):
        a = max(0, t - win + 1)
        num = float(y[a:t + 1].sum()) + lam
        den = 0.0
        for s in range(a, t + 1):
            acc = 0.0
            for u in range(k):
                j = s - (u + 1)
                acc += w[u] * (y[j] if j >= 0 else y[:max(j + 1, 1)].mean())
            den += acc
        out[t] = num / max(den + lam, 1e-9)
    return out


def main() -> int:
    print("=" * 94)
    print("  W46 · Q3 粒子滤波估计 R_t")
    print("=" * 94)
    wk, y = load_ili()
    w = gt_weights()
    print(f"  世代时间：均值 {GT_MEAN} 周、SD {GT_SD}、截断 {GT_MAX} 周")
    print(f"    权重 " + ", ".join(f"{v:.3f}" for v in w))
    print(f"  粒子数 {NPART}，log R 随机游走步长 {SIGMA_ETA}")
    rep: dict = {}

    # ---- 全序列（**故意不处理断点**）----
    print(f"\n  ── 方法一：粒子滤波（全序列，不处理断点）──")
    qs_all, pred_all, neff_all = particle_filter(y, w)
    Rt_med = np.exp(qs_all[1])
    Rt_lo = np.exp(qs_all[0])
    Rt_hi = np.exp(qs_all[2])
    print(f"     Neff 中位数 {np.median(neff_all):.0f} / {NPART}")
    print(f"     R_t 中位数范围 {Rt_med.min():.2f} ~ {Rt_med.max():.2f}")

    # ---- 分段处理（**正确处理**）----
    print(f"\n  ── 方法一（分段）：按口径分段后分别滤波 ──")
    segs = [(2000, 2019), (2020, 2022), (2023, 2026)]
    seg_res = {}
    for y0, y1 in segs:
        m = (wk // 100 >= y0) & (wk // 100 <= y1)
        if m.sum() < 20:
            continue
        q, p, ne = particle_filter(y[m], w, seed=SEED + y0)
        Rm = np.exp(q[1])
        seg_res[f"{y0}-{y1}"] = {"n": int(m.sum()),
                                 "R_median": float(np.median(Rm)),
                                 "R_max": float(Rm.max()),
                                 "R_p2.5": float(np.percentile(Rm, 2.5)),
                                 "R_p97.5": float(np.percentile(Rm, 97.5))}
        print(f"     {y0}–{y1}  n={int(m.sum()):>4}  中位 R {np.median(Rm):.3f}"
              f"  最大 {Rm.max():.3f}")

    # ---- ★ 断点危害演示 ----
    print(f"\n  ══ 口径断点演示（选题第 3 小问）══")
    # 在 2020 前后各取 40 周，把"跨断点"与"分段"的做法对照
    pre = (wk // 100 >= 2018) & (wk // 100 <= 2019)
    post = (wk // 100 >= 2020) & (wk // 100 <= 2021)
    straddle = pre | post
    idx = np.where(straddle)[0]
    y2 = y[idx]
    w2 = wk[idx]
    q_st, _, _ = particle_filter(y2, w, seed=SEED + 99)
    R_st = np.exp(q_st[1])
    # 分段各半，再拼回同一时间轴
    npre = int(pre.sum())
    q_a, _, _ = particle_filter(y2[:npre], w, seed=SEED + 1)
    q_b, _, _ = particle_filter(y2[npre:], w, seed=SEED + 2)
    R_seg = np.concatenate([np.exp(q_a[1]), np.exp(q_b[1])])
    # 用"跨断点连续滤波"与"分段滤波"的差，量化假尖峰
    diff = np.abs(R_st - R_seg)
    j = int(np.argmax(diff))
    print(f"     窗口 {w2[0]}–{w2[-1]}（{len(y2)} 周，跨越 2020 断点）")
    print(f"     跨断点连续滤波 R 中位 {np.median(R_st):.3f}")
    print(f"     分段滤波       R 中位 {np.median(R_seg):.3f}")
    print(f"     **最大偏差 {diff.max():.3f} 出现在 {w2[j]}**"
          f"（跨 {R_st[j]:.3f} vs 分段 {R_seg[j]:.3f}）")
    print(f"     => 不处理断点会在此处产生**假尖峰**，幅度 "
          f"{diff.max()/max(np.median(R_seg),1e-9)*100:.0f}%")
    rep["breakpoint_demo"] = {
        "window": [int(w2[0]), int(w2[-1])], "n": int(len(y2)),
        "R_straddle_median": float(np.median(R_st)),
        "R_segment_median": float(np.median(R_seg)),
        "max_abs_diff": float(diff.max()),
        "max_diff_week": int(w2[j]),
        "R_straddle_at_max": float(R_st[j]),
        "R_segment_at_max": float(R_seg[j])}

    # ---- 方法二互验 ----
    print(f"\n  ══ 方法互验（选题第 4 小问）══")
    Rt_sw = sliding_window_rt(y, w, win=5)
    m = np.isfinite(Rt_sw) & np.isfinite(Rt_med)
    # 分位数归一化后比较（两者尺度定义略不同）
    x1 = Rt_med[m] / np.median(Rt_med[m])
    x2 = Rt_sw[m] / np.median(Rt_sw[m])
    r = float(np.corrcoef(x1, x2)[0, 1])
    print(f"     滑动窗口法 R 中位 {np.median(Rt_sw[m]):.3f}")
    print(f"     两法（归一化后）相关系数 r = {r:.3f}")
    dd = np.abs(x1 - x2)
    kk = np.argsort(-dd)[:5]
    idxm = np.where(m)[0]
    print(f"     分歧最大的 5 周：")
    for k in kk:
        t = idxm[k]
        print(f"        {wk[t]}  粒子滤波 {Rt_med[t]:.3f}  "
              f"滑动窗口 {Rt_sw[t]:.3f}  相对差 {dd[k]:.3f}")
    rep["cross_validation"] = {
        "corr": r, "n": int(m.sum()),
        "divergent_weeks": [[int(wk[idxm[k]]), float(Rt_med[idxm[k]]),
                             float(Rt_sw[idxm[k]])] for k in kk]}

    # ---- 关注窗口（2026 起爆段）----
    sel = (wk // 100 == 2026) & (wk % 100 >= 20) & (wk % 100 <= 38)
    ii = np.where(sel)[0]
    print(f"\n  ══ 关注窗口 2026 W20–38 的 R_t ══")
    print(f"     {'周':>5}{'ili':>8}{'R中位':>9}{'95%区间':>18}")
    for t in ii:
        print(f"     {wk[t] % 100:>5}{y[t]:>8.2f}{Rt_med[t]:>9.3f}"
              f"{f'({Rt_lo[t]:.2f},{Rt_hi[t]:.2f})':>18}")
    rep["window_2026"] = {
        "weeks": [int(wk[t] % 100) for t in ii],
        "ili": [float(y[t]) for t in ii],
        "R_median": [float(Rt_med[t]) for t in ii],
        "R_lo": [float(Rt_lo[t]) for t in ii],
        "R_hi": [float(Rt_hi[t]) for t in ii]}

    # ---- 图 ----
    fig, ax = plt.subplots(3, 1, figsize=(13, 10))
    yv = wk // 100 + (wk % 100) / 52.0
    ax[0].plot(yv, y, "-", lw=0.8, color="#7f8c8d")
    for y0, y1, c2 in ((2000, 2019, "#95a5a6"), (2020, 2022, "#e74c3c"),
                       (2023, 2026, "#27ae60")):
        ax[0].axvspan(y0, y1 + 1, color=c2, alpha=0.10)
    ax[0].set_ylabel("ili (%)")
    ax[0].set_title("Q3 时变传播力 $R_t$ 的粒子滤波估计", fontsize=13)
    ax[0].grid(alpha=0.3)
    ax[1].fill_between(yv, Rt_lo, Rt_hi, color="#2c6fbb", alpha=0.25,
                       label="95% 区间")
    ax[1].plot(yv, Rt_med, "-", lw=1.0, color="#2c6fbb", label="后验中位")
    ax[1].axhline(1.0, ls="--", color="k", lw=1)
    ax[1].set_ylabel("$R_t$")
    ax[1].legend(fontsize=8)
    ax[1].grid(alpha=0.3)
    ax[2].plot(yv[m], x1, "-", lw=0.8, color="#2c6fbb", label="粒子滤波")
    ax[2].plot(yv[m], x2, "-", lw=0.8, color="#e67e22", label="滑动窗口")
    ax[2].set_ylabel("归一化 $R_t$")
    ax[2].set_xlabel("年")
    ax[2].legend(fontsize=8)
    ax[2].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "q3_Rt.png", dpi=150)
    plt.close(fig)
    print(f"\n  -> {FIGS/'q3_Rt.png'}")

    rep["segments"] = seg_res
    rep["config"] = {"GT_MEAN": GT_MEAN, "GT_SD": GT_SD, "GT_MAX": GT_MAX,
                     "SIGMA_ETA": SIGMA_ETA, "NPART": NPART, "SEED": SEED}
    (RES / "q3_Rt.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  -> {RES/'q3_Rt.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
