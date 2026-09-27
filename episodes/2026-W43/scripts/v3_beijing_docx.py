#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""数据核验（三）：下载并解析**北京住建委附件 (.docx)**，核对分摊比例表。

## 为什么关键

北京通知页正文**只有原则表述，没有比例表** —— 表在附件里。
我们现有的北京数字来自**新浪财经转载**。附件是 .docx，可直接解压读 XML。

用法：
    $PY v3_beijing_docx.py
"""
from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent.parent.parent
EP = ROOT / "episodes" / "2026-W43"
RES = EP / "results"
CACHE = EP / "data" / "raw" / "official"

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

BASE = "https://zjw.beijing.gov.cn"
ATTACH = "/bjjs/wwz/ljxqjzdt/zcwj61/436242402/2023100808193080833.docx"

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def docx_text(p: Path) -> tuple[str, list[list[str]]]:
    """返回 (纯文本, 表格行)。"""
    with zipfile.ZipFile(p) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    # 表格
    tables: list[list[str]] = []
    for tbl in root.iter(f"{{{NS['w']}}}tbl"):
        for tr in tbl.iter(f"{{{NS['w']}}}tr"):
            cells = []
            for tc in tr.iter(f"{{{NS['w']}}}tc"):
                txt = "".join(t.text or "" for t in tc.iter(f"{{{NS['w']}}}t"))
                cells.append(txt.strip())
            if any(cells):
                tables.append(cells)
    # 全文
    paras = []
    for pnode in root.iter(f"{{{NS['w']}}}p"):
        txt = "".join(t.text or "" for t in pnode.iter(f"{{{NS['w']}}}t"))
        if txt.strip():
            paras.append(txt.strip())
    return "\n".join(paras), tables


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    out: list[str] = []

    def P(s: str = "") -> None:
        out.append(s)
        print(s, flush=True)

    P("=" * 104)
    P("  数据核验（三）· 北京住建委附件 (.docx) 原文核对")
    P("=" * 104)

    url = BASE + ATTACH
    fn = CACHE / "beijing_436242402.docx"
    P(f"\n  URL: {url}")
    if not fn.exists():
        try:
            b = urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=60,
                context=_CTX).read()
            if b[:2] != b"PK":
                P(f"  ❌ 返回的不是 docx（前 2 字节 {b[:2]!r}，{len(b)} 字节）")
                (RES / "v3_beijing_docx.txt").write_text("\n".join(out),
                                                         encoding="utf-8")
                return 1
            fn.write_bytes(b)
        except urllib.error.HTTPError as e:
            P(f"  ❌ HTTP {e.code}")
            (RES / "v3_beijing_docx.txt").write_text("\n".join(out),
                                                     encoding="utf-8")
            return 1
        except Exception as e:                 # noqa: BLE001
            P(f"  ❌ {type(e).__name__}: {e}")
            (RES / "v3_beijing_docx.txt").write_text("\n".join(out),
                                                     encoding="utf-8")
            return 1
    P(f"  ✅ 已下载/缓存：{fn.name}  {fn.stat().st_size:,} 字节")

    txt, tables = docx_text(fn)
    P(f"  正文 {len(txt)} 字，表格 {len(tables)} 行")
    P(f"\n  ── 全文 ──")
    for line in txt.split("\n"):
        P(f"    {line}")
    P(f"\n  ── 表格 ──")
    for row in tables:
        P(f"    {' | '.join(row)}")

    # ---- 与我们的记录比对 ----
    P(f"\n{'='*104}")
    P("  ★ 与 data/clean/city_rules.csv 的记录比对")
    P("=" * 104)
    ours = {"1层": "0", "2层": "4-6", "3层": "11-13", "4层": "19-21",
            "5层": "27-29", "6层": "32-34"}
    flat = re.sub(r"\s+", "", txt + " " + " ".join(
        "".join(r) for r in tables))
    n_ok = 0
    for k, v in ours.items():
        found = v.replace("-", "-") in flat or v in flat
        n_ok += 1 if found else 0
        P(f"    {k:<5} 我们记录 {v:<8} 原文{'找到 ✅' if found else '未找到 ❌'}")

    # 抽所有百分比
    pcts = re.findall(r"\d{1,3}\s*[-–~]\s*\d{1,3}\s*%|\d{1,3}\s*%", flat)
    P(f"\n    原文中所有百分比：{pcts[:40]}")

    (RES / "v3_beijing_docx.txt").write_text("\n".join(out), encoding="utf-8")
    (RES / "v3_beijing_docx.json").write_text(json.dumps(
        {"url": url, "bytes": fn.stat().st_size, "正文": txt,
         "表格": tables, "百分比": pcts,
         "比对": {k: (v in flat) for k, v in ours.items()}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  比对命中 {n_ok}/{len(ours)}")
    print(f"  log -> {RES / 'v3_beijing_docx.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
