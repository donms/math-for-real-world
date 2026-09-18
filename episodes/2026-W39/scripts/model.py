#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W39 悬架建模核心：四分之一车模型 + 控制权限 + ISO 8608 路面。

================================ 模型推导 ================================
二自由度四分之一车。记
    z_s 簧上（车身）位移，z_u 簧下（车轮）位移，z_r 路面高程
    m_s, m_u 簧上/簧下质量；k_s 悬架刚度；k_t 轮胎刚度；c 阻尼系数
    u   作动器力（半主动时 u=0，阻尼体现在 c 上）

动力学：
    m_s·z̈_s = −k_s(z_s−z_u) − c(ż_s−ż_u) + u
    m_u·z̈_u = +k_s(z_s−z_u) + c(ż_s−ż_u) − k_t(z_u−z_r) − u

**状态与输入的选取（关键，曾在此处出错）**
取 5 维状态
    x = [ z_s−z_u , z_u−z_r , ż_s , ż_u , z_r ]ᵀ
输入取**路面加速度** `ẇ = z̈_r`（路面速度谱是白噪声，其导数即标准白噪声，
且这样代数关系闭合，不会出现"积分关系错位"）。

记 Δz=x₁, Δz_t=x₂, v_s=x₃, v_u=x₄, z_r=x₅，则
    k_s(z_s−z_u) = k_s·x₁
    k_t(z_u−z_r) = k_t·x₂
    z_s−z_r = x₁+x₂      ← 阻尼速度项要用它

求导可得（推导见论文 §3.1）：
    ẋ₁ = x₃ − x₄
    ẋ₂ = x₄ − ż_r，其中 ż_r = x₅ 的导数，作为状态的一部分
    ẋ₃ = [ −k_s·x₁ − c(x₃−x₄) + u ] / m_s
    ẋ₄ = [ +k_s·x₁ + c(x₃−x₄) − k_t·x₂ − u ] / m_u
    ẋ₅ 由积分 ẇ 得到（ẋ₅ = ż_r，ż_r 亦为状态；实现时令 ẋ₅ = 0 并把 ẇ 从
        输出侧耦合会丢信息，故采用 6 维状态 [.., ż_r, z_r]）

为严格闭合，实际实现用 **6 维状态**：
    x = [ z_s−z_u , z_u−z_r , ż_s , ż_u , ż_r , z_r ]ᵀ ,  输入 w = z̈_r

=========================================================================
性能指标（越小越好）
    J1 舒适性  = RMS(z̈_s)           车身垂向加速度
    J2 姿态    = RMS(z_s−z_u)       悬架动挠度
    J3 操稳    = RMS(k_t·(z_u−z_r)) 轮胎动载荷
"""
from __future__ import annotations

import numpy as np

G = 9.80665


# ------------------------------------------------------------------ 参数
def default_params() -> dict:
    """B 级乘用车典型参数（公开文献同级别取值，**非该车实测**）。"""
    m_s, m_u = 320.0, 40.0          # kg（四分之一车）
    k_s, k_t = 24000.0, 200000.0    # N/m
    zeta = 0.30                     # 被动阻尼比（舒适取向家用车 0.25–0.35）
    c0 = 2 * zeta * np.sqrt(k_s * m_s)
    return {
        "m_s": m_s, "m_u": m_u, "k_s": k_s, "k_t": k_t,
        "zeta": zeta, "c0": c0,
        # 半主动可调阻尼：按磁流变/CDC 器件典型可调比（厂商数字互相矛盾，
        # 故取包络并做情景扫描，见 data/来源清单.md §二）
        "c_min": 0.15 * c0,
        "c_max": 8.0 * c0,
        "g": G,
    }


def natural_freqs(p: dict) -> tuple[float, float]:
    """车身固有频率与车轮固有频率（Hz），用于自检。"""
    f_body = np.sqrt(p["k_s"] / p["m_s"]) / (2 * np.pi)
    f_wheel = np.sqrt((p["k_s"] + p["k_t"]) / p["m_u"]) / (2 * np.pi)
    return float(f_body), float(f_wheel)


# ------------------------------------------------------------------ 架构
ARCHS = ["被动", "云辇-C", "云辇-A", "云辇-M", "云辇-X"]


def arch_spec(arch: str, p: dict) -> dict:
    r"""各架构的控制权限描述。

    判据是**能否向系统注入能量**，而不是"调节速度多快"：
    * 被动   —— 参数常数，无可控自由度
    * 半主动 —— 只能改变**耗散**特性，恒有 `u·(ż_s−ż_u) ≥ 0`（只做负功）
    * 全主动 —— `u` 任意，可注入能量

    云辇-C / A / M 的阻尼执行器均为**耗散型**（电磁阀 CDC / 磁流变），
    故都属半主动；其中
      · C：阻尼可调（带宽按 CDC 典型值取数十 Hz）
      · A：阻尼可调 + 空气弹簧刚度/高度（刚度与高度是**慢自由度**，
           静力学调节，不改变瞬态隔振的权限层级）
      · M：磁流变阻尼，**带宽显著更高**（宣传"每秒上千次"）
      · X：全主动（本项目用作理论上界）
    """
    c0 = p["c0"]
    if arch == "被动":
        return {"kind": "passive", "c_fixed": c0, "bandwidth": None,
                "can_inject": False, "authority": "常数参数，无自由度"}
    if arch == "云辇-C":
        return {"kind": "semiactive", "c_range": (p["c_min"], p["c_max"]),
                "bandwidth": 30.0, "can_inject": False,
                "authority": "阻尼 c(t) 可调（耗散型）"}
    if arch == "云辇-A":
        return {"kind": "semiactive", "c_range": (p["c_min"], p["c_max"]),
                "bandwidth": 30.0, "can_inject": False,
                "k_range": (0.7 * p["k_s"], 1.3 * p["k_s"]),
                "authority": "阻尼 c(t) 可调 + 刚度/高度（慢自由度，耗散型）"}
    if arch == "云辇-M":
        return {"kind": "semiactive", "c_range": (p["c_min"], p["c_max"]),
                "bandwidth": 300.0, "can_inject": False,
                "authority": "磁流变阻尼，高带宽（耗散型）"}
    if arch == "云辇-X":
        return {"kind": "active", "bandwidth": 100.0, "can_inject": True,
                "authority": "主动力 u 任意（可注入能量）"}
    raise ValueError(arch)


# ------------------------------------------------------------------ 状态空间
def state_space(p: dict, c):
    r"""构造 6 维状态空间 `ẋ = A x + B w + B_u u`，`w = z̈_r`。

    x = [ z_s−z_u , z_u−z_r , ż_s , ż_u , ż_r , z_r ]ᵀ

    输出 y = [ z̈_s , z_s−z_u , k_t(z_u−z_r) ]。
    """
    ms, mu, ks, kt = p["m_s"], p["m_u"], p["k_s"], p["k_t"]
    n = 6
    A = np.zeros((n, n))
    # ẋ1 = ż_s − ż_u
    A[0, 2], A[0, 3] = 1.0, -1.0
    # ẋ2 = ż_u − ż_r
    A[1, 3], A[1, 4] = 1.0, -1.0
    # ẋ3 = [−ks·x1 − c(ż_s−ż_u)] / ms
    A[2, 0] = -ks / ms
    A[2, 2] = -c / ms
    A[2, 3] = c / ms
    # ẋ4 = [ks·x1 + c(ż_s−ż_u) − kt·x2] / mu
    A[3, 0] = ks / mu
    A[3, 1] = -kt / mu
    A[3, 2] = c / mu
    A[3, 3] = -c / mu
    # ẋ5 = ż_r 的导数 = w（输入）
    # ẋ6 = ż_r = x5
    A[5, 4] = 1.0

    B = np.zeros((n, 1))
    B[4, 0] = 1.0                       # w = z̈_r 直接作用于 ż_r

    Bu = np.zeros((n, 1))
    Bu[2, 0] = 1.0 / ms
    Bu[3, 0] = -1.0 / mu

    C = np.zeros((3, n))
    # z̈_s = [−ks·x1 − c(ż_s−ż_u)] / ms
    C[0, 0] = -ks / ms
    C[0, 2] = -c / ms
    C[0, 3] = c / ms
    # z_s − z_u = x1
    C[1, 0] = 1.0
    # kt(z_u − z_r) = kt·x2
    C[2, 1] = kt

    D = np.zeros((3, 1))
    Du = np.zeros((3, 1))
    Du[0, 0] = 1.0 / ms
    return A, B, Bu, C, D, Du


def freqresp(p: dict, c, f: np.ndarray, active_gain=None) -> np.ndarray:
    r"""频响 `H(jω)`：输出/输入（输入为 `z̈_r`）。

    直接求 resolvent `C(jωI−A)⁻¹B`，不走 scipy 的 ZPK 转换
    （`ss2zpk` 只支持单输入单输出，本模型 3 输出会报错）。
    """
    A, B, Bu, C, D, Du = state_space(p, c)
    I = np.eye(A.shape[0])
    H = np.zeros((3, len(f)), dtype=complex)
    K = np.zeros((1, A.shape[0])) if active_gain is None else active_gain
    for k, fk in enumerate(f):
        w = 2 * np.pi * max(fk, 1e-9)
        M = 1j * w * I - A
        if active_gain is not None:
            # 状态反馈 u = −K x → ẋ = (A − Bu K) x + B w
            M = M + Bu @ K
        H[:, k] = (C @ np.linalg.solve(M, B)).ravel()
    return H


# ------------------------------------------------------------------ 路面
# ISO 8608:2016 路面不平度系数 Gd(n0)（位移谱，单位 m^3/cycle）
ISO_ROAD_GD = {
    "A": 16e-6, "B": 64e-6, "C": 256e-6, "D": 1024e-6,
    "E": 4096e-6, "F": 16384e-6, "G": 65536e-6, "H": 262144e-6,
}
N0 = 0.1          # 参考空间频率 cycle/m
WAVINESS = 2.0    # 功率谱指数（ISO 8608 标准值）


def road_psd_spatial(level: str, n: np.ndarray) -> np.ndarray:
    r"""空间位移功率谱 `Gd(n) = Gd(n0)·(n/n0)^(−2)` [m^3/cycle]。"""
    gd0 = ISO_ROAD_GD[level]
    n = np.asarray(n, dtype=float)
    out = np.zeros_like(n)
    m = n > 0
    out[m] = gd0 * (n[m] / N0) ** (-WAVINESS)
    return out


def road_psd_velocity(level: str, f: np.ndarray, v: float) -> np.ndarray:
    r"""时间**速度**功率谱 `Gż(f)` [m²·s]。

    推导：空间位移谱 `Gd(n)`，`n = f/v`；对时间求导得速度谱
    `Gż(f) = (2πf)² · Gd(n)/v`。本模型输入是**加速度**，故再乘 `(2πf)²`。
    """
    f = np.asarray(f, dtype=float)
    n = np.maximum(f / v, 1e-12)
    gd = road_psd_spatial(level, n)
    return (2 * np.pi * f) ** 2 * gd / v


def road_psd_accel(level: str, f: np.ndarray, v: float) -> np.ndarray:
    r"""时间**加速度**功率谱 `Gz̈(f)` [m²/s³]（本模型的输入谱）。"""
    f = np.asarray(f, dtype=float)
    return (2 * np.pi * f) ** 2 * road_psd_velocity(level, f, v)


def generate_road_accel(level: str, v: float, dur: float, dt: float,
                        seed: int = 0,
                        f_lo: float = 0.2, f_hi: float = 30.0) -> tuple[np.ndarray, np.ndarray]:
    r"""时域生成路面**加速度** `z̈_r(t)`（按 PSD 加权随机相位合成）。

    ⚠️ **幅值标定（曾在此处犯错，务必留意）**
    用 `irfft` 由**单边**谱重建实数信号时，负频率是共轭镜像、**不额外贡献功率**；
    而离散余弦分量的功率为 `A²/2`。因此每根谱线的幅值应为

        A_k = sqrt( S(f_k)·Δf / 2 )

    若误写成 `sqrt(S·Δf)`，合成信号的 RMS 会**偏大 √2 倍**（实测比值 1.414），
    导致时域与频域结果系统性不符。

    `f_lo`/`f_hi` 为**空间频率**限带，避免把远超真实路面谱上限的高频
    （在加速度谱中按 f² 放大）灌进模型。按 ISO 8608 有效空间频率上限
    约 1–2 cycle/m，取 `f_hi = 2·v`（即 2 cycle/m 对应的时域频率）。
    """
    rng = np.random.default_rng(seed)
    n = int(round(dur / dt))
    t = np.arange(n) * dt
    f = np.fft.rfftfreq(n, dt)
    psd = road_psd_accel(level, f, v)

    # 空间频率限带：n = f/v ∈ [n_lo, n_hi]
    f_hi_eff = min(f_hi, 2.0 * v)          # 2 cycle/m
    f_lo_eff = max(f_lo, 0.01 * v)
    psd = np.where((f >= f_lo_eff) & (f <= f_hi_eff), psd, 0.0)

    df = f[1] - f[0]
    amp = np.sqrt(np.maximum(psd, 0.0) * df / 2.0)     # ← 单边谱功率因子 1/2
    spec = amp * np.exp(1j * rng.uniform(0, 2 * np.pi, size=f.shape))
    spec[0] = 0.0
    return t, np.fft.irfft(spec, n=n) * n


# ------------------------------------------------------------------ 指标
def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.asarray(x, dtype=float) ** 2)))


def metrics_freq(p: dict, c, level: str, v: float, f_max: float = 30.0,
                 n_f: int = 6000, active_gain=None) -> dict:
    """频域法：`RMS² = ∫|H(f)|²·G(f) df`（线性系统精确解）。"""
    f = np.linspace(1e-3, f_max, n_f)
    H = freqresp(p, c, f, active_gain=active_gain)
    psd = road_psd_accel(level, f, v)
    out = {}
    names = ["acc", "travel", "tire"]
    for k, nm in enumerate(names):
        integrand = np.abs(H[k, :]) ** 2 * psd
        out[nm] = float(np.sqrt(np.trapz(integrand, f)))
    return out


def metrics_time(p: dict, c, level: str, v: float, dur: float = 40.0,
                 dt: float = 1e-3, seed: int = 0) -> dict:
    r"""时域法：生成路面加速度 → 线性系统数值积分 → 输出 RMS。

    与频域法交叉验证，且把"线性定常"这一简化的影响显式化。
    """
    from scipy import signal as _sig
    A, B, Bu, C, D, Du = state_space(p, c)
    t, w = generate_road_accel(level, v, dur, dt, seed=seed)
    sysd = _sig.StateSpace(A, B, C, D)
    _, y, _ = _sig.lsim(sysd, U=w, T=t)
    return {"acc": rms(y[:, 0]), "travel": rms(y[:, 1]), "tire": rms(y[:, 2])}
