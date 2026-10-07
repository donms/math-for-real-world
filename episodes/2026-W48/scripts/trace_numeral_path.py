#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W48 · 追查"中文数词被转成阿拉伯"的**错误产生路径**。

## 为什么要逐级打印

"1小部分组织"这类错误，可能产生在**四个**不同环节：

| 环节 | 函数 | 会做什么 |
|---|---|---|
| ① 切条 | `split_captions` | 把一屏正文切成字幕条 |
| ② 清洗 | `clean_caption` | **汉字数词 -> 阿拉伯**（罪魁） |
| ③ 还原 | `_nr_restore` | 阿拉伯 -> 汉字（我加的补丁） |
| ④ 口播 | `to_tts` | 阿拉伯 -> 汉字（发音用） |

只看到一个成品字符串，**无法判断是哪一环出错**。
所以本脚本**逐级打印**，把每一步的输入输出都摊开。

用法：
    $PY trace_numeral_path.py
    $PY trace_numeral_path.py --phrase "一小部分"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import tts_text                                                  # noqa: E402
from tts_text import clean_caption, to_tts                       # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phrase", default=None)
    args = ap.parse_args()

    print("=" * 90)
    print("  中文数词错误路径追查")
    print("=" * 90)

    # ── ㈠ 暴露 tts_text 里的补丁层 ──
    print("\n  ── tts_text 的补丁层 ──")
    for name in ("clean_caption", "to_tts"):
        f = getattr(tts_text, name)
        chain = []
        cur = f
        for _ in range(6):
            chain.append(getattr(cur, "__name__", type(cur).__name__))
            nxt = getattr(cur, "__wrapped__", None)
            if nxt is None:
                break
            cur = nxt
        print(f"    {name}: {' -> '.join(chain)}")
    print(f"    _nr_restore 存在: {hasattr(tts_text, '_nr_restore')}")
    print(f"    _NR_PHRASES 条数: "
          f"{len(getattr(tts_text, '_NR_PHRASES', []))}")
    print(f"    RESTORE_AS_HANZI 条数: "
          f"{len(getattr(tts_text, 'RESTORE_AS_HANZI', []))}")

    # ── ㈡ 逐级追踪 ──
    if args.phrase:
        phrases = [args.phrase]
    else:
        # 用户在成片里实际看到的错误串
        phrases = [
            "只能影响光源附近的一小部分组织",
            "蓝光一照，通道就打开",
            "我一开始用的是文献里的典型范围",
            "什么不用蒙特卡洛？下一屏讲",
            "它和解析解在两三个自由程处交叉",
        ]

    print("\n  ── 逐级追踪 ──")
    for ph in phrases:
        print(f"\n    原文：{ph}")
        # ① + ② 走真实管线：先切条，再逐条 clean_caption
        caps = tts_text.split_captions(ph) if hasattr(tts_text,
                                                      "split_captions") else [ph]
        print(f"      ① split_captions -> {len(caps)} 条: "
              f"{[c[:20] for c in caps]}")
        cleaned = [clean_caption(c) for c in caps]
        print(f"      ②+③ clean_caption -> {cleaned}")
        said = [to_tts(c) for c in caps]
        print(f"      ④ to_tts        -> {said}")
        # 单独看裸函数（绕过补丁）
        raw_clean = getattr(tts_text, "_NR_ORIG_CLEAN", None)
        if raw_clean is not None:
            print(f"      （裸 clean_caption，无还原层）-> "
                  f"{[raw_clean(c) for c in caps]}")

    # ── ㈢ 分环节定位：是谁把"一"变成"1"的 ──
    print("\n  ── 环节定位：裸 clean_caption vs 加还原层 ──")
    raw_clean = getattr(tts_text, "_NR_ORIG_CLEAN", None)
    probe = ["一小部分", "一照", "一开始", "一屏", "两三个", "一半", "一条",
             "11个", "21个", "7.44e-14"]
    print(f"    {'输入':<12}{'裸 clean_caption':<22}{'加还原层后':<22}")
    for t in probe:
        a = raw_clean(t) if raw_clean else "(无)"
        b = clean_caption(t)
        flag = "" if a == b else "   <- 被还原层改动"
        print(f"    {t:<12}{a:<22}{b:<22}{flag}")

    print("\n  ── 结论 ──")
    print("    ① `一X` 这种**词汇化的数词**被 CN_NUM 正则当成计数，转成了 `1X`；")
    print("    ② 还原层只能修**词表里列出的**搭配；")
    print("       ⇒ **词表之外的一律漏掉**（这就是逐条加词打不完地鼠的根因）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
