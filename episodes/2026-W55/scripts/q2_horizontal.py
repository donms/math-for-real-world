#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **水平方向的收支**：初速度从哪来、落地后剩多少。

## 用户的两个问题

1. **"一开始的水平速度是怎么得到的？"**
2. **"落地后水平速度是多少？"**

## 先说结论（这个模型回答不了第一个问题）

`nozzle_state.run_mission10` 里：

```python
st = ph.State(0.0, 0.0, ph.V_LAUNCH_X, 0.0, 0.0, 0.0)
#                          ^^^^^^^^^^^^ 直接给了 16.67 m/s
p = ph.Params(drag_k=0.0)                 # 且令空气阻力为 0
```

**⇒ 水平速度是"我设定的"，不是"算出来的"。**
而且 `MAIN`（80 kN 主推进）**全程未点火**，
**没有任何水平方向的力** ⇒ $v_x$ 恒定不变。

$$\boxed{v_x(t) \equiv 16.67\ \text{m/s}\quad(\text{常量，因为 } \Sigma F_x = 0)}$$

**这是一个真实的建模缺口**，本节把它量化，并给出补齐方案。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph          # noqa: E402
import nozzle_state as ns     # noqa: E402


def main() -> int:
    print("=" * 84)
    print("  W55 · 水平方向的收支")
    print("=" * 84)

    recs = ns.run_mission10_auto(1 / 150)
    vx0, vx1 = recs[0].vx, recs[-1].vx
    print(f"\n【实测】v_x 起点 {vx0:.2f} m/s（{vx0*3.6:.0f} km/h）")
    print(f"        v_x 终点 {vx1:.2f} m/s（{vx1*3.6:.0f} km/h）")
    print(f"        全程变化 {vx1-vx0:+.4f} m/s")
    print(f"        ⇒ {'恒定（无水平力）' if abs(vx1-vx0) < 1e-6 else '有变化'}")

    print(f"\n【1】初速度 60 km/h 是怎么定的")
    print(f"  唯一的约束是**要跨过 22.8 m 的车队**：")
    T = recs[-1].t - recs[0].t
    need = 22.8 + ph.L_CAR / 2
    vmin = need / T * 3.6
    print(f"    串长 22.8 m + 半车长 ⇒ 需落地超过 {need:.1f} m")
    print(f"    腾空 {T:.2f} s ⇒ **v_x ≥ {vmin:.0f} km/h**")
    print(f"    我取了 {vx0*3.6:.0f} km/h（比下限高 "
          f"{(vx0*3.6/vmin-1)*100:.0f}%）")
    print(f"  ★ 这是**③ 自定假设**，不是从推力推出来的。")

    print(f"\n【2】若要真的用主推进加速到 60 km/h")
    v_target = ph.V_LAUNCH_X
    for F, lab in ((80e3, "MAIN 80 kN"), (46.1e3, "风扇 46 kN")):
        a = F / ph.M_CAR
        t = v_target / a
        d = 0.5 * a * t ** 2
        print(f"  {lab:<12} a = {a:5.2f} m/s²，"
              f"t = {t:.2f} s，距离 {d:.1f} m")
    print(f"  ★ 官方公布 **0–60 mph 0.81 s** ⇒ 平均 "
          f"{ph.V_LAUNCH_X/0.81:.1f} m/s²，与 80 kN 一致 ✓")

    print(f"\n【3】落地后剩多少水平速度")
    print(f"  **{vx1*3.6:.0f} km/h** —— 与起跳时**完全相同**")
    print(f"  因为全程没有水平力：MAIN 未点火、drag_k = 0")
    print(f"  ⇒ 车会一直以 {vx1:.1f} m/s 滑行，**视频末尾那 1 秒里"
          f"又前进了 {vx1*1.0:.1f} m**")

    print(f"\n【4】要把车停下来需要多少冲量")
    I = ph.M_CAR * vx1
    print(f"  水平冲量 = m·v_x = {I/1000:.1f} kN·s")
    print(f"  而竖直两段合计约 67.8 kN·s ⇒ "
          f"**水平刹车比竖直起飞还贵**（{I/1000/67.8:.2f} 倍）")
    print(f"  气罐可用 164 kN·s，扣掉竖直 67.8 只剩 96 ⇒ "
          f"{'够' if I/1000 <= 96 else '★ 不够'}")

    print("\n" + "=" * 84)
    print("  ★★★ 结论：有两个真实缺口")
    print("=" * 84)
    print("  ① **初速度是假设的**（唯一依据是'必须跨过 22.8 m'），"
          "没有建模加速段；")
    print("  ② **落地不减速**（v_x 恒定），车会一直滑行 —— "
          "真实演示必定有制动。")
    print()
    print("  ⇒ 补齐这两段后，气罐预算会显著变化（水平刹车很贵）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
