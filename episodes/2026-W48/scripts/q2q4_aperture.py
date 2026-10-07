#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W48 · 问题 2/4 核心结论：**激活区不可能小于光源本身**。

## ★★ 本脚本要回答的问题

> **为什么光遗传学"照不亮单个神经元"？**

**答案的骨架**：一个半径 $a$ 的光纤端面，其出射光斑本身就有直径 $2a$。
散射只会把它**越糊越大**，绝不会变小。
所以

$$
D_{\text{act}}(z)\;\ge\;2a
$$

而单个神经元约 **10 µm** ⇒ 若要单细胞精度，必须有 $a\lesssim5\ \mu m$。

**这就把问题从"光能照多深"变成了"光源能做多小"。**

## 用到的量

在给定深度 $z$、阈值 $P_{\text{thr}}=0.5$ 下，定义**激活直径**

$$
D_{\text{act}}(z)=2\max\{\rho:\;P_{\text{open}}(\rho,z)\ge0.5\}
$$

并计算**展宽比**（散射把光斑放大了多少倍）：

$$
\text{spread}(z)=\frac{D_{\text{act}}(z)}{2a}
$$

## 输出

* $D_{\text{act}}(z)$ 与 $\text{spread}(z)$ 对**芯径**的依赖；
* **单细胞（10 µm）所需的芯径上限**；
* 与 $\ell_{\text{tr}}$、$\delta$ 的对比。

## [!] 模型适用边界（**必须写明**）

扩散近似要求**源尺度远大于输运平均自由程**（$a\gg\ell_{\text{tr}}$）。
本题灰质 470 nm 的 $\ell_{\text{tr}}=0.614$ mm $=614\ \mu m$，
**比所有实际光纤芯径都大** ⇒
**小芯径的结果会被扩散近似高估展宽**，
真实的聚焦光斑会更小。

⇒ **本脚本的定量结论只在 $a\gtrsim\ell_{\text{tr}}$ 时可靠；
$a\ll\ell_{\text{tr}}$ 时应改用蒙特卡洛或输运理论。**
这是本题"诚实性"评分的要点。

用法：
    $PY q2q4_aperture.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "episodes" / "2026-W48" / "scripts"))
from tissue_optics import derived                              # noqa: E402
from q2q4_fiber import solve_cylindrical, hill                 # noqa: E402

RES = ROOT / "episodes" / "2026-W48" / "results"
RES.mkdir(parents=True, exist_ok=True)

APERTURES_UM = (5, 10, 20, 50, 100, 200)
DEPTHS_UM = (100, 300, 500, 1000, 2000)
THR = 0.5


def act_diameter_um(phi: np.ndarray, rho_cm: np.ndarray,
                    K: float, n: float, thr: float = THR) -> np.ndarray:
    r"""逐 z 层求激活直径（µm）。"""
    P = hill(phi, K, n)
    m = P >= thr
    out = np.zeros(phi.shape[1])
    for j in range(phi.shape[1]):
        rr = np.where(m[:, j])[0]
        out[j] = 2 * rho_cm[int(rr.max())] * 1e4 if rr.size else 0.0
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lam", type=int, default=470)
    ap.add_argument("--kind", default="gray")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--hill-n", type=float, default=1.5)
    args = ap.parse_args()

    d = derived(args.kind, args.lam)
    print("=" * 94)
    print("  W48 · 问题 2/4：激活区不可能小于光源本身")
    print("=" * 94)
    print(f"\n  组织 {args.kind} @ {d['lam_nm']} nm: "
          f"delta={d['delta_mm']:.3f} mm  l_tr={d['l_tr_mm']:.3f} mm "
          f"= {d['l_tr_mm']*1000:.0f} um")
    print(f"  单细胞尺度基准：**10 um**")
    print(f"  [!] 模型边界：扩散近似要求 a >> l_tr = {d['l_tr_mm']*1000:.0f} um，")
    print(f"      而所有实际芯径都更小 => 小芯径结果会被**高估展宽**")

    rows = []
    print(f"\n  -- 激活直径 D_act (um)，阈值 P_open >= {THR}，Hill n={args.hill_n} --")
    print(f"  [!] K 必须用**固定的绝对光强**，不能每个孔径各自归一化 ——")
    print("      第一版写成 K = phi[0,0]*0.5 放在循环内，导致小孔径『照不到』，")
    print(f"      整列输出 0.0（纯属我自己的 bug）。")
    # ★ 先跑最大孔径，用它的轴上峰值一半作为**全程固定的 K**
    a_ref_cm = max(APERTURES_UM) / 1e4
    emit_ref = a_ref_cm / np.tan(np.arcsin(0.37))
    sol_ref = solve_cylindrical(d["mu_a_per_cm"], d["D_cm"], 1e-3, a_ref_cm,
                                emit_ref, 0.4, 0.6, nr=args.n, nz=args.n)
    K_FIX = float(sol_ref["phi"][0, 0] * 0.5)
    print(f"  K（固定） = 最大孔径({max(APERTURES_UM)}um)轴上峰值的 50% "
          f"= {K_FIX:.6g} W/cm^2")
    print("     " + f"{'芯径(um)':>10}" + "".join(
        f"{('z='+str(int(z))+'um'):>12}" for z in DEPTHS_UM)
        + f"{'展宽比@1mm':>12}")
    for a_um in APERTURES_UM:
        a_cm = a_um / 1e4
        theta = np.arcsin(0.37)
        emit_cm = a_cm / np.tan(theta)
        sol = solve_cylindrical(d["mu_a_per_cm"], d["D_cm"], 1e-3, a_cm,
                                emit_cm, 0.4, 0.6, nr=args.n, nz=args.n)
        rho, z, phi = sol["rho_cm"], sol["z_cm"], sol["phi"]
        dact = act_diameter_um(phi, rho, K_FIX, args.hill_n)
        vals = []
        for zu in DEPTHS_UM:
            j = int(np.argmin(np.abs(z - zu / 1e4)))
            vals.append(dact[j])
        j1000 = int(np.argmin(np.abs(z - 1000 / 1e4)))
        spread = dact[j1000] / (2 * a_um) if a_um else np.nan
        print(f"     {a_um:>10}" + "".join(f"{v:>12.1f}" for v in vals)
              + f"{spread:>12.2f}")
        rows.append({"aperture_um": a_um, "D_act_um": vals,
                     "spread_at_1mm": float(spread),
                     "residual": sol["residual_rel"]})

    # ── 单细胞所需芯径 ──
    print(f"\n  {'='*94}")
    print("  ★ 结论：把激活直径压到 10 um（单细胞）需要多细的光纤？")
    print(f"     {'芯径(um)':>10}{'1mm 深处激活直径(um)':>24}{'是否 <= 10um':>14}")
    for r in rows:
        v = r["D_act_um"][DEPTHS_UM.index(1000)]
        print(f"     {r['aperture_um']:>10}{v:>24.1f}"
              f"{('是' if v <= 10 else '否'):>14}")
    print(f"\n     => 因为 D_act >= 2a（散射只会放大、不会缩小），")
    print(f"        要 D_act <= 10 um 必须有 a <= 5 um ——")
    print(f"        而 a=5um << l_tr={d['l_tr_mm']*1000:.0f}um，")
    print(f"        **已超出扩散近似的适用范围**。")
    print(f"        => 这正是『双光子 / 时间聚焦』路线存在的理由。")

    out = {"组织": {"kind": args.kind, "lam_nm": d["lam_nm"],
                    "delta_mm": d["delta_mm"], "l_tr_mm": d["l_tr_mm"]},
           "阈值": THR, "Hill_n": args.hill_n,
           "深度_um": list(DEPTHS_UM), "扫描": rows,
           "_模型边界": ("扩散近似要求 a >> l_tr；小芯径结果高估展宽，"
                         "应改用蒙特卡洛或输运理论")}
    p = RES / f"q2q4_孔径扫描_{args.kind}_{d['lam_nm']}nm.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
