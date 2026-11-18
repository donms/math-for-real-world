"""血糖动力学：Bergman 最小模型 + 双室胃排空 + CGM 间质液滞后。

单位约定（写死，别再混）
------------------------
* 血糖 G：mg/dL（÷18 = mmol/L）
* 胰岛素 I：μU/mL
* 时间：min
* 剂量：mg（50 g 碳水 = 50 000 mg）

模型（公开文献，①）
-------------------
    dG/dt = -(p1 + X)·G + p1·Gb + Ra/V_G
    dX/dt = -p2·X + p3·max(I - Ib, 0)
    dI/dt = -n·(I - Ib) + γ·max(G - h, 0)

    dq1/dt = -kabs·q1
    dq2/dt =  kabs·q1 - k21·q2
    Ra     =  k21·q2

    dG_isf/dt = (G - G_isf)/τ        （CGM 测的是组织间液）
"""
from __future__ import annotations

from dataclasses import dataclass, replace

MG_PER_MMOL = 18.0


@dataclass(frozen=True)
class Params:
    p1: float = 0.028        # 1/min  葡萄糖自身清除
    p2: float = 0.025        # 1/min  胰岛素作用衰减
    p3: float = 1.5e-5       # (μU/mL)^-1 min^-2  胰岛素敏感性
    n: float = 0.140         # 1/min  胰岛素清除
    gamma: float = 0.010     # (μU/mL)/(mg/dL)/min  胰岛素分泌
    h: float = 90.0          # mg/dL  分泌阈值
    Vg: float = 1.6          # dL/kg  分布容积
    Gb: float = 90.0         # mg/dL  基础血糖
    Ib: float = 8.0          # μU/mL  基础胰岛素
    kabs: float = 0.030      # 1/min  胃排空
    k21: float = 0.020       # 1/min  肠道吸收
    tau: float = 8.0         # min    CGM 滞后
    BW: float = 70.0         # kg


def simulate(meal_g: float = 50.0, T: float = 300.0, dt: float = 0.5,
             p: Params | None = None, with_cgm: bool = True) -> dict:
    """RK4 积分，返回时间序列。"""
    p = p or Params()
    D = meal_g * 1000.0
    G, X, I, q1, q2 = p.Gb, 0.0, p.Ib, D, 0.0
    G_isf = p.Gb

    def deriv(G, X, I, q1, q2, G_isf):
        Ra = p.k21 * q2
        dG = -(p.p1 + X) * G + p.p1 * p.Gb + Ra / (p.Vg * p.BW)
        dX = -p.p2 * X + p.p3 * max(I - p.Ib, 0.0)
        dI = -p.n * (I - p.Ib) + p.gamma * max(G - p.h, 0.0)
        dq1 = -p.kabs * q1
        dq2 = p.kabs * q1 - p.k21 * q2
        dG_isf = (G - G_isf) / p.tau
        return dG, dX, dI, dq1, dq2, dG_isf

    ts, Gs, Is, Xs, Ras, Isf = [], [], [], [], [], []
    t = 0.0
    steps = int(T / dt) + 1
    for _ in range(steps):
        ts.append(t)
        Gs.append(G)
        Is.append(I)
        Xs.append(X)
        Ras.append(p.k21 * q2 / (p.Vg * p.BW))
        Isf.append(G_isf)

        k1 = deriv(G, X, I, q1, q2, G_isf)
        k2 = deriv(*(v + 0.5 * dt * k for v, k in zip((G, X, I, q1, q2, G_isf), k1)))
        k3 = deriv(*(v + 0.5 * dt * k for v, k in zip((G, X, I, q1, q2, G_isf), k2)))
        k4 = deriv(*(v + dt * k for v, k in zip((G, X, I, q1, q2, G_isf), k3)))

        G += dt / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
        X += dt / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
        I += dt / 6 * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2])
        q1 += dt / 6 * (k1[3] + 2 * k2[3] + 2 * k3[3] + k4[3])
        q2 += dt / 6 * (k1[4] + 2 * k2[4] + 2 * k3[4] + k4[4])
        G = max(G, 20.0)          # 数值下限，防止发散
        G_isf += dt / 6 * (k1[5] + 2 * k2[5] + 2 * k3[5] + k4[5])
        t += dt

    return {"t": ts, "G": Gs, "I": Is, "X": Xs, "Ra": Ras,
            "G_isf": Isf if with_cgm else None, "params": p}


def summarize(res: dict) -> dict:
    """峰值、峰值时刻、回落时间。"""
    ts, Gs = res["t"], res["G"]
    i_peak = max(range(len(Gs)), key=lambda i: Gs[i])
    base = res["params"].Gb
    back = next((t for t, g in zip(ts, Gs) if t > ts[i_peak] and g < base + 10), None)
    return {"peak": Gs[i_peak], "peak_tt": ts[i_peak], "back_tt": back,
            "rise": Gs[i_peak] - base}


def calibrate(target_peak: float = 150.0, target_tt: float = 55.0,
              meal_g: float = 50.0) -> tuple[Params, dict]:
    """网格搜索 γ 与 p3，使峰值与峰值时刻接近目标（健康人 50 g 餐后）。"""
    best, best_err = None, 1e9
    for gamma in (0.010, 0.015, 0.020, 0.026, 0.032, 0.040):
        for p3 in (1.5e-5, 3e-5, 6e-5, 1e-4, 2e-4, 4e-4):
            for kabs in (0.020, 0.026, 0.030, 0.036, 0.044):
                p = replace(Params(), gamma=gamma, p3=p3, kabs=kabs)
                s = summarize(simulate(meal_g=meal_g, T=300, dt=1.0, p=p, with_cgm=False))
                err = abs(s["peak"] - target_peak) / 10 + abs(s["peak_tt"] - target_tt) / 5
                if err < best_err:
                    best_err, best, best_s = err, p, s
    return best, best_s


if __name__ == "__main__":
    base = Params()
    s0 = summarize(simulate(p=base))
    print(f"[初始参数] 峰值 {s0['peak']:.0f} mg/dL @ {s0['peak_tt']:.0f} min"
          f"，回落 {s0['back_tt']}")

    p, s = calibrate()
    print(f"[标定后]  峰值 {s['peak']:.0f} mg/dL @ {s['peak_tt']:.0f} min"
          f"，回落 {s['back_tt']}")
    print(f"          gamma={p.gamma:.3f}  p3={p.p3:.2e}  kabs={p.kabs:.3f}")
