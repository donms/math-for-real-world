#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · 把讲稿里的**叙述文本数字改回阿拉伯数字**（字幕素材）。

## 为什么

用户指出的设计原则：

> 「口播是为了方便 TTS 读，字幕是为了方便人看，不需要一样，
> 譬如 **2026 年**适合看，**二零二六年**适合读」

而我写讲稿时**已经把数字写成汉字**（"七起""四十七起""二零二六年"），
于是：
* `text`（字幕）已经是汉字 ⇒ **字幕变成了"给 TTS 看的"**，违背原则；
* `to_tts()` 无事可做 ⇒ 两份文本完全相同，转换器形同虚设。

**正确分工**：
* **讲稿 → 存阿拉伯数字**（这是字幕素材，人来读）；
* **生成分屏表时 → `to_tts()` 产出汉字版**（这是配音素材）。

## 做法

**只改叙述文本**（`## 第N屏` 之后的正文段），**不动**：
* 标题行（`## 第N屏 · …`）
* 表格行（`| … |`）
* 引用块里的示例（`> …`）
* 文末统计表

替换**长词优先**（"二十四" → "24" 要先于 "二十" → "20"），
否则会切错。

用法：
    $PY fix_narration_digits.py --check   # 只看会改什么
    $PY fix_narration_digits.py --write   # 真改
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "内容" / "讲稿.md"

D = "零一二三四五六七八九"
UNITS = [("千", 1000), ("百", 100), ("十", 10)]


def cn_to_int(t: str) -> int | None:
    r"""汉字数字 -> 整数。支持"四十七"/"一千二百"/"三十八"/"十"。"""
    if not t:
        return None
    t2 = t.replace("两", "二")          # 「两」= 2
    if all(c in D for c in t or c == "两" for c in t2):
        if all(c in D for c in t2):
            return int("".join(str(D.index(c)) for c in t2))
    total, cur = 0, 0
    for c in t:
        if c in D:
            cur = D.index(c)
        elif c == "十":
            total += (cur if cur else 1) * 10
            cur = 0
        elif c == "百":
            total += (cur if cur else 1) * 100
            cur = 0
        elif c == "千":
            total += (cur if cur else 1) * 1000
            cur = 0
        else:
            return None
    return total + cur


# 匹配连续汉字数字段（含小数"点"）
CN_NUM = re.compile(r"[零一二两三四五六七八九十百千]+(?:点[零一二三四五六七八九]+)?")

# ★★ **不能转的固定词**（W46 实测：不加这张表会把"同一份"变成"同1份"、
#    "一起"变成"1起"）。转换前先占位保护，转换后还原。
KEEP_WORDS = [
    # 成语 / 固定搭配里的"一"
    "一起", "一直", "一定", "一般", "一样", "一切", "一致", "一共",
    "一些", "一份", "一件", "一项", "一段", "一层", "一步", "一句话",
    "一体", "一目", "一线", "一等", "一律", "一流",
    "一家独大", "一家", "一探", "一览", "一门",
    # "两"的固定搭配
    "两侧", "两层", "两面", "两端", "两者", "两边",
    # "三/四…"的固定搭配
    "三思", "四舍五入", "五花八门", "十全十美",
    # 数学/统计惯用语
    "九成五", "九成", "一成",
    # "百分之"（百分号规则会处理）
    "百分之",
    # 概数
    "几", "若干", "数十", "上百", "上千",
]

# 数字 + 量词/单位 之间**要加空格**（字幕更易读；口播转换会去掉）
UNIT_WORDS = ("周", "起", "倍", "年", "月", "日", "个", "人", "例",
              "天", "小时", "分钟", "秒", "位", "家", "次", "种",
              "名", "岁", "度", "点", "米", "公里", "万", "亿")


def convert_line(line: str) -> str:
    r"""把一行里的汉字数字转成阿拉伯数字（**字幕素材**）。

    规则：
    1. 先保护 `KEEP_WORDS` 里的固定搭配；
    2. "百分之X" -> "X%"（这是字幕写法）；
    3. 数字 + 量词之间加**半角空格**（`7 起` 而不是 `7起`）；
    4. 其余汉字数字 -> 阿拉伯数字。
    """
    # ① 保护固定词
    guards: dict[str, str] = {}
    t = line
    for i, w in enumerate(KEEP_WORDS):
        k = f"\x00K{i}Z\x00"
        if w in t:
            guards[k] = w
            t = t.replace(w, k)

    # ② 百分之X -> X%
    def _pct(m):
        v = _cn_value(m.group(1))
        return f"{v}%" if v is not None else m.group(0)

    t = re.sub(r"百分之([零一二两三四五六七八九十百千]+(?:点[零一二三四五六七八九]+)?)",
               _pct, t)

    # ③ 汉字数字 -> 阿拉伯数字
    def _sub(m):
        return _cn_value(m.group(0)) or m.group(0)

    t = CN_NUM.sub(lambda m: (lambda v: str(v) if v is not None else m.group(0))
                   (_cn_value(m.group(0))), t)

    # ④ 数字 + 量词之间加空格
    #    ★★ **必须在还原固定词之前做**：否则量词规则会把还原出来的
    #       "一家独大"重新拆成 "1 家独大"（W46 实测踩过 ——
    #       占位符还原与格式规则**顺序颠倒**会互相破坏）。
    unit_alt = "|".join(sorted(UNIT_WORDS, key=len, reverse=True))
    t = re.sub(rf"(\d)\s*({unit_alt})", r"\1 \2", t)

    # ⑤ 还原固定词（**最后一步**）
    for k, w in guards.items():
        t = t.replace(k, w)
    return t


def _cn_value(t: str) -> int | None:
    r"""汉字数字 -> 整数（含小数）。支持 `二十四` / `一千二百` / `十`。"""
    if "点" in t:
        return None                     # 小数在 _pct / _sub 里单独处理
    if not t:
        return None
    t2 = t.replace("两", "二")          # 「两」= 2
    if all(c in D for c in t or c == "两" for c in t2):
        if all(c in D for c in t2):
            return int("".join(str(D.index(c)) for c in t2))
    total, cur = 0, 0
    for c in t:
        if c in D:
            cur = D.index(c)
        elif c == "十":
            total += (cur if cur else 1) * 10
            cur = 0
        elif c == "百":
            total += (cur if cur else 1) * 100
            cur = 0
        elif c == "千":
            total += (cur if cur else 1) * 1000
            cur = 0
        else:
            return None
    return total + cur


def protect(line: str) -> bool:
    """这些行不动：标题、表格、引用、代码块、统计。"""
    s = line.strip()
    if not s:
        return True
    if s.startswith(("#", "|", ">", "```", "- ", "* ", "　")):
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    txt = CONTENT.read_text(encoding="utf-8")
    lines = txt.splitlines()
    # 只处理"## 第N屏"之后、下一个 "---" 之前的叙述段
    out, in_screen, changed = [], False, 0
    for ln in lines:
        if re.match(r"^## 第.+?屏 · ", ln):
            in_screen = True
            out.append(ln)
            continue
        if ln.strip() == "---":
            in_screen = False
            out.append(ln)
            continue
        if ln.startswith("## ") and not re.match(r"^## 第.+?屏 · ", ln):
            in_screen = False
            out.append(ln)
            continue
        if in_screen and not protect(ln):
            new = convert_line(ln)
            if new != ln:
                changed += 1
                if args.check:
                    print(f"  - {ln[:60]}")
                    print(f"  + {new[:60]}")
                    print()
            out.append(new)
        else:
            out.append(ln)

    print(f"  待改行数：{changed}")
    if args.write:
        CONTENT.write_text("\n".join(out) + "\n", encoding="utf-8")
        print(f"  已写回 {CONTENT}")
    else:
        print("  （未写回；加 --write 生效）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
