#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **脉冲频率调制（PFM）**：把"占空比需求 $d(t)$"变成"开关脉冲序列"。

## 为什么要有这个模块

之前的 PFM 直接写在 `nozzle_state.run_mission10` 的循环里，于是
**"记账方式"与"物理积分"耦合在同一段代码**，无法单独验证哪一半错了。
更严重的是：同一个任务、只改记账方式，落地横漂在 **0.57 – 8.28 m**
之间跳（14 倍）—— 见 `paper/论文.md` §6.7。

⇒ 本模块把调制器**独立出来**，使它 ① 可被一个纯账目脚本单独调用，
② 同一份代码里保留 legacy 三档，用于**复现**旧值并作对照。

## 两种实现

| kind | 采样 | 触发时刻 | 含义 |
|---|---|---|---|
| `legacy` | **步首** $d(t_n)$ | **落在网格上** $t_n$ | 旧实现：`pwm_acc += d*dt`，攒够 $t_{\min}$ 就在**这一步的开头**点火 |
| `analytic` | **步中点** $d(t_n+\Delta t/2)$ | **解析插值** $t_n+\tau$ | 新实现：预算按中点累积，触发时刻由预算**线性插值**求出，脉冲起止都是绝对时刻 |

`analytic` 的两条改动正好对上"与步长无关"的两个必要条件：

1. **累积用步中点**（二阶），而不是步首值（一阶）；
   步长一变，采样点不再落在不同的地方；
2. **脉冲序列解析化**：脉冲的起止时刻是**绝对时刻**，与网格无关；
   每一步只计算"本步与该脉冲的重叠比例"，力与耗气都按该比例施加。

⇒ 于是 $\int F\,dt = F_{\text{full}}\sum(\text{on}\cdot\Delta t)$
与 $\int d\,dt$ 的差只剩 **MIB 量化**（$<t_{\min}$），**且不随 $\Delta t$ 变化**。
这正是 `verify_pfm_ledger.py` 要证明的东西。

## 三档 legacy 与两档新实现的差别（`FORCE_MODE` / `MASS_MODE`）

| ledger | 力 | 耗气 | 用在 |
|---|---|---|---|
| `asrun` | **整步满推力** | 分数步 | ★ **旧代码的真实行为**（见下），用来复现 85.0 cm |
| `legacy1` | **整步满推力** | **整步** | 旧表 ①（超发 39%） |
| `legacy2` | 分数步 | **整步** | 旧表 ②（罐压掉快 ⇒ 系统漂移） |
| `legacy3` | 分数步 | 分数步 | 旧表 ③（逐项守恒，但仍用步首采样） |
| `analytic` | 分数步 | 分数步 | **本版**（步中点 + 解析脉冲） |

## ★★ `asrun` 这一档为什么必须存在

旧 `nozzle_state.run_mission10` 里写着

```python
f_now[n] = fnow * on_frac.get(...)      # 注释：本步只施加与该脉冲重叠的那部分
...
fz_n = fnow * w[2]                      # ← 却是满推力进动力学
fz_total += fz_n
```

⇒ **记录值按分数步、动力学按整步**。注释与代码不一致，而飞行结果里看不出来
（动画用的 `f_now` 是对的，物理用的是满的）。
留这一档，才能验证重构后的代码**复现得出旧的 85.0 cm**。
"""
from __future__ import annotations

# ledger -> (kind, 采样点, 力的施加, 耗气的施加)
LEDGERS: dict[str, tuple[str, str, str, str]] = {
    "asrun":    ("legacy",   "beg", "full", "frac"),
    "legacy1":  ("legacy",   "beg", "full", "full"),
    "legacy2":  ("legacy",   "beg", "frac", "full"),
    "legacy3":  ("legacy",   "beg", "frac", "frac"),
    "analytic": ("analytic", "mid", "frac", "frac"),
}
#: 需要把控制律在**步中点**再求一次值的 ledger（其余只用步首值）
NEEDS_MID = {k for k, v in LEDGERS.items() if v[1] == "mid"}


class PFM:
    r"""多通道脉冲调制器。**一个通道一条预算，互不干扰。**

    ## 用法

    ```python
    pfm = PFM(t_min=0.012, ledger="analytic")
    on = pfm.step(t, dt, {"lift": 0.42, "side": 0.11})   # ch -> 占空比需求
    ff, mf = pfm.scales(on["lift"])                      # 力/耗气各自的系数
    ```

    `step()` 返回 `{通道: on_frac}`，`on_frac ∈ [0,1]` 是本步的**重叠比例**。
    力与耗气的系数由 `scales()` 按 ledger 决定 —— **两者分开是为了能复现旧账**
    （旧实现里力按分数步、耗气按整步，那一档正是 ②）。
    """

    def __init__(self, t_min: float = 0.012, ledger: str = "analytic"):
        if ledger not in LEDGERS:
            raise ValueError(f"未知 ledger={ledger!r}，可选 {sorted(LEDGERS)}")
        self.t_min = float(t_min)
        self.ledger = ledger
        self.kind, self.sample, self.force_mode, self.mass_mode = LEDGERS[ledger]

        # ---- legacy 状态：预算 + "正在飞的脉冲"（每通道至多一个）----
        self.pwm_acc: dict[str, float] = {}
        self.t_on: dict[str, float] = {}

        # ---- analytic 状态：预算 + **脉冲队列**（绝对时刻）----
        self.budget: dict[str, float] = {}
        self.n_fired: dict[str, int] = {}
        self.queue: dict[str, list[list[float]]] = {}
        self.last_end: dict[str, float] = {}

        # ---- 统计（用于账目对账）----
        self.demand: dict[str, float] = {}    # ∫d dt
        self.on_time: dict[str, float] = {}   # ∫on dt
        self.n_pulse = 0

    # ------------------------------------------------------------------
    def scales(self, on: float) -> tuple[float, float]:
        r"""本步的（力系数, 耗气系数）。`on=0` 时两者都是 0。"""
        if on <= 0.0:
            return 0.0, 0.0
        return (on if self.force_mode == "frac" else 1.0,
                on if self.mass_mode == "frac" else 1.0)

    # ------------------------------------------------------------------
    def step(self, t: float, dt: float,
             duty: dict[str, float]) -> dict[str, float]:
        r"""前进一拍，返回每通道的**重叠比例**。

        `duty` 是**本步采用的**占空比需求：
        `analytic` 传**中点值**，`legacy` 传**步首值**（用 `NEEDS_MID` 判断）。
        """
        if self.kind == "legacy":
            return self._step_legacy(t, dt, duty)
        return self._step_analytic(t, dt, duty)

    # ------------------------------------------------------------------
    def _step_legacy(self, t: float, dt: float,
                     duty: dict[str, float]) -> dict[str, float]:
        r"""**逐字复刻旧实现**（含它的一个隐性缺陷，见下）。

        ★ 旧代码只遍历 `duty>0` 的通道 ⇒ 若某通道的 `d` 掉到 0 而脉冲还没飞完，
        它就**永远不会被删除**（`t_on` 只在 `ch in ch_duty` 的循环里删）。
        下一次 `d>0` 时该通道**丢掉一步**。这是旧账的一部分，故**保留**，
        否则复现不出旧表里的 0.566 / 8.281 / 7.844。
        """
        out: dict[str, float] = {}
        for ch, d in duty.items():
            if d <= 0.0:
                continue
            self.pwm_acc[ch] = self.pwm_acc.get(ch, 0.0) + d * dt
            self.demand[ch] = self.demand.get(ch, 0.0) + d * dt
            if ch not in self.t_on and self.pwm_acc[ch] >= self.t_min - 1e-12:
                self.pwm_acc[ch] -= self.t_min
                self.t_on[ch] = t                    # ★ 落在网格上
                self.n_pulse += 1
            on = 0.0
            if ch in self.t_on:
                t0p = self.t_on[ch]
                ov = min(t + dt, t0p + self.t_min) - max(t, t0p)
                on = max(0.0, min(1.0, ov / dt))
                if t + dt >= t0p + self.t_min - 1e-12:
                    del self.t_on[ch]
            out[ch] = on
            self.on_time[ch] = self.on_time.get(ch, 0.0) + on * dt
        return out

    # ------------------------------------------------------------------
    def _step_analytic(self, t: float, dt: float,
                       duty: dict[str, float]) -> dict[str, float]:
        r"""**与步长无关**的实现（本版）。

        ## 三个要点

        1. 预算用**中点**值累积（调用方保证传进来的是中点 $d$）；
        2. 触发时刻 $t+\tau$ 由**预算线性插值**解出：
           $\tau=\big((k+1)t_{\min}-D(t)\big)/d$，**不是**"这一步的开头"；
        3. 脉冲进**队列**、带绝对起止时刻；每步只算重叠比例 ⇒
           一个脉冲可以横跨十几步（$dt$ 很小时）或一步里塞进两个（$dt$ 很大时），
           **两种情形给出同一条脉冲序列**。

        ★ 与 legacy 的一个有意差别：这里遍历
        "**有需求或有在飞脉冲**"的通道并集 ⇒ 脉冲一旦点火就会**飞完**，
        不会因为 $d$ 中途掉到 0 而丢掉。
        """
        chs = set(duty) | {c for c, q in self.queue.items() if q}
        out: dict[str, float] = {}
        for ch in chs:
            d = duty.get(ch, 0.0)
            d0 = self.budget.get(ch, 0.0)       # 本步开始时的预算
            d1 = d0 + d * dt
            self.budget[ch] = d1
            self.demand[ch] = self.demand.get(ch, 0.0) + d * dt

            n = self.n_fired.get(ch, 0)
            while d1 >= self.t_min * (n + 1) - 1e-15:
                target = self.t_min * (n + 1)
                # 预算在**本步内**跨过 target 的时刻（d 在步内按常数近似）
                tau = (target - d0) / d if d > 1e-12 else 0.0
                s = t + min(max(tau, 0.0), dt)
                # 不许与上一发重叠
                s = max(s, self.last_end.get(ch, -1e18))
                self.queue.setdefault(ch, []).append([s, s + self.t_min])
                self.last_end[ch] = s + self.t_min
                n += 1
                self.n_fired[ch] = n
                self.n_pulse += 1

            ov = 0.0
            for p0, p1 in self.queue.get(ch, ()):
                ov += max(0.0, min(t + dt, p1) - max(t, p0))
            on = min(1.0, ov / dt) if dt > 0 else 0.0
            out[ch] = on
            self.on_time[ch] = self.on_time.get(ch, 0.0) + on * dt

            # 剪掉已经飞完的脉冲（留一点浮点余量）
            self.queue[ch] = [p for p in self.queue.get(ch, ())
                              if p[1] > t + dt + 1e-15]
        return out

    # ------------------------------------------------------------------
    def report(self) -> dict[str, dict[str, float]]:
        r"""账目汇总：每通道 `∫d dt`、`∫on dt`、脉冲数。"""
        return {ch: {"demand": self.demand.get(ch, 0.0),
                     "on_time": self.on_time.get(ch, 0.0),
                     "n_pulse": float(self.n_fired.get(ch, 0))}
                for ch in self.demand}
