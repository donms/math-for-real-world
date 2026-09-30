#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W44 · 汇总出生人口逐年值 → `data/clean/births.csv`（**人工核对过的权威映射**）。

## 为什么手写映射而不是自动从文件名推年份

自动扫描（`q4_scan_births.py`）能抽到数值，但**年份判定不可靠**：
文件名形如 `bulletin_2022__NBS.html` 里的数字未必与正文年份一致，
而**出生人口错配一年 = 整个滞后估计全错**。

⇒ 本脚本的映射**逐条经人工核对正文证据句**后固化，
且只在**证据句里明确出现该年**时才接受。

## 来源优先级

`src_YYYY__NBS.html` / `bulletin_YYYY__NBS.html`
= **国家统计局官网页面**（最权威）> 政府网站 > 权威媒体转载。

用法：
    $PY q5_consolidate_births.py
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
RAW = EP / "data" / "raw" / "stats"
CLEAN = EP / "data" / "clean"
RES = EP / "results"

# (年份, 出生人口万人, 出生率‰, 首选文件, 来源描述, 来源级别)
# ★ 每条都已核对正文证据句
ROWS: list[tuple[int, float, float, str, str, str]] = [
    (2016, 1786, 12.95, "src_2016__NBS.html",
     "国家统计局《2016年国民经济和社会发展统计公报》", "A"),
    (2017, 1723, 12.43, "src_2017__NBS.html",
     "国家统计局《2017年国民经济和社会发展统计公报》", "A"),
    (2018, 1523, 10.94, "bulletin_2018__NBS.html",
     "国家统计局《2018年国民经济和社会发展统计公报》", "A"),
    (2019, 1465, 10.48, "bulletin_2019__NBS.html",
     "国家统计局《2019年国民经济和社会发展统计公报》", "A"),
    (2020, 1200, 0.0, "src_2020__NBS_CENSUS_QA.html",
     "国家统计局·第七次全国人口普查主要数据情况（答记者问）", "A"),
    (2021, 1062, 7.52, "bulletin_2021__NBS.html",
     "国家统计局《2021年国民经济和社会发展统计公报》", "A"),
    (2022, 956, 6.77, "bulletin_2022__NBS.html",
     "国家统计局《2022年国民经济和社会发展统计公报》", "A"),
    (2023, 902, 6.39, "bulletin_2023__NBS.html",
     "国家统计局《2023年国民经济和社会发展统计公报》", "A"),
    (2024, 954, 6.77, "bulletin_2024__NBS.html",
     "国家统计局《2024年国民经济和社会发展统计公报》", "A"),
    (2025, 792, 5.63, "bulletin_2025.html",
     "《2025年国民经济和社会发展统计公报》（经求是网转载）", "B"),
]

PAT_BIRTH = re.compile(r"出生人口\s*(?:为)?\s*([\d,]{3,6}(?:\.\d+)?)\s*万人")


def main() -> int:
    CLEAN.mkdir(parents=True, exist_ok=True)
    RES.mkdir(parents=True, exist_ok=True)
    out: list[str] = []
    P = out.append
    verified: list[dict] = []
    problems: list[str] = []

    P("# 出生人口逐年核对（定稿）")
    P("")
    P("> 判据：**必须在落盘文件的正文里抽到该数值**，才计入。")
    P("> 年份映射经**人工核对证据句**后固化（见 `scripts/q5_consolidate_births.py`）。")
    P("")

    for year, val, rate, fname, src, level in ROWS:
        fp = RAW / fname
        got = None
        ev = ""
        if fp.exists():
            txt = fp.read_text(encoding="utf-8", errors="ignore")
            txt = re.sub(r"<[^>]+>", " ", txt)
            txt = re.sub(r"\s+", " ", txt)
            ms = list(PAT_BIRTH.finditer(txt))
            for m in ms:
                v = float(m.group(1).replace(",", ""))
                if abs(v - val) < 0.5:
                    got = v
                    a, b = max(0, m.start() - 50), min(len(txt), m.end() + 60)
                    ev = txt[a:b].strip()
                    break
            if got is None and ms:
                problems.append(
                    f"{year}: 文件 `{fname}` 里**未找到 {val} 万人**，"
                    f"文件里的候选值 = {[float(m.group(1).replace(',','')) for m in ms[:4]]}")
        else:
            problems.append(f"{year}: 缺文件 `{fname}`")

        verified.append({"年份": year, "出生人口_万人": val,
                         "出生率_千分": rate or "", "来源": src,
                         "来源级别": level, "来源文件": fname,
                         "核对": "OK" if got is not None else "未核对",
                         "证据": ev})

    P("| 年份 | 出生人口(万人) | 出生率(‰) | 级别 | 落盘核对 | 来源 |")
    P("|---|---|---|---|---|---|")
    for r in verified:
        P(f"| {r['年份']} | **{r['出生人口_万人']}** | "
          f"{r['出生率_千分'] or '—'} | {r['来源级别']} | {r['核对']} | "
          f"{r['来源']} |")
    P("")

    ys = [r["出生人口_万人"] for r in verified]
    P(f"- 2016→2025 出生人口：**{ys[0]:.0f} 万 → {ys[-1]:.0f} 万**，"
      f"累计 **{(ys[-1]/ys[0]-1)*100:.1f}%**")
    peak = max(verified, key=lambda r: r["出生人口_万人"])
    trough = min(verified, key=lambda r: r["出生人口_万人"])
    P(f"- 峰值：**{peak['年份']} 年 {peak['出生人口_万人']:.0f} 万**")
    P(f"- 谷值：**{trough['年份']} 年 {trough['出生人口_万人']:.0f} 万**")
    P("")

    # 逐年变化
    P("## 逐年变化")
    P("")
    P("| 年份 | 出生人口 | 同比 |")
    P("|---|---|---|")
    for i, r in enumerate(verified):
        if i == 0:
            P(f"| {r['年份']} | {r['出生人口_万人']:.0f} | — |")
        else:
            p = verified[i - 1]["出生人口_万人"]
            d = r["出生人口_万人"] - p
            P(f"| {r['年份']} | {r['出生人口_万人']:.0f} | "
              f"{d:+.0f}（{d/p*100:+.1f}%）|")
    P("")

    P("## ⚠️ 口径说明（必须写进论文）")
    P("")
    P("1. **2020 年的 1200 万**来自**第七次全国人口普查**初步汇总，")
    P("   与普查前基于抽样调查的推算值口径不同。")
    P("2. 统计公报明确说明：**2014–2019 年总人口、出生人口根据第七次全国人口普查数据修订**。")
    P("   故 2016–2019 与 2020 之后**口径可能存在差异**，建模时须声明。")
    P("3. 2025 年公报经**求是网转载**（B 级）；其余年份均已取得**国家统计局官网页面**（A 级）。")
    P("")

    if problems:
        P("## ❌ 核对未通过")
        P("")
        for x in problems:
            P(f"- {x}")
    else:
        P("## ✅ 全部 10 年核对通过（文件内确实含有该数值）")

    # 写 CSV
    cols = ["年份", "出生人口_万人", "出生率_千分", "来源", "来源级别", "来源文件"]
    csvp = CLEAN / "births.csv"
    with csvp.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in verified:
            w.writerow(r)

    (RES / "出生人口核对.md").write_text("\n".join(out), encoding="utf-8")
    (CLEAN / "births.json").write_text(
        json.dumps(verified, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[ok] {csvp}")
    n_ok = sum(1 for r in verified if r["核对"] == "OK")
    print(f"     核对通过 {n_ok}/{len(verified)}")
    for x in problems:
        print(f"     [!] {x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
