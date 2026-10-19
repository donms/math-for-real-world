#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **dt 敏感性**：为什么 `sim_anim` 落不了地，而 `physics.run_jump` 可以。

## 现象

| 调用 | 落地 $v_z$ |
|---|---|
| `physics.run_jump(dt=1/240)` | **−0.50** ✓ |
| `sim_anim.run_mission(dt=1/120)` | **−6.36** ✗ |

**两者用的是同一个 `BufferController`。⇒ 差别只可能在步长或调用方式。**
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("sa", HERE / "sim_anim.py")
sa = importlib.util.module_from_spec(spec)
sys.modules["sa"] = sa
spec.loader.exec_module(sa)
ph = sa.ph


def main() -> int:
    print("=" * 82)
    print("  W55 · dt 敏感性")
    print("=" * 82)

    print(f"\n  【physics.run_jump】")
    print(f"  {'dt':>10}{'z_max':>9}{'落地vz':>10}{'下落':>8}{'姿态':>8}")
    for dt in (1 / 120, 1 / 240, 1 / 480, 1 / 960):
        traj = ph.run_jump(n_turns=1.0, dt=dt)
        s = ph.summarize(traj)
        print(f"  1/{int(round(1/dt)):<8}{s['z_max']:>9.2f}"
              f"{s['vz_land']:>10.2f}{s['t_down']:>8.2f}"
              f"{s['theta_end_deg']:>8.0f}")

    print(f"\n  【sim_anim.run_mission】")
    print(f"  {'dt':>10}{'z_max':>9}{'落地vz':>10}{'姿态':>8}{'耗气':>8}")
    for dt in (1 / 120, 1 / 240, 1 / 480):
        recs = sa.run_mission(dt)
        print(f"  1/{int(round(1/dt)):<8}{max(r.z for r in recs):>9.2f}"
              f"{recs[-1].vz:>10.2f}"
              f"{ph.wrap_deg(recs[-1].theta):>8.0f}"
              f"{recs[-1].m_used:>8.1f}")

    print("\n" + "=" * 82)
    print("  ★ 判读")
    print("=" * 82)
    print("  · 若 physics.run_jump 在各种 dt 下都 −0.5 ⇒ 控制器没问题；")
    print("  · 若 sim_anim 在各种 dt 下都 −6.x ⇒ 是 run_mission 的写法问题。")
    print()
    print("  ★ 最可疑的一处：`sim_anim` 里 4 个竖推**把总力除以 4** 再各算 duty，")
    print("    而 `duty` 封顶 1.0 —— 若 `f_each > f_max`（即需求超过可用），")
    print("    总力就会被截在 4×15=60 kN。**而 39 kN 的需求理应不会被截。**")
    print("  ⇒ 更可能是 `ctrl.step` 的**触发时刻**在 sim_anim 里偏了。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
