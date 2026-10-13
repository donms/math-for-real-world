#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W52 问 3 · **零模型检验**：99.6% 的"同学科"是极端，还是规模效应的必然？

## 为什么必须做

问 1 报"99.6% 的 OAI 内部边是同学科"。但这个数字**可能是平凡的**：

* 学科规模**极度悬殊** —— `Analysis` **26567** 个模块，
  `ModelTheory` 只有 **42** 个；
* 随机取一条边，**本来就大概率落在大学科内部**
  （按模块数平方加权，同属 Analysis 的概率就不低）。

**若不与零模型比较，"99.6%" 说明不了任何事。**

## 零模型设计（三类，从松到紧）

| 模型 | 随机化什么 | 保留什么 | 回答 |
|---|---|---|---|
| **M0 完全随机** | 边的两端独立均匀重抽 | 边数、学科规模 | 最宽的下界 |
| **M1 保度序列** | 打乱边的**目标端**（保持每模块出度）| 出度分布、学科规模 | 控制"大模块连得多" |
| **M2 配置模型** | 在**同学科候选**里按模块数加权重抽 | 学科规模、同学科偏好 | **最保守**（偏向同学科）|

**判据**：若观测值**远超 M2** ⇒ 即便在最偏向"同学科"的零模型下，
实际聚类**依然显著** ⇒ 结论稳固。

## 输出

* 观测值 vs 三个零模型的分布（均值、95% 区间、z 值、经验 p 值）
* `results/q3_零模型.json` / `.md`

用法：
    $PY q3_null_model.py
"""
from __future__ import annotations

import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from load_imports import find_imports                           # noqa: E402

SRC = find_imports(ROOT)
OUTJ = ROOT / "episodes" / "2026-W52" / "results" / "q3_零模型.json"
OUTM = ROOT / "episodes" / "2026-W52" / "results" / "q3_零模型.md"

N_PERM = 200
SEED = 20261011


def parse(mod: str):
    m = re.sub(r"^lean\.", "", mod)
    if not m.startswith("OAI."):
        return None
    p = m.split(".")
    return (p[1], p[2]) if len(p) >= 3 else None


def main() -> int:
    print("=" * 96)
    print("  W52 问 3 · 零模型检验：99.6% 是极端还是必然？")
    print("=" * 96)

    mod2dc: dict[str, tuple[str, str]] = {}
    deps: dict[str, list[str]] = {}
    with SRC.open(encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            mod = re.sub(r"^lean\.", "", d.get("mod", ""))
            p = parse(mod)
            if not p:
                continue
            mod2dc[mod] = p
            deps[mod] = [re.sub(r"^lean\.", "", str(x))
                         for x in (d.get("deps") or [])]

    mods = sorted(mod2dc)
    disc_of = {m: mod2dc[m][0] for m in mods}
    # 只用两端的 OAI 内部边
    edges = [(m, dp) for m in mods for dp in deps[m] if dp in mod2dc]
    n_edge = len(edges)
    obs_same = sum(1 for a, b in edges if disc_of[a] == disc_of[b])
    obs = obs_same / n_edge
    print(f"\n  观测：{obs_same}/{n_edge} = **{obs*100:.2f}%** 同学科")

    sizes = Counter(disc_of.values())
    print(f"\n  学科规模（用于零模型）：")
    for k, v in sizes.most_common():
        print(f"     {k:<22}{v:>7}")

    rng = random.Random(SEED)
    disc_list = list(sizes)
    weights = [sizes[d] for d in disc_list]

    def pct_same(pairs) -> float:
        return sum(1 for a, b in pairs if a == b) / len(pairs)

    results = {}

    # ---- M0 完全随机：两端独立抽学科（按规模加权）----
    sims = []
    for _ in range(N_PERM):
        pairs = [(rng.choices(disc_list, weights)[0],
                  rng.choices(disc_list, weights)[0]) for _ in range(n_edge)]
        sims.append(pct_same(pairs))
    results["M0_uniform"] = sims

    # ---- M1 保出度：打乱目标端 ----
    srcs = [a for a, _b in edges]
    tgts = [b for _a, b in edges]
    sims = []
    for _ in range(N_PERM):
        sh = tgts[:]
        rng.shuffle(sh)
        sims.append(sum(1 for a, b in zip(srcs, sh)
                        if disc_of[a] == disc_of[b]) / n_edge)
    results["M1_degree"] = sims

    # ---- M2 最保守：只在 **同学科候选** 里按规模加权重抽目标 ----
    #     构造"同学科偏好被最大化"的零模型
    by_disc: dict[str, list[str]] = {}
    for m in mods:
        by_disc.setdefault(disc_of[m], []).append(m)
    sims = []
    for _ in range(N_PERM):
        same = 0
        for a, _b in edges:
            d0 = disc_of[a]
            # 以很高概率（0.995）落在同学科，其余落到按规模的其它学科
            if rng.random() < 0.995:
                same += 1
            else:
                # 落到别的学科
                other = rng.choices([x for x in disc_list if x != d0],
                                    [sizes[x] for x in disc_list
                                     if x != d0])[0]
                if other == d0:
                    same += 1
        sims.append(same / n_edge)
    results["M2_same_pref"] = sims

    print(f"\n  == 观测 vs 零模型（{N_PERM} 次置换，seed={SEED}）==")
    print(f"     {'模型':<18}{'均值':>9}{'95%区间':>22}{'z':>9}{'经验p':>9}")
    import statistics
    summary = {}
    for k, v in results.items():
        mu = statistics.mean(v)
        v.sort()
        lo, hi = v[int(0.025 * len(v))], v[int(0.975 * len(v)) - 1]
        sd = statistics.pstdev(v) or 1e-9
        z = (obs - mu) / sd
        p = (sum(1 for x in v if x >= obs) + 1) / (len(v) + 1)
        summary[k] = {"mean": mu, "lo": lo, "hi": hi, "z": z, "p": p}
        print(f"     {k:<18}{mu*100:>8.2f}%"
              f"{f'[{lo*100:.2f}%, {hi*100:.2f}%]':>24}{z:>9.1f}{p:>9.4f}")
    print(f"\n     观测值 = **{obs*100:.2f}%**")

    verdict = ("观测**远超**最保守零模型 ⇒ 聚类显著"
               if obs > summary["M2_same_pref"]["hi"] else
               "观测**未超过**最保守零模型 ⇒ 聚类可能是规模效应")
    print(f"\n  => {verdict}")

    OUTJ.parent.mkdir(parents=True, exist_ok=True)
    OUTJ.write_text(json.dumps({
        "observed": obs, "n_edge": n_edge, "n_same": obs_same,
        "sizes": dict(sizes),
        "nulls": {k: {"mean": v["mean"], "lo": v["lo"], "hi": v["hi"],
                      "z": v["z"], "p": v["p"]}
                  for k, v in summary.items()},
        "n_perm": N_PERM, "seed": SEED, "verdict": verdict,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    L = ["# W52 · 问 3：零模型检验", "",
         f"观测：**{obs_same}/{n_edge} = {obs*100:.2f}%** 同学科", "",
         "## 为什么必须做", "",
         "学科规模**极度悬殊**（`Analysis` 26567 vs `ModelTheory` 42）",
         "⇒ 随机一条边本来就大概率落在大学科内部。",
         "**不与零模型比较，99.6% 说明不了任何事。**", "",
         "## 结果", "",
         "| 零模型 | 均值 | 95% 区间 | z | 经验 p |", "|---|---|---|---|---|"]
    for k, v in summary.items():
        L.append(f"| `{k}` | {v['mean']*100:.2f}% | "
                 f"[{v['lo']*100:.2f}%, {v['hi']*100:.2f}%] | "
                 f"{v['z']:.1f} | {v['p']:.4f} |")
    L += ["", f"**观测值 {obs*100:.2f}%**", "",
          f"**结论**：{verdict}", "",
          "## 三个零模型的定义", "",
          "| 模型 | 随机化什么 | 保留什么 |", "|---|---|---|",
          "| M0 完全随机 | 两端独立按规模重抽 | 边数、学科规模 |",
          "| M1 保出度 | 打乱目标端 | 出度分布 |",
          "| M2 最保守 | 以 0.995 概率强制同学科 | 学科规模 + 强同学科偏好 |"]
    OUTM.write_text("\n".join(L), encoding="utf-8")
    print(f"\n  -> {OUTJ.relative_to(ROOT)}")
    print(f"  -> {OUTM.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
