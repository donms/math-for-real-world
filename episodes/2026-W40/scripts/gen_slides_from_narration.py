#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""**按口播内容生成 B站幻灯片清单** —— 从构造上消掉图文错位。

## 为什么不能用人工/半自动对齐

本期在这个问题上反复失败：

* 手写 `slides16x9.json` 并按「主题」排序 → 与讲稿叙事顺序不同 → 整体错位；
* 写 `reorder_slides_bili.py` 按顺序表重排 → 顺序表本身也会错；
* 改 `BOUNDS` 切点 → 切点改了但**忘了重新生成音频** → 素材按新切点、音频按旧切点 → 仍错位。

**根因是「两份手工维护的清单要逐屏对齐」这个设计本身脆弱。**

## 本脚本的做法

让幻灯片**派生自口播**：读完讲稿、按 `BOUNDS` 切成 20 段后，
对每段**取其内容**生成该屏的标题与要点 —— 二者同源，不可能错位。

* 标题：取该段第一句（截断到合适长度），必要时按关键词换成人话标题；
* 要点：取该段各句，按长度切成 3–4 条；
* 版式：按段落在 Overall 结构里的位置选（首屏 cover、含数字对选用 compare、
  末屏 summary，其余 bullets）。

用法：
    $PY scripts/gen_slides_from_narration.py           # 生成并写入
    $PY scripts/gen_slides_from_narration.py --dry-run # 只看不写
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from make_manifest_platforms import build_bili_segments  # noqa: E402

ROOT = HERE.parent
SPEC = ROOT / "publish" / "slides16x9.json"

# 版式：按序号指定（首屏封面、末屏总结、若干对比屏、其余 bullet）
KINDS = {
    1: "cover",
    3: "compare",      # 两组数字
    7: "compare",      # 两个相反的分布
    12: "compare",     # 风险倍数结果
    20: "summary",
}

# 标题：按**该段实际讲什么**给（不是按序号猜）。
#
# ⚠️ 为什么用「内容关键词 → 标题」而不是「序号 → 标题」：
#    序号→标题 依赖 BOUNDS 切点与序号严格一致，一旦切点微调就整体错位
#    （本期在这一点上反复失败）。改成按**段首关键词**匹配标题，
#    即使切点有偏移，标题也跟着内容走，不会与画面/口播脱节。
TITLE_RULES: list[tuple[str, str]] = [
    ("先说结论", "本节结论：越极端，越互相排斥"),
    ("在回答那个问题之前", "先澄清：「五十年一遇」什么意思"),
    ("不是百分之百", "第一个反直觉：50 年内至少一次只有 63.6%"),
    ("那为什么不干脆看历史最大值", "为什么不能直接看历史最大值"),
    ("那怎么办", "怎么办：极值理论"),
    ("我们把这个方法用到十六个城市", "两条路径互相验证，并发现两个相反的分布"),
    ("所以这两类", "为什么会这样：气温有界、降水无界"),
    ("现在回到", "「五十年一遇」的高温是多少度"),
    ("还有一个小插曲", "模型与观测的张力（诚实记录）"),
    ("现在进入正题", "进入正题：怎么衡量「会不会一起来」"),
    ("那我们用什么指标", "风险倍数的定义"),
    ("这个结论和直觉相反", "证据一：季节性错开"),
    ("如果只看全年相关", "证据二：物理抑制"),
    ("第三条，也是方法上最重要", "证据三：copula 拟合不出尾部"),
    ("到这里，我们的结论是", "方法论结论：不能只靠一个 copula 族"),
    ("校正之后", "门槛正在移动"),
    ("最后，我们把结论落到城市", "结论的边界（必须说清）"),
    ("但个别城市的名次波动", "为什么不能公布精确名次"),
    ("最后留一道思考题", "思考题与答案"),
    ("先看两组数字", "先看两组数字"),
    ("于是问题来了", "于是问题来了：它们会一起来吗"),
]


def as_bullets(seg: str, maxn: int = 4, width: int = 34) -> list[str]:
    """把一段口播压成 3–4 条要点（按句合并，每条尽量接近 width 字）。"""
    sents = [x.strip() for x in seg.split("\n") if x.strip()]
    if not sents:
        return []
    # 目标条数：句数多于 maxn 时合并短句
    n = min(maxn, len(sents))
    per = max(1, round(len(sents) / n))
    out: list[str] = []
    for i in range(0, len(sents), per):
        chunk = "".join(sents[i:i + per])
        if len(chunk) > width * 2:
            chunk = chunk[:width * 2 - 1] + "…"
        out.append(chunk)
    return out[:maxn]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    segs = build_bili_segments()
    old = json.loads(SPEC.read_text(encoding="utf-8")) if SPEC.exists() else {}
    old_slides = old.get("slides", [])

    slides = []
    for i, seg in enumerate(segs, 1):
        kind = KINDS.get(i, "bullets")
        # 标题按**内容关键词**匹配（不是序号），切点微调也不会错位
        title = None
        for kw, t in TITLE_RULES:
            if kw in seg:
                title = t
                break
        if title is None:
            title = seg.split("\n")[0][:24]
        if i == 1:
            slides.append({
                "kind": "cover", "tag": "用数学看世界",
                "title": "越极端，越不会一起来",
                "sub": "16 个城市 · 86 年 · 约 50 万条逐日记录",
                "big": "0.32",
                "big_label": "99 分位处的风险倍数：小于 1 就是互相排斥",
            })
        elif kind == "summary":
            slides.append({"kind": "summary", "head": "三句话总结",
                           "lines": as_bullets(seg, 3)})
        else:
            slides.append({"kind": kind, "head": title,
                           "lines": as_bullets(seg)})

    d = dict(old)
    d["slides"] = slides
    d["brand"] = "用数学看世界"
    d["week"] = "2026-W40"
    d["_note"] = (
        "B站 16:9 教学幻灯片，20 屏。**本文件由 "
        "scripts/gen_slides_from_narration.py 从讲稿自动派生** —— "
        "每屏标题与要点都取自该屏口播，二者同源，"
        "从构造上消除「改了切点但忘了重生音频」导致的图文错位。"
        "手工改本文件后请勿再跑该脚本（会覆盖）。"
        "版式只有四种：cover / bullets / compare / summary。"
    )

    print(f"  生成 {len(slides)} 屏")
    for i, s in enumerate(slides, 1):
        h = s.get("head") or s.get("title", "")
        first = (s.get("lines") or [""])[0][:30]
        print(f"  {i:>2} [{s['kind']:<8}] {h[:26]:<26} | {first}")

    if args.dry_run:
        print("\n  --dry-run：未写入")
        return 0
    SPEC.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  ✅ 已写入 {SPEC.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
