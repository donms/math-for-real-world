#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""抓上海（及各地）**分摊表 PDF** —— 表格往往只在 PDF 里。

## 目标

检索中出现的候选（含"楼层/户数/分摊比率/每户分摊费用/政府补贴后"完整表格）：
* `sqcb.zhoudaosh.com/.../070315.pdf`（社区晨报，上海口径）
* 长春、上羊市街社区等其它表格

PDF 用 PyMuPDF 抽文本，**重点抽「楼层—分摊比率」成对数值**。

用法：
    $PY elevator_pdf_tables.py
"""
from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent.parent.parent
EP = ROOT / "episodes" / "2026-W42"
RES = EP / "results"
CACHE = EP / "data" / "raw" / "elevator"

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

CANDIDATES = [
    ("上海社区晨报·分摊表",
     "http://sqcb.zhoudaosh.com/mlz/images/2021-03/15/07/070315.pdf"),
    ("长春·加装电梯续",
     "http://bxshszb.bcxww.com/page/41/2021-03/29/03/2021032903_pdf.pdf"),
    ("宁波·如何取得居民同意",
     "http://daily.cnnb.com.cn/nbwb/images/2018-01/10/A3/nbwb20180110A3.pdf"),
]


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    out: list[str] = []
    recs = []

    def P(s: str = "") -> None:
        out.append(s)
        print(s, flush=True)

    P("=" * 100)
    P("  分摊表 PDF 抽取")
    P("=" * 100)

    for name, url in CANDIDATES:
        P(f"\n{'━'*100}\n  【{name}】\n  {url}\n{'━'*100}")
        fn = CACHE / (re.sub(r"[^A-Za-z0-9]+", "_", url)[-60:] + ".pdf")
        try:
            if not fn.exists():
                b = urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=45,
                    context=_CTX).read()
                if b[:4] != b"%PDF":
                    P(f"  ⚠️ 非 PDF（前 4 字节 {b[:4]!r}），跳过")
                    recs.append({"名称": name, "url": url, "ok": False})
                    continue
                fn.write_bytes(b)
            doc = fitz.open(fn)
            txt = "\n".join(doc[i].get_text() for i in range(len(doc)))
            P(f"  ✅ {len(doc)} 页，{len(txt):,} 字符")
            # 找楼层/分摊相关行
            lines = [x.strip() for x in txt.split("\n") if x.strip()]
            hit = 0
            for i, ln in enumerate(lines):
                if re.search(r"(楼层|一层|二层|三层|四层|五层|六层|分摊|出资|比率|比例)",
                             ln):
                    ctx = " | ".join(lines[i:i + 6])
                    P(f"    · {ctx[:190]}")
                    hit += 1
                    if hit >= 12:
                        break
            # 抽「数字层 + 百分比」对
            pairs = re.findall(
                r"([一二三四五六七八九]|\d)\s*层?[^\d%]{0,14}?"
                r"(\d{1,3}(?:\.\d+)?)\s*%", txt)
            if pairs:
                P(f"    ★ 抽到「层-百分比」{len(pairs)} 组：{pairs[:20]}")
            recs.append({"名称": name, "url": url, "ok": True,
                         "页数": len(doc), "字符": len(txt),
                         "层百分比对": pairs[:30]})
        except urllib.error.HTTPError as e:
            P(f"  ❌ HTTP {e.code}")
            recs.append({"名称": name, "url": url, "ok": False,
                         "err": f"HTTP {e.code}"})
        except Exception as e:                 # noqa: BLE001
            P(f"  ❌ {type(e).__name__}: {e}")
            recs.append({"名称": name, "url": url, "ok": False,
                         "err": type(e).__name__})

    (RES / "elevator_pdf_tables.txt").write_text("\n".join(out),
                                                 encoding="utf-8")
    (RES / "elevator_pdf_tables.json").write_text(
        json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ndone")
    print(f"  log -> {RES / 'elevator_pdf_tables.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
