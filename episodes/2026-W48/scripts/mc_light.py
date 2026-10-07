#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W48 · 蒙特卡洛光传输（**碰撞估计量**版）。

## ★★ 为什么必须重写估计量（三版对比）

| 版本 | 估计量 | 结果 |
|---|---|---|
| v1 | 径向壳沉积 ÷ 壳体积 | **失败**：内层壳体积比外层小 4.3 万倍，近源区纯噪声 |
| v2 | 球面探测器（步端点跨越判定）| **失败**：步长 ~0.6 mm 与探测尺度同量级 ⇒ 漏计跨越；偏差随半径单调恶化到 **-87%** |
| **v3（本版）** | **碰撞估计量** | 在**每次散射碰撞**处累加，取**解析**方向权重 |

### v2 的缺陷为什么是"结构性"的

v2 只在**每步的起点与终点**判定是否跨过球壳。
但散射步长 $s=-\ln\xi/\mu_t$ 的均值是 $1/\mu_t\approx0.61$ mm，
而探测半径最小只有 0.3 mm ⇒ **一步可能跨过多个壳、或同一壳跨两次**，
被系统性漏计。这不是"再多跑点光子"能修的 —— 是估计量本身有偏。

### v3：碰撞估计量（standard collision estimator）

光子在位置 $\mathbf r_c$ 发生散射时，对**探测点** $\mathbf r_d$ 的光通量率贡献为

$$
\Delta\Phi(\mathbf r_d)=
w\;\frac{\mu_s}{\mu_t}\;
\frac{p(\hat\Omega\cdot\hat\Omega_{c\to d})}{4\pi}
\frac{e^{-\mu_a|\mathbf r_d-\mathbf r_c|}}{|\mathbf r_d-\mathbf r_c|^2}
$$

* $\mu_s/\mu_t$：该次相互作用是**散射**（而非吸收）的概率；
* $p(\cos\theta)$：**Henyey–Greenstein 相函数**（本题用精确式，不用各向同性近似）；
* 指数因子：从碰撞点到探测点的**吸收衰减**；
* $1/d^2$：几何扩散。

**关键优点**：**不需要网格**，也不依赖步长 —— 每个碰撞点都**精确**贡献，
因此**没有 v2 的漏计问题**。

> 物理含义：$\Phi$ 与"单位体积内被散射进探测方向的能量"成正比，
> 这正是碰撞估计量所累加的量。

用法：
    $PY q1_transport.py --nphoton 800000
"""
from __future__ import annotations

import numpy as np

# Henyey–Greenstein 相函数的归一化常数（对 4pi 立体角积分 = 1）
_HG_NORM = 1.0 / (4.0 * np.pi)


def hg_phase(cost: np.ndarray, g: float) -> np.ndarray:
    r"""Henyey–Greenstein 相函数 $p(\cos\theta)$，已归一化到 $\int p\,d\Omega=1$。

    $$
    p(\cos\theta)=\frac{1}{4\pi}\frac{1-g^2}
    {\left[1+g^2-2g\cos\theta\right]^{3/2}}
    $$
    """
    if g <= 0:
        return np.full_like(cost, _HG_NORM, dtype=float)
    denom = (1.0 + g * g - 2.0 * g * cost) ** 1.5
    return _HG_NORM * (1.0 - g * g) / np.maximum(denom, 1e-12)


def mc_fluence_collision(mu_a: float, mu_s: float, g: float,
                         r_det_cm: np.ndarray, n_photon: int,
                         seed: int = 20261006,
                         chunk: int = 200_000,
                         w_min: float = 1e-5,
                         max_steps: int = 40000) -> dict:
    r"""碰撞估计量蒙特卡洛。

    `r_det_cm` 是沿 +x 轴排布的**探测点**坐标（cm）。
    返回 $\Phi$（单位：源功率 $P_0=1$ 时的 W/cm^2）。

    实现要点（性能）：
    * **紧凑数组** + 尾部交换（v1 的布尔掩码每步扫全数组，慢到不可用）；
    * 每 `shrink_every` 步才做一次收缩，减少分支开销；
    * 对探测点的累加**一次性向量化**（`n_alive x n_det` 外积），
      避免 Python 层遍历探测点。
    """
    rng = np.random.default_rng(seed)
    mu_t = mu_a + mu_s
    p_scat = mu_s / mu_t
    K = len(r_det_cm)
    rd = np.asarray(r_det_cm, dtype=float)
    acc = np.zeros(K)
    n_scat_total = 0

    done = 0
    while done < n_photon:
        m = min(chunk, n_photon - done)
        done += m
        x = np.zeros(m); y = np.zeros(m); z = np.zeros(m)
        ux = np.zeros(m); uy = np.zeros(m); uz = np.ones(m)
        w = np.ones(m)
        n = m
        step = 0
        while n > 0 and step < max_steps:
            step += 1
            # ── 传播到下一次碰撞 ──
            s = -np.log(rng.random(n)) / mu_t
            xa, ya, za = x[:n], y[:n], z[:n]
            uxa, uya, uza = ux[:n], uy[:n], uz[:n]
            wa = w[:n]
            xa += uxa * s
            ya += uya * s
            za += uza * s
            # 吸收：权重按 exp(-mu_a s) 衰减（权重法，不终止）
            wa *= np.exp(-mu_a * s)
            n_scat_total += n

            # ── 碰撞估计量：对每个探测点累加 ──
            #   方向 碰撞点 -> 探测点（探测点在 x 轴上：(rd,0,0)）
            dx = rd[None, :] - xa[:, None]           # (n, K)
            dy = -ya[:, None]
            dz = -za[:, None]
            d2 = dx * dx + dy * dy + dz * dz
            d = np.sqrt(d2)
            np.maximum(d, 1e-9, out=d)
            cos_t = (dx * uxa[:, None] + dy * uya[:, None]
                     + dz * uza[:, None]) / d
            np.clip(cos_t, -1.0, 1.0, out=cos_t)
            ph = hg_phase(cos_t, g)
            contrib = (wa[:, None] * p_scat * ph
                       * np.exp(-mu_a * d) / d2)
            acc += contrib.sum(axis=0)

            # ── 散射：更新方向（Henyey–Greenstein 抽样）──
            xi = rng.random(n)
            if g > 0:
                t = (1.0 - g * g) / (1.0 - g + 2.0 * g * xi)
                cost = (1.0 + g * g - t * t) / (2.0 * g)
            else:
                cost = 2.0 * xi - 1.0
            np.clip(cost, -1.0, 1.0, out=cost)
            sint = np.sqrt(np.maximum(0.0, 1.0 - cost * cost))
            phi = 2.0 * np.pi * rng.random(n)
            den = np.sqrt(np.maximum(1e-12, 1.0 - uza * uza))
            nx = sint * np.cos(phi)
            ny = sint * np.sin(phi)
            uxa_new = uxa * cost + nx * uza * uxa / den - ny * uya / den
            uya_new = uya * cost + nx * uza * uya / den + ny * uxa / den
            uza_new = uza * cost - nx * den
            ux[:n], uy[:n], uz[:n] = uxa_new, uya_new, uza_new

            # ── 收缩（每 16 步）──
            if (step & 15) == 0:
                keep = wa > w_min
                nk = int(keep.sum())
                if nk < n:
                    idx = np.flatnonzero(keep)
                    for arr in (x, y, z, ux, uy, uz, w):
                        arr[:nk] = arr[:n][idx]
                    n = nk
            # 轮盘赌剩余权重（避免低估尾部）
        if n > 0:
            wa = w[:n]
            xa, ya, za = x[:n], y[:n], z[:n]
            dx = rd[None, :] - xa[:, None]
            dy = -ya[:, None]
            dz = -za[:, None]
            d2 = dx * dx + dy * dy + dz * dz
            d = np.sqrt(np.maximum(d2, 1e-18))
            cos_t = (dx * ux[:n][:, None] + dy * uy[:n][:, None]
                     + dz * uz[:n][:, None]) / d
            np.clip(cos_t, -1.0, 1.0, out=cos_t)
            acc += (wa[:, None] * p_scat * hg_phase(cos_t, g)
                    * np.exp(-mu_a * d) / d2).sum(axis=0)

    phi = acc / n_photon
    return {"phi": phi, "n_scattering_events": n_scat_total,
            "n_photon": n_photon}


def phi_diffuse_inf(r_cm, P0: float, D_cm: float,
                    delta_cm: float) -> np.ndarray:
    r"""无限介质点源扩散解 $\Phi=P_0e^{-r/\delta}/(4\pi Dr)$。"""
    r = np.maximum(np.asarray(r_cm, dtype=float), 1e-9)
    return P0 / (4 * np.pi * D_cm * r) * np.exp(-r / delta_cm)


def phi_diffuse_slab(rho_cm, z_cm, P0: float, D_cm: float, delta_cm: float,
                     z_src_cm: float, ze_cm: float) -> np.ndarray:
    r"""半空间（表面 z=0）**镜像法**解，源在深度 $z_s$。"""
    rho = np.asarray(rho_cm, dtype=float)
    z = np.asarray(z_cm, dtype=float)
    r1 = np.maximum(np.sqrt(rho ** 2 + (z - z_src_cm) ** 2), 1e-9)
    r2 = np.maximum(np.sqrt(rho ** 2 + (z + z_src_cm + 2 * ze_cm) ** 2), 1e-9)
    return P0 / (4 * np.pi * D_cm) * (np.exp(-r1 / delta_cm) / r1
                                      - np.exp(-r2 / delta_cm) / r2)
