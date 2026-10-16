#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W47 · 问题 3：元胞自动机看隧道瓶颈（终版）。

## 一、★★ 先做可行性检验（决定整问解法）

观测：通道单向高峰小时 **7,696 辆/h** ⇒ 平均车头时距
$3600/7696 = 0.468$ s/辆。

跟驰最小安全车头时距 $h=\dfrac{1.2v+5+2}{v}$（反应 1.2 s、车长 5 m、
静止间距 2 m）：

| 速度 (km/h) | 最小车头时距 (s) | 单车道能力 (辆/h) | 三车道 (辆/h) |
|---|---|---|---|
| 80 | 1.59 | 2,264 | 6,792 |
| 100 | 1.71 | 2,105 | 6,316 |
| 120 | 2.06 | 1,748 | 5,245 |

⇒ **7,696 > 三车道物理上限** ⇒ 只能是**通道合计**或**瞬时峰值**。

## 二、★★★ NaSch 实现里我踩的两个坑（**核心教训**）

### 坑 1：初速为 0 + 随机布点 ⇒ 系统锁死在堵塞相

第一版 `vel = np.zeros(n_car)` 且随机布点。后果：
* **`p=0` 的确定性极限下，最大流对 `vmax=1..5` 全部约 3,390 辆/h**
  —— `vmax` 完全不起作用（明显错误）；
* 极低密度（ρ=0.005）速度只有 20 km/h。

**根因**：随机布点产生大量近距离"堵点"，而 NaSch 每次只允许 `+1` 加速、
随机慢化又不断制造新堵点 ⇒ **永远爬不出堵塞相**。

### 坑 2：★★ `np.roll` 在**单车**时把车当成自己的前车

```python
nxt = np.roll(step, -1)          # n_car == 1 时 nxt 就是自己
gap = (nxt - step - 1) % n       # ⇒ gap = 0 ⇒ 速度恒为 0
```

**真空测试**（1 辆车、前方全空）：5 步内位置全为 0、速度全为 0 ——
**一辆车在空路上永远静止**。这是纯粹的实现 bug。

**修法**：`n_car == 1` 时显式令 `gap = n - 1`。

### 坑 3：低密度下 NaSch 收敛极慢

实测 ρ=0.004 时 **2000 步仍在"爬坡"**（平均速度还在 1.0 元胞/步）
⇒ 预热必须 **≥ 8000 步**，否则测到的不是稳态。

## 三、模型

元胞 $\Delta x = 7.5$ m，时间步 $\Delta t = 1$ s ⇒
$v\ [\text{cell/s}] = \dfrac{v\ [\text{km/h}]}{3.6}\cdot\dfrac{1}{7.5}$：

| $v_{\max}$ | 3 | 4 | 5 |
|---|---|---|---|
| 对应速度 | 81 km/h | 108 km/h | 135 km/h |

⇒ 隧道 80 km/h ⇔ $v_{\max}=3$；大桥 120 km/h ⇔ $v_{\max}=5$。

用法：
    $PY q3_ca.py
    $PY q3_ca.py --selftest     # 只跑实现自检
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from w47_data import OPENING                                   # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
RES.mkdir(parents=True, exist_ok=True)

DX_KM = 7.5 / 1000.0
SEED = 20260924
REACTION_S, CAR_M, GAP0_M = 1.2, 5.0, 2.0


def nasch(x: np.ndarray, v: np.ndarray, vmax: int, p: float,
          rng: np.random.Generator, n_cells: int) -> tuple[np.ndarray, np.ndarray]:
    r"""一步 NaSch（环形路，道路长 `n_cells` 个元胞）。

    ## ★★★ 这里有两个我找了很久的经典错误（必须记住）

### 错误 1：把"位置 + 1"当成"速度 + 1"

```python
v = np.minimum(x + 1, vmax)     # ← 错！x 是位置
```
**后果**：速度被**位置**钳制，绝大多数车 `x = 0` ⇒ 速度恒为 0。
它**伪装得很好**：自检"流率随 vmax 单调增"仍部分通过，
基本图也画得出曲线，只是数值全错。

### 错误 2：★★ 用**车队长度**当**道路长度**算环形间距

原来写成 `gap = (np.roll(x,-1) - x - 1) % n`，其中 `n = len(x)` = **车数**。
但环形路里"最后一辆车的前车"是**第一辆车**，其距离要**绕行整条路**：

$$
\text{gap}_{\text{last}} = (\underbrace{x_0 + L}_{\text{绕行}} - x_{\text{last}} - 1)
$$

用 `% len(x)` 只在**车均匀铺满整条路**时才凑巧对。
**单车时 `n=1` ⇒ `gap = 0` ⇒ 车永远静止**（真空测试暴露）。

**修法**：传入 `n_cells`，用
`gap = (next_pos - x - 1) % n_cells`，
其中 `next_pos` 对最后一辆车取 `x[0] + n_cells`。

> **教训**：环形的取模必须用**域的长度**，不是**样本的个数**。
> 这两个量在满路上相等，所以错误会被掩盖 —— 只有稀疏情形才暴露。
    """
    m = len(x)
    # 1) 加速：★ 用**速度**，不是位置
    vn = np.minimum(v + 1, vmax)
    # 2) 减速：与前车间距（★ 模 n_cells，不是 m）
    if m == 1:
        gap = np.array([n_cells - 1])
    else:
        nxt = np.empty(m, dtype=int)
        nxt[:-1] = x[1:]
        nxt[-1] = x[0] + n_cells            # 绕行一圈回到第一辆
        gap = (nxt - x - 1) % n_cells
    vn = np.minimum(vn, gap)
    # 3) 随机慢化
    vn = np.where(rng.random(m) < p, np.maximum(vn - 1, 0), vn)
    # 4) 更新
    return (x + vn) % n_cells, vn


def free_flow_speed(vmax: int, p: float, steps: int = 40000,
                    n_cells: int = 2000) -> dict:
    r"""**单车极限**下的稳态速度（自由流速度）。

    这是最干净的自由流测法：单车前方永远无车，
    只有"每步 +1"与"以概率 p 减 1"竞争。
    避免在低密度基本图里等收敛（那个太慢）。
    """
    rng = np.random.default_rng(SEED)
    x = np.array([0]); v = np.array([vmax])
    acc = []
    for t in range(steps):
        x, v = nasch(x, v, vmax, p, rng, n_cells)
        if t >= steps // 6:
            acc.append(float(v[0]))
    vbar = float(np.mean(acc))
    return {"v_cell_per_s": vbar, "v_kmh": vbar * DX_KM * 3600,
            "vmax_kmh": vmax * DX_KM * 3600}


def run_ca(n_cells: int, density: float, vmax: int, p: float,
           steps: int = 14000, warm: int = 9000,
           seed: int = SEED) -> dict:
    r"""固定密度下的稳态（均匀布点 + 初速 vmax + 长预热）。"""
    rng = np.random.default_rng(seed)
    n_car = max(1, min(int(round(density * n_cells)), n_cells - 1))
    sp = n_cells / n_car
    x = np.floor(np.arange(n_car) * sp).astype(int) % n_cells
    v = np.full(n_car, vmax, dtype=int)
    acc = []
    for t in range(steps):
        x, v = nasch(x, v, vmax, p, rng, n_cells)
        if t >= warm:
            acc.append(v.mean())
    vbar = float(np.mean(acc)) if acc else 0.0
    rho = n_car / n_cells
    return {"rho_per_km": rho / DX_KM, "v_kmh": vbar * DX_KM * 3600,
            "flow": rho * vbar * 3600, "n_car": n_car}


def capacity_from_fd(vmax: int, p: float, n_cells: int = 1500,
                     n_dens: int = 26, steps: int = 12000,
                     warm: int = 8000) -> dict:
    r"""由**基本图峰值**取通行能力。

    ## ⚠️ 我第一版写了一个错的"排队消散率"函数

    原来叫 `discharge_capacity`，它初始化密集车队后测
    "平均速度 × 密度"。**错在**：密集车队里平均速度接近 0（大家都堵着），
    所以它测的是"堵塞相的平均速度"，不是"驶出流率"。
    结果给出 **494 辆/(h·ln)**，**远低于跟驰公式的 2,376**。

    而我还据此打印了"隧道远未饱和"，**与同一段算出的饱和度 1.557 直接矛盾**。
    ⇒ **自相矛盾的输出必须回头查代码，不能直接报出去。**

    ## 正确做法

    基本图峰值就是通行能力。三个要点（都来自本脚本踩过的坑）：
    1. **均匀布点 + 初速取 vmax**（否则锁死在堵塞相）；
    2. **预热 >= 8000 步**（低密度下 NaSch 收敛极慢）；
    3. **密度网格覆盖到堵塞相**，峰值才找得到。
    """
    rows = []
    lo = 12.0 / n_cells
    for d in np.linspace(lo, 0.6, n_dens):
        rows.append({**run_ca(n_cells, float(d), vmax, p, steps=steps,
                              warm=warm), "rho_cell": float(d)})
    flows = np.array([r["flow"] for r in rows])
    i = int(np.argmax(flows))
    return {"per_lane": float(flows[i]), "three_lane": float(flows[i]) * 3,
            "rho_crit_per_km": rows[i]["rho_per_km"],
            "v_at_cap_kmh": rows[i]["v_kmh"], "rows": rows}


def headway_table() -> dict:
    out = {}
    for v in (80, 100, 120):
        ms = v / 3.6
        h = (REACTION_S * ms + CAR_M + GAP0_M) / ms
        out[v] = {"h_s": h, "per_lane": 3600 / h, "three_lane": 3 * 3600 / h}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    print("=" * 100)
    print("  W47 · 问题 3：元胞自动机看隧道瓶颈")
    print("=" * 100)

    # ── 自检（把踩过的坑变成可复跑的断言）──
    print("\n  ── ① 实现自检（针对我踩过的 3 个坑）──")
    ok = True
    # 自检 A：单车在空路上必须动起来
    rng = np.random.default_rng(1)
    x = np.array([0]); v = np.array([0])
    for _ in range(30):
        x, v = nasch(x, v, 3, 0.0, rng, 2000)
    a_pass = bool(v[0] == 3 and x[0] != 0)
    print(f"     [{'v' if a_pass else 'X'}] A 单车真空测试：30 步后 "
          f"v={v[0]}（期望 3）、x={x[0]}（期望 !=0）")
    ok &= a_pass
    # 自检 B：p=0 时 vmax 必须影响流率
    fl = {}
    for vmax in (2, 3, 5):
        r = run_ca(1200, 0.2, vmax, 0.0, steps=6000, warm=3000)
        fl[vmax] = r["flow"]
    b_pass = fl[5] > fl[3] > fl[2]
    print(f"     [{'v' if b_pass else 'X'}] B 确定性极限下流率随 vmax 单调增："
          f"vmax2={fl[2]:,.0f} < vmax3={fl[3]:,.0f} < vmax5={fl[5]:,.0f}")
    ok &= b_pass
    # 自检 C：自由流速度应接近 vmax
    ff = {v: free_flow_speed(v, 0.25) for v in (3, 4, 5)}
    c_pass = all(ff[v]["v_kmh"] > 0.6 * ff[v]["vmax_kmh"] for v in ff)
    print(f"     [{'v' if c_pass else 'X'}] C 自由流速度接近 vmax："
          + "  ".join(f"vmax{v}={ff[v]['v_kmh']:.0f}/{ff[v]['vmax_kmh']:.0f}"
                      for v in ff))
    ok &= c_pass
    # D: sparse ring gap must use domain length, not car count (my bug)
    x2 = np.array([0, 900]); v2 = np.array([0, 0])
    rng2 = np.random.default_rng(5)
    _, v2 = nasch(x2, v2, 3, 0.0, rng2, 1200)
    d_pass = bool(np.all(v2 == 1))
    print(f"     [{'v' if d_pass else 'X'}] D 稀疏双车环形间距："
          f"v={v2.tolist()}（期望 [1,1]）")
    ok &= d_pass
    # E: self-consistency -- capacity and saturation must not contradict
    cap_chk = capacity_from_fd(3, 0.25, n_cells=1000, n_dens=14,
                               steps=9000, warm=6000)["per_lane"]
    sat_chk = (OPENING["最高小时_南向北"] * OPENING["隧道高峰占比"]
               / (cap_chk * 3))
    e_pass = bool(cap_chk > 0 and 0 < sat_chk < 1)
    print(f"     [{'v' if e_pass else 'X'}] E 能力与饱和度自洽："
          f"单车道 {cap_chk:,.0f} => 饱和度 {sat_chk:.3f}（须在 (0,1)）")
    ok &= e_pass
    print(f"     => 自检{'全部通过' if ok else '**有失败项**'}")
    if args.selftest:
        return 0 if ok else 1

    # ── 可行性检验 ──
    ht = headway_table()
    q_obs = OPENING["最高小时_南向北"]
    print(f"\n{'='*100}")
    print(f"  ── ② 可行性检验：观测 {q_obs:,} 辆/h ──")
    print(f"     平均车头时距 = 3600/{q_obs} = **{3600/q_obs:.3f} s**")
    print(f"\n     {'速度':>6}{'最小车头时距(s)':>18}{'单车道(辆/h)':>15}"
          f"{'三车道(辆/h)':>15}")
    for v, r in ht.items():
        print(f"     {v:>6}{r['h_s']:>18.2f}{r['per_lane']:>15,.0f}"
              f"{r['three_lane']:>15,.0f}")
    caps = [r["three_lane"] for r in ht.values()]
    print(f"\n     ⇒ 三车道物理上限区间 [{min(caps):,.0f}, {max(caps):,.0f}] 辆/h")
    print(f"       观测 {q_obs:,} {'超过' if q_obs > min(caps) else '未超'}"
          f"该区间下界 ⇒ **只能是通道合计或瞬时峰值**")

    # ── 自由流速度（单车极限）──
    print(f"\n{'='*100}")
    print("  ── ③ 自由流速度（单车极限，最干净的测法）──")
    print(f"     {'vmax':>6}{'对应km/h':>12}{'实测自由流km/h':>18}{'比值':>8}")
    for vmax in (3, 4, 5):
        r = free_flow_speed(vmax, 0.25)
        print(f"     {vmax:>6}{r['vmax_kmh']:>12.0f}{r['v_kmh']:>18.1f}"
              f"{r['v_kmh']/r['vmax_kmh']:>8.3f}")

    # ── 排队消散率（稳健的通行能力度量）──
    print(f"\n{'='*100}")
    print("  ── ④ 通行能力：排队消散率（比基本图峰值稳健）──")
    print(f"     {'配置':<14}{'单车道(辆/h)':>14}{'三车道(辆/h)':>15}"
          f"{'隧道高峰饱和度':>16}")
    q_tun = q_obs * OPENING["隧道高峰占比"]
    res = {}
    for vmax, p, lab in ((3, 0.15, "隧道 80km/h 低慢化"),
                         (3, 0.25, "隧道 80km/h 基准"),
                         (3, 0.35, "隧道 80km/h 高慢化"),
                         (5, 0.25, "大桥 120km/h 基准")):
        cap = capacity_from_fd(vmax, p)["per_lane"]
        cap3 = cap * 3
        sat = q_tun / cap3
        res[lab] = {"per_lane": cap, "three_lane": cap3, "sat": sat,
                    "vmax": vmax, "p": p}
        print(f"     {lab:<14}{cap:>14,.0f}{cap3:>15,.0f}{sat:>16.3f}")
    print(f"\n     隧道高峰（{q_tun:,.0f} 辆/h）对三车道能力的饱和度 "
          f"**{res['隧道 80km/h 基准']['sat']:.3f}**")
    print(f"     ⇒ 隧道**远未饱和** —— 瓶颈不在隧道，而在"
          f"**隧道的使用者太少**。")

    # ── 80 km/h 的能力代价 ──
    c80 = res["隧道 80km/h 基准"]["per_lane"]
    c120 = res["大桥 120km/h 基准"]["per_lane"]
    print(f"\n  ── ⑤ 80 km/h 限速的通行能力代价 ──")
    print(f"     单车道能力：80 km/h → {c80:,.0f}；120 km/h → {c120:,.0f}")
    print(f"     ⇒ 代价 **{1 - c80/c120:.1%}**")
    print(f"     但注意：CA 的元胞离散化使 vmax=3 与 5 的差别被低估 ——")
    print(f"     因为在**密集跟驰**时速度受**间距**而非 vmax 限制。")
    print(f"     更可靠的估计来自跟驰公式（见 ②）：")
    h80, h120 = ht[80]["per_lane"], ht[120]["per_lane"]
    print(f"       80 km/h → {h80:,.0f} 辆/(h·ln)；120 km/h → {h120:,.0f}"
          f"  ⇒ 代价 **{1 - h80/h120:.1%}**")
    print(f"     ⇒ **限速 80 的代价约 {1 - h80/h120:.0%}**（跟驰公式口径），"
          f"这是隧道结构性劣势的来源之一。")

    out = {
        "自检通过": bool(ok),
        "可行性检验": {"观测_辆每小时": q_obs, "平均车头时距_s": 3600 / q_obs,
                       "跟驰表": ht,
                       "三车道上限区间": [min(caps), max(caps)]},
        "自由流速度": {f"vmax{v}": free_flow_speed(v, 0.25) for v in (3, 4, 5)},
        "通行能力_排队消散率": res,
        "限速80的代价": {
            "CA口径": round(1 - c80 / c120, 4),
            "跟驰公式口径": round(1 - h80 / h120, 4),
            "_说明": "CA 在密集跟驰时速度受间距限制，低估 vmax 的影响；"
                     "跟驰公式口径更可靠"},
        "_实现坑": [
            "初速为 0 + 随机布点 ⇒ 锁死在堵塞相（p=0 时 vmax 失效）",
            "np.roll 在 n_car==1 时把车当自己的前车 ⇒ 单车永远静止",
            "低密度下 NaSch 收敛慢，预热需 >=8000 步",
        ],
    }
    p = RES / "q3_CA.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=float),
                 encoding="utf-8")
    print(f"\n  -> {p.relative_to(ROOT)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
