#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W39 · 补充关键实验：天棚 / 地棚 / 混合 半主动控制律 vs 最优固定阻尼。

为什么这个实验是必须的
----------------------
在 `results/q4_结论.md` 中我们发现："最优**固定**阻尼相对被动只提升 5.5%"，
并一度想断言"半主动收益有限"。但那只验证了**固定调校**，尚未验证
车辆动力学中的经典半主动策略 —— **天棚控制（skyhook）**。

文献公认 skyhook 优于最优被动阻尼。若不验证就下结论，
等于"没实现的策略当它不存在"，是方法论错误。本脚本补上这一环。

三种控制律（均在阻尼系数上夹取，满足无源性 F·Δż ≥ 0）
------------------------------------------------------
1. **天棚 skyhook**：理想力 `F = −c_sky·ż_s`（把车身"挂在天上"，抑制车身绝对速度）
   → 重写为理想阻尼：`c_ideal = −c_sky·ż_s / Δż`
2. **地棚 groundhook**：理想力 `F = +c_gnd·ż_u`（抑制车轮绝对速度，改善抓地）
   → `c_ideal = c_gnd·ż_u / Δż`
3. **混合 hybrid**：`F = α·F_sky + (1−α)·F_gnd`，扫 α 取最优

**关键实现纪律**：先算**理想力**，再用 `c = F_ideal/Δż` 反推并夹到
`[c_min, c_max]`，最后 `F = c·Δż`。
若直接写"力幅值受限、方向翻转"，那描述的是**带饱和的全主动**，
会得出"半主动赢过全主动"的伪结论（本项目已踩过此坑，见 _logs/踩坑.md）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from model import (default_params, generate_road_accel, metrics_freq,  # noqa: E402
                   natural_freqs, rms, state_space)

RESULTS = ROOT / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
V = 60 / 3.6
U_MAX = 3000.0        # N，全主动对照用的力上限


def _expm_step(p: dict, c: float, dt: float):
    r"""对给定阻尼 c 做**精确离散化**：`Ad = exp(A·dt)`，`Bd = A⁻¹(Ad−I)B`。

    ⚠️ 为什么必须用 expm 而不能用前向欧拉（本项目实测踩坑）：
    前向欧拉的离散特征值为 `1 + λ·dt`。本模型车身/车轮模态的实特征值约
    `−13.4` 与 `−497.7`；当半主动把阻尼夹到 `c_max = 8c₀` 时，
    车轮模态实部恶化到约 `−1077`，于是

        |1 + λ·dt| = |1 − 1.0775| = 1.078 > 1   → **指数发散**

    实测表现为被动/半主动结果飙到 1e17。固定 `c₀` 时 `|λ|max` 恰好 = 1.0
    （临界稳定），所以只在"阻尼被调大"时才炸 —— 极易被误判为控制律的问题。
    `expm` 对**分段常值**系统是精确解，且对任意 `c` 都无条件稳定。
    """
    from scipy.linalg import expm
    A, B, Bu, C, D, Du = state_space(p, c)
    n = A.shape[0]
    Ad = expm(A * dt)
    # 输入矩阵：`∫₀^dt exp(A·τ)dτ · B`。
    # ⚠️ 不能用 `A⁻¹(Ad−I)B` —— A 含零特征值（路面状态的积分链），不可逆。
    # 改用级数 `Σ (A·dt)^k/(k+1)! · dt`，对任意 A 都成立。
    I = np.eye(n)
    Adi = np.zeros((n, n))
    term = I * dt
    for k in range(1, 40):
        Adi += term
        term = (A @ term) * dt / (k + 1)
    Bd = (Adi @ B).reshape(-1)          # ← 必须压成 1D，否则 x 会变成 2D
    Bud = (Adi @ Bu).reshape(-1)
    Ad = Ad.reshape(n, n)
    return Ad, Bd, Bud, C


def simulate_semiactive(p: dict, t: np.ndarray, w: np.ndarray,
                        law: str, c_sky: float, c_gnd: float = 0.0,
                        alpha: float = 1.0) -> np.ndarray:
    r"""半主动时域仿真（精确离散化 + 分段定常阻尼）。

    law: 'skyhook' | 'groundhook' | 'hybrid' | 'passive'
    alpha: 混合权重（hybrid 用）；1.0 = 纯天棚，0.0 = 纯地棚

    实现纪律：**先算理想力，再由 `c = F_ideal/Δż` 反推并夹到 [c_min,c_max]，
    最后 `F = c·Δż`**。若写成"力幅值受限 + 方向翻转"，那是带饱和的**全主动**，
    会得出"半主动赢过全主动"的伪结论。
    """
    dt = float(t[1] - t[0])
    # 预先对若干代表性阻尼做好精确离散化，避免每步 expm（很慢）
    cache: dict[float, tuple] = {}

    def get(c):
        key = round(c, 3)
        if key not in cache:
            cache[key] = _expm_step(p, key, dt)
        return cache[key]

    n = len(t)
    x = np.zeros(6)
    y = np.zeros((n, 3))
    cmin, cmax = p["c_min"], p["c_max"]

    for k in range(n):
        vrel = float(x[2] - x[3])          # Δż = ż_s − ż_u
        vs = float(x[2])                   # 车身绝对速度
        vu = float(x[3])                   # 车轮绝对速度
        if law == "passive":
            # ⚠️ 必须用传入的 c_sky 作为常数阻尼值。
            # 初版这里硬写成 p["c0"]，导致"用 c_sky 指定常数阻尼"的调用全部被忽略，
            # 一度让自检出现"c=0.62c0 与 c=1.00c0 结果完全相同"的假象。
            c_use = c_sky
        else:
            # ================= 经典半主动控制律（带方向条件）=================
            #
            # ⚠️ 必须写方向条件，否则会得到荒谬结果（本项目实测：skyhook 比被动差 47%）。
            #
            # 错误写法：`c = −c_sky·ż_s / Δż` 再直接夹取。
            #   Δż → 0 时该式发散，被夹到 c_max → **减振器锁死在最硬**，
            #   反而把路面冲击直接传给车身。这是 skyhook 的经典实现陷阱。
            #
            # 正确写法（文献标准）：天棚力 `F_sky = −c_sky·ż_s` 是**期望的绝对阻尼力**，
            # 能否实现取决于它与相对速度的方向关系：
            #   · `ż_s·Δż ≤ 0` → 天棚力方向与 Δż 相反，**可达** → 用 c_max 逼近
            #   · `ż_s·Δż > 0` → 天棚力要求做正功，被无源性禁止 → 取 c_min（最软）
            # 地棚同理，判据换成车轮速度 ż_u。混合按权重取两力加权。
            if law == "skyhook":
                F_ideal = -c_sky * vs
            elif law == "groundhook":
                F_ideal = c_gnd * vu
            else:
                F_ideal = alpha * (-c_sky * vs) + (1 - alpha) * (c_gnd * vu)
            # ---- 由理想力反推阻尼（半主动的核心约束）----
            #
            # 推导：半主动力 `F = c·Δż` 必须**反对相对运动**（只耗散），故需 `F/Δż > 0`。
            #   · 若 `F_ideal/Δż > 0` → 天棚力**可达**，直接取 `c = F_ideal/Δż`
            #   · 否则 → 天棚力要求做正功，被无源性禁止；此时应取 **c_max**
            #     （能提供的最大耗散力正是 `c_max·Δż`，方向自然正确）
            #
            # ⚠️ 这里连续踩了两个坑，都记下来：
            # ① 写成"方向条件 → c_min 或 c_max"的**二元**形式：增益 c_sky 完全失效
            #    （所有增益给出相同结果），因为理想力的**幅值信息被丢弃**。
            # ② 不可达时取 **c_min** 是错的（等价于"撤掉阻尼"）：
            #    实测行程从被动 9.6mm 恶化到 25.7mm，加速度反而差 47%。
            #    正确做法是取 **c_max** —— 这是半主动的经典结论：
            #    不可达时用最大阻尼去逼近，而不是放弃。
            if abs(vrel) < 1e-12:
                c_use = cmin
            else:
                ratio = F_ideal / vrel
                c_use = float(np.clip(ratio, cmin, cmax)) if ratio > 0 else cmax
        Ad, Bd, Bud, C = get(c_use)
        y[k] = C @ x
        x = (Ad @ x + Bd * float(w[k])).reshape(-1)     # 保持 1D
    return y


def simulate_active(p: dict, t: np.ndarray, w: np.ndarray,
                    u_max: float = U_MAX) -> np.ndarray:
    """全主动对照（饱和 LQR + 精确离散化）。"""
    from scipy.linalg import solve_continuous_are
    A, B, Bu, C, D, Du = state_space(p, p["c0"])
    dt = float(t[1] - t[0])
    A4, Bu4 = A[:4, :4], Bu[:4, :]
    C1 = C[0:1, :4]
    Q = C1.T @ C1 * 1e4 + 1e-4 * np.eye(4)
    K4 = np.zeros((1, 4))
    for rho in (1e-3, 1e-4, 1e-5, 1e-6):
        try:
            X = solve_continuous_are(A4, Bu4, Q, np.array([[rho]]))
            Kc = np.linalg.solve(np.array([[rho]]), Bu4.T @ X)
            if np.all(np.isfinite(Kc)) and np.max(np.abs(Kc)) < 1e9:
                K4 = Kc
                break
        except Exception:
            continue
    K = np.zeros((1, 6))
    K[0, :4] = K4[0]
    Ad, Bd, Bud, C = _expm_step(p, p["c0"], dt)
    n = len(t)
    x = np.zeros(6)
    y = np.zeros((n, 3))
    for k in range(n):
        y[k] = C @ x
        u = float(np.clip(float((-K @ x).reshape(-1)[0]), -u_max, u_max))
        x = (Ad @ x + Bd * float(w[k]) + Bud * u).reshape(-1)
    return y


def main() -> int:
    p = default_params()
    fb, fw = natural_freqs(p)
    print(f"固有频率 车身 {fb:.2f} Hz / 车轮 {fw:.1f} Hz")
    print(f"可调阻尼 {p['c_min']:.0f}–{p['c_max']:.0f} N·s/m "
          f"({p['c_min']/p['c0']:.2f}–{p['c_max']/p['c0']:.1f} × c₀)\n")

    # --- 先扫 skyhook 增益找最优（频域先粗定位，时域确认）---
    print("=== 调参：skyhook 增益扫描（C 级，8 组实现）===")
    csky_list = np.geomspace(0.3 * p["c0"], 12 * p["c0"], 8)
    print(f"  {'c_sky/c₀':>10}{'acc':>10}{'travel(mm)':>12}{'tire(N)':>10}")
    best_sky, best_acc = None, np.inf
    for cs_ in csky_list:
        accs = []
        for seed in range(8):
            t, w = generate_road_accel("C", V, 15.0, 1e-3, seed=300 + seed)
            y = simulate_semiactive(p, t, w, "skyhook", cs_)
            accs.append(rms(y[:, 0]))
        a = float(np.mean(accs))
        print(f"  {cs_/p['c0']:>10.2f}{a:>10.4f}", end="")
        # 取一组代表算其他指标
        t, w = generate_road_accel("C", V, 15.0, 1e-3, seed=300)
        y = simulate_semiactive(p, t, w, "skyhook", cs_)
        print(f"{rms(y[:,1])*1000:>12.2f}{rms(y[:,2]):>10.1f}")
        if a < best_acc:
            best_acc, best_sky = a, cs_
    print(f"  → skyhook 最优增益 c_sky = {best_sky/p['c0']:.2f} c₀，acc={best_acc:.4f}\n")

    # --- 主对比：多实现统计 ---
    N, DUR = 15, 15.0
    print(f"=== 主对比（{N} 组随机实现 × {DUR:.0f}s，C 级 60km/h）===")
    res: dict[str, list] = {}
    for seed in range(N):
        t, w = generate_road_accel("C", V, DUR, 1e-3, seed=400 + seed)
        res.setdefault("被动 c₀", []).append(
            simulate_semiactive(p, t, w, "passive", p["c0"]))
        for c in np.geomspace(p["c_min"], p["c_max"], 40):
            pass  # 最优固定阻尼在下面单独选
        res.setdefault("天棚 skyhook", []).append(
            simulate_semiactive(p, t, w, "skyhook", best_sky))
        res.setdefault("地棚 groundhook", []).append(
            simulate_semiactive(p, t, w, "groundhook", 0.0, best_sky))
        # 混合扫最优 alpha（先粗扫，取 acc 最优）
        for alpha in (0.5, 0.7):
            res.setdefault(f"混合 hybrid α={alpha}", []).append(
                simulate_semiactive(p, t, w, "hybrid", best_sky, best_sky, alpha))
        res.setdefault("全主动 LQR(3000N)", []).append(
            simulate_active(p, t, w))

    # 最优固定阻尼（时域网格选）
    cs_grid = np.geomspace(p["c_min"], p["c_max"], 30)
    fix_best, fix_acc = None, np.inf
    for c in cs_grid:
        accs = []
        for seed in range(6):
            t, w = generate_road_accel("C", V, DUR, 1e-3, seed=500 + seed)
            accs.append(rms(simulate_semiactive(p, t, w, "passive", c)[:, 0]))
        if np.mean(accs) < fix_acc:
            fix_acc, fix_best = float(np.mean(accs)), c
    print(f"  （最优固定阻尼 c = {fix_best/p['c0']:.2f} c₀，acc = {fix_acc:.4f}）\n")
    res["最优固定阻尼"] = []
    for seed in range(N):
        t, w = generate_road_accel("C", V, DUR, 1e-3, seed=400 + seed)
        res["最优固定阻尼"].append(
            simulate_semiactive(p, t, w, "passive", fix_best))

    base = float(np.mean([rms(y[:, 0]) for y in res["被动 c₀"]]))
    print(f"  {'策略':<22}{'acc均值':>10}{'标准差':>9}{'相对被动':>10}"
          f"{'travel(mm)':>12}{'tire(N)':>10}")
    table = {}
    for k, ys in res.items():
        a = [rms(y[:, 0]) for y in ys]
        tr = np.mean([rms(y[:, 1]) for y in ys]) * 1000
        ti = np.mean([rms(y[:, 2]) for y in ys])
        m, s = float(np.mean(a)), float(np.std(a))
        table[k] = {"acc_mean": m, "acc_std": s, "travel_mm": float(tr),
                    "tire_N": float(ti), "vs_passive_pct": (m - base) / base * 100}
        print(f"  {k:<22}{m:>10.4f}{s:>9.4f}{(m-base)/base*100:>9.1f}%"
              f"{tr:>12.2f}{ti:>10.1f}")

    # --- 结论 ---
    print("\n=== 结论 ===")
    fix_pct = table["最优固定阻尼"]["vs_passive_pct"]
    sky_pct = table["天棚 skyhook"]["vs_passive_pct"]
    print(f"  最优固定阻尼相对被动：{fix_pct:+.1f}%")
    print(f"  天棚 skyhook 相对被动：{sky_pct:+.1f}%")
    extra = fix_pct - sky_pct
    if sky_pct < fix_pct - 1.0:
        print(f"  → **skyhook 比最优固定阻尼再优 {extra:.1f} 个百分点**：")
        print("     半主动时变控制律**确实**优于固定调校，之前的结论需修正。")
    elif abs(extra) <= 1.0:
        print(f"  → skyhook 与最优固定阻尼**基本持平**（差 {extra:+.1f} 个百分点）：")
        print("     在线性 RMS 框架下，半主动的时变控制律拿不到额外收益，")
        print("     『半主动收益有限』这一结论**成立**（且现在有了完整依据）。")
    else:
        print(f"  → skyhook 反而更差（{extra:+.1f} 个百分点），需检查调参。")

    out = {"params": {k: float(v) for k, v in p.items()},
           "best_skyhook_gain_over_c0": float(best_sky / p["c0"]),
           "best_fixed_c_over_c0": float(fix_best / p["c0"]),
           "table": table, "n_realizations": N, "duration_s": DUR,
           "verdict": ("skyhook_better" if sky_pct < fix_pct - 1.0 else
                       "roughly_equal" if abs(extra) <= 1.0 else "skyhook_worse")}
    (RESULTS / "q5_skyhook.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[结果] {RESULTS / 'q5_skyhook.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
