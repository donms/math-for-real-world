# W52 · 深挖 `Combinatorics.SumProduct`：它是不是"工具类"？

> **用户提问**：「SumProduct 这个模块看名字应该是个工具类的，细看一下呢」
>
> **结论：不是工具库，是"一个问题"的研究项目。**
> **而且这次深挖改写了"最大桥梁"的解释。**

---

## 一、为什么"看起来像工具"

`SumProduct` 有 **259 个模块**，子模块名里全是**通用词**：

```
Alignment.AbelianMalcev01 / Admissible01 / AffineCoefficient01 /
AffineOrbit01 / AlignmentMass01 / AllLevel01 … AllLevel08
```

`AllLevel`、`Admissible`、`Orbit`、`Mass` —— **这些确实像工具库的命名**。
**用户的怀疑是合理的。**

---

## 二、四条证据：它不是工具库

### 证据 1：**259 个模块，但子族只有 1 个**

| | |
|---|---|
| 模块数 | **259** |
| 子族数 | **1**（`Alignment`）|

**=> 所有模块都是"一个构造（Alignment）"的展开**，
而不是"很多个可复用的小工具"。

### 证据 2：**外部引用方只有 1 个族**

| 是谁在引用 `SumProduct` | 模块数 |
|---|---|
| `Geometry.NilpotentCharts` | **263** |
| 其他任何族 | **0** |

**=> 若它是通用工具库，会被多个互不相关的族引用。实际只被一个族用。**

### 证据 3：**名字是"问题名"，不是"工具名"**

`CONTENTS.md` 里查到：

> **[164] Hindman's finite sums and products conjecture.**

**=> "SumProduct" 对应的是「有限和与积」这个著名的组合数论猜想**
（Hindman 猜想），**是一个问题，不是一类工具。**

### 证据 4：★ **源码里的数学内容，"工具"二字完全不符**

`Alignment.AbelianMalcev01` 的 import 段（**原文**）：

```lean
import Mathlib
import OAI.Combinatorics.SumProduct.Alignment.FourierObstruction01
import OAI.Combinatorics.SumProduct.Alignment.PolynomialDephasing01
import OAI.Geometry.NilpotentCharts.Main
```

源码里的实际数学对象：

| 名字 | 是什么 |
|---|---|
| namespace `TorusLeibman` | **Leibman** —— 幂零群动力系统的学者 |
| `polynomialOrbit : (ι -> Polynomial R) -> N -> UnitAddTorus ι` | **多项式在环面上的轨道** |
| `IntegerHyperplane` / `splitCoordinates` | **整数超平面与分裂坐标** |
| `ConstructedWordPlan.GlobalWordPlan` | **构造字计划**（Malcev 基相关）|
| `open AlignmentScales RationalPivotPlan` | 对齐尺度、有理枢轴计划 |

**定理名**（从入度最高的 4 个模块抓取）：

| 模块 | 声明 |
|---|---|
| `Alignment.LeibmanSquare01` | `iterDiff_*` · `polynomial_pair` · `normalized_conjugate_polynomial` · **`reduced_pair_polynomial`** |
| `Alignment.FourierObstruction01` | **`torus_character_obstruction`** · `discrepancy_bound` · `compact_bracket_fourier` |
| `Alignment.CubePolynomials01` | **`partial_taylor`** · `word_update` · `determined_by_initial` |
| `Alignment.IntegerArrays14` | `source_terminal_arithmetic` · `source_pivot_reading` |

> **=> 这是"多项式轨道 + 环面特征障碍 + Malcev 基"的研究工作，
> 不是"和积工具"。**

---

## 三、★ 深挖修正了"最大桥梁"的解释

**依赖方向（实测）**：

| 方向 | 边数 |
|---|---|
| `Combinatorics.SumProduct` -> `Geometry.NilpotentCharts` | **263** |
| `Geometry.NilpotentCharts` -> `Combinatorics.SumProduct` | **0** |

**=> 单向：组合那边用几何那边的工具。**

而 `NilpotentCharts` 的内容（25 个模块）是：

`Adjoint` · `AdjointPolynomials` · `AxesDerivatives` · `CentralAxes` ·
`CentralSubspaces` · `CentralWords` · `CompactGroups` · `Coordinates` ·
`Exponential` · `FilteredBasis` · `Filtrations` · `Flows` · `GlobalAxes` ·
`LatticeAxes`

**=> 这是"幂零群 / Malcev 基 / 中心列"的基础设施** ——
**放在 `Geometry` 目录下，但数学上属于李群与幂零群理论。**

### 于是"最大的一对桥梁"要重新定性

| 之前（按目录）| 现在（读源码后）|
|---|---|
| `Combinatorics` <-> `Geometry` 跨学科桥梁 | **组合数论的一个问题**，用**幂零群理论**做工具 |
| 263 条边 | 263 条边，**方向单向** |
| "跨领域合作" | **"一个研究项目要借用另一个数学分支的基础设施"** |

> **★ 这恰恰是"费马大定理式桥梁"的一个真实样本，但规模小得多**：
> 不是两个成熟领域互相启发，而是
> **一个组合问题需要幂零群理论才能推进**。

---

## 四、对总体结论的影响

| 问 4/题 A 的结论 | 深挖后 |
|---|---|
| "903 条跨科跨族边，占 0.44%" | **不变** |
| "Top-12 族对占 87%" | **不变，且解释更清楚** |
| "最大的一对是 263 条边" | **不变，但性质改写**：它是**一个具体研究项目**，不是学科间的普遍交流 |
| "95% 是数学内容不是基础设施" | **不变，且得到印证**（这个族的内容全是数学对象）|

**=> 深挖没有推翻结论，而是让结论更精确：**

> **那 0.44% 的"跨领域桥梁"，主要形态是
> 「一个具体问题借用另一个分支的工具」，
> 而不是「两个领域互相启发」。**
>
> **后者（费马大定理式的双向融合）在本数据里几乎看不到。**

---

## 五、方法论收获

1. **模块名不可信，要读源码。**
   `SumProduct` 的名字看起来像"和积工具"，实际是"**Hindman 猜想**"的研究项目。
2. **"子族数"是一个好判据**：259 个模块 / **1 个子族**
   => 立刻排除"工具库"（工具库会有多个平行的子族）。
3. **"外部引用方数量"是第二个好判据**：
   工具库会被多个不相关的族引用；只被一个族引用 => 是项目内部依赖。
4. **依赖方向必须显式测**：`a2b = 263, b2a = 0`
   => 才知道谁是底座、谁是上层。
   （不测方向就写"跨领域合作"是**不准确的**。）
