# W52 · 问 2：mathlib 反驳检验

## 为什么必须做

问 1 说「99.6% 的内部边是同学科」。一个立刻的反驳：

> 所有模块都 import mathlib，mathlib 覆盖全部数学分支
> => 它们**间接**都用了跨领域知识。

**若不排除这个解释，问 1 的结论不成立。**

## ★ 关键区分：共享底座 != 互相引用

| | 含义 | 费马大定理需要的是？ |
|---|---|---|
| **共享底座** | 两个学科都用 mathlib 的集合论 | [X] 不需要 |
| **桥梁** | 椭圆曲线引用模形式的**具体定理** | [OK] 正是它 |

## 检验结果

| 学科 | 含 mathlib 可达学科数 | 剔除后 | 仅靠 mathlib 才通的 |
|---|---|---|---|
| Algebra | 1 | 1 | 0 |
| AlgebraicGeometry | 1 | 1 | 0 |
| AlgebraicTopology | 4 | 4 | 0 |
| Analysis | 8 | 8 | 0 |
| CategoryTheory | 2 | 2 | 0 |
| Combinatorics | 5 | 5 | 0 |
| Computability | 3 | 3 | 0 |
| Dynamics | 3 | 3 | 0 |
| GameTheory | 1 | 1 | 0 |
| Geometry | 8 | 8 | 0 |
| GroupTheory | 5 | 5 | 0 |
| InformationTheory | 4 | 4 | 0 |
| LinearAlgebra | 1 | 1 | 0 |
| MathematicalPhysics | 5 | 5 | 0 |
| MeasureTheory | 2 | 2 | 0 |
| ModelTheory | 1 | 1 | 0 |
| NumberTheory | 1 | 1 | 0 |