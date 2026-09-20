#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""核对「每屏素材」与「该屏口播」是否同主题 —— 交付前的硬检查。

## 为什么要这个脚本

本项目的教训：**图和文可能各自都对，但整体错位一格**。
原因是「改了讲稿切点后忘了重新生成音频」——
于是素材按新顺序排、音频按旧切点切，逐屏看都"有内容"，
连起来才发现图文不搭。用户一眼就看出来了。

**光验证分段函数没用**（函数可能已正确，磁盘上的音频还是旧的）。
所以本脚本直接读**磁盘上的清单**（不是函数输出），
把每屏的 `text` 首句与该屏素材的标题并排打印，供人工确认。

用法：
    $PY scripts/check_av_match.py --root episodes\\2026-W40 --variant bili
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--variant", required=True)
    ap.add_argument("--spec", default=None,
                    help="素材清单（slides16x9.json / cards_*.json）。"
                         "默认按 variant 猜：bili→slides16x9.json，"
                         "douyin→cards_douyin.json")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    man = json.loads((root / "publish" /
                      f"video_manifest_{args.variant}.json").read_text(
        encoding="utf-8"))
    scenes = man["scenes"]

    spec_name = args.spec or ("slides16x9.json" if args.variant == "bili"
                              else f"cards_{args.variant}.json")
    spec_p = root / "publish" / spec_name
    titles = []
    if spec_p.exists():
        sp = json.loads(spec_p.read_text(encoding="utf-8"))
        items = sp.get("slides") or sp.get("cards") or []
        titles = [(s.get("head") or s.get("title") or "") for s in items]

    print(f"  {args.variant}：{len(scenes)} 屏 / 素材标题 {len(titles)} 个")
    print()
    print("  屏 | 素材标题                     | 该屏口播首句")
    print("  " + "-" * 84)
    for i, sc in enumerate(scenes, 1):
        title = titles[i - 1] if i - 1 < len(titles) else "(无素材标题)"
        first = (sc.get("text") or "").split("\n")[0]
        caps = sc.get("captions") or []
        n = len(caps)
        # 该屏第一条字幕的文本（这才是真正念出来的）
        c0 = (caps[0]["text"].split("\n")[0] if caps else "(无字幕)")
        print(f"  {i:>2} | {title[:26]:<26} | {first[:32]}")
        if caps and first[:12] not in caps[0]["text"]:
            print(f"     ⚠️ 清单 text 与首条字幕不一致")
        print(f"     └ 念的是：{c0[:52]}")
    print()
    print("  ⚠️ 请**人眼核对**每行「素材标题」与该屏念的内容是否同主题。")
    print("     脚本无法自动判断语义是否匹配 —— 它只能把两者并排给你看。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
