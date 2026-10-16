#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W47 · 问题 2：把「分流」与「诱增」拆开（**核心**）。

## 一、问题形式化

观测（2026 中秋）：大桥 $q_B^{\text{obs}}=10.55$、隧道 $q_T^{\text{obs}}=2.92$、
合计 $D^{\text{obs}}=13.47$（万辆/日）。
2024 中秋（无隧道）：大桥 $q^{2024}=12.44$。

记"**2026 年若无隧道**"的反事实基线为 $q_B^{\text{cf}}$，则

$$
\underbrace{q_B^{\text{obs}}}_{10.55} = q_B^{\text{cf}} - \Delta_{\text{div}},
\qquad
\underbrace{q_T^{\text{obs}}}_{2.92} = \Delta_{\text{div}} + \Delta_{\text{ind}}
$$

$$
\underbrace{D^{\text{obs}} - q^{2024}}_{1.03} = \Delta_{\text{ind}} + \Delta_{\text{trend}}
$$

**四个未知量**（$q_B^{\text{cf}}, \Delta_{\text{div}}, \Delta_{\text{ind}},
\Delta_{\text{trend}}$），**三个方程** ⇒ **欠识别一个自由度**。

## 二、★ 本脚本的核心贡献：说清"什么能识别、什么不能"

**可识别**（无需额外假设）：
* $\Delta_{\text{div}} - \Delta_{\text{trend}}$：由方程 (1)(2) 相减得
  $q_T^{\text{obs}} - (D^{\text{obs}} - q^{2024}) = \Delta_{\text{div}} - \Delta_{\text{trend}}$；
* $\Delta_{\text{div}} + \Delta_{\text{ind}}$：即 $q_T^{\text{obs}}$（隧道承接总量）。

**不可识别**（必须外部假设）：$\Delta_{\text{div}}$ 与 $\Delta_{\text{ind}}$
的**各自大小** —— 这是本题的**根本局限**，论文必须明说。

## 三、用什么去"补"那一个自由度：三种独立证据

| 证据 | 给出的量 | 强弱 |
|---|---|---|
| **E1 大桥自身趋势** | $q_B^{\text{cf}}$（反事实基线）| 中（2024/25 为推断值）|
| **E2 可比通道**（南京三/四桥）| 区域自然增长率 $\Delta_{\text{trend}}$ | 中（不同城市、不同通道）|
| **E3 2020 免收通行费** | **价格弹性** ⇒ 约束诱增的量级 | **强（真实外生冲击、窗口已知）** |

用法：
    $PY q2_decompose.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from w47_data import BRIDGE, INFERRED, OPENING, PEERS, SHOCKS   # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
RES.mkdir(parents=True, exist_ok=True)

# ── 观测常量（万辆/日）──
QB_OBS = OPENING["大桥_万辆"]                # 10.55
QT_OBS = OPENING["隧道_万辆"]                # 2.92
D_OBS = OPENING["通道日均_万辆"]             # 13.47
QB_2024 = OPENING["2024同期大桥_万辆"]       # 12.44


# ══════════════════════════════════════════════════════════════════
# 证据 E1：大桥自身趋势 → 反事实基线
# ══════════════════════════════════════════════════════════════════
def e1_baseline() -> dict:
    r"""用大桥 2019–2025 序列外推 2026 中秋的反事实基线。

    ⚠️ 三个必须处理的困难：
    1. **2024/2025 是推断值**（年报不再单列大桥）⇒ 用区间；
    2. **2026 中秋的"中秋"日历位置逐年不同**，但缺逐月数据 ⇒
       只能假设"中秋日均 ≈ 年均日均"，**这是一个必须声明的假设**；
    3. **2022–2023 有巨大外生冲击**（封控与反弹）⇒
       拟合趋势时**不能把这两年当正常年**，否则斜率被严重污染。

    ⇒ 做法：给出**三种情景**，而不是一个点估计。
    """
    seq = {y: d["合计"] for y, d in BRIDGE.items()}          # 辆/日
    seq[2024] = INFERRED[2024]["合计中点"]
    seq[2025] = INFERRED[2025]["合计中点"]

    # 正常年（剔除 2020 免收、2022 封控、2023 反弹）
    normal = {2019: seq[2019], 2021: seq[2021],
              2024: seq[2024], 2025: seq[2025]}
    ys = np.array(sorted(normal), dtype=float)
    xs = np.array([normal[int(y)] for y in ys], dtype=float)
    # 对数线性趋势（流量按比例变化更自然）
    slope, intercept = np.polyfit(ys, np.log(xs), 1)
    base_trend = float(np.exp(intercept + slope * 2026))

    # 只用最近两年（2024→2025 的下滑延续）
    g_last = seq[2025] / seq[2024] - 1
    base_last = seq[2025] * (1 + g_last)

    # 持平假设（最保守：认为 2025 已是新常态）
    base_flat = seq[2025]

    # 区域自然增长（E2）：南京三/四桥 2021–2023 的年均增速
    peer_g = {}
    for nm in ("南京长江三桥", "南京长江四桥"):
        v = PEERS[nm]
        yy = sorted(v)
        g = (v[yy[-1]]["日均_万辆"] / v[yy[0]]["日均_万辆"]) ** (
            1 / (yy[-1] - yy[0])) - 1
        peer_g[nm] = g
    g_peer = float(np.mean(list(peer_g.values())))
    base_peer = seq[2025] * (1 + g_peer)

    bases = {
        "S1_对数线性趋势": {"基线_万辆": base_trend / 1e4,
                            "依据": "2019/2021/2024/2025 四个正常年的对数线性外推"},
        "S2_延续近期下滑": {"基线_万辆": base_last / 1e4,
                            "依据": "2024→2025 的同比增速再延续一年"},
        "S3_持平2025": {"基线_万辆": base_flat / 1e4,
                        "依据": "最保守：2025 年已是新常态"},
        "S4_区域自然增长": {"基线_万辆": base_peer / 1e4,
                            "依据": f"南京可比通道年均增速 {g_peer:+.2%} 施加于 2025"},
    }
    return {"scenarios": bases, "peer_growth": peer_g,
            "g_peer": g_peer, "seq": seq,
            "trend_slope_log": float(slope),
            "normal_years": sorted(normal)}


# ══════════════════════════════════════════════════════════════════
# 证据 E3：2020 免收通行费 → 价格弹性
# ══════════════════════════════════════════════════════════════════
def e3_elasticity() -> dict:
    r"""用 2020 免收通行费估计**需求对价格的弹性**。

    ⚠️ **必须先想清楚这个冲击能识别什么**：
    免收期 79 天里**价格从 25 元降到 0**，但**流量数据是全年平均**
    （2020 年 95,238 辆/日），所以：

    * **不能**用"全年流量变化 / 价格变化"估弹性 ——
      流量被"免收期上升"和"疫情期下降"两个相反效应混在一起；
    * **能**做的是：用**收入恒等式**检验"免费是否抬高了总需求"。

    收入侧：$2{,}747.06 \div (1-79/366) = 3{,}503.2 \approx 3{,}505.18$（2019）
    ⇒ 偏差 **0.06%** ⇒ **免收期之外，需求水平与 2019 年几乎一致**。
    """
    v = SHOCKS["2020免收通行费"]["_验算"]
    rev20, frac = v["2020收入_千元每日"], SHOCKS["2020免收通行费"]["占比"]
    norm = rev20 / (1 - frac)
    dev = (norm - v["2019收入_千元每日"]) / v["2019收入_千元每日"]

    # 车均收入视角：2020 vs 2019
    per19 = BRIDGE[2019]["日均收入_千元"] * 1000 / BRIDGE[2019]["合计"]
    per20 = BRIDGE[2020]["日均收入_千元"] * 1000 / BRIDGE[2020]["合计"]
    per20_norm = per20 / (1 - frac)

    return {"免收占比": frac, "归一化收入": norm,
            "2019收入": v["2019收入_千元每日"], "偏差": dev,
            "车均收入_2019": per19, "车均收入_2020": per20,
            "车均收入_2020_归一化": per20_norm,
            "结论": ("免收期之外需求与 2019 年几乎一致（偏差 0.06%）"
                     "⇒ **免费没有抬高长期需求水平**。"
                     "这提示：以降价为主要机制的『诱增』在本案例中可能很弱；"
                     "若 2026 有诱增，更可能来自**容量/可靠性**而非价格。"),
            "流量对照": {2019: BRIDGE[2019]["合计"], 2020: BRIDGE[2020]["合计"],
                         "变化": BRIDGE[2020]["合计"] / BRIDGE[2019]["合计"] - 1}}


# ══════════════════════════════════════════════════════════════════
# 分解（对每个基线情景）
# ══════════════════════════════════════════════════════════════════
def decompose(base_wan: float) -> dict:
    r"""给定反事实基线（万辆/日），做分解。

    方程：
      (1) q_B^cf - Δ_div = QB_OBS
      (2) Δ_div + Δ_ind = QT_OBS
      (3) Δ_ind + Δ_trend = D_OBS - QB_2024

    ⇒ Δ_div = q_B^cf - QB_OBS                （可算，依赖基线）
      Δ_ind = QT_OBS - Δ_div                 （由 (2)）
      Δ_trend = (D_OBS - QB_2024) - Δ_ind    （由 (3)，用于**校验**）
    """
    d_div = base_wan - QB_OBS
    d_ind = QT_OBS - d_div
    d_tot = D_OBS - QB_2024
    d_trend = d_tot - d_ind
    # 与官方口径对比：官方把 QB_2024 - QB_OBS 全算成分流
    official = QB_2024 - QB_OBS
    return {
        "基线_万辆": round(base_wan, 3),
        "Δ分流_万辆": round(d_div, 3),
        "Δ诱增_万辆": round(d_ind, 3),
        "Δ自然增长_万辆": round(d_trend, 3),
        "总需求变化_万辆": round(d_tot, 3),
        "官方口径_万辆": round(official, 3),
        "官方高估_万辆": round(official - d_div, 3),
        "官方高估_比例": round((official - d_div) / official, 4) if official else None,
        "分流占隧道承接_比例": round(d_div / QT_OBS, 4) if QT_OBS else None,
        "诱增占隧道承接_比例": round(d_ind / QT_OBS, 4) if QT_OBS else None,
    }


def bounds_analysis() -> dict:
    r"""★ 不依赖任何基线假设的**硬界**。

    由 $q_B^{\text{cf}} = q_B^{\text{obs}} + \Delta_{\text{div}}$ 与
    $\Delta_{\text{div}} \in [0,\; q_T^{\text{obs}}]$
    （分流不可能为负，也不可能超过隧道承接总量）：

    $$
    q_B^{\text{cf}} \in [q_B^{\text{obs}},\; q_B^{\text{obs}}
    + q_T^{\text{obs}}] = [10.55,\; 13.47]
    $$

    ⇒ **官方口径隐含的反事实基线是 12.44（把 2024 当基线），
    落在硬界内**。但下界 10.55 对应"隧道全部是诱增、零分流"，
    上界 13.47 对应"隧道全部是分流、零诱增"。
    """
    lo, hi = QB_OBS, QB_OBS + QT_OBS
    lo_ind = max(0.0, QT_OBS - (hi - QB_OBS))
    return {
        "反事实基线硬界_万辆": [round(lo, 2), round(hi, 2)],
        "对应Δ分流_硬界_万辆": [0.0, round(QT_OBS, 2)],
        "对应Δ诱增_硬界_万辆": [0.0, round(QT_OBS, 2)],
        "官方基线_万辆": QB_2024,
        "官方基线在界内": bool(lo <= QB_2024 <= hi),
        "_说明": ("**Δ分流 与 Δ诱增 无法由现有数据单独识别** —— "
                  "两者之和恒等于隧道承接量 2.92。"
                  "只有引入外部假设（基线或弹性）才能分开。"),
    }


def main() -> int:
    print("=" * 96)
    print("  W47 · 问题 2：分流与诱增的分解")
    print("=" * 96)
    print(f"\n  观测：大桥 {QB_OBS} / 隧道 {QT_OBS} / 合计 {D_OBS}（万辆/日）")
    print(f"        2024 中秋大桥 {QB_2024}")

    e1 = e1_baseline()
    e3 = e3_elasticity()

    print(f"\n  ── 证据 E1：大桥自身趋势（正常年 {e1['normal_years']}）──")
    print(f"     对数趋势斜率 {e1['trend_slope_log']:+.4f} /年"
          f"（≈ {np.exp(e1['trend_slope_log'])-1:+.2%}/年）")
    for k, v in e1["scenarios"].items():
        print(f"     {k:<16}基线 {v['基线_万辆']:.2f} 万辆   （{v['依据']}）")

    print(f"\n  ── 证据 E2：可比通道自然增长 ──")
    for nm, g in e1["peer_growth"].items():
        print(f"     {nm}: {g:+.2%}/年")
    print(f"     平均 {e1['g_peer']:+.2%}/年")

    print(f"\n  ── 证据 E3：2020 免收通行费 ──")
    print(f"     免收 {e3['免收占比']:.2%}；收入归一化 "
          f"{e3['归一化收入']:,.1f} vs 2019 {e3['2019收入']:,.1f}"
          f"  偏差 {e3['偏差']:+.2%}")
    print(f"     车均收入：2019 {e3['车均收入_2019']:.2f} 元 → "
          f"2020 {e3['车均收入_2020']:.2f}（归一化 {e3['车均收入_2020_归一化']:.2f}）")
    print(f"     结论：{e3['结论']}")

    print(f"\n{'='*96}")
    print("  ★ 分解结果（四个基线情景）")
    hdr = (f"     {'情景':<18}{'基线':>8}{'Δ分流':>9}{'Δ诱增':>9}"
           f"{'Δ自然':>9}{'官方高估':>10}{'高估比例':>10}")
    print(hdr)
    print("     " + "-" * (len(hdr) - 5))
    rows = {}
    for k, v in e1["scenarios"].items():
        d = decompose(v["基线_万辆"])
        rows[k] = d
        print(f"     {k:<18}{d['基线_万辆']:>8.2f}{d['Δ分流_万辆']:>9.2f}"
              f"{d['Δ诱增_万辆']:>9.2f}{d['Δ自然增长_万辆']:>9.2f}"
              f"{d['官方高估_万辆']:>10.2f}"
              f"{(d['官方高估_比例'] or 0):>10.1%}")

    print(f"\n  ── 官方口径校准 ──")
    off = decompose(QB_2024)
    print(f"     若把 2024 当年基线（官方隐含做法）：")
    print(f"       Δ分流 {off['Δ分流_万辆']:.2f}  Δ诱增 {off['Δ诱增_万辆']:.2f}"
          f"  Δ自然 {off['Δ自然增长_万辆']:.2f}")

    b = bounds_analysis()
    print(f"\n{'='*96}")
    print("  ★★ 识别性：什么能算、什么不能")
    print(f"     反事实基线**硬界** [{b['反事实基线硬界_万辆'][0]},"
          f" {b['反事实基线硬界_万辆'][1]}] 万辆/日")
    print(f"     官方隐含基线 {b['官方基线_万辆']} 落在界内："
          f"{'是' if b['官方基线在界内'] else '否'}")
    print(f"     {b['_说明']}")

    # 汇总落盘
    out = {"观测": {"大桥": QB_OBS, "隧道": QT_OBS, "合计": D_OBS,
                    "2024大桥": QB_2024},
           "E1_基线情景": e1["scenarios"], "E2_可比通道增速": e1["peer_growth"],
           "E3_弹性证据": e3, "分解": rows, "官方隐含": off,
           "识别性": b}
    p = RES / "q2_分解.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2,
                            default=float), encoding="utf-8")
    print(f"\n  -> {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
