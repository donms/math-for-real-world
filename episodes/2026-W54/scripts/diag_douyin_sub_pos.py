#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W54 · 诊断：抖音 summary 卡的 CTA 与字幕是否重叠。

## 背景（实测发现的问题）

抽帧看 `douyin_08.png` 时，字幕出现在 **y≈1490–1530**，
而 summary 卡的 CTA 色块在 **y=1520–1660** ⇒ **几乎贴在一起**。

**算术核对**：

| 元素 | 位置 |
|---|---|
| CTA 色块 | `y = H − SAFE_BOTTOM − 230 = 1920 − 170 − 230 = 1520` 到 `1660` |
| 字幕 | `MarginV = 190` ⇒ 底边在 `1920 − 190 = 1730`；单行 `fontsize 70` ⇒ 顶边 ≈ `1480` |

**⇒ 字幕带上沿（≈1480）低于 CTA 下沿（1660）⇒ 重叠。**

**并且 CTA 本来就在抖音底部 25% 的 UI 遮挡区内（`y > 1440`）。**

## 本脚本作用

把两边的实际值都打出来，并给出**能避让的 `margin_v` 取值**。
只诊断，不改。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W54"
PUB = EP / "publish"

H = 1920
SAFE_BOTTOM = 170
FS = 70


def main() -> int:
    man = json.loads((PUB / "video_manifest_douyin.json").read_text(
        encoding="utf-8"))
    mv = int(man["sub"]["margin_v"])
    cards = json.loads((PUB / "cards_2026-W54.json").read_text(
        encoding="utf-8"))["cards"]

    print("=" * 84)
    print("  抖音 9:16 字幕 vs 卡片元素 位置核对")
    print("=" * 84)
    print(f"  画布 {man['w']}x{man['h']}｜字幕 fontsize {FS}｜"
          f"MarginV {mv}")
    print(f"  抖音底部 UI 遮挡区：y > {int(H*0.75)}（底部 25%）")

    # 字幕带
    sub_bottom = H - mv
    sub_top_1 = sub_bottom - int(FS * 1.25)          # 单行
    sub_top_2 = sub_bottom - int(FS * 1.25) * 2      # 双行
    print(f"\n  字幕（单行）：y ≈ {sub_top_1} → {sub_bottom}")
    print(f"  字幕（双行）：y ≈ {sub_top_2} → {sub_bottom}")

    # CTA
    print("\n  有 cta 的卡片：")
    any_cta = False
    for c in cards:
        if c.get("cta"):
            any_cta = True
            y0 = H - SAFE_BOTTOM - 230
            y1 = y0 + 140
            print(f"    卡 {c['idx']}（{c['kind']}）CTA：y = {y0} → {y1}")
            print(f"      ⇒ 与单行字幕重叠：{not (y1 < sub_top_1 or y0 > sub_bottom)}")
            print(f"      ⇒ CTA 是否在 UI 遮挡区（y>{int(H*0.75)}）：{y0 > H*0.75}")
    if not any_cta:
        print("    （无）")

    # 建议
    print("\n  " + "-" * 70)
    print("  ★ 结论与建议")
    print("  " + "-" * 70)
    print("  ① 抖音卡片**不应有 cta** —— CTA 色块在 y1520–1660，")
    print("     既撞字幕，又落在抖音底部 UI 遮挡区内；")
    print("  ② 若保留 cta，字幕 MarginV 必须 ≥ "
          f"{H - (H - SAFE_BOTTOM - 230) + 20} 才能完全避让，")
    print("     但那样字幕会跑到画面中部，压住卡片正文。")
    print("  ⇒ **正解：抖音版的 summary 卡去掉 cta。**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
