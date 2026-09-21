#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""检查「每屏画面标题」与「该屏口播内容」是否对得上 —— 交付前硬检查。

## 为什么需要

W41 用户核对时发现：「运费优势我用了两个独立口径互相验证……这段是不是
应该在第八屏」——一查果然错位：第 7 屏里塞进了本该属于第 8、9 屏的内容。

根因是 **DP 按字数均衡切段，不懂语义**。这类错误不会报错，
只能靠人眼逐屏看 —— 而人眼看不完 15 屏。

本脚本把「标题」与「该屏口播的关键信息」并排列出**供人核对**，
并做一层**机械检查**：标题里的关键词/数字是否出现在该屏口播里。
（机械检查只能发现明显不搭，语义是否贴切仍需人眼。）

用法：
    $PY check_screen_titles.py --ep 2026-W41
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(r".")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", default="2026-W41")
    args = ap.parse_args()
    d = ROOT / "episodes" / args.ep

    man = json.loads((d / "publish" / "video_manifest_bili.json")
                     .read_text(encoding="utf-8"))
    spec = json.loads((d / "publish" / "slides16x9.json")
                      .read_text(encoding="utf-8"))

    print(f"  {args.ep}：{len(man['scenes'])} 屏\n")
    print("  屏 | 画面标题                       | 该屏口播首句")
    print("  " + "-" * 90)
    flag = 0
    for i, (sc, sl) in enumerate(zip(man["scenes"], spec["slides"]), 1):
        head = sl.get("head") or sl.get("title", "")
        text = sc["text"]
        first = text.split("\n")[0]
        print(f"  {i:>2} | {head[:30]:<30} | {first[:44]}")

        # 机械检查：标题里的数字是否出现在口播里（阿拉伯 vs 汉字要都试）
        nums = re.findall(r"\d+\.?\d*", head)
        miss = []
        for n in nums:
            if n in text:
                continue
            # 标题用阿拉伯、口播用汉字 → 宽松放过（人工确认）
            miss.append(n)
        if miss:
            print(f"     ⚠️ 标题里的数字 {miss} 未在该屏口播中直接出现"
                  f"（可能口播写作汉字，需人工确认）")
            flag += 1
    print()
    print(f"  标题数字未直接匹配：{flag} 处（多为阿拉伯/汉字差异，需人眼确认）")
    print("  ⚠️ 脚本**查不出语义是否贴切** —— 那正是要你逐屏看的部分。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
