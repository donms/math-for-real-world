#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W54 · 工具：把 Python 源码里**中文文本内部的 ASCII 双引号**成对换成「」。

## 与 `fix_cjk_quotes.py` 的分工

* `fix_cjk_quotes.py`：**只处理"整行本来就无法解析"的文件**，
  用"两侧都是中文"的判据替换，带 `ast.parse` 回滚；
* **本脚本**：**逐行处理**，用"**先出现的当左引号、后出现的当右引号**"
  的配对策略 —— 能处理"一行里有多对引号"的情况
  （那是 `fix_cjk_quotes.py` 搞不定的，例如 Markdown 表格行）。

## 安全约束（**两条**）

1. 只在**该行本身就是 Python 语法错误来源**时才改（即先确认整文件解析失败）；
2. 改完**必须 `ast.parse` 通过**，否则**整文件回滚**。
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

# 中文/全角字符类（用来看"引号两侧是不是中文"）
CJK = r"\u3000-\u303f\u4e00-\u9fff\uff00-\uffef"
# 行内成对的 ASCII 引号：前一个左侧是中文，后一个右侧是中文或中文标点
PAIR = re.compile(rf'(?<=[{CJK}])"(?P<mid>[^"]*)"(?=[{CJK}])')


def fix_line(ln: str) -> tuple[str, int]:
    r"""把一行里"被中文包围的成对 ASCII 引号"换成「」。

    ★ 用**最小匹配** `[^"]*` 保证不会跨引号乱配；
      若一行里有 2 对（如表格行），`sub` 会逐对处理。
    """
    n = 0

    def rep(m: re.Match) -> str:
        nonlocal n
        n += 1
        return "「" + m.group("mid") + "」"

    return PAIR.sub(rep, ln), n


def main() -> int:
    apply = "--apply" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("用法: fix_cjk_quotes2.py <文件...> [--apply]")
        return 2
    total = 0
    for a in args:
        p = Path(a)
        src = p.read_text(encoding="utf-8")
        try:
            ast.parse(src)
            print(f"  [skip] {p.name}：本来就能解析")
            continue
        except SyntaxError:
            pass
        out, n = [], 0
        for ln in src.split("\n"):
            new, k = fix_line(ln)
            out.append(new)
            n += k
        if n == 0:
            print(f"  [ -- ] {p.name}：没有可配对的中文引号")
            continue
        cand = "\n".join(out)
        try:
            ast.parse(cand)
        except SyntaxError as e:
            print(f"  [ !! ] {p.name}：替换 {n} 处后仍无法解析 ⇒ 回滚"
                  f"（L{e.lineno}: {e.msg}）")
            # 打印仍报错的行，便于人工处理
            for i, ln in enumerate(cand.split("\n"), 1):
                if i == e.lineno:
                    print(f"         L{i}: {ln.strip()[:100]}")
            continue
        print(f"  [ ok ] {p.name}：配对替换 {n} 处 ⇒ 现在能解析")
        total += n
        if apply:
            p.write_text(cand, encoding="utf-8")
    print(f"\n  合计 {total} 处"
          f"{'（已写回）' if apply else '（dry-run，加 --apply 写回）'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
