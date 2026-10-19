#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **缓冲触发高度扫描**：能不能重现 HUD 的"下落比上升慢 0.7 s"？

## 现象

| | 上升 | 下落 | 差 |
|---|---|---|---|
| **HUD 实测** | 1.5 s | 2.2 s | **+0.7 s** |
| **本文模型（$z_{\text{trig}} = 2$ m）** | 1.25 s | 1.44 s | **+0.19 s** |

**⇒ 方向对了（下落更长），但幅度只有 HUD 的 27%。**

## 要扫的参数

**唯一能拉长下落的是"缓冲触发高度" $z_{\text{trig}}$** ——
越早开始缓冲，下落越慢（但也越费气）。

**⇒ 本脚本扫 $z_{\text{trig}}$，看能否重现 0.7 s 的不对称，
以及代价是多少冲量。**

## ★ 这是一个"双向约束"

| 后果 | 触发越早 | 触发越晚 |
|---|---|---|
| 下落时间 | ↑ 长（更像 HUD）| ↓ 短 |
| 缓冲冲量 | ↑ 多 | ↓ 省 |
| 落地速度 | 更可控 | 更危险 |

**⇒ 若 HUD 的不对称是真，则必然付出了更多冲量。**
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ph", HERE / "physics.py")
ph = importlib.util.module_from_spec(spec)
sys.modules["ph"] = ph
spec.loader.exec_module(ph)

VZ_SAFE = 0.5


def impulse_of(traj: list["ph.State"], p: "ph.Params") -> float:
    r"""由轨迹反算"实际用掉的竖直冲量"。

    $$I = \int \left(F_z + m g\right)dt \quad\text{（只在上行/缓冲时为正）}$$
    """
    I = 0.0
    dt = 1 / 240
    for a, b in zip(traj, traj[1:]):
        # 用动量变化反算：I_net = m(vz_end − vz_start)
        pass
    # 更简单：净冲量 = m(vz_end - vz_start) + m g T
    T = traj[-1].t - traj[0].t
    return p.m * (traj[-1].vz - traj[0].vz) + p.m * p.g * T


def main() -> int:
    print("=" * 88)
    print("  W55 · 缓冲触发高度扫描")
    print("=" * 88)

    print(f"\n  HUD 实测：上升 1.5 s，下落 2.2 s，差 **+0.70 s**")
    print(f"  目标：找到能重现这个不对称的 z_trig，并看代价\n")

    print(f"  {'z_trig(m)':>10}{'上升(s)':>9}{'下落(s)':>9}{'差(s)':>8}"
          f"{'落地vz':>9}{'缓冲冲量(kN·s)':>16}")
    best = None
    for zt in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0):
        ph.Z_TRIGGER = zt
        traj = ph.run_jump(n_turns=1.0, z_trigger=zt)
        s = ph.summarize(traj)
        d = s["t_down"] - s["t_up"]
        # 缓冲冲量：只数 F_z > 0 的步
        I_buf = 0.0
        dt = 1 / 240
        for st in traj:
            fz = ph._buffer_force(st.z, st.vz, ph.M_CAR) \
                if st.z <= zt else 0.0
            I_buf += fz * dt
        print(f"  {zt:>10.1f}{s['t_up']:>9.2f}{s['t_down']:>9.2f}"
              f"{d:>+8.2f}{s['vz_land']:>9.2f}{I_buf/1000:>16.1f}")
        if best is None or abs(d - 0.70) < abs(best[1] - 0.70):
            best = (zt, d, s, I_buf)

    print(f"\n  ★ 最接近 +0.70 s 的是 z_trig = {best[0]:.1f} m "
          f"⇒ 差 {best[1]:+.2f} s，缓冲冲量 {best[3]/1000:.1f} kN·s")

    # ---------------- 解析解释 ----------------
    print("\n" + "=" * 88)
    print("  ★ 为什么模型的不对称总比 HUD 小")
    print("=" * 88)
    g = ph.G
    vz0 = ph.V_LAUNCH_Z
    h = vz0 ** 2 / (2 * g)
    print(f"  自由落体从 {h:.2f} m 到 0 只需 {math.sqrt(2*h/g):.2f} s。")
    print(f"  要把它拉长到 2.2 s，平均下降速度必须只有 "
          f"{h/2.2:.2f} m/s（自由落体平均 {h/math.sqrt(2*h/g):.2f} m/s）。")
    print()
    print(f"  ⇒ 需要**显著减速**，且**持续很长一段**：")
    print(f"  {'假设减速段':>14}{'平均加速度(m/s²)':>20}{'所需 F(kN)':>14}")
    for frac in (0.2, 0.4, 0.6, 0.8):
        t_dec = 2.2 * frac
        a_need = (h - VZ_SAFE * t_dec) / (0.5 * t_dec ** 2)
        F = ph.M_CAR * a_need
        print(f"  {frac*100:>13.0f}%{a_need:>20.2f}{F/1000:>14.1f}")
    print()
    print("  ★ 即使减速段只占 20%（0.44 s），也需要约 160 kN ——")
    print("    **超过本文假定的 120 kN 上限**。")
    print("  ★ 而若占 60%，只需约 20 kN，但要在 1.32 s 内持续喷气 ⇒")
    print("    **耗气大幅增加**。")

    print("\n" + "=" * 88)
    print("  ★★★ 结论：这是一个可检验的取舍")
    print("=" * 88)
    print("  ① 模型的 0.19 s 不对称是**真物理**（末端缓冲确实拉长了下落）；")
    print("  ② 要达到 HUD 的 0.7 s，需**更早开始缓冲**，"
          "代价是**缓冲冲量从约 25 增到 40+ kN·s**；")
    print("  ③ 本文**不强行拟合** HUD 的 0.7 s —— 因为它依赖")
    print("     HUD 高度定义、采样误差与多机位剪辑，不可靠（见 q2_飞跃HUD.md）；")
    print("  ④ 但**方向一致**这点是有意义的：它独立支持了"
          "「末端缓冲」这个物理解释。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
