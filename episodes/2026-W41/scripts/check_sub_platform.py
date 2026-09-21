#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""校验某条视频字幕的单行宽度与折行是否适合该平台。

与 `check_sub_width.py`（教学片专用）的区别：本脚本读**任意变体**的清单与 ASS，
按清单里的 `sub` 配置（字号/边距/画布宽）判定。

⚠️ 判据必须用**真实像素宽度**：`wrap_cjk` 按「字数」折算，
而中文字符比英文字母宽，中英混排时字数相同但像素更宽。

用法：
    $PY scripts/check_sub_platform.py --root episodes\\2026-W40 --variant bili
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from PIL import ImageFont


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--variant", required=True)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    man_p = root / "publish" / f"video_manifest_{args.variant}.json"
    man = json.loads(man_p.read_text(encoding="utf-8"))
    cfg = man.get("sub") or {}
    fs = int(cfg.get("fontsize", 46))
    canvas_w = int(man.get("w", 1920))
    canvas_h = int(man.get("h", 1080))
    margin_v = int(cfg.get("margin_v", 58))
    one_line = bool(cfg.get("one_line", True))

    ass_p = root / "publish" / "视频" / f"sub_{man['week']}_{args.variant}.ass"
    if not ass_p.exists():
        print(f"  [!] 缺字幕文件 {ass_p.name}")
        return 2

    try:
        f = ImageFont.truetype(r"<LOCAL_PATH>", fs)
    except Exception:                                          # noqa: BLE001
        f = None

    def w_px(s: str) -> float:
        return f.getlength(s) if f else len(s) * fs

    margin = 60
    limit = canvas_w - 2 * margin

    lines = [ln for ln in ass_p.read_text(encoding="utf-8-sig").splitlines()
             if ln.startswith("Dialogue:")]
    subs = [ln for ln in lines if ln.split(",", 9)[3].strip() == "Sub"]
    over, worst, rows = [], (0.0, ""), []
    for ln in subs:
        body = re.sub(r"\{[^}]*\}", "", ln.split(",", 9)[-1])
        parts = body.split(r"\N")
        rows.append(len(parts))
        for p in parts:
            w = w_px(p)
            if w > limit:
                over.append((len(p), w, p))
            if w > worst[0]:
                worst = (w, p)

    print(f"  {args.variant}：画布 {canvas_w}×{canvas_h}  字号 {fs}  "
          f"底部留白 {margin_v}px  单行模式={'开' if one_line else '关'}")
    print(f"  字幕事件 {len(subs)} 条")
    if rows:
        print(f"  每条行数：最少 {min(rows)} 最多 {max(rows)} 平均 {sum(rows)/len(rows):.2f}")
    print(f"  最长单行 {len(worst[1])} 字 / {worst[0]:.0f}px（画布 {worst[0]/canvas_w*100:.0f}%）")
    print(f"    内容：{worst[1]}")
    if one_line and max(rows, default=0) > 1:
        print(f"  ❌ 单行模式已开，但仍有 {max(rows)} 行的字幕")
    print(f"  超出安全宽度（>{limit:.0f}px）的行：{len(over)}")
    for n, w, p in sorted(over, key=lambda z: -z[1])[:5]:
        print(f"    {n:>3} 字 {w:>6.0f}px  {p}")

    # 底部安全区：字幕底部不能压到平台 UI
    if canvas_h == 1920:
        sub_bottom = margin_v
        print(f"  抖音底部安全区：字幕距底 {sub_bottom}px"
              f"（{'OK' if sub_bottom >= 250 else '偏小，建议 ≥250'}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
