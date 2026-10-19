#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **落地横向偏移的步长收敛性扫描**。

## 为什么要做

同一次任务、同一套模型：

| 步长 | 落地横向 y |
|---|---|
| 1/120 | 0.566 m |
| 1/150 | 0.850 m |

差 0.28 m（相对 50%）。**若结果依赖步长，那它还不是物理量。**
用户判：**先查收敛性，再决定图/封面/口播里写哪个数。**

## 扫什么

`dt = 1/60, 1/120, 1/240, 1/480, 1/960`（用户指定 ≥5 个点），每个都输出：

* **落地横向 y**：过顶点后 `z` 首次 ≤ `Z_TOL` 的那一步
* **落地 vy**、**峰值 z**、**耗气**、**末帧 y / x / t**
* 另报**末帧 y**（有些实现把落地定义成记录结束）

## 判读

* 随 dt→0 单调收敛 ⇒ 取最细步长的值，报"收敛到 ±X cm"
* 震荡/漂移 ⇒ 模型里有随步长突变的机制（重点怀疑 PFM 占空比量化：`n=round(t_min/dt)`）

用完即弃（但结论会写进 `_logs/踩坑.md`）。
"""
from __future__ import annotations

import sys
from pathlib import Path

EP = Path(r".\episodes\2026-W55")
sys.path.insert(0, str(EP / "scripts"))

import nozzle_state as ns          # noqa: E402
import physics as ph               # noqa: E402

DT_LIST = [1 / 60, 1 / 120, 1 / 240, 1 / 480, 1 / 960]
Z_TOL = 0.02


def one(dt: float) -> dict:
    recs = ns.run_mission10_auto(dt)
    n = len(recs)
    ia = max(range(n), key=lambda i: recs[i].z)
    k_land = n - 1
    for i in range(ia, n):
        if recs[i].z <= Z_TOL:
            k_land = i
            break
    land = recs[k_land]
    m_total = 0.0
    try:
        m_total = float(sum((r.m_used or {}).values()))
    except Exception:                                    # noqa: BLE001
        m_total = float("nan")
    return dict(dt=dt, n=n, t_land=land.t, y_land=land.y, vy_land=land.vz,
                z_max=max(r.z for r in recs), m_total=m_total,
                y_last=recs[-1].y, x_land=land.x)


def main() -> int:
    print("=" * 88)
    print("  落地横向偏移 · 步长收敛扫描（Z_TOL = %.3f m）" % Z_TOL)
    print("=" * 88)
    print("   dt      步数   落地t    落地y(m)   落地vy    峰值z(m)   耗气(kg)  末帧y(m)  落地x(m)")
    print("  " + "-" * 86)
    rows = []
    for dt in DT_LIST:
        try:
            r = one(dt)
        except Exception as e:                            # noqa: BLE001
            print("  1/%-6.0f [X] %s" % (1 / dt, e))
            continue
        rows.append(r)
        print("  1/%-6.0f %5d  %7.3f  %8.4f  %7.2f  %8.3f  %8.2f  %8.4f  %8.2f"
              % (1 / dt, r["n"], r["t_land"], r["y_land"], r["vy_land"],
                 r["z_max"], r["m_total"], r["y_last"], r["x_land"]))

    if len(rows) >= 2:
        print("\n  —— 相对最细步长的偏差 ——")
        ref = rows[-1]["y_land"]
        for r in rows:
            d = r["y_land"] - ref
            print("    1/%-6.0f y=%8.4f  Δ=%+7.4f m (%+6.1f%%)"
                  % (1 / r["dt"], r["y_land"], d,
                     100 * d / ref if ref else float("nan")))
        print("\n  最细步长 1/%.0f 的落地 y = **%.4f m**（%.1f cm）"
              % (1 / rows[-1]["dt"], ref, 100 * ref))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
