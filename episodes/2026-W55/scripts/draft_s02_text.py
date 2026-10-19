#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · 屏 02 新旁白的字幕切分与字数/时长预估（**只算不录**）。

口径（2026-10-18 第三次修正）：实拍那一帧是**落地态**，
对照点是**落地横向残余 +85.0 cm**；顶点 72.2 只作为过程出现在 y(t) 曲线里。
"""
import sys

sys.path.insert(0, r".\scripts")
from render_video import split_caption          # noqa: E402

TEXT = (
    "先说状态。实拍那一帧是落地之后：车已经在跑道上，横向离线。"
    "模型算出的落地横向残余，是正 85.0 厘米。"
    "实拍看着大约半个车身，按车宽 2.0 米算，1 米左右。"
    "85 对 100，同一个量级。"
    "还要交代一句：这台车在空中是一路往外扩的，扩到 95.8 厘米，落地才回收成 85.0。"
    "所以看着更歪，是过程里的事，不是结局。"
    "跨时刻比两个位置，就是比错了时刻。"
    "另外，视频里的偏移量不出精确值，角度、透视、车在画面中的位置，都会影响读数，"
    "只能说量级吻合。"
)

TEXT_DOUYIN = (
    "实拍那帧已落地，在跑道上。"
    "模型落地 85 厘米。"
    "实拍约半个车身，一个量级。"
    "空中扩到 96 厘米，落地收回 85 厘米。"
    "只比量级。"
)

SLOT = {"bili": (34.684, 46), "douyin": (9.770, 26)}
RATE = {"bili": 6.57, "douyin": 6.40}   # 字/秒（df=0.66 / 0.56 实测反推）

for tag, txt in (("bili", TEXT), ("douyin", TEXT_DOUYIN)):
    cap_sum, mx = SLOT[tag]
    caps = split_caption(txt, mx)
    print("=" * 70)
    print(f"  {tag}  正文 {len(txt)} 字  →  {len(caps)} 条字幕")
    print("=" * 70)
    for i, c in enumerate(caps, 1):
        print(f"  {i:02d} [{len(c):2d}] {c}")
    est = len(txt) / RATE[tag]
    k = cap_sum / est
    print(f"\n  预估自然时长 {est:.2f}s ⇒ k ≈ {k:.3f}"
          f"（槽位 Σ字幕 {cap_sum:.3f}s；允许 0.92–1.08）")
    if not (0.92 <= k <= 1.08):
        print(f"  [!] k 超出区间：稿子{'偏长' if k < 1 else '偏短'}，需要增删字数")
    print()
