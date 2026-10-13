# W52 · 深挖 `Geometry.NilpotentCharts`：独立结果，还是脚手架？

> 承接 `SumProduct` 的诊断：`SumProduct` **单向依赖** `NilpotentCharts` 263 条边。
> 本文件判定**被依赖的那一侧**是什么性质。

---

## 四条判据的结果（**两条指向"独立"，两条指向"专为项目"**）

| # | 判据 | 实测 | 指向 |
|---|---|---|---|
| **1** | **子族数** | **26 个平行子族**（`Adjoint`/`CentralAxes`/`Filtrations`/`QuotientCharts`/`SmoothCalculus`/`TriangularBasis`…）| ★ **独立结果** |
| **2** | **外部引用方** | **只有 1 个族**（`Combinatorics.SumProduct`，263 条边）| 专为该项目 |
| **3** | **在 `formalization.yaml` 里吗** | `status.main_results` 200 个文件里含 `NilpotentChart` 的：**0 个**；`sources` 标题命中：**0 个** | 专为该项目（不是主结果）|
| **4** | **内部顶层定理** | 入度最高的是 `SmoothCalculus`(3) / `LinearLattices`(2) / `Polynomials`(2)，**出度为 0** => **没有汇总性主定理**，是一批并列的工具模块 | 专为该项目 |

---

## 关键区分：判据 1 与判据 2–4 说的不是同一件事

**判据 1（26 个平行子族）说明它"内容广、结构完整"** ——
`CentralAxes` 有 25 条定理、`LinearLattices` 有 12 条、`SmoothCalculus` 有 8 条。

**判据 2–4 说明它"在这个仓库里只服务一个用途"**。

**=> 这两件事不矛盾，合起来给出一个更精确的图像：**

> **`NilpotentCharts` 是"一个独立发展出来的数学方向"，
> 但它在**本仓库里**没有被当作独立成果发布
> —— 它只作为某一个组合问题的工具而存在。**

**证据**：它**不在** `formalization.yaml` 的 173 个 `sources` 里，
也**不在** 200 条 `main_results` 里。
=> **它在官方口径里不是"一个结果"，而是"某个结果的支撑材料"。**

---

## 源码证据：它在做什么数学

| 模块 | 内容 |
|---|---|
| `SmoothCalculus` | `exists_smooth_local_inverse` · `contMDiff_parameter_derivative` · `vectorPart` |
| `CentralAxes` | `centralAxesHom` · `centralAxesHom_range_le_center` · `exists_central_quotient_openChart` |
| `LinearLattices` | `Triangular` · `exists_vector_lattice_basis_of_span` · `compact_quotient_of_span` |
| `Polynomials` / `AdjointPolynomials` / `Filtrations` / `FilteredBasis` / `TriangularBasis` | Malcev 基与过滤结构 |
| `QuotientCharts` / `QuotientLie` / `QuotientTopology` / `SubspaceQuotients` | 商空间上的图表 |
| `RationalCoordinates` / `LatticeAxes` / `LatticeQuotients` | 有理坐标与格 |

**=> 这是"幂零李群上的坐标图表（charts）"的一整套理论**：
中心列、过滤基、三角基、商图表、格、光滑局部逆。
**这在数学上是自成一体的**（对应 Malcev 对应与幂零流形的坐标化）。

---

## ★ 于是"最大桥梁"的最终定性

**完整链条**：

```
Combinatorics.SumProduct          （Hindman 有限和与积猜想）
        |
        |  263 条边，单向
        v
Geometry.NilpotentCharts          （幂零李群上的图表理论）
        |
        |  不被任何其他族使用；
        |  也不在 formalization.yaml 里
        v
      （在本仓库里没有独立的"结果"身份）
```

| 问题 | 答案 |
|---|---|
| 依赖方向 | **单向**：组合 -> 几何 |
| 这是"两个领域互相启发"吗 | **不是** |
| 这是"一个分支借用另一个分支的工具"吗 | **是** |
| 被借的那一侧有独立成果身份吗 | **没有**（不在 formalization.yaml 里）|

> ### 最终结论
>
> **本仓库里最大的那对"跨领域桥梁"，形态是：
> 一个组合数论难题，伸手去够幂零李群理论里一套现成的坐标工具。
> 这与费马大定理（椭圆曲线借模形式）是同一个模式 ——
> 但**被借的那一侧在这里甚至没有被当作独立成果**。**
>
> **=> 这进一步支持"分支壁垒"的结论**：
> 不是两个领域在对等地合作，
> 而是**一个领域在做难题时，临时征用了另一个领域的机器**。

---

## 对总体结论的最终影响

| 层次 | 结论 | 是否被本次深挖改变 |
|---|---|---|
| 数字（99.55% / 98.3% / 0.44%）| 不变 | **否** |
| "87% 集中在 12 对族" | 不变，解释更清楚 | **否** |
| "95% 是数学内容不是基础设施" | 不变 | **否** |
| **"跨领域桥梁"的性质** | **从一个具体问题借用另一个分支的专门工具** | ★ **是（更精确）** |
| **"费马大定理式双向融合"在本数据里的出现** | **几乎看不到** | ★ **是（强化）** |

**=> 三次深挖（四层解剖 -> SumProduct -> NilpotentCharts）都没有推翻结论，
而是把"0.44% 是什么"从"目录不同"精确到了"哪种借用模式"。**
