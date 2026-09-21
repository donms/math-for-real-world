#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""分屏表 —— **视频结构的唯一来源** + 人可读审查文档（零渲染）。

## 为什么重做这一步（W41 五次返工的分析）

五次用户反馈里 **3 次是同一类错误：分屏边界**。根因有二：

1. **结构决策由启发式做，却让用户验收启发式的输出。**
   DP 按字数均衡切段、关键词匹配标题 —— 都是"看起来对"的猜，
   用户实际在**调试我的启发式**。
2. **审查面是"渲染后的图"**，而这一步要判断的问题
   「这屏讲的是不是标题说的那件事」**只靠文字就能回答**。
   图不提供额外信息，却带来渲染耗时、同名文件覆盖、查看器缓存三个失效点。

## 本脚本的设计

* **`分屏表.json` 是唯一结构来源**：屏数、段区间、标题、要点全在里面。
  改结构 = 改这个文件（或改本脚本的 `BOOTSTRAP`），**不改代码逻辑**。
* **`分屏表.md` 是人看的那一份**：表格 + 每屏口播全文 + **版本 diff** +
  **覆盖度自检**。生成耗时毫秒级，**不渲染任何图**。
* **diff 是省时间的关键**：每次重出都在顶部列出"本次改了哪几屏"，
  审查者只看改动处，不必重读全部。

## 用法

    $PY make_storyboard.py --ep 2026-W41 --bootstrap   # 首次：从现有脚本状态建 json
    $PY make_storyboard.py --ep 2026-W41               # 生成 分屏表.md（含 diff）
    $PY make_storyboard.py --ep 2026-W41 --check       # 只跑自检，不写文件
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(r".")
SPEED_CPS = 6.7

# ---------------------------------------------------------------------------
# 引导数据：与已验收的 W41 版本一致（屏号 → 节号、段区间、标题、版式、要点）
# 仅用于 --bootstrap 首次生成 分屏表.json；之后以 json 为准。
# ---------------------------------------------------------------------------
BOOTSTRAP: dict[str, list[dict]] = {
    "2026-W41": [
        dict(sec=1, paras=[0, 6], kind="cover",
             head="一条新运河，能解开一个老堵点吗",
             sub="长洲船闸 15 期官方简报 · 平陆运河三枢纽",
             big="22%-45%", big_label="长洲货量预计降幅"),
        dict(sec=2, paras=[0, 5], kind="bullets",
             head="一个反差：1 亿吨 vs 2.24 亿吨",
             lines=["平陆运河 2035 年预测运量 = 1 亿吨",
                    "长洲船闸 2025 年实际过闸 = 2.24 亿吨",
                    "新通道只有老通道的一半量级",
                    "分流不可能等于全部转移"]),
        dict(sec=2, paras=[5, 7], kind="bullets",
             head="新运河要抢的，正是老瓶颈的主力货类",
             lines=["长洲上行：煤炭 30%、铁矿 18%、粮食 16%",
                    "长洲下行：碎石 34%、水泥 16%、机制砂 15%",
                    "平陆运河批复货种：煤炭、金属矿石、水泥、粮食",
                    "两者几乎完全重叠"]),
        dict(sec=3, paras=[0, 6], kind="bullets",
             head="第一步：把老瓶颈量出来",
             lines=["每闸次载货中位 1.0098 万吨",
                    "10 个月变异系数仅 11.7%（很稳）",
                    "年通过能力 2.72-3.35 亿吨",
                    "2025 实际 2.24 亿吨 → 利用率 82% / 67%"]),
        dict(sec=4, paras=[0, 6], kind="bullets",
             head="我的假设被数据否定了",
             lines=["先验：枯水期水位低 → 装不满 → 通过量降",
                    "corr(水位, 装载率) = -0.461（方向相反）",
                    "装载率全年 0.577-0.640，极差仅 10%",
                    "装载率由货源结构决定，与水位无关"]),
        dict(sec=4, paras=[6, 14], kind="bullets",
             head="真正的成因：不是水位，是检修",
             lines=["排除检修期后 corr(水位, 日闸次) 只剩 +0.078",
                    "corr(日闸次, 待闸数) = -0.605",
                    "检修期日闸次 47.7 / 61.6，其余 55.7-73.7",
                    "待闸 71 → 813 艘对应的是检修停航",
                    "政策含义：该优化检修安排，不是水文调控"]),
        dict(sec=5, paras=[0, 3], kind="bullets",
             head="分流怎么算：广义成本",
             lines=["C = 运费 + 时间成本 + 过闸费",
                    "等待时间由实测反推：待闸数 ÷ 日均放行数",
                    "排除检修期均值 0.59 天（范围 0.20-2.63）",
                    "该量可被 15 期数据检验"]),
        dict(sec=5, paras=[3, 7], kind="bullets",
             head="运费优势：两个口径互相印证",
             lines=["口径A 航程折算：560 km × 0.03-0.08 元/吨·km",
                    "　　　　　　 = 16.8-44.8 元/吨",
                    "口径B 报道反推：50 亿 ÷ 2.24 亿吨",
                    "　　　　　　 = 22.37 元/吨",
                    "两者同量级，互相印证"]),
        dict(sec=5, paras=[7, 12], kind="bullets",
             head="一次模型失败：100% 分流率",
             lines=["初版 MNL：16 个货种全部 100.0%",
                    "不可能：新通道装不下 2.24 亿吨",
                    "根因：缺「转换摩擦」（码头协议、回程货配）",
                    "所有个体结果一致 = 模型结构有问题"]),
        dict(sec=5, paras=[12, 17], kind="bullets",
             head="判据与修正：加一个转换摩擦",
             lines=["判据：所有个体结果一致 = 模型结构有问题",
                    "修正：加转换摩擦 s（码头协议、回程货配）",
                    "s 与 θ 都无法标定 → 做情景扫描",
                    "取 s=30 元/吨 → 平均分流率约 54%"]),
        dict(sec=6, paras=[0, 5], kind="bullets",
             head="新通道自己会不会堵",
             lines=["3 座梯级串联 → 能力由最慢一级决定",
                    "瓶颈 = 马道枢纽（落差 29.6 m 最大）",
                    "通道年能力 2.281 亿吨",
                    "分流量 1.20 亿吨 → 利用率 52.5%"]),
        dict(sec=6, paras=[5, 9], kind="bullets",
             head="临界值：要等 21 天才会抵消优势",
             lines=["W* = ΔC ÷ v = 31.80 ÷ 1.5 = 21.2 天",
                    "实际估计等待仅 0.59 天",
                    "即使利用率 95%，等待也只有 11.2 天",
                    "新通道不会因拥堵失去优势"]),
        dict(sec=7, paras=[0, 6], kind="bullets",
             head="决定成败的是转换摩擦，不是硬件",
             lines=["转换摩擦 ±90%",
                    "单位运费 ±59%｜时间价值 ±57%",
                    "通道能力 ±18%｜成本敏感度 ±8%",
                    "政策重点应是降低转换摩擦"]),
        dict(sec=8, paras=[0, 6], kind="bullets",
             head="这份预测可以被检验",
             lines=["长洲简报逐月公开发布",
                    "预测 2027H1 过闸量 5000-8359 万吨",
                    "验证时点：2027 年 7 月",
                    "若错，最可能：摩擦估错 / 新通道堵 / 货源变"]),
        dict(sec=9, paras=[0, 4], kind="bullets",
             head="边界：哪些缺陷把结论推向哪边",
             lines=["月度汇总非逐船 → 高估分流",
                    "过闸费未计入 → 低估分流",
                    "腹地货源总量未建模 → 高估长洲降幅",
                    "方向相反，净偏差有限（±10-20%）"]),
        dict(sec=9, paras=[4, 10], kind="summary",
             head="三句话总结",
             lines=["会分流，但幅度 22%-45%，不是全搬",
                    "新通道不会变成新瓶颈（利用率 52%）",
                    "老瓶颈的主因是检修，不是水位"]),
    ],
}


def load_sections(md: Path) -> dict[int, list[str]]:
    """讲稿 → {节号: [自然段]}（与 make_video_spec.py 同一口径：按空行切）。"""
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


# ---------------------------------------------------------------------------
# 覆盖度自检：口播里提到的数字/专名，画面有没有漏掉
#
# ⚠️ 设计边界：**不是判定错误，是筛出可疑处**。
#    不是口播里每个数字都该上画面，所以只报"可能未覆盖"，供人看。
#    这正是 W41 第 3 次错误（口播讲了两个口径、画面只写广义成本）
#    本该被拦住的地方。
# ---------------------------------------------------------------------------
_CN = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
       "六": 6, "七": 7, "八": 8, "九": 9}
_UNIT = {"十": 10, "百": 100, "千": 1000, "万": 10000}


def _cn_int(s: str) -> int | None:
    total, cur = 0, 0
    for ch in s:
        if ch in _CN:
            cur = _CN[ch]
        elif ch in _UNIT:
            total += (cur or 1) * _UNIT[ch]
            cur = 0
        else:
            return None
    return total + cur


def nums_in(text: str) -> set[str]:
    r"""抽出文本里的数值（把汉字数字折算成阿拉伯），用于两侧比对。"""
    out = set(re.findall(r"\d+\.?\d*", text))
    NUM = r"[零一二两三四五六七八九十百千万]+(?:点[零一二三四五六七八九]+)?"
    for m in re.finditer(NUM + r"(?![\u4e00-\u9fff])", text):
        raw = m.group(0)
        if "点" in raw:
            a, b = raw.split("点", 1)
            ai = _cn_int(a) if a else 0
            if ai is None:
                continue
            out.add(f"{ai}." + "".join(str(_CN.get(c, "")) for c in b))
        else:
            v = _cn_int(raw)
            if v is not None and v != 0:
                out.add(str(v))
    return out


def _same_num(a: str, b: str) -> bool:
    try:
        return abs(float(a) - float(b)) < 1e-9
    except ValueError:
        return a == b


# 带单位的数值才值得上画面；年份、小整数是噪音
_UNIT_AFTER = ("万吨", "亿吨", "元", "天", "艘", "闸次", "公里", "km",
               "米", "年", "%", "倍", "个百分点")
_YEAR = re.compile(r"^(19|20)\d\d$")


def coverage(narration: str, onscreen: str) -> list[str]:
    r"""返回『口播里出现、画面没有』的**实质性**数值（供人判断是否该补）。

    ⚠️ **必须收紧，否则全是误报**（实测宽口径报 9/16 屏，
    就变成噪音 —— 与 skill 里记的「抖音全被误报口播偏短」同一毛病）。

    只保留：
      · 带小数点的数（1.0098、22.37 —— 通常是关键量）
      · 后接单位的数（560 公里、813 艘）
    排除：年份（2026/2035）、无单位的小整数（三个、两次）。
    """
    ns = nums_in(narration)
    os_ = nums_in(onscreen)

    def substantive(n: str) -> bool:
        if _YEAR.match(n):
            return False
        # 带小数点的数（1.0098、22.37）通常是关键量
        if "." in n:
            return True
        # 无小数点的整数：只有**后接单位**才算实质（由下面的扫描加入）
        return n in with_unit

    # 带单位的整数：单独扫一遍原文
    with_unit = set()
    for m in re.finditer(r"(\d+)\s*(?=" + "|".join(_UNIT_AFTER) + r")",
                         narration):
        v = m.group(1)
        if not _YEAR.match(v):
            with_unit.add(v)
    ns |= with_unit

    miss = [n for n in ns if substantive(n)
            and not any(_same_num(n, o) for o in os_)]
    return sorted(miss, key=lambda x: -len(x))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", default="2026-W41")
    ap.add_argument("--bootstrap", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    sys.path.insert(0, str(ROOT / "episodes" / args.ep / "scripts"))
    d = ROOT / "episodes" / args.ep
    pub = d / "publish"
    pub.mkdir(parents=True, exist_ok=True)
    spec_p = pub / "分屏表.json"
    secs = load_sections(d / "内容" / "讲稿.md")

    # ---------- bootstrap：首次从引导数据建 json ----------
    if args.bootstrap or not spec_p.exists():
        rows = BOOTSTRAP.get(args.ep)
        if not rows:
            print(f"  [!] 未登记 {args.ep} 的引导数据")
            return 2
        data = {"week": args.ep, "version": 1,
                "_note": "★ 视频结构的**唯一来源**。改结构改这里，"
                         "不要改脚本逻辑。屏号即顺序；paras 是该屏在讲稿里"
                         "的段区间 [起, 止)（左闭右开）。",
                "screens": [dict(page=i, **r) for i, r in enumerate(rows, 1)]}
        spec_p.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                          encoding="utf-8")
        print(f"  ✅ 已引导生成 {spec_p.name}（{len(rows)} 屏）")

    data = json.loads(spec_p.read_text(encoding="utf-8"))
    screens = data["screens"]

    # ---------- 校验区间 ----------
    bad = 0
    for s in screens:
        n, (a, b) = s["sec"], s["paras"]
        if not secs.get(n) or not secs[n][a:b]:
            print(f"  ❌ 第 {s['page']} 屏取不到 第{n}节 段{a}-{b-1}")
            bad += 1
    if bad:
        return 2

    # ---------- 组装 ----------
    rows = []
    for s in screens:
        n, (a, b) = s["sec"], s["paras"]
        text = "\n".join(secs[n][a:b])
        chars = len(text.replace("\n", ""))
        onscreen = (s.get("head", "") + s.get("title", "")
                    + "".join(s.get("lines", [])))
        rows.append({**s, "narration": text, "chars": chars,
                     "sec_of": chars / SPEED_CPS,
                     "miss": coverage(text, onscreen)})

    total_chars = sum(r["chars"] for r in rows)
    total_sec = total_chars / SPEED_CPS

    # ---------- diff（与上一版比） ----------
    prev_p = pub / "分屏表.prev.json"
    diffs: list[str] = []
    if prev_p.exists():
        prev = {r["page"]: r for r in
                json.loads(prev_p.read_text(encoding="utf-8"))["screens"]}
        cur = {r["page"]: r for r in screens}
        for p in sorted(set(prev) | set(cur)):
            if p not in prev:
                diffs.append(f"新增 第 {p} 屏")
            elif p not in cur:
                diffs.append(f"删除 第 {p} 屏")
            elif prev[p] != cur[p]:
                what = []
                if prev[p]["paras"] != cur[p]["paras"]:
                    what.append(f"段区间 {prev[p]['paras']}→{cur[p]['paras']}")
                if prev[p].get("head") != cur[p].get("head"):
                    what.append("标题")
                if prev[p].get("lines") != cur[p].get("lines"):
                    what.append("要点")
                diffs.append(f"改 第 {p} 屏（{'、'.join(what)}）")

    # ---------- 输出 markdown ----------
    L: list[str] = []
    add = L.append
    add(f"# 分屏表 · {args.ep}")
    add("")
    add(f"> **这一份是纯文本，不渲染任何图** —— 视频结构的审查在这里完成。")
    add(f"> 定稿后再渲染素材，那时只需抽查渲染有无画错。")
    add("")
    add(f"**{len(rows)} 屏 / {total_chars} 字 / 约 {total_sec/60:.1f} 分钟**"
        f"（语速 {SPEED_CPS} 字/秒）")
    add("")
    if diffs:
        add(f"## 本次改动（{len(diffs)} 处）")
        add("")
        for x in diffs:
            add(f"- {x}")
        add("")
        add("> **只看上面这几屏即可**，其余未变。")
    else:
        add("## 本次改动")
        add("")
        add("- 无（与上一版一致）")
    add("")

    add("## 一、总览表")
    add("")
    add("| 屏 | 画面标题 | 画面要点 | 口播字数 | 约秒 |")
    add("|----|---------|---------|---------|-----|")
    for r in rows:
        lines = r.get("lines", [])
        brief = " ｜ ".join(x.strip() for x in lines[:3])
        if len(lines) > 3:
            brief += f" ｜(+{len(lines)-3})"
        brief = brief.replace("|", "/")[:60]
        head = (r.get("head") or r.get("title", "")).replace("|", "/")
        mark = " ⚠️" if r["miss"] else ""
        add(f"| {r['page']} | {head}{mark} | {brief} | {r['chars']} "
            f"| {r['sec_of']:.0f} |")
    add("")
    add("> ⚠️ = 覆盖度自检有提示（口播里的数字可能没上画面），见第三节。")
    add("")

    add("## 二、逐屏详表（含口播全文）")
    add("")
    add("> 判断「这一屏讲的是不是标题说的那件事」，必须能看到口播全文。")
    add("")
    for r in rows:
        head = r.get("head") or r.get("title", "")
        add(f"### 第 {r['page']} 屏　{head}")
        add("")
        add(f"- 版式：`{r.get('kind','bullets')}`　"
            f"讲稿：第 {r['sec']} 节 段 {r['paras'][0]}-{r['paras'][1]-1}　"
            f"{r['chars']} 字 ≈ {r['sec_of']:.0f} 秒")
        add("")
        add("**画面要点**")
        add("")
        for x in (r.get("lines") or []):
            add(f"- {x}")
        if r.get("big"):
            add(f"- 大数字：**{r['big']}** — {r.get('big_label','')}")
        add("")
        add("<details><summary>这一屏念的话（点开）</summary>")
        add("")
        for para in r["narration"].split("\n"):
            add(para)
            add("")
        add("</details>")
        add("")

    hit = [r for r in rows if r["miss"]]
    add("## 三、覆盖度自检")
    add("")
    if not hit:
        add("✅ 未发现「口播有数字、画面没有」的情况。")
    else:
        add("以下屏的**口播里出现了数字，但画面要点里没有**。")
        add("**不一定是错**（不是每个数字都该上画面），请人眼判断：")
        add("")
        for r in hit:
            head = r.get("head") or r.get("title", "")
            add(f"- **第 {r['page']} 屏**（{head}）："
                f"未上画面的数字 `{'`, `'.join(r['miss'][:8])}`")
    add("")
    add("## 四、这一版之后要做什么")
    add("")
    add("1. 确认上面的分屏与要点 —— **只改 `publish/分屏表.json`**，"
        "改完重跑本脚本即可（毫秒级）")
    add("2. 定稿后再渲染：`render_slides16x9.py` → `make_manifest.py` "
        "→ `make_preflight_doc.py`（那时只抽查）")
    add("3. 最后配音")

    out = pub / "分屏表.md"
    if not args.check:
        out.write_text("\n".join(L), encoding="utf-8")
        # 记下本版，供下次 diff
        (pub / "分屏表.prev.json").write_text(
            json.dumps({"screens": screens}, ensure_ascii=False, indent=2),
            encoding="utf-8")

    print(f"  {len(rows)} 屏 / {total_chars} 字 / 约 {total_sec/60:.1f} 分钟")
    print(f"  本次改动 {len(diffs)} 处"
          + (f"：{'；'.join(diffs[:4])}" if diffs else ""))
    print(f"  覆盖度自检：{len(hit)} 屏有提示"
          + (f"（{'、'.join(str(r['page']) for r in hit)}）" if hit else " ✅"))
    if not args.check:
        print(f"  ✅ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
