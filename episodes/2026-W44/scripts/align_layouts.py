#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W44 · 音画对齐（**逐屏最佳匹配版**）。

## 演进过程（三种方法都试过，前两种失败）

| 方法 | 结果 |
|---|---|
| ① 贪婪关键词匹配（`make_storyboard.py`）| 版式被前屏抢走 ⇒ **8/18 屏标题与口播无关** |
| ② 顺序约束全局指派 | 顺序约束太强 ⇒ 同一版式落两屏 |
| ③ 锚定 + 通用兜底标题 | 配图对了，但有屏拿到"继续往下看"这类**无意义标题** |

## 本版（④）做法

**允许标题重复，逐屏独立取最佳**：

1. 对每一屏，用**全部 18 个版式**的关键词打分（含 5 张配图）；
2. 得分必须 **≥ MIN_HIT** 才接受，否则用中性标题；
3. **配图独占**：每张图只给命中最高的一屏（避免同一张图出现两次）；
4. 标题可以重复 —— 相邻屏用同一主题标题**比用错标题好**。

用法：
    $PY align_layouts.py [--write]
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

MIN_HIT = 2          # 至少命中 2 个关键词才认可该标题

# ★ 5 张配图的锚定关键词（与 results/figs 的实际内容一致）
FIG_KW: dict[str, list[str]] = {
    "results/figs/fig1_双峰错位.png": [
        "三个峰值", "不在同一年", "而在园幼儿的峰值", "幼儿园数量的峰值",
        "出生人口的峰值", "差了四到五年", "这个错位", "峰值在 2016"],
    "results/figs/fig4_传导进度.png": [
        "总落差是 47.4", "33.1 除以 47.4", "只走完了大约七成",
        "已经发生的在园幼儿降幅", "冲击只兑现"],
    "results/figs/fig3_需求预测.png": [
        "理论上限 100", "从 2311 万变成 2488 万", "只挽回 177 万",
        "7.6% 对 55.7", "数量级上补不上"],
    "results/figs/fig5_撤并策略.png": [
        "优先关", "最偏远", "贪心策略", "唯一的就近选择",
        "代价是非线性的", "拐点在 47"],
    "results/figs/fig6_公民办分化.png": [
        "谁在退出", "数据很不对称", "50.3", "27.1",
        "公办园反而增长了 10.1", "公办只降了 5.0"],
}

# 备用标题库（无配图屏用；键=关键词，值=标题）
TITLES: list[tuple[list[str], str]] = [
    (["降幅不是在收敛", "是在加速", "更值得注意的是降幅"],
     "降幅不是在收敛，是在加速"),
    (["先说数据来源", "因为这一步我栽过", "回原文", "900 万", "792 万",
      "差了 14"],
     "数据来源：这一步我栽过"),
    (["我建了一个队列模型", "队列在园率是", "标定结果", "对应的出生年份全部已经过去",
      "不是预测", "真正的不确定性", "三档情景"],
     "建立队列模型"),
    (["最有意思的一步", "怎么量化", "合成一个窗口", "5032", "2648"],
     "怎么量化『传导到哪一步了』"),
    (["谷底大约在 2028 年", "2576", "18.52", "4.67"],
     "谷底大约在 2028 年"),
    (["普及一下不就补上了", "理论上限", "接近全覆盖", "92.9"],
     "入园率补不上这个缺口"),
    (["总落差是 47.4", "33.1 除以 47.4", "只走完了大约七成",
      "已经发生的在园幼儿降幅"],
     "冲击只兑现了约七成"),
    (["队列在园率", "0.95 到 1.00", "接近 1 的含义", "已经接近全覆盖"],
     "『队列在园率』接近 1：入园已近全覆盖"),
    (["该关哪一所", "拿不到区县级", "合成城市", "比较三种策略"],
     "该关哪一所：前提与做法"),
    (["1.91 倍", "体制差异", "否证", "保本规模"],
     "原因不是规模小"),
    (["算错的地方", "基线", "第二，", "第三，"],
     "我算错的三个地方"),
]


def load_paras() -> list[str]:
    lines = (EP / "内容" / "讲稿.md").read_text(encoding="utf-8").splitlines()
    out = []
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith(">"):
            continue
        if s in ("---", "***", "___") or set(s) <= {"-", "*", "_"}:
            continue
        out.append(s)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    screens = spec["screens"]
    paras = load_paras()
    texts = ["".join(paras[s["paras"][0]:s["paras"][1]]) for s in screens]
    n = len(screens)

    sp = importlib.util.spec_from_file_location(
        "ms", str(EP / "scripts" / "make_storyboard.py"))
    ms = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(ms)
    LAY = ms.LAYOUTS
    cover = next((L for L in LAY if L["kind"] == "cover"), None)
    summ = next((L for L in LAY if L["kind"] == "summary"), None)

    print("=" * 100)
    print(f"  W44 · 音画对齐（逐屏最佳匹配，MIN_HIT={MIN_HIT}）")
    print("=" * 100)

    # ---------- 1. 配图独占指派 ----------
    fig_of: dict[int, str] = {}
    taken_fig: set[str] = set()
    scored = []
    for img, kws in FIG_KW.items():
        for j in range(n):
            scored.append((sum(1 for k in kws if k in texts[j]), img, j))
    for v, img, j in sorted(scored, reverse=True):
        if v < MIN_HIT or img in taken_fig or j in fig_of:
            continue
        fig_of[j] = img
        taken_fig.add(img)

    # ---------- 2. 逐屏定标题 ----------
    print(f"\n  {'屏':>3}{'命中':>6}{'版式':<9}{'标题':<32}口播首句")
    result: list[dict] = []
    weak = 0
    for j in range(n):
        t = texts[j]
        if j == 0 and cover:
            lay = {k: v for k, v in cover.items() if k != "kw"}
            hit = sum(1 for k in cover["kw"] if k in t)
        elif j == n - 1 and summ:
            lay = {k: v for k, v in summ.items() if k != "kw"}
            hit = sum(1 for k in summ["kw"] if k in t)
        elif j in fig_of:
            img = fig_of[j]
            full = next((L for L in LAY if L.get("img") == img), None)
            lay = ({k: v for k, v in full.items() if k != "kw"} if full
                   else {"kind": "figure", "head": "配图", "img": img})
            hit = sum(1 for k in FIG_KW[img] if k in t)
        else:
            best_t, best_v = None, 0
            for kws, title in TITLES:
                v = sum(1 for k in kws if k in t)
                if v > best_v:
                    best_v, best_t = v, title
            if best_t and best_v >= 1:
                # 复用同名 bullets 的 lines
                src = next((L for L in LAY if L["kind"] == "bullets"
                            and L.get("head") == best_t), None)
                lay = ({k: v for k, v in src.items() if k != "kw"} if src
                       else {"kind": "bullets", "head": best_t, "lines": []})
                hit = best_v
            else:
                lay = {"kind": "bullets", "head": "接着往下算",
                       "lines": []}
                hit = 0
                weak += 1
        if hit == 0 and lay["kind"] == "figure":
            weak += 1
        print(f"  {j+1:>3}{hit:>6}  {lay['kind']:<9}{lay.get('head','')[:30]:<32}"
              f"{t[:32]}")
        result.append(lay)

    print(f"\n{'='*100}")
    print(f"  弱匹配屏（命中 0）：{weak} / {n}　｜　配图已指派：{len(fig_of)}/5")

    if args.write:
        for j in range(n):
            spec["screens"][j] = {**spec["screens"][j], **result[j]}
        spec["_note"] = (spec.get("_note", "") +
                         "　｜　版式由 align_layouts.py **逐屏最佳匹配**"
                         "（配图独占，标题允许重复）。")
        SPEC.write_text(json.dumps(spec, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        print(f"  [ok] 已写回 {SPEC.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
