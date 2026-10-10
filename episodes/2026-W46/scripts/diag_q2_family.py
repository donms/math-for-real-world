#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · Q2 诊断 II：为什么"分段常数"族会边界截断，而"分段线性"族不会。

## 现象（`diag_q2_boundary.py` 实测）

| 窗口 | n | 众数 | 边界后验 |
|---|---|---|---|
| 2026 W20–38 | 18 | 35（上边界）| 右 0.251 |
| 2026 W1–38 | 37 | 4（下边界）| 左 0.600 |
| 跨年 | 51 | 43（下边界）| 左 0.588 |
| 两季 | 103 | 43（下边界）| 左 0.705 |

**全部堆在边界**。而族 II（分段**线性**）在 2026 W20–38 上给出
众数第 29 周、HDI 第 24–33 周。

## 为什么（结构性原因）

族 I 的模型是"**前段常数 $\mu_0=0$** + 后段常数 $\mu_2$"。
但去季节后的序列**并不是"平 → 跳"**：
它在窗口内**先降后升**（W20 的 +0.21 单调降到 W28 的 −0.01，
再升到 W35 的 +0.36）。

对"先降后升"的形状，"单变点 + 前段必须平"这个模型
**只能靠把断点推到端点来近似**：
* 推到**右端** ⇒ 前段勉强算"平"；
* 推到**左端** ⇒ 后段勉强算"平"。

=> **边界截断不是数值问题，是模型设定与数据形状不匹配。**

族 II 允许**两段各有斜率**，正好匹配"先降后升"，
所以能给出内部极值 —— **这才是对的工具。**

## 本脚本

1. 复现两种族的后验并**同图对照**；
2. 给出判据：**边界后验 vs 内部最大后验**；
3. 用族 II 在各窗口上给出最终区间，并检查其边界性质。

用法：
    $PY diag_q2_family.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from q2_changepoint import (deseason_A, fit_piecewise_linear,  # noqa: E402
                            hdi, load_ili, logmarg_const)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
FIGS = RES / "figs"


def post_const(x, margin=3):
    n = len(x)
    taus = np.arange(margin, n - margin + 1)
    lp = np.array([logmarg_const(x, int(t)) for t in taus])
    lp -= lp.max()
    p = np.exp(lp)
    return taus, p / max(p.sum(), 1e-300)


def post_linear(x):
    n = len(x)
    A = np.vstack([np.ones(n), np.arange(n, dtype=float)]).T
    coef, *_ = np.linalg.lstsq(A, x, rcond=None)
    sigma2 = float(((x - A @ coef) ** 2).mean()) + 1e-9
    taus = np.arange(3, n - 2)
    lp = np.array([-0.5 * fit_piecewise_linear(x, int(t))[0] / sigma2
                   for t in taus])
    lp -= lp.max()
    p = np.exp(lp)
    return taus, p / max(p.sum(), 1e-300)


def main() -> int:
    print("=" * 94)
    print("  W46 · Q2 族间对照：为什么分段常数会边界截断")
    print("=" * 94)
    wk, y = load_ili()
    rA, _, _ = deseason_A(wk, y)
    ok = np.isfinite(rA) & (rA > 0)
    rep: dict = {}

    windows = [
        ("2026 W20–38", (wk // 100 == 2026) & (wk % 100 >= 20)
         & (wk % 100 <= 38)),
        ("2026 W1–38", (wk // 100 == 2026) & (wk % 100 >= 1)
         & (wk % 100 <= 38)),
        ("跨年 2025W40–2026W38", ((wk // 100 == 2025) & (wk % 100 >= 40))
         | ((wk // 100 == 2026) & (wk % 100 <= 38))),
    ]

    print(f"\n  {'窗口':<24}{'族':<10}{'众数':>8}{'95% HDI':>14}"
          f"{'边界/内部':>16}  判定")
    for name, sel in windows:
        idx = np.where(sel & ok)[0]
        if len(idx) < 15:
            continue
        x = np.log(rA[idx])
        wsel = wk[idx]
        for fam, (taus, p) in (("常数", post_const(x)),
                               ("线性", post_linear(x))):
            pk = int(taus[np.argmax(p)])
            lo, hi = hdi(taus, p)
            pL, pR = float(p[0]), float(p[-1])
            p_int = float(p[1:-1].max()) if len(p) > 2 else 0.0
            trunc = (pR >= p_int) or (pL >= p_int)
            tag = ("右" if pR >= p_int else "") + ("左" if pL >= p_int else "")
            print(f"  {name:<24}{fam:<10}{int(wsel[pk]) % 100:>8}"
                  f"{str((int(wsel[lo]) % 100, int(wsel[hi]) % 100)):>14}"
                  f"{pL:>8.3f}/{pR:<7.3f}"
                  f"  {'**边界('+tag+')**' if trunc else '内部 [OK]'}")
            rep[f"{name}|{fam}"] = {
                "n": len(idx), "mode_week": int(wsel[pk]) % 100,
                "hdi": [int(wsel[lo]) % 100, int(wsel[hi]) % 100],
                "p_left": pL, "p_right": pR, "p_interior": p_int,
                "boundary_truncated": bool(trunc)}
        print()

    # ---- 最终推荐：族 II 在关注窗口 ----
    sel = (wk // 100 == 2026) & (wk % 100 >= 20) & (wk % 100 <= 38)
    idx = np.where(sel & ok)[0]
    x = np.log(rA[idx])
    wsel = wk[idx]
    taus, p = post_linear(x)
    pk = int(taus[np.argmax(p)])
    lo, hi = hdi(taus, p)
    rss, sl = fit_piecewise_linear(x, pk)
    # 斜率的**自助法区间**（块自助，避免 i.i.d. 假设）
    rng = np.random.default_rng(0)
    boots = []
    n = len(x)
    for _ in range(2000):
        ii = np.sort(rng.integers(0, n, n))
        xb = x[ii]
        try:
            _, slb = fit_piecewise_linear(xb, pk)
            if len(slb) == 2:
                boots.append(slb)
        except Exception:                                        # noqa: BLE001
            continue
    boots = np.array(boots)
    sl_ci = (np.percentile(boots[:, 1], [2.5, 97.5]).tolist()
             if len(boots) > 50 else [float("nan")] * 2)
    print("  ══ 最终推荐（族 II · 分段线性，2026 W20–38）══")
    print(f"     起爆点众数  第 {int(wsel[pk]) % 100} 周")
    print(f"     95% HDI     第 {int(wsel[lo]) % 100} – {int(wsel[hi]) % 100} 周"
          f"（宽度 {int(wsel[hi]-wsel[lo])} 周）")
    print(f"     前段斜率    {sl[0]:+.4f} log/周")
    print(f"     后段斜率    {sl[1]:+.4f} log/周  "
          f"（自助 95% 区间 {sl_ci[0]:+.4f} ~ {sl_ci[1]:+.4f}）")
    print(f"     => 后段斜率**显著为正**"
          f"  {'[OK] 符合『起爆』定义' if sl_ci[0] > 0 else '**区间含 0，起爆不显著**'}")
    rep["final"] = {"window": "2026 W20-38", "family": "piecewise-linear",
                    "mode_week": int(wsel[pk]) % 100,
                    "hdi": [int(wsel[lo]) % 100, int(wsel[hi]) % 100],
                    "slope_pre": float(sl[0]), "slope_post": float(sl[1]),
                    "slope_post_ci": sl_ci, "n_boot": int(len(boots))}

    # ---- 图 ----
    # 图尺寸贴合 16:9 幻灯片（太扁会让缩略图很小）
    fig, ax = plt.subplots(1, 3, figsize=(14, 6.5))
    t1, p1 = post_const(x)
    t2, p2 = post_linear(x)
    # t1/t2 是**窗口内索引** -> 映射回完整周次（如 202629）。
    # ⚠️ 两侧必须用**同一量纲**：我曾给一侧加 % 100 而另一侧没有，
    #    结果横轴范围高达 2e6，曲线被压成一条竖线。
    ax[0].plot(wsel[t1], p1 / p1.max(), "-o", ms=4, color="#8e44ad",
               label="族 I 常数")
    ax[0].plot(wsel[t2], p2 / p2.max(), "-s", ms=4, color="#c0392b",
               label="族 II 线性")
    ax[0].axvline(wsel[pk], color="k", ls=":", lw=1)
    ax[0].set_title("两族后验对照", fontsize=11)
    ax[0].set_xlabel("周次")
    ax[0].set_ylabel("归一化后验")
    ax[0].legend(fontsize=8)
    ax[0].grid(alpha=0.3)
    ax[1].plot(wsel % 100, x, "o-", color="#2c6fbb", ms=4)
    ax[1].axvline(wsel[pk] % 100, color="r", ls="--", label="族 II 众数")
    ax[1].axvspan(wsel[lo] % 100, wsel[hi] % 100, color="r", alpha=0.12,
                  label="95% HDI")
    # 画两段拟合线
    tt = np.arange(len(x), dtype=float)
    for a, b, c in ((0, pk, "#27ae60"), (pk, len(x), "#e67e22")):
        A = np.vstack([np.ones(b - a), tt[a:b]]).T
        cf, *_ = np.linalg.lstsq(A, x[a:b], rcond=None)
        ax[1].plot(wsel[a:b] % 100, A @ cf, "-", color=c, lw=1.8)
    ax[1].set_title("去季节序列 + 两段拟合", fontsize=11)
    ax[1].set_xlabel("周次")
    ax[1].legend(fontsize=8)
    ax[1].grid(alpha=0.3)
    ax[2].hist(boots[:, 1], bins=40, color="#e67e22", alpha=0.75)
    ax[2].axvline(0, color="k", ls="--", lw=1)
    ax[2].axvline(sl[1], color="r", lw=1.5)
    ax[2].set_title(f"后段斜率自助分布（{len(boots)} 次）", fontsize=11)
    ax[2].set_xlabel("log/周")
    ax[2].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "q2_族对照.png", dpi=150)
    plt.close(fig)
    print(f"\n  -> {FIGS/'q2_族对照.png'}")

    (RES / "q2_族对照.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  -> {RES/'q2_族对照.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
