#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W40 视频的**唯一事实来源**：20 段口播 + 对应 20 屏幻灯片。

## 为什么要这样设计

W40 在这一步反复失败，根因是**幻灯片与口播是两份手工维护的清单、
再靠「逐屏对齐」** —— 这个设计天然脆弱。

已经踩过的三种翻车方式：

1. 幻灯片按**主题**排序、讲稿按**叙事**排序 → 顺序天然不同；
2. 写「顺序表」重排 → 顺序表本身会错；
3. 改切点 → **切点改了但忘了重新生成音频** → 素材按新切点、音频按旧切点。

**第 4 种（本次）**：段落边界由 `calibrate_segments.py` 用 DP 重算过，
而 `PAGES` 还是按**旧边界**写的 → 幻灯片比口播**早一屏**：
实测第 5 屏标题是「办法：极值理论」，该屏念的却是
「说明分布有上界——存在一个天花板」（那还是上一段的内容）。

## 现在的做法：**画面从该段的实际口播派生**

```
内容/讲稿.md
   ↓ calibrate_segments.py（DP 切 20 段）
publish/segments.json                    ← 边界
   ├→ build_narration()  → 口播 20 段（汉字数字，给配音）
   └→ build_slides()     → 画面 20 屏（阿拉伯数字，从**同一段**口播提取要点）
```

要点由 `KEY` 里登记的关键句（**按内容匹配，不按下标**）从该段口播中挑出，
配合 `FIGS` 登记该屏要放的论文图。

⚠️ 口播文本（念出来的）与画面文本（看的）**有意分开**：
口播为发音写汉字数字，画面必须写阿拉伯数字。

## 用法

    $PY calibrate_segments.py --export   # 先算边界
    $PY episode_spec.py                  # 打印对照表
    $PY episode_spec.py --export         # 导出 slides16x9.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_MD = ROOT / "内容" / "讲稿.md"
PUB = ROOT / "publish"
SEG_JSON = PUB / "segments.json"

# ---------------------------------------------------------------------------
# 每屏的**标题**（人写）与该屏要放的**论文图**（可选）。
# ⚠️ 键是**屏号 = 段号**，与 segments.json 严格一一对应。
#    段边界改了（重跑 calibrate）之后，必须回来核对这里每一行的标题
#    是否仍与该段口播同主题 —— 这是本文件唯一需要人工维护的地方。
# ---------------------------------------------------------------------------
TITLES: dict[int, str] = {
    1: "越极端，越不会一起来",
    2: "「五十年一遇」不是「每五十年一次」",
    3: "第一个反直觉：50 年内至少一次只有 63.6%",
    4: "为什么不能直接看历史最大值",
    5: "办法：极值理论 —— 最大值只有三种形态",
    6: "意外发现：气温有界，降水无界",
    7: "为什么会这样：气温受能量平衡约束，降水没有上限",
    8: "「五十年一遇」的高温是多少度",
    9: "区间宽度本身就是结论",
    10: "进入正题：为什么不能用相关系数",
    11: "风险倍数：结果与假设相反",
    12: "证据一：季节性错开",
    13: "证据二：物理抑制",
    14: "证据三：copula 拟合不出尾部",
    15: "门槛正在移动：16 城全部升温",
    16: "北京：五十年一遇 → 六年一遇",
    17: "城市风险：谁在前面",
    18: "为什么不能公布精确名次",
    19: "思考题：50 年内至少一次的概率",
    20: "三句话总结",
}

# 该屏放哪张论文图（键=屏号）。图在 results/figs/。
FIGS: dict[int, tuple[str, str]] = {
    6: ("q1_xi_compare.png",
        "14/16 城气温 ξ<0（有上界）；14/16 城降水 ξ>0（重尾）"),
    8: ("q1_tmax_return.png",
        "各城日最高气温的重现期曲线；吐鲁番 48.8℃ [47.7, 50.1]"),
    14: ("q2_lambdaU.png",
        "99 分位处经验联合概率一致低于全部 5 个拟合族"),
    16: ("q3_trend.png",
        "16 城位置参数趋势；北京 1940 年「五十年一遇」= 40.9℃"),
    17: ("q4_risk.png",
        "风险构成与复合事件倍数随窗口的变化"),
}

# 版式：16:9 渲染器支持 cover / bullets / compare / summary / figure
KINDS: dict[int, str] = {
    1: "cover",
    3: "compare",
    9: "compare",
    11: "compare",
    20: "summary",
}
# figure 显式覆盖（有登记图的屏优先用图）
for _p in FIGS:
    KINDS.setdefault(_p, "figure")

COVER = {
    "tag": "用数学看世界",
    "sub": "16 个城市 · 86 年 · 约 50 万条逐日记录",
    "big": "0.32",
    "big_label": "99 分位处的风险倍数：小于 1 就是互相排斥",
}

# 汉字数字 → 阿拉伯数字（**仅用于画面**）
_CN_DIGIT = {"零": "0", "一": "1", "二": "2", "两": "2", "三": "3", "四": "4",
             "五": "5", "六": "6", "七": "7", "八": "8", "九": "9"}
_CN_UNIT = {"十": 10, "百": 100, "千": 1000, "万": 10000}


def cn2num(text: str) -> str:
    r"""把画面文本里的汉字数字转成阿拉伯数字。

    ⚠️ 只用于**画面**。口播必须保留汉字数字（为发音写），故两条路径分开。

    ⚠️ **过转是真实踩过的坑**：早期贪婪替换把「任一年」变成「任1年」、
    「二者」变成「2者」、「一致」变成「1致」。所以只转明确的数量表达，
    并排除「任/同/某/另/下/每/前后/第 + 数字」这类非数量用法。
    """
    if not text:
        return text

    def to_int(s: str) -> int:
        total, cur = 0, 0
        for ch in s:
            if ch in _CN_DIGIT:
                cur = int(_CN_DIGIT[ch])
            elif ch in _CN_UNIT:
                total += (cur or 1) * _CN_UNIT[ch]
                cur = 0
        return total + cur

    def with_point(s: str) -> str:
        if "点" in s:
            a, b = s.split("点", 1)
            return f"{to_int(a) if a else 0}." + "".join(
                _CN_DIGIT.get(c, "") for c in b)
        return str(to_int(s))

    NUM = r"[零一二两三四五六七八九十百千万]+(?:点[零一二三四五六七八九]+)?"
    EXCL = r"(?<![任同某另下每前后第])"
    text = re.sub(r"百分之" + f"({NUM})",
                  lambda m: f"{with_point(m.group(1))}%", text)
    text = re.sub(
        EXCL + f"({NUM})(?=(?:个|年|月|日|度|次|种|档|城|倍|分位|年一遇))",
        lambda m: with_point(m.group(1)), text)
    text = re.sub(EXCL + f"({NUM})(?=(?:℃|摄氏度|毫米|米))",
                  lambda m: with_point(m.group(1)), text)
    # ⚠️ 修过转：「每五十年一次」的「一」是「一次」这个固定说法，不是计数 1；
    #    「一个」在中文里也常读作量词而非数字 1。
    #    实测被转成「每五10年1次」「澄清1个我们天天挂在嘴边」，很怪。
    text = text.replace("1次", "一次")
    text = re.sub(r"(?<![0-9.])1个(?=[^0-9])", "一个", text)
    text = text.replace("第1", "第一")
    # ⚠️ 「每五十年一次」里的「五十」被第一条规则转成「50」后，
    #    又会被「数字+年」的规则二次匹配成「五10年」。
    #    「每五十年」是固定说法，保留汉字更好读。
    text = text.replace("五10年", "五十年")
    return text


def load_script_sections() -> dict[int, list[str]]:
    """讲稿 → {节号: [自然段, …]}，只做最小清洗（不按句号重切）。"""
    t = SCRIPT_MD.read_text(encoding="utf-8")
    parts = re.split(r"^##\s*第\s*(\d+)\s*节\s*·?\s*(.*)$", t, flags=re.M)
    out: dict[int, list[str]] = {}
    for i in range(1, len(parts), 3):
        n = int(parts[i])
        paras = []
        for raw in re.split(r"\n\s*\n", parts[i + 2]):
            p = raw.strip()
            p = re.sub(r"^---\s*$", "", p, flags=re.M).strip()
            p = p.replace("**", "")
            p = re.sub(r"（停顿）", "", p)
            if p:
                paras.append(p)
        out[n] = paras
    return out


def load_segments() -> list[dict]:
    if not SEG_JSON.exists():
        raise SystemExit("[!] 缺 publish/segments.json —— 先跑 "
                         "calibrate_segments.py --export")
    return json.loads(SEG_JSON.read_text(encoding="utf-8"))["segments"]


def build_narration() -> list[str]:
    """20 段口播（**汉字数字，给配音**）。"""
    secs = load_script_sections()
    return ["\n".join(secs[r["sec"]][r["paras"][0]:r["paras"][1]])
            for r in load_segments()]


def _clip(s: str, limit: int = 30) -> str:
    """把一条要点裁到 limit 字内，在标点处断，不要断在词中间。"""
    s = s.strip()
    if len(s) <= limit:
        return s
    head = s[:limit]
    for sep in ("；", "，", "、", "。"):
        k = head.rfind(sep)
        if k >= limit * 0.45:
            return head[:k]
    return head.rstrip("，。；、") + "…"


def _split_sents(text: str) -> list[str]:
    out = []
    for p in text.split("\n"):
        for s in re.split(r"(?<=[。？！])", p.strip()):
            if s.strip():
                out.append(s.strip())
    return out


def build_lines(page: int, text: str, maxn: int = 4) -> list[str]:
    r"""从**该段口播**提取画面要点。

    ⚠️ **幻灯片要点必须是短语，不能是整句**。

    踩过的坑：早期取整句（单条最长 76 字，实际一条 33 字），
    4 条铺满一屏 —— 用户反馈"文字太多"，而且视觉上像论文摘要而非幻灯片。
    观众在看视频，**扫一眼**就要能抓到重点，读不下长句。

    现在的做法：把该段口播拆成**短分句**（按 。！？；，），
    挑信息密度高的（含数字/结论词），每条压到 **≤30 字**。

    挑选优先级：
      ① 含数字或结论词、且长度在 8–30 字之间的分句；
      ② 该段前几个分句（通常是主题）；
      ③ 其余按顺序补齐。
    """
    # 拆到短分句级
    parts: list[str] = []
    for s in _split_sents(text):
        for c in re.split(r"[；，、]", s):
            c = c.strip().strip("。？！")
            if len(c) >= 6:
                parts.append(c)
    if not parts:
        return [""]

    _LOW = ("顺便说一句", "这里有个细节", "说到这里", "值得一提的是")
    _HOT = re.compile(r"[0-9]|百|十|形状参数|上界|重尾|copula|风险倍数|显著|优先|"
                      r"上界|下界|区间|趋势")
    cand = [c for c in parts if not c.startswith(_LOW) and 8 <= len(c) <= 30]
    hot = [c for c in cand if _HOT.search(c)]

    picked: list[str] = []
    for c in hot:                                  # ① 高信息量短语
        if len(picked) >= maxn:
            break
        picked.append(c)
    for c in cand:                                 # ②③ 主题句与补齐
        if len(picked) >= maxn:
            break
        if c not in picked:
            picked.append(c)
    if not picked:                                 # 兜底：短语都不合格就裁分句
        picked = [_clip(c) for c in parts[:maxn]]
    return [cn2num(_clip(c)) for c in picked[:maxn]]


def to_slides_json() -> dict:
    narr = build_narration()
    slides = []
    for page, text in enumerate(narr, 1):
        kind = KINDS.get(page, "bullets")
        title = cn2num(TITLES.get(page, f"第 {page} 屏"))
        if kind == "cover":
            slides.append({"kind": "cover", "title": title, **COVER})
        elif kind == "figure":
            fname, note = FIGS[page]
            slides.append({"kind": "figure", "head": title,
                           "img": f"results/figs/{fname}",
                           "note": cn2num(note)})
        elif kind == "summary":
            slides.append({"kind": "summary", "head": title,
                           "lines": build_lines(page, text)[:3]})
        elif kind == "compare":
            ls = build_lines(page, text)
            slides.append({"kind": "compare", "head": title,
                           "rows": [["", x] for x in ls[:3]]})
        else:
            slides.append({"kind": "bullets", "head": title,
                           "lines": build_lines(page, text)})
    return {
        "brand": "用数学看世界", "week": "2026-W40",
        "_note": "本文件由 scripts/episode_spec.py 自动派生，请勿手工编辑。"
                 "标题改 episode_spec.py 的 TITLES、配图改 FIGS；"
                 "段落边界跑 calibrate_segments.py --export。"
                 "⚠️ 画面用阿拉伯数字、不写 markdown 标记；"
                 "口播用汉字数字 —— 两条路径有意分开。",
        "slides": slides,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", action="store_true")
    args = ap.parse_args()

    narr = build_narration()
    spec = to_slides_json()
    slides = spec["slides"]
    print(f"  口播 {len(narr)} 段 / 画面 {len(slides)} 屏\n")
    if len(narr) != len(slides):
        print(f"  ⚠️ 段数 {len(narr)} ≠ 屏数 {len(slides)}")
    print("  屏 版式      标题                          | 该段口播首句 / 画面首条")
    print("  " + "-" * 100)
    for i, (t, s) in enumerate(zip(narr, slides), 1):
        head = s.get("head") or s.get("title", "")
        body = (s.get("lines") or [s.get("note") or s.get("sub", "")])[0]
        print(f"  {i:>2} {s['kind']:<9}{head[:28]:<30}| "
              f"{t.split(chr(10))[0][:22]} → {body[:26]}")
    tot = sum(len(t.replace("\n", "")) for t in narr)
    print(f"\n  口播合计 {tot} 字 → 约 {tot/6.7/60:.1f} 分钟")

    if args.export:
        p = PUB / "slides16x9.json"
        p.write_text(json.dumps(spec, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        print(f"\n  ✅ {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
