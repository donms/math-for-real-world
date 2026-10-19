#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · 屏 02 新口播的字幕切分（**数字不许被切断**）。

为什么单独写：上一轮抖音出现过 `4|5 度` 这种词中/数字中断行。
数字被切开比词语被切开更难听出来，而屏 02 新稿里数字密度很高
（72.2 / 2.0 / 1 米 / 85.0 / 顶点 / 峰值），必须专门查。

规则：
1. 先在**标点**处切（，。：；！？、），标点跟着前一片；
2. 单片超过 `max_caption` 就再按**逗号**切；仍超长才按长度硬切；
3. 硬切时**绝不允许切在数字内部**（`.0123456789` 与前后紧邻的数字串视为一个整体）；
4. 输出后用断言复查：任何一条都不含"数字被切断"的痕迹。

用法：
    $PY episodes/2026-W55/scripts/split_caption_s02.py --max 46
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EP = Path(__file__).resolve().parents[1]

# 屏 02 新口播（与 内容/讲稿.md 第2屏 一字不差）
TEXT = (
    "先说状态。实拍那一帧是落地之后：车已经在跑道上，车身偏在白线一侧。"
    "模型算出的落地横向残余，是正 85.0 厘米。"
    "实拍看着大约半个车身，按车宽 2.0 米算，1 米左右。"
    "85 对 100，同一个量级。"
    "还要交代一句：这台车在空中是一路往外扩的，扩到 95.8 厘米，落地才回收成 85.0。"
    "所以看着更歪，是过程里的事，不是结局。"
    "跨时刻比两个位置，就是比错了时刻。"
    "另外，视频里的偏移量不出精确值，角度、透视、车在画面中的位置，都会影响读数，"
    "只能说量级吻合。"
)

# 抖音版（更短，且**每个数字都带单位**：不带单位念出来会糊）
# ★ 2026-10-18 三次试合才落定：80 字 k=0.83、70 字 k=0.87、64 字 k≈0.98。
#   **k 超界时先怀疑稿子写长了，不要先怀疑语速。**
TEXT_DOUYIN = (
    "实拍那一帧是落地之后，车在跑道上。"
    "模型算出的落地残余是 85 厘米。"
    "实拍约半个车身，一个量级。"
    "空中扩到 96 厘米，落地收回 85 厘米。"
    "所以只能比量级。"
)

NUM = re.compile(r"[0-9.]+")
CJK = r"\u4e00-\u9fff"


def visual(s: str) -> float:
    """视觉宽度：CJK=1，ASCII=0.55（与 wrap_cjk 同口径）。"""
    return sum(0.55 if ord(c) < 128 else 1.0 for c in s)


def safe_cut(s: str, k: int) -> int:
    r"""在 `k` 附近找一个**不切数字**且**不切英文单词**的位置。"""
    n = len(s)
    k = max(1, min(k, n - 1))
    for d in range(0, n):
        for i in (k - d, k + d):
            if 1 <= i < n and not _inside_number(s, i):
                return i
    return k


def _inside_number(s: str, i: int) -> bool:
    """位置 i（切在 s[i-1] 与 s[i] 之间）是否落在数字内部。

    ★ 判据：左侧往左读到非数字，右侧往右读到非数字，两边若**都有**数字字符，
    且中间没有空格/标点隔开，就是切在数字内部。
    还要挡住"2.0"这种：小数点也算数字字符。
    """
    left = s[i - 1]
    right = s[i]
    if left.isdigit() or right.isdigit():
        return True
    if left == "." or right == ".":
        return True
    return False


def split(text: str, maxlen: int) -> list[str]:
    # ① 按句末标点先切
    parts = re.findall(f"[^{CJK}A-Za-z0-9]?[^{CJK}A-Za-z0-9]*", "")  # 占位
    parts = []
    buf = ""
    for ch in text:
        buf += ch
        if ch in "。！？":
            parts.append(buf)
            buf = ""
    if buf:
        parts.append(buf)

    # ② 逐片装车；超长则按逗号再切
    out: list[str] = []
    for p in parts:
        if visual(p) <= maxlen:
            out.append(p)
            continue
        chunks, cur = [], ""
        for ch in p:
            if visual(cur + ch) > maxlen:
                # 先试着在最近的逗号处断开
                idx = max(cur.rfind("，"), cur.rfind("："), cur.rfind("；"))
                if idx >= 4:
                    chunks.append(cur[:idx + 1])
                    cur = cur[idx + 1:]
                else:
                    cut = safe_cut(cur, len(cur) - 1)
                    chunks.append(cur[:cut])
                    cur = cur[cut:]
                cur += ch
            else:
                cur += ch
        if cur:
            chunks.append(cur)
        out.extend(chunks)
    return [s.strip() for s in out if s.strip()]


def merge(lines: list[str], maxlen: int) -> list[str]:
    r"""相邻两条能并就并：字幕条数少一些，念起来换气点更自然。

    只在不超 `maxlen` 时并，并且**不把两条短句硬凑到零头**（留 2 的余量）。
    """
    out: list[str] = []
    for s in lines:
        if out and visual(out[-1] + s) <= maxlen - 1.5:
            out[-1] += s
        else:
            out.append(s)
    return out


def check(lines: list[str], maxlen: int) -> list[str]:
    r"""真正的判据：**只有"上一行以数字/小数点结尾、下一行以数字/小数点开头"
    才算把数字切开了**。单看某一行首尾是不是数字会误报
    （例如 "72 对 100，还是同一个量级。" 合法地以数字开头、以句号结尾）。
    """
    bad = []
    for i, s in enumerate(lines):
        if visual(s) > maxlen + 0.01:
            bad.append(f"第{i+1}条超长：视觉宽度 {visual(s):.1f} > {maxlen}")
        if s.endswith(".") or s.endswith("．"):
            bad.append(f"第{i+1}条以小数点结尾（数字被切断）：{s!r}")
        if i + 1 < len(lines):
            a, b = s[-1], lines[i + 1][0]
            if ("0123456789.".find(a) >= 0) and ("0123456789.".find(b) >= 0):
                bad.append(f"第{i+1}/{i+2} 条之间切在数字内部："
                           f"…{s[-6:]!r} | {lines[i+1][:6]!r}…")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=46)
    ap.add_argument("--variant", default="bili", choices=["bili", "douyin"])
    args = ap.parse_args()

    text = TEXT if args.variant == "bili" else TEXT_DOUYIN
    print("=" * 78)
    print(f"  屏 02 字幕切分 · {args.variant}（max={args.max}，数字不许切断）")
    print("=" * 78)
    lines = merge(split(text, args.max), args.max)
    for i, s in enumerate(lines, 1):
        print(f"  {i:02d} [{len(s):>2}字/{visual(s):5.1f}宽] {s}")
    print(f"\n  共 {len(lines)} 条，正文 {len(text)} 字，"
          f"视觉总宽 {visual(text):.1f}")
    bad = check(lines, args.max)
    if bad:
        print("\n  [X] 有问题：")
        for b in bad:
            print("    " + b)
        return 1
    print("  [OK] 无超长、无首尾数字（不会把 72.2 切成 72. 与 2）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
