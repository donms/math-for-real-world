#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""扫 `data/raw/stats/` 下**所有**已抓到手的 HTML/PDF，抽"全年出生人口 X 万人"。

## 为什么要写这个

出生人口是本题唯一的自变量，而逐年官方值尚未凑齐。
子代理正在逐年抓各年公报，但抓回来的页面**已经落盘** ——
直接扫这些本地文件最快，也能**验证子代理的抓取是否真的含有目标数字**。

判据：**从落盘文件里抽到**原文句，才算确认（不接受检索摘要）。

用法：
    $PY q4_scan_births.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
RAW = EP / "data" / "raw" / "stats"
RES = EP / "results"
CLEAN = EP / "data" / "clean"

# 出生人口：允许"全年出生人口 X 万人"或"出生人口 X 万人"
PAT_BIRTH = re.compile(r"(?:全年)?出生人口\s*(?:为)?\s*([\d,]{3,6}(?:\.\d+)?)\s*万人")
PAT_RATE = re.compile(r"出生率\s*(?:为)?\s*([\d.]+)\s*(?:‰|&permil;|千分之)")
# 年份：优先取"XXXX年国民经济和社会发展统计公报"或"全年"上下文
PAT_YEAR_TITLE = re.compile(r"(20[0-2]\d)\s*年(?:国民经济和社会发展)?统计公报")


def strip_tags(h: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", h, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", t)


def text_of(p: Path) -> str:
    if p.suffix.lower() == ".pdf":
        try:
            import fitz
            d = fitz.open(p)
            return "\n".join(d[i].get_text() for i in range(len(d)))
        except Exception:                      # noqa: BLE001
            return ""
    try:
        return strip_tags(p.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        try:
            return strip_tags(p.read_text(encoding="gb18030"))
        except Exception:                      # noqa: BLE001
            return ""
    except Exception:                          # noqa: BLE001
        return ""


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    CLEAN.mkdir(parents=True, exist_ok=True)
    out: list[str] = []
    P = out.append

    P("# 出生人口 · 本地落盘文件扫描结果")
    P("")
    P("> 判据：**必须从落盘文件抽到原文句**才算确认（不接受检索摘要）")
    P("")

    files = sorted(RAW.glob("*"))
    P(f"扫描 `data/raw/stats/` 共 {len(files)} 个文件")
    P("")

    hits: dict[int, dict] = {}
    for p in files:
        if p.suffix.lower() not in (".html", ".htm", ".pdf", ".txt"):
            continue
        txt = text_of(p)
        if len(txt) < 500:
            continue
        ms = list(PAT_BIRTH.finditer(txt))
        if not ms:
            continue
        # 年份：先看标题，再看文件名
        ym = PAT_YEAR_TITLE.search(txt)
        year = int(ym.group(1)) if ym else None
        if year is None:
            fm = re.search(r"(20[0-2]\d)", p.stem)
            year = int(fm.group(1)) if fm else None
        P(f"### `{p.name}`　({p.stat().st_size/1024:.0f} KB)")
        P("")
        if year:
            P(f"- 判定年份：**{year}**")
        for m in ms[:4]:
            a, b = max(0, m.start() - 45), min(len(txt), m.end() + 70)
            ev = txt[a:b].strip()
            val = float(m.group(1).replace(",", ""))
            rm = PAT_RATE.search(txt)
            P(f"- 抽到 **{val} 万人**　← …{ev}…")
            if year and 1900 < val < 2500:
                prev = hits.get(year)
                if prev is None or prev["值"] != val:
                    hits[year] = {
                        "年份": year, "出生人口_万人": val,
                        "出生率_千分": float(rm.group(1)) if rm else "",
                        "来源文件": p.name, "证据": ev,
                        "冲突": prev is not None,
                    }
        P("")

    P("## 汇总：按年份")
    P("")
    P("| 年份 | 出生人口(万人) | 出生率(‰) | 来源文件 |")
    P("|---|---|---|---|")
    for y in sorted(hits):
        h = hits[y]
        mark = " ⚠️冲突" if h.get("冲突") else ""
        P(f"| {y} | {h['出生人口_万人']} | {h['出生率_千分']} | "
          f"`{h['来源文件']}`{mark} |")
    P("")
    confirmed = sorted(hits)
    P(f"**已确认 {len(confirmed)} 年**：{confirmed}")
    P("")
    P("预期区间 2016–2025，缺：" +
      str([y for y in range(2016, 2026) if y not in hits]))

    (RES / "出生人口_本地扫描.md").write_text("\n".join(out), encoding="utf-8")
    (CLEAN / "births_scanned.json").write_text(
        json.dumps(hits, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] 确认 {len(confirmed)} 年: {confirmed}")
    print(f"[ok] {RES / '出生人口_本地扫描.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
