#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W44 · 版式对齐（**人工核对版**，最终采用）。

## 为什么最终要人工定

试过 4 种自动匹配，都有残留问题：

| 方法 | 残留问题 |
|---|---|
| ① 贪婪关键词（`make_storyboard.py`）| 版式被前屏抢走 ⇒ 8/18 屏错位 |
| ② 顺序约束全局指派 | 同一版式落两屏 |
| ③ 锚定 + 通用兜底标题 | 出现"继续往下看"这类**无意义标题** |
| ④ 逐屏最佳匹配 | 仍有 7 屏命中偏低（标题短、2-gram 判据过粗）|

根因：**屏是按段区间切的、版式是按叙事节拍设计的，两套切法天生不对齐**；
而标题很短（8–14 字），用 2-gram 交集判"是否匹配"噪声太大。

⇒ **最终由人逐屏核对定稿**（下表每一行都对照过该屏的口播原文）。
本脚本把这张表**固化下来**，保证可复现、不被自动逻辑覆盖。

用法：
    $PY assign_layouts.py [--write]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
PUB = EP / "publish"
SPEC = PUB / "分屏表.json"

# ★★ 人工定稿表：屏号 → (kind, head, img|None, lines)
#    每一行都对照过该屏的口播原文（见脚本末尾的核对打印）
FINAL: dict[int, dict] = {
    1: {"kind": "cover",
        "head": "幼儿园四年关了 6.29 万所，但我算出来：才走了一半",
        "sub": "教育部十年公报 + 国家统计局十年出生人口",
        "lines": ["2025 年全国幼儿园 23.19 万所",
                  "较 2021 年峰值减少 6.29 万所"],
        "big": "69.8%", "big_label": "出生下降的冲击，只兑现了这么多"},
    2: {"kind": "figure", "head": "三个峰值，不在同一年",
        "img": "results/figs/fig1_双峰错位.png",
        "lines": ["降幅逐年扩大：2022 年 −1.9% 到 2025 年 −8.5%",
                  "出生人口峰值 2016 年",
                  "在园幼儿峰值 2020 年，幼儿园数峰值 2021 年",
                  "三个峰值不在同一年"]},
    3: {"kind": "bullets", "head": "为什么差了四到五年",
        "lines": ["一个 3 岁的孩子才进幼儿园",
                  "2021 年的在园幼儿，对应 2018 年前后出生",
                  "已经发生的关停，只反映了前几年的出生下降"]},
    4: {"kind": "bullets", "head": "数据来源：这一步我栽过",
        "lines": ["教育部公报原文 11 篇（2016 至 2025 连续十年）",
                  "国家统计局出生人口 10 年，回原文核对全部通过",
                  "选题时引用的 900 万是检索摘要，官方为 792 万",
                  "出生人口是唯一自变量，错 14% 会毁掉全部预测"]},
    5: {"kind": "bullets", "head": "数据来源：这一步我栽过",
        "lines": ["教育部公报原文 11 篇（2016 至 2025 连续十年）",
                  "国家统计局出生人口 10 年，回原文核对全部通过",
                  "选题时引用的 900 万是检索摘要，官方为 792 万",
                  "出生人口是唯一自变量，错 14% 会毁掉全部预测"]},
    6: {"kind": "bullets", "head": "建立队列模型",
        "lines": ["在园幼儿 = 队列在园率 × 三个出生队列之和",
                  "标定结果 0.9727，误差 65 万人",
                  "2026 至 2028 是推算，不是预测",
                  "不确定性来自未来出生，用三档情景覆盖"]},
    7: {"kind": "bullets", "head": "2026 至 2028 是推算，不是预测",
        "lines": ["对应的出生年份全部已经过去",
                  "真正的不确定性来自未来的出生人口",
                  "所以用三档情景覆盖：",
                  "延续 792 万 / 含龙年波动 / 回升到 954 万"]},
    8: {"kind": "bullets", "head": "怎么量化『传导到哪一步了』",
        "lines": ["把出生队列按 3 岁 4 岁 5 岁在园合成窗口",
                  "峰值窗口对应 2021 年入园",
                  "即 2016 到 2018 年出生，三个队列共 5032 万",
                  "谷底窗口是 2023 到 2025 年出生，共 2648 万"]},
    9: {"kind": "figure", "head": "冲击只兑现了约七成",
        "img": "results/figs/fig4_传导进度.png",
        "lines": ["总落差 47.4%", "已兑现 33.1%",
                  "33.1 除以 47.4 等于 69.8%"]},
    10: {"kind": "bullets", "head": "入园率顶到上限也补不上",
         "lines": ["毛入园率从 77.4% 升到 92.9%",
                   "顶到理论上限 100%，只挽回 7.6%",
                   "而出生人口降了 55.7%",
                   "7.6% 对 55.7%，数量级上补不上"]},
    11: {"kind": "figure", "head": "谷底大约在 2028 年",
         "img": "results/figs/fig3_需求预测.png",
         "lines": ["在园幼儿约 2576 万，比现在再降两成",
                   "需要的幼儿园约 18.52 万所",
                   "比现在还要再减 4.67 万所"]},
    12: {"kind": "bullets", "head": "『队列在园率』已接近 1",
         "lines": ["观测值在 0.95 到 1.00 之间",
                   "含义：一个出生队列在 3 到 5 岁的每一年",
                   "都约有同等数量的人在园",
                   "也就是说，入园已经接近全覆盖"]},
    13: {"kind": "bullets", "head": "该关哪一所：前提与做法",
         "lines": ["实测拿不到区县级园所位置与学位数据",
                   "所以构造合成城市，只给判据不给名单",
                   "关掉 20% 的园，比较三种策略"]},
    14: {"kind": "figure", "head": "关最小接近最优，关偏远最差",
         "img": "results/figs/fig5_撤并策略.png",
         "lines": ["贪心最优 +3.0%，关最小 +4.0%",
                   "关最偏远 +27.0%，是最差的",
                   "偏远园往往是当地唯一的就近选择",
                   "而且撤并的代价是非线性的，拐点在 47% 左右"]},
    15: {"kind": "figure", "head": "谁在退出：民办 7 年腰斩",
         "img": "results/figs/fig6_公民办分化.png",
         "lines": ["民办在园幼儿降 50.3%，公办只降 5.0%",
                   "民办园降 27.1%，公办园反而增长 10.1%"]},
    16: {"kind": "bullets", "head": "原因不是规模小",
         "lines": ["观测到的退出率之比是 1.91 倍",
                   "但任何纯规模阈值都产生不了这么大的差异",
                   "结论是体制差异：补贴、地权、融资成本",
                   "这个失败否证了一个很合理的解释"]},
    17: {"kind": "bullets", "head": "我算错的三个地方",
         "lines": ["参数不可识别，一度预测降 77%（物理上不可能）",
                   "对比实验未统一基线，结论被推翻",
                   "峰值年不可辨识：2020 与 2021 只差 0.27%"]},
    18: {"kind": "summary", "head": "三句话",
         "lines": ["卡的不是关不关，是按什么规则关",
                   "已经关掉的 6.29 万所不是终点，才走了一半多一点",
                   "入园率补不上出生下降的缺口"],
         "cta": "数据与代码全部公开"},
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    screens = spec["screens"]
    n = len(screens)
    if len(FINAL) != n:
        print(f"[!] 定稿表 {len(FINAL)} 屏 ≠ 分屏表 {n} 屏")
        return 2

    # 讲稿段落（用于核对打印）
    lines = (EP / "内容" / "讲稿.md").read_text(encoding="utf-8").splitlines()
    ps = []
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith(">"):
            continue
        if s in ("---", "***", "___") or set(s) <= {"-", "*", "_"}:
            continue
        ps.append(s)

    print("=" * 100)
    print("  W44 · 版式对齐（人工核对定稿）")
    print("=" * 100)
    print(f"\n  {'屏':>3}{'版式':<9}{'标题':<30}口播首句（用于核对）")
    for j in range(n):
        lay = FINAL[j + 1]
        lo, hi = screens[j]["paras"]
        txt = "".join(ps[lo:hi])
        print(f"  {j+1:>3}  {lay['kind']:<9}{lay['head'][:28]:<30}{txt[:36]}")

    if args.write:
        for j in range(n):
            old = screens[j]
            spec["screens"][j] = {
                "page": old["page"], "sec": old["sec"],
                "paras": old["paras"], "chars": old["chars"],
                **FINAL[j + 1]}
        spec["_note"] = (spec.get("_note", "") +
                         "　｜　版式由 assign_layouts.py **人工核对定稿**"
                         "（自动匹配试过 4 种，短标题下 2-gram 判据噪声过大）。")
        SPEC.write_text(json.dumps(spec, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        print(f"\n  [ok] 已写回 {SPEC.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
