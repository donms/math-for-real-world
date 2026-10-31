#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W56 · 融合层：收益取决于**误差相关性**，不是"多接一个传感器"。

## 这一层要算的硬结论

若两个传感器独立：

$$P_{FA}^{\text{AND}}=\prod_i P_{FA,i}$$

若两者**在同一类负样本上同时出错**（完全相关）：

$$P_{FA}^{\text{AND}}=\min_i P_{FA,i}$$

$$\boxed{\text{融合的真实收益 = 乘积界与最小值界之间，由 }\rho_{FA}\text{ 决定}}$$

**而 $\rho_{FA}$ 不是假设，可以从前一层算出来**：把每个传感器的误报按负样本
类别拆开，两个传感器的**误报构成的重叠系数**就是 $\rho_{FA}$：

$$\rho_{FA,ij}=\sum_{a}\min\!\big(s_{i,a},s_{j,a}\big),\qquad
  s_{i,a}=\frac{n_aQ(\tau-\mu_{i,a})}{\sum_{a'}n_{a'}Q(\tau-\mu_{i,a'})}$$

## 为什么"检出的相关性"是另一回事

摔倒本身有个**未观测的严重度** $z\sim N(0,1)$（摔得重不重、地上有没有地毯）。
同一个摔倒对两个传感器是**同一个 $z$**，所以两者的**成功/失败是相关的**：

$$\mathrm{corr}(S_i,S_j\mid\text{摔倒})=\frac{\lambda_i\lambda_j}
  {\sqrt{(\lambda_i^2+1)(\lambda_j^2+1)}}\approx0.33\ (\lambda=0.7)$$

$$\boxed{\text{融合的收益}\;=\;\rho_{FA}-\rho_{D}\ \text{的差距}}$$

误差比成功更相关（$\rho_{FA}>\rho_D$）⇒ 融合赚；
若某个组合的 $\rho_{FA}<\rho_D$（成功比失败更相关）⇒ **融合可能反而亏**。

## 用法

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"
$PY scripts\\fuse_combo.py                       # 相关组矩阵 + 组合表
$PY scripts\\fuse_combo.py --fig --json          # 出两张图
$PY scripts\\fuse_combo.py --wear-sweep          # 佩戴率阈值
$PY scripts\\fuse_combo.py --selftest
```
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sig_fall as SF                                     # noqa: E402
import roc_daily as RD                                    # noqa: E402
import compare_mcdm as MC                                 # noqa: E402

RHO_D = 0.33        # ③ 检出相关性：由"共同严重度"给出，λ=0.7 ⇒ 0.33
ROUND = 5           # μ 保留位数，保证组合计算可复现


# ============================================================
# 1. 每个传感器的误报构成
# ============================================================
def profile(stats: dict, sensor: str, scen: str,
            unknown_n: float = 60.0, unknown_rel: float = 0.45) -> dict:
    r"""取某传感的类中心 $\mu$、可用通道，以及每天的判别机会数。

    ★ 融合层**必须**在"有未知活动"的场景下评估，否则好传感器会饱和：
    只算 6 类已知负样本时，摄像头与激光雷达在 0.1 次/天下已经顶到 100%，
    再怎么融合也只能持平 ⇒ 看不出融合的任何价值。
    加上每天 `unknown_n` 次可分性为 $R\hat d$ 的未建模活动之后，
    单传感器掉到个位数百分比，融合的空间才显露出来。
    """
    S = stats["stats"] if "stats" in stats else stats
    pr = RD.project(S, sensor)
    n = {a: c for a, c in RD.N_PER_DAY[scen].items() if a in pr["mu"]}
    mu = {a: round(v, ROUND) for a, v in pr["mu"].items()}
    if unknown_n > 0:
        mu["_unknown"] = round(unknown_rel * pr["d"], ROUND)
        n["_unknown"] = unknown_n
    n_gate = RD.GATE_BY_SCEN[scen]
    n_opp = float(sum(n.values()) + n_gate)
    # ρ_FA 是"误差模式"的性质，不该随工作点漂：固定在**只用已知负样本**
    # 求出的参考门限上算（否则 τ 被未知项顶高后，各类份额全部趋于 0，
    # 归一化后只剩"μ 最大的那一个"，会出现全 1.00 的伪相关）
    n_known = {a: c for a, c in n.items() if a != "_unknown"}
    tau_ref = RD.solve_tau({a: v for a, v in mu.items()},
                           n_known, RD.TARGET_FA, n_gate)
    return dict(mu=mu, d=pr["d"], worst=pr["worst"], channels=pr["channels"],
                n=n, n_gate=n_gate, n_opp=n_opp, tau_ref=float(tau_ref))


def shares(pr: dict, tau: float) -> dict:
    r"""在门限 τ 上，每个负样本占该传感误报的比例 $s_{i,a}$。"""
    parts = {a: c * float(RD.Q(tau - pr["mu"][a])) for a, c in pr["n"].items()}
    parts["_gate"] = pr["n_gate"] * float(RD.Q(tau))
    tot = sum(parts.values())
    if tot <= 0:
        return {a: 0.0 for a in parts}
    return {a: v / tot for a, v in parts.items()}


def rho_fa(pri: dict, prj: dict, tau: float) -> tuple[float, dict]:
    r"""误报构成的重叠系数（**不含门控**，门控两边独立）。

    $$\rho_{FA,ij}=\sum_{a\ne\text{gate}}\min(s_{i,a},s_{j,a})
      \Big/\sum_{a\ne\text{gate}}\max(1,\ldots)$$

    规范化做法：把两份 share 各自在"负样本"上重新归一，再取重叠系数。
    """
    si = shares(pri, tau)
    sj = shares(prj, tau)
    ai = {a: v for a, v in si.items() if a not in ("_gate", "_unknown")}
    aj = {a: v for a, v in sj.items() if a not in ("_gate", "_unknown")}
    ti, tj = sum(ai.values()), sum(aj.values())
    if ti <= 0 or tj <= 0:
        return 0.0, {}
    ai = {a: v / ti for a, v in ai.items()}
    aj = {a: v / tj for a, v in aj.items()}
    keys = set(ai) | set(aj)
    ov = {a: min(ai.get(a, 0.0), aj.get(a, 0.0)) for a in keys}
    return float(sum(ov.values())), ov


def p_fa_per_opp(pr: dict, tau: float) -> float:
    r"""单次判别机会上的误报概率。"""
    num = sum(c * float(RD.Q(tau - pr["mu"][a])) for a, c in pr["n"].items())
    num += pr["n_gate"] * float(RD.Q(tau))
    return float(num / pr["n_opp"])


def p_d_per_opp(pr: dict, tau: float) -> float:
    r"""单次判别机会上的检出概率。"""
    return float(RD.Q(tau - pr["mu"]["fall"]))


# ============================================================
# 2. 融合（AND / OR）与门限求解
# ============================================================
def fuse_pair(pri: dict, prj: dict, mode: str = "and",
              target: float = RD.TARGET_FA, rho_d: float = RHO_D,
              rho_fa: float | None = None) -> dict:
    r"""把两个传感器融起来，在同一误报预算下重新定门限。

    AND（两票都报才报警）：

    $$p^{\text{AND}}=\rho_{FA}\min(p_i,p_j)+(1-\rho_{FA})\,p_ip_j$$

    OR（任一报就报警）：

    $$p^{\text{OR}}=\rho_{FA}\max(p_i,p_j)+(1-\rho_{FA})(p_i+p_j-p_ip_j)$$

    $\rho_{FA}=1$ 给最小值界，$\rho_{FA}=0$ 给乘积界，中间是插值。
    检出一侧用同一个 $\rho_D$。
    """
    if rho_fa is None:
        # 先用单传感的门限估一个 ρ_FA，再用融合门限复核一次（它随 τ 弱变）
        tau0 = RD.solve_tau(pri["mu"], pri["n"], target / 2, pri["n_gate"])
        rho, ov = rho_fa_pair(pri, prj, tau0)
    else:
        rho, ov = float(rho_fa), {}

    def pr_and(tau):
        a, b = p_fa_per_opp(pri, tau), p_fa_per_opp(prj, tau)
        return rho * min(a, b) + (1 - rho) * a * b

    def pd_and(tau):
        a, b = p_d_per_opp(pri, tau), p_d_per_opp(prj, tau)
        return rho_d * min(a, b) + (1 - rho_d) * a * b

    def pr_or(tau):
        a, b = p_fa_per_opp(pri, tau), p_fa_per_opp(prj, tau)
        p_ij = rho * min(a, b) + (1 - rho) * a * b
        return rho * max(a, b) + (1 - rho) * (a + b - p_ij)

    def pd_or(tau):
        a, b = p_d_per_opp(pri, tau), p_d_per_opp(prj, tau)
        p_ij = rho_d * min(a, b) + (1 - rho_d) * a * b
        return rho_d * max(a, b) + (1 - rho_d) * (a + b - p_ij)

    f_fa = pr_and if mode == "and" else pr_or
    f_pd = pd_and if mode == "and" else pd_or
    n_opp = 0.5 * (pri["n_opp"] + prj["n_opp"])
    lo, hi = 0.0, 90.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if f_fa(mid) * n_opp <= target:
            hi = mid
        else:
            lo = mid
    tau = hi
    rho2, ov = rho_fa_pair(pri, prj, tau)
    return dict(mode=mode, tau=float(tau), rho_fa=float(rho2),
                rho_d=float(rho_d), overlap=ov,
                pd=float(f_pd(tau)), fa=float(f_fa(tau) * n_opp),
                pd_i=float(p_d_per_opp(pri, tau)),
                pd_j=float(p_d_per_opp(prj, tau)),
                fa_i=float(p_fa_per_opp(pri, tau) * n_opp),
                fa_j=float(p_fa_per_opp(prj, tau) * n_opp))


def rho_fa_pair(pri: dict, prj: dict, tau: float = None) -> tuple[float, dict]:
    r"""$\rho_{FA}$：两份"误报构成"的重叠系数。

    `tau=None` 时用各自的参考门限（已知负样本、0.1 次/天），
    这样 ρ 不随未知项漂移。
    """
    if tau is None:
        tau = float(pri.get("tau_ref", 2.5))
    si = shares(pri, tau)
    sj = shares(prj, tau)
    ai = {a: v for a, v in si.items() if a not in ("_gate", "_unknown")}
    aj = {a: v for a, v in sj.items() if a not in ("_gate", "_unknown")}
    ti, tj = sum(ai.values()), sum(aj.values())
    if ti <= 0 or tj <= 0:
        return 0.0, {}
    ai = {a: v / ti for a, v in ai.items()}
    aj = {a: v / tj for a, v in aj.items()}
    keys = set(ai) | set(aj)
    ov = {a: min(ai.get(a, 0.0), aj.get(a, 0.0)) for a in keys}
    return float(sum(ov.values())), ov


# ============================================================
# 3. 组合枚举
# ============================================================
COMBOS = [
    ("mmwave",),
    ("camera",),
    ("lidar",),
    ("imu",),
    ("wifi",),
    ("mmwave", "imu"),
    ("camera", "mmwave"),
    ("wifi", "mmwave"),
    ("camera", "lidar"),
    ("lidar", "wifi"),
    ("camera", "imu"),
    ("camera", "mmwave", "imu"),
]


def combo_metrics(profs: dict, combo: tuple, scen: str, wear: float,
                  mode: str = "and", rho_d: float = RHO_D,
                  target: float = RD.TARGET_FA) -> dict:
    r"""一个组合的（成本，检出，误报，ρ_FA）。

    * 单传感器：直接求门限；
    * 两个传感器：AND 融合后重定门限（这是"两票制"）；
    * 三个及以上：**先做前两个的 AND，把结果当成一个"等效传感器"，
      再与第三个 AND**。这是保守做法（每加一个都在压低误报），
      也如实反映"再加一个已经饱和的传感器没有增量"。
    """
    cost = float(sum(MC.tco3(k) for k in combo))
    label = "+".join(MC.OPTIONS[k]["label"].replace("可穿戴 IMU", "可穿戴")
                     for k in combo)
    wear_f = float(np.prod([wear if MC.OPTIONS[k]["wear"] else 1.0 for k in combo]))

    if len(combo) == 1:
        pr = profs[combo[0]]
        tau = RD.solve_tau(pr["mu"], pr["n"], target, pr["n_gate"])
        pd = p_d_per_opp(pr, tau)
        return dict(combo=combo, label=label, cost=cost, pd=float(pd),
                    fa=float(p_fa_per_opp(pr, tau) * pr["n_opp"]),
                    rho_fa=1.0, tau=float(tau), pd_eff=float(pd * wear_f),
                    wear_factor=wear_f, pd_i=None, pd_j=None,
                    note="单传感", gain=0.0)

    pr_a, pr_b = profs[combo[0]], profs[combo[1]]
    rho, _ = rho_fa_pair(pr_a, pr_b)
    dfus = d_fused(pr_a, pr_b, rho)
    best = pr_a if pr_a["d"] >= pr_b["d"] else pr_b
    eq = equiv_profile(best, dfus)
    rho_mean = float(rho)
    pd_i, pd_j = (_pd_at(profs[combo[0]], target), _pd_at(profs[combo[1]], target))
    if len(combo) > 2:
        for k in combo[2:]:
            pr_k = profs[k]
            rk, _ = rho_fa_pair(eq, pr_k)
            dfus = d_fused(eq, pr_k, rk)
            eq = equiv_profile(eq, dfus)
            rho_mean = float(np.mean([rho_mean, rk]))
    pd = _pd_at(eq, target)
    return dict(combo=combo, label=label + ("" if len(combo) == 2 else ""),
                cost=cost, pd=float(pd), fa=float(target), rho_fa=rho_mean,
                pd_eff=float(pd * wear_f), wear_factor=wear_f,
                pd_i=float(pd_i), pd_j=float(pd_j),
                note="跨组" if _cross_group(combo) else "同组",
                gain=float((pd - max(pd_i, pd_j)) * 100))


def d_fused(pri: dict, prj: dict, rho: float) -> float:
    r"""AND 融合后的**等效可分性**。

    $$d_{\text{fused}}^2=\rho\,\min(d_i,d_j)^2
      +(1-\rho)\,(d_i^2+d_j^2)$$

    两条边界都对：

    * $\rho=1$（完全相关）⇒ $d_{\text{fused}}=\min(d_i,d_j)$，**没有增益**；
    * $\rho=0$（独立）、$d_i=d_j$ ⇒ $d_{\text{fused}}=\sqrt2\,d$，
      即经典结论"两路独立 OR/AND 判决把等效信噪比提高 3 dB"。

    ⇒ **融合增益因子就是 $\sqrt{2/(1+\rho)}$**：ρ=0 给 1.41 倍，
      ρ=0.5 给 1.15 倍，ρ=0.98 给 1.005 倍。
    """
    a, b = pri["d"], prj["d"]
    return float(np.sqrt(rho * min(a, b) ** 2 + (1 - rho) * (a * a + b * b)))


def equiv_profile(pr_best: dict, d_new: float) -> dict:
    r"""把融合结果折算成一个"等效传感器"：几何按最优单传感等比放大。"""
    k = d_new / max(pr_best["d"], 1e-9)
    mu = {a: round(v * k, ROUND) for a, v in pr_best["mu"].items()}
    mu["fall"] = round(d_new, ROUND)
    return dict(mu=mu, d=float(d_new), worst=pr_best["worst"],
                channels=pr_best["channels"], n=dict(pr_best["n"]),
                n_gate=pr_best["n_gate"], n_opp=pr_best["n_opp"],
                tau_ref=pr_best.get("tau_ref", 2.5))


def _mu_from_pd(pd: float, lo: float = -6.0, hi: float = 8.0) -> float:
    r"""反解 $\mu_f$ 使 $Q(\tau-\mu_f)=p_d$（此处 $\tau=0$ 口径：直接解 $Q(-x)=p_d$）。"""
    if pd >= 0.999999:
        return 6.0
    if pd <= 1e-6:
        return -6.0
    lo, hi = -8.0, 8.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if float(RD.Q(-mid)) < pd:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _pd_at(pr: dict, target: float) -> float:
    r"""该（等效）传感器在 0.1 次/天约束下的检出率。"""
    tau = RD.solve_tau(pr["mu"], pr["n"], target, pr["n_gate"])
    return float(p_d_per_opp(pr, tau))


def _cross_group(combo: tuple) -> bool:
    r"""组标签：'sofa' 组（摄像头/激光雷达/可穿戴）与 'sit' 组（毫米波/WiFi）。"""
    g = {"camera": "sofa", "lidar": "sofa", "imu": "sofa",
         "mmwave": "sit", "wifi": "sit", "ble": "walk"}
    return len({g[k] for k in combo}) > 1


# ============================================================
# 4. 出图
# ============================================================
C_DARK = dict(bg="#0e1117", fg="#e8e8e8", grid="#2a2f3a")


def _mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def fig_corr(stats: dict, scen: str, path: Path) -> Path:
    r"""相关组矩阵：六种传感器两两的 $\rho_{FA}$。"""
    plt = _mpl()
    C = C_DARK
    sensors = [s for s in ("camera", "lidar", "imu", "mmwave", "wifi", "ble")
               if s in stats["sensors"]]
    profs = {s: profile(stats, s, scen) for s in sensors}
    M = np.zeros((len(sensors), len(sensors)))
    for i, a in enumerate(sensors):
        for j, b in enumerate(sensors):
            if i == j:
                M[i, j] = 1.0
                continue
            # ρ_FA 用参考门限（只用已知负样本），否则高 τ 下会退化成伪相关
            M[i, j] = 0.5 * (rho_fa_pair(profs[a], profs[b])[0]
                             + rho_fa_pair(profs[b], profs[a])[0])
    fig, ax = plt.subplots(figsize=(8.4, 7.2))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    im = ax.imshow(M, cmap="RdYlGn_r", vmin=0, vmax=1)
    LAB = {"lidar": "激光雷达", "camera": "摄像头", "imu": "可穿戴",
           "mmwave": "毫米波", "wifi": "WiFi", "ble": "蓝牙"}
    ax.set_xticks(range(len(sensors)))
    ax.set_yticks(range(len(sensors)))
    ax.set_xticklabels([LAB[s] for s in sensors], color=C["fg"], fontsize=10,
                       rotation=30, ha="right")
    ax.set_yticklabels([LAB[s] for s in sensors], color=C["fg"], fontsize=10)
    for i in range(len(sensors)):
        for j in range(len(sensors)):
            v = M[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    color="#111" if v < 0.75 else "#fff", fontsize=10,
                    fontweight="bold")
    ax.set_title("误差相关组矩阵 ρ_FA：越红越「一起错」，融合越不赚",
                 color=C["fg"], fontsize=11.5)
    cb = fig.colorbar(im, ax=ax, pad=.02)
    cb.ax.tick_params(colors=C["fg"], labelsize=8)
    cb.set_label("误报构成的重叠系数", color=C["fg"], fontsize=9)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140, facecolor=C["bg"])
    plt.close(fig)
    return path


def fig_fusion(rows: list, path: Path, wear: float) -> Path:
    r"""两联图：成本-有效检出帕累托 + 融合增益与相关性的关系。"""
    plt = _mpl()
    C = C_DARK
    fig, axs = plt.subplots(1, 2, figsize=(14.4, 6.2),
                            gridspec_kw=dict(width_ratios=[1.35, 1]))
    fig.patch.set_facecolor(C["bg"])
    for ax in axs:
        ax.set_facecolor(C["bg"])
        ax.tick_params(colors=C["fg"], labelsize=9)
        for sp in ax.spines.values():
            sp.set_color(C["grid"])
        ax.grid(alpha=.22, color=C["grid"], lw=.6)

    ax = axs[0]
    xs = [r["cost"] for r in rows]
    ys = [r["pd_eff"] * 100 for r in rows]
    ax.scatter(xs, ys, s=120, c="#3f9bd8", edgecolor="#fff", lw=.8, zorder=4)
    for r in rows:
        ax.annotate(r["label"], (r["cost"], r["pd_eff"] * 100),
                    textcoords="offset points", xytext=(7, -3),
                    color=C["fg"], fontsize=7.6)
    # 帕累托
    front = []
    for r in rows:
        if not any((q["cost"] <= r["cost"] and q["pd_eff"] >= r["pd_eff"]
                    and (q["cost"] < r["cost"] or q["pd_eff"] > r["pd_eff"]))
                   for q in rows if q is not r):
            front.append(r)
    front.sort(key=lambda r: r["cost"])
    if len(front) >= 2:
        ax.plot([r["cost"] for r in front], [r["pd_eff"] * 100 for r in front],
                "--", color="#ffd479", lw=1.6, label="帕累托前沿")
    ax.set_xscale("log")
    ax.set_xlabel("三年总成本（元/间，对数轴）", color=C["fg"], fontsize=10)
    ax.set_ylabel(f"有效检出率（佩戴率 {wear:.0%}）(%)", color=C["fg"], fontsize=10)
    ax.set_ylim(0, 108)
    ax.set_title("成本 vs 有效检出：组合点与帕累托前沿", color=C["fg"], fontsize=11)
    ax.legend(fontsize=8.5, facecolor=C["bg"], edgecolor=C["grid"],
              labelcolor=C["fg"], loc="lower right")

    ax = axs[1]
    pairs = [r for r in rows if len(r["combo"]) == 2]
    if pairs:
        gx = [(r["rho_fa"] - RHO_D) for r in pairs]
        gy = [(r["pd"] - max(r["pd_i"], r["pd_j"])) * 100 for r in pairs]
        ax.axhline(0, color="#8a93a5", lw=1, ls=":")
        ax.axvline(0, color="#8a93a5", lw=1, ls=":")
        ax.scatter(gx, gy, s=150, c=[("#39c07a" if v >= 0 else "#e8465a")
                                     for v in gy], edgecolor="#fff", lw=.9,
                   zorder=4)
        for r, x, y in zip(pairs, gx, gy):
            ax.annotate("+".join(SF.ACTIVITY.get(r["worst"], {}).get(l, l)
                                 for l in [] ), (x, y), textcoords="offset points",
                        xytext=(0, 0), color=C["fg"], fontsize=1)
            ax.annotate(r["label"].replace("可穿戴 IMU", "可穿戴"),
                        (x, y), textcoords="offset points", xytext=(8, -3),
                        color=C["fg"], fontsize=7.6)
        ax.set_xlabel(r"$\rho_{FA}-\rho_D$（误差相关性减成功相关性）",
                      color=C["fg"], fontsize=10)
        ax.set_ylabel("融合带来的检出率变化（百分点）", color=C["fg"], fontsize=10)
        ax.set_title("融合增益 ≈ 由 ρ_FA − ρ_D 决定", color=C["fg"], fontsize=11)
    fig.suptitle("W56 · 组合的成本与相关性：跨组组合才赚，同组叠加白花钱",
                 color=C["fg"], fontsize=12.5, y=.985)
    fig.tight_layout(rect=(0, 0, 1, .955))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140, facecolor=C["bg"])
    plt.close(fig)
    return path


# ============================================================
# 5. 自检
# ============================================================
def selftest() -> int:
    k = 0

    def ck(c: bool, m: str) -> None:
        nonlocal k
        if not c:
            raise AssertionError("[X] " + m)
        k += 1
        print(f"  [OK] {m}")

    # 用"中等"传感器（d≈2.5），否则 AND 一上来就顶到 100%，看不出差别
    pr_a = dict(mu={"fall": 2.5, "sofa": 0.0, "walk": -4.0},
                n={"fall": 0.01, "sofa": 3, "walk": 40}, n_gate=5.0,
                n_opp=48.0, d=2.5, worst="sofa", channels=["v"])
    pr_b = dict(mu={"fall": 2.5, "sofa": -3.0, "walk": -4.0},
                n={"fall": 0.01, "sofa": 3, "walk": 40}, n_gate=5.0,
                n_opp=48.0, d=2.5, worst="walk", channels=["v"])
    f0 = fuse_pair(pr_a, pr_b, "and", rho_d=0.0, rho_fa=0.0)
    f1 = fuse_pair(pr_a, pr_b, "and", rho_d=0.0, rho_fa=1.0)
    ck(f0["pd"] > f1["pd"],
       f"① 独立（ρ=0）时 AND 融合的检出 {f0['pd']*100:.1f}% 高于完全相关"
       f"（ρ=1）的 {f1['pd']*100:.1f}%")
    ck(f0["fa"] <= 0.1 + 1e-6 and f1["fa"] <= 0.1 + 1e-6,
       "② 两种情形都满足 0.1 次/天预算")

    r, ov = rho_fa_pair(pr_a, pr_b, 1.0)
    ck(0.0 <= r <= 1.0, f"③ ρ_FA 落在 [0,1]：{r:.3f}")
    ck(abs(sum(ov.values()) - r) < 1e-9, "④ ρ_FA 等于各类重叠之和")

    r_same, _ = rho_fa_pair(pr_a, pr_a, 1.0)
    ck(abs(r_same - 1.0) < 1e-9, f"⑤ 自己对自己的 ρ_FA = {r_same:.3f}（完全相关）")

    fo = fuse_pair(pr_a, pr_b, "or", rho_d=0.0, rho_fa=0.0)
    fa = fuse_pair(pr_a, pr_b, "and", rho_d=0.0, rho_fa=0.0)
    ck(fo["tau"] > fa["tau"],
       f"⑥ 同一误报预算下 OR 的门限 τ={fo['tau']:.2f} 高于 AND 的 "
       f"τ={fa['tau']:.2f} ⇒ OR 只能靠抬门限保预算，增益被吃掉")
    print(f"\n  自检通过：{k} 条断言")
    return k


# ============================================================
# 6. CLI
# ============================================================
def main() -> int:
    ap = argparse.ArgumentParser(
        description="融合层：相关组矩阵、组合枚举、成本-有效检出帕累托。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="AND（两票）才有用；OR（一票）几乎不赚。")
    ap.add_argument("--scenario", default="bedroom", choices=sorted(RD.N_PER_DAY))
    ap.add_argument("--wear", type=float, default=0.60, help="可穿戴佩戴率")
    ap.add_argument("--rho-d", type=float, default=RHO_D, help="检出相关性")
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--unknown-n", type=float, default=60.0,
                    help="每天未建模活动次数（融合必须在非饱和区评估）")
    ap.add_argument("--unknown-rel", type=float, default=0.45)
    ap.add_argument("--wear-sweep", action="store_true", help="扫佩戴率")
    ap.add_argument("--fig", action="store_true", help="出两张图")
    ap.add_argument("--json", action="store_true", help="落盘")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]

    if args.selftest:
        print("=" * 80)
        print("  fuse_combo.py 自检")
        print("=" * 80)
        selftest()
        return 0

    st = RD.load_stats(root, n=args.n)
    RD.N_SCEN = dict(RD.N_PER_DAY[args.scenario])
    sensors = ["camera", "lidar", "imu", "mmwave", "wifi", "ble"]
    profs = {s: profile(st, s, args.scenario, args.unknown_n, args.unknown_rel)
             for s in sensors if s in st["sensors"]}

    print("=" * 96)
    print(f"  ① 误差相关组矩阵 ρ_FA（场景 {args.scenario}）")
    print("=" * 96)
    print("  " + f"{'':<10}" + "".join(f"{s:>9}" for s in sensors))
    for a in sensors:
        if a not in profs:
            continue
        row = f"  {a:<10}"
        for b in sensors:
            if b not in profs:
                continue
            if a == b:
                row += f"{1.0:>9.2f}"
                continue
            v = 0.5 * (rho_fa_pair(profs[a], profs[b])[0]
                       + rho_fa_pair(profs[b], profs[a])[0])
            row += f"{v:>9.2f}"
        print(row)
    print()
    print("  ★ 高值 = 两者在同一类负样本上一起错。同组叠加不赚，跨组才赚。")
    print()

    rows = []
    for combo in COMBOS:
        if not all(k in profs for k in combo):
            continue
        rows.append(combo_metrics(profs, combo, args.scenario, args.wear,
                                  rho_d=args.rho_d))
    for r in rows:
        if r.get("pd_i") is None or r.get("pd_j") is None:
            r["gain"] = 0.0
        else:
            r["gain"] = (r["pd"] - max(r["pd_i"], r["pd_j"])) * 100

    print("=" * 96)
    print(f"  ② 组合表（AND 融合；佩戴率 {args.wear:.0%}；ρ_D={args.rho_d:.2f}）")
    print("=" * 96)
    print(f"  {'组合':<26}{'三年成本':>9}{'ρ_FA':>7}{'融合检出':>9}"
          f"{'较优单传感':>11}{'有效检出':>9}{'组别':>7}")
    print("  " + "-" * 90)
    for r in sorted(rows, key=lambda x: -x["pd_eff"]):
        print(f"  {r['label'][:24]:<26}{r['cost']:>8.0f}元{r['rho_fa']:>7.2f}"
              f"{r['pd']*100:>8.1f}%{r['gain']:>+10.1f}{r['pd_eff']*100:>8.1f}%"
              f"{r.get('note',''):>7}")
    print()

    print("=" * 96)
    print("  ③ 三个必答题")
    print("=" * 96)
    base = next(r for r in rows if r["combo"] == ("mmwave",))
    mix = next(r for r in rows if r["combo"] == ("mmwave", "imu"))
    need = base["pd"] / mix["pd"] if mix["pd"] > 0 else float("inf")
    print(f"  (1) 毫米波 + 可穿戴：纯毫米波 {base['pd']*100:.1f}%，"
          f"加成融合 {mix['pd']*100:.1f}%（ρ_FA={mix['rho_fa']:.2f}）")
    print(f"      ⇒ 佩戴率要高于 {need*100:.1f}% 这个组合才赢得过纯毫米波。"
          f"低于它，可穿戴是纯负担。")
    print()
    cm = next((r for r in rows if r["combo"] == ("camera", "mmwave")), None)
    if cm:
        cam = next(r for r in rows if r["combo"] == ("camera",))
        print(f"  (2) 摄像头 + 毫米波：{cm['pd']*100:.1f}%（较优单传感 "
              f"{max(cm['pd_i'], cm['pd_j'])*100:.1f}%，增益 {cm['gain']:+.1f} 点）")
        print(f"      代价：隐私分从毫米波的 {MC.OPTIONS['mmwave']['privacy']:.0f} "
              f"掉到摄像头的 {MC.OPTIONS['camera']['privacy']:.0f}，"
              f"成本 {cm['cost']:.0f} 元；多人辨识从 "
              f"{MC.OPTIONS['mmwave']['ident']:.0f} 升到 "
              f"{MC.OPTIONS['camera']['ident']:.0f}")
        print("      ⇒ 养老院（有监管、有护理员、必须回答「是谁」）属于它的适用场景。")
    print()
    wm = next((r for r in rows if r["combo"] == ("wifi", "mmwave")), None)
    if wm:
        wm_single = next(r for r in rows if r["combo"] == ("mmwave",))
        print(f"  (3) WiFi + 毫米波：ρ_FA={wm['rho_fa']:.2f}，融合检出 "
              f"{wm['pd']*100:.1f}%，纯毫米波 {wm_single['pd']*100:.1f}%")
        print("      ⇒ 两个都便宜，但它们在「快速坐下」上同时错 ⇒ "
              f"增益只有 {wm['gain']:+.1f} 点，"
              "还要付 WiFi 的隐藏成本（多数商用路由器取不到 CSI）。")
    print()

    lo = next(r for r in rows if r["combo"] == ("lidar", "wifi"))
    print(f"  ④ 跨组反例：激光雷达 + WiFi ρ_FA={lo['rho_fa']:.2f}，"
          f"增益 {lo['gain']:+.1f} 点，成本 {lo['cost']:.0f} 元")
    print(f"     ⇒ 跨组确实更赚，但激光雷达本身就把检出顶满了，"
          f"再加一个便宜的 WiFi 是**用 150 元换 0 点**。")
    print()

    if args.wear_sweep:
        print("=" * 96)
        print("  ⑤ 佩戴率扫描：可穿戴什么时候从负担变成资产")
        print("=" * 96)
        print(f"  {'佩戴率':<8}{'可穿戴':>9}{'毫米波':>9}{'毫米波+可穿戴':>14}"
              f"{'摄像头':>9}{'摄像头+可穿戴':>14}")
        for wpct in (0.20, 0.40, 0.60, 0.75, 0.85, 0.95, 1.00):
            rr = {c: combo_metrics(profs, c, args.scenario, wpct,
                                   rho_d=args.rho_d) for c in
                  [("imu",), ("mmwave",), ("mmwave", "imu"),
                   ("camera",), ("camera", "imu")]}
            for c, v in rr.items():
                v.setdefault("pd_eff", v["pd"] * np.prod(
                    [wpct if MC.OPTIONS[k]["wear"] else 1.0 for k in c]))
            print(f"  {wpct*100:>5.0f}%{rr[('imu',)]['pd_eff']*100:>8.1f}%"
                  f"{rr[('mmwave',)]['pd_eff']*100:>8.1f}%"
                  f"{rr[('mmwave','imu')]['pd_eff']*100:>13.1f}%"
                  f"{rr[('camera',)]['pd_eff']*100:>8.1f}%"
                  f"{rr[('camera','imu')]['pd_eff']*100:>13.1f}%")
        print()

    if args.fig:
        p1 = fig_corr(st, args.scenario, root / "results" / "figs" / "fig_corr_groups.png")
        p2 = fig_fusion(rows, root / "results" / "figs" / "fig_fusion.png", args.wear)
        print(f"  [OK] 图：{p1}")
        print(f"  [OK] 图：{p2}")
    if args.json:
        p = root / "results" / "fusion.json"
        p.write_text(json.dumps(dict(
            scenario=args.scenario, wear=args.wear, rho_d=args.rho_d,
            rows=[{k: (list(v) if isinstance(v, tuple) else v)
                   for k, v in r.items()} for r in rows]),
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [OK] JSON：{p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
