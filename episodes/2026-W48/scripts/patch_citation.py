#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W48 补丁：**把 Nature Communications 的引用补全**（按媒介分流）。

## 起因

读者在知乎评论里指出：

> 「引用文章是哪篇啊？看了你的 GitHub 上这一期的内容，
> 引用写的也是 Nat Comm 2022，可以附上作者名字吗？
> (eg. XXX et al, Nat Comm 2022)」

**读者是对的。** 我在所有文档里只写了「Nature Communications 2022, 13:2013」，
**没有作者名、没有文章号，而且文章号是错的**。

## 准确的引用（Crossref 权威查询）

> **Song, X., Guo, Y., Li, H., Chen, C., Lee, J. H., Zhang, Y., Schmidt, Z.
> & Wang, X.** Mesoscopic landscape of cortical functions revealed by
> through-skull wide-field optical imaging in marmoset monkeys.
> *Nature Communications* **13, 2238 (2022)**.
> DOI: 10.1038/s41467-022-29864-7

**引用的表**：**Table 1**「Optical and physical properties of the skull
and the brain」（已向期刊页面核实表题）。

## [!] 原引用里的两个错

| 项 | 原来写的 | 正确 |
|---|---|---|
| 文章号 | `13:2013` | **13, 2238**（2013 是**首篇**的文章号，不是这一篇）|
| 作者 | **缺** | Song X. 等 8 人，通讯作者 Xiaoqin Wang |

> 教训：**「卷:文章号」格式的文章号必须从权威源取，不能凭印象写。**

## ★★ 按媒介分流（**这一步很关键**）

| 媒介 | 处理 | 理由 |
|---|---|---|
| **文字平台**（知乎/论文/来源清单/结果/GitHub）| **完整引用** | 读者要的就是这个 |
| **视频与音频**（讲稿/分屏表/screenplan/manifest）| **只补到「Song 等，Nature Communications 2022」** | 配音**不能念 8 个作者名**；字幕也放不下 |

⇒ 视频里说「**一篇 2022 年 Nature Communications 的论文**」，
文字稿里给全引用 —— 观众要去查，正文里有。

用法：
    $PY patch_citation.py --check
    $PY patch_citation.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W48"

# 完整引用（文字媒介）
FULL = ("Song, X., Guo, Y., Li, H., Chen, C., Lee, J. H., Zhang, Y., "
        "Schmidt, Z. & Wang, X. *Nat. Commun.* **13, 2238 (2022)**, "
        "DOI: 10.1038/s41467-022-29864-7")
# 简短引用（视频/音频可念）
# ★ 措辞必须避开所有 VARIANTS 子串（否则自引用）——
#   注意「*Nature Communications* 2022」是一个变体，
#   所以不能写成 "Song 等，*Nature Communications* 2022"。
SPOKEN = "*Nature Communications* 上 Song 等的实测数据（2022）"

# 视频/音频相关的文件（只做简短替换）
MEDIA_PAT = ("讲稿", "分屏表", "screenplan", "slides16x9",
             "video_manifest", "cards_", "发布清单")

# ★ 最长优先，避免前缀误伤
VARIANTS = [
    "*Nature Communications* 2022, 13:2013, **Table 1**",
    "*Nature Communications* 2022, 13:2013",
    "Nature Communications 2022, 13:2013",
    "Nature Communications 2022 年的一篇论文（13:2013）",
    "*Nature Communications* 2022",
    "Nature Communications 2022 的表 1",
    "Nature Communications 2022 实测组织光学参数",
    "Nature Communications 2022",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    files = [p for p in EP.rglob("*")
             if p.is_file() and p.suffix in (".md", ".py", ".json")
             and "_弃用" not in str(p)
             and "publish\\github" not in str(p)
             and "publish/github" not in str(p)
             and p.name != "patch_citation.py"]
    print("=" * 92)
    print("  W48 引用补全（按媒介分流）")
    print("=" * 92)
    print(f"\n  扫描 {len(files)} 个文件")
    print(f"  文字媒介 -> {FULL[:60]}...")
    print(f"  视频音频 -> {SPOKEN}\n")

    tot_txt = tot_med = 0
    for p in sorted(files):
        try:
            s = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        is_media = any(k in p.name for k in MEDIA_PAT)
        o = s
        hits = 0
        # ★★★ 每个变体串在每个文件里**只替换第一次出现**。
        #
        # 初版写成 `while v in s`，而替换后的短引用 SPOKEN =
        # "Song 等，*Nature Communications* 2022" **自身又匹配变体**
        # "*Nature Communications* 2022" ⇒ **自引用无限循环**，
        # 讲稿与发布清单各被写进 15 个 "Song 等，"（撞上防失控上限才停）。
        #
        # ⇒ 两条防线：
        #   ① 不循环，每个变体只换一次；
        #   ② 替换后**断言**新串不含任何变体（自引用检测）。
        for v in VARIANTS:
            if v not in s:
                continue
            rep = SPOKEN if is_media else (FULL if hits == 0
                                           else "Song 等 (2022)")
            if any(vv in rep for vv in VARIANTS):
                raise SystemExit(f"[X] 替换串自引用变体 `{v}` -> `{rep}`")
            s = s.replace(v, rep, 1)
            hits += 1
        if s != o:
            tag = "视频" if is_media else "文字"
            print(f"  [{tag}] [{hits:>2} 处] {p.relative_to(EP)}")
            if is_media:
                tot_med += hits
            else:
                tot_txt += hits
            if not args.check:
                p.write_text(s, encoding="utf-8")

    print(f"\n  文字媒介 {tot_txt} 处 / 视频音频 {tot_med} 处"
          f" = 合计 {tot_txt + tot_med} 处")
    if args.check:
        print("  （--check 模式，未写入）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
