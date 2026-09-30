#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W44 取数 · 逐年**出生人口**（B 级：国民经济和社会发展统计公报原文）。

## 为什么要逐年抓

出生人口是本题**唯一的自变量**：入园需求 ≈ f(出生人口, 入园率)。
选题阶段我用的是检索摘要（2016=1786万、2023=902万、2025≈900万），
其中 **2025 的 ≈900 万是错的**（官方 792 万）——
**自变量的错会直接放大到全部预测**，所以逐年回原文钉死。

## 产出

```
data/clean/births.csv          年份, 出生人口(万人), 出生率(‰), 来源
results/出生人口核对.md         逐年表 + 每条的原文证据句
```

用法：
    $PY q2_birth_series.py
"""
from __future__ import annotations

import csv
import json
import re
import ssl
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
RAW = EP / "data" / "raw" / "stats"
CLEAN = EP / "data" / "clean"
RES = EP / "results"

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
_CTX.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
try:
    _CTX.set_ciphers("DEFAULT@SECLEVEL=1")
except Exception:                              # noqa: BLE001
    pass
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120"}

# 逐年公报（尽量取官方/权威转载；stats.gov.cn 对脚本 403）
PAGES: list[tuple[int, str, str]] = [
    (2024, "2024公报·地方政府转载",
     "http://tqx.gov.cn/gongkai/show/"
     "508dc7f99367db87d1d4831c1e1534c9.html"),
    (2025, "2025公报·求是网",
     "https://www.qstheory.com/20260301/06955fa56347457a9db78f6d7692f5f2/"
     "c.html"),
]

# 已由上一脚本确认的年份（附 URL），一并纳入
KNOWN_OK = {
    2025: ("求是网转载 2025 公报",
           "https://www.qstheory.com/20260301/06955fa56347457a9db78f6d7692f5f2/c.html"),
    2023: ("新浪财经 2024-01-17 统计局发布",
           "https://finance.sina.com.cn/jjxw/2024-01-17/doc-inacvauf3348102.shtml"),
}


def get(url: str) -> tuple[int, str]:
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=30, context=_CTX)
        b = r.read()
        st = r.status
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:                          # noqa: BLE001
        return -1, ""
    for enc in ("utf-8", "gb18030"):
        try:
            return st, b.decode(enc)
        except UnicodeDecodeError:
            continue
    return st, b.decode("utf-8", "ignore")


def strip_tags(h: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", h, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", t)


def extract(txt: str) -> tuple[float | None, float | None, str]:
    """抽 (出生人口万人, 出生率‰, 证据句)。"""
    m = re.search(r"全年出生人口\s*([\d,]+(?:\.\d+)?)\s*万人", txt)
    if not m:
        m = re.search(r"出生人口\s*([\d,]+(?:\.\d+)?)\s*万人", txt)
    if not m:
        return None, None, ""
    pop = float(m.group(1).replace(",", ""))
    a, b = max(0, m.start() - 30), min(len(txt), m.end() + 90)
    ev = txt[a:b].strip()
    r = re.search(r"出生率[为]?\s*([\d.]+)\s*(?:‰|&permil;|千分)", txt)
    rate = float(r.group(1)) if r else None
    return pop, rate, ev


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    CLEAN.mkdir(parents=True, exist_ok=True)
    RES.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    out: list[str] = []
    P = out.append

    P("# 出生人口逐年核对（B 级：统计公报原文）")
    P("")
    P("> 抓取日 2026-09-26　｜　脚本 `scripts/q2_birth_series.py`")
    P("> ⚠️ 出生人口是本题**唯一的自变量**，故逐年回原文。")
    P("")

    seen: dict[int, dict] = {}

    for year, name, url in PAGES:
        st, h = get(url)
        if st != 200 or len(h) < 2000:
            print(f"  [{year}] ❌ {name} status={st}")
            continue
        fp = RAW / f"bulletin_{year}.html"
        fp.write_text(h, encoding="utf-8")
        pop, rate, ev = extract(strip_tags(h))
        print(f"  [{year}] {name}: 出生 {pop} 万人  率 {rate} ‰")
        if pop:
            seen[year] = {"年份": year, "出生人口_万人": pop,
                          "出生率_千分": rate or "", "来源": name,
                          "来源URL": url, "证据": ev}

    # 把已知确认的年份并入
    for y, (name, url) in KNOWN_OK.items():
        if y in seen:
            continue
        st, h = get(url)
        if st == 200 and len(h) >= 2000:
            (RAW / f"bulletin_{y}.html").write_text(h, encoding="utf-8")
            pop, rate, ev = extract(strip_tags(h))
            if pop:
                seen[y] = {"年份": y, "出生人口_万人": pop,
                           "出生率_千分": rate or "", "来源": name,
                           "来源URL": url, "证据": ev}
                print(f"  [{y}] {name}: 出生 {pop} 万人")

    rows = [seen[y] for y in sorted(seen)]

    P("## 一、已确认的年份")
    P("")
    P("| 年份 | 出生人口(万人) | 出生率(‰) | 来源 |")
    P("|---|---|---|---|")
    for r in rows:
        P(f"| {r['年份']} | {r['出生人口_万人']} | {r['出生率_千分']} | "
          f"{r['来源']} |")
    P("")
    P("## 二、原文证据")
    P("")
    for r in rows:
        P(f"- **{r['年份']}**：…{r['证据'][:150]}…")
        P(f"  - {r['来源URL']}")
    P("")
    P("## 三、⚠️ 仍缺的年份")
    P("")
    want = list(range(2016, 2026))
    miss = [y for y in want if y not in seen]
    if miss:
        P(f"- 缺 {miss}")
        P("- 处理：这些年份需从**各年统计公报**补抓；")
        P("  在补齐前，模型中**不得使用未经原文确认的出生人口**。")
    else:
        P("- 无（2016–2025 齐全）")

    csvp = CLEAN / "births.csv"
    with csvp.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["年份", "出生人口_万人", "出生率_千分",
                                          "来源", "来源URL"],
                           extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    (RES / "出生人口核对.md").write_text("\n".join(out), encoding="utf-8")
    (CLEAN / "births.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[ok] {csvp}（{len(rows)} 年）")
    print(f"[ok] {RES / '出生人口核对.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
