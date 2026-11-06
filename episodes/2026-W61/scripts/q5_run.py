"""Q5：全程模拟 —— 0→503 km/h 的时间、距离与功率去向。

纵向动力学
----------
    m·dv/dt = F_drive − F_drag − F_roll
    F_drive = min(P/v, μ·Fz(v))
    Fz(v)   = m·g + ½ρ·ClA·v²      （下压力随 v² 增长）

低速段**受抓地限制**，高速段**受功率限制**，最后**受阻力限制**——
三段交接处就是设计要盯的地方。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

EP = Path(__file__).resolve().parents[1]
RES = EP / "results"
FIGS = RES / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

RHO = 1.15
M = 1800.0
G = 9.81
CDA = 0.521
CLA = 0.55
P = 1000e3
MU = 1.0
CRR = 0.010
DT = 0.002
T_MAX = 60.0


def accel(v: float) -> tuple[float, str]:
    fz = M * G + 0.5 * RHO * CLA * v ** 2
    f_traction = MU * fz
    f_power = P / max(v, 1.0)
    if v < 1.0:
        f_drive, mode = f_traction, "traction"
    elif f_power < f_traction:
        f_drive, mode = f_power, "power"
    else:
        f_drive, mode = f_traction, "traction"
    f_drag = 0.5 * RHO * CDA * v ** 2
    f_roll = CRR * M * G
    return (f_drive - f_drag - f_roll) / M, mode


def simulate() -> dict:
    v, s, t = 0.0, 0.0, 0.0
    hist = {"t": [], "v": [], "s": [], "a": [], "mode": []}
    marks = {100: None, 200: None, 300: None, 400: None, 500: None, 503.17: None}
    while t < T_MAX:
        a, mode = accel(v)
        hist["t"].append(t); hist["v"].append(v * 3.6); hist["s"].append(s)
        hist["a"].append(a / G); hist["mode"].append(mode)
        for kmark in marks:
            if marks[kmark] is None and v * 3.6 >= kmark:
                marks[kmark] = {"t": round(t, 2), "s_km": round(s / 1000, 3)}
        if abs(a) < 1e-4 and t > 5:
            break
        v += a * DT
        s += v * DT
        t += DT
        if v * 3.6 > 560:
            break
    return {"hist": hist, "marks": marks, "vmax_kmh": round(max(hist["v"]), 1)}


def main() -> int:
    sim = simulate()
    marks = sim["marks"]

    # 刹车距离（1.5 g）
    v503 = 503.17 / 3.6
    brake = v503 ** 2 / (2 * 1.5 * G)

    out = {
        "config": {"cda": CDA, "cla": CLA, "power_kw": P / 1e3, "mu": MU,
                   "mass_kg": M, "crr": CRR},
        "marks": marks,
        "vmax_kmh": sim["vmax_kmh"],
        "brake_distance_m": round(brake, 0),
        "runway_km": round((marks[500]["s_km"] + brake / 1000) if marks[500] else 0, 2),
    }
    (RES / "q5_run.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                     encoding="utf-8")

    print(f"[极速] 模拟最高 {sim['vmax_kmh']:.1f} km/h")
    print("[里程碑]")
    for k, v in marks.items():
        if v:
            print(f"   {k:6.1f} km/h: {v['t']:5.2f} s，{v['s_km']:6.3f} km")
    print(f"[刹车] 从 503 km/h 到停（1.5 g）需 {brake:.0f} m")
    print(f"[直道] 加速 + 刹车合计约 {out['runway_km']:.2f} km")

    plot(sim)
    return 0


def plot(sim: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import rcParams
    rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    rcParams["axes.unicode_minus"] = False

    h = sim["hist"]
    fig, ax = plt.subplots(1, 3, figsize=(15.6, 4.4), dpi=150)

    ax[0].plot(h["t"], h["v"], color="#e8604a", lw=2.4)
    for k, v in sim["marks"].items():
        if v and k in (100, 300, 500):
            ax[0].plot([v["t"]], [k], "o", color="#333")
            ax[0].annotate(f"{k}: {v['t']:.1f}s", (v["t"], k),
                           textcoords="offset points", xytext=(6, -14), fontsize=9)
    ax[0].axhline(503.17, color="#8a9bb0", ls="--", lw=1.2, label="现纪录 503.17")
    ax[0].set_xlabel("时间（s）")
    ax[0].set_ylabel("速度（km/h）")
    ax[0].set_title("速度-时间：先陡后缓", fontsize=12)
    ax[0].legend(frameon=False, fontsize=9)
    ax[0].grid(alpha=0.25)

    ax[1].plot(h["s"], h["v"], color="#569cd6", lw=2.4)
    ax[1].axhline(503.17, color="#8a9bb0", ls="--", lw=1.2)
    ax[1].set_xlabel("距离（m）")
    ax[1].set_ylabel("速度（km/h）")
    ax[1].set_title("速度-距离：500 之后爬得很慢", fontsize=12)
    ax[1].grid(alpha=0.25)

    modes = np.array(h["mode"])
    ax[2].plot(h["t"], h["a"], color="#7fb069", lw=2.4)
    ax[2].axhline(1.0, color="#e8604a", ls="--", lw=1.2, label="1 g")
    ax[2].set_xlabel("时间（s）")
    ax[2].set_ylabel("纵向加速度（g）")
    ax[2].set_title("加速度从 1 g 一路掉到 0.05 g", fontsize=12)
    ax[2].legend(frameon=False, fontsize=9)
    ax[2].grid(alpha=0.25)

    fig.tight_layout()
    fig.savefig(FIGS / "q5_run.png")
    print(f"[图] {FIGS / 'q5_run.png'}")


if __name__ == "__main__":
    raise SystemExit(main())
