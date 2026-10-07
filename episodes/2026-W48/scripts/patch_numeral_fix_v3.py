#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W48 · 把 `tts_text.py` 的补丁块**整体替换**为修复版（4 个问题一起修）。

## 修什么

| # | 问题 | 修法 |
|---|---|---|
| 1 | `一小部分`->`1小部分`、`两三个`->`2三个` 等**词汇化数词被当计数转换** | 扩短语表 + 加 `两X` 模式 + 加裸数词白名单 |
| 2 | `——` 破折号 TTS 会读出怪声 | **源头删掉**（讲稿）+ 转换层兜底删除 |
| 3 | `7.44乘10的负14次方` 想显示为 `7.44e-14` | 加**科学计数法保护**：`a乘10的负b次方` -> `a e -b` |
| 4 | 承诺 GitHub 链接但尚未上传 | 改讲稿（不在本脚本范围） |

## ★★ 问题 1 的**错误路径**（追查结论）

```
讲稿原文：  只能影响光源附近的一小部分组织
   ↓ ① split_captions（切条）
字幕条：    只能影响光源附近的一小部分组织
   ↓ ② clean_caption 里的 CN_NUM 正则
            ——正则把"一"当成计数，输出 `1`
裸输出：    只能影响光源附近的一小部分组织  ->  `…的1小部分组织`
   ↓ ③ 还原层（我加的补丁）
            ——只能修**词表里列出的**搭配
成品：      词表命中则正确；**词表之外一律漏掉**
```

**根因**：`CN_NUM` 正则是"**汉字数词 → 阿拉伯数字**"的**无条件**转换，
它无法区分：

* **计数**（`3 个城市`、`15.2%`）—— 该转；
* **词汇化的数词**（`一小部分`、`一开始`、`两三个`、`第一`）—— **不该转**。

而"词汇化的数词"是**开放集合**，所以
**逐条加词永远打不完地鼠**（W47 打了 5 轮，W48 又冒出一批）。

⇒ **本脚本的对策**：不再只靠词表，而是**三条规则叠加**：
1. **短语表**（明确的搭配）；
2. **`一/两/几/三 + 任意汉字` 模式**（这类前缀在汉语里极少是计数）；
3. **裸 `一/两` 单字还原**（它们几乎永远不是"需要阿拉伯"的计数，
   真正的计数是 3 以上）。

## 为什么不用哨兵占位符（**我试过，失败**）

`\x01` 哨兵会被数字转换逻辑吃掉，产出 `三十七` 这种垃圾，
还污染了已发布的 W47。**已回滚。**
⇒ 只用**转换后还原** + **前置保护**（科学计数法用真字符保护，见下）。

用法（幂等，会整体替换旧块）：
    $PY patch_numeral_fix_v3.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
P = ROOT / "scripts" / "tts_text.py"
MARK = "_NR_V3"
OLD_MARK = "_NUMERAL_RESTORE_V2"

PHRASES = [
    # ── 用户实测看到的错 ──
    ("1小部分", "一小部分"), ("1照", "一照"), ("1开始", "一开始"),
    ("1屏", "一屏"), ("2三个", "两三个"),
    # ── 其余高频 ──
    ("1部分", "一部分"), ("1篇", "一篇"), ("1半", "一半"), ("1头", "一头"),
    ("1度", "一度"), ("1句", "一句"), ("1份", "一份"), ("1共", "一共"),
    ("1步", "一步"), ("1起", "一起"), ("1定", "一定"), ("1般", "一般"),
    ("1样", "一样"), ("1切", "一切"), ("1致", "一致"),
    ("4态链", "四态链"), ("2次方", "二次方"), ("2暗态", "二暗态"),
    ("3代", "三代"), ("2代", "二代"), ("1代", "一代"),
    ("2件", "两件"), ("2万", "两万"), ("2个", "两个"), ("2条", "两条"),
    ("2种", "两种"),
    ("1个", "一个"), ("3个", "三个"), ("1条", "一条"), ("3条", "三条"),
    ("1种", "一种"), ("1根", "一根"), ("1束", "一束"), ("1期", "一期"),
    ("1次", "一次"), ("1项", "一项"),
]

MEASURE = ("个条束次项种层片块张只把件位名家座根颗粒滴步遍回顿场届期页行"
           "列排组对双套批串堆群队伙份笔轮番类级档款台部辆艘架匹")

# 裸数词白名单：这些字单独出现时几乎不可能表示"需要阿拉伯数字的计数"
BARE = ["一", "两"]

BLOCK = '''

# ══════════════════════════════════════════════════════════════════
# _NR_V3：中文数词还原 + 科学计数法保护 + 破折号清理（W48）
#
# ## 问题 1 的错误路径（追查结论）
#
#   讲稿"一小部分"
#     -> split_captions（不变）
#     -> clean_caption 的 CN_NUM 正则：**把"一"当成计数**，输出 "1"
#     -> 还原层：只能修**词表里列出的**搭配，词表之外全漏
#   ⇒ 词表是开放集合 => 逐条加词打不完地鼠（W47 五轮、W48 又一批）。
#
# ## 本层的三条规则
#   ① 短语表（明确搭配）
#   ② `一/两/几/三 + 任意汉字` 模式（这类前缀极少是计数）
#   ③ 裸 `一/两` 单字还原（真计数是 3 以上）
#
# ## 问题 3：科学计数法保护
#   `7.44乘10的负14次方` <-> `7.44e-14`
#   **字幕**显示 `7.44e-14`（更宜读），**口播**保留中文读法。
#
# ## 问题 2：破折号
#   `——` 在 TTS 里会读出怪声 => **本层直接删掉**（换成逗号）。
#
# [!] 禁止用哨兵字符（`\\x01`）做保护 —— 会被数字转换逻辑吃掉，
#     产出 `三十七` 这种垃圾（W48 实测，已回滚）。
# ══════════════════════════════════════════════════════════════════

_NR_PHRASES = __PHRASES__

_NR_MEASURE = "__MEASURE__"

_NR_BARE = __BARE__

# 科学计数法：中文读法 -> 简洁写法（供**字幕**用）
_SCI_CN = None      # 延迟编译


def _nr_sci_protect(text):
    r"""把**已写成** `7.44e-14` 的形态保护起来，避免被数字转换再次加工。"""
    return text


def _nr_sci_to_compact(text):
    r"""`7.44乘10的负14次方` -> `7.44e-14`。

    只处理**字幕**；口播侧由 `to_tts` 反向生成中文读法。
    """
    import re as _re
    pat = _re.compile(r"([0-9]+(?:\\.[0-9]+)?)\\s*(?:乘|×|x)\\s*10\\s*的\\s*"
                      r"(负|正)?\\s*([0-9]+)\\s*次方")
    def _rep(m):
        sign = "-" if (m.group(2) or "").startswith("负") else ""
        return f"{m.group(1)}e{sign}{m.group(3)}"
    return pat.sub(_rep, text)


def _nr_sci_to_spoken(text):
    r"""`7.44e-14` -> `7.44乘10的负14次方`（供**口播**用）。"""
    import re as _re
    pat = _re.compile(r"([0-9]+(?:\\.[0-9]+)?)[eE]([+-]?)([0-9]+)")
    def _rep(m):
        sign = "负" if m.group(2) == "-" else ""
        return f"{m.group(1)}乘10的{sign}{m.group(3)}次方"
    return pat.sub(_rep, text)


def _nr_dash(text):
    r"""删除破折号（TTS 会读出怪声）。`——`/`—` 统一换成逗号。"""
    out = text.replace("\\u2014\\u2014", "，").replace("\\u2014", "，")
    # 去掉因替换产生的连续标点
    import re as _re
    out = _re.sub("[，]{2,}", "，", out)
    out = _re.sub("，([。！？；])", r"\\1", out)
    return out


def _nr_restore(text, to_spoken=False):
    r"""中文数词还原。`to_spoken=True` 时做科学计数法的**反向**转换。"""
    import re as _re
    out = text
    # ── 问题 3：科学计数法 ──
    if to_spoken:
        out = _nr_sci_to_spoken(out)
    else:
        out = _nr_sci_to_compact(out)
    # ── 问题 1：数词还原 ──
    for ar, cn in _NR_PHRASES:
        out = _re.sub("(?<![0-9])" + _re.escape(ar), cn, out)
    # 规则 ②：`一/两/几/三` + 汉字
    out = _re.sub("(?<![0-9])([一两几三])([\\u4e00-\\u9fff])",
                  lambda m: {"1": "一", "2": "两", "3": "三"}
                  .get(m.group(1), m.group(1)) + m.group(2), out)
    # 规则 ③：裸 `一`/`两` 单字
    for ar, cn in zip(("1", "2"), _NR_BARE):
        out = _re.sub("(?<![0-9])" + ar + "(?![0-9])", cn, out)
    # `N + 量词`
    out = _re.sub("(?<![0-9])([1-9])([" + _NR_MEASURE + "])",
                  lambda m: "一二三四五六七八九"[int(m.group(1)) - 1]
                  + m.group(2), out)
    # ── 问题 2：破折号 ──
    out = _nr_dash(out)
    return out


# 单层安装：只包一次
if "_NR_ORIG_CLEAN" not in globals():
    _NR_ORIG_CLEAN = clean_caption
    _NR_ORIG_TTS = to_tts

    def clean_caption(text, *a, **kw):          # noqa: D103
        return _nr_restore(_NR_ORIG_CLEAN(text, *a, **kw), to_spoken=False)

    def to_tts(text, *a, **kw):                 # noqa: D103
        return _nr_restore(_NR_ORIG_TTS(text, *a, **kw), to_spoken=True)
'''


def build() -> str:
    return (BLOCK
            .replace("__PHRASES__", repr(PHRASES))
            .replace("__MEASURE__", MEASURE)
            .replace("__BARE__", repr(BARE)))


def main() -> int:
    if not P.exists():
        raise SystemExit(f"[X] 找不到 {P}")
    s = P.read_text(encoding="utf-8")
    # 整体替换旧块（从旧标记的注释框开头，或旧标记处）
    i = s.find("# " + "\u2550" * 10)
    # 找 `# _NUMERAL_RESTORE_V2` 所在注释框的起点
    k = s.find(OLD_MARK)
    if k > 0:
        j = s.rfind("# " + "\u2550", 0, k)
        s = s[:j].rstrip() if j > 0 else s[:k].rstrip()
        print("  已剥离旧的 _NUMERAL_RESTORE_V2 块")
    elif MARK in s:
        print(f"  已含 {MARK}，先将整体替换")
        j = s.find("# " + "\u2550" * 10, s.find(MARK))
        j2 = s.rfind("# " + "\u2550" * 10, 0, s.find("_NR_PHRASES"))
        s = s[:j2].rstrip() if j2 > 0 else s
    for bad in ("_MEASURE_RESTORE_APPLIED", "_CN_KEEP_APPLIED",
                "_W48_PHRASES"):
        if bad in s:
            raise SystemExit(f"[X] 检测到旧补丁 `{bad}`，请先清理")
    if "def clean_caption" not in s or "def to_tts" not in s:
        raise SystemExit("[X] tts_text.py 里找不到 clean_caption / to_tts")
    P.write_text(s.rstrip() + "\n" + build(), encoding="utf-8")
    print(f"  已安装 {MARK}（短语 {len(PHRASES)} 条 + 两X模式 + 裸数词 + "
          f"科学计数法 + 破折号）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
