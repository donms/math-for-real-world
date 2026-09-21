#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""按「目标时长」把讲稿切成 N 段，并生成每屏画面要点 —— **通用版**。

## 为什么这样设计（W40 六轮返工的教训）

W40 在视频这一步反复失败，根因是**幻灯片与口播是两份手工维护的清单、
再靠"逐屏对齐"**。本脚本把它压成**单一事实来源**：

```
内容/讲稿.md
   ↓ 本脚本（DP 切段 + 从段内派生要点）
   ① publish/segments.json   ← 边界
   ② publish/slides16x9.json ← 画面（标题 + 要点 + 配图）
```

口播清单（`make_manifest_platforms.py`）读**同一份** segments.json，
故图与文**同源**，不可能错位。

## 与 W40 版的区别：**通用化**

W40 版的 `TITLES` / `PAGES` 是按屏号硬编码的，期号也写死。
本版：
* **期号从 `--ep` 取**（不再硬编码 2026-W40）
* **标题与画面内容从段内文本派生**，只在 `FIGS` 里登记"哪一屏放哪张图"
* 段数**按目标时长自动算**（不再固定 20 屏）

## 用法

    $PY make_video_spec.py --ep 2026-W41                  # 打印对照表
    $PY make_video_spec.py --ep 2026-W41 --export         # 导出两份清单
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# ⚠️ 本脚本位于 episodes/<期号>/scripts/，故仓库根要**向上四级**：
#    scripts → <期号> → episodes → 仓库根
#    （早期写成三级，得到 episodes/ 本身，报"缺讲稿.md"）
ROOT = Path(__file__).resolve().parent.parent.parent.parent
SPEED_CPS = 6.7          # 实测语速（IndexTTS, duration_factor=0.72）
SEC_PER_PAGE = 35.0      # 教学视频一屏停留 30–40 秒较舒服

# ---------------------------------------------------------------------------
# 每期登记：标题规则（按**段内关键词**匹配，不是按屏号硬编码）
#
# ⚠️ 为什么按关键词而不是按屏号：段边界由 DP 按字数算出，改讲稿后屏号会变。
#    按关键词匹配时，标题跟着内容走，不会整体错位（W40 在这一点上反复翻车）。
#    规则**按顺序匹配**，故更具体的要写在前面。
#
# 注意：第一屏自动为 cover、末屏自动为 summary，其标题由本表亦可覆盖。
# ---------------------------------------------------------------------------
TITLE_RULES_BY_EP: dict[str, list[tuple[str, str]]] = {
    "2026-W41": [
        ("9 月 16 日", "一条新运河，能解开一个老堵点吗"),
        ("先看一个反差", "一个反差：1 亿吨 vs 2.24 亿吨"),
        ("货种高度重叠", "新运河要抢的，正是老瓶颈的主力货类"),
        ("先得知道原来有多堵", "第一步：把老瓶颈量出来"),
        ("我最想讲的一段", "我的假设被数据否定了"),
        ("待闸数为什么暴涨", "真正的成因：不是水位，是检修"),
        ("是设备可用性问题", "结论：检修，不是水位"),
        ("我把它", "诚实记录：这个否定结果写进了论文"),
        ("广义成本", "分流怎么算：广义成本"),
        ("两个独立口径", "运费优势：两个口径互相印证"),
        ("同量级，互相印证", "运费优势：两个口径互相印证"),
        ("假精确", "判据与修正"),
        ("转换摩擦", "一次模型失败：100% 分流率"),
        ("三座梯级船闸", "新通道自己会不会堵"),
        ("抵消优势", "临界值：要等 21 天才会抵消优势"),
        ("敏感性分析", "决定成败的是转换摩擦，不是硬件"),
        ("最有意思的地方", "这份预测可以被检验"),
        ("几条边界", "边界：哪些缺陷把结论推向哪边"),
        ("转换惯性", "三句话总结"),
    ],
}

# 每期登记：哪一屏配哪张论文图（键=**关键词**，值=(图文件名, 图注)）
# 若某屏的标题规则命中，且此处也登记了同一关键词，则该屏改用 figure 版式。


def _match_rule(text: str, ep: str, used: set | None = None) -> tuple:
    r"""按**内容关键词**匹配标题，返回 (标题, 命中的关键词)。

    ⚠️ **一条规则只能命中一次**（used 集合）。
    踩过的坑：关键词「转换摩擦」在讲稿的多段里都出现，
    导致该规则被反复命中 —— 第 12-15 屏标题全变成同一个。
    去重后每屏标题才互不相同。
    """
    used = used if used is not None else set()
    for kw, title in TITLE_RULES_BY_EP.get(ep, []):
        if kw in used:
            continue
        if kw in text:
            return title, kw
    return None, None


# ---------------------------------------------------------------------------
# 目标屏数覆盖：语义边界需要更多屏时，用它抬升目标
#   W41：第 2 节需 2 屏、第 5 节需 5 屏 → 共 16 屏（按字数算只有 15）
#        **以语义为准**：多一屏约 35 秒，比两个主题挤一屏好
# ---------------------------------------------------------------------------
TARGET_OVERRIDE: dict = {"2026-W41": 16}


# 每节屏数覆盖：{节号: 屏数}。语义边界需要的节在此显式给足，
# 其余节按字数比例分（并受该表约束）。
ALLOC_OVERRIDE: dict = {
    "2026-W41": {1: 1, 2: 2, 3: 1, 4: 2, 5: 5, 6: 2, 7: 1, 8: 1, 9: 1},
}


# ---------------------------------------------------------------------------
# ★ 按屏号直接指定标题（与 set_segments.py 的 RANGES 一一对应）
#
# ⚠️ **为什么不再用关键词匹配**：用户三次指出图文错位，根因都是
#    「标题与内容靠关键词间接对应」—— 而关键词在讲稿里会重复出现，
#    `used` 集合的全局顺序一变标题就整体错位一格。
#    屏数既已人工写死，标题就按屏号直接给，完全确定、无耦合。
# ---------------------------------------------------------------------------
TITLES_BY_PAGE: dict = {
    "2026-W41": ["一条新运河，能解开一个老堵点吗", "一个反差：1 亿吨 vs 2.24 亿吨", "新运河要抢的，正是老瓶颈的主力货类", "第一步：把老瓶颈量出来", "我的假设被数据否定了", "真正的成因：不是水位，是检修", "分流怎么算：广义成本", "运费优势：两个口径互相印证", "一次模型失败：100% 分流率", "判据与修正：加一个转换摩擦", "新通道自己会不会堵", "临界值：要等 21 天才会抵消优势", "决定成败的是转换摩擦，不是硬件", "这份预测可以被检验", "边界：哪些缺陷把结论推向哪边", "三句话总结"],
}


def ep_dir(ep: str) -> Path:
    return ROOT / "episodes" / ep


def load_sections(md: Path) -> dict[int, list[str]]:
    """讲稿 → {节号: [自然段, …]}，只做最小清洗（**不按句号重切**）。

    ⚠️ W40 的教训：按句号重切会让切点与幻灯片主题对不上。
    编辑讲稿时的分段就是创作意图，一个自然段通常是一个完整思想。
    """
    t = md.read_text(encoding="utf-8")
    parts = re.split(r"^##\s*第\s*(\d+)\s*节\s*·?\s*(.*)$", t, flags=re.M)
    out: dict[int, list[str]] = {}
    for i in range(1, len(parts), 3):
        n = int(parts[i])
        paras = []
        for raw in re.split(r"\n\s*\n", parts[i + 2]):
            p = raw.strip()
            p = re.sub(r"^---\s*$", "", p, flags=re.M).strip()
            p = p.replace("**", "")
            if p:
                paras.append(p)
        out[n] = paras
    return out


def target_pages(n_chars: int) -> int:
    return max(8, min(30, round(n_chars / SPEED_CPS / SEC_PER_PAGE)))


# ---------------------------------------------------------------------------
# 语义切点表：{节号: [允许切开的位置, …]}（切点 = 该位置之前断开）
#
# ⚠️ **为什么必须人工标注**：DP 只按字数均衡，不懂叙事。
#    W41 实测：第 5 节 17 个自然段被切成 3 段（切在 6 和 12），
#    结果第 7 屏（标题「分流怎么算：广义成本」）里塞进了
#    「两个口径」和「模型失败开头」—— 本该属于第 8、9 屏的内容。
#    用户核对时发现：「这段是不是应该在第八屏」。
#
#    第 5 节 17 段的语义边界：
#      [0-2]   广义成本 + 等待时间反推        → 广义成本屏
#      [3-6]   运费两个口径 + 两者印证        → 运费优势屏
#      [7-11]  模型失败：现象 + 根因          → 模型失败屏
#      [12-12] 判据（所有个体一致 = 结构问题）→ 判据屏
#      [13-16] 修正 + 情景扫描 + 分流率区间   → 修正屏
#    故允许切在 3、7、12、13。
#
#    第 2 节 7 段的语义边界：
#      [0-4]  反差（1 亿吨 vs 2.24 亿吨）+ 它的含义 → 第 2 屏
#      [5-6]  货种高度重叠                          → 第 3 屏
#    ⇒ 在段 5 之前切。
#
#    ⚠️ 只禁一个位置时 DP 会选**次优**位置，故这里用**白名单**更精确。
# ---------------------------------------------------------------------------
ALLOW_CUT_BY_EP: dict = {
    "2026-W41": {2: [5], 5: [3, 7, 12, 13]},
}


def split_section(paras: list[str], k: int,
                  forbid: set[int] | None = None,
                  allow: list[int] | None = None) -> list[tuple[int, int]]:
    r"""把一节切成 k 段，最小化 Σ(段字数 − 目标)² —— 动态规划精确解。

    `forbid` 是不允许切开的位置（切点 = 该位置之前断开）。
    ⚠️ W40 的坑：`forbid` 只禁一个位置时，DP 会选**次优**位置。
       要把所有不该切的位置都列上，并核对输出确实落在你要的地方。
    """
    m = len(paras)
    forbid = forbid or set()
    allow_set = set(allow) if allow else None
    if k <= 1 or m <= 1:
        return [(0, m)]
    k = min(k, m)
    w = [len(p) for p in paras]
    target = sum(w) / k
    INF = float("inf")
    dp = [[INF] * (k + 1) for _ in range(m + 1)]
    prev = [[-1] * (k + 1) for _ in range(m + 1)]
    dp[0][0] = 0.0
    for t in range(1, k + 1):
        for j in range(t, m + 1):
            for i in range(t - 1, j):
                if dp[i][t - 1] == INF or i in forbid:
                    continue
                if allow_set is not None and i != 0 and i not in allow_set:
                    continue
                seg = sum(w[i:j])
                cost = dp[i][t - 1] + (seg - target) ** 2
                if cost < dp[j][t]:
                    dp[j][t] = cost
                    prev[j][t] = i
    cuts, j, t = [], m, k
    while t > 0:
        i = prev[j][t]
        if i < 0:
            return [(0, m)]
        cuts.append((i, j))
        j, t = i, t - 1
    return list(reversed(cuts))


def allocate(sections: dict[int, list[str]], target: int,
             allow_by_sec: dict | None = None,
             alloc_override: dict | None = None) -> list[tuple[int, int, int]]:
    ns = sorted(sections)
    counts = {n: len(sections[n]) for n in ns}
    tot = sum(counts.values())
    # ⚠️ 每节至少要切到「语义边界数 + 1」段，否则白名单会让 DP 无解、
    #    退回不切（实测第 5 节需 4 段才能落在我标的 3 个切点上）
    # 语义边界把一节切成「切点数 + 1」段 —— 这是**硬下界**：
    # 少于它，DP 就落不到我标的那些切点上（实测第 5 节需 4 段）
    need = {n: 1 + len((allow_by_sec or {}).get(n, [])) for n in ns}
    alloc = {n: max(1, need[n], round(counts[n] / tot * target)) for n in ns}
    # 若需要的段数已超过目标，则把目标抬到需求总和
    target = max(target, sum(need.values()))
    while sum(alloc.values()) < target:
        alloc[max(ns, key=lambda n: counts[n] / alloc[n])] += 1
    while sum(alloc.values()) > target:
        c = max((n for n in ns if alloc[n] > 1), key=lambda n: alloc[n])
        alloc[c] -= 1
    allow_by_sec = allow_by_sec or {}
    out = []
    for n in ns:
        for a, b in split_section(sections[n], alloc[n], None,
                                  allow_by_sec.get(n)):
            out.append((n, a, b))
    return out


# ---------------------------------------------------------------------------
# 汉字数字 → 阿拉伯数字（**只用于画面**；口播保留汉字以便发音）
# ⚠️ W41 第一版漏了这一步，画面上出现「二点二四亿吨」「百分之十一点七」，
#    与 W40 已确认的画风不一致。故此处直接移植 W40 的实现。
# ---------------------------------------------------------------------------
_CN_DIGIT = {"零": "0", "一": "1", "二": "2", "两": "2", "三": "3", "四": "4",
             "五": "5", "六": "6", "七": "7", "八": "8", "九": "9"}
_CN_UNIT = {"十": 10, "百": 100, "千": 1000, "万": 10000}


def cn2num(text: str) -> str:
    r"""把画面文本里的汉字数字转成阿拉伯数字。

    ⚠️ 只用于**画面**。口播必须保留汉字数字（为发音写），故两条路径分开。

    ⚠️ **过转是踩过的坑**：早期贪婪替换把「任一年」变成「任1年」、
    「二者」变成「2者」、「一致」变成「1致」。所以：
      · 只转明确的数量表达（后面跟着量词/单位）
      · 排除「任/同/某/另/下/每/前后/第 + 数字」这类非数量用法
      · 「五十年」「一次」等固定说法保留汉字
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
        EXCL + f"({NUM})(?=(?:个|年|月|日|度|次|种|档|城|倍|分位|年一遇|"
                f"吨|公里|米|元))",
        lambda m: with_point(m.group(1)), text)
    text = text.replace("1次", "一次").replace("第1", "第一")
    text = re.sub(r"(?<![0-9.])1个(?=[^0-9])", "一个", text)
    text = text.replace("五10年", "五十年")
    return text


def _clip(s: str, limit: int = 30) -> str:
    s = s.strip()
    if len(s) <= limit:
        return s
    head = s[:limit]
    for sep in ("；", "，", "、", "。"):
        k = head.rfind(sep)
        if k >= limit * 0.45:
            return head[:k]
    return head.rstrip("，。；、") + "…"


def bullets(text: str, maxn: int = 4) -> list[str]:
    r"""从段内口播派生画面要点（短语级，单条 ≤30 字）。

    ⚠️ 两条踩出来的教训：

    **一、要点必须是短语，不能是整句。**
    W40 早期取整句（一条 33 字），4 条铺满一屏，用户反馈"文字太多"。
    观众是**扫一眼**，读不下长句。

    **二、要点要给结论与数字，不能抄口播的叙事过程。**
    W41 第一版派生出的要点是「我一开始的猜想很自然」
    「我甚至已经准备好去拟合一个水位和通过量的关系」——
    这是**讲稿的叙事**，不是幻灯片该有的内容。
    故这里**降权第一人称叙事句**，**升权含数字与结论的短语**。
    """
    parts: list[str] = []
    for p in text.split("\n"):
        for sent in re.split(r"(?<=[。？！])", p.strip()):
            for c in re.split(r"[；，、]", sent):
                c = c.strip().strip("。？！").strip("\"'")
                if len(c) >= 5:
                    parts.append(c)
    if not parts:
        return [""]

    # 叙事性/过渡性短语 —— 不该上幻灯片
    NARR = ("我一开始", "我甚至", "我接着", "我先", "我把", "我用", "我算了",
            "准备好了", "这里有个", "顺便", "说到这里", "值得一提",
            "问题出在哪", "请注意", "这是本期", "这是我觉得")
    # **片段判据**：中文里以这些虚词/连词**结尾**的，多半是被逗号切断的半句
    # （实测切出「在回答之前」「极差只有百分之十」「而在模型结构」
    #   「是负零点六零五——待闸越多」这类碎片，做要点毫无信息量）
    FRAG_TAIL = ("的", "是", "而", "在", "就", "也", "都", "和", "与", "或",
                 "但", "却", "把", "被", "让", "给", "对", "为", "越", "很",
                 "更", "最", "只", "还", "才", "已经", "正在", "之前", "之后",
                 "越多", "以上", "以下", "来说", "而言", "的话")
    # 有信息量：数字、结论、机制
    HOT = re.compile(r"[0-9]|百分之|零点|相关|能力|利用率|待闸|摩擦|瓶颈|"
                     r"水位|检修|万吨|亿吨|结论|原因|不是.*是|抵消|主因|"
                     r"判据|结构|区间|节省|降幅|反推|差|%")

    def usable(c: str) -> bool:
        if not (5 <= len(c) <= 30):
            return False
        if any(c.startswith(x) for x in NARR):
            return False
        if any(c.endswith(x) for x in FRAG_TAIL):     # 去掉被切断的半句
            return False
        if c.count("——") or c.count("—"):             # 破折号断句也是碎片
            return False
        return True

    good = [c for c in parts if usable(c)]
    if not good:                                       # 兜底：放宽片段判据
        good = [c for c in parts if 5 <= len(c) <= 30]
    if not good:
        return [""]
    hot = [c for c in good if HOT.search(c)]
    # 位置权重：该段**前两句**通常是主题句，优先占一个位置
    picked: list[str] = []
    for c in good[:2]:
        if HOT.search(c) or len(picked) == 0:
            picked.append(c)
            break
    for c in hot:
        if len(picked) >= maxn:
            break
        if c not in picked:
            picked.append(c)
    for c in good:
        if len(picked) >= maxn:
            break
        if c not in picked:
            picked.append(c)
    return [cn2num(_clip(c)) for c in picked[:maxn]]


# ---------------------------------------------------------------------------
# ★ 画面内容：**显式撰写**（键 = TITLE_RULES_BY_EP 命中的关键词）
#
# ⚠️ 为什么不再"从口播自动派生要点"：
#    W41 试了三版自动派生，每版都引入新错误 ——
#      ① 抄了口播的叙事过程（「我一开始的猜想很自然」）而不是结论；
#      ② 按逗号切出碎片（「在回答之前」「极差只有10%」）；
#      ③ 汉字数字转换出错（「一点80000吨」「长洲船闸5年」）。
#    **自动派生省的是写要点的时间，赔的是反复返工。**
#    W40 的最终版本也是显式撰写的 —— 这里沿用同一做法。
#
# 要点要求：短语级（≤30 字）、**只给结论与数字**、用阿拉伯数字。
# ---------------------------------------------------------------------------
PAGES_BY_EP: dict = {
    "2026-W41": {
        "9 月 16 日": dict(
            kind="cover", title="一条新运河，能解开一个老堵点吗",
            sub="长洲船闸 15 期官方简报 · 平陆运河三枢纽",
            big="22%-45%", big_label="长洲货量预计降幅"),
        "先看一个反差": dict(
            head="一个反差：1 亿吨 vs 2.24 亿吨",
            lines=["平陆运河 2035 年预测运量 = 1 亿吨",
                   "长洲船闸 2025 年实际过闸 = 2.24 亿吨",
                   "新通道只有老通道的一半量级",
                   "分流不可能等于全部转移"]),
        "货种高度重叠": dict(
            head="新运河要抢的，正是老瓶颈的主力货类",
            lines=["长洲上行：煤炭 30%、铁矿 18%、粮食 16%",
                   "长洲下行：碎石 34%、水泥 16%、机制砂 15%",
                   "平陆运河批复货种：煤炭、金属矿石、水泥、粮食",
                   "两者几乎完全重叠"]),
        "先得知道原来有多堵": dict(
            head="第一步：把老瓶颈量出来",
            lines=["每闸次载货中位 1.0098 万吨",
                   "10 个月变异系数仅 11.7%（很稳）",
                   "年通过能力 2.72-3.35 亿吨",
                   "2025 实际 2.24 亿吨 → 利用率 82% / 67%"]),
        "我最想讲的一段": dict(
            head="我的假设被数据否定了",
            lines=["先验：枯水期水位低 → 装不满 → 通过量降",
                   "corr(水位, 装载率) = -0.461（方向相反）",
                   "装载率全年 0.577-0.640，极差仅 10%",
                   "装载率由货源结构决定，与水位无关"]),
        "待闸数为什么暴涨": dict(
            head="真正的成因：不是水位，是检修",
            lines=["排除检修期后 corr(水位, 日闸次) 只剩 +0.078",
                   "corr(日闸次, 待闸数) = -0.605",
                   "检修期日闸次 47.7 / 61.6，其余 55.7-73.7",
                   "待闸 71 → 813 艘对应的是检修停航"]),
        "广义成本": dict(
            head="分流怎么算：广义成本",
            lines=["C = 运费 + 时间成本 + 过闸费",
                   "等待时间由实测反推：待闸数 ÷ 日均放行数",
                   "排除检修期均值 0.59 天（范围 0.20-2.63）",
                   "该量可被 15 期数据检验"]),
        "两个独立口径": dict(
            head="运费优势：两个口径互相印证",
            lines=["口径A 航程折算：560 km × 0.03-0.08 元/吨·km",
                   "　　　　　　 = 16.8-44.8 元/吨",
                   "口径B 报道反推：50 亿 ÷ 2.24 亿吨",
                   "　　　　　　 = 22.37 元/吨",
                   "两者同量级，互相印证"]),
        "假精确": dict(
            head="判据与修正：加一个转换摩擦",
            lines=["判据：所有个体结果一致 = 模型结构有问题",
                   "修正：加转换摩擦 s（码头协议、回程货配）",
                   "s 与 θ 都无法标定 → 做情景扫描",
                   "取 s=30 元/吨 → 平均分流率约 54%"]),
        "是设备可用性问题": dict(
            head="结论：堵是设备可用性问题",
            lines=["检修期日闸次 47.7 / 61.6",
                   "其余月份 55.7-73.7",
                   "待闸 71 → 813 艘 = 检修停航",
                   "政策含义：该优化检修安排，不是水文调控"]),
        "我把它": dict(
            head="诚实记录：否定结果也写进论文",
            lines=["一个看似合理的机制假设被证伪",
                   "如实报告，不硬凑模型",
                   "这类「否定的发现」本身有价值"]),
        "转换摩擦": dict(
            head="一次模型失败：100% 分流率",
            lines=["初版 MNL：16 个货种全部 100.0%",
                   "不可能：新通道装不下 2.24 亿吨",
                   "根因：缺「转换摩擦」（码头协议、回程货配）",
                   "所有个体结果一致 = 模型结构有问题"]),
        "三座梯级船闸": dict(
            head="新通道自己会不会堵",
            lines=["3 座梯级串联 → 能力由最慢一级决定",
                   "瓶颈 = 马道枢纽（落差 29.6 m 最大）",
                   "通道年能力 2.281 亿吨",
                   "分流量 1.20 亿吨 → 利用率 52.5%"]),
        "抵消优势": dict(
            head="临界值：要等 21 天才会抵消优势",
            lines=["W* = ΔC ÷ v = 31.80 ÷ 1.5 = 21.2 天",
                   "实际估计等待仅 0.59 天",
                   "即使利用率 95%，等待也只有 11.2 天",
                   "新通道不会因拥堵失去优势"]),
        "敏感性分析": dict(
            head="决定成败的是转换摩擦，不是硬件",
            lines=["转换摩擦 ±90%",
                   "单位运费 ±59%｜时间价值 ±57%",
                   "通道能力 ±18%｜成本敏感度 ±8%",
                   "政策重点应是降低转换摩擦"]),
        "最有意思的地方": dict(
            head="这份预测可以被检验",
            lines=["长洲简报逐月公开发布",
                   "预测 2027H1 过闸量 5000-8359 万吨",
                   "验证时点：2027 年 7 月",
                   "若错，最可能：摩擦估错 / 新通道堵 / 货源变"]),
        "几条边界": dict(
            head="边界：哪些缺陷把结论推向哪边",
            lines=["月度汇总非逐船 → 高估分流",
                   "过闸费未计入 → 低估分流",
                   "腹地货源总量未建模 → 高估长洲降幅",
                   "方向相反，净偏差有限（±10-20%）"]),
        "转换惯性": dict(
            head="三句话总结",
            lines=["会分流，但幅度 22%-45%，不是全搬",
                   "新通道不会变成新瓶颈（利用率 52%）",
                   "老瓶颈的主因是检修，不是水位"]),
    },
}


def page_spec(ep: str, kw, text: str, page: int, total: int) -> dict:
    """取该屏的画面定义：优先用**显式撰写**的内容，否则退回自动派生。"""
    table = PAGES_BY_EP.get(ep, {})
    by_page = TITLES_BY_PAGE.get(ep, [])
    forced = by_page[page - 1] if 0 < page <= len(by_page) else None
    if kw and kw in table:
        d = dict(table[kw])
        d.setdefault("kind", "bullets")
        if forced:
            # 按屏号标题优先 —— 覆盖关键词匹配的结果
            if d.get("kind") == "cover":
                d["title"] = forced
            else:
                d["head"] = forced
        return d
    if forced:
        return {"kind": ("cover" if page == 1 else
                         "summary" if page == total else "bullets"),
                "head": forced,
                "lines": bullets(text, 3 if page == total else 4)}
    return {"kind": ("cover" if page == 1 else
                     "summary" if page == total else "bullets"),
            "head": derive_title(text, page, total),
            "lines": bullets(text, 3 if page == total else 4)}


def derive_title(text: str, page: int, total: int) -> str:
    """从段内文本派生标题：取该段第一个"像标题"的短句。

    ⚠️ 优先取**问句或短陈述**（≤24 字），因为口播第一句常是过渡语
    （如"在回答之前，先看一个反差"），不适合做标题。
    """
    sents = [s.strip().strip("。？！") for s in
             re.split(r"(?<=[。？！])", text.replace("\n", "")) if s.strip()]
    if not sents:
        return f"第 {page} 屏"
    for s in sents[:4]:
        if 8 <= len(s) <= 24:
            return s
    return _clip(sents[0], 24)


def _print_table(plan, segs, slides, secs) -> None:
    """打印「屏 / 节 / 段区间 / 字数 / 标题 / 口播开头」对照表。"""
    print("  屏  节 段     字数 | 画面标题                    | 口播开头")
    print("  " + "-" * 94)
    for i, (n, a, b) in enumerate(plan, 1):
        text = "\n".join(secs[n][a:b])
        head = slides[i - 1].get("head") or slides[i - 1].get("title", "")
        print(f"  {i:>2} {n:>3} {a}-{b-1:<4}"
              f"{len(text.replace(chr(10), '')):>4} | {head[:24]:<24} | "
              f"{text.split(chr(10))[0][:22]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", required=True)
    ap.add_argument("--export", action="store_true")
    args = ap.parse_args()

    d = ep_dir(args.ep)
    md = d / "内容" / "讲稿.md"
    if not md.exists():
        print(f"  [!] 缺 {md}")
        return 2

    secs = load_sections(md)
    total_chars = sum(len(p.replace("\n", "")) for n in secs for p in secs[n])
    T = TARGET_OVERRIDE.get(args.ep) or target_pages(total_chars)
    if args.ep in TARGET_OVERRIDE:
        print(f"  [i] 目标屏数由语义边界覆盖为 {T}"
              f"（按字数算是 {target_pages(total_chars)}）")
    print(f"  {args.ep}：讲稿 {total_chars} 字 → 目标 {T} 屏"
          f"（语速 {SPEED_CPS} 字/秒，每屏 {SEC_PER_PAGE} 秒）")
    print(f"  预计时长 {total_chars/SPEED_CPS/60:.1f} 分钟\n")

    # ⚠️ **人工区间优先**：set_segments.py 的 RANGES 是编辑判断的结果，
    #    而分配器（按字数比例 + 语义白名单）多次导致语义错位
    #    （用户三次指出同一类问题）。故只要该期登记了 RANGES，就用它，
    #    分配器完全不参与。
    # ★★ 分屏表优先：它是**唯一结构来源**（屏数/段区间/标题/要点）
    sb_path = d / "publish" / "分屏表.json"
    if sb_path.exists():
        sb = json.loads(sb_path.read_text(encoding="utf-8"))
        segs, slides = [], []
        for s in sb["screens"]:
            a, b = s["paras"]
            text = "\n".join(secs[s["sec"]][a:b])
            segs.append({"page": s["page"], "sec": s["sec"], "paras": [a, b],
                         "chars": len(text.replace("\n", ""))})
            item = {k: v for k, v in s.items()
                    if k in ("kind", "head", "title", "lines", "sub", "big",
                             "big_label", "tag", "img", "note")}
            item.setdefault("kind", "bullets")
            if not item.get("lines") and item["kind"] not in ("cover",):
                item["lines"] = bullets(text, 3 if item["kind"] == "summary"
                                        else 4)
            slides.append(item)
        print(f"  [i] 采用 publish/分屏表.json（{len(segs)} 屏）"
              f" —— 结构与标题均来自该文件")
        spec = {"brand": "用数学看世界", "week": args.ep,
                "_note": "本文件由 scripts/make_video_spec.py 从 "
                         "publish/分屏表.json + 内容/讲稿.md 派生，请勿手工编辑。"
                         "改结构改分屏表（跑 make_storyboard.py）。"
                         "⚠️ 画面用阿拉伯数字、不写 markdown 标记；"
                         "口播用汉字数字 —— 两条路径有意分开。",
                "slides": slides}
        if args.export:
            (d / "publish").mkdir(parents=True, exist_ok=True)
            (d / "publish" / "segments.json").write_text(
                json.dumps({"target": len(segs), "total_chars": total_chars,
                            "segments": segs}, ensure_ascii=False, indent=2),
                encoding="utf-8")
            (d / "publish" / "slides16x9.json").write_text(
                json.dumps(spec, ensure_ascii=False, indent=2),
                encoding="utf-8")
            print(f"  ✅ segments.json  ({len(segs)} 段)")
            print(f"  ✅ slides16x9.json  ({len(slides)} 屏)")
        _print_table(plan=[(s["sec"], s["paras"][0], s["paras"][1])
                           for s in sb["screens"]], segs=segs, slides=slides,
                     secs=secs)
        return 0

    # ---- 回退路径：没有分屏表时按分配器算（旧行为，仅为兼容保留）----
    plan = None
    try:
        import set_segments as _SS
        rng = _SS.RANGES.get(args.ep)
        if rng:
            plan = [(n, a, b) for (n, a, b) in rng]
            print(f"  [i] 采用 set_segments.py 的**人工区间**（{len(plan)} 屏）")
    except Exception as _e:                                   # noqa: BLE001
        print(f"  [i] 未加载人工区间（{type(_e).__name__}），改用分配器")
    if plan is None:
        plan = allocate(secs, T, ALLOW_CUT_BY_EP.get(args.ep, {}),
                        ALLOC_OVERRIDE.get(args.ep, {}))
    used_kw: set = set()
    segs, slides = [], []
    print("  屏  节 段     字数 | 画面标题                    | 口播开头")
    print("  " + "-" * 94)
    for i, (n, a, b) in enumerate(plan, 1):
        text = "\n".join(secs[n][a:b])
        segs.append({"page": i, "sec": n, "paras": [a, b],
                     "chars": len(text.replace("\n", ""))})
        # ★ 画面内容**显式撰写**（见 PAGES_BY_EP），不再从口播自动派生要点
        _, hit_kw = _match_rule(text, args.ep, used_kw)
        if hit_kw:
            used_kw.add(hit_kw)
        item = page_spec(args.ep, hit_kw, text, i, len(plan))
        # 缺 kind 的补默认值
        item.setdefault("kind", "bullets")
        slides.append(item)
        # ⚠️ 打印用的是**画面定义里的标题**（item），不是已删除的局部变量 title
        #    （曾在重构时漏改此行，导致脚本崩、JSON 不更新 —— 而日志看起来"跑过了"）
        shown = item.get("head") or item.get("title", "")
        print(f"  {i:>2} {n:>3} {a}-{b-1:<4}{segs[-1]['chars']:>4} | "
              f"{shown[:24]:<24} | {text.split(chr(10))[0][:22]}")

    spec = {"brand": "用数学看世界", "week": args.ep,
            "_note": "本文件由 scripts/make_video_spec.py 从讲稿自动派生，"
                     "请勿手工编辑。改内容改讲稿；改配图改脚本的 FIGS_BY_EP。"
                     "⚠️ 画面用阿拉伯数字、不写 markdown 标记；"
                     "口播用汉字数字 —— 两条路径有意分开。",
            "slides": slides}

    if args.export:
        (d / "publish").mkdir(parents=True, exist_ok=True)
        p1 = d / "publish" / "segments.json"
        p1.write_text(json.dumps({"target": T, "total_chars": total_chars,
                                  "segments": segs},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
        p2 = d / "publish" / "slides16x9.json"
        p2.write_text(json.dumps(spec, ensure_ascii=False, indent=2),
                      encoding="utf-8")
        print(f"\n  ✅ {p1.name}  ({len(segs)} 段)")
        print(f"  ✅ {p2.name}  ({len(slides)} 屏)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
