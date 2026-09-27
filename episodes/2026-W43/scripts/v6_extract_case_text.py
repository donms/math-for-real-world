#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""数据核验（六）：从最高法典型案例官方转载中**切出判例全文**。

源：广东政法网 / 湖南长安网 转载的
《民法典颁布五周年典型案例——"坚持司法为民，更好保障人民美好生活需要"专题》

切出"一、…徐某等六人诉范某排除妨害纠纷案"与后续案例的完整文本，
存到 `data/raw/official/` 供论文直接引用。

用法：
    $PY v6_extract_case_text.py
"""
from __future__ import annotations

import re
import ssl
import urllib.request
from pathlib import Path

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

SRC = "https://www.gdzf.org.cn/yasf/content/mpost_181550.html"


def strip_html(h: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", h, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = re.sub(r"&[a-z]+;", " ", t)
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n{2,}", "\n", t).strip()


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    r = urllib.request.urlopen(
        urllib.request.Request(SRC, headers=UA), timeout=45, context=_CTX)
    txt = strip_html(r.read().decode("utf-8", "ignore"))

    out: list[str] = []
    out.append("=" * 100)
    out.append("  最高法《民法典颁布五周年典型案例》—— 加装电梯相关判例（官方转载全文）")
    out.append("=" * 100)
    out.append(f"  源：{SRC}")
    out.append("      （转载自最高人民法院发布，2025-05-27）")
    out.append("=" * 100)

    # 切出"一、…案"到"二、"之间的正文
    start = txt.find("一、依法妥善处理老旧小区加装电梯纠纷")
    end = txt.find("二、", start + 10) if start >= 0 else -1
    if start < 0:
        out.append("\n  ❌ 未找到案例一起点")
    else:
        seg = txt[start:end if end > 0 else start + 4000]
        seg = re.sub(r"\n+", "\n", seg).strip()
        out.append("\n" + "─" * 100)
        out.append("  【判例一】徐某等六人诉范某排除妨害纠纷案（无锡）")
        out.append("─" * 100)
        out.append(seg)

    # 找"广州"相关案例（补缴后使用）
    for m in re.finditer(r"[三四五六七八九]、", txt):
        seg = txt[m.start():m.start() + 2200]
        if "电梯" in seg and ("补缴" in seg or "共有" in seg):
            out.append("\n" + "─" * 100)
            out.append("  【判例】含『补缴/共有』的电梯案例")
            out.append("─" * 100)
            out.append(re.sub(r"\n+", "\n", seg).strip())
            break

    body = "\n".join(out)
    (CACHE / "最高法典型案例_加装电梯.txt").write_text(body, encoding="utf-8")
    (RES / "v6_case_text.txt").write_text(body, encoding="utf-8")
    print(body)
    print(f"\n  saved -> {CACHE / '最高法典型案例_加装电梯.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
