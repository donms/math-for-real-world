#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **诊断**：落地缓冲为什么没生效。

## 症状

`physics.py` 的 `run_jump` 输出 `落地vz = -12.32 m/s`，
**等于自由落体速度** ⇒ 缓冲完全没起作用。

## 本脚本要查三件事

1. `_buffer_force` 在下降段是否被调用（返回值是否 > 0）？
2. `z_trigger = 2.0 m` 时，下落速度已有多大？需要的减速度是否超过 `FZ_MAX`？
3. `run_jump` 里的 `if st.z <= z_trigger` 判断是否真的命中？
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ph", HERE / "physics.py")
ph = importlib.util.module_from_spec(spec)
# ★ 必须先注册到 sys.modules：`@dataclass` 会在装饰时回查
#   `sys.modules[cls.__module__].__dict__`，未注册会抛 AttributeError。
sys.modules["ph"] = ph
spec.loader.exec_module(ph)


def main() -> int:
    print("=" * 84)
    print("  W55 · 落地缓冲诊断")
    print("=" * 84)

    g = ph.G
    m = ph.M_CAR
    vz0 = ph.V_LAUNCH_Z
    print(f"\n  起飞 vz0 = {vz0:.2f} m/s，峰值 {vz0**2/(2*g):.2f} m")

    # ---- 1) 自由落体到各高度时的速度 ----
    print(f"\n【1】自由落体到各高度时的速度（从峰值 {vz0**2/(2*g):.2f} m 落下）")
    h = vz0 ** 2 / (2 * g)
    print(f"  {'z(m)':>7}{'vz(m/s)':>10}{'需要 a(m/s²)':>14}"
          f"{'需要 F(kN)':>12}{'FZ_MAX 够?':>12}")
    for z in (5, 3, 2, 1.5, 1.0, 0.5, 0.2):
        vz = -math.sqrt(max(vz0 ** 2 - 2 * g * (h - z), 0))
        # ★ 正确符号：a = (vz² − v_safe²)/(2z) + g
        a = (vz * vz - ph.VZ_SAFE ** 2) / (2 * z) + g
        F = m * a
        print(f"  {z:>7.1f}{vz:>10.2f}{a:>14.2f}{F/1000:>12.1f}"
              f"{('✓' if F <= ph.FZ_MAX else '✗ 超限'):>12}")

    # ---- 2) _buffer_force 单独测 ----
    print(f"\n【2】`_buffer_force` 单独测试")
    print(f"  {'z':>6}{'vz':>9}{'返回 F(N)':>14}{'状态':>10}")
    for z, vz in ((2.0, -6.0), (1.0, -9.0), (0.5, -11.0),
                  (0.1, -12.0), (2.0, +6.0), (0.0, -12.0)):
        f = ph._buffer_force(z, vz, m)
        print(f"  {z:>6.1f}{vz:>9.1f}{f:>14.0f}"
              f"{('作用' if f > 0 else '不作用'):>10}")

    # ---- 3) 手工重跑，打印下降段 ----
    print(f"\n【3】手工重跑 run_jump，打印下降段（每 0.1 s）")
    p = ph.Params(drag_k=0.0)
    st = ph.State(0.0, 0.0, ph.V_LAUNCH_X, ph.V_LAUNCH_Z, 0.0, 0.0)
    dt = 1 / 240
    vz_max_seen = 0.0
    n_buf = 0
    samples = []
    while st.t < 20:
        fz = ph._buffer_force(st.z, st.vz, p.m) if st.z <= ph.Z_TRIGGER else 0.0
        if fz > 0:
            n_buf += 1
        st = ph.rk4_step(st, ph.Thrust(fz=fz), p, dt)
        if st.z < 0:
            break
        if int(st.t * 10) != int((st.t - dt) * 10):
            samples.append((st.t, st.z, st.vz, fz))
        vz_max_seen = min(vz_max_seen, st.vz)

    print(f"  {'t(s)':>6}{'z(m)':>8}{'vz(m/s)':>10}{'F_z(N)':>11}")
    for t, z, vz, fz in samples[-16:]:
        print(f"  {t:>6.2f}{z:>8.2f}{vz:>10.2f}{fz:>11.0f}")
    print(f"\n  ★ 缓冲作用过的步数：{n_buf}（{n_buf*dt:.2f} s）")
    print(f"  ★ 全程最负 vz = {vz_max_seen:.2f} m/s")
    print(f"  ★ 最终 z = {st.z:.3f}, vz = {st.vz:.2f}")

    if n_buf == 0:
        print("\n  ⇒ **缓冲从未触发** ⇒ 问题在 `run_jump` 的调用链，"
              "而不是控制器公式。")
    else:
        print("\n  ⇒ 缓冲触发过，但**力量不够**或**触发太晚**。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
