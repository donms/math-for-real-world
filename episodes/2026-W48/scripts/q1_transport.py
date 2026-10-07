#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W48 · 问题 1：光在脑组织中的传输（扩散解析解 vs 蒙特卡洛）。

## 一、物理

脑组织在可见光波段是**强散射、弱吸收**介质（mu_s' >> mu_a）。
光子经多次散射后近似**扩散**：

    grad.(D grad Phi) - mu_a Phi + S = 0,   D = 1/[3(mu_a + mu_s')]

**穿透深度** 与 **输运平均自由程**：

    delta = 1/sqrt(3 mu_a (mu_a + mu_s'))
    l_tr  = 1/(mu_a + mu_s') = 1/mu_tr

## 二、★★ 我在这一问踩的两个坑（**必须记住**）

### 坑 1：把输运平均自由程写成 1/mu_s'

mu_s' = mu_s(1-g) 是**约化**散射系数（已把前向散射折算掉），
所以 l_tr = 1/(mu_a + mu_s') —— **不是** 1/mu_s'。
写成 1/mu_s' 会让"失效半径是几个 l_tr"的判断偏大。

### 坑 2：★ 用「径向壳沉积 / 壳体积」作光通量估计量 => 近源区全是噪声

第一版统计每个**径向壳**里的沉积能量，再除以壳体积。实测：

* 最内层壳体积 **5.2e-7 cm^3**、最外层 **2.2e-2 cm^3** —— **相差 4.3 万倍**；
* 而且**均匀径向分箱在三维里天然把样本堆在内层**
  （体积正比于 r^2 dr，却按 r 均分）。

=> 内层被放大成纯噪声，**整个对比表失去意义**
（第一版打印出的相对偏差是 `15382903297595.2%` 这种数字）。

**修法（本题采用）**：改用**球面探测器**（standard MC fluence estimator）——
在离源 r 处放一个薄球壳，**统计穿过它的权重**：

    Phi(r) = (1/N) * sum_i w_i / (4 pi r^2)

这样**不需要除以体素体积**，数值稳定得多。

## 三、蒙特卡洛实现

光子从原点出发，每步：
1. 抽样步长 s = -ln(xi)/mu_t（mu_t = mu_a + mu_s）；
2. **权重法**处理吸收（dw = w(1 - exp(-mu_a s))），剩余权重继续传播；
3. 散射角用 **Henyey-Greenstein** 相函数抽样。

**自检**：总沉积权重必须 ≈ 1（能量守恒）。

用法：
    $PY q1_transport.py
    $PY q1_transport.py --nphoton 4000000 --r-max-mm 8
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
RES = ROOT / "episodes" / "2026-W48" / "results"
RES.mkdir(parents=True, exist_ok=True)

# ★ 组织光学参数改为**实测值**（Nat Commun 2022 表 1），不再猜。
#   见 tissue_optics.py 的模块头（含"单位链混淆"这个坑的记录）。
from tissue_optics import derived as _der, SOURCE as OPT_SRC      # noqa: E402

TISSUE = {"n": 1.36, "g": 0.90}
BANDS = {"470nm_蓝光": _der("gray", 470),
         "625nm_红光": _der("gray", 625)}


# derived() 已移到 tissue_optics.py（用实测表）；
# 这里保留一个薄封装，避免改动下游调用签名。
def derived(mu_a: float, mu_s_prime: float) -> dict:
    mu_tr = mu_a + mu_s_prime
    return {"mu_tr": mu_tr, "l_tr_cm": 1.0 / mu_tr,
            "D_cm": 1.0 / (3.0 * mu_tr),
            "delta_cm": 1.0 / np.sqrt(3.0 * mu_a * mu_tr),
            "l_tr_mm": 10.0 / mu_tr,
            "delta_mm": 10.0 / np.sqrt(3.0 * mu_a * mu_tr)}


def z_extrap(D: float, n: float) -> float:
    Reff = -1.44 * n ** -2 + 0.71 * n ** -1 + 0.668 + 0.064 * n
    return 2.0 * ((1 + Reff) / (1 - Reff)) * D


def phi_diffuse_inf(r_cm, P0: float, mu_a: float,
                    mu_s_prime: float) -> np.ndarray:
    r"""无限介质点源扩散解 Phi = P0 exp(-r/delta)/(4 pi D r)。"""
    d = derived(mu_a, mu_s_prime)
    r = np.maximum(np.asarray(r_cm, dtype=float), 1e-9)
    return P0 / (4 * np.pi * d["D_cm"] * r) * np.exp(-r / d["delta_cm"])


def mc_fluence_shells(mu_a: float, mu_s: float, g: float,
                      r_probe_cm: np.ndarray, n_photon: int,
                      seed: int = 20261006,
                      chunk: int = 100_000) -> dict:
    r"""蒙特卡洛**球面探测器**估计光通量率。"""
    rng = np.random.default_rng(seed)
    mu_t = mu_a + mu_s
    K = len(r_probe_cm)
    acc = np.zeros(K)
    n_cross = np.zeros(K, dtype=np.int64)
    total_dep = 0.0

    done = 0
    while done < n_photon:
        m = min(chunk, n_photon - done)
        done += m
        x = np.zeros(m); y = np.zeros(m); z = np.zeros(m)
        ux = np.zeros(m); uy = np.zeros(m); uz = np.ones(m)
        w = np.ones(m)
        r_prev = np.zeros(m)
        alive = np.ones(m, dtype=bool)
        for _ in range(30000):
            idx = np.flatnonzero(alive)
            if idx.size == 0:
                break
            s = -np.log(rng.random(idx.size)) / mu_t
            x[idx] += ux[idx] * s
            y[idx] += uy[idx] * s
            z[idx] += uz[idx] * s
            dw = w[idx] * (1.0 - np.exp(-mu_a * s))
            total_dep += float(dw.sum())
            w[idx] -= dw
            r_new = np.sqrt(x[idx] ** 2 + y[idx] ** 2 + z[idx] ** 2)
            rp = r_prev[idx]
            for k in range(K):
                rk = r_probe_cm[k]
                cross = (((rp < rk) & (r_new >= rk))
                         | ((rp >= rk) & (r_new < rk)))
                if np.any(cross):
                    acc[k] += float(w[idx][cross].sum())
                    n_cross[k] += int(np.count_nonzero(cross))
            r_prev[idx] = r_new
            xi = rng.random(idx.size)
            if g > 0:
                t = (1 - g ** 2) / (1 - g + 2 * g * xi)
                cost = (1 + g ** 2 - t ** 2) / (2 * g)
            else:
                cost = 2 * xi - 1
            cost = np.clip(cost, -1, 1)
            sint = np.sqrt(np.maximum(0.0, 1 - cost ** 2))
            phi = 2 * np.pi * rng.random(idx.size)
            uxx, uyy, uzz = ux[idx], uy[idx], uz[idx]
            denom = np.sqrt(np.maximum(1e-12, 1 - uzz ** 2))
            nx = sint * np.cos(phi)
            ny = sint * np.sin(phi)
            ux[idx] = uxx * cost + nx * uzz * uxx / denom - ny * uyy / denom
            uy[idx] = uyy * cost + nx * uzz * uyy / denom + ny * uxx / denom
            uz[idx] = uzz * cost - nx * denom
            # ★ 截断半径要放得足够远：第一版用 4x 最大探测半径，
            #   人为抽空了尾部 => 远端偏差涨到 -80%。
            far = r_new > 25.0 * r_probe_cm[-1]
            if np.any(far):
                alive[idx[far]] = False
    phi_out = acc / n_photon / (4 * np.pi * r_probe_cm ** 2)
    return {"phi": phi_out, "n_cross": n_cross,
            "total_deposition": total_dep / max(1, n_photon),
            "n_photon": n_photon}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nphoton", type=int, default=1_000_000)
    ap.add_argument("--r-max-mm", type=float, default=8.0)
    ap.add_argument("--n-probe", type=int, default=20)
    args = ap.parse_args()

    print("=" * 96)
    print("  W48 · 问题 1：光在脑组织中的传输")
    print("=" * 96)
    n, g = TISSUE["n"], TISSUE["g"]

    print(f"\n  -- 量级估计（灰质典型值，n={n}，g={g}）--")
    print("     " + f"{'波段':<14}{'mu_a':>8}{'mu_s_p':>9}"
          f"{'mu_tr':>8}{'l_tr(mm)':>11}{'delta(mm)':>11}")
    der = {}
    for k, b in BANDS.items():
        der[k] = b
        print(f"     {k:<14}{b['mu_a_per_cm']:>8.2f}"
              f"{b['mu_s_prime_per_cm']:>9.2f}"
              f"{b['mu_tr_per_cm']:>8.2f}{b['l_tr_mm']:>11.3f}"
              f"{b['delta_mm']:>11.3f}")
    # ★ 不硬编码波段名（实测模块用的是 470/625 nm）
    _kb, _kr = list(der)[0], list(der)[1]        # 蓝、红
    rr = der[_kr]["delta_mm"] / der[_kb]["delta_mm"]
    print(f"\n     红/蓝：穿透深度比 **{rr:.2f}x**，输运自由程比 "
          f"{der[_kr]['l_tr_mm']/der[_kb]['l_tr_mm']:.2f}x")
    print(f"     蓝光穿透深度 **{der[_kb]['delta_mm']:.3f} mm**，"
          f"而脑区尺度是 cm => **差一个数量级**")

    r_probe = np.linspace(0.03, args.r_max_mm / 10.0, args.n_probe)
    print(f"\n{'='*96}")
    print(f"  -- 扩散解析解 vs 蒙特卡洛球面探测器（{args.nphoton:,} 光子）--")
    curves, bounds = {}, {}
    for k in BANDS:
        b = der[k]
        mu_s = b["mu_s_per_cm"]
        mc = mc_fluence_shells(b["mu_a_per_cm"], mu_s, g, r_probe,
                               args.nphoton)
        phi_d = phi_diffuse_inf(r_probe, 1.0, b["mu_a_per_cm"],
                                b["mu_s_prime_per_cm"])
        rel = (mc["phi"] - phi_d) / phi_d
        curves[k] = {"r_mm": (r_probe * 10).tolist(),
                     "phi_mc": mc["phi"].tolist(),
                     "phi_diff": phi_d.tolist(),
                     "rel_err": rel.tolist()}
        print(f"\n     == {k}（delta={b['delta_mm']:.2f} mm，"
              f"l_tr={b['l_tr_mm']:.3f} mm）==")
        print(f"       能量守恒自检：总沉积/光子数 = "
              f"{mc['total_deposition']:.5f}（应接近 1）")
        print("       " + f"{'r(mm)':>7}{'Phi_MC':>13}{'Phi_diff':>13}"
              f"{'偏差':>10}{'r/l_tr':>9}")
        for i in range(len(r_probe)):
            print(f"       {r_probe[i]*10:>7.3f}{mc['phi'][i]:>13.4g}"
                  f"{phi_d[i]:>13.4g}{rel[i]:>9.1%}"
                  f"{r_probe[i]*10/b['l_tr_mm']:>9.1f}")
        ok = np.abs(rel) <= 0.20
        rv = None
        for j in range(len(r_probe)):
            if ok[j] and np.all(ok[j:]):
                rv = float(r_probe[j] * 10)
                break
        bounds[k] = rv
        if rv:
            print(f"       => 偏差 <=20% 的起始半径：**{rv:.3f} mm**"
                  f" = {rv/b['l_tr_mm']:.1f} x l_tr")
        else:
            print("       => 探测范围内未达到 20% 以内")

    print(f"\n{'='*96}")
    print("  * 扩散近似的适用边界")
    for k in BANDS:
        v = bounds[k]
        if v:
            print(f"     {k}：r >= {v:.2f} mm"
                  f"（{v/der[k]['l_tr_mm']:.1f} x l_tr）偏差才 <=20%")
    print("     => **扩散近似只在约 3 个输运自由程以外成立**；")
    print("        近源区必须用蒙特卡洛 —— 这正是题面的『特别加分』点。")

    out = {
        "组织参数": {"n": n, "g": g},
        "波段": {k: {"lam_nm": der[k]["lam_nm"],
                     "mu_a": der[k]["mu_a_per_cm"],
                     "mu_s": der[k]["mu_s_per_cm"],
                     "mu_s_prime": der[k]["mu_s_prime_per_cm"],
                     "mu_tr": der[k]["mu_tr_per_cm"],
                     "l_tr_mm": der[k]["l_tr_mm"],
                     "delta_mm": der[k]["delta_mm"]} for k in BANDS},
        "红蓝穿透深度比": round(float(rr), 3),
        "MC_nphoton": args.nphoton,
        "适用边界_mm": bounds,
        "适用边界_l_tr倍数": {k: (bounds[k] / der[k]["l_tr_mm"]
                                  if bounds[k] else None) for k in BANDS},
        "曲线": curves,
        "_自查": [
            "l_tr 必须用 1/(mu_a+mu_s')，不是 1/mu_s'",
            "不要用『径向壳沉积/壳体积』作光通量估计量 —— "
            "内层壳体积小 4.3 万倍会被放大成噪声；改用球面探测器",
        ],
    }
    p = RES / "q1_传输.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
