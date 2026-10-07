#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W48 · 问题 4 核心：**空间分辨率随深度的变化**（FWHM(z)）。

## 一、为什么用 FWHM

光在强散射介质里被"糊"开。要量化"糊到什么程度"，
最直接的量是**点扩散函数（PSF）的半高全宽 FWHM**：

* 若 FWHM $\lesssim$ 单细胞尺度（约 **10 µm**）=> **单细胞精度**；
* 若 FWHM 达到数百 µm => 只能"点亮一片"。

## 二、★★ 一个必须写明的建模选择：几何 vs 弹道

**纯粹的扩散解没有有限的 FWHM。**
在球对称点源解里，横向剖面 $\Phi(\rho)$ 在 $\rho=0$ 处是
$1/\rho$ 型**对数发散**，FWHM 恒为 0 —— 这不是物理，是扩散近似在
**近源区失效**的体现（扩散假设光子已充分随机化）。

**正确做法**：引入**弹道（直达）成分**。光在组织里可分解为

$$
\Phi = \underbrace{\Phi_{\text{ballistic}}}_{\text{未散射，仅几何扩散}}
+ \underbrace{\Phi_{\text{diffuse}}}_{\text{多次散射后}}
$$

* **浅层**（$z\lesssim\ell_{\text{tr}}$）：弹道项主导 => PSF 窄，**能分辨单细胞**；
* **深层**（$z\gg\ell_{\text{tr}}$）：扩散项主导 => PSF 宽，**分辨率失效**。

**本脚本按此二成分模型计算 FWHM(z)**，并给出**交叉深度**。

### 弹道成分（解析）

点源在深度 $z_s$、波长 $\lambda$，探测点在 $(x,0,z_s)$ 平面
（源正上方沿 $x$ 方向扫描）：

$$
\Phi_{\text{bal}}(x,z_s)=\frac{P_0\,e^{-\mu_t\sqrt{x^2+z_s^2}}}
{4\pi\,(x^2+z_s^2)}
$$

### 扩散成分（球对称解析解）

$$
\Phi_{\text{dif}}(r)=\frac{P_0\,e^{-r/\delta}}{4\pi D r},
\qquad r=\sqrt{x^2+z_s^2}
$$

> **诚实声明**：这是**一阶唯象模型**。
> 它把"弹道"与"扩散"直接相加，**没有做通量守恒的严格拼接**
> （真实的拼接需要 $\delta$ 函数源 + 外推边界 + 角度分辨的边界条件）。
> 它的价值在于给出**尺度与趋势**，不应被当作精确解。

## 三、输出

* 各波长、灰质/白质下的 **FWHM(z)** 曲线；
* **"单细胞精度（10 µm）"的最大可行深度**；
* **精度–深度相图**的数据（供作图）。

用法：
    $PY q4_fwhm.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "episodes" / "2026-W48" / "scripts"))
from tissue_optics import derived, LAMS, G                      # noqa: E402

RES = ROOT / "episodes" / "2026-W48" / "results"
RES.mkdir(parents=True, exist_ok=True)

SINGLE_CELL_UM = 10.0        # "单细胞精度"的判据（µm）


def psf_profile(x_cm: np.ndarray, z_s_cm: float, mu_t: float, mu_a: float,
                D: float, delta: float, P0: float = 1.0,
                ball_weight: float = 1.0) -> dict:
    r"""返回弹道项、扩散项及其和的横向剖面。"""
    r = np.sqrt(x_cm ** 2 + z_s_cm ** 2)
    r = np.maximum(r, 1e-12)
    bal = P0 * np.exp(-mu_t * r) / (4 * np.pi * r ** 2)
    dif = P0 * np.exp(-r / delta) / (4 * np.pi * D * r)
    return {"ballistic": ball_weight * bal, "diffuse": dif,
            "total": ball_weight * bal + dif, "r_cm": r}


def fwhm_mm(x_cm: np.ndarray, y: np.ndarray) -> float:
    r"""数值求半高全宽（单位 mm）。

    先在峰值两侧找到首次降到半高以下的点，再**线性插值**细化 ——
    只用最近网格点会让 FWHM 依赖网格（浅层尤其严重）。
    """
    half = 0.5 * y.max()
    above = y >= half
    if not above.any():
        return float("nan")
    i_pk = int(np.argmax(y))
    # 左边界
    i_l = i_pk
    while i_l > 0 and above[i_l - 1]:
        i_l -= 1
    # 右边界
    i_r = i_pk
    n = len(y)
    while i_r < n - 1 and above[i_r + 1]:
        i_r += 1
    def interp(i_in, i_out):
        if i_out < 0 or i_out >= n or y[i_in] == y[i_out]:
            return x_cm[i_in]
        t = (half - y[i_in]) / (y[i_out] - y[i_in])
        return x_cm[i_in] + t * (x_cm[i_out] - x_cm[i_in])
    xl = interp(i_l, i_l - 1) if i_l > 0 else x_cm[0]
    xr = interp(i_r, i_r + 1) if i_r < n - 1 else x_cm[-1]
    return float((xr - xl) * 10.0)          # cm -> mm


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xmax-mm", type=float, default=12.0)
    ap.add_argument("--nx", type=int, default=240001)
    ap.add_argument("--zmin-um", type=float, default=20.0)
    ap.add_argument("--zmax-mm", type=float, default=5.0)
    ap.add_argument("--nz", type=int, default=120)
    args = ap.parse_args()

    print("=" * 92)
    print("  W48 · 问题 4：空间分辨率随深度的变化 FWHM(z)")
    print("=" * 92)
    print(f"\n  [!] 建模选择：弹道项 + 扩散项（纯扩散解的 FWHM 恒为 0，不可用）")
    print(f"  单细胞精度判据：FWHM <= {SINGLE_CELL_UM} um")
    print(f"  证据：光在 ~l_tr 以内还没'随机化'，行为是弹道的（见 q1 结果 §4）")

    x = np.linspace(-args.xmax_mm / 10.0, args.xmax_mm / 10.0, args.nx)
    zs = np.geomspace(args.zmin_um / 1e4, args.zmax_mm / 10.0, args.nz)

    out = {"单细胞判据_um": SINGLE_CELL_UM, "曲线": {}, "最大单细胞深度_mm": {}}
    for kind in ("gray", "white"):
        for lam in LAMS:
            d = derived(kind, lam)
            mu_t = d["mu_a_per_cm"] + d["mu_s_per_cm"]
            fw = np.array([fwhm_mm(x, psf_profile(x, z, mu_t,
                                                  d["mu_a_per_cm"], d["D_cm"],
                                                  d["delta_cm"])["total"])
                           for z in zs])
            key = f"{kind}_{lam}nm"
            out["曲线"][key] = {"z_mm": (zs * 10).tolist(),
                                "fwhm_mm": fw.tolist()}
            ok = fw * 1000.0 <= SINGLE_CELL_UM
            zmax = float(zs[ok].max() * 10) if ok.any() else 0.0
            out["最大单细胞深度_mm"][key] = zmax

    # ── 打印灰质（主要结果）──
    print(f"\n  -- 灰质 FWHM(z)（单位 um）--")
    hdr = "     " + f"{'z(um)':>9}" + "".join(
        f"{str(l)+'nm':>11}" for l in LAMS)
    print(hdr)
    idx = np.unique(np.linspace(0, args.nz - 1, 14).astype(int))
    for i in idx:
        row = f"     {zs[i]*1e4:>9.0f}"
        for lam in LAMS:
            row += f"{out['曲线'][f'gray_{lam}nm']['fwhm_mm'][i]*1000:>11.1f}"
        print(row)

    print(f"\n  -- 单细胞精度（FWHM <= {SINGLE_CELL_UM:.0f} um）的最大深度 --")
    print(f"     {'波长':>8}{'灰质(um)':>12}{'白质(um)':>12}")
    for lam in LAMS:
        g = out["最大单细胞深度_mm"][f"gray_{lam}nm"] * 1000
        w = out["最大单细胞深度_mm"][f"white_{lam}nm"] * 1000
        print(f"     {lam:>6}nm{g:>12.0f}{w:>12.0f}")

    print(f"\n  -- 与穿透深度 delta 对比（灰质，um）--")
    print(f"     {'波长':>8}{'delta(um)':>12}{'最大单细胞深度(um)':>20}"
          f"{'比值':>10}")
    for lam in LAMS:
        d = derived("gray", lam)
        g = out["最大单细胞深度_mm"][f"gray_{lam}nm"] * 1000
        print(f"     {lam:>6}nm{d['delta_mm']*1000:>12.0f}{g:>20.0f}"
              f"{(g/(d['delta_mm']*1000) if d['delta_mm'] else 0):>10.2f}")

    p = RES / "q4_fwhm.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
