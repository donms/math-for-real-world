#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""核对**发布清单**里的实际内容 —— 交付前最后一道检查。

## 为什么要单独查「发布清单」

`publish_check.py` 校验的是 `内容/*.md` 源文件，
但用户实际**照着复制**的是 `publish/发布清单.md`（它由脚本生成）。
两者可能不同步 —— 实测踩过：改了 `内容/小红书.md` 之后
没重跑 publish_check，清单里还是旧正文。

另外查两件源文件校验**查不出**的事：

1. **markdown 标记残留**：小红书/B站 都不解析 markdown，
   `**加粗**` 会原样显示成星号（与幻灯片踩过的是同一个坑）；
2. **过时引用**：B站 稿里若写着旧视频文件名/旧时长/旧时间轴，
   发布后观众会点到错误的章节。

用法：
    $PY verify_publish_list.py --ep 2026-W40
"""
from __future__ import annotations

import argparse
import pathlib
import re

FENCE = "`" * 3


def section_body(md: str, plat: str) -> str | None:
    m = re.search(rf"^###\s*{plat}.*?$", md, re.M)
    if not m:
        return None
    tail = md[m.end():]
    nxt = re.search(r"^###\s", tail, re.M)
    seg = tail[: nxt.start()] if nxt else tail
    b = re.search(rf"{FENCE}[a-zA-Z]*\n(.*?){FENCE}", seg, re.S)
    return b.group(1).strip() if b else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", default="2026-W40")
    args = ap.parse_args()
    ep = pathlib.Path(r".\episodes") / args.ep
    lst = ep / "publish" / "发布清单.md"
    if not lst.exists():
        print(f"  [!] 缺 {lst}")
        return 2

    md = lst.read_text(encoding="utf-8")
    src_mtime = max((ep / "内容" / f).stat().st_mtime
                    for f in ("小红书.md", "B站.md", "知乎.md", "抖音.md"))
    stale = lst.stat().st_mtime < src_mtime
    print(f"  发布清单: {lst.name}")
    print(f"  ⚠️ 清单比内容源旧（需重跑 publish_check.py）" if stale
          else "  ✅ 清单比内容源新")
    print()

    problems = 0
    # ⚠️ 哪些平台**不解析** markdown：小红书/B站/抖音 都是纯文本输入框，
    #    `**加粗**` 会原样显示成星号。**知乎原生支持 markdown**，故不检查它。
    NO_MD = ("小红书", "B站", "抖音")
    for plat in ("知乎", "小红书", "B站", "抖音"):
        body = section_body(md, plat)
        if body is None:
            print(f"  [!] 清单里找不到「{plat}」一节")
            problems += 1
            continue
        n = len(re.sub(r"\s", "", body))
        line = f"  {plat:<5} {n:>5} 字符"
        if plat in NO_MD and "**" in body:
            line += "   ❌ 含 ** 标记（该平台不解析，会显示成星号）"
            problems += 1
        elif plat == "知乎":
            line += "   ✅（知乎支持 markdown，允许 ** 标记）"
        else:
            line += "   ✅ 无 markdown 标记"
        print(line)

    # B站 专查：旧视频文件名 / 旧时长
    b = section_body(md, "B站") or ""
    if "lecture.mp4" in b or "12.21" in b:
        print("  ❌ B站 稿引用了**旧视频**（lecture.mp4 / 12.21 分钟）")
        problems += 1
    else:
        print("  ✅ B站 稿未引用旧视频")

    print()
    print(f"  {'✅ 清单内容正常' if not problems else f'❌ {problems} 处问题'}")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
