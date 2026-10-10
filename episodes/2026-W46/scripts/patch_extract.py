#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""共享检查器修补：`publish_check.extract_publish_block` 的**结构性缺陷**。

## 症状（W46 发布前实测）

知乎稿报「**正文未填（需放在 ``` 代码块里）**」，而它的正文**明明有 3000+ 字**。

## 根因

抽取器的逻辑是「按小标题定位，再在**下一个 `##`/`###` 之前**找第一个代码块」：

```python
nxt = re.search(r"^#{2,3}\s", tail, re.M)
seg = tail[: nxt.start()] if nxt else tail
```

而 W46 知乎稿的结构是：

    ## 二、正文
    ### 引子：一条涨得太快的曲线
    （正文是**散文**，不是代码块）

⇒ `## 二、正文` 之后**紧跟** `### 引子` ⇒ **`seg` 为空** ⇒ 永远找不到块。

## 为什么不能简单"往后多找几个块"

因为 B站/抖音稿里**后面还有口播脚本的代码块**，
放宽搜索范围会**抓到口播**（W43 的老问题）。

## 修法（分两步，保守优先）

1. **先按原逻辑**在"下一个标题之前"找 —— 这一条对
   `## 发布简介\n\n```…```\n\n---` 这种**紧凑结构**是对的；
2. **若 `seg` 为空**（正文紧跟子标题），**不放弃**，改为
   **从该标题起向后扫，取第一个"足够长"的代码块**，
   但**在遇到下一个同级或更高级标题中的"正文/文案/简介"类标题时停止**
   —— 即只跨过 `###` 子标题，不跨过另一个"正文类"小节。

> [!] 仍**不能覆盖**"正文是散文、完全没有代码块"的情况（如 W46 知乎稿）。
> 那种情况会在**修复后仍报"正文未填"**，需要**作者补一个代码块**
> —— 这是**有意的**：宁可报错，也不要静默去猜一段散文是正文。

用法：
    $PY patch_extract.py          # 应用
    $PY patch_extract.py --check  # 只看
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET = ROOT / "scripts" / "publish_check.py"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    s = TARGET.read_text(encoding="utf-8")
    if "_MULTI_BLOCK_FALLBACK" in s:
        print("  [跳过] 补丁已应用")
        return 0

    old = '''        nxt = re.search(r"^#{2,3}\\s", tail, re.M)
        seg = tail[: nxt.start()] if nxt else tail
        bm = re.search(r"```[a-zA-Z]*\\n(.*?)```", seg, re.S)
        if bm and count_cjk(bm.group(1)) > 40:
            body = bm.group(1)
            break'''
    new = '''        nxt = re.search(r"^#{2,3}\\s", tail, re.M)
        seg = tail[: nxt.start()] if nxt else tail
        bm = re.search(r"```[a-zA-Z]*\\n(.*?)```", seg, re.S)
        if bm and count_cjk(bm.group(1)) > 40:
            body = bm.group(1)
            break
        # ★★ _MULTI_BLOCK_FALLBACK（W46 补丁）
        #   若"下一个标题之前"没有代码块，**不要立刻放弃** ——
        #   常见于 `## 正文` 紧跟 `### 子标题` 的结构（子标题下才有块）。
        #   但**只跨过 `###` 子标题**；一旦遇到另一个"正文类"标题就停，
        #   否则会抓到后面的口播脚本（W43 踩过）。
        if not bm or count_cjk(bm.group(1)) <= 40:
            rest = md[hm.end():]
            stop = re.search(
                r"^#{2,3}[^\\n]*(?:正文|文案|简介|脚本|口播)[^\\n]*$",
                rest, re.M)
            span = rest[: stop.start()] if stop else rest
            for cand in re.findall(r"```[a-zA-Z]*\\n(.*?)```", span, re.S):
                if count_cjk(cand) > 40:
                    body = cand
                    break
            if body:
                break'''
    if old not in s:
        print("  [X] 找不到锚点 —— 请人工核对 publish_check.py")
        return 1

    s = s.replace(old, new, 1)
    if not args.check:
        TARGET.write_text(s, encoding="utf-8")
        print(f"  已给 {TARGET.name} 打补丁（_MULTI_BLOCK_FALLBACK）")
    else:
        print("  [--check] 锚点匹配成功，未写入")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
