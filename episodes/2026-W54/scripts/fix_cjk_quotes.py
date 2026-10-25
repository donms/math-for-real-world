#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W54 · 工具：把 Python 源码里**中文文本内部的 ASCII 双引号**换成「」。

## 为什么要写这个

本期在 f-string 里用 ASCII 双引号包裹中文，**已造成 8 次 `SyntaxError`**
（skill W52-8 / W53 已记过两次，仍复发）。

**⇒ 与其每次手改，不如写一个安全的重写器。**

## 判据（只改"明显是中文引号"的地方）

ASCII `"` 若**两侧都是中文/全角字符**，则几乎必然是打字时误用了英文引号
⇒ 换成 `「`（左）或 `」`（右）。

## ★ 安全约束

* **只在"两侧都是中文"时替换**，绝不碰真正的语法引号；
* 替换后**必须能通过 `ast.parse`**，否则**回滚**；
* 默认 dry-run，`--apply` 才写回。
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

CJK = r"\u4e00-\u9fff\u3000-\u303f\uff00-\uffef"
# 两侧都是中文/全角 ⇒ 这个引号是"文本内的引号"
PAT_L = re.compile(rf"(?<=[{CJK}])[\"](?=[{CJK}])")
PAT_R = re.compile(rf"(?<=[{CJK}])[\"](?=[{CJK}0-9A-Za-z])")


def fix_text(src: str) -> tuple[str, int]:
    n = 0
    out_lines = []
    for ln in src.split("\n"):
        # 跳过注释行（注释里无所谓）与三引号界定行
        if ln.lstrip().startswith("#") or len(ln) < 3:
            out_lines.append(ln)
            continue
        new = ln
        # 反复扫：每次把"两侧中文"的成对引号换成「」
        while True:
            m = PAT_L.search(new)
            if not m:
                break
            # 找它右侧最近的另一个"两侧中文"引号
            rest = new[m.end():]
            m2 = PAT_R.search(rest)
            if not m2:
                break
            i, j = m.start(), m.end() + m2.start()
            new = new[:i] + "「" + new[i + 1:j] + "」" + new[j + 1:]
            n += 1
        out_lines.append(new)
    return "\n".join(out_lines), n


def main() -> int:
    apply = "--apply" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("用法: fix_cjk_quotes.py <文件或目录> [--apply]")
        return 2
    targets: list[Path] = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            targets.extend(sorted(p.rglob("*.py")))
        else:
            targets.append(p)
    total = 0
    for p in targets:
        src = p.read_text(encoding="utf-8")
        try:
            ast.parse(src)
            print(f"  [skip] {p.name}：本来就能解析")
            continue
        except SyntaxError:
            pass
        new, n = fix_text(src)
        if n == 0:
            print(f"  [ -- ] {p.name}：没有可安全替换的引号")
            continue
        try:
            ast.parse(new)
        except SyntaxError as e:
            print(f"  [ !! ] {p.name}：替换后仍无法解析 ⇒ 回滚（{e.msg}）")
            continue
        print(f"  [ ok ] {p.name}：替换 {n} 处 ⇒ 现在能解析")
        total += n
        if apply:
            p.write_text(new, encoding="utf-8")
    print(f"\n  合计替换 {total} 处"
          f"{'（已写回）' if apply else '（dry-run，加 --apply 写回）'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
