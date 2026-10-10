#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""诊断：W46 字幕里的数字形态是从哪一步来的。

用户报告两件事：
1. 字幕里又变成口播内容了；
2. 「先分清楚 2 个概念，它们经常被混为 1 谈」——
   讲稿写的是「两个概念 / 混为一谈」，字幕却成了阿拉伯数字。

本脚本逐步定位：讲稿原文 -> split_captions -> clean_caption -> 分屏表。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W46"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(EP / "scripts"))

from tts_text import clean_caption, to_tts                          # noqa: E402

PROBE = "先分清楚两个概念，它们经常被混为一谈。"


def main() -> int:
    print("=" * 88)
    print("  诊断：字幕数字形态的来源")
    print("=" * 88)

    print(f"\n  [1] 直接调 clean_caption")
    print(f"      输入: {PROBE}")
    print(f"      输出: {clean_caption(PROBE)}")
    print(f"      to_tts: {to_tts(PROBE)}")

    print(f"\n  [2] 讲稿原文（第四屏附近）")
    narr = (EP / "内容" / "讲稿.md").read_text(encoding="utf-8")
    for ln in narr.splitlines():
        if "混为一谈" in ln or "混为1谈" in ln:
            print(f"      {ln.strip()[:80]}")

    print(f"\n  [3] 分屏表里屏 4 的实际值")
    d = json.loads((EP / "publish" / "分屏表.json").read_text(encoding="utf-8"))
    for s in d["screens"]:
        if s.get("idx") == 4:
            print(f"      text     : {str(s.get('text'))[:70]}")
            for c in s.get("captions", [])[:3]:
                print(f"      caption  : {str(c)[:70]}")
            for c in s.get("tts_captions", [])[:3] if "tts_captions" in s else []:
                print(f"      tts_cap  : {str(c)[:70]}")

    print(f"\n  [4] 结论")
    a = clean_caption(PROBE)
    if "2" in a or "1" in a:
        print("      **clean_caption 仍在做「汉字->阿拉伯」** —— 单向改造没生效")
    else:
        print("      clean_caption 干净 ⇒ 转换发生在别处（见 [3] 的 raw 值）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
