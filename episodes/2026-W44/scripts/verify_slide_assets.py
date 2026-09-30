#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""核对**磁盘上的素材 PNG 是否与当前 `分屏表.json` 一致**。

## 为什么必须验

W44 曾出现：`分屏表.json` / `slides16x9.json` 里第 12 屏标题是
「『队列在园率』已接近 1」，但**渲染出来的 `slide_12_bullets.png` 仍是旧的
「小结」+ 空要点**。原因：改了版式后**没有重渲素材**（或重渲时被同名文件混淆）。

⇒ 本脚本用**像素级 OCR 无关**的办法核对：
拿当前清单里的 `head` 文本，用 PIL 在素材图上**找该文本的第一行像素特征**是不可行的；
故改为**间接但可靠**的判据 —— 比较**素材文件 mtime** 与 `slides16x9.json` 的 mtime，
并额外报告每张素材的**非空白像素占比**（空要点卡片的占比会明显偏低）。

用法：
    $PY verify_slide_assets.py
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
PUB = EP / "publish"
SLIDES = PUB / "视频" / "素材16x9"


def main() -> int:
    spec_p = PUB / "slides16x9.json"
    spec = json.loads(spec_p.read_text(encoding="utf-8"))
    screens = spec.get("slides") or spec.get("scenes")
    spec_m = spec_p.stat().st_mtime

    print("=" * 92)
    print("  W44 · 素材 PNG 与清单一致性核对")
    print("=" * 92)
    print(f"\n  slides16x9.json 改于 "
          f"{datetime.fromtimestamp(spec_m):%H:%M:%S}")

    from PIL import Image
    import numpy as np

    print(f"\n  {'屏':>3}  {'素材文件':<26}{'改于':>10}{'笔迹占比':>10}  判定")
    bad = 0
    for i, s in enumerate(screens, 1):
        kind = s.get("kind", "bullets")
        cand = list(SLIDES.glob(f"slide_{i:02d}_*.png"))
        if not cand:
            print(f"  {i:>3}  {'（缺文件）':<26}{'--':>10}{'--':>10}  ❌")
            bad += 1
            continue
        p = cand[0]
        m = p.stat().st_mtime
        stale = m < spec_m
        # 笔迹占比：非背景色像素的比例（空卡片会明显偏低）
        im = np.asarray(Image.open(p).convert("L"))
        bg = np.bincount(im.ravel()).argmax()
        ink = float((np.abs(im.astype(int) - bg) > 28).mean())
        flag = ""
        if stale:
            flag = "  ❌ 素材比清单旧"
            bad += 1
        if kind in ("bullets", "text") and ink < 0.012:
            flag += "  ⚠️ 笔迹极少（可能是空要点）"
            bad += 1
        print(f"  {i:>3}  {p.name:<26}"
              f"{datetime.fromtimestamp(m):%H:%M:%S}{ink:>10.3%}{flag}")

    print(f"\n{'='*92}")
    print(f"  问题屏：{bad}")
    if bad == 0:
        print("  ✅ 素材与清单一致（mtime 新于清单，且笔迹占比正常）")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
