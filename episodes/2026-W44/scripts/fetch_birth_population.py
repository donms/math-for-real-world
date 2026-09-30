#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W44 取数 · 出生人口官方口径（B 级来源：统计公报原文）。

## 为什么要单独核

选题阶段我引用的出生人口（2016=1786万、2023=902万、2025≈900万）
**来自检索摘要，未核对原文**。而 2025 年一处检索结果说 **792 万** —— 与 ≈900 万
差距很大。**这个数直接决定"谷底有多深"，必须先钉死。**

## 做法

抓《国民经济和社会发展统计公报》原文页 → 抽"出生人口/出生率/死亡率"句子。

用法：
    $PY fetch_birth_population.py
"""
from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
RAW = EP / "data" / "raw" / "stats"
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

# 2025 年公报的多个镜像（stats.gov.cn 对脚本 403，故优先用可访问的官方转载）
TARGETS = [
    ("求是网转载·2025公报",
     "https://www.qstheory.com/20260301/06955fa56347457a9db78f6d7692f5f2/c.html"),
    ("东方财富转载·2025公报",
     "https://finance.eastmoney.com/a/202603013657643940.html"),
    ("新浪财经·2023人口数据",
     "https://finance.sina.com.cn/jjxw/2024-01-17/doc-inacvauf3348102.shtml"),
]


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


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    RES.mkdir(parents=True, exist_ok=True)
    out: list[str] = []
    found: list[dict] = []

    def P(s: str = "") -> None:
        out.append(s)
        print(s, flush=True)

    P("=" * 100)
    P("  W44 取数 · 出生人口官方口径")
    P("=" * 100)

    for name, url in TARGETS:
        st, h = get(url)
        P(f"\n{'━'*100}\n  [{name}]\n  {url}\n  status={st}  {len(h):,}B")
        if st != 200 or len(h) < 2000:
            P("  ❌ 取不到")
            continue
        fp = RAW / (re.sub(r"\W+", "_", name)[:40] + ".html")
        fp.write_text(h, encoding="utf-8")
        txt = strip_tags(h)
        # 抽出生的句子
        sents = [s.strip() for s in re.split(r"[。；]", txt)
                 if ("出生人口" in s or "出生率" in s) and re.search(r"\d", s)]
        P(f"  含「出生」的句子 {len(sents)} 条")
        for s in sents[:8]:
            P(f"    ▸ {s[:170]}")
        # 抽 年末人口 相关
        pop = [s.strip() for s in re.split(r"[。；]", txt)
               if "年末全国人口" in s or "全国人口" in s]
        for s in pop[:3]:
            P(f"    ▸ {s[:170]}")
        rec = {"来源": name, "url": url, "文件": fp.name,
               "出生句": sents[:12], "人口句": pop[:6]}
        found.append(rec)

    P(f"\n{'='*100}\n  汇总\n{'='*100}")
    for r in found:
        P(f"\n  [{r['来源']}]")
        for s in r["出生句"][:4]:
            P(f"    {s[:170]}")

    (RAW / "birth_population.json").write_text(
        json.dumps(found, ensure_ascii=False, indent=2), encoding="utf-8")
    (RES / "出生人口原文摘录.md").write_text(
        "# 出生人口 · 官方公报原文摘录（B 级来源）\n\n"
        + "\n".join(f"- 抓取日 2026-09-26；来源 {r['来源']} {r['url']}\n"
                    + "\n".join(f"  - {s}" for s in r["出生句"][:8])
                    for r in found)
        + "\n", encoding="utf-8")
    print(f"\n  → {RES / '出生人口原文摘录.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
