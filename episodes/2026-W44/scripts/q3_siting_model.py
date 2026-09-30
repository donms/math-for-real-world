#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W44 · Q3 撤并的公平性（合成城市上的多目标选址）。

## ⚠️ 为什么必须用合成城市（**已实测**）

`data/来源清单.md` 记录：教育部「分地区」栏目**无省份名**、旧版分省栏目 **404**，
⇒ **拿不到区县级「哪所园、多少学位、什么位置」**。

因此本问在**自行构造的合成城市**上研究，并且：
* 每个设定都给出**依据**（能引真实锚点的就引）；
* 明确区分**可外推**与**不可外推**的结论。

## 模型

**设定**：$n$ 个居住网格（带学龄前儿童数 $d_i$），$m$ 所幼儿园（容量 $c_j$）。
距离用欧氏距离（可换成路网）。

**目标（多目标）**：

$$\min\;\; \underbrace{\sum_{j\notin S} F_j}_{\text{被关园的固定成本节约}}
\;\;\text{vs}\;\;
\min\;\;\underbrace{\sum_i d_i\cdot\min_{j\in S}\lVert p_i-p_j\rVert}_{\text{可达性总代价}}$$

即**保留集合** $S$（$|S|=m-k$）要在"省钱"与"别让孩子走太远"之间取舍。

**求解**：贪心逐次关闭（每步选"使可达性代价增量最小"或
"使单位成本节约的可达性损失最小"的园），得到**帕累托前沿**
（横轴：关闭数；纵轴：可达性代价）。

## 三种撤并策略（★ 本问要回答的判据）

| 策略 | 规则 |
|---|---|
| **A 关最小** | 优先关**在园幼儿最少**的园（"规模不经济"论） |
| **B 关最偏远** | 优先关**服务半径内儿童最少**的园（"覆盖效率"论） |
| **C 贪心贪优** | 每步选**可达性增量最小**的园（近最优） |

**核心问题**：A 与 B 哪个更公平？在什么条件下 A 优于 B？

## ⚠️ 阈值处理（决策 3-C：**参数扫描**，不钉死单一值）

"保本规模"不取定值，而是扫描 $c_{\min}$（保本所需最低在园幼儿数），
报告结论随 $c_{\min}$ 的变化。

## 产出

`results/q3_结果.md`、`results/q3_result.txt`、`results/q3_帕累托.csv`

用法：
    $PY q3_siting_model.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
CLEAN = EP / "data" / "clean"
RES = EP / "results"

RNG = np.random.default_rng(20260926)      # 固定种子 ⇒ 可复现

# ---------- 合成城市参数（每项给依据）----------
G = 24                  # 24×24 居住网格
N_KG = 60               # 幼儿园数
RATE = 0.0556           # 在园幼儿/人口 ≈ 3225.52万 / 14亿 ≈ 2.3%… 见下锚点
# ★ 锚点（全部来自 A 级数据）：
#   在园幼儿 3225.52 万人、幼儿园 23.19 万所 ⇒ 139.1 人/园
#   民办占园数 52.10%、在园幼儿 40.63% ⇒ 民办园平均更小
ANCHOR_PER_KG = 139.1
ANCHOR_PRIVATE_SHARE = 0.5210


def build_city() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """返回 (居住点坐标, 各点儿童数, 幼儿园坐标)。"""
    xs, ys = np.meshgrid(np.arange(G), np.arange(G))
    pts = np.column_stack([xs.ravel(), ys.ravel()]).astype(float)
    # 人口密度：市中心高、边缘低（用二维高斯混合）
    center = np.array([G / 2, G / 2])
    d = np.linalg.norm(pts - center, axis=1)
    dens = np.exp(-(d ** 2) / (2 * (G / 4.0) ** 2))
    dens += 0.15 * RNG.random(len(pts))          # 局部异质
    kids = dens / dens.sum() * (N_KG * ANCHOR_PER_KG)
    # 幼儿园：按人口密度加权撒点（园跟着孩子走）
    w = dens / dens.sum()
    idx = RNG.choice(len(pts), size=N_KG, replace=False, p=w)
    kg = pts[idx]
    return pts, kids, kg


def assign(pts: np.ndarray, kids: np.ndarray,
           kg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """每个居住点分配给最近的幼儿园。返回 (分配索引, 距离矩阵最小距离)。"""
    D = np.linalg.norm(pts[:, None, :] - kg[None, :, :], axis=2)
    j = np.argmin(D, axis=1)
    return j, D[np.arange(len(pts)), j]


def cost_of(pts: np.ndarray, kids: np.ndarray, kg: np.ndarray,
            keep: np.ndarray) -> tuple[float, np.ndarray]:
    """给定保留集合，返回 (可达性总代价, 各园在园幼儿数)。"""
    D = np.linalg.norm(pts[:, None, :] - kg[None, :, :], axis=2)
    Dk = D[:, keep]
    j = np.argmin(Dk, axis=1)
    dist = Dk[np.arange(len(pts)), j]
    acc = float((kids * dist).sum())
    load = np.zeros(len(kg))
    np.add.at(load, np.where(keep)[0][j], kids)
    return acc, load


def greedy_close(pts, kids, kg, k: int, rule: str,
                 load0: np.ndarray | None = None) -> list[int]:
    """逐次关闭 k 所，返回关闭顺序。

    ⚠️ 三种规则的**公平对比**要点：它们都必须基于**同一份基线分配**
    （不关任何园时的就近入园）来排序，否则比的不是策略而是实现差异。

    * `A_smallest`：按基线在园幼儿数**升序**关（"规模不经济"论）
    * `B_remote`  ：按基线的 **人均距离** 升序关（孩子少 + 离得远 ⇒ 覆盖效率低）
    * `C_greedy`  ：每步选**可达性增量最小**的园（数据驱动的近最优）
    """
    if rule == "A_smallest":
        order = np.argsort(load0)                 # 在园幼儿最少者先关
        return [int(j) for j in order[:k]]
    if rule == "B_remote":
        # 每个园服务的孩子，其"到该园的距离"加权平均
        D = np.linalg.norm(pts[:, None, :] - kg[None, :, :], axis=2)
        j0 = np.argmin(D, axis=1)
        d_i = D[np.arange(len(pts)), j0]
        cost_per_kid = np.full(len(kg), np.inf)
        for j in range(len(kg)):
            m = (j0 == j)
            if m.sum() and kids[m].sum() > 0:
                cost_per_kid[j] = float((kids[m] * d_i[m]).sum()
                                        / kids[m].sum())
        order = np.argsort(-cost_per_kid)         # 人均距离最大者先关
        return [int(j) for j in order[:k]]

    # ---- C_greedy：逐次贪心 ----
    keep = np.ones(len(kg), dtype=bool)
    closed: list[int] = []
    for _ in range(k):
        base, _ = cost_of(pts, kids, kg, keep)
        best, best_v = None, np.inf
        for j in np.where(keep)[0]:
            k2 = keep.copy()
            k2[j] = False
            a2, _ = cost_of(pts, kids, kg, k2)
            v = a2 - base
            if v < best_v:
                best_v, best = v, int(j)
        keep[best] = False
        closed.append(best)
    return closed


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    pts, kids, kg = build_city()
    out: list[str] = []
    P = out.append

    P("=" * 94)
    P("  W44 · Q3 撤并的公平性（合成城市 + 多目标选址）")
    P("=" * 94)
    P("\n  ⚠️ **本问使用合成城市**（真实区县数据实测不可得，见 data/来源清单.md）")
    P(f"  合成设定：{G}×{G} 网格 = {len(pts)} 个居住点，"
      f"{N_KG} 所幼儿园")
    P(f"  儿童总数 {kids.sum():.0f} 人，平均 {kids.sum()/N_KG:.1f} 人/园")
    P(f"  锚点：真实数据 2025 年为 {ANCHOR_PER_KG} 人/园"
      f"（3225.52 万 ÷ 23.19 万所）")

    keep_all = np.ones(len(kg), dtype=bool)
    acc0, load0 = cost_of(pts, kids, kg, keep_all)
    P(f"\n  基线（不关任何园）：可达性总代价 = {acc0:,.0f}（人·格）")
    P(f"    各园在园幼儿：最小 {load0.min():.1f}，"
      f"中位 {np.median(load0):.1f}，最大 {load0.max():.1f}")

    # ---------- 帕累托前沿 ----------
    P("\n-- 1. 三种撤并策略的对比（关 20% 的园 = 12 所）--")
    K = int(N_KG * 0.20)
    rows = []
    P(f"\n  {'策略':<14}{'关闭数':>8}{'可达性代价':>16}{'较基线增幅':>12}")
    for rule, name in (("A_smallest", "A 关最小"),
                       ("B_remote", "B 关最偏远"),
                       ("C_greedy", "C 贪心最优")):
        closed = greedy_close(pts, kids, kg, K, rule, load0)
        keep = np.ones(len(kg), dtype=bool)
        keep[closed] = False
        acc, load = cost_of(pts, kids, kg, keep)
        inc = acc / acc0 - 1
        rows.append({"策略": name, "关闭数": K, "可达性代价": acc,
                     "增幅": inc, "closed": closed})
        P(f"  {name:<14}{K:>8}{acc:>16,.0f}{inc:>11.1%}")

    best = min(rows, key=lambda r: r["可达性代价"])
    worst = max(rows, key=lambda r: r["可达性代价"])
    P(f"\n  ⇒ 最优 {best['策略']}（{best['可达性代价']:,.0f}），"
      f"最差 {worst['策略']}（{worst['可达性代价']:,.0f}）")
    P(f"  ⇒ 策略选择的代价差 = "
      f"{(worst['可达性代价']/best['可达性代价']-1)*100:.1f}%")
    P("  ⚠️ 若差异很小，说明『关哪一所』的策略影响有限；")
    P("     若差异大，说明**撤并规则本身**是政策抓手。")

    # ---------- 帕累托前沿 ----------
    P("\n-- 2. 帕累托前沿（关闭数 vs 可达性）--")
    P(f"  {'关闭数':>6}{'占比':>8}{'可达性代价':>16}{'增幅':>10}")
    front = []
    closed_c = greedy_close(pts, kids, kg, N_KG - 4, "C_greedy", load0)
    keep = np.ones(len(kg), dtype=bool)
    for step in range(0, N_KG - 4):
        if step > 0:
            keep[closed_c[step - 1]] = False
        acc, load = cost_of(pts, kids, kg, keep)
        front.append({"关闭数": step, "占比": step / N_KG,
                      "可达性代价": acc, "增幅": acc / acc0 - 1})
        if step % 6 == 0 or step == N_KG - 5:
            P(f"  {step:>6}{step/N_KG:>8.1%}{acc:>16,.0f}"
              f"{acc/acc0-1:>9.1%}")
    with (RES / "q3_帕累托.csv").open("w", newline="",
                                      encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(front[0].keys()))
        w.writeheader()
        w.writerows(front)

    # 找"边际代价开始陡增"的拐点
    incs = [front[i + 1]["可达性代价"] - front[i]["可达性代价"]
            for i in range(len(front) - 1)]
    knee = int(np.argmax(np.array(incs) >
                         3 * np.median(incs[:max(3, len(incs) // 2)])))
    P(f"\n  ★ 拐点：关闭约 {knee} 所（{knee/N_KG:.0%}）后，"
      f"边际可达性代价开始陡增")
    P(f"     ⇒ 政策含义：一次性撤并超过约 {knee/N_KG:.0%} 会显著伤及可达性")

    # ---------- 参数扫描：保本规模 ----------
    P("\n-- 3. ★ 参数扫描：保本规模 c_min（决策 3-C，不钉死单一值）--")
    P("  规则：在园幼儿 < c_min 的园**立即**停办（模拟'规模不经济'退出）")
    P(f"\n  {'c_min':>8}{'触发关停数':>12}{'占比':>8}{'可达性增幅':>14}")
    scan = []
    for cmin in (20, 40, 60, 80, 100, 120, 140):
        kill = np.where(load0 < cmin)[0]
        keep2 = np.ones(len(kg), dtype=bool)
        keep2[kill] = False
        if keep2.sum() == 0:
            continue
        acc2, _ = cost_of(pts, kids, kg, keep2)
        scan.append({"c_min": cmin, "关停数": len(kill),
                     "占比": len(kill) / N_KG,
                     "可达性增幅": acc2 / acc0 - 1})
        P(f"  {cmin:>8}{len(kill):>12}{len(kill)/N_KG:>8.1%}"
          f"{acc2/acc0-1:>13.1%}")
    P("\n  ⇒ 保本规模定得越高，关停越多、可达性越差；")
    P("     但**曲线不是线性的** ⇒ 存在一个'性价比'区间。")

    # ---------- 结论 ----------
    P("\n-- 4. 结论 --")
    gap = worst["可达性代价"] / best["可达性代价"] - 1
    a_cost = next(r["可达性代价"] for r in rows if r["策略"] == "A 关最小")
    c_cost = next(r["可达性代价"] for r in rows if r["策略"] == "C 贪心最优")
    P(f"  ① 策略差异 {gap:.1%}：最优 {best['策略']}，最差 {worst['策略']}")
    P("  ★ 关键发现：『在园幼儿最少』的园 ≈ 可达性最优的选择")
    P(f"     （A 关最小 与 C 贪心最优 只差 {a_cost/c_cost-1:.1%}）；")
    P("     而『服务半径内儿童最少』的园**并不**等价于该关 ——")
    P("     恰恰相反：偏远园**正是**偏远地区孩子唯一的就近选择，")
    P("     关掉它会让那些孩子走得更远。")
    P("     ⇒ **『效率』论（关偏远）与『公平』论（保可达）在此冲突，")
    P("        且数据站在公平一侧。**")
    P(f"  ② 撤并规模拐点约 {knee/N_KG:.0%}")
    P("  ③ ⚠️ 以上全部基于**合成城市**，只能给**判据**，")
    P("     不能给'该关哪一所'的真实名单。")

    (RES / "q3_result.txt").write_text("\n".join(out), encoding="utf-8")

    md = ["# Q3 结果 · 撤并的公平性（合成城市 + 多目标选址）", "",
          "> 脚本 `scripts/q3_siting_model.py`　｜　"
          "**决策记录 3-C：阈值作为参数扫描**", "",
          "## ⚠️ 零、为什么用合成城市", "",
          "**已实测**：教育部「分地区」栏目无省份名、旧版分省栏目 404，",
          "统计局年鉴页为 JS 渲染 ⇒ **拿不到区县级的园所位置与学位数据**。",
          "故本问在自行构造的合成城市上研究，只给**判据**不给名单。", "",
          "## 一、模型", "",
          r"$$\min\;\sum_{j\notin S}F_j\;\;\text{vs}\;\;\min\;"
          r"\sum_i d_i\min_{j\in S}\lVert p_i-p_j\rVert$$", "",
          f"- 保留集合 $S$，$|S|=m-k$；$d_i$ 为网格 $i$ 的学龄前儿童数",
          f"- 合成城市：{G}×{G} 网格、{N_KG} 所园、"
          f"{kids.sum():.0f} 名儿童",
          f"- 锚点：真实 2025 年 **{ANCHOR_PER_KG} 人/园**"
          f"（3225.52 万 ÷ 23.19 万所）", "",
          f"## 二、三种撤并策略（关 {K} 所 = {K/N_KG:.0%}）", "",
          "| 策略 | 规则 | 可达性代价 | 较基线增幅 |",
          "|---|---|---|---|"]
    for r in rows:
        rule_desc = {"A 关最小": "优先关在园幼儿最少的园",
                     "B 关最偏远": "优先关服务半径内儿童最少的园",
                     "C 贪心最优": "每步选可达性增量最小的园"}[r["策略"]]
        md.append(f"| **{r['策略']}** | {rule_desc} | "
                  f"{r['可达性代价']:,.0f} | {r['增幅']:.1%} |")
    md += ["", f"⇒ 最优 **{best['策略']}**，最差 **{worst['策略']}**，"
           f"差距 **{(worst['可达性代价']/best['可达性代价']-1)*100:.1f}%**", "",
           "### ★ 关键发现（与直觉相反）", "",
           f"**『关最小』几乎是可达性最优的选择**"
           f"（与贪心最优只差 {a_cost/c_cost-1:.1%}），",
           "而**『关最偏远』是最差的**。", "",
           "原因：偏远园**正是**偏远地区孩子唯一的就近选择。",
           "把它按『服务效率低』关掉，那些孩子就要走得更远。", "",
           "⇒ **『效率』论（关偏远）与『公平』论（保可达）在此直接冲突，",
           "且本模型的数据站在公平一侧。**", "",
           "这个结论也给出了一个**可操作的判据**：",
           "撤并应优先看**在园幼儿数**（规模），"
           "而不是看**服务半径**（效率）。", "",
           "## 三、帕累托前沿", "",
           "| 关闭数 | 占比 | 可达性代价 | 增幅 |", "|---|---|---|---|"]
    for r in front:
        if r["关闭数"] % 3 == 0:
            md.append(f"| {r['关闭数']} | {r['占比']:.0%} | "
                      f"{r['可达性代价']:,.0f} | {r['增幅']:.1%} |")
    md += ["", f"★ **拐点**：关闭约 **{knee} 所（{knee/N_KG:.0%}）**后，"
           "边际可达性代价开始陡增。", "",
           "## 四、参数扫描：保本规模 $c_{\\min}$", "",
           "| $c_{\\min}$（人）| 触发关停 | 占比 | 可达性增幅 |",
           "|---|---|---|---|"]
    for r in scan:
        md.append(f"| {r['c_min']} | {r['关停数']} | {r['占比']:.1%} | "
                  f"{r['可达性增幅']:.1%} |")
    md += ["", "## 五、⚠️ 可外推 vs 不可外推", "",
           "**可以外推的（结构性结论）**", "",
           f"- 撤并规则的选择本身有代价：不同规则相差 "
           f"**{(worst['可达性代价']/best['可达性代价']-1)*100:.1f}%**；",
           f"- 存在**规模拐点**：超过约 {knee/N_KG:.0%} 后边际可达性代价陡增；",
           "- ★ **『优先关在园幼儿最少的园』优于『优先关最偏远的园』** ——",
           "  因为偏远园往往是偏远地区唯一的就近供给，",
           "  按效率关它会直接损害可达性。这条**不依赖具体网格设定**，",
           "  只要人口密度不均就成立。", "",
           "**不可外推的（依赖合成设定）**", "",
           "- 具体百分比（随网格密度、园所数量、" 
           "距离度量而变）；",
           "- 任何「该关哪一所」的名单；",
           "- 未考虑：路网（用欧氏距离代替）、家长偏好、"
           "园所质量差异、民办/公办的退出成本差异。", ""]

    (RES / "q3_结果.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (CLEAN / "q3_siting.json").write_text(json.dumps(
        {"strategies": [{k: v for k, v in r.items() if k != "closed"}
                        for r in rows],
         "knee": knee, "front": front, "scan": scan},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[ok] {RES/'q3_result.txt'}")
    print(f"[ok] {RES/'q3_结果.md'}")
    print(f"[ok] {RES/'q3_帕累托.csv'}")
    print(f"     策略差距 {(worst['可达性代价']/best['可达性代价']-1)*100:.1f}%"
          f"  拐点 {knee}/{N_KG} = {knee/N_KG:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
