#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W48 · 组织光学参数（**实测值，非估计**）。

## 来源

*Nature Communications* 2022, 13:2013, Table 1
「Optical and physical properties of the skull and the brain」
（狨猴 through-skull 宽场光学成像研究）
https://www.nature.com/articles/s41467-022-29864-7/tables/1

## 原始表（**单位 mm^-1**）

| 波长 (nm) | 470 | 530 | 590 | 625 | 730 | 850 |
|---|---|---|---|---|---|---|
| 灰质 mu_a | 0.465 | 0.638 | 0.287 | 0.032 | 0.009 | 0.016 |
| 灰质 mu_s | 11.63 | 10.53 | 9.62 | 9.15 | 8.12 | 7.24 |
| 白质 mu_a | 0.465 | 0.638 | 0.287 | 0.032 | 0.009 | 0.016 |
| 白质 mu_s | 42.85 | 41.94 | 40.70 | 40.28 | 38.61 | 35.31 |

## ★★ 我在这一步踩的坑：**单位链混淆**

表里 `mu_s(470 nm) = 11.63`（**mm^-1**）。换算到 cm^-1 后是 **`116.3`**；
再乘 `(1-g)=0.1` 得到 `mu_s' = 11.63 cm^-1` ——
**数值恰好与原始表的 mm^-1 数字相同**，于是我把两者搞混，
一度以为 `mu_s'` 就是 11.63 mm^-1（错了 10 倍）。

**正确链条**（本题固定用这一条）：

```
论文表值 (mm^-1)
  --x10-->  cm^-1
  --mu_s' = mu_s (1-g)-->  约化散射系数 (cm^-1)
  --mu_tr = mu_a + mu_s'-->  输运系数 (cm^-1)
  --l_tr = 1/mu_tr,  delta = 1/sqrt(3 mu_a mu_tr)-->  长度 (cm)
```

对照 `tissue_optics.py` 与 `q1_transport.py` 的输出必须一致 —— 已核对。

## 由此得到的关键数字（灰质）

| 波长 | mu_a | mu_s' | l_tr | **delta** |
|---|---|---|---|---|
| **470 nm**（近 ChR2 峰）| 4.65 cm^-1 | 11.63 cm^-1 | 0.614 mm | **0.664 mm** |
| 530 nm | 6.38 | 10.53 | 0.591 | 0.556 |
| 590 nm | 2.87 | 9.62 | 0.801 | 0.964 |
| **625 nm**（红光）| 0.32 | 9.15 | 1.056 | **3.317 mm** |
| 730 nm | 0.09 | 8.12 | 1.218 | 6.717 |
| 850 nm | 0.16 | 7.24 | 1.351 | 5.306 |

> [!] **`mu_a` 不单调**：530 nm（6.38）比 470 nm（4.65）**更高**，
> 到 625 nm 才骤降到 0.32 —— 这是可见光段血红素/细胞色素吸收带的真实特征。
> ⇒ **"波长优化"不能想当然地选最长波长**（见问题 4）。

> [!] **白质散射比灰质高约 3.7 倍**（470 nm：428.5 vs 116.3 cm^-1）
> ⇒ 穿透深度只有灰质的 **约 58%**（0.388 vs 0.664 mm）。
> 这解释了问题 4 里"两层组织"对照的必要性。

用法：
    from tissue_optics import derived, table, LAMS
    print(derived("gray", 470)["delta_mm"])
"""
from __future__ import annotations

import numpy as np

# 实测表（**原始单位 mm^-1**，照抄论文，不做任何加工）
_MM = {
    470: {"gray_a": 0.465, "gray_s": 11.63, "white_a": 0.465, "white_s": 42.85},
    530: {"gray_a": 0.638, "gray_s": 10.53, "white_a": 0.638, "white_s": 41.94},
    590: {"gray_a": 0.287, "gray_s": 9.62, "white_a": 0.287, "white_s": 40.70},
    625: {"gray_a": 0.032, "gray_s": 9.15, "white_a": 0.032, "white_s": 40.28},
    730: {"gray_a": 0.009, "gray_s": 8.12, "white_a": 0.009, "white_s": 38.61},
    850: {"gray_a": 0.016, "gray_s": 7.24, "white_a": 0.016, "white_s": 35.31},
}
SOURCE = ("Nat Commun 2022, 13:2013, Table 1 "
          "(doi:10.1038/s41467-022-29864-7)")
MM_TO_CM = 10.0
G = 0.90          # 各向异性因子（论文表未单列，取灰质常用值）
N_TISSUE = 1.36   # 折射率

LAMS = sorted(_MM)


def raw(lam: int) -> dict:
    r"""取最接近的**实测**波长（**不插值**，避免引入未实测的假设）。"""
    near = min(LAMS, key=lambda x: abs(x - lam))
    return {"lam_nm": near, "exact": near == lam, **_MM[near]}


def derived(kind: str = "gray", lam: int = 470, g: float = G) -> dict:
    r"""由实测 $\mu_a,\mu_s$ 推出 $\mu_s',\mu_{\text{tr}},\ell_{\text{tr}},\delta$。

    返回单位：`*_per_cm` 为 cm^-1；`l_tr_cm`/`delta_cm` 为 cm；
    `l_tr_mm`/`delta_mm` 为 mm。
    """
    o = raw(lam)
    mu_a = o[f"{kind}_a"] * MM_TO_CM          # cm^-1
    mu_s = o[f"{kind}_s"] * MM_TO_CM          # cm^-1
    mu_s_p = mu_s * (1.0 - g)                 # cm^-1
    mu_tr = mu_a + mu_s_p                     # cm^-1
    return {"lam_nm": o["lam_nm"], "kind": kind, "g": g,
            "mu_a_per_cm": mu_a, "mu_s_per_cm": mu_s,
            "mu_s_prime_per_cm": mu_s_p, "mu_tr_per_cm": mu_tr,
            "l_tr_cm": 1.0 / mu_tr, "l_tr_mm": 10.0 / mu_tr,
            "D_cm": 1.0 / (3.0 * mu_tr),
            "delta_cm": 1.0 / np.sqrt(3.0 * mu_a * mu_tr),
            "delta_mm": 10.0 / np.sqrt(3.0 * mu_a * mu_tr),
            "attenuation_ratio": mu_s_p / mu_a}


def z_extrap(D_cm: float, n: float = N_TISSUE) -> float:
    r"""外推边界距离 $z_e=2AD$（Groenhuis 近似）。"""
    Reff = -1.44 * n ** -2 + 0.71 * n ** -1 + 0.668 + 0.064 * n
    return 2.0 * ((1 + Reff) / (1 - Reff)) * D_cm


def table(kind: str = "gray") -> str:
    L = [f"{'lambda':>7}{'mu_a':>9}{'mu_s':>10}{'mu_s_p':>9}"
         f"{'l_tr(mm)':>10}{'delta(mm)':>11}{'mu_s_p/mu_a':>13}"]
    for lam in LAMS:
        d = derived(kind, lam)
        L.append(f"{lam:>7}{d['mu_a_per_cm']:>9.2f}{d['mu_s_per_cm']:>10.1f}"
                 f"{d['mu_s_prime_per_cm']:>9.2f}{d['l_tr_mm']:>10.3f}"
                 f"{d['delta_mm']:>11.3f}{d['attenuation_ratio']:>13.1f}")
    return "\n".join(L)


if __name__ == "__main__":
    print("=" * 84)
    print("  W48 组织光学参数（实测）")
    print(f"  来源：{SOURCE}")
    print("=" * 84)
    for kind in ("gray", "white"):
        print(f"\n  -- {kind} matter（mu: cm^-1；长度: mm）--")
        print(table(kind))
    print("\n  单位提示：论文原表是 mm^-1，本模块已 x10 转 cm^-1")
    print("  [!] 注意 mu_a 在 530 nm 处比 470 nm 更高（非单调）")
    d4 = derived("gray", 470)
    d6 = derived("gray", 625)
    print(f"\n  ChR2 激发峰 485 nm ⇒ 最近实测点 470 nm："
          f"delta = {d4['delta_mm']:.3f} mm")
    print(f"  红光 625 nm：delta = {d6['delta_mm']:.3f} mm"
          f"  ⇒ 红/蓝 = {d6['delta_mm']/d4['delta_mm']:.2f}x")
