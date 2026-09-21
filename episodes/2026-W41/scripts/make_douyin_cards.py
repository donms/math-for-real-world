#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""生成抖音 9:16 竖屏素材清单（cards_douyin.json）—— 通用版。

## 为什么抖音要单独一套

小红书卡片是 3:4（1080×1440），抖音是 9:16（1080×1920）——
**二者不能互相替代**：抖音是满屏竖版，3:4 放上去会留黑边。

而 W41 的抖音**没有小红书卡片可复用**（本期小红书文案尚未出图），
故这里显式撰写一套。

## 内容设计：与 B站**刻意不同**

B站是 15 屏长教学（8.9 分钟），抖音是 **7 屏 / 约 45 秒**单点打穿。
抖音只讲一个最有钩子的发现：**"堵点不是水位造成的，是检修"**。

要点要求：短语级（≤28 字）、只给结论与数字、用阿拉伯数字。

用法：
    $PY make_douyin_cards.py --ep 2026-W41            # 打印
    $PY make_douyin_cards.py --ep 2026-W41 --export    # 写 cards_douyin.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent

# ---------------------------------------------------------------------------
# 每期的抖音 7 屏（显式撰写；字段须与 render_cards.py 的 draw_<kind> 一致）
#
# 各类型字段：
#   cover   : title / sub / big / big_label / tag
#   text    : head / lines
#   ⚠️ 卡片渲染器**没有 bullets 版式** —— 那是 16:9 幻灯片的；
#      卡片用 text。写成 bullets 会被未知卡片类型静默跳过（实测漏渲 2 屏）。
#   compare : head / rows=[[左,右],…]（**最多 3 行**，超出会被丢弃）
#   summary : head / lines / cta（**cta 单行**，过长会溢出）
#   formula : head / formula / terms / key
#   text    : head / lines
# ---------------------------------------------------------------------------
CARDS_BY_EP: dict[str, list[dict]] = {
    "2026-W41": [
        dict(kind="cover", tag="用数学看世界",
             title="堵点不是水位造成的",
             sub="长洲船闸 15 期官方简报",
             big="0.078",
             big_label="排除检修期后，水位与日闸次几乎无关"),
        dict(kind="compare", head="我原以为是这样",
             rows=[["枯水期", "水位低"],
                   ["水位低", "船装不满"],
                   ["结果", "通过量下降"]]),
        dict(kind="compare", head="数据说不是",
             rows=[["水位 vs 装载率", "−0.461（方向相反）"],
                   ["装载率全年", "0.577–0.640"],
                   ["极差", "仅 10%"]]),
        dict(kind="compare", head="那真正的原因是什么",
             rows=[["检修期日闸次", "47.7 / 61.6"],
                   ["其余月份", "55.7–73.7"],
                   ["待闸 71 → 813 艘", "对应检修停航"]]),
        dict(kind="text", head="这个区别很实在",
             lines=["以为主因是水位 → 去搞水文调控",
                    "实际主因是检修 → 该优化检修安排"]),
        dict(kind="text", head="顺带说新运河",
             lines=["平陆运河 9 月 16 日通航",
                    "预计分流长洲 22%–45% 的货",
                    "它自己不会堵（利用率仅 52%）"]),
        dict(kind="summary", head="记住一句话",
             lines=["堵是设备可用性问题，不是水位问题",
                    "换个归因，就换个解法"],
             cta="数据、代码、论文全部公开"),
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", required=True)
    ap.add_argument("--export", action="store_true")
    args = ap.parse_args()

    cards = CARDS_BY_EP.get(args.ep)
    if not cards:
        print(f"  [!] 未登记 {args.ep} 的抖音卡片")
        return 2

    spec = {"week": args.ep, "brand": "用数学看世界",
            "series": "用数学看世界", "footer_series_only": True,
            "_note": "抖音 9:16 竖屏素材（1080×1920），与小红书 3:4 卡片"
                     "严格分开。渲染命令要加 --size 1080x1920。"
                     "字段名须与 render_cards.py 的 draw_<kind> 一致 ——"
                     "写错不报错、只渲染出空白卡（W40 踩过）。",
            "cards": cards}

    print(f"  {args.ep}：{len(cards)} 屏")
    print()
    for i, c in enumerate(cards, 1):
        h = c.get("head") or c.get("title", "")
        print(f"  {i}. [{c['kind']:<8}] {h[:30]}")
        for k in ("lines", "rows"):
            for x in (c.get(k) or [])[:4]:
                s = "　".join(str(y) for y in x) if isinstance(x, list) else x
                print(f"        · {s[:52]}")
        if c.get("big"):
            print(f"        大数字 {c['big']} — {c.get('big_label','')[:34]}")

    # 校验：compare 最多 3 行、要点长度、cta 长度
    print()
    bad = 0
    for i, c in enumerate(cards, 1):
        if c["kind"] == "compare" and len(c.get("rows", [])) > 3:
            print(f"  ❌ 第 {i} 屏 compare 有 {len(c['rows'])} 行（最多 3，"
                  f"超出会被静默丢弃）")
            bad += 1
        for x in (c.get("lines") or []):
            if len(x) > 30:
                print(f"  ⚠️ 第 {i} 屏要点偏长（{len(x)} 字）：{x[:28]}…")
        if c.get("cta") and len(c["cta"]) > 22:
            print(f"  ⚠️ 第 {i} 屏 cta 偏长（{len(c['cta'])} 字），可能溢出")
    print(f"  {'✅ 校验通过' if bad == 0 else f'❌ {bad} 处硬错误'}")

    if args.export:
        p = ROOT / "episodes" / args.ep / "publish" / "cards_douyin.json"
        p.write_text(json.dumps(spec, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        print(f"\n  ✅ {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
