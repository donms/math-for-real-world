#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""Q1：受益模型、理论基准，与五地规则比较（**含用宁波案例标定**）。

## 关键设计：为什么受益函数不能是线性的

宁波的协商过程给了一个**天然的标定机会**：

| 轮次 | 方案 | 结果 |
|---|---|---|
| 第 1 轮 | 6→2 层按 **5:4:3:2:1** | 提出 |
| 第 2 轮 | 按"**每层减少爬楼梯格数**"测算（8/14/20/26/32）| ❌ **被业主否决** |
| 第 3 轮 | 协商调整，**4 楼最终 19%** | ✅ 达成 |

**被否的理由原文**："反映不出建电梯的紧迫感，**2 楼、3 楼居民的获得感不高**，
却要承担 8% 和 14% 的费用。"

⇒ **"客观受益"（爬梯级数）不等于"获得感"。**
因此本模型采用**凸的受益函数**：

$$
b_i \;\propto\; (i-1)^{\gamma},\qquad \gamma \ge 1
$$

* $\gamma = 1$ ⇒ 线性（等价于"按楼层高度"）
* $\gamma > 1$ ⇒ **凸**，高层相对更"值"，低层相对更"不值"
* $\gamma < 1$ ⇒ 凹

**用宁波的三轮数据标定 $\gamma$**，再看五地规则落在哪个 $\gamma$ 附近。

**这与"爬梯级数"的关系**：爬梯级数近似**线性**于楼层（γ≈1），
而业主想要的是**更陡**的分配 ⇒ 实证上 $\gamma > 1$。

## 三个理论基准

1. **线性受益** $b_i\propto (i-1)$
2. **凸受益（获得感）** $b_i\propto (i-1)^{\gamma}$
3. **Shapley 值**（合作博弈解，见下）

### Shapley 值怎么算

把"加装电梯"视为**全体业主的合作**。定义特征函数：
* 不含顶层的联盟：电梯只服务到该联盟最高层 ⇒ 收益按该联盟最高层计
* 含全部楼层则得全额收益

对楼层集合 $N=\{1,\dots,H\}$，令联盟 $S$ 的价值
$v(S)=\max_{i\in S}(i-1)$（以最高层代表电梯带来的服务上限），$v(\varnothing)=0$。
则 Shapley 值为

$$
\phi_i=\sum_{S\subseteq N\setminus\{i\}}
\frac{|S|!\,(H-|S|-1)!}{H!}\bigl[v(S\cup\{i\})-v(S)\bigr]
$$

再归一化为分摊比例。$H\le 7$ 时可直接枚举。

用法：
    $PY q2_benefit_model.py
"""
from __future__ import annotations

import contextlib
import csv
import io
import itertools
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
EP = ROOT / "episodes" / "2026-W43"
CLEAN = EP / "data" / "clean"
RES = EP / "results"

H = 6  # 六层楼（基准楼型，一层 1 户）

# 五地规则归一化数据（由 q1_build_tables.py 生成）
RULES_FILE = CLEAN / "city_rules.json"


# ---------------- 受益函数 ----------------
def benefit(H: int, gamma: float, floor2_base: bool = True) -> dict[int, float]:
    r"""$b_i \propto (i-1)^{\gamma}$，一层恒为 0，归一化。

    floor2_base=False 时把二层也记为 0（武汉/宁波口径的"三层起分摊"）。
    """
    raw = {i: float(i - 1) ** gamma for i in range(1, H + 1)}
    raw[1] = 0.0
    if not floor2_base:
        raw[2] = 0.0
    s = sum(raw.values())
    return {i: (v / s if s else 0.0) for i, v in raw.items()}


# ---------------- Shapley ----------------
def shapley(H: int) -> dict[int, float]:
    r"""特征函数 $v(S)=\max_{i\in S}(i-1)$，$v(\varnothing)=0$。"""
    N = list(range(1, H + 1))

    def v(S: frozenset) -> float:
        return max((i - 1) for i in S) if S else 0.0

    phi = {i: 0.0 for i in N}
    for i in N:
        others = [j for j in N if j != i]
        for k in range(len(others) + 1):
            for S in itertools.combinations(others, k):
                Sset = frozenset(S)
                w = (math.factorial(len(S)) * math.factorial(H - len(S) - 1)
                     / math.factorial(H))
                phi[i] += w * (v(Sset | {i}) - v(Sset))
    s = sum(phi.values())
    return {i: (x / s if s else 0.0) for i, x in phi.items()}


def equal(H: int) -> dict[int, float]:
    return {i: 1.0 / H for i in range(1, H + 1)}


def l1(a: dict[int, float], b: dict[int, float]) -> float:
    return sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in set(a) | set(b))


def corr(a: dict[int, float], b: dict[int, float]) -> float:
    ks = sorted(set(a) & set(b))
    n = len(ks)
    ax = [a[k] for k in ks]
    bx = [b[k] for k in ks]
    ma, mb = sum(ax) / n, sum(bx) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ax, bx))
    da = sum((x - ma) ** 2 for x in ax) ** 0.5
    db = sum((y - mb) ** 2 for y in bx) ** 0.5
    return num / (da * db) if da and db else 0.0


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    _data = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    rules = _data["归一化_六层"]
    RULES_RAW = {k: {int(i): float(v) for i, v in d.items()}
                 for k, d in _data["原始系数"].items()}
    norm_rules = {k: {int(i): v for i, v in d.items()} for k, d in rules.items()}

    def normalize_full(d: dict[int, float], Hx: int) -> dict[int, float]:
        sub = {i: d.get(i, 0.0) for i in range(1, Hx + 1)}
        s = sum(sub.values())
        return {i: (v / s if s else 0.0) for i, v in sub.items()}

    out: list[str] = []

    def P(s: str = "") -> None:
        out.append(s)
        print(s, flush=True)

    P("=" * 104)
    P("  Q1  受益模型与五地规则比较（6 层楼，每层 1 户）")
    P("=" * 104)

    # ---------- 1. γ 的标定：用宁波第 3 轮的"4 楼 19%" ----------
    P("\n【1】用宁波协商数据标定 γ")
    P("    目标：第 3 轮达成时 4 楼 = 19%")
    best_g, best_err = None, float("inf")
    grid = [1.0 + 0.05 * k for k in range(0, 41)]     # 1.00 ~ 3.00
    for g in grid:
        f4 = benefit(H, g)[4] * 100
        err = abs(f4 - 19.0)
        if err < best_err:
            best_err, best_g = err, g
    P(f"    ⇒ 标定结果 γ* = {best_g:.2f}（4 楼 = {benefit(H,best_g)[4]*100:.2f}%，"
      f"与 19% 差 {best_err:.2f} pp）")
    P(f"    参考：γ=1（线性）时 4 楼 = {benefit(H,1.0)[4]*100:.2f}%")

    # ---------- 2. 各模型曲线 ----------
    P(f"\n{'='*104}")
    P("  【2】各受益/分摊模型的曲线（归一化 %）")
    P("=" * 104)
    models: dict[str, dict[int, float]] = {}
    models["线性受益 γ=1"] = benefit(H, 1.0)
    models["凸受益 γ=1.5"] = benefit(H, 1.5)
    models[f"凸受益 γ*={best_g:.2f}(宁波标定)"] = benefit(H, best_g)
    models["Shapley"] = shapley(H)
    models["等额分摊"] = equal(H)
    for g in (2.0, 2.5, 3.0):
        models[f"凸受益 γ={g}"] = benefit(H, g)

    P(f"  {'模型':<28}" + "".join(f"{i}层".rjust(9) for i in range(1, H + 1)))
    P("  " + "-" * 82)
    for name, d in models.items():
        P(f"  {name:<28}" + "".join(f"{d[i]*100:>8.2f}%" for i in range(1, H + 1)))

    P(f"\n  {'五地规则':<28}" + "".join(f"{i}层".rjust(9) for i in range(1, H + 1)))
    P("  " + "-" * 82)
    for name, d in norm_rules.items():
        P(f"  {name:<28}" + "".join(f"{d.get(i,0)*100:>8.2f}%"
                                    for i in range(1, H + 1)))

    # ---------- 3. 谁最接近哪个基准 ----------
    P(f"\n{'='*104}")
    P("  【3】五地规则 vs 三个基准（L1 距离，越小越近）")
    P("     ⚠️ 北京四/五层规则按其**自身层数**归一化比较，不做 6 层补零")
    P("=" * 104)
    bases6 = {
        "线性受益 γ=1": benefit(6, 1.0),
        f"凸受益 γ*={best_g:.2f}": benefit(6, best_g),
        "Shapley": shapley(6),
        "等额": equal(6),
    }
    hdr = f"  {'地区':<26}" + "".join(f"{k:>16}" for k in bases6) + f"{'最近':>10}"
    P(hdr)
    P("  " + "-" * (26 + 16 * len(bases6) + 10))
    nearest: dict[str, str] = {}
    for name, d in norm_rules.items():
        if "五层" in name or "四层" in name:
            continue                      # 层数不同，不参与 6 层比较
        vals = {k: l1(d, b) for k, b in bases6.items()}
        win = min(vals, key=lambda k: vals[k])
        nearest[name] = win
        P(f"  {name:<26}" + "".join(f"{vals[k]:>16.4f}" for k in bases6)
          + f"{win:>10}")

    # 四/五层单独比
    P(f"\n  【3b】北京四/五层规则按其自身层数比较")
    for Hx, key in ((5, "北京(五层·区间中位)"), (4, "北京(四层·区间中位)")):
        if key not in norm_rules:
            continue
        d = normalize_full(RULES_RAW[key], Hx)
        bs = {"线性受益 γ=1": benefit(Hx, 1.0),
              f"凸受益 γ*={best_g:.2f}": benefit(Hx, best_g),
              "Shapley": shapley(Hx), "等额": equal(Hx)}
        vals = {k: l1(d, b) for k, b in bs.items()}
        win = min(vals, key=lambda k: vals[k])
        P(f"    {key:<24} n={Hx}  " +
          "  ".join(f"{k}={vals[k]:.4f}" for k in bs) + f"   ⇒ 最近 {win}")

    # ---------- 4. 宁波三轮的检验 ----------
    P(f"\n{'='*104}")
    P("  【4】★ 宁波三轮方案对照（本模型的核心验证）")
    P("=" * 104)
    nb = {k: v for k, v in norm_rules.items() if k.startswith("宁波")}
    P(f"  {'方案':<28}" + "".join(f"{i}层".rjust(9) for i in range(1, H + 1))
      + f"{'Σ|偏差|':>10}{'γ=1偏离':>11}")
    P("  " + "-" * 94)
    g1 = benefit(H, 1.0)
    for name, d in nb.items():
        dev = l1(d, g1)
        P(f"  {name:<28}" + "".join(f"{d.get(i,0)*100:>8.2f}%"
                                    for i in range(1, H + 1))
          + f"{dev:>10.4f}{dev*100:>10.2f}pp")

    P(f"\n  判读：")
    P(f"    · 第 1 轮（5:4:3:2:1）与『线性受益 γ=1』几乎重合")
    P(f"      ⇒ 第一轮实质上是**按楼层高度线性分摊**")
    P(f"    · 第 2 轮（爬梯级数）比第 1 轮**更平缓**（2 层 8% vs 6.67%，"
      f"6 层 32% vs 33.33%）")
    P(f"      ⇒ 它把负担**从高层移向低层**，与业主『觉得 2、3 层获得感低』的"
      f"抱怨方向一致")
    P(f"    · 第 3 轮的 4 楼 19% 对应 γ* = {best_g:.2f} ⇒ **比线性更陡**")
    P(f"  ⇒ **三轮的方向是『越来越陡』**：从线性走向凸，")
    P(f"     即**低层少担、高层多担**。这与『提高获得感』的诉求一致。")

    # ---------- 5. 五地规则的陡峭度 ----------
    P(f"\n{'='*104}")
    P("  【5】五地规则的陡峭度与等效 γ（**各自按其真实层数**）")
    P("=" * 104)
    HEIGHT_OF = {"北京(六层·区间中位)": 6, "北京(五层·区间中位)": 5,
                 "北京(四层·区间中位)": 4, "南京(系数+0.3)": 7,
                 "广州(系数+0.1)": 7, "武汉(个案+5%)": 7,
                 "宁波(第1轮 5:4:3:2:1)": 6, "宁波(第2轮 爬梯级数)": 6}
    # 统一按 6 层口径展示顶层占比（便于横向读），但等效 γ 用真实层数拟合
    P(f"  {'地区':<26}{'真实层':>7}{'顶层占比(6层口径)':>17}"
      f"{'等效γ':>10}{'L1':>10}")
    P("  " + "-" * 72)
    stat = []
    for name, d in norm_rules.items():
        Hx = HEIGHT_OF.get(name, 6)
        dr = normalize_full(RULES_RAW[name], Hx)
        bg, be = None, float("inf")
        for g in grid:
            e = l1(dr, benefit(Hx, g, floor2_base=(dr.get(2, 0) > 0)))
            if e < be:
                be, bg = e, g
        stat.append({"地区": name, "真实层数": Hx,
                     "顶层占比6层口径": round(d.get(6, 0), 4),
                     "等效γ": round(bg, 2), "L1": round(be, 4)})
        P(f"  {name:<26}{Hx:>7}{d.get(6,0)*100:>16.2f}%{bg:>10.2f}{be:>10.4f}")

    P(f"\n  【相关性与偏离】（各自真实层数）")
    P(f"  {'地区':<26}{'vs γ=1':>12}{'vs γ*':>12}{'vs Shapley':>14}")
    P("  " + "-" * 66)
    for name, d in norm_rules.items():
        Hx = HEIGHT_OF.get(name, 6)
        dr = normalize_full(RULES_RAW[name], Hx)
        c1 = corr(dr, benefit(Hx, 1.0))
        cg = corr(dr, benefit(Hx, best_g))
        cs = corr(dr, shapley(Hx))
        P(f"  {name:<26}{c1:>12.4f}{cg:>12.4f}{cs:>14.4f}")

    # ---------- 落盘 ----------
    (RES / "q2_benefit_model.txt").write_text("\n".join(out), encoding="utf-8")
    (RES / "q2_benefit_model.json").write_text(json.dumps({
        "γ标定": {"γ*": best_g, "4楼%": round(benefit(H, best_g)[4]*100, 3),
                 "目标": 19.0, "误差pp": round(best_err, 3)},
        "模型曲线": {k: {str(i): round(v, 6) for i, v in d.items()}
                  for k, d in models.items()},
        "五地规则": {k: {str(i): round(v, 6) for i, v in d.items()}
                  for k, d in norm_rules.items()},
        "最近基准": nearest,
        "陡峭度": stat,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ndone  -> {RES / 'q2_benefit_model.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
