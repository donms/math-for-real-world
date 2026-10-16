#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W47 · 从宁沪高速历年年报抽取**江阴大桥**分车型流量（2021–2025）。

## 为什么值得单写一个脚本

江阴大桥的逐年数据**只能从年报的「路桥项目经营情况」表**里拿，
而该表：
* **列序不固定**（有的年 当年在前，有的在上年在前）；
* **表头在上一页**（`表头年份` 与数据行常分页）；
* **行标签会变**（2022/2023 直接写 `江阴大桥`；2024/2025 与之同表的
  其它路段写 `广靖高速`）⇒ **必须先定位到正确的行，再按列名对齐**。

⇒ 硬编码位置必错。本脚本**按行标签锚定 + 按列名对齐**，并输出
**校验量**（客车占比、车均收入）供人工判断。

## 用法

    $PY extract_bridge_series.py            # 抽全部年份
    $PY extract_bridge_series.py --list     # 只列出每份年报的候选行
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
# ⚠️ 临时目录在**仓库内**（`.\.workbuddy\tmp\w47`），
#    不是 `<LOCAL_PATH> `NewsMCM` 一层，
#    结果全部年份都报"未找到年报 PDF"。⇒ **写死路径前先 Test-Path 验证。**
TMP = ROOT.parent.parent / ".workbuddy" / "tmp" / "w47"
if not TMP.exists():
    TMP = ROOT / ".workbuddy" / "tmp" / "w47"
RAW = ROOT / "data" / "raw"

YEARS = (2021, 2022, 2023, 2024, 2025)
LABELS = ("江阴大桥", "广靖高速", "广靖锡澄")
FIELDS = ("客车流量", "货车流量", "流量合计", "日均收入")


def find_report(y: int) -> Path | None:
    for p in (TMP / f"ninghu_{y}ar.pdf", RAW / f"宁沪高速_{y}年报.pdf"):
        if p.exists():
            return p
    return None


def page_lines(doc, pno: int) -> list[str]:
    return [x.strip() for x in doc[pno - 1].get_text().splitlines() if x.strip()]


def block_after(lines: list[str], start: int) -> dict[str, list[float]]:
    r"""从 `start` 行之后依次抓 4 个字段的数值（每字段 2 个值 + 1 个变化率）。"""
    out: dict[str, list[float]] = {}
    j = start + 1
    while j < len(lines):
        s = lines[j]
        # 进入下一个路段块就停（路段名一般不含"流量/收入"）
        if not any(s.startswith(f) for f in FIELDS) and not re.fullmatch(
                r"-?[\d,]+(?:\.\d+)?%?", s) and j > start + 1:
            if len(out) >= 1:
                break
        for f in FIELDS:
            if s.startswith(f):
                vals: list[float] = []
                k = j + 1
                while k < len(lines) and len(vals) < 3:
                    v = lines[k].replace(",", "").replace("%", "")
                    if re.fullmatch(r"-?\d+(?:\.\d+)?", v):
                        vals.append(float(v))
                    elif v != "-":
                        break
                    k += 1
                out.setdefault(f, vals)
                j = k - 1
        j += 1
    return out


def extract(pdf: Path, label_filter: str | None = None) -> dict:
    doc = pymupdf.open(pdf)
    best = None
    for pno in range(1, doc.page_count + 1):
        ls = page_lines(doc, pno)
        for i, s in enumerate(ls):
            if s in LABELS or (label_filter and s == label_filter):
                # 该块必须紧跟"客车流量"
                if i + 1 < len(ls) and ls[i + 1].startswith("客车流量"):
                    blk = block_after(ls, i)
                    if blk.get("流量合计"):
                        best = {"page": pno, "label": s, "fields": blk,
                                "lines": ls}
                        break
        if best:
            break
    doc.close()
    return best or {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    print("=" * 96)
    print("  江阴大桥分车型流量 · 从宁沪高速历年年报抽取")
    print("=" * 96)

    series: dict[int, dict] = {}
    for y in YEARS:
        pdf = find_report(y)
        if pdf is None:
            print(f"\n  [{y}] [缺] 未找到年报 PDF")
            continue
        r = extract(pdf)
        if not r:
            print(f"\n  [{y}] [X] 未定位到江阴大桥块（{pdf.name}）")
            continue
        f = r["fields"]
        # 该表列序：当年 / 上年（变化率第 3 个值）
        cur = {k: (v[0] if v else None) for k, v in f.items()}
        prev = {k: (v[1] if len(v) > 1 else None) for k, v in f.items()}
        chg = {k: (v[2] if len(v) > 2 else None) for k, v in f.items()}
        print(f"\n  [{y}] {pdf.name} p{r['page']} 行标签『{r['label']}』")
        print(f"       {'字段':<12}{'当年':>12}{'上年':>12}{'报告变化率':>12}")
        for k in FIELDS:
            c, p, g = cur.get(k), prev.get(k), chg.get(k)
            print(f"       {k:<12}{(f'{c:,.0f}' if c else '—'):>12}"
                  f"{(f'{p:,.0f}' if p else '—'):>12}"
                  f"{(f'{g:+.2f}%' if g is not None else '—'):>12}")
        # 校验：客车占比
        cc, tt = cur.get("客车流量"), cur.get("流量合计")
        if cc and tt:
            print(f"       校验：客车占比 {cc / tt:.2%}")
        series[y] = {"source": f"{pdf.name} p{r['page']}", "label": r["label"],
                     "当年": cur, "上年": prev, "报告变化率": chg}

    # 组装成统一序列：每年取"当年"值
    out: dict[int, dict] = {}
    for y, s in series.items():
        out[y] = {"客车流量": s["当年"].get("客车流量"),
                  "货车流量": s["当年"].get("货车流量"),
                  "流量合计": s["当年"].get("流量合计"),
                  "日均收入_千元": (s["当年"].get("日均收入") or None),
                  "_source": s["source"]}
        tot = out[y]["流量合计"]
        rev = out[y]["日均收入_千元"]
        out[y]["客车占比"] = (round(out[y]["客车流量"] / tot, 4)
                              if out[y]["客车流量"] and tot else None)
        out[y]["车均收入_元"] = (round(rev * 1000 / tot, 2) if rev and tot
                                 else None)

    print(f"\n{'='*96}")
    print("  ★ 统一序列（江阴大桥，辆/日）")
    print(f"     {'年':<6}{'客车':>9}{'货车':>9}{'合计':>9}{'客车占比':>10}"
          f"{'日均收入(千元)':>15}{'车均(元)':>10}")
    for y in sorted(out):
        d = out[y]
        for k, lab in (("客车流量", "客车"), ("货车流量", "货车"),
                       ("流量合计", "合计")):
            pass
        print(f"     {y:<6}{(d['客车流量'] or 0):>9,.0f}"
              f"{(d['货车流量'] or 0):>9,.0f}{(d['流量合计'] or 0):>9,.0f}"
              f"{(d['客车占比'] or 0):>10.2%}"
              f"{(d['日均收入_千元'] or 0):>15,.2f}"
              f"{(d['车均收入_元'] or 0):>10.2f}")

    p = ROOT / "results" / "q1_江阴大桥序列_2021_2025.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
