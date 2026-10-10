#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""诊断：`clean_caption` 里的「汉字 -> 阿拉伯」是谁装上的。

## 背景

W48 已把数字转换改成**单向**（讲稿=字幕形态，只有 `to_tts` 做 阿拉伯->汉字），
`clean_caption` 应当**只清标点**。

但 W46 实测：

    输入: 先分清楚两个概念，它们经常被混为一谈。
    clean_caption -> 先分清楚2个概念，它们经常被混为1谈。   <-- 又转了

⇒ 说明 `scripts/tts_text.py` 里**仍有一个「汉字->阿拉伯」的实现**，
   而且它在 `clean_caption` 之后执行（或就是 `clean_caption` 本身）。

## 本脚本要查清

1. `clean_caption` 当前绑定的**函数对象**是哪个（`__module__` / `__qualname__`）；
2. 该函数的**源码**里有没有 CN_NUM 类转换；
3. `tts_text` 模块里所有**patch 块**的安装顺序与最终生效者；
4. 现场复现最小输入，逐个 patch 关掉看是哪个在起作用。

用法：
    $PY diag_clean_caption.py
"""
from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TT = ROOT / "scripts" / "tts_text.py"
sys.path.insert(0, str(ROOT / "scripts"))

import tts_text                                                   # noqa: E402

PROBE = "先分清楚两个概念，它们经常被混为一谈。"


def main() -> int:
    print("=" * 92)
    print("  诊断：clean_caption 里谁在做「汉字->阿拉伯」")
    print("=" * 92)

    f = tts_text.clean_caption
    print(f"\n  [1] 当前 clean_caption")
    print(f"      {f.__module__}.{f.__qualname__}")
    try:
        src = inspect.getsource(f)
        print(f"      源码 {len(src.splitlines())} 行；含 CN 转换关键字：")
        for kw in ("CN_NUM", "汉字", "阿拉伯", "cn2num", "digits",
                   "零一二三四五六七八九十"):
            n = src.count(kw)
            if n:
                print(f"         `{kw}` x{n}")
        # 打印函数体前若干行
        print("      ---- 源码前 30 行 ----")
        for ln in src.splitlines()[:30]:
            print(f"      {ln}")
    except (OSError, TypeError) as e:
        print(f"      [!] 取不到源码：{e}")

    print(f"\n  [2] 实测")
    print(f"      输入      : {PROBE}")
    print(f"      clean     : {tts_text.clean_caption(PROBE)}")
    print(f"      to_tts    : {tts_text.to_tts(PROBE)}")

    print(f"\n  [3] tts_text.py 里的 patch 块（按出现顺序）")
    s = TT.read_text(encoding="utf-8")
    print(f"      文件 {len(s.splitlines())} 行")
    for m in re.finditer(r"(?m)^#\s*={3,}.*$|^#\s*[★\s]*([A-Z_]{4,})", s):
        ln = s[:m.start()].count("\n") + 1
        line = s.splitlines()[ln - 1].strip()
        if line:
            print(f"      L{ln}: {line[:88]}")

    print(f"\n  [4] 含「汉字数字表」的行")
    for m in re.finditer(r"[\"']零[\"']|[\"']一[\"']|零一二三四五六七八九", s):
        ln = s[:m.start()].count("\n") + 1
        line = s.splitlines()[ln - 1].strip()
        print(f"      L{ln}: {line[:96]}")

    print(f"\n  [5] 定义/重定义 clean_caption 的位置")
    for m in re.finditer(r"(?m)^\s*def clean_caption|clean_caption\s*=", s):
        ln = s[:m.start()].count("\n") + 1
        print(f"      L{ln}: {s.splitlines()[ln - 1].strip()[:96]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
