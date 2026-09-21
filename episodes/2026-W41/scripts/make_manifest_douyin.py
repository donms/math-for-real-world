#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""生成抖音竖屏的清单与字幕 —— 追加到 make_manifest.py 的能力。

## 抖音与 B站的关系

两者**共用素材目录结构但内容不同**：

| | B站 | 抖音 |
|---|---|---|
| 画布 | 1920×1080 | 1080×1920 |
| 内容 | 15 屏长教学（8.9 分钟）| **7 屏 / 约 45 秒** |
| 口播 | 讲稿 15 段（汉字数字，发音用）| 短文案（逐句）|
| 字幕 | 字号 46 / 每行 30 字 / 底 58px | 字号 62 / 每行 14 字 / **底 300px** |

**为什么抖音字幕底部留 300px**：抖音底部有播放条与文案区，
字幕压在那里会被遮住。

## 口播来源

抖音口播**不取自讲稿**（讲稿是长视频的），而是取自
`内容/抖音.md` 的方案 A（纠错版）—— 与画面同一角度：**"堵点不是水位造成的"**。

用法：
    $PY make_manifest_douyin.py --ep 2026-W41
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent

# ---------------------------------------------------------------------------
# 每期抖音的逐屏口播（与 cards_douyin.json 的 7 屏一一对应）
# 写成"汉字数字"以便 TTS 正确发音；画面用的是阿拉伯数字。
# ---------------------------------------------------------------------------
DOUYIN_BY_EP: dict[str, list[str]] = {
    "2026-W41": [
        "西江堵了很多年，我以为是枯水期水位低造成的。",
        "逻辑很顺：枯水期水位低，船就装不满，通过量自然下降。",
        "但翻了十五期官方月度简报，数据说不是。"
        "水位和装载率的相关性是负的，而装载率全年就在零点五七七到零点六四零之间，"
        "极差只有百分之十。",
        "那真正的原因是什么？我把检修期和其余月份分开看："
        "检修期日均闸次只有四十七点七和六十一点六，其余月份是五十五点七到七十三点七。"
        "待闸从七十一艘涨到八百一十三艘，对应的正是检修停航。",
        "这个区别很实在。以为主因是水位，就会去搞水文调控；"
        "而实际主因是检修，该做的是优化检修安排。",
        "顺带说新运河：平陆运河九月十六日通航，"
        "预计分流长洲百分之二十二到四十五的货，而它自己不会堵，利用率只有百分之五十二。",
        "记住一句话：堵是设备可用性问题，不是水位问题。"
        "换个归因，就换个解法。",
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", required=True)
    args = ap.parse_args()

    d = ROOT / "episodes" / args.ep
    lines = DOUYIN_BY_EP.get(args.ep)
    if not lines:
        print(f"  [!] 未登记 {args.ep} 的抖音口播")
        return 2

    cards_p = d / "publish" / "cards_douyin.json"
    if not cards_p.exists():
        print(f"  [!] 缺 {cards_p} —— 先跑 make_douyin_cards.py --export")
        return 2
    n_cards = len(json.loads(cards_p.read_text(encoding="utf-8"))["cards"])

    imgs = sorted((d / "publish" / "视频" / "素材9x16").glob("*.png"))
    if not imgs:
        print("  [!] 缺 9:16 素材，先跑 render_cards.py --size 1080x1920")
        return 2
    if not (len(lines) == len(imgs) == n_cards):
        print(f"  [!] 口播 {len(lines)} 条 ≠ 素材 {len(imgs)} 张 "
              f"≠ 卡片 {n_cards} 屏")
        return 2

    scenes = []
    for i, (img, txt) in enumerate(zip(imgs, lines), 1):
        scenes.append({
            "img": f"publish/视频/素材9x16/{img.name}",
            "dur": 0.0, "text": txt, "_page": i,
            "captions": [], "audio": None, "gap_after": 0.0,
        })

    # 自检：图片必须存在（W40 因此出现过"一屏纯背景色"）
    missing = [s["img"] for s in scenes if not (d / s["img"]).exists()]
    if missing:
        print(f"  [!] 清单里有 {len(missing)} 张图不存在")
        return 2

    man = {"week": args.ep, "brand": "用数学看世界",
           "fps": 30, "w": 1080, "h": 1920, "bgm": None,
           "sub": {"fontsize": 62, "margin_v": 300, "outline": 3,
                   "font": "Microsoft YaHei", "wrap": 14,
                   "max_caption": 42, "one_line": True},
           "_note": "抖音 9:16 竖屏短视频。7 屏 = cards_douyin.json 的 7 张；"
                    "口播取自 内容/抖音.md 的方案 A（纠错版），"
                    "与画面同一角度。margin_v=300 是底部安全区"
                    "（抖音 UI 占位）。",
           "scenes": scenes, "voice": {}}
    p = d / "publish" / "video_manifest_douyin.json"
    p.write_text(json.dumps(man, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    tot = sum(len(s["text"]) for s in scenes)
    print(f"  [douyin] {len(scenes)} 屏 / {tot} 字 → {p.name}"
          f"（预计 {tot/6.7:.0f} 秒）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
