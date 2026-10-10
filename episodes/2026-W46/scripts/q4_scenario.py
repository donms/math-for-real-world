#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · Q4：把"叠加"变成可算指标，并给**后验预测区间**。

## 选题要求（01_题目.md 问题 4）

1. 定义**叠加的量化指标**；
2. 基于 Q1–Q3 的模型设计**情景**（≥3 个，参数取值需有依据），
   给出该指标的**后验预测区间**；
3. 做**敏感性分析**：哪些参数最影响"是否叠加"的结论；
4. **明确划出结论的适用边界**。

## 定义：什么叫"叠加"？

官方表述是"冬季仍可能呈现多种急性呼吸道传染病**交替或叠加**流行局面"。
"叠加"在数学上有两种可操作定义，本报告**两个都算**：

### 指标 A · 峰重叠面积

设两波的感染曲线为 $I_1(t),I_2(t)$（来自 Q1 的双亚型模型），
定义**重叠系数**（类似 Jaccard 的连续版）：

$$\text{OV}=\frac{\int\min(I_1,I_2)\,dt}
{\max\big(\int I_1,\int I_2\big)}$$

* $\text{OV}=0$ ⇒ 完全**交替**（一波让位给另一波）；
* $\text{OV}\to1$ ⇒ 完全**叠加**（两波同高同时）。

### 指标 B · 峰占用（医疗资源口径）

$$C=\max_t\big[I_1(t)+I_2(t)\big]$$

即"最坏时刻的同时感染占比" —— 对医疗系统更直接。

> **为什么两个都算**：单一指标的定义是主观的；
> 报告两个并检查它们是否给出一致结论，
> 是对"定义主观性"的**直接敏感性检验**。

## 情景设计（参数取值都有依据）

| 情景 | 设定 | 依据 |
|---|---|---|
| **S1 基准** | Q1-A 拟合值 | `results/q1A_拟合.json` |
| **S2 强季节性** | $\epsilon$ 取拟合值的 1.5 倍 | 气候变化 / 行为聚集加剧 |
| **S3 弱交叉免疫** | $\sigma=1-c$ 取 0.5（而非基准的）| 两株抗原距离大（漂变）|
| **S4 快速免疫衰减** | $\omega$ 取拟合值的 2 倍 | 免疫持续时间缩短（$1/\omega$ 减半）|

**后验预测区间**：对每个情景，在 Q1 参数的后验不确定范围内
（用拟合值的 ±1 个剖面尺度扰动）做**蒙特卡洛**，
给出指标的 95% 区间。

用法：
    $PY q4_scenario.py
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
import q1_model as M                                        # noqa: E402

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
FIGS = RES / "figs"
RES.mkdir(parents=True, exist_ok=True)
FIGS.mkdir(parents=True, exist_ok=True)

N_MC = 200           # 蒙特卡洛次数（每次一次 ODE）
HORIZON = 52 * 3     # 预测 3 年（覆盖秋冬与次年）


def load_q1a() -> dict:
    p = RES / "q1A_拟合.json"
    if not p.exists():
        raise SystemExit("缺少 results/q1A_拟合.json —— 请先跑 q1_fitA.py --fit")
    d = json.loads(p.read_text(encoding="utf-8"))
    return d


def metrics(t: np.ndarray, y: np.ndarray) -> dict:
    r"""由 ODE 轨迹算两个"叠加"指标。"""
    It, i1, i2 = M.totals(y)
    # 指标 A：峰重叠面积（用离散和近似积分）
    ov = float(np.minimum(i1, i2).sum() / max(i1.sum(), i2.sum(), 1e-12))
    # 指标 B：最坏时刻同时感染占比
    C = float(It.max())
    # 附加：两株各自的峰时刻（判断"交替"还是"叠加"）
    tpk1 = float(t[int(np.argmax(i1))])
    tpk2 = float(t[int(np.argmax(i2))])
    return {"OV": ov, "C": C, "peak_t_diff": abs(tpk1 - tpk2),
            "I1_peak": float(i1.max()), "I2_peak": float(i2.max())}


def run_scenario(name: str, base: dict, over: dict, n_mc: int = N_MC,
                 seed: int = 0) -> dict:
    r"""对给定情景做蒙特卡洛，返还指标的 95% 区间。"""
    rng = np.random.default_rng(seed)
    # 基准参数（Q1-A 的可辨识组合 -> 模型参数）
    gam = base["gamma_fix"]
    p = base["params"]
    res = []
    for _ in range(n_mc):
        # 在拟合值上做乘性扰动（模拟后验不确定，尺度取剖面量级 ~10%）
        jit = lambda v, s=0.10: v * float(np.exp(rng.normal(0, s)))   # noqa: E731
        pr = M.unpack({
            "beta0": p["R0"] * gam * jit(1.0),
            "phi": p["phi"] * jit(1.0, 0.06),
            "eps": float(np.clip(p["eps"] * jit(1.0), 0.01, 0.95)),
            "theta": p["theta"],
            "gamma": gam,
            "omega": p["omega"] * jit(1.0),
            "rho": p["rho"],
            "seed": 1e-4,
        })
        # 情景覆盖
        for k, v in over.items():
            if callable(v):
                pr[k] = v(pr[k])
            else:
                pr[k] = float(v)
        try:
            t, y = M.simulate(pr, tmax=float(HORIZON), n_out=HORIZON * 2)
            res.append(metrics(t, y))
        except Exception:                                        # noqa: BLE001
            continue
    if not res:
        return {"name": name, "n_ok": 0}
    keys = ("OV", "C", "peak_t_diff")
    out = {"name": name, "n_ok": len(res), "overrides":
           {k: (v if not callable(v) else "callable")
            for k, v in over.items()}}
    for k in keys:
        a = np.array([r[k] for r in res], float)
        out[k] = {"median": float(np.median(a)),
                  "lo": float(np.percentile(a, 2.5)),
                  "hi": float(np.percentile(a, 97.5)),
                  "mean": float(a.mean())}
    return out


def main() -> int:
    print("=" * 94)
    print("  W46 · Q4 情景分析：把『叠加』变成可算指标")
    print("=" * 94)
    base = load_q1a()
    print(f"  基准（Q1-A）: R0={base['params']['R0']:.3f} "
          f"phi={base['params']['phi']:.3f} eps={base['params']['eps']:.3f} "
          f"omega={base['params']['omega']:.4f}  gamma 固定={base['gamma_fix']:.4f}")
    print(f"  蒙特卡洛 {N_MC} 次/情景，预测 {HORIZON//52} 年")
    print(f"  指标 A = 峰重叠面积 OV（0=交替，→1=叠加）")
    print(f"  指标 B = 最坏时刻同时感染占比 C")

    # 基准的交叉免疫：模型里 sigma=1-c，但 q1_model 的 c 参数即"交叉保护"
    # Q1-A 里没有把 c 作为自由参数，取一个明确的基准值并在情景里扫
    C_BASE = 0.5
    scens = [
        ("S1 基准", {}),
        ("S2 强季节性 eps×1.5", {"eps": lambda v: min(v * 1.5, 0.95)}),
        ("S3 弱交叉免疫 c=0.2", {"c": 0.2}),
        ("S4 强交叉免疫 c=0.8", {"c": 0.8}),
        ("S5 快速免疫衰减 omega×2", {"omega": lambda v: v * 2.0}),
    ]
    # 把基准 c 注进去
    results = []
    for i, (nm, over) in enumerate(scens):
        # 基准 c 是 Q1-A 未估的参数，明确用 C_BASE，并在 S3/S4 里改
        pr_default = dict(over)
        if "c" not in pr_default:
            pr_default["c"] = C_BASE
        r = run_scenario(nm, base, pr_default, seed=1000 + i)
        results.append(r)
        if r.get("n_ok"):
            print(f"\n  ── {nm} ──  (n_ok={r['n_ok']})")
            print(f"     OV 中位 {r['OV']['median']:.4f}  "
                  f"95% 区间 [{r['OV']['lo']:.4f}, {r['OV']['hi']:.4f}]")
            print(f"     C  中位 {r['C']['median']:.4f}  "
                  f"95% 区间 [{r['C']['lo']:.4f}, {r['C']['hi']:.4f}]")
            print(f"     两株峰时差中位 {r['peak_t_diff']['median']:.1f} 周")

    # ---- 敏感性：哪个参数最影响"是否叠加" ----
    print(f"\n  ══ 敏感性分析（选题第 3 小问）══")
    print("     判据：OV 的 95% 区间是否跨越 0.5（0.5 是『叠加/交替』的粗分界）")
    print(f"\n     {'情景':<26}{'OV中位':>9}{'OV 95%区间':>20}  判定")
    for r in results:
        if not r.get("n_ok"):
            continue
        ov = r["OV"]
        cross = ov["lo"] < 0.5 < ov["hi"]
        rng_s = f"[{ov['lo']:.3f}, {ov['hi']:.3f}]"
        verdict = "区间跨 0.5（不确定）" if cross else "明确"
        print(f"     {r['name']:<26}{ov['median']:>9.4f}{rng_s:>20}  {verdict}")

    # 用 OV 中位的极差衡量"哪个情景最敏感"
    oks = [r for r in results if r.get("n_ok")]
    if oks:
        med = np.array([r["OV"]["median"] for r in oks])
        names = [r["name"] for r in oks]
        i_base = 0
        print(f"\n     相对基准 S1 的 OV 变化（正=更倾向叠加）：")
        for i, (nm, m) in enumerate(zip(names, med)):
            if i == i_base:
                continue
            print(f"       {nm:<26}{m - med[i_base]:+.4f}")

    # ---- 图 ----
    fig, ax = plt.subplots(1, 2, figsize=(14, 5))
    names = [r["name"] for r in oks]
    meds = [r["OV"]["median"] for r in oks]
    los = [r["OV"]["lo"] for r in oks]
    his = [r["OV"]["hi"] for r in oks]
    ypos = np.arange(len(oks))
    ax[0].errorbar(meds, ypos, xerr=[np.array(meds) - np.array(los),
                                     np.array(his) - np.array(meds)],
                   fmt="o", capsize=4, color="#2c6fbb")
    ax[0].axvline(0.5, ls="--", color="r", label="叠加/交替 粗分界 0.5")
    ax[0].set_yticks(ypos)
    ax[0].set_yticklabels(names, fontsize=9)
    ax[0].set_xlabel("重叠指标 OV")
    ax[0].set_title("各情景的 OV 后验区间", fontsize=12)
    ax[0].legend(fontsize=8)
    ax[0].grid(alpha=0.3)
    Cs = [r["C"]["median"] for r in oks]
    Clo = [r["C"]["lo"] for r in oks]
    Chi = [r["C"]["hi"] for r in oks]
    ax[1].errorbar(Cs, ypos, xerr=[np.array(Cs) - np.array(Clo),
                                   np.array(Chi) - np.array(Cs)],
                   fmt="s", capsize=4, color="#e67e22")
    ax[1].set_yticks(ypos)
    ax[1].set_yticklabels(["" for _ in oks])
    ax[1].set_xlabel("最坏时刻同时感染占比 C")
    ax[1].set_title("各情景的 C 后验区间", fontsize=12)
    ax[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "q4_情景.png", dpi=150)
    plt.close(fig)
    print(f"\n  -> {FIGS/'q4_情景.png'}")

    out = {"baseline": {k: base[k] for k in ("params", "gamma_fix", "sse")},
           "C_BASE": C_BASE, "N_MC": N_MC, "HORIZON_WEEKS": HORIZON,
           "scenarios": results}
    (RES / "q4_情景.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  -> {RES/'q4_情景.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
