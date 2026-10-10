#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · **讲稿清洗**：一次把源文件修干净。

## 为什么要单独写这个

我先后写了 `fix_narration_digits.py`（阿拉伯→汉字）和 `tts_text.clean_caption()`
（汉字→阿拉伯），来回转换，**把源文件反复污染**：

| 污染 | 症状 | 后果 |
|---|---|---|
| **术语被拆** | `A H3N2` -> `A H三N二` | **内容损坏**，最严重 |
| 多余空格 | `流感三 周从七 起` | 读着别扭 |
| 混排 | `从七起涨到47 起` | 一眼假 |
| 数字算错 | `二百零九` -> `200九` | 内容错误 |

**根因**：我在**下游**反复打补丁，而没有把**源文件**定成干净的一种形式。

## 本脚本做的事（**幂等**，可反复跑）

1. **修术语**：`H三N二` -> `H3N2`（汉字数字还原回阿拉伯）；
2. **去空格**：`三 周` -> `三周`、`二零二六 年` -> `二零二六年`、
   `47 起` -> `47 起`（数字与汉字之间去空格）；
3. **统一数字形式**：按用户原则
   > 「口播是为了方便 TTS 读，字幕是为了方便人看，不需要一样，
   > 譬如 **2026 年**适合看，**二零二六年**适合读」

   **讲稿是给人看的** ⇒ 数字统一成**阿拉伯**（`2026年`、`47起`），
   口播版由 `to_tts()` 生成。

4. 保留 Markdown 结构（标题、表格、引用块不动）。

## 用法

    $PY clean_narration.py --check    # 只看会改什么
    $PY clean_narration.py --write    # 真改
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tts_text import clean_caption                          # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "内容" / "讲稿.md"

D = "零一二三四五六七八九"

# 术语里的汉字数字 -> 阿拉伯（**先修这个，否则内容损坏**）
TERM_FIX = [
    (re.compile(r"H([零一二三四五六七八九])N([零一二三四五六七八九])"),
     lambda m: f"H{D.index(m.group(1))}N{D.index(m.group(2))}"),
    (re.compile(r"A\s*H([零一二三四五六七八九])N([零一二三四五六七八九])"),
     lambda m: f"A H{D.index(m.group(1))}N{D.index(m.group(2))}"),
    (re.compile(r"R\s*零"), "R0"),
    (re.compile(r"R\s*零\s*t"), "R_t"),
    (re.compile(r"\bR\s*t\b"), "R_t"),
    (re.compile(r"\bILI\b"), "ILI"),
]

# 固定词：这些**在中文里用汉字数字才自然**，转换后要还原回来。
#
# 键 = "全阿拉伯转换后"的形式，值 = "人读更自然"的形式。
#
# ★ 判据（也是踩坑总结）：
# * **该还原**：`一下`、`一个`、`两段`、`一次`、`两个`、`两株`
#   —— 这些是**中文的构词成分**，写 `1下`、`2段` 会让人停顿；
# * **不该还原**：`2起`、`3周`、`7起`
#   —— 这些是**数据**（"第33周2起"），必须保持阿拉伯，
#     还原成"两起"反而把数据和文字混在一起。
RESTORE_AS_HANZI = [
    # 一
    ("1下", "一下"), ("1共", "一共"), ("1样", "一样"), ("1直", "一直"),
    ("1定", "一定"), ("1般", "一般"), ("1切", "一切"),
    ("1个", "一个"), ("1次", "一次"), ("1种", "一种"), ("1份", "一份"),
    ("1件", "一件"), ("1项", "一项"), ("1段", "一段"), ("1层", "一层"),
    ("1步", "一步"), ("1周", "一周"), ("1年", "一年"), ("1天", "一天"),
    ("同1", "同一"), ("1家独大", "一家独大"), ("1致", "一致"),
    ("第1步", "第一步"), ("第1层", "第一层"), ("第1屏", "第一屏"),
    ("第1个", "第一个"), ("第1次", "第一次"),
    # 两
    ("2法", "两法"), ("2次", "两次"), ("2个", "两个"), ("2种", "两种"),
    ("2周", "两周"), ("2层", "两层"), ("2株", "两株"), ("2者", "两者"),
    ("2侧", "两侧"), ("2端", "两端"), ("2面", "两面"),
    # 其它固定搭配
    ("9成5", "九成五"), ("8成", "八成"),
]


def fix_spaces(t: str) -> str:
    r"""去掉数字/汉字之间的多余空格。

    * `流感三 周` -> `流感三周`
    * `二零二六 年九 月` -> `二零二六年九月`
    * `47 起` -> `47 起`（数字与汉字**也**去空格）
    * 但 `A H3N2`、`R_t 是` 这类拉丁词之间的空格**保留**
    """
    # 汉字 + 空格 + 汉字
    t = re.sub(r"([\u4e00-\u9fff])\s+([\u4e00-\u9fff])", r"\1\2", t)
    # 数字 + 空格 + 汉字
    t = re.sub(r"(\d)\s+([\u4e00-\u9fff])", r"\1\2", t)
    # 汉字 + 空格 + 数字
    t = re.sub(r"([\u4e00-\u9fff])\s+(\d)", r"\1\2", t)
    return t


def clean_line(line: str) -> str:
    r"""把一行讲稿清成**干净的字幕形式**。

    ## ★ 实现上的关键取舍（避免"两层保护互相破坏"）

    我上一版在调用 `clean_caption()` **之前**就用占位符保护固定词，
    结果 `clean_caption()` **内部**也有自己的占位符与空格规则，
    两套机制互相破坏（实测报"保护占位符未还原"）。

    ⇒ 改成**串行、单层**：

    1. 先修术语（`H三N二` -> `H3N2`）；
    2. 交给 `clean_caption()` 全量转成阿拉伯（它是**幂等**的，
       已经是阿拉伯的文本再跑一次不变）；
    3. **最后**才把我希望保留汉字的固定词（`一下`、`两法`…）
       从阿拉伯**还原**回汉字。

    > 第 3 步之所以放最后，是因为"把 `1下` 还原成 `一下`"没有歧义，
    > 而"先保护再转换"会因为两层占位符冲突而失败。
    """
    t = line
    for pat, rep in TERM_FIX:
        t = pat.sub(rep, t)
    # ② 全量转阿拉伯（幂等）
    t = clean_caption(t)
    # ③ 再把固定词从阿拉伯还原成汉字
    for arab, han in RESTORE_AS_HANZI:
        t = t.replace(arab, han)
    # ④ 收尾去空格
    t = fix_spaces(t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


def is_body(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    return not s.startswith(("#", "|", ">", "```", "- ", "* ", "　"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    txt = CONTENT.read_text(encoding="utf-8")
    out: list[str] = []
    in_sc = False
    changed: list[tuple[str, str]] = []
    for ln in txt.splitlines():
        if re.match(r"^## 第.+?屏 · ", ln):
            in_sc = True
            out.append(ln)
            continue
        if ln.strip() == "---" or (ln.startswith("## ")
                                   and not re.match(r"^## 第.+?屏 · ", ln)):
            in_sc = False
            out.append(ln)
            continue
        if in_sc and is_body(ln):
            new = clean_line(ln)
            if new != ln:
                changed.append((ln, new))
            out.append(new)
        else:
            out.append(ln)

    print("=" * 90)
    print("  W46 · 讲稿清洗")
    print("=" * 90)
    print(f"  待改行数：{len(changed)}")
    for a, b in changed[:14]:
        print(f"\n  - {a[:88]}")
        print(f"  + {b[:88]}")
    if len(changed) > 14:
        print(f"\n  … 另有 {len(changed)-14} 行")
    if args.write:
        CONTENT.write_text("\n".join(out) + "\n", encoding="utf-8")
        print(f"\n  已写回 {CONTENT}")
    else:
        print("\n  （未写回；加 --write 生效）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
