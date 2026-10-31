#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W56 · 从可分性到「每天误报几次 vs 检出率」：全期主图。

## 这一层要回答的问题

**判据不该是"准确率"，而是"每小时误报率"。**

$$\text{一个每天误报 1 次的报警器} = \text{没有报警器}$$

理由可以算（③ 假设"人对报警的响应概率随误报率指数衰减"，
$\lambda$ 为每天误报次数）：

$$\Pr(\text{响应})=\exp(-\lambda/\lambda_0),\qquad \lambda_0=1\ \text{次/天}$$

| 每天误报 | 响应概率 | 说明 |
|---|---|---|
| 0.1 | **90.5%** | 十次报警九次被当真 |
| 1 | **36.8%** | 十次里四次被当真 |
| 5 | **0.7%** | 报警器被关掉 |

⇒ 所以本期把指标定在 **$\lambda\le0.1$ 次/天**，并问：
**在这个约束下，每种传感器还能剩下多少检出率？**

## 数学形式：泊松混合 + 一维判别投影

对传感 $s$，取它**最像摔倒的那个负样本** $a^*$（决定门限的那一个），
按 Fisher 方向投影成一维得分：

$$\mathbf w=\Sigma^{-1}(\boldsymbol\mu_{\text{fall}}-\boldsymbol\mu_{a^*}),\qquad
  S=\frac{\mathbf w^{\mathsf T}\mathbf f}{\sqrt{\mathbf w^{\mathsf T}\Sigma\mathbf w}}$$

于是 $\mu_{a^*}=0$、$\mu_{\text{fall}}=\hat d_{a^*}$（就是可分性本身），
所有类的方差都是 1。每天误报次数：

$$\Lambda(\tau)=\underbrace{\sum_{i}n_i\,Q(\tau-\mu_i)}_{\text{已知负样本}}
  +\underbrace{N_{\text{gate}}\,Q(\tau)}_{\text{门控误开}}$$

门限 $\tau^*=\min\{\tau:\Lambda(\tau)\le0.1\}$，检出率 $P_d=Q(\tau^*-\mu_{\text{fall}})$。

**注意两件事（都会在结果里单独报）**：

1. **谁咬住门限**：可能是某个负样本，也可能是"门控误开"那一项。
   二者对应完全不同的工程对策（前者要加通道，后者要加门控）。
2. **$\hat d$ 只统计了 6 类已知负样本**。真实系统还有"未知未知"，
   所以这里的 $P_d$ 是**上界**，`--unknown-n` 可把未知项加进来扫。

## 用法

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"
$PY scripts\\roc_daily.py                     # 上界口径（只算 6 类已知负样本）
$PY scripts\\roc_daily.py --unknown-n 60      # 工程实际口径（加 60 次/天未知活动）
$PY scripts\\roc_daily.py --scenario nh --unknown-n 60    # 养老院，工程实际
$PY scripts\\roc_daily.py --sweep             # 四组敏感性（未知项/门控/判据/类内变异）
$PY scripts\\roc_daily.py --selftest
```

**两个口径必须分开报**（W56 修订一）：`--unknown-n 0` 是**上界**，只用来说明
"模型只考了六道题"；`--unknown-n 60` 是**工程实际**，也是本文表 6、表 8、表 9、
表 11 的口径。**同一个检出率不能不带口径出现。**

`--sweep` 的敏感性 D 是**生成参数级**的整体放大（所有生成参数同乘 $k$，重跑蒙特卡洛，
类中心随噪声移动），也就是论文表 21 的第一套算子。**要"一次只放大一个通道"、
以及"std×k、类中心不动"的第二套算子，见 `diag_jitter_channel.py`**：那里的
`gen` 段给生成参数级、`single` 段给 std×k，两套的数不能混用。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sig_fall as SF                                     # noqa: E402
import sig_confounders as SC                              # noqa: E402

# ============================================================
# 0. 场景与假设（③）
# ============================================================
# 每天各负样本发生次数。两档场景：独居老人卧室（单人）、养老院多人间。
N_PER_DAY = {
    "bedroom": {"fall": 0.011, "sit_fast": 6, "bend": 12, "sofa": 3,
                "walk": 40, "door": 8, "bed": 10},
    "nh": {"fall": 0.022, "sit_fast": 20, "bend": 25, "sofa": 4,
           "walk": 120, "door": 15, "bed": 12},
}
N_GATE_FALSE = 20.0      # 门控每天误开次数（缺省；按场景覆盖，见 GATE_BY_SCEN）
# ★ 这是全模型最吃重的一个 ③：门控误开 n_gate 次/天时，光它就把门限顶到
#   Q^{-1}(0.1/n_gate)：5 次/天给 2.05σ，20 次/天给 2.58σ，100 次/天给 3.09σ。
#   而各负样本要求的分隔只有 1.8–2.2σ ⇒ **多数场合真正咬住门限的是门控**。
GATE_BY_SCEN = {"bedroom": 5.0, "nh": 20.0}
TARGET_FA = 0.1          # 每天误报上限（本期判据）
LAMBDA0 = 1.0            # 响应衰减尺度（③ 次/天）


def Q(x):
    r"""标准正态上尾 $Q(x)=\frac1{\sqrt{2\pi}}\int_x^\infty e^{-t^2/2}dt$。"""
    return 0.5 * math.erfc(np.asarray(x) / math.sqrt(2.0))


# ============================================================
# 1. 取特征统计
# ============================================================
def load_stats(root: Path, n: int = 120, jitter: float = 1.0,
               force: bool = False) -> dict:
    r"""优先读 `results/features.json`，没有就现算（并落盘）。"""
    p = root / "results" / "features.json"
    if p.exists() and not force:
        d = json.loads(p.read_text(encoding="utf-8"))
        if abs(d.get("n", 0) - n) <= 1 and abs(d.get("jitter", -1) - jitter) < 1e-9:
            print(f"  [i] 复用特征统计：{p.name}（n={d['n']}, jitter={d['jitter']}）")
            return d
    print(f"  [i] 现算特征统计（n={n}, jitter={jitter}）…")
    d = SC.run(n=n, jitter=jitter, verbose=False)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dict(d, separability=SC.separability(
        d["stats"], d["sensors"])), ensure_ascii=False, indent=2),
        encoding="utf-8")
    return d


# ============================================================
# 2. 单传感的判别投影与 ROC
# ============================================================
def project(stats: dict, sensor: str, fall: str = "fall") -> dict:
    r"""按"摔倒 vs 最像它的负样本"的 Fisher 方向投影到一维得分。

    返回：

    * `mu`：每个活动在该得分轴上的位置（以最坏负样本为原点，方差 = 1）
    * `worst`：最坏负样本（决定门限的那一个）
    * `d`：$\mu_{\text{fall}}$，即可分性
    * `channels`：该传感可用的通道
    """
    acts = [a for a in stats if a != fall]
    chs = [c for c in SC.CH_NAMES
           if stats[fall][sensor].get(c, {}).get("mean") is not None]

    def vec(a):
        return np.array([stats[a][sensor][c]["mean"] for c in chs], float)

    def var(a):
        return np.array([max(stats[a][sensor][c]["std"], 1e-9) ** 2 for c in chs])

    mf = vec(fall)
    # 最坏负样本 = 与摔倒的 Mahalanobis 距离最小者
    d = {}
    for a in acts:
        vt = 0.5 * (var(fall) + var(a))
        d[a] = float(np.sqrt(np.sum((mf - vec(a)) ** 2 / np.maximum(vt, 1e-12))))
    a_star = min(d, key=d.get)
    vt = 0.5 * (var(fall) + var(a_star))
    w = (mf - vec(a_star)) / np.maximum(vt, 1e-12)
    Z = float(np.sqrt(np.sum(w ** 2 * vt)))
    if Z <= 0:
        return dict(mu={}, worst=a_star, d=0.0, channels=chs, w=None, Z=0.0)

    mu = {a: float(np.sum(w * (vec(a) - vec(a_star))) / Z) for a in stats}
    return dict(mu=mu, worst=a_star, d=float(mu[fall]), channels=chs,
                w=w.tolist(), Z=Z)


def fa_rate(tau: float, mu: dict, n: dict, n_gate: float = N_GATE_FALSE) -> float:
    r"""$\Lambda(\tau)$：每天误报次数。"""
    s = n_gate * float(Q(tau))
    for a, cnt in n.items():
        if a in mu and cnt > 0:
            s += cnt * float(Q(tau - mu[a]))
    return s


def solve_tau(mu: dict, n: dict, target: float = TARGET_FA,
              n_gate: float = N_GATE_FALSE) -> float:
    r"""二分求最小 $\tau$ 使 $\Lambda(\tau)\le$ target。

    边界：$\tau=0$ 时 $\Lambda\ge n_{\text{gate}}/2$（已经超了）说明
    **这个约束在本场景下无解** ⇒ 返回 $\tau=0$ 并把结论标成"不可达"。
    """
    lo, hi = 0.0, 80.0
    if fa_rate(hi, mu, n, n_gate) > target:
        return hi
    for _ in range(90):
        mid = 0.5 * (lo + hi)
        if fa_rate(mid, mu, n, n_gate) <= target:
            hi = mid
        else:
            lo = mid
    return hi


def roc_curve(mu: dict, taus: np.ndarray, n: dict | None = None
              ) -> tuple[np.ndarray, np.ndarray]:
    r"""把 $(\tau\mapsto \Lambda, P_d)$ 扫成 ROC 曲线。

    `n` 为每个活动每天的次数（缺省用当前场景的 `N_SCEN`）；若 `mu` 里带
    `_unknown`，则 `n` 里也要带同名的次数，否则那一项不计入误报。
    """
    nn = N_SCEN if n is None else n
    lam = np.array([fa_rate(t, mu, nn) for t in taus])
    pd = np.array([float(Q(t - mu["fall"])) for t in taus])
    return lam, pd


def balanced_accuracy(pd: float, mu: dict, tau: float) -> float:
    r"""平衡测试集上的"准确率"（正负 1:1），用来演示**准确率陷阱**。

    $$\text{acc}=\tfrac12\Big[P_d+1-\overline{P_{fa}}\Big]$$
    """
    vals = [float(Q(tau - m)) for a, m in mu.items() if a != "fall"]
    return 0.5 * (pd + 1.0 - float(np.mean(vals)))


# ============================================================
# 3. 主表
# ============================================================
N_SCEN: dict = {}


def report(stats: dict, scenario: str, target: float = TARGET_FA,
           n_gate: float = N_GATE_FALSE, unknown_n: float = 0.0,
           unknown_rel: float = 0.45, verbose: bool = True) -> dict:
    r"""六种传感在给定场景下、给定误报约束下的检出率。

    `unknown_n` / `unknown_rel`：把"未建模的日常活动"当成第 7 个负样本，
    它每天发生 `unknown_n` 次，可分性取 $R\cdot\hat d_{a^*}$
    （$R$ 默认 0.45，即"未知的比已知的最坏情况差一半"）。
    """
    n = dict(N_PER_DAY[scenario])
    S = stats["stats"] if "stats" in stats else stats
    out: dict = {}
    for s in stats["sensors"]:
        pr = project(S, s)
        if not pr["mu"]:
            continue
        mu = dict(pr["mu"])
        nn = {a: c for a, c in n.items() if a in mu}
        if unknown_n > 0:
            mu["_unknown"] = unknown_rel * pr["d"]
            nn["_unknown"] = unknown_n
        tau = solve_tau(mu, nn, target, n_gate)
        pd = float(Q(tau - mu["fall"]))
        lam = fa_rate(tau, mu, nn, n_gate)
        # 哪一项咬住了门限
        parts = {a: float(c) * float(Q(tau - mu[a])) for a, c in nn.items()}
        parts["_gate"] = n_gate * float(Q(tau))
        bind = max(parts, key=parts.get)
        out[s] = dict(
            d=pr["d"], worst=pr["worst"], channels=pr["channels"],
            tau=float(tau), pd=pd, fa=lam, bind=bind,
            bind_share=parts[bind] / max(sum(parts.values()), 1e-12),
            acc=balanced_accuracy(pd, mu, tau),
            respond=float(math.exp(-lam / LAMBDA0)),
            pd_eff=pd * float(math.exp(-lam / LAMBDA0)),
            mu=mu, parts=parts,
        )
    if verbose:
        print_report(out, scenario, target, n_gate)
    return out


def required_margin(act: str, scenario: str, target: float = TARGET_FA) -> float:
    r"""某负样本每天出现 $ 次时，它的得分必须比门限低多少。

    Q(\tau-\mu_i)\le\frac{\text{target}}{n_i}
      \iff \mu_i\le\tau-Q^{-1}\!\left(\frac{\text{target}}{n_i}\right)

    ⇒ **要求的分隔 = ^{-1}(\text{target}/n_i)$**。
    这条是全期最该带走的公式：**误报预算按次数加权**，
    每天 120 次的走动要求 3.49σ，每天 3 次的躺沙发只要求 1.88σ。
    """
    n = N_PER_DAY[scenario].get(act, 1.0)
    if n <= 0:
        return 0.0
    from scipy.stats import norm
    return float(norm.isf(target / n))


def print_report(out: dict, scenario: str, target: float, n_gate: float) -> None:
    name = {"bedroom": "独居老人卧室（单人）", "nh": "养老院多人间"}[scenario]
    print("=" * 88)
    print(f"  场景：{name}　目标：每天误报 ≤ {target} 次　门控误开 {n_gate:.0f}/天")
    print("=" * 88)
    print(f"  {'传感':<9}{'最坏负样本':<12}{'d′':>6}{'要求分隔':>9}{'门限τ':>7}{'检出':>7}"
          f"{'误报/天':>8}{'咬住项':>11}{'平衡准确率':>10}{'有效检出':>9}")
    print("  " + "-" * 88)
    order = sorted(out, key=lambda k: -out[k]["pd"])
    for s in order:
        r = out[s]
        lbl = SF.ACTIVITY.get(r["worst"], {}).get("label", r["worst"])
        if r["worst"] == "_unknown":
            lbl = "未知活动"
        need = required_margin(r["worst"], scenario)
        print(f"  {s:<9}{lbl:<12}{r['d']:>6.2f}{need:>9.2f}{r['tau']:>7.2f}"
              f"{r['pd']*100:>6.1f}%{r['fa']:>8.3f}"
              f"{r['bind']:>11}{r['acc']*100:>9.1f}%{r['pd_eff']*100:>8.1f}%")
    print()
    print("  ⚠ 本表只统计 6 类已知负样本 ⇒ 是**上界**。加未知活动后绝对值会掉，")
    print("    但排序稳健（见 --sweep 的未知项扫描）。")
    print("  ★ 「咬住项」= 谁的误报额度先占满门限。它决定该怎么改：")
    print("     咬住项是某个负样本 ⇒ 要加能区分它的那个通道；")
    print("     咬住项是 _gate（门控误开）⇒ 要加门控，加通道没用。")
    print()


# ============================================================
# 4. 出图：ROC 族 + 准确率陷阱
# ============================================================
def make_fig(out: dict, path: Path, scenario: str = "bedroom",
             unknown_n: float = 0.0, unknown_rel: float = 0.45) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False

    C = dict(bg="#0e1117", fg="#e8e8e8", grid="#2a2f3a",
             c={"lidar": "#3f9bd8", "camera": "#39c07a", "imu": "#9b6bd8",
                "mmwave": "#f0a02a", "wifi": "#e8465a", "ble": "#7a8394"})
    LAB = dict(lidar="激光雷达", camera="摄像头", imu="可穿戴 IMU",
               mmwave="毫米波", wifi="WiFi CSI", ble="蓝牙 RSSI")

    fig, axs = plt.subplots(1, 2, figsize=(14.2, 5.9),
                            gridspec_kw=dict(width_ratios=[1.55, 1]))
    fig.patch.set_facecolor(C["bg"])
    for ax in axs:
        ax.set_facecolor(C["bg"])
        ax.tick_params(colors=C["fg"], labelsize=9)
        for sp in ax.spines.values():
            sp.set_color(C["grid"])
        ax.grid(alpha=.22, color=C["grid"], lw=.6)

    # 左：ROC 族，x 轴是每天误报次数（对数）
    ax = axs[0]
    taus = np.linspace(0.0, 12.0, 900)
    for s, r in out.items():
        mu = dict(r["mu"])
        nn = dict(N_SCEN)
        if unknown_n > 0:
            mu["_unknown"] = unknown_rel * r["d"]
            nn["_unknown"] = unknown_n
        lam, pd = roc_curve(mu, taus, nn)
        m = (lam > 1e-5) & (lam < 3.0)
        LS = dict(lidar="-", camera="--", imu="-.", mmwave="-", wifi="--",
                  ble=":")
        ax.plot(lam[m], pd[m] * 100, color=C["c"][s], lw=2.1, ls=LS[s],
                label=LAB[s])
        ax.plot([r["fa"]], [r["pd"] * 100], "o", color=C["c"][s], ms=7,
                mec="#111", mew=.8)
    ax.axvline(TARGET_FA, color="#e8e8e8", ls="--", lw=1.2)
    ax.text(TARGET_FA * 1.06, 42, "本期判据\n0.1 次/天", color="#e8e8e8",
            fontsize=9, va="bottom")
    ax.axvline(1.0, color="#8a93a5", ls=":", lw=1.1)
    ax.text(1.06, 62, "1 次/天\n响应只剩 37%", color="#8a93a5", fontsize=8.5,
            va="bottom")
    ax.set_xscale("log")
    ax.set_xlim(1e-4, 1.6)
    ax.set_ylim(0, 101)
    ax.set_xlabel("每天误报次数 Λ（对数轴）", color=C["fg"], fontsize=10)
    ax.set_ylabel("检出率 $P_d$ (%)", color=C["fg"], fontsize=10)
    ax.set_title("ROC 族：每条曲线的圆点是「0.1 次/天」下的工作点",
                 color=C["fg"], fontsize=11)
    ax.legend(fontsize=8.5, facecolor=C["bg"], edgecolor=C["grid"],
              labelcolor=C["fg"], loc="lower right", bbox_to_anchor=(1.0, 0.02),
              framealpha=.92)

    # 右：准确率陷阱
    ax = axs[1]
    order = sorted(out, key=lambda k: -out[k]["pd"])
    y = np.arange(len(order))
    pdv = [out[s]["pd"] * 100 for s in order]
    accv = [out[s]["acc"] * 100 for s in order]
    ax.barh(y + .19, pdv, height=.36, color=[C["c"][s] for s in order],
            label="0.1 次/天下的检出率")
    ax.barh(y - .19, accv, height=.36, color="#555d6d",
            label="平衡测试集「准确率」")
    for i, (p, a) in enumerate(zip(pdv, accv)):
        ax.text(p + 1.2, i + .19, f"{p:.0f}%", color=C["fg"], va="center",
                fontsize=8)
        ax.text(a + 1.2, i - .19, f"{a:.0f}%", color="#aab", va="center",
                fontsize=8)
    ax.set_yticks(y)
    ax.set_yticklabels([LAB[s] for s in order], color=C["fg"], fontsize=9)
    ax.set_xlim(0, 118)
    ax.set_xlabel("百分比", color=C["fg"], fontsize=10)
    ax.set_title("准确率陷阱：同样一个系统，两个指标差多少", color=C["fg"],
                 fontsize=11)
    ax.legend(fontsize=8, facecolor=C["bg"], edgecolor=C["grid"],
              labelcolor=C["fg"], loc="upper right")

    fig.suptitle("W56 · 判据不是准确率，是每天误报几次"
                 f"（合成模型，{'工程实际口径' if unknown_n > 0 else '已知负样本'}）",
                 color=C["fg"], fontsize=13, y=.985)
    fig.tight_layout(rect=(0, 0, 1, .955))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140, facecolor=C["bg"])
    plt.close(fig)
    return path


# ============================================================
# 5. 自检
# ============================================================
def selftest() -> int:
    r"""八条断言：概率函数、门限求解、单调性、响应模型。"""
    k = 0

    def ck(c: bool, m: str) -> None:
        nonlocal k
        if not c:
            raise AssertionError("[X] " + m)
        k += 1
        print(f"  [OK] {m}")

    ck(abs(float(Q(0.0)) - 0.5) < 1e-12, f"① Q(0)=0.5")
    ck(abs(float(Q(1.0)) - 0.158655) < 1e-5, f"② Q(1)=0.158655")
    ck(abs(float(Q(4.7534)) - 1e-6) < 2e-8, f"③ Q(4.7534)≈1e-6")

    mu = {"fall": 5.0, "sofa": 0.0, "walk": -3.0}
    n = {"fall": 0.01, "sofa": 3, "walk": 40}
    tau = solve_tau(mu, n, 0.1, 20.0)
    lam = fa_rate(tau, mu, n, 20.0)
    ck(lam <= 0.1 + 1e-9, f"④ 门限求解满足约束：Λ={lam:.4f} ≤ 0.1")
    ck(fa_rate(tau + 0.05, mu, n, 20.0) < lam,
       "⑤ 门限抬高误报必降（单调性）")

    # 结构性失效：若某个负样本比摔倒得分还高，门限被它顶到摔倒之上
    mu_bad = {"fall": 1.0, "walk": 3.0}
    n_bad = {"fall": 0.011, "walk": 40.0}
    tau_bad = solve_tau(mu_bad, n_bad, 0.1, 20.0)
    pd_bad = float(Q(tau_bad - mu_bad["fall"]))
    ck(pd_bad < 0.02, f"⑥ 负样本比摔倒还高分时，检出率被压到 {pd_bad*100:.3f}%"
                      f"（门限 τ={tau_bad:.2f} 高过摔倒得分 1.00）")

    ck(abs(math.exp(-0.1 / LAMBDA0) - 0.9048) < 1e-4,
       f"⑦ 0.1 次/天 ⇒ 响应概率 {math.exp(-0.1):.3f}")
    ck(abs(math.exp(-1.0 / LAMBDA0) - 0.3679) < 1e-4,
       f"⑧ 1 次/天 ⇒ 响应概率 {math.exp(-1.0):.3f}")
    print(f"\n  自检通过：{k} 条断言")
    return k


# ============================================================
# 6. CLI
# ============================================================
def main() -> int:
    ap = argparse.ArgumentParser(
        description="从可分性算「每天误报次数 vs 检出率」，这是全期的主图。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="判据是每小时误报率，不是准确率。")
    ap.add_argument("--scenario", default="bedroom", choices=sorted(N_PER_DAY),
                    help="bedroom=独居卧室（默认）｜nh=养老院多人间")
    ap.add_argument("--target", type=float, default=TARGET_FA,
                    help="每天误报上限（默认 0.1）")
    ap.add_argument("--n-gate", type=float, default=None,
                    help="门控每天误开次数（缺省按场景：卧室 5、养老院 20）")
    ap.add_argument("--unknown-n", type=float, default=0.0,
                    help="每天未建模活动次数（默认 0 = 只算 6 类已知负样本）")
    ap.add_argument("--unknown-rel", type=float, default=0.45,
                    help="未知活动的相对可分性（默认 0.45）")
    ap.add_argument("--n", type=int, default=120, help="特征统计的蒙特卡洛次数")
    ap.add_argument("--jitter", type=float, default=1.0, help="类内变异倍数")
    ap.add_argument("--force", action="store_true", help="强制重算特征统计")
    ap.add_argument("--fig", nargs="?", const="", default=None, help="出主图")
    ap.add_argument("--json", nargs="?", const="", default=None, help="落盘结果")
    ap.add_argument("--sweep", action="store_true",
                    help="另跑未知项/门控/判据/类内变异的敏感性扫描")
    ap.add_argument("--selftest", action="store_true", help="跑断言自检")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]

    if args.selftest:
        print("=" * 80)
        print("  roc_daily.py 自检")
        print("=" * 80)
        selftest()
        return 0

    st = load_stats(root, n=args.n, jitter=args.jitter, force=args.force)
    if args.n_gate is None:
        args.n_gate = GATE_BY_SCEN[args.scenario]
    global N_SCEN
    N_SCEN = dict(N_PER_DAY[args.scenario])

    res = report(st, args.scenario, args.target, args.n_gate,
                 args.unknown_n, args.unknown_rel)

    if args.sweep:
        SEN = ("lidar", "camera", "imu", "mmwave", "wifi")
        print("=" * 88)
        print("  敏感性 A：每天还有多少次「未建模活动」（同样的可分性比例 r）")
        print("=" * 88)
        print("  ★ 这一项决定绝对水平。已知负样本只给出上界；")
        print("    真实系统的误报主要来自没被列进表里的活动。")
        print()
        for rel in (0.60, 0.85):
            print(f"  r = {rel}（未知活动的可分性取最坏已知负样本的 {rel:.0%}）")
            print("  " + f"{'传感':<9}" + "".join(f"{f'{u}/天':>10}" for u in (0, 20, 60, 150)))
            tab = {}
            for u in (0, 20, 60, 150):
                tab[u] = report(st, args.scenario, args.target, args.n_gate, u,
                                rel, verbose=False)
            for s in SEN:
                if s in tab[0]:
                    print(f"  {s:<9}" + "".join(
                        f"{tab[u][s]['pd']*100:>9.1f}%" for u in tab))
            print()

        print("=" * 88)
        print("  敏感性 B：门控每天误开几次（它独自把门限顶到 Q^-1(0.1/n_gate)）")
        print("=" * 88)
        for g in (0, 2, 5, 20, 100):
            r = report(st, args.scenario, args.target, g, args.unknown_n,
                       args.unknown_rel, verbose=False)
            line = "  ".join(f"{s}:{r[s]['pd']*100:5.1f}%" for s in SEN)
            print(f"  门控 {g:>4}/天 ⇒ {line}")
        print()

        print("=" * 88)
        print("  敏感性 C：把判据从 0.1 次/天放宽到 1 次/天，检出率涨多少")
        print("=" * 88)
        for t in (0.01, 0.1, 0.3, 1.0, 3.0):
            r = report(st, args.scenario, t, args.n_gate, args.unknown_n,
                       args.unknown_rel, verbose=False)
            line = "  ".join(f"{s}:{r[s]['pd']*100:5.1f}%" for s in SEN)
            print(f"  目标 {t:>5}/天 ⇒ {line}")
        print("  ★ 同一个系统，判据从 1 次/天收紧到 0.1 次/天，检出率普遍掉十几到几十点；")
        print("    而 1 次/天时人的响应概率只有 37% ⇒ 那点检出率涨得毫无意义。")
        print()

        print("=" * 88)
        print("  敏感性 D：类内变异放大（不同人、不同房间、换季）")
        print("=" * 88)
        for j in (1.0, 1.4, 1.8):
            if abs(j - args.jitter) < 1e-9:
                sj = st
            else:
                sj = SC.run(n=args.n, jitter=j, verbose=False)   # 不落盘，避免污染基线
            r = report(sj, args.scenario, args.target, args.n_gate,
                       args.unknown_n, args.unknown_rel, verbose=False)
            line = "  ".join(f"{s}:{r[s]['pd']*100:5.1f}%" for s in SEN)
            print(f"  抖动 ×{j:.1f} ⇒ {line}")
        print()

    if args.fig is not None:
        p = Path(args.fig) if args.fig else root / "results" / "figs" / "fig_roc_daily.png"
        make_fig(res, p, args.scenario, args.unknown_n, args.unknown_rel)
        print(f"  [OK] 图：{p}")

    if args.json is not None:
        p = Path(args.json) if args.json else root / "results" / "roc_daily.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        keep = {s: {k: v for k, v in r.items()} for s, r in res.items()}
        p.write_text(json.dumps(dict(scenario=args.scenario, target=args.target,
                                     n_gate=args.n_gate,
                                     unknown_n=args.unknown_n,
                                     unknown_rel=args.unknown_rel,
                                     res=keep),
                                ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [OK] JSON：{p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
