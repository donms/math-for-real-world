#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""生成 W40 教学视频的**占位**素材（16:9, 1920x1080）。

为什么先做占位：
    配音管线（add_voice → render_video）要求每屏有对应图片路径存在。
    用户当前的优先级是**先审音频内容**，故先用占位图把音频流程跑通；
    正式教学幻灯片之后替换同路径文件即可，无需改清单。

⚠️ 两个坑：
  1. 函数名与参数名都叫 `font` 会导致
     "positional argument follows keyword argument" —— 故函数改名 `get_font`，
     且调用一律用**位置参数**（PIL 的 `text` 签名是 (xy, text, fill, font, ...)，
     第 3 位是 fill 而不是 font，写成 `font=` 容易与位置参数顺序冲突）。
  2. 字体缺字形会**静默出豆腐块**，故本文件只用中英文与数字，不用特殊下标。
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
MAN = ROOT / "publish" / "video_manifest_lecture.json"
OUT = ROOT / "publish" / "视频" / "素材16x9"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080
NAVY = (31, 59, 99)
RED = (192, 57, 43)
WHITE = (255, 255, 255)
LIGHT = (187, 204, 221)
YELLOW = (255, 217, 102)
DIM = (150, 160, 170)

FONT_B = r"<LOCAL_PATH>"
FONT_R = r"<LOCAL_PATH>"


def get_font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except Exception:                                          # noqa: BLE001
        return ImageFont.load_default()


def centered(d: ImageDraw.ImageDraw, y: int, text: str, f, fill) -> None:
    """PIL 的签名是 text(xy, text, fill, font, ...) —— **fill 在 font 之前**。

    早期写成 d.text(xy, text, f, fill) 会报
    `TypeError: color must be int or tuple`（把字体对象当成了颜色）。
    """
    bb = d.textbbox((0, 0), text, font=f)
    d.text(((W - (bb[2] - bb[0])) / 2, y), text, fill, f)


def main() -> int:
    man = json.loads(MAN.read_text(encoding="utf-8"))
    scenes = man["scenes"]

    # 封面
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 26, H], fill=RED)
    centered(d, 250, "用数学看世界", get_font(FONT_R, 46), LIGHT)
    centered(d, 340, "越来越热，也越来越涝？", get_font(FONT_B, 96), WHITE)
    centered(d, 490, "高温与暴雨的联合极值风险", get_font(FONT_R, 52), LIGHT)
    d.rounded_rectangle([300, 640, W - 300, 790], 18, fill=(42, 74, 115))
    centered(d, 680, "风险主要来自单独的极端，而非叠加的极端",
             get_font(FONT_B, 50), YELLOW)
    centered(d, 880, "16 个中国城市 · 1940–2026 年 · 约 50 万条逐日记录",
             get_font(FONT_R, 34), LIGHT)
    img.save(OUT / "sec_00.png")

    # 各节
    f_sec = get_font(FONT_R, 46)
    f_title = get_font(FONT_B, 58)
    f_body = get_font(FONT_R, 40)
    f_foot = get_font(FONT_R, 26)
    for sc in scenes:
        n = sc["_sec"]
        title = sc.get("_title") or f"第 {n} 节"
        img = Image.new("RGB", (W, H), WHITE)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W, 150], fill=NAVY)
        d.rectangle([0, 0, 26, H], fill=RED)
        d.text((80, 46), f"第 {n} 节", LIGHT, f_sec)
        d.text((300, 34), title, WHITE, f_title)

        y = 260
        for ln in sc["text"].split("\n")[:8]:
            d.text((110, y), ln, NAVY, f_body)
            y += 76
        if sc["text"].count("\n") > 8:
            d.text((110, y + 10), "……", DIM, f_body)

        d.text((80, H - 84), "用数学看世界 · 越来越热，也越来越涝？",
               DIM, f_foot)
        img.save(OUT / f"sec_{n:02d}.png")

    files = sorted(OUT.glob("sec_*.png"))
    print(f"  生成 {len(files)} 张占位素材 → {OUT}")
    for f in files:
        print(f"    {f.name}  {f.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
