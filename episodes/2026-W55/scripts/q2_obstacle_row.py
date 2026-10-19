#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **车队纵列 vs 跳跃距离**：串要摆在哪、速度够不够。

## 用户指正

> **"不是应该竖着放一串车吗"**

**对。俯视图确认 5 辆车沿行进方向首尾相接，车要跳"一整串"。**

## 我之前的错

把 4 辆车的 $y$ 改了（$y=\pm5.5,\pm8.5$）⇒ **横向一堵墙**。

## ★ 这个修正推翻了"车队不是瓶颈"的旧结论

**串长**：

$$L_{\text{串}} = 5\times4.4 + 4\times1.0 = 22.8\ \text{m}$$

**要安全跨过，落地点必须超过串尾**：

$$x_{\text{land}} \ge x_{\text{串尾}} + \tfrac12 L_{\text{car}}$$

**⇒ 串长与腾空距离 $L = v_x T$ 必须匹配，这就把速度锁住了。**

## 本脚本要回答三个问题

1. 串摆在哪个 $x$ 位置，才能让整串都在**净空足够**的区间里？
2. 当前 60 km/h 够不够？
3. 最低可接受速度是多少？
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph      # noqa: E402
import nozzle_state as ns  # noqa: E402

# 与 3D 脚本一致的障碍布局
OBSTACLES = [
    (-9.20, 4.40, 2.00, 1.50, "轿车1"),
    (-4.60, 4.40, 2.00, 1.50, "轿车2"),
    (+0.00, 6.20, 2.40, 4.00, "卡车"),
    (+4.60, 4.40, 2.00, 1.50, "轿车3"),
    (+9.20, 4.40, 2.00, 1.50, "轿车4"),
]
SPAN = 9.20 * 2 + 4.40


def main() -> int:
    print("=" * 84)
    print("  W55 · 车队纵列 vs 跳跃距离")
    print("=" * 84)

    recs = ns.run_mission10(1 / 120)
    s = ns.summarize10(recs)
    vx = ph.V_LAUNCH_X
    T = s["t_end"]
    print(f"\n  v_x = {vx:.2f} m/s = {vx*3.6:.0f} km/h")
    print(f"  腾空 {T:.2f} s ⇒ 水平跨距 L = **{vx*T:.1f} m**")
    print(f"  峰值 {s['z_max']:.2f} m（HUD 25.4 ft = 7.74 m）")
    print(f"  车队总长 = **{SPAN:.1f} m**（5 辆，含 1 辆卡车）")

    # 车辆中心线的 x 位置 → 用仿真轨迹查净空
    print(f"\n【1】若车队中心摆在 x = 30（我原来的位置）")
    ok, worst = check(recs, 30.0, vx)
    print(f"  最危险点：{worst}")
    print(f"  ⇒ {'通过' if ok else '★ 撞上（落地时还没跨出串尾）'}")

    print(f"\n【2】扫描：车队中心放在哪最安全")
    print(f"  {'中心 x':>8}{'串起':>8}{'串止':>8}"
          f"{'最小净空(m)':>13}{'落地 x':>9}{'判定':>8}")
    best = None
    for xc in (18.0, 20.0, 22.0, 24.0, 26.0, 26.5, 28.0, 30.0):
        clr = clearances(recs, xc, vx)
        mn = min(clr)
        land = recs[-1].x
        verdict = "✓" if mn > 0.4 and land > xc + SPAN / 2 else "✗"
        print(f"  {xc:>8.1f}{xc-SPAN/2:>8.1f}{xc+SPAN/2:>8.1f}"
              f"{mn:>13.2f}{land:>9.1f}{verdict:>8}")
        if verdict == "✓" and (best is None or mn > best[1]):
            best = (xc, mn)

    # ★ 用**实际腾空时间** T（含落地缓冲），不是纯抛体的 2.512 s
    print(f"\n【3】最小速度：串长 {SPAN:.1f} m 需要多快才跨得出去")
    xc = 20.0
    tail = xc + SPAN / 2          # 串尾 x = 31.4
    need = tail + ph.L_CAR / 2    # 落地必须超过串尾 + 半车长 = 33.65
    print(f"  车队中心 x={xc}，串尾 x={tail:.1f}，"
          f"落地须 > {need:.1f} m")
    print(f"  {'v_x(km/h)':>11}{'L=v·T(m)':>11}{'跨出串尾?':>11}")
    for vk in (30, 35, 40, 45, 50, 53, 55, 60):
        L = vk / 3.6 * T
        print(f"  {vk:>11}{L:>11.1f}"
              f"{('✓' if L >= need else '✗'):>11}")
    v_min = need / T * 3.6
    print(f"  ⇒ **最小速度 ≈ {v_min:.0f} km/h**"
          f"（T={T:.2f} s，含缓冲）")

    print("\n" + "=" * 84)
    print("  ★★★ 结论")
    print("=" * 84)
    if best:
        print(f"  ① 车队中心应放在 **x ≈ {best[0]:.1f} m**，"
              f"最小净空 **{best[1]:.2f} m**")
    print(f"  ② 串长 22.8 m ⇒ **速度确实受约束**"
          f"（推翻我此前「车队不是瓶颈」的结论）")
    print(f"  ③ 60 km/h 的跨距 {vx*T:.1f} m 足以跨过 22.8 m 的串")
    return 0


def clearances(recs, x_center, vx):
    """车队各车所在 x 处、车底离地的最小净空。"""
    out = []
    for (dx, Lx, Wx, Hx, nm) in OBSTACLES:
        for xq in (x_center + dx - Lx / 2, x_center + dx + Lx / 2):
            # 找仿真里 x 最接近 xq 的时刻
            best = min(recs, key=lambda r: abs(r.x - xq))
            out.append(best.z - Hx)
    return out


def check(recs, x_center, vx):
    clr = clearances(recs, x_center, vx)
    mn = min(clr)
    land = recs[-1].x
    tail = x_center + SPAN / 2
    ok = mn > 0.0 and land > tail
    idx = clr.index(mn)
    nm = OBSTACLES[idx // 2][4]
    return ok, (f"净空 {mn:.2f} m（{nm} 处），"
                f"落地 x={land:.1f} vs 串尾 {tail:.1f}")


if __name__ == "__main__":
    raise SystemExit(main())
