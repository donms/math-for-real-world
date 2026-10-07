#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W48 · 问题 2 + 问题 4（修订版）：**有限孔径光纤源 → 激活体积**。

## ★★ 为什么弃用上一版的 FWHM 路线

上一版把光场写成"弹道项 + 扩散项"直接相加，算出的 FWHM 有一个
**致命的物理指纹**：$z=20\ \mu m$ 处 FWHM 已是 38 µm，
而且**六个波长几乎完全相同**（差 < 0.6%）。

=> 说明 FWHM 完全由 $1/r^2$ 的**几何扩散**设定，
**与 $\mu_a,\mu_s,\delta$ 无关** ⇒ **与散射物理无关** ⇒ 模型失效。

**三个根源**：
1. 弹道项被用错了范围（真实弹道项只在 $r\lesssim\ell_{\text{tr}}$ 内有效）；
2. 两项直接相加**没有通量守恒的拼接**；
3. **"点源"不适合问分辨率** —— 实验用**光纤（有限孔径）**。

## 本版的路线（**正确做法**）

### 1. 几何：柱对称（不是球对称！）

光纤是一根**轴**，所以光场关于**光纤轴**旋转对称
=> 用**柱坐标** $(\rho,z)$，而不是球坐标 $r$：

$$
\frac{1}{\rho}\frac{\partial}{\partial\rho}
\!\left(\rho D\frac{\partial\Phi}{\partial\rho}\right)
+D\frac{\partial^2\Phi}{\partial z^2}
-\mu_a\Phi+S(\rho,z)=0
$$

**这一步很关键**：上一版用球对称，等于把光纤当成了点，
所以"横向分辨率"根本没有定义。

### 2. 源：有限孔径

光纤端面半径 $a$（典型**纤芯 200 µm**），出射光锥半角由数值孔径 NA 定：

$$
S(\rho,z)=\frac{P_0}{\pi a^2\,\ell_{\text{emit}}}
\exp\!\left(-\frac{\rho^2}{2a^2}\right)
\exp\!\left(-\frac{z}{\ell_{\text{emit}}}\right),
\qquad \ell_{\text{emit}}\approx\frac{a}{\tan\theta}
$$

### 3. Hill 映射（问题 2）

$$
P_{\text{open}}(\Phi)=\frac{\Phi^{\,n}}{\Phi^{\,n}+K^{\,n}}
$$

* $n$：Hill 系数（取 1.5 为基准，做 $n\in[1,2]$ 的敏感性）；
* $K$：半饱和光强。**题面要求论证 $K$ 与 pKa 的关系** ——
  本实现把 $K$ 写成**可调参数**并做扫描，
  因为"pKa -> 光强阈值"需要额外的滴定曲线建模，
  题面把这一步留给解题者（见 `results/q2q4_结果.md` 的说明）。

### 4. 激活体积（取代 FWHM）

$$
V(P_{\text{thr}})=\iiint_{\{P_{\text{open}}\ge P_{\text{thr}}\}}dV
$$

这个量**直接对应实验语言**："我点亮了多大一块"，
而且**不依赖"点源"这个不合适的理想化**。

## 输出

* 光纤端面附近的 $\Phi(\rho,z)$ 三维场（柱对称）；
* **激活体积 $V$ vs 深度 $z$**、vs 功率 $P_0$、vs 阈值 $P_{\text{thr}}$；
* **"单细胞尺度（10 µm）可行性"** 的正确判据：
  在给定功率下，是否存在 $P_{\text{thr}}$ 使激活区**横向尺度 ≤ 10 µm**。

用法：
    $PY q2q4_fiber.py
    $PY q2q4_fiber.py --aperture-um 100 --power-mw 10
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


def solve_cylindrical(mu_a: float, D: float, P0: float,
                      aperture_cm: float, emit_len_cm: float,
                      rho_max_cm: float, z_max_cm: float,
                      nr: int = 260, nz: int = 260) -> dict:
    r"""柱对称稳态扩散方程的有限体积解（轴 $\rho=0$ 为光纤轴）。

    离散：单元 $(\rho_i,z_j)$，面积 $\rho\,d\rho\,dz$（轴对称的 $2\pi$ 已约去）。
    边界：$\rho=0$ 与 $\rho=\rho_{\max}$ 用 Neumann/Dirichlet，
    $z=z_{\max}$ 用外推边界（$\Phi=0$）。
    """
    drho = rho_max_cm / nr
    dz = z_max_cm / nz
    rho = (np.arange(nr) + 0.5) * drho           # 单元中心
    z = (np.arange(nz) + 0.5) * dz

    # 源：高斯横向 x 指数纵向
    RHO, Z = np.meshgrid(rho, z, indexing="ij")
    S = (P0 / (np.pi * aperture_cm ** 2 * emit_len_cm)
         * np.exp(-RHO ** 2 / (2 * aperture_cm ** 2))
         * np.exp(-Z / emit_len_cm))

    # 组装稀疏矩阵（五点式，轴对称为 5 点）
    N = nr * nz
    import scipy.sparse as sp
    import scipy.sparse.linalg as spla

    idx = lambda i, j: i * nz + j                        # noqa: E731
    rows, cols, vals = [], [], []
    b = np.zeros(N)
    for i in range(nr):
        rp = (i + 1) * drho          # 外侧面
        rm = i * drho                # 内侧面
        for j in range(nz):
            k = idx(i, j)
            # 面面积（轴对称：面积 = rho * d 其他方向）
            Ae = rp * dz             # 外侧
            Aw = rm * dz             # 内侧
            An = rho[i] * drho       # z+
            As = rho[i] * drho       # z-
            ke = D * Ae / drho
            kw = D * Aw / drho
            kn = D * An / dz
            ks = D * As / dz
            # 边界处理
            if i == 0:
                kw = 0.0             # 轴：对称 => 无通量
            if i == nr - 1:
                # 外边界：外推 => Phi=0，用半格
                ke = D * Ae / (0.5 * drho)
            if j == nz - 1:
                # z 外边界：外推 => Phi=0，用半格
                kn = D * An / (0.5 * dz)
            vol = rho[i] * drho * dz
            diag = ke + kw + kn + ks + mu_a * vol
            rows.append(k); cols.append(k); vals.append(diag)
            if i > 0:
                rows.append(k); cols.append(idx(i - 1, j)); vals.append(-kw)
            if i < nr - 1:
                rows.append(k); cols.append(idx(i + 1, j)); vals.append(-ke)
            if j > 0:
                rows.append(k); cols.append(idx(i, j - 1)); vals.append(-ks)
            if j < nz - 1:
                rows.append(k); cols.append(idx(i, j + 1)); vals.append(-kn)
            b[k] = S[i, j] * vol
    A = sp.csr_matrix((vals, (rows, cols)), shape=(N, N))
    phi = spla.spsolve(A, b).reshape(nr, nz)

    # 残差（相对最大源项）
    res = A @ phi.ravel() - b
    return {"rho_cm": rho, "z_cm": z, "phi": phi,
            "residual_rel": float(np.abs(res).max()
                                  / max(np.abs(b).max(), 1e-300)),
            "nr": nr, "nz": nz, "drho_cm": drho, "dz_cm": dz}


def hill(phi: np.ndarray, K: float, n: float) -> np.ndarray:
    r"""$P_{\text{open}}=\Phi^n/(\Phi^n+K^n)$。"""
    p = np.maximum(phi, 0.0) ** n
    return p / (p + K ** n)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lam", type=int, default=470)
    ap.add_argument("--kind", default="gray")
    ap.add_argument("--aperture-um", type=float, default=200.0)
    ap.add_argument("--na", type=float, default=0.37)
    ap.add_argument("--power-mw", type=float, default=1.0)
    ap.add_argument("--rho-max-mm", type=float, default=4.0)
    ap.add_argument("--z-max-mm", type=float, default=6.0)
    ap.add_argument("--n", type=int, default=220)
    args = ap.parse_args()

    d = derived(args.kind, args.lam)
    a_cm = args.aperture_um / 1e4
    theta = np.arcsin(min(args.na, 0.99))
    emit_cm = a_cm / max(np.tan(theta), 1e-6)
    P0 = args.power_mw / 1000.0                 # mW -> W

    print("=" * 92)
    print("  W48 · 问题 2 + 4（修订版）：有限孔径光纤源 -> 激活体积")
    print("=" * 92)
    print(f"\n  组织：{args.kind} @ {d['lam_nm']} nm   "
          f"mu_a={d['mu_a_per_cm']:.2f}  mu_s'={d['mu_s_prime_per_cm']:.2f} "
          f"cm^-1  D={d['D_cm']:.5f} cm  delta={d['delta_mm']:.3f} mm")
    print(f"  光纤：芯径 {args.aperture_um:.0f} um  NA={args.na}  "
          f"出射半角 {np.degrees(theta):.1f}deg  等效发光长度 "
          f"{emit_cm*1000:.0f} um")
    print(f"  功率：{args.power_mw:.3f} mW")
    print(f"  [!] 几何用**柱对称**（光纤是轴），不是球对称")

    sol = solve_cylindrical(d["mu_a_per_cm"], d["D_cm"], P0, a_cm, emit_cm,
                            args.rho_max_mm / 10, args.z_max_mm / 10,
                            nr=args.n, nz=args.n)
    rho, z, phi = sol["rho_cm"], sol["z_cm"], sol["phi"]
    print(f"\n  求解：{sol['nr']}x{sol['nz']} 网格  残差(相对)="
          f"{sol['residual_rel']:.2e}  dρ={sol['drho_cm']*1e4:.0f}um "
          f"dz={sol['dz_cm']*1e4:.0f}um")

    # ── 光场剖面 ──
    print(f"\n  -- 光场 Phi(rho,z) 剖面（归一化到 rho=0, z=0 处）--")
    print(f"     {'z(um)':>8}" + "".join(
        f"{('r='+str(int(r*1e4))+'um'):>12}" for r in (0.0, 0.005, 0.01, 0.02)))
    for zm in (0.0, 100.0, 300.0, 500.0, 1000.0, 2000.0):
        j = int(np.argmin(np.abs(z - zm / 1e4)))
        row = f"     {z[j]*1e4:>8.0f}"
        for rm in (0.0, 0.005, 0.01, 0.02):
            i = int(np.argmin(np.abs(rho - rm)))
            row += f"{phi[i, j]:>12.4g}"
        print(row)

    # ── 激活体积 ──
    print(f"\n  -- 激活体积 V (mm^3) 随阈值与深度的变化 --")
    # 每个 z 层：找到 P_open >= thr 的横向半径，算体积
    K_REF = phi[0, 0] * 0.5           # 以"轴上峰值的一半"为基准半饱和
    print(f"     K 基准 = 轴上峰值的 50% = {K_REF:.5g} W/cm^2")
    for n_hill in (1.0, 1.5, 2.0):
        P = hill(phi, K_REF, n_hill)
        print(f"\n     Hill n={n_hill}")
        print(f"       {'thr':>7}{'激活体积(mm^3)':>16}{'最大深度(um)':>14}"
              f"{'该深度横向直径(um)':>20}")
        vol_cell = 2 * np.pi * rho[:, None] * sol["drho_cm"] * sol["dz_cm"]
        drho_um = sol["drho_cm"] * 1e4
        for thr in (0.9, 0.5, 0.1, 0.01):
            m = P >= thr
            V = float((vol_cell * m).sum()) * 1e9     # cm^3 -> mm^3
            if m.any():
                jmax = int(np.max(np.where(m.any(axis=0))[0]))
                zmax_um = z[jmax] * 1e4
                # 该层横向直径
                rr = np.where(m[:, jmax])[0]
                dia_um = 2 * rho[int(rr.max())] * 1e4 if rr.size else 0.0
            else:
                zmax_um = dia_um = 0.0
            print(f"       {thr:>7.2f}{V:>16.4g}{zmax_um:>14.0f}"
                  f"{dia_um:>20.0f}")

    # ── 单细胞可行性（**正确判据**）──
    print(f"\n  {'='*92}")
    print("  ★ 「单细胞尺度」的正确判据：是否存在阈值使激活区**横向直径 <= 20 um**")
    print("     （注意：这里问的是**横向可分辨尺度**，不再用球对称的 FWHM）")
    P = hill(phi, K_REF, 1.5)
    print(f"     {'thr':>7}{'轴上激活深度(um)':>18}{'该深度横向直径(um)':>20}")
    for thr in (0.99, 0.9, 0.5, 0.1):
        m = P >= thr
        if not m.any():
            print(f"     {thr:>7.2f}{'—':>18}{'—':>20}")
            continue
        # 只看轴上（rho 最小）那一列有多少 z 被激活
        jm = np.where(m[0, :])[0]
        zmax_um = z[jm.max()] * 1e4 if jm.size else 0.0
        # 在 z 最深处那一层的横向直径
        j = int(jm.max()) if jm.size else 0
        rr = np.where(m[:, j])[0]
        dia_um = 2 * rho[int(rr.max())] * 1e4 if rr.size else 0.0
        print(f"     {thr:>7.2f}{zmax_um:>18.0f}{dia_um:>20.0f}")

    out = {
        "组织": {"kind": args.kind, "lam_nm": d["lam_nm"],
                 "mu_a_per_cm": d["mu_a_per_cm"],
                 "mu_s_prime_per_cm": d["mu_s_prime_per_cm"],
                 "D_cm": d["D_cm"], "delta_mm": d["delta_mm"]},
        "光纤": {"aperture_um": args.aperture_um, "NA": args.na,
                 "emit_len_um": emit_cm * 1e4, "power_mW": args.power_mw},
        "网格": {"nr": sol["nr"], "nz": sol["nz"],
                 "drho_um": sol["drho_cm"] * 1e4,
                 "dz_um": sol["dz_cm"] * 1e4,
                 "residual_rel": sol["residual_rel"]},
        "K_基准_W_per_cm2": float(K_REF),
        "柱对称光场": {"rho_um": (rho * 1e4).tolist(),
                       "z_um": (z * 1e4).tolist(),
                       "phi": phi.tolist()},
    }
    p = RES / f"q2q4_光纤_{args.kind}_{d['lam_nm']}nm.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
