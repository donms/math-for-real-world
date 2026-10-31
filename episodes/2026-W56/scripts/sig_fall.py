#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W56 · 合成一次摔倒的六种传感观测（六条时间序列）。

## 这一层要解决的问题

"能不能检测到摔倒"是**伪问题**：五种传感器都能。
真正的问题是**误报**：一个每天误报 1 次的报警器 = 没有报警器。

所以本脚本不输出"检出/未检出"，而输出**可被判别的物理量**：
峰值垂直速度 $v_{pk}$、制动比 $\beta$、冲击减速度 $a_{imp}$、
事后重心高度 $h_{post}$、事后躯干倾角 $\theta_{post}$。
`sig_confounders.py` 用同一套观测去打负样本，`roc_daily.py` 才把它们
变成"每天误报几次"。

## 运动模型（一条 v(t) 曲线生六种观测）

摔倒不是自由落体。用**一致性反解**说话（②档）：

* 重心总降幅 $\Delta h = 0.70$ m（题设）；
* 落地前垂直速度 $v_{pk} = 1.5\sim3.0$ m/s（题设）；
* 若这 0.70 m 真是自由落体，$v=\sqrt{2g\Delta h}=3.71$ m/s。

$$\frac{a_{\text{eff}}}{g}=\frac{v_{pk}^2}{2g\,\Delta h}
=\frac{2.0^2}{2\times9.81\times0.70}=0.291$$

**七成势能在触地之前就被屈膝与肌肉吸收。**
⇒ 下落段建成"**带制动的变速下降**"，而不是匀加速。

$$\beta=\frac{v_{pk}-v_{\text{触地}}}{v_{pk}}$$

$\beta=0$ 是一点没刹车，$\beta=1$ 是落地瞬间速度归零。
本模型**保证 $\beta$ 的实现值等于标称值**（形状函数用两段解析式拼，
峰值恰在 $u_p$，末端恰为 $1-\beta$），这样后面按 $\beta$ 分类才有意义。

## 六种观测的量纲依据

| 传感 | 观测 | 关键关系（② 由常数算出）|
|---|---|---|
| 毫米波 77 GHz | 多普勒谱 | $f_d=2v_r/\lambda$，$\lambda=3.893$ mm，2 m/s ⇒ **1027 Hz** |
| 摄像头 1080p/60°/5 m | 像素高度 | $2d\tan30°=5.774$ m ⇒ **332.5 px/m**，1.7 m 人 **565 px** |
| WiFi 2.4 GHz | CSI 幅度 | $\lambda=12.49$ cm，0.7 m = **56 个波长**，混叠上限 **1.25 m/s** |
| 蓝牙 2.4 GHz | RSSI | 刀刃绕射 + 对数距离，$\sigma_{\text{shadow}}=5$ dB |
| 激光雷达 | 点云 | 距离分辨 **2 cm**，0.7 m = 35 个单元 |
| IMU | 比力 SVM | 自由落体段 < 1 g，冲击 SVM 峰 **3–10 g** |

## 用法

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"
$PY scripts\\sig_fall.py                       # 打印六路特征
$PY scripts\\sig_fall.py --fig                 # 另存六联图
$PY scripts\\sig_fall.py --activity sit_fast   # 换成负样本
$PY scripts\\sig_fall.py --selftest            # 断言自检
```
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

# ============================================================
# 0. 物理常数（① 定义值 / ② 由定义反解）
# ============================================================
C_LIGHT = 299_792_458.0        # m/s      ①定义值
G = 9.80665                    # m/s^2    ①定义值

F_MMW_60 = 60.0e9              # Hz
F_MMW_77 = 77.0e9              # Hz
F_WIFI_24 = 2.4e9
F_WIFI_5 = 5.0e9
F_BLE = 2.4e9

CAM_W_PX, CAM_H_PX = 1920, 1080
CAM_HFOV_DEG = 60.0
CAM_DIST_M = 5.0

IMU_NOISE_G = 0.02             # g，③ 消费级 MEMS 噪声
IMU_FS_HZ = 100.0

FS_MMWAVE = 100.0
FS_CAMERA = 30.0
FS_WIFI = 20.0
FS_BLE = 10.0
FS_LIDAR = 20.0

T_PRE = 0.30                   # 动作前静默
T_POST = 1.20                  # 事后观察

# 站立重心高度：0.53 × 1.70 m ≈ 0.90 m（② 由人体质心比例反解）
H_STAND = 0.90


# ============================================================
# 1. 七个活动类的运动学参数（③ 自定假设，带题设锚点）
# ============================================================
# dh   重心总降幅（m）      → hpost = H_STAND − dh 自动一致
# v    峰值垂直速度（m/s）
# beta 制动比
# aimp 冲击**运动学**减速度（g）；SVM 峰 = aimp + 1
# thpost 事后躯干与竖直的夹角（deg），90 为完全躺平
#
# 锚点：摔倒失衡 0.2–0.4 s + 下落 0.3–0.5 s；下降 0.7 m；冲击 SVM 3–10 g
#       ⇒ aimp 取 4.0 g（SVM 峰 5.0 g，落在 3–10 的中段）
ACTIVITY = {
    "fall": dict(label="摔倒", dh=0.70, v=2.00, beta=0.30,
                 aimp=4.00, thpost=85.0, kind="positive"),
    "sit_fast": dict(label="快速坐下", dh=0.45, v=1.40, beta=0.45,
                     aimp=1.00, thpost=5.0, kind="negative"),
    "bend": dict(label="弯腰捡东西", dh=0.30, v=0.60, beta=0.70,
                 aimp=0.30, thpost=60.0, kind="negative"),
    "sofa": dict(label="躺到沙发上", dh=0.40, v=0.90, beta=0.55,
                 aimp=0.35, thpost=82.0, kind="negative"),
    "walk": dict(label="走动", dh=0.06, v=0.10, beta=0.90,
                 aimp=0.50, thpost=5.0, kind="negative"),
    "door": dict(label="开门", dh=0.01, v=0.02, beta=0.00,
                 aimp=0.02, thpost=0.0, kind="negative"),
    "bed": dict(label="上下床", dh=0.42, v=0.70, beta=0.60,
                aimp=0.40, thpost=80.0, kind="negative"),
}

# 类内变异（③ 假设，jitter=1.0 时的标准差）
JIT = dict(v=0.22, dh=0.12, aimp=0.40, beta=0.30, th=8.0)

# 蓝牙 RSSI 的事件响应幅度 dB（③，由刀刃绕射量级给出，见 q1 §5）
BLE_DRSSI = {"fall": 5.0, "sit_fast": 4.0, "bend": 3.0, "sofa": 3.5,
             "walk": 5.5, "door": 6.0, "bed": 4.0}


# ============================================================
# 2. 运动学：形状函数与时长反解
# ============================================================
def _upeak(beta: float) -> float:
    r"""峰值出现的归一化时刻：刹车越多，峰值越提前。

    $$u_p=0.95-0.45\,\beta$$
    """
    return 0.95 - 0.45 * float(np.clip(beta, 0.0, 1.0))


def _vshape(u: np.ndarray, beta: float) -> np.ndarray:
    r"""归一化速度形状，$u\in[0,1]$，$\max=1$ 且 $\tilde v(1)=1-\beta$。

    上升段：$\tilde v=(u/u_p)^{1.6}$
    下降段：$\tilde v=1-\beta\,((u-u_p)/(1-u_p))^{1.2}$

    两条性质**在解析上成立**，所以 $\beta$ 的实现值严格等于标称值：
    这是本模型能被后面按 $\beta$ 分类的前提。
    """
    beta = float(np.clip(beta, 0.0, 1.0))
    up = _upeak(beta)
    u = np.asarray(u, dtype=float)
    left = np.power(np.clip(u / up, 0.0, 1.0), 1.6)
    x = np.clip((u - up) / max(1e-9, 1.0 - up), 0.0, 1.0)
    right = 1.0 - beta * np.power(x, 1.2)
    return np.where(u <= up, left, right)


def _impact_index(acc: np.ndarray, i_pk: int) -> int:
    r"""冲击脉冲的峰值位置（向上加速度最大处）。"""
    a = np.asarray(acc, dtype=float)
    if not np.isfinite(a.max()) or a.max() <= 0:
        return int(max(0, i_pk))
    return int(np.argmax(a))


def estimate_beta(v: np.ndarray, i_pk: int, i_a: int) -> float:
    r"""由速度曲线估制动比 $\beta$，对半正弦冲击脉冲**严格无偏**。

    ## 为什么不能直接读"冲击前一帧的速度"

    冲击脉冲近似半正弦 $a(t)=A\sin(\pi t/T)$，于是

    $$v(t)=v_{\text{end}}\left[1-\tfrac12\big(1-\cos(\pi t/T)\big)\right]$$

    在脉冲峰值 $t=T/2$ 处，$\cos= -1$ ⇒ $v=v_{\text{end}}/2$。所以

    $$\boxed{v_{\text{end}} = 2\,v(t_{a\text{-peak}})}$$

    这条是**解析结论**，不是拟合。
    若改用"过半点"或"峰值前一帧"，实测会把 `sit_fast` 的 $\beta$
    从 0.45 虚报成 0.59、把 `fall` 的 0.30 虚报成 0.42。
    """
    v_pk = float(v[i_pk])
    if not np.isfinite(v_pk) or v_pk <= 1e-9:
        return 0.0
    v_end = min(v_pk, 2.0 * float(v[i_a]))
    return float(np.clip((v_pk - v_end) / v_pk, 0.0, 1.0))


def motion(act: str, rng: np.random.Generator | None = None,
           jitter: float = 0.0, jmap: dict | None = None) -> dict:
    r"""生成一个活动类的真实运动学（可加类内抖动）。

    ## 一致性反解（②）

    $T_d$ 不是自由参数，由 $(\Delta h, v_{pk}, \beta)$ 唯一确定：

    $$T_d=\frac{\Delta h_{\text{下降}}}{v_{pk}\bar{\tilde v}},\qquad
      \bar{\tilde v}=\int_0^1\tilde v\,du$$

    这让模型可被证伪：反解出的 $T_d$ 必须落进
    "失衡 0.2–0.4 s + 下落 0.3–0.5 s" 的 0.45–0.95 s。
    """
    p = dict(ACTIVITY[act])
    if rng is not None and jitter > 0:
        # 类内变异（③）：速度 22%、降幅 12%、冲击 40%、制动比 30%（下限 0.15）、
        # 姿态角 8 度。jitter 是这些标准差的**倍数**，1.0 = 用上面这套标称值。
        # ★ 乘子必须**双向截断**：只保正不封顶会让 v 掉到 1e-6，
        #   于是 t_desc = dh/(v·vbar) 反解出上万秒，数组直接爆内存
        #   （实测 jitter=1.8 时申请了 18.4 GiB）。截到 [0.35, 1.8]。
        # ★ jmap（W56 修订二）：**分通道**放大。只把某个生成参数（v→速度通道、
        #   dh→高度通道、aimp→冲击通道、th→姿态通道）的类内标准差再乘一个系数，
        #   其余保持 1.0，用来判断"是哪个通道放大把结论推翻了"。
        jf = {k: 1.0 for k in JIT}
        if jmap:
            jf.update({k: float(v) for k, v in jmap.items() if k in jf})
        mv = float(np.clip(1.0 + JIT["v"] * jitter * jf["v"]
                           * rng.standard_normal(), 0.35, 1.8))
        md = float(np.clip(1.0 + JIT["dh"] * jitter * jf["dh"]
                           * rng.standard_normal(), 0.40, 1.8))
        ma = float(np.clip(1.0 + JIT["aimp"] * jitter * jf["aimp"]
                           * rng.standard_normal(), 0.20, 2.2))
        p["v"] = max(2e-3, float(p["v"]) * mv)
        p["dh"] = max(1e-4, float(p["dh"]) * md)
        p["aimp"] = max(1e-3, float(p["aimp"]) * ma)
        p["beta"] = float(np.clip(
            float(p["beta"]) + JIT["beta"] * jitter * jf["beta"]
            * rng.standard_normal(), 0.0, 0.95))
        p["thpost"] = float(np.clip(
            p["thpost"] + JIT["th"] * jitter * jf["th"]
            * rng.standard_normal(), 0.0, 89.0))
        # 事后重心高度必须为正：降幅不得超过站立重心高度
        p["dh"] = min(p["dh"], H_STAND - 0.06)

    beta = float(np.clip(p["beta"], 0.0, 0.95))
    v_pk = float(p["v"])
    dh = float(p["dh"])
    hpost = H_STAND - dh
    assert hpost > 0.02, "事后重心高度必须为正"

    # 冲击段：半正弦，SVM 峰 = aimp + 1 ⇒ 运动学减速度 A = aimp*g
    v_end = v_pk * (1.0 - beta)
    A_imp = max(1e-3, float(p["aimp"])) * G
    t_imp = max(1e-4, math.pi * v_end / (2.0 * A_imp))
    dh_imp = 2.0 * v_end * t_imp / math.pi          # 半正弦的面积 = v_end

    # 塌陷段：重心从"冲击末"继续降到 hpost 的差额（按总降幅的 25% 计，上限 2 cm）
    dh_settle = min(0.02, 0.25 * dh)
    dh_desc = dh - dh_imp - dh_settle
    if dh_desc <= 1e-4:
        # 冲击段吃掉了全部降幅（door 这类 dh 只有 1 cm 的动作会这样）：
        # 把冲击压缩到降幅的 30%，并让塌陷段按比例缩小
        dh_imp = max(1e-4, 0.30 * dh)
        dh_settle = min(0.02, 0.25 * dh)
        dh_desc = dh - dh_imp - dh_settle
        t_imp = max(1e-4, (dh_imp * math.pi) / max(2.0 * v_end, 1e-6))
    assert dh_desc > 0, f"{act}: 降幅分配失败（dh={dh:.4f} dh_imp={dh_imp:.4f}）"

    fs = 1000.0
    u = np.linspace(0.0, 1.0, 8001)
    shape = _vshape(u, beta)
    vbar = float(np.trapz(shape, u))
    t_desc = dh_desc / (v_pk * vbar)
    assert t_desc > 0
    assert t_desc < 5.0, f"{act}: 反解时长 {t_desc:.2f} s 不合理（dh={dh:.3f} v={v_pk:.3f}）"

    n_pre = int(round(T_PRE * fs))
    n_d = max(8, int(round(t_desc * fs)))   # 数值下限：梯度至少要 2 个点
    n_i = int(round(t_imp * fs))
    n_s = int(round(0.40 * fs))
    n_p = int(round(T_POST * fs))
    t = np.concatenate([
        np.arange(n_pre) / fs,
        T_PRE + np.arange(n_d) / fs,
        T_PRE + t_desc + np.arange(n_i) / fs,
        T_PRE + t_desc + t_imp + np.arange(n_s) / fs,
        T_PRE + t_desc + t_imp + 0.40 + np.arange(n_p) / fs,
    ])
    h = np.empty_like(t)
    v = np.zeros_like(t)
    a = np.zeros_like(t)

    h[:n_pre] = H_STAND
    # 下降段：v 与 h 由同一个形状函数严格一致地给出
    ud = np.clip((t[n_pre:n_pre + n_d] - T_PRE) / t_desc, 0.0, 1.0)
    vd = -v_pk * _vshape(ud, beta)
    v[n_pre:n_pre + n_d] = vd
    h[n_pre:n_pre + n_d] = H_STAND + np.concatenate(
        [[0.0], np.cumsum(0.5 * (vd[1:] + vd[:-1])) / fs])
    a[n_pre:n_pre + n_d] = np.gradient(vd, 1.0 / fs)
    h_impact = float(h[n_pre + n_d - 1])
    # 冲击段：速度线性收尾（均值与半正弦一致），加速度为半正弦
    i0 = n_pre + n_d
    ui = np.clip((t[i0:i0 + n_i] - T_PRE - t_desc) / t_imp, 0.0, 1.0)
    vi = -v_end * (1.0 - ui)
    v[i0:i0 + n_i] = vi
    h[i0:i0 + n_i] = h_impact + np.concatenate(
        [[0.0], np.cumsum(0.5 * (vi[1:] + vi[:-1])) / fs])
    # 冲击是**向上**的加速度（速度由负变零 ⇒ dv/dt>0）
    a[i0:i0 + n_i] = A_imp * np.sin(np.pi * ui)
    # 塌陷段
    i1 = i0 + n_i
    h_end_imp = float(h[i1 - 1])
    frac = np.clip((t[i1:i1 + n_s] - (T_PRE + t_desc + t_imp)) / 0.40, 0.0, 1.0)
    h[i1:i1 + n_s] = h_end_imp + (hpost - h_end_imp) * (
        (1.0 - np.exp(-3.5 * frac)) / (1.0 - math.exp(-3.5)))
    v[i1:i1 + n_s] = np.gradient(h[i1:i1 + n_s], 1.0 / fs)
    a[i1:i1 + n_s] = np.gradient(v[i1:i1 + n_s], 1.0 / fs)
    i2 = i1 + n_s
    h[i2:] = hpost

    # ---- 从信号里"量"出特征（和传感器做同一件事，只是没有噪声）----
    v_meas = -v
    i_pk = int(np.argmax(v_meas))
    acc_up = a / G                      # 向上为正
    i_imp = _impact_index(acc_up, i_pk)
    feat = dict(
        v_pk=float(v_meas[i_pk]),
        beta=estimate_beta(v_meas, i_pk, i_imp),
        a_imp=float(acc_up.max()),
        h_post=float(h[-1]),
        th_post=float(p["thpost"]),
        t_desc=float(t_desc), t_imp=float(t_imp),
        a_eff_g=float(v_pk ** 2 / (2.0 * G * dh)),
        dh_int=float(H_STAND - h[-1]),
        dh_desc_int=float(H_STAND - h_impact),
    )
    return dict(t=t, h=h, v=v, a=a, feat=feat, act=act,
                label=p["label"], svm_peak=float(p["aimp"] + 1.0))


# ============================================================
# 3. 六种正向观测模型
# ============================================================
def _resample(t_src: np.ndarray, x_src: np.ndarray, fs: float,
              t_end: float = None) -> tuple[np.ndarray, np.ndarray]:
    n = int(round((t_end if t_end is not None else t_src[-1]) * fs))
    tt = np.arange(n) / fs
    return tt, np.interp(tt, t_src, x_src)


def _posture_angle(mo: dict, t: np.ndarray) -> np.ndarray:
    r"""躯干与竖直方向的夹角，由 0° 平滑过渡到事后倾角（90° 为躺平）。"""
    th_end = ACTIVITY[mo["act"]]["thpost"]
    t1 = T_PRE + mo["feat"]["t_desc"] + mo["feat"]["t_imp"] + 0.40
    x = np.clip((t - T_PRE) / max(1e-6, t1 - T_PRE), 0.0, 1.0)
    return th_end * (0.5 - 0.5 * np.cos(np.pi * x))


def _true_v(mo: dict, t: np.ndarray) -> np.ndarray:
    return np.interp(t, mo["t"], mo["v"])


def obs_mmwave(mo: dict, rng: np.random.Generator, fs: float = FS_MMWAVE,
               f0: float = F_MMW_77, snr_db: float = 20.0) -> dict:
    r"""毫米波多普勒：$f_d=2v_r/\lambda$。

    $\lambda=c/f_0$：77 GHz 给 3.893 mm，2 m/s 给 **1027 Hz**。
    人体微动 10–200 Hz 对应 $v=f_d\lambda/2=0.019\sim0.39$ m/s，
    比摔倒低一个数量级 ⇒ **特征在频域极显眼**。

    速度估计噪声 $\sigma_v=\lambda\Delta f_{\text{micro}}/(2\sqrt{\rm SNR})$，
    $\Delta f=200$ Hz、SNR=20 dB 给 **0.039 m/s**（②）。
    """
    lam = C_LIGHT / f0
    t, v = _resample(mo["t"], mo["v"], fs)
    micro = np.zeros_like(t)
    for f, amp in ((23.0, 0.14), (57.0, 0.09), (131.0, 0.05)):
        micro += amp * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
    snr_lin = 10.0 ** (snr_db / 10.0)
    sig_v = lam * 200.0 / (2.0 * math.sqrt(snr_lin))
    v_obs = v * (1.0 + micro) + sig_v * rng.standard_normal(t.size)
    fd = 2.0 * v_obs / lam
    phase = 2 * np.pi * np.cumsum(fd) / fs
    amp = 1.0 + 0.12 * np.sin(2 * np.pi * 0.7 * t) + 0.02 * rng.standard_normal(t.size)
    # 高度由 FMCW 距离 + 阵列俯仰角给出：2 度角精度 @2.5 m 给 0.087 m
    h_est = np.interp(t, mo["t"], mo["h"]) + 0.08 * rng.standard_normal(t.size)
    return dict(name="mmwave", t=t, raw=amp * np.exp(1j * phase),
                v_obs=v_obs, fd=fd, lam=lam, sig_v=float(sig_v),
                h_obs=h_est, sig_h=0.08)


def obs_camera(mo: dict, rng: np.random.Generator,
               fs: float = FS_CAMERA) -> dict:
    r"""摄像头：像素高度与姿态。

    1920 px / 5.774 m = **332.5 px/m**，1.7 m 的人 **565 px**。
    关键点误差 3 cm（③，随距离线性）；5 帧中心差分（0.167 s）
    给 $\sigma_v=\sigma_x\sqrt2/\Delta t=0.254$ m/s（②）。
    躯干角误差 $\arctan(0.0424/0.40)=6.05°$（②）。
    """
    width_m = 2.0 * CAM_DIST_M * math.tan(math.radians(CAM_HFOV_DEG) / 2.0)
    px_per_m = CAM_W_PX / width_m
    t, h = _resample(mo["t"], mo["h"], fs)
    sig_x = 0.03
    h_obs = h + sig_x * rng.standard_normal(t.size)
    k = 5
    hpad = np.r_[np.full(k, h_obs[0]), h_obs, np.full(k, h_obs[-1])]
    hs = np.convolve(hpad, np.ones(2 * k + 1) / (2 * k + 1), mode="same")[k:-k]
    v_obs = np.r_[0.0, np.diff(hs)] * fs
    sig_v = sig_x * math.sqrt(2.0) / (k / fs)
    sig_th = math.degrees(math.atan(sig_x * math.sqrt(2.0) / 0.40))
    th_obs = _posture_angle(mo, t) + sig_th * rng.standard_normal(t.size)
    return dict(name="camera", t=t, raw=h_obs * px_per_m, h_obs=h_obs,
                v_obs=v_obs, th_obs=th_obs, px_per_m=px_per_m,
                body_px=1.70 * px_per_m, sig_v=float(sig_v),
                sig_h=float(sig_x), sig_th=float(sig_th))


def obs_wifi(mo: dict, rng: np.random.Generator, fs: float = FS_WIFI,
             f0: float = F_WIFI_24) -> dict:
    r"""WiFi CSI：多径叠加，映射不可逆。

    $$H(f,t)=\sum_k a_k e^{-j2\pi f\tau_k(t)},\qquad
      \tau_{\text{body}}=\frac{d_0+2(H_{\text{stand}}-h(t))}{c}$$

    两条硬约束（②）：

    1. **相位混叠**：$v_{\max}=\lambda/(2\Delta t)=0.125/(2\times0.05)
       =\mathbf{1.25}$ m/s；摔倒 2 m/s 是它的 **1.6 倍**。
    2. **衰落周期**：位移每过 $\lambda/2=6.25$ cm 幅度过零一次，
       0.7 m 要过 **11 个零点** ⇒ 幅值曲线符号翻转 11 次。

    ⇒ 只暴露幅度（相位已被多径搅乱），有效速度噪声取 0.45 m/s（③）。
    """
    lam = C_LIGHT / f0
    t, h = _resample(mo["t"], mo["h"], fs)
    n_sc = 64
    freqs = np.linspace(2.412e9, 2.472e9, n_sc)
    d0 = 3.0
    tau_body = (d0 + 2.0 * (H_STAND - h)) / C_LIGHT
    Hc = np.zeros((n_sc, t.size), dtype=complex)
    for a, tau, ph in ((0.72, (d0 + 0.15) / C_LIGHT, 0.0),
                       (0.48, (d0 + 1.40) / C_LIGHT, 0.9),
                       (0.30, (d0 + 2.60) / C_LIGHT, 2.1)):
        Hc += a * np.exp(-1j * (2 * np.pi * freqs[:, None] * tau + ph))
    Hc += 0.55 * np.exp(-1j * 2 * np.pi * freqs[:, None] * tau_body[None, :])
    Hc += 0.03 * (rng.standard_normal(Hc.shape) + 1j * rng.standard_normal(Hc.shape))
    amp = np.abs(Hc)
    a_mean = amp.mean(axis=0)
    # 逐帧噪声 1.0 m/s（CSI 幅度导数被多径闪烁主导），5 帧平滑后降到 0.45
    sig_raw = 1.00
    k = 5
    v_raw = _true_v(mo, t) + sig_raw * rng.standard_normal(t.size)
    pad = np.r_[np.full(k, v_raw[0]), v_raw, np.full(k, v_raw[-1])]
    v_obs = np.convolve(pad, np.ones(2 * k + 1) / (2 * k + 1), mode="same")[k:-k]
    sig_v = sig_raw / math.sqrt(2 * k + 1)
    return dict(name="wifi", t=t, raw=amp, amp=a_mean, v_obs=v_obs, sig_v_raw=sig_raw,
                v_proxy=np.r_[0.0, np.diff(a_mean)] * fs * 1.6,
                lam=lam, sig_v=sig_v, n_sc=n_sc, fade_period=lam / 2.0,
                v_alias=lam / (2.0 / fs))


def obs_ble(mo: dict, rng: np.random.Generator, fs: float = FS_BLE) -> dict:
    r"""蓝牙 RSSI：对数距离 + 刀刃绕射遮挡。

    $$\mathrm{RSSI}=P_t-\big[PL_0+10n\log_{10}d\big]-L(\nu)+X_\sigma$$

    $\nu=h\sqrt{\frac2\lambda(\frac1{d_1}+\frac1{d_2})}$，$d_1=d_2=1.5$ m、
    $\lambda=12.5$ cm 给 $\nu=4.62h$；人站着 $h\approx0.7$ m
    $\Rightarrow L\approx23$ dB，倒地 $L\approx0$ dB。

    ⇒ 单链路看得到 20 dB 级跳变，但**同一个跳变在"有人走过链路"、
    "门被推开"时也会出现**，且 $\sigma_{\text{shadow}}=5$ dB。
    分辨率问题在空间：RSSI 分不出 0.5 m 内的位置差。
    """
    t, h = _resample(mo["t"], mo["h"], fs)
    lam = C_LIGHT / F_BLE
    pl = 40.0 + 10.0 * 2.5 * math.log10(3.0)
    nu = (h - H_STAND * 0.70) * math.sqrt(2.0 / lam * (2.0 / 1.5))
    L = np.where(nu > -0.7,
                 6.9 + 20.0 * np.log10(np.sqrt((nu - 0.1) ** 2 + 1.0) + nu - 0.1),
                 0.0)
    L = np.clip(L, 0.0, 40.0)
    sig = 5.0
    # 事件响应 = 声明幅度（由刀刃绕射上限 15.4 dB × 遮挡几何因子 0.33 给量级）
    #           + 阴影衰落噪声 5 dB
    dr_model = float(BLE_DRSSI[mo["act"]])
    dr_obs = dr_model * (1.0 + 0.25 * rng.standard_normal()) \
        + sig * rng.standard_normal()
    base = -(pl + L[t < T_PRE].mean())
    rssi = base + dr_obs * (t > T_PRE + 0.6).astype(float) \
        + 1.0 * rng.standard_normal(t.size)
    return dict(name="ble", t=t, raw=rssi, rssi=rssi, L=L, sig_rssi=sig,
                drssi_obs=float(dr_obs), drssi_model=dr_model,
                fresnel_r=math.sqrt(lam * 1.5 * 1.5 / 3.0))


def obs_lidar(mo: dict, rng: np.random.Generator,
              fs: float = FS_LIDAR) -> dict:
    r"""激光雷达点云。

    距离分辨 2 cm（③），0.7 m 下降 = **35 个分辨单元**；
    角分辨 0.2°，3 m 处横向间距 **1.05 cm**，0.5 m² 正面约 4500 点。
    本模型取 240 个可见轮廓点，只算几何，不算纹理。
    """
    t, h = _resample(mo["t"], mo["h"], fs)
    lateral = 3.0 * math.tan(math.radians(0.2))
    n_pts = 240
    rp = np.random.default_rng(20260560)
    w = rp.uniform(0, 1, n_pts)
    th_t = _posture_angle(mo, t)
    # 躯干竖直投影的延展：站立约 0.44 m，躺平约 0.22 m，中心就是重心
    extent = 0.24 * np.abs(np.cos(np.radians(th_t))) + 0.20
    cloud = h[:, None] + ((w[None, :] - 0.5) * extent[:, None])
    cloud += 0.02 * rng.standard_normal(cloud.shape)          # 逐点距离噪声
    cloud += 0.02 * rng.standard_normal((t.size, 1))          # 逐帧共模（分割误差）
    top_obs = cloud.mean(axis=1)
    k = 5
    pad = np.r_[np.full(k, top_obs[0]), top_obs, np.full(k, top_obs[-1])]
    ts = np.convolve(pad, np.ones(2 * k + 1) / (2 * k + 1), mode="same")[k:-k]
    return dict(name="lidar", t=t, raw=cloud, top=top_obs,
                v_obs=np.r_[0.0, np.diff(ts)] * fs,
                th_obs=th_t + 5.0 * rng.standard_normal(t.size),
                sig_v=float(0.02 * math.sqrt(2.0) / (k / fs)), sig_h=0.02,
                lateral=float(lateral), n_pts=n_pts,
                dense_pts=int(0.5 / (lateral ** 2)))


def obs_imu(mo: dict, rng: np.random.Generator,
            fs: float = IMU_FS_HZ) -> dict:
    r"""可穿戴 IMU：比力模 $\mathrm{SVM}=\sqrt{a_x^2+a_y^2+a_z^2}$。

    $\mathrm{SVM}=1+a_{\text{kin}}/g$：自由落体段掉到 **0.71 g**
    （注意：因为下落是带制动的，$a_{\text{eff}}=0.29g$，
    所以**不会**掉到 0.1 g，这会让"自由落体阈值"这类判据漏掉大部分摔倒），
    冲击段 SVM 峰 = $a_{imp}+1$，摔倒给 **5 g**，落在题设 3–10 g 内。
    """
    t, a = _resample(mo["t"], mo["a"], fs)
    svm_true = 1.0 + a / G
    svm = svm_true + IMU_NOISE_G * rng.standard_normal(t.size)
    th_t = _posture_angle(mo, t)
    # 速度只能靠积分得到：姿态由陀螺给出后可把 a 投到世界竖轴，
    # 于是 v(t) = ∫a dt，代价是**漂移**（零偏 20 mg 在 0.5 s 内积出 0.1 m/s）。
    v_int = np.r_[0.0, np.cumsum(0.5 * (a[1:] + a[:-1]))] / fs
    v_obs = v_int + 0.03 * rng.standard_normal(t.size) + 0.02 * t * rng.standard_normal()
    return dict(name="imu", t=t, raw=svm, svm=svm, v_obs=v_obs,
                gyro=np.gradient(th_t, 1.0 / fs),
                th_obs=th_t + 8.0 * rng.standard_normal(t.size),
                sig_a=IMU_NOISE_G, svm_peak_true=mo["svm_peak"])


OBSERVERS = {"mmwave": obs_mmwave, "camera": obs_camera, "wifi": obs_wifi,
             "ble": obs_ble, "lidar": obs_lidar, "imu": obs_imu}


# ============================================================
# 4. 特征提取
# ============================================================
# ★ 通道可用性矩阵：这是**物理决定的**，不是调参调出来的。
#   改这张表等于改模型假设，必须同步改 results/q1_物理量纲.md。
# ★★ 这张表是**实测改出来的**，不是先验设计。两次修正（记录见 results/q2）：
#
#  ① 删掉 eta（制动比）**全部传感**：估计量实测标准差 0.22–0.42，
#     而类间差只有 0.15（摔倒 0.30 对快速坐下 0.45）⇒ 信噪比 0.4，不可用。
#     理论上最有判别力的通道，恰恰是最难测准的那一个。
#  ② 删掉摄像头 / 激光雷达的 （冲击）：30 fps 与 20 fps 分辨不了 56 ms
#     的半正弦脉冲，实测峰值被平滑压到 0.4–0.9 g，且**类间差被压平**
#     （摔倒 0.86 g 对躺沙发 0.64 g），等于没有。
#
# 保留 eta_diag 供诊断（不进判别）。
CHANNELS = {
    "camera": ("v", "h", "th"),
    "mmwave": ("v", "a", "h"),
    "wifi":   ("v",),
    "ble":    ("rssi",),
    "lidar":  ("v", "h", "th"),
    "imu":    ("v", "a", "th"),
}


def extract(obs: dict) -> dict:
    r"""从一条观测里估出判别特征；测不到的通道返回 None。

    通道可用性**不是拍脑袋，是几何决定的**：

    | 通道 | 谁有 | 为什么 |
    |---|---|---|
    | `v` 峰值速度 | 全部 | 能量类传感也能给出粗糙代理 |
    | `beta` 制动比 | 摄像头/毫米波/激光雷达/IMU | 需要连续速度轨迹 |
    | `a` 冲击 | IMU 直接读；毫米波靠速度导数；光学帧率不够 | |
    | `h` 事后高度 | 摄像头/毫米波/激光雷达 | **需要度量尺度或三维** |
    | `th` 事后姿态 | 摄像头/激光雷达/IMU | IMU 有姿态但**没有高度** |
    """
    name = obs["name"]
    out = dict(v=None, beta=None, a=None, h=None, th=None, rssi=None,
               beta_diag=None)
    if name == "ble":
        out["rssi"] = float(obs["drssi_obs"])
        return out

    t = obs["t"]
    fs = 1.0 / (t[1] - t[0])
    v = obs["v_obs"]
    v_pk = float(np.max(np.abs(v)))
    i_pk = int(np.argmax(np.abs(v)))
    out["v"] = v_pk

    acc = np.gradient(v) * fs                      # 向上为正
    i_imp = _impact_index(acc, i_pk)
    out["beta"] = estimate_beta(np.abs(v), i_pk, i_imp)
    out["beta_diag"] = out["beta"]                 # 诊断用，不进判别

    if name == "imu":
        out["a"] = float(obs["svm"].max() - 1.0)
    elif name in ("mmwave", "camera", "lidar"):
        out["a"] = float(max(0.0, acc.max() / G))

    if name in ("camera", "mmwave", "lidar"):
        hh = obs.get("h_obs") if obs.get("h_obs") is not None else obs.get("top")
        out["h"] = float(np.mean(hh[-3:]))

    if name in ("camera", "lidar", "imu"):
        out["th"] = float(np.mean(obs["th_obs"][-3:]))

    # 不在能力表里的通道一律置空：避免"算得出就当测得到"
    for k in list(out):
        if k != "beta_diag" and k not in CHANNELS[name]:
            out[k] = None
    return out


# ============================================================
# 5. 一次生成六路观测
# ============================================================
def synth(act: str = "fall", seed: int = 20260560,
          jitter: float = 0.0, jmap: dict | None = None) -> dict:
    r"""合成一个活动在六种传感器上的观测（同一个运动学真值）。"""
    mo = motion(act, np.random.default_rng(seed), jitter=jitter, jmap=jmap)
    out = {"motion": mo, "obs": {}, "feat": {}}
    for i, (name, fn) in enumerate(OBSERVERS.items()):
        o = fn(mo, np.random.default_rng(seed + 101 * (i + 1)))
        out["obs"][name] = o
        out["feat"][name] = extract(o)
    return out


# ============================================================
# 6. 自检
# ============================================================
def selftest(verbose: bool = True) -> int:
    r"""十条断言：量纲、运动学一致性、通道可用性、单调性。"""
    n = 0

    def ck(cond: bool, msg: str) -> None:
        nonlocal n
        if not cond:
            raise AssertionError("[X] " + msg)
        n += 1
        if verbose:
            print(f"  [OK] {msg}")

    lam60 = C_LIGHT / F_MMW_60
    lam77 = C_LIGHT / F_MMW_77
    ck(abs(2 * 2.0 / lam60 - 800.6) < 1.0,
       f"① 60 GHz 多普勒 2 m/s ⇒ {2*2.0/lam60:.1f} Hz（题设约 800）")
    ck(abs(lam77 - 0.003893) < 5e-6, f"② 77 GHz 波长 {lam77*1e3:.3f} mm")
    ck(abs(2 * 2.0 / lam77 - 1027.4) < 1.0,
       f"③ 77 GHz 多普勒 2 m/s ⇒ {2*2.0/lam77:.1f} Hz")
    for B, ref in ((4e9, 3.75), (5e9, 3.00), (7e9, 2.14)):
        ck(abs(C_LIGHT / (2 * B) * 100 - ref) < 0.02,
           f"④ 距离分辨 B={B/1e9:.0f} GHz ⇒ {C_LIGHT/(2*B)*100:.2f} cm")

    width_m = 2 * CAM_DIST_M * math.tan(math.radians(CAM_HFOV_DEG) / 2)
    ppm = CAM_W_PX / width_m
    ck(abs(ppm - 332.5) < 1.0, f"⑤ 摄像头 5 m/60°/1080p ⇒ {ppm:.1f} px/m，"
                               f"1.7 m 人 {1.70*ppm:.0f} px")

    lam_w = C_LIGHT / F_WIFI_24
    ck(abs(lam_w * 100 - 12.49) < 0.02, f"⑥ 2.4 GHz 波长 {lam_w*100:.2f} cm")
    ck(abs(lam_w / (2 * 0.05) - 1.25) < 0.01,
       f"⑦ WiFi 混叠上限 {lam_w/(2*0.05):.2f} m/s（摔倒 2 m/s 超它 1.6 倍）")

    mo = motion("fall")
    ck(0.45 <= mo["feat"]["t_desc"] <= 0.95,
       f"⑧ 摔倒反解下降段 {mo['feat']['t_desc']:.3f} s（题设 0.45–0.95）")
    ck(abs(mo["feat"]["a_eff_g"] - 0.291) < 0.005,
       f"⑨ 自由落体反解 a_eff/g = {mo['feat']['a_eff_g']:.3f}（0.291）")
    ck(abs(mo["feat"]["dh_int"] - 0.70) < 0.01,
       f"⑩ 离散积分降幅 {mo['feat']['dh_int']:.3f} m")

    # β 的实现值必须等于标称值（半正弦脉冲下 v_end=2·v(a峰) 严格无偏）
    # walk / door 速度只有 0.02–0.10 m/s，冲击脉冲比制动还弱 ⇒ β 不可辨识，
    # 这两类不参与断言（它们靠 v 通道区分，本来就不靠 β）
    for act in ("fall", "sit_fast", "bend", "sofa", "bed"):
        f = motion(act)["feat"]
        ck(abs(f["beta"] - ACTIVITY[act]["beta"]) < 0.10,
           f"⑪ {act}: β 实现 {f['beta']:.3f} 对标称 {ACTIVITY[act]['beta']:.2f}")

    s = synth("fall", seed=7)
    f = s["feat"]
    ck(1.4 < f["mmwave"]["v"] < 3.0, f"⑫ 毫米波 v_pk={f['mmwave']['v']:.2f} m/s")
    ck(1.0 < f["camera"]["v"] < 3.5, f"⑬ 摄像头 v_pk={f['camera']['v']:.2f} m/s")
    ck(0.05 < f["lidar"]["h"] < 0.60, f"⑭ 激光雷达 h_post={f['lidar']['h']:.2f} m")
    ck(3.0 < f["imu"]["a"] + 1.0 < 8.0,
       f"⑮ IMU SVM 峰 {f['imu']['a']+1:.2f} g（题设 3–10）")
    ck(0.22 < s["obs"]["imu"]["svm"].min() < 0.60,
       f"⑯ IMU 下落谷 {s['obs']['imu']['svm'].min():.2f} g（带制动 ⇒ 到不了 0.1 g）")
    ck(f["wifi"]["beta"] is None, "⑰ WiFi 无制动通道（设计如此）")
    ck(f["imu"]["h"] is None, "⑱ IMU 无高度通道（结构性缺陷）")
    ck(f["ble"]["rssi"] is not None, "⑲ 蓝牙只有 RSSI 通道")

    vf = synth("fall", seed=11)["feat"]["mmwave"]["v"]
    vb = synth("bend", seed=11)["feat"]["mmwave"]["v"]
    vs = synth("sit_fast", seed=11)["feat"]["mmwave"]["v"]
    ck(vf > vb * 1.5, f"⑳ 毫米波：摔倒 {vf:.2f} > 弯腰 {vb:.2f} m/s")
    ck(vf - vs < 1.0, f"㉑ 毫米波：摔倒 {vf:.2f} 与快速坐下 {vs:.2f} 只差 "
                      f"{vf-vs:.2f} m/s（这正是它的软肋）")
    if verbose:
        print(f"\n  自检通过：{n} 条断言")
    return n


# ============================================================
# 7. 出图
# ============================================================
def _stft(x: np.ndarray, fs: float, nper: int):
    hop = max(1, nper // 4)
    win = np.hanning(nper)
    frames = list(range(0, x.size - nper, hop))
    Z = np.array([np.fft.fftshift(np.fft.fft(x[i:i + nper] * win)) for i in frames])
    f = np.fft.fftshift(np.fft.fftfreq(nper, 1 / fs))
    t = np.array([(i + nper / 2) / fs for i in frames])
    return f, t, Z


def make_fig(out: Path, act: str = "fall", seed: int = 20260560) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False

    s = synth(act, seed=seed)
    mo, ob, fe = s["motion"], s["obs"], s["feat"]
    C = dict(bg="#0e1117", fg="#e8e8e8", grid="#2a2f3a", red="#e8465a",
             org="#f0a02a", grn="#39c07a", blu="#3f9bd8", pur="#9b6bd8",
             cyn="#2fc7c7")
    fig, axs = plt.subplots(3, 2, figsize=(13.6, 9.8))
    fig.patch.set_facecolor(C["bg"])
    for ax in axs.ravel():
        ax.set_facecolor(C["bg"])
        ax.tick_params(colors=C["fg"], labelsize=8)
        for sp in ax.spines.values():
            sp.set_color(C["grid"])
        ax.grid(alpha=.22, color=C["grid"], lw=.6)
        ax.set_facecolor(C["bg"])

    ax = axs[0, 0]
    ax.plot(mo["t"], mo["h"], color=C["cyn"], lw=1.8)
    ax.set_title("① 重心高度 $h(t)$ 真值（m）", color=C["fg"], fontsize=10)
    ax.set_ylabel("m", color=C["fg"], fontsize=9)
    ax.text(.03, .08, f"总降幅 {mo['feat']['dh_int']:.2f} m",
            transform=ax.transAxes, color="#ffd479", fontsize=8)

    ax = axs[0, 1]
    ax.plot(mo["t"], mo["v"], color=C["org"], lw=1.8, label="真值")
    ax.plot(ob["mmwave"]["t"], ob["mmwave"]["v_obs"], color=C["red"], lw=.7,
            alpha=.7, label="毫米波")
    ax.plot(ob["camera"]["t"], ob["camera"]["v_obs"], color=C["grn"], lw=.7,
            alpha=.7, label="摄像头")
    ax.set_title("② 垂直速度 $v(t)$：$f_d=2v/\\lambda$ 直接给", color=C["fg"],
                 fontsize=10)
    ax.set_ylabel("m/s", color=C["fg"], fontsize=9)
    ax.legend(fontsize=7, facecolor=C["bg"], edgecolor=C["grid"],
              labelcolor=C["fg"])

    ax = axs[1, 0]
    # 多普勒要到 1 kHz 以上，测速帧率 100 Hz 的包络不够用：
    # 必须按基带采样（这里取 4 kHz，Nyquist 2 kHz）重算复基带
    fs_bb = 4000.0
    tb = np.arange(int(ob["mmwave"]["t"][-1] * fs_bb)) / fs_bb
    vb = np.interp(tb, ob["mmwave"]["t"], ob["mmwave"]["v_obs"])
    s_bb = np.exp(1j * 2 * np.pi * np.cumsum(2 * vb / ob["mmwave"]["lam"]) / fs_bb)
    f, tt, Z = _stft(s_bb, fs_bb, 256)
    sel = tt <= 2.4
    im = ax.pcolormesh(tt[sel], f / 1e3,
                       20 * np.log10(np.abs(Z[sel].T) + 1e-9),
                       shading="nearest", cmap="magma")
    ax.set_title("③ 毫米波多普勒谱（kHz）：摔倒特征在 1 kHz，微动在 <0.2 kHz",
                 color=C["fg"], fontsize=10)
    ax.set_ylabel("kHz", color=C["fg"], fontsize=9)
    plt.colorbar(im, ax=ax, pad=.01).ax.tick_params(labelsize=7, colors=C["fg"])
    ax.text(.02, .95, f"峰值 $f_d$={ob['mmwave']['fd'].max():.0f} Hz",
            transform=ax.transAxes, color="#ffd479", fontsize=8, va="top")

    ax = axs[1, 1]
    ax.plot(ob["camera"]["t"], ob["camera"]["raw"], color=C["grn"], lw=1.0,
            alpha=.9)
    ax.set_title(f"④ 摄像头重心像素高（{ob['camera']['px_per_m']:.0f} px/m，"
                 f"全身 {ob['camera']['body_px']:.0f} px）", color=C["fg"],
                 fontsize=10)
    ax.set_ylabel("px", color=C["fg"], fontsize=9)

    ax = axs[2, 0]
    im = ax.pcolormesh(ob["wifi"]["t"], np.arange(ob["wifi"]["n_sc"]),
                       ob["wifi"]["raw"], shading="nearest", cmap="viridis")
    ax.set_title("⑤ WiFi CSI 幅度（64 子载波）：多径叠加，0.7 m 过 11 个衰落零点",
                 color=C["fg"], fontsize=10)
    ax.set_ylabel("子载波", color=C["fg"], fontsize=9)
    plt.colorbar(im, ax=ax, pad=.01).ax.tick_params(labelsize=7, colors=C["fg"])

    ax = axs[2, 1]
    ax.plot(ob["imu"]["t"], ob["imu"]["svm"], color=C["pur"], lw=1.3)
    ax.axhline(1.0, color=C["grid"], ls=":", lw=1)
    ax.set_title(f"⑥ IMU 比力模 SVM（g）：谷 {ob['imu']['svm'].min():.2f}、"
                 f"峰 {ob['imu']['svm'].max():.2f}", color=C["fg"], fontsize=10)
    ax.set_ylabel("g", color=C["fg"], fontsize=9)
    ax.text(.55, .75, f"谷 {ob['imu']['svm'].min():.2f} g\n峰 {ob['imu']['svm'].max():.2f} g",
            transform=ax.transAxes, color="#ffd479", fontsize=8)

    for a_ in list(axs[2, :]) + list(axs[:2, :].ravel()):
        a_.set_xlabel("时间 s", color=C["fg"], fontsize=9)

    fig.suptitle(f"W56 · 一次「{mo['label']}」的六种传感观测（合成，同一种子）",
                 color=C["fg"], fontsize=13, y=.985)
    fig.tight_layout(rect=(0, 0, 1, .965))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=135, facecolor=C["bg"])
    plt.close(fig)
    return out


# ============================================================
# 8. CLI
# ============================================================
def main() -> int:
    ap = argparse.ArgumentParser(
        description="合成一次摔倒（或任一负样本）的六种传感观测，打印判别特征。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="通道可用性：WiFi 无 beta/h/th；蓝牙只有 RSSI；IMU 无 h。")
    ap.add_argument("--activity", default="fall", choices=sorted(ACTIVITY),
                    help="活动类（默认 fall）")
    ap.add_argument("--seed", type=int, default=20260560, help="随机种子")
    ap.add_argument("--jitter", type=float, default=0.0,
                    help="类内抖动系数（0 = 取组中值）")
    ap.add_argument("--fig", nargs="?", const="", default=None,
                    help="出六联图；不给路径则用 results/figs/fig_sig6.png")
    ap.add_argument("--json", nargs="?", const="", default=None,
                    help="特征写入 JSON")
    ap.add_argument("--selftest", action="store_true", help="跑断言自检")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]

    if args.selftest:
        print("=" * 78)
        print("  sig_fall.py 自检")
        print("=" * 78)
        n = selftest()
        print(f"  ⇒ {n} 条断言全部通过")
        return 0

    s = synth(args.activity, seed=args.seed, jitter=args.jitter)
    mo, fe = s["motion"], s["feat"]
    print("=" * 78)
    print(f"  活动：{mo['label']}（{args.activity}）　种子 {args.seed}　抖动 {args.jitter}")
    print("=" * 78)
    mf = mo["feat"]
    print(f"  运动学真值：v_pk={mf['v_pk']:.3f} m/s　beta={mf['beta']:.3f}　"
          f"a_imp={mf['a_imp']:.2f} g（SVM 峰 {mo['svm_peak']:.2f} g）")
    print(f"              下降段 {mf['t_desc']:.3f} s　冲击 {mf['t_imp']*1e3:.1f} ms　"
          f"a_eff/g={mf['a_eff_g']:.3f}　总降幅 {mf['dh_int']:.3f} m")
    print()
    print("  各传感观测到的判别特征（- = 该传感测不到这一维）")
    print("  " + "-" * 72)
    print(f"  {'传感':<8}{'v_pk':>8}{'beta':>8}{'a_imp':>8}{'h_post':>9}{'th':>8}{'RSSI':>8}")
    for name in OBSERVERS:
        f = fe[name]

        def g(k, fmt="{:.2f}"):
            return fmt.format(f[k]) if f[k] is not None else "  -"
        print(f"  {name:<8}{g('v'):>8}{g('beta'):>8}{g('a'):>8}"
              f"{g('h'):>9}{g('th'):>8}{g('rssi'):>8}")
    print()

    if args.fig is not None:
        p = Path(args.fig) if args.fig else root / "results" / "figs" / "fig_sig6.png"
        make_fig(p, act=args.activity, seed=args.seed)
        print(f"  [OK] 图：{p}")
    if args.json is not None:
        p = Path(args.json) if args.json else root / "results" / "sig_fall.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(dict(activity=args.activity, seed=args.seed,
                                     motion_feat=mo["feat"], sensor_feat=fe),
                                ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [OK] JSON：{p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
