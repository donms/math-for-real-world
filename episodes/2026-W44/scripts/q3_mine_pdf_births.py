#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W44 取数 · 从已缓存的统计局 PDF 里挖**出生人口逐年序列**。

## 背景（一个我之前的误判）

我先前把这个 360 页 PDF 判为"《金砖国家联合统计手册》，跨国对照，无用"。
但检索结果显示：**它的第 141 页附近有一张 `2000/2015/2016/2017/2018/…`
为表头的多年份表** —— 那正是我要的**出生人口序列**。

⇒ 教训：**"这不是我要的那类文档"不等于"里面没有我要的表"**。
   对长文档应当**先扫关键词所在页**，再判断有没有用。

本脚本：扫全 PDF 找含"出生人口"的页，抽出年份—数值对。

用法：
    $PY q3_mine_pdf_births.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
# ⚠️ 该 PDF 最初被误存到 `<LOCAL_PATH> 层级算错），
#    已归位到期目录的 data/raw/stats/。原始下载页见 results/统计局PDF_出生人口勘探.md
PDF = EP / "data" / "raw" / "stats" / "stats_yearbook_or_handbook.pdf"
RES = EP / "results"
CLEAN = EP / "data" / "clean"

out: list[str] = []


def P(s: str = "") -> None:
    out.append(s)
    print(s, flush=True)


def main() -> int:
    import fitz
    RES.mkdir(parents=True, exist_ok=True)
    CLEAN.mkdir(parents=True, exist_ok=True)

    P("=" * 100)
    P("  从统计局 PDF 挖出生人口序列")
    P("=" * 100)
    P(f"  文件：{PDF}")
    doc = fitz.open(PDF)
    P(f"  页数：{len(doc)}")

    # 找含"出生人口"的页
    hit_pages = []
    for i in range(len(doc)):
        t = doc[i].get_text()
        if "出生人口" in t or "出生率" in t:
            hit_pages.append(i)
    P(f"\n  含「出生人口/出生率」的页：{len(hit_pages)} 页 → "
      f"{[p+1 for p in hit_pages][:30]}")

    tables: list[dict] = []
    for i in hit_pages:
        t = doc[i].get_text()
        # 抽"年份 数值"对
        pairs = re.findall(r"\b(20[0-2]\d)\b[^\d\n]{0,30}?([\d,]{3,7}(?:\.\d+)?)",
                           t)
        P(f"\n{'━'*100}")
        P(f"  ── 第 {i+1} 页 ──（年份-数值对 {len(pairs)} 组）")
        for line in t.split("\n")[:45]:
            if line.strip():
                P(f"    {line.strip()[:104]}")
        if pairs:
            P(f"    年份数值对：{pairs[:18]}")
        tables.append({"页": i + 1, "年份数值对": pairs[:40],
                       "正文": t[:4000]})

    (RES / "统计局PDF_出生人口勘探.md").write_text(
        "# 统计局 PDF · 出生人口勘探\n\n" + "\n".join(out),
        encoding="utf-8")
    (CLEAN / "pdf_birth_probe.json").write_text(
        json.dumps(tables, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  → {RES / '统计局PDF_出生人口勘探.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
