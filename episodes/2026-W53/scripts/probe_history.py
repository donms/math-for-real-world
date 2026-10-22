#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W53 · 查数据集在**暑假之前**还有多少数据（决定往前取多久）。

## 为什么需要

用户的要求：**覆盖暑假前 / 中 / 后**，以分清"周内结构"与"季节效应"。

而 NYC DOT Traffic Speeds 是一个**滚动数据集** ——
它可能只保留最近若干个月。若 3 月已无数据，
那么"暑假前"就只能取到数据集的最早月份。

⇒ **先量出可用下限，再定取数区间。**

## ⚠️ URL 编码（本会话第 3 次踩）

SoQL 的 `$where` 里**含空格**（`AND`），而 `urlopen` 不做自动编码
⇒ 必须 `quote(url, safe=...)`，且 **`$` `=` `&` `'` `(` `)` `,` 都要在 safe 里**
（把它们编码掉会让 Socrata 报 `Unrecognized arguments`）。

用法：
    $PY probe_history.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
BASE = "https://data.cityofnewyork.us/resource/i4gi-tjb9.json"
SAFE = ":/?&=%$,()'*.-_[]{}<>~+"


def count(month: str, timeout: int = 240):
    from net_resolve import open_url
    q = (f"$select=count(*)&$where=data_as_of>'{month}-01T00:00:00'"
         f" AND data_as_of<'{month}-08T00:00:00'")
    u = quote(f"{BASE}?{q}", safe=SAFE)
    d = json.loads(open_url(u, timeout=timeout, tries=2)
                   .read().decode("utf-8", "ignore"))
    return int(d[0]["count"])


def main() -> int:
    print("=" * 88)
    print("  W53 · 数据集在暑假之前还有多少（每月头 7 天）")
    print("=" * 88)
    for m in ("2025-10", "2025-12", "2026-01", "2026-02", "2026-03",
              "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"):
        try:
            t0 = time.time()
            n = count(m)
            tag = "有数据" if n > 1000 else ("极少" if n > 0 else "**无**")
            print(f"  {m}: {n:>12,} 行  ({time.time()-t0:>5.0f}s)  {tag}")
        except Exception as e:                                       # noqa: BLE001
            print(f"  {m}: [!] {type(e).__name__}: {str(e)[:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
