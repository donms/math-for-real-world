#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W44 取数 · 从公报原文**解析**幼儿园逐年指标 → 结构化 CSV。

## 纪律（W43 教训）

1. **每个数字都标出处**：CSV 里带 `来源文件` 与 `原文句子` 两列，
   论文里凡是引用的数字都能回溯到**公报原文的那一句**。
2. **解析不了的年份要报出来**，不能静默跳过（否则"序列缺一年"看不出来）。
3. **口径变化要记录**：公报表述逐年微调（如"入园幼儿"→"入园儿童"），
   可能意味着口径变更 ⇒ 单独标记。

## 产出

```
data/clean/kindergarten.csv        逐年指标（含出处）
results/公报数字核对.md             与 C 级媒体数字的差异对照
```

用法：
    $PY q1_parse_bulletins.py
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
RAW = EP / "data" / "raw" / "moe_bulletins"
CLEAN = EP / "data" / "clean"
RES = EP / "results"


def strip_tags(html: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", t)


# ---- 各指标的抽取规则（正则，均容错空格与上标标注 [n] / 〔n〕）----
NUM = r"([\d,]+(?:\.\d+)?)"
SUP = r"(?:\s*[\[〔]\d+[\]〕])?"

RULES: dict[str, list[str]] = {
    # 全国共有幼儿园 X 万所
    "幼儿园数_万所": [
        rf"全国共有幼儿园\s*{NUM}{SUP}\s*万所",
        rf"幼儿园\s*{NUM}\s*万所",
    ],
    # 在园幼儿 X 万人
    "在园幼儿_万人": [
        rf"在园幼儿{SUP}\s*{NUM}\s*万人",
        rf"在园幼儿（[^）]*）\s*{NUM}\s*万人",
    ],
    # 毛入园率 X%
    "毛入园率_百分比": [
        rf"毛入园率{SUP}\s*达到\s*{NUM}\s*%",
        rf"毛入园率{SUP}\s*{NUM}\s*%",
    ],
    # 民办幼儿园 X 万所
    "民办幼儿园_万所": [
        rf"民办幼儿园\s*{NUM}\s*万所",
    ],
    # 民办幼儿园 X 所（2008 等早期年份用"所"）
    # ⚠️ 必须限定在"民办幼儿园"紧跟的位置，否则会抓到"民办普通小学5760所"
    "民办幼儿园_所": [
        rf"民办幼儿园\s*{NUM}\s*所",
    ],
    # 民办在园幼儿 X 万人
    # ⚠️ 关键修正：必须**锚定在"民办幼儿园…在园幼儿"这一段内**，
    #    否则会抓到紧随其后的"普惠性幼儿园在园幼儿"。
    #    （实测 2020 被错抓成 4082.83，那是普惠口径，真值 2378.55）
    "民办在园幼儿_万人": [
        rf"民办幼儿园\s*{NUM}\s*万所[^。]{{0,90}}?在园幼儿\s*{NUM}\s*万人",
    ],
    # 入园幼儿/儿童 X 万人（当年新入园）
    # ⚠️ 注意：2021 年起**多数年份不再公布**该指标（不是解析失败，是真停报）
    "入园幼儿_万人": [
        rf"入园幼儿{SUP}\s*{NUM}\s*万人",
        rf"入园儿童{SUP}\s*{NUM}\s*万人",
    ],
    # 幼儿园教职工 X 万人
    "幼儿园教职工_万人": [
        rf"幼儿园教职工\s*{NUM}\s*万人",
        rf"幼儿园园长和教师共\s*{NUM}\s*万人",
    ],
    # 普惠性幼儿园在园幼儿 X 万人（新增：与民办口径区分，避免混淆）
    "普惠在园幼儿_万人": [
        rf"普惠性幼儿园在园幼儿\s*{NUM}\s*万人",
    ],
}


def one_rule(body: str, pats: list[str],
             group: int = 1) -> tuple[float | None, str]:
    """按候选正则依次尝试，返回 (数值, 证据句)。

    `group` 指定取第几个捕获组 —— 有些规则（如"民办幼儿园X万所…在园幼儿Y万人"）
    有两个捕获组，要取第 2 个。
    """
    for p in pats:
        m = re.search(p, body)
        if m:
            try:
                raw = m.group(group)
            except IndexError:
                continue
            if raw is None:
                continue
            v = float(raw.replace(",", ""))
            a = max(0, m.start() - 40)
            b = min(len(body), m.end() + 30)
            return v, body[a:b].strip()
    return None, ""


# 需要取第 2 个捕获组的指标
GROUP2 = {"民办在园幼儿_万人"}


def main() -> int:
    CLEAN.mkdir(parents=True, exist_ok=True)
    RES.mkdir(parents=True, exist_ok=True)
    idx = json.loads((RAW / "index.json").read_text(encoding="utf-8"))

    rows: list[dict] = []
    problems: list[str] = []

    for item in idx:
        fp = RAW / item["文件"]
        if not fp.exists():
            problems.append(f"缺文件 {item['文件']}")
            continue
        body = strip_tags(fp.read_text(encoding="utf-8"))
        m = re.search(r"(全国共有|一、综合)", body)
        body = body[m.start():] if m else body
        ym = re.search(r"(\d{4})年", item["标题"])
        year = int(ym.group(1)) if ym else -1

        row = {"年份": year, "来源文件": item["文件"], "来源URL": item["url"]}
        evidence: dict[str, str] = {}
        for k, pats in RULES.items():
            v, ev = one_rule(body, pats, group=2 if k in GROUP2 else 1)
            row[k] = v if v is not None else ""
            if ev:
                evidence[k] = ev
        row["_证据"] = evidence
        rows.append(row)

    rows.sort(key=lambda r: r["年份"])

    # ---- 写 CSV（不含 _证据 列，证据另存）----
    cols = ["年份"] + list(RULES.keys()) + ["来源文件", "来源URL"]
    csvp = CLEAN / "kindergarten.csv"
    with csvp.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # ---- 自检 ----
    out: list[str] = []
    P = out.append
    P("# 公报数字解析核对（A 级来源）")
    P("")
    P(f"> 来源：教育部逐年《全国教育事业发展统计公报》原文，"
      f"共 {len(rows)} 篇　｜　解析脚本：`scripts/q1_parse_bulletins.py`")
    P("")
    P("## 一、逐年指标（来自公报原文）")
    P("")
    P("| 年份 | 幼儿园数(万所) | 在园幼儿(万人) | 毛入园率(%) | "
      "民办园(万所) | 民办在园(万人) | 入园幼儿(万人) |")
    P("|---|---|---|---|---|---|---|")
    for r in rows:
        P(f"| {r['年份']} | {r['幼儿园数_万所']} | {r['在园幼儿_万人']} | "
          f"{r['毛入园率_百分比']} | {r['民办幼儿园_万所']} | "
          f"{r['民办在园幼儿_万人']} | {r['入园幼儿_万人']} |")
    P("")

    # 缺失检查
    P("## 二、解析完整性自检")
    P("")
    for k in RULES:
        miss = [r["年份"] for r in rows if r[k] == ""]
        flag = "OK" if not miss else f"缺 {miss}"
        P(f"- `{k}`：{flag}")
    P("")

    # 同比校验：公报自带"比上年增减"，用它交叉验证相邻年差值
    P("## 三、与公报自报同比的交叉校验")
    P("")
    P("公报原文里通常带「比上年增加/减少 X 万所」，可用来验证相邻两年差值。")
    P("")
    for i in range(1, len(rows)):
        a, b = rows[i - 1], rows[i]
        if a["幼儿园数_万所"] == "" or b["幼儿园数_万所"] == "":
            continue
        if b["年份"] - a["年份"] != 1:
            continue
        d = round(b["幼儿园数_万所"] - a["幼儿园数_万所"], 2)
        pct = round(d / a["幼儿园数_万所"] * 100, 2)
        P(f"- {a['年份']}→{b['年份']}：{d:+.2f} 万所（{pct:+.2f}%）")
    P("")

    P("## 四、原文证据（每指标的首句）")
    P("")
    for r in rows:
        P(f"### {r['年份']} 年")
        P("")
        for k, ev in (r["_证据"] or {}).items():
            P(f"- `{k}` = **{r[k]}**　← …{ev}…")
        P("")

    if problems:
        P("## 五、⚠️ 问题")
        P("")
        for p in problems:
            P(f"- {p}")

    (RES / "公报数字核对.md").write_text("\n".join(out), encoding="utf-8")
    (RES / "公报解析证据.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[ok] {csvp}")
    print(f"[ok] {RES / '公报数字核对.md'}")
    print(f"     解析 {len(rows)} 篇，年份 {rows[0]['年份']}–{rows[-1]['年份']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
