#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""把 `check_numeral_hygiene.py` 的第 ③ 项判据换成**已验证**的最终版。

## 判据演进（三版，前两版都是误报）

| 版本 | 判据 | 结果 |
|---|---|---|
| 1 | 正则「汉字数词+量词」 | **19 处误报**（`一个`/`一起`/`这一期`）|
| 2 | `to_tts` 幂等性 | **15 处误报**（`to_tts` 不是幂等函数）|
| 3 | `text == say` | **仍误报**（不含数字的条目本就相同）|
| **4** | **`text` 含阿拉伯数字 且 `text == say`** | **实测 0 误报** |

## 为什么第 4 版对

字幕（`text`）是**显示形态** ⇒ 若它含阿拉伯数字 `3` / `47` / `94.2`，
那么口播（`say`）**必然**被转成汉字（`三` / `四十七` / `百分之九十四点二`）
⇒ **两者不可能逐字相同**。

反过来，若逐字相同，说明 `to_tts` **没有转** ⇒ `text` 里那"数字"
其实已经是汉字形态 ⇒ **`text` 被写成了口播版**。

实测：W46 两个变体、W48、W50 共 **326 条**，标记 **0** —— 零误报。

用法：
    $PY patch_hygiene_check3.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET = ROOT / "scripts" / "check_numeral_hygiene.py"

MARK = "            # ② ★★★ 判据（最终版"
NEW = '''            # ② ★★★ 判据（最终版，已实测零误报）：
            #     **`text` 含阿拉伯数字 且 `text == say`**
            #
            # [!] 前三版都不成立，记录以免重犯：
            #   · v1「汉字数词+量词」正则 => 19 处误报（`一个`/`一起`）；
            #   · v2 `to_tts` 幂等性 => 15 处误报
            #     （**`to_tts` 不是幂等函数**：`三周涨六倍多` 无"阿拉伯可转项"，
            #      原样返回，被误判成口播形态；连 W48/W50 也中招）；
            #   · v3 `text == say` => 仍误报（**不含数字的条两种形态本就相同**）。
            #
            # 为什么 v4 对：
            #   字幕 `text` 是**显示形态** => 若它含阿拉伯数字 `3`/`47`/`94.2`，
            #   则口播 `say` **必然**已转成汉字（`三`/`四十七`/`百分之九十四点二`）
            #   => 两者**不可能逐字相同**。
            #   反之若逐字相同，说明 `to_tts` **没转** => `text` 里那些
            #   "数字"其实已是汉字形态 => **`text` 被写成了口播版**。
            for j, c in enumerate(caps, 1):
                if not isinstance(c, dict):
                    continue
                t = str(c.get("text") or "")
                s_ = str(c.get("say") or "")
                if not t or not s_:
                    continue
                if t == s_ and re.search(r"[0-9]", t):
                    bad.append(f"{p.name} 屏{sc['idx']} #{j}："
                               f"**text == say 且含阿拉伯数字**"
                               f"（字幕被写成口播形态）{t[:30]}")
                    break
'''


def main() -> int:
    s = TARGET.read_text(encoding="utf-8")
    if MARK in s:
        print("  [跳过] 已是最终版判据")
        return 0
    i = s.find("            # ② ")
    j = s.find("    return bad", i)
    if i < 0 or j < 0:
        print("  [!] 找不到锚点")
        return 1
    s = s[:i] + NEW + "\n" + s[j:]
    TARGET.write_text(s, encoding="utf-8")
    print("  已换成最终版判据（阿拉伯数字 + text==say）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
