#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""核对 ASS 字幕的单行宽度是否超出安全区。

⚠️ 判据踩过的坑：最初写成
    len(整条字幕去掉 \N 后)
这等于**把所有行拼成一行**再量，一条 4 行字幕自然"超宽"——
87 条误报。正确做法是**先按 \N 拆成单行，再取最长行**。

安全宽度依据 manifest 的 sub 配置（fontsize 46、wrap 20）：
20 个全角字 × 46px ≈ 920px，1920 宽下左右各余 500px，安全。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASS = ROOT / "publish" / "视频" / "sub_2026-W40_lecture.ass"
MAN = ROOT / "publish" / "video_manifest_lecture.json"


def main() -> int:
    man = json.loads(MAN.read_text(encoding="utf-8"))
    cfg = man.get("sub") or {}
    fs = int(cfg.get("fontsize", 46))
    wrap = int(cfg.get("wrap", 20))
    canvas_w = int(man.get("w", 1920))
    font_name = cfg.get("font", "Microsoft YaHei")

    # **必须用真实像素宽度**：wrap_cjk 是按「字数」折算的，
    # 而中文字符比英文字母/数字宽，中英混排时字数相同但像素更宽。
    # 故这里用 PIL 实测。
    from PIL import ImageFont
    cand = {"Microsoft YaHei": r"<LOCAL_PATH>",
            "SimHei": r"<LOCAL_PATH>"}
    f = None
    try:
        f = ImageFont.truetype(cand.get(font_name, cand["Microsoft YaHei"]), fs)
    except Exception:                                          # noqa: BLE001
        pass

    def px_width(s: str) -> float:
        if f is None:
            return len(s) * fs
        return f.getlength(s)

    # 字幕居中显示，故安全条件是「单行宽度 <= 画布宽 - 2×边距」
    margin = 60
    limit_px = canvas_w - 2 * margin
    print(f"  配置：fontsize={fs} wrap={wrap} 画布宽={canvas_w} 字体={font_name}")
    print(f"  真实安全单行宽 <= {limit_px}px（画布 {limit_px/canvas_w*100:.0f}%，"
          f"左右各留 {margin}px 边距）\n")

    t = ASS.read_text(encoding="utf-8")
    lines = [ln for ln in t.splitlines() if ln.startswith("Dialogue:")]
    over, worst = [], (0.0, "")
    stats = []
    for ln in lines:
        body = ln.split(",", 9)[-1]
        body = re.sub(r"\{[^}]*\}", "", body)          # 去样式标签
        parts = body.split(r"\N")
        stats.append(len(parts))
        for p in parts:
            w = px_width(p)
            if w > limit_px:
                over.append((len(p), w, p))
            if w > worst[0]:
                worst = (w, p)

    print(f"  Dialogue 条数: {len(lines)}")
    print(f"  每条行数: 最少 {min(stats)} 最多 {max(stats)} "
          f"平均 {sum(stats)/len(stats):.1f}")
    print(f"  最长单行: {len(worst[1])} 字 / {worst[0]:.0f}px "
          f"（画布 {worst[0]/canvas_w*100:.0f}%）")
    print(f"    内容: {worst[1]}")
    print(f"  超出安全宽度的行: {len(over)}")

    if over:
        print("\n  超宽行明细（前 8 条）：")
        for n, w, p in sorted(over, key=lambda z: -z[1])[:8]:
            print(f"    {n:>3} 字 {w:>6.0f}px  {p}")
    else:
        print("\n  ✅ 所有单行均在安全宽度内")

    # 内容完整性：字幕文本 vs 讲稿
    script = (ROOT / "内容" / "讲稿.md").read_text(encoding="utf-8")
    script = re.sub(r"^\s*[>#].*$", "", script, flags=re.M).replace("**", "")
    script = re.sub(r"（[^）]*）", "", script)
    body_chars = len(re.sub(r"\s+", "", script))
    sub_chars = 0
    for ln in lines:
        b = re.sub(r"\{[^}]*\}", "", ln.split(",", 9)[-1])
        sub_chars += len(b.replace(r"\N", "").strip())
    print(f"\n  讲稿 {body_chars} 字 / 字幕 {sub_chars} 字  "
          f"差 {body_chars - sub_chars}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
