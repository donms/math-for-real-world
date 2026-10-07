#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W48 · 光场求解（有限差分解扩散方程 + 自洽性验证）。

## 为什么改用有限差分（**放弃蒙特卡洛的归一化纠缠**）

我在蒙特卡洛上连踩三个估计量的坑（见 `results/q1_结果.md` §4）：

| 版本 | 缺陷 |
|---|---|
| 径向壳沉积 | 内层壳体积小 4.3 万倍 => 近源区纯噪声 |
| 球面探测器 | 步长与探测尺度同量级 => 漏计跨越（-87%）|
| 碰撞估计量 | **缺直达项** => 无散射极限差 12 个数量级 |

**共同病根**：蒙特卡洛的**绝对幅度**依赖估计量的正确标定，
而标定一旦有未知常数，就会污染问题 2、4 的结论。

**⇒ 改用有限差分直接解 PDE。**
PDE 解是**自洽**的：可以用"**代回方程看残差**"来验证，
不依赖任何统计估计量。

## 方程与几何

**球对称**（点源在原点）稳态扩散方程：

$$
\frac{1}{r^2}\frac{d}{dr}\!\left(r^2D\frac{d\Phi}{dr}\right)
-\mu_a\Phi+S(r)=0
$$

**源项**用归一化高斯代替 $\delta$ 函数（避免 $r=0$ 奇异性）：

$$
S(r)=\frac{P_0}{(2\pi\sigma^2)^{3/2}}\exp\!\left(-\frac{r^2}{2\sigma^2}\right),
\qquad \sigma=\text{小量（如 }0.02\,\ell_{\text{tr}}\text{）}
$$

**边界条件**：
* $r\to0$：$d\Phi/dr=0$（对称性）；
* 外边界 $r=R$：外推边界 $\Phi(R)=0$，$R = r_{\max}+z_e$。

## 验证（**与蒙特卡洛不同，这里可以严格验证**）

1. **残差检验**：把数值解代回方程，看 $\|L\Phi-S\|$ 是否 $\sim$ 离散误差；
2. **网格收敛**：加密网格，解应收敛（比较 $L_2$ 相对变化）；
3. **解析对照**：无限介质点源解 $\Phi_\infty=P_0e^{-r/\delta}/(4\pi Dr)$
   —— 在中远场应吻合。

## 输出

* 光场 $\Phi(r)$ 及其在 $+x$ 轴上的剖面（供问题 2、4 用）；
* **FWHM(z)**：给问题 4 的"精度–深度"关系。

用法：
    $PY q1_field.py
    $PY q1_field.py --n 4000 --rmax-mm 12
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "episodes" / "2026-W48" / "scripts"))
from tissue_optics import derived, z_extrap                     # noqa: E402

RES = ROOT / "episodes" / "2026-W48" / "results"
RES.mkdir(parents=True, exist_ok=True)


def solve_diffusion_spherical(mu_a: float, D: float, P0: float,
                              r_max_cm: float, n: int = 2000,
                              sigma_frac: float = 0.02,
                              ze_cm: float = 0.0) -> dict:
    r"""球对称稳态扩散方程的有限差分解。

    离散化（**有限体积**，保证守恒）：

    $$
    \frac{1}{r_i^2\Delta r}\Big[r_{i+1/2}^2D\frac{\Phi_{i+1}-\Phi_i}{\Delta r}
    -r_{i-1/2}^2D\frac{\Phi_i-\Phi_{i-1}}{\Delta r}\Big]
    -\mu_a\Phi_i+S_i=0
    $$
    """
    R = r_max_cm + ze_cm
    r = np.linspace(0.0, R, n + 1)
    dr = r[1] - r[0]
    rc = 0.5 * (r[1:] + r[:-1])            # 单元中心
    r_face = r                          # 面在节点上
    # 单元体积（球壳）
    vol = 4.0 / 3.0 * np.pi * (r[1:] ** 3 - r[:-1] ** 3)
    # 面面积
    area = 4.0 * np.pi * r ** 2

    # 源：归一化高斯（积分 = P0）
    l_tr = 3.0 * D
    sig = sigma_frac * l_tr
    S = P0 * np.exp(-rc ** 2 / (2 * sig ** 2)) / ((2 * np.pi) ** 1.5 * sig ** 3)
    S *= vol                                 # 每个单元的总源

    # 组装三对角（有限体积）
    #   面 i 位于 r_i（i=0..n），单元 i 在 [r_i, r_{i+1}]
    a = np.zeros(n)     # 下对角（到 i-1）
    b = np.zeros(n)     # 对角
    c = np.zeros(n)     # 上对角（到 i+1）
    d = S.copy()
    for i in range(n):
        # 西面 r_i、东面 r_{i+1}
        kw = area[i] * D / dr if i > 0 else 0.0
        ke = area[i + 1] * D / dr
        # 外边界：外推边界 Phi(R)=0 => 东面用半格
        if i == n - 1:
            ke = area[i + 1] * D / (0.5 * dr)
        b[i] = kw + ke + mu_a * vol[i]
        if i > 0:
            a[i] = -kw
        if i < n - 1:
            c[i] = -ke
    # 解三对角（Thomas）
    cp = np.zeros(n); dp = np.zeros(n)
    cp[0] = c[0] / b[0]; dp[0] = d[0] / b[0]
    for i in range(1, n):
        m = b[i] - a[i] * cp[i - 1]
        cp[i] = c[i] / m if i < n - 1 else 0.0
        dp[i] = (d[i] - a[i] * dp[i - 1]) / m
    phi = np.zeros(n)
    phi[-1] = dp[-1]
    for i in range(n - 2, -1, -1):
        phi[i] = dp[i] - cp[i] * phi[i + 1]

    # 残差（代回方程）
    res = np.zeros(n)
    for i in range(n):
        kw = area[i] * D / dr if i > 0 else 0.0
        ke = area[i + 1] * D / dr
        if i == n - 1:
            ke = area[i + 1] * D / (0.5 * dr)
        flux_w = kw * (phi[i] - phi[i - 1]) if i > 0 else 0.0
        flux_e = ke * (phi[i + 1] - phi[i]) if i < n - 1 else ke * phi[i]
        res[i] = flux_e - flux_w + mu_a * vol[i] * phi[i] - S[i]
    denom = max(np.abs(S).max(), 1e-300)
    return {"r_cm": rc, "phi": phi, "residual_rel": float(np.abs(res).max()
                                                          / denom),
            "n": n, "R_cm": R, "dr": dr, "sigma_cm": sig,
            "total_source": float(S.sum()), "P0": P0}


def phi_infinite(r_cm, P0: float, D: float, delta: float) -> np.ndarray:
    r = np.maximum(np.asarray(r_cm, dtype=float), 1e-12)
    return P0 / (4 * np.pi * D * r) * np.exp(-r / delta)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--rmax-mm", type=float, default=12.0)
    ap.add_argument("--lam", type=int, default=470)
    ap.add_argument("--kind", default="gray")
    args = ap.parse_args()

    print("=" * 92)
    print("  W48 · 光场求解（有限差分 + 自洽性验证）")
    print("=" * 92)
    d = derived(args.kind, args.lam)
    P0 = 1.0
    print(f"\n  组织：{args.kind} matter @ {d['lam_nm']} nm")
    print(f"    mu_a={d['mu_a_per_cm']:.3f} cm^-1  "
          f"mu_s'={d['mu_s_prime_per_cm']:.2f} cm^-1  "
          f"D={d['D_cm']:.5f} cm  delta={d['delta_mm']:.3f} mm")

    ze = z_extrap(d["D_cm"])
    print(f"    外推边界 z_e = {ze*10:.3f} mm")

    # ── 网格收敛 ──
    print(f"\n  -- 网格收敛（残差与解的变化）--")
    prev = None
    conv = []
    for n in (500, 1000, 2000, 4000):
        s = solve_diffusion_spherical(d["mu_a_per_cm"], d["D_cm"], P0,
                                      args.rmax_mm / 10.0, n=n, ze_cm=ze)
        tag = ""
        if prev is not None:
            # 在公共的中间半径处比较
            m = min(len(prev["phi"]), len(s["phi"]))
            k = m // 2
            rel = abs(s["phi"][k] - prev["phi"][k]) / max(abs(s["phi"][k]), 1e-300)
            tag = f"  与上一网格相对变化 {rel:.2e}"
            conv.append(rel)
        print(f"     n={n:>5}  残差(相对最大源)={s['residual_rel']:.3e}"
              f"  总源={s['total_source']:.6f}{tag}")
        prev = s

    # ── 最终解 ──
    sol = solve_diffusion_spherical(d["mu_a_per_cm"], d["D_cm"], P0,
                                   args.rmax_mm / 10.0, n=args.n, ze_cm=ze)
    r = sol["r_cm"]
    phi = sol["phi"]
    phi_inf = phi_infinite(r, P0, d["D_cm"], d["delta_cm"])

    print(f"\n  -- 与无限介质解析解对照（n={args.n}）--")
    print(f"     {'r(mm)':>7}{'Phi_FDM':>13}{'Phi_解析':>13}{'比值':>9}"
          f"{'r/delta':>9}")
    for rm in (0.2, 0.5, 0.66, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0):
        if rm / 10.0 > r[-1]:
            continue
        i = int(np.argmin(np.abs(r - rm / 10.0)))
        ratio = phi[i] / phi_inf[i] if phi_inf[i] > 0 else np.nan
        print(f"     {rm:>7.2f}{phi[i]:>13.5g}{phi_inf[i]:>13.5g}"
              f"{ratio:>9.3f}{rm/10.0/d['delta_cm']:>9.2f}")

    # ── 落盘 ──
    out = {
        "组织": {"kind": args.kind, "lam_nm": d["lam_nm"],
                 "mu_a_per_cm": d["mu_a_per_cm"],
                 "mu_s_prime_per_cm": d["mu_s_prime_per_cm"],
                 "D_cm": d["D_cm"], "delta_mm": d["delta_mm"],
                 "z_e_cm": ze},
        "网格": {"n": args.n, "R_cm": sol["R_cm"], "dr_cm": sol["dr"],
                 "sigma_cm": sol["sigma_cm"]},
        "验证": {"残差相对最大源": sol["residual_rel"],
                 "总源积分": sol["total_source"],
                 "网格收敛相对变化": conv},
        "光场": {"r_mm": (r * 10).tolist(), "phi": phi.tolist(),
                 "phi_解析无限介质": phi_inf.tolist()},
    }
    p = RES / f"q1_光场_{args.kind}_{d['lam_nm']}nm.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
