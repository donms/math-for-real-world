#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""自证：标题判据能抓住空标题 —— **从实际渲染文件动手**，不再依赖第二个渲染器。

## 前两次失败

* 第一版判据 `max(亮字, 深字)`：把 navy 带本身当墨 ⇒ 22 屏全 86–97%，**恒过**。
* 第二版对照实验：用 `render_cards.py`（小红书卡片渲染器，字段是 `title`）
  去验证 `render_slides16x9.py`（B站，字段是 `head` 且带回退）的行为 ⇒
  两张卡**完全一样**，实验无效。

## 本脚本（可靠做法）

拿**真实的** `slide_01_cover.png`：
1. 量原始标题带的亮字占比；
2. **把标题带涂成纯 navy**（模拟"标题没渲出来"）；
3. 再量一次。

若两次差异显著且"涂掉后"低于阈值 ⇒ **判据有效**。

用法：
    $PY selftest_title_metric.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

EP = Path(__file__).resolve().parents[1]
SRC = EP / "publish" / "视频" / "素材16x9" / "slide_01_cover.png"
THR = 0.004


def light_ratio(arr: np.ndarray) -> float:
    band = arr[130:400, 90:1830]
    return float((band > 200).mean())


def main() -> int:
    im = np.asarray(Image.open(SRC).convert("L")).copy()
    before = light_ratio(im)

    # 模拟"标题没渲出来"：把标题带填成该区域的众数灰度（= 底色）
    blanked = im.copy()
    band = blanked[130:400, 90:1830]
    bg = int(np.bincount(band.ravel()).argmax())
    band[:] = bg
    after = light_ratio(blanked)

    print("=" * 76)
    print("  标题判据自证（从真实成片素材动手）")
    print("=" * 76)
    print(f"  源文件：{SRC.name}")
    print(f"  标题带底色灰度 = {bg}")
    print(f"  原始 亮字占比 = {before:>8.4%}")
    print(f"  涂掉标题后     = {after:>8.4%}")
    print(f"\n  阈值 {THR:.3%}")
    ok_before = before >= THR
    ok_after = after < THR
    print(f"    原始卡判 OK  : {ok_before}  （应 True）")
    print(f"    空标题判缺陷 : {ok_after}  （应 True）")
    verdict = "**有效**" if (ok_before and ok_after) else "**失效**"
    print(f"\n  ⇒ 判据{verdict}（{before:.2%} → {after:.2%}，"
          f"相差 {before - after:.2%}）")
    return 0 if (ok_before and ok_after) else 1


if __name__ == "__main__":
    raise SystemExit(main())
