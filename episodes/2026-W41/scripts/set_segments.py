#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""**直接指定每屏的段区间**并写入 segments.json（不再依赖分配器）。

## 为什么改成完全手工

`make_video_spec.py` 的流程是「按字数比例分配屏数 → 在语义白名单里切」。
两层都含启发式，结果语义边界反复落不到位，用户**三次**指出同一类问题：

* 第 1 次：「两个口径」那段应在后面一屏
* 第 2 次：货种重叠应在第 3 屏
* 第 3 次：**两个口径那段在第 8 屏上没体现**

每次我只修一层（改白名单，或改覆盖表），另一层又把结果挪走。
**根因是「让启发式猜屏数」这件事本身不对** —— 哪几段合成一屏是编辑判断，
规则穷举不了。故本脚本**直接写死每屏的段区间**，完全确定性。

## 用法

    $PY set_segments.py --ep 2026-W41 --write
    # 然后依次：make_video_spec.py --export → render_slides16x9.py
    #          → make_manifest.py → make_preflight_doc.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(r".")

# ---------------------------------------------------------------------------
# 每屏的段区间（人工指定；(节号, 起始段, 结束段)，左闭右开）
#
# W41 设计（16 屏）：
#   屏 1  第1节[0,6)   开场：平陆运河通航 + 西江堵点
#   屏 2  第2节[0,5)   反差：1 亿吨 vs 2.24 亿吨
#   屏 3  第2节[5,7)   货种高度重叠
#   屏 4  第3节[0,6)   把老瓶颈量出来
#   屏 5  第4节[0,6)   我的假设被数据否定了
#   屏 6  第4节[6,12)  真正成因：检修
#   屏 7  第5节[0,3)   广义成本 + 等待时间反推
#   屏 8  第5节[3,7)   ★ 运费优势：两个独立口径互相印证
#   屏 9  第5节[7,12)  模型失败：100% 分流率
#   屏 10 第5节[12,17) 判据与修正（加转换摩擦）
#   屏 11 第6节[0,5)   新通道自己会不会堵
#   屏 12 第6节[5,9)   临界值：21 天
#   屏 13 第7节[0,6)   敏感性：转换摩擦 ±90%
#   屏 14 第8节[0,6)   可检验的预测
#   屏 15 第9节[0,4)   边界：缺陷方向性
#   屏 16 第9节[4,10)  最后总结三句话（含引子）

# ---------------------------------------------------------------------------
RANGES: dict[str, list[tuple[int, int, int]]] = {
    "2026-W41": [
        (1, 0, 6), (2, 0, 5), (2, 5, 7), (3, 0, 6),
        (4, 0, 6), (4, 6, 14),
        (5, 0, 3), (5, 3, 7), (5, 7, 12), (5, 12, 17),
        (6, 0, 5), (6, 5, 9),
        (7, 0, 6), (8, 0, 6), (9, 0, 4), (9, 4, 10),
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", default="2026-W41")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    import sys
    sys.path.insert(0, str(ROOT / "episodes" / args.ep / "scripts"))
    from make_video_spec import load_sections

    d = ROOT / "episodes" / args.ep
    secs = load_sections(d / "内容" / "讲稿.md")
    ranges = RANGES[args.ep]

    segs = []
    print(f"  {'屏':>3} {'节':>3} {'段区间':>10} {'字数':>5}  内容首句")
    print("  " + "-" * 78)
    bad = 0
    for page, (n, a, b) in enumerate(ranges, 1):
        paras = secs[n][a:b]
        if not paras:
            print(f"  ❌ 第 {page} 屏取不到 第{n}节 段{a}-{b-1}")
            bad += 1
            continue
        text = "\n".join(paras)
        segs.append({"page": page, "sec": n, "paras": [a, b],
                     "chars": len(text.replace("\n", ""))})
        print(f"  {page:>3} {n:>3} {f'{a}-{b-1}':>10} "
              f"{len(text.replace(chr(10), '')):>5}  {paras[0][:40]}")
    print(f"\n  合计 {len(segs)} 屏")
    if bad:
        print(f"  ❌ {bad} 处区间越界，请检查 RANGES")
        return 2

    if args.write:
        p = d / "publish" / "segments.json"
        data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        data["segments"] = segs
        data["target"] = len(segs)
        data["_note"] = ("边界由 scripts/set_segments.py 的 RANGES **人工写死**，"
                         "不经分配器 —— 自动分配多次导致语义错位"
                         "（用户三次指出同一类问题）。")
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        print(f"\n  ✅ 已写入 {p.name}（{len(segs)} 屏）")
        print("  ⚠️ 接着依次跑：make_video_spec.py --export → "
              "render_slides16x9.py → make_manifest.py → make_preflight_doc.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
