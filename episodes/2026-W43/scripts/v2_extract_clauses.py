#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""数据核验（二）：**逐字提取**官方原文里的规则条款与北京附件。

## 目的

(1) 北京：通知页正文**不含比例表**（表在附件里）⇒ 必须找到附件原文。
    若找不到，就把北京的数字**降级标注**为"转载来源"。
(2) 广州：核对我记录的系数（三层=1、二层=0.5、一层=0、+0.1）
(3) 武汉：核对"三楼每户 5%、每高一层 +5%"的**精确表述**
    —— 报道里有另一种口径（三楼每户 3 万、每高一层 +1 万），需分清是不同楼栋。
(4) 找出北京附件的 PDF/图片链接。

用法：
    $PY v2_extract_clauses.py
"""
from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
EP = ROOT / "episodes" / "2026-W43"
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

URLS = {
    "北京": "https://zjw.beijing.gov.cn/bjjs/wwz/ljxqjzdt/zcwj61/436242402/index.shtml",
    "广州": "https://www.gz.gov.cn/gfxwj/szfgfxwj/gzsrmzfbgt/content/mpost_10320726.html",
    "武汉": "https://www.wuhan.gov.cn/whyw/gqdt/202410/t20241023_2472560.shtml",
}


def raw(url: str) -> tuple[int, str, str]:
    """返回 (status, 解码后 HTML, content-type)。"""
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=40, context=_CTX)
        b = r.read()
        ct = (r.headers.get("Content-Type") or "")
        for enc in ("utf-8", "gb18030"):
            try:
                return r.status, b.decode(enc), ct
            except UnicodeDecodeError:
                continue
        return r.status, b.decode("utf-8", "ignore"), ct
    except urllib.error.HTTPError as e:
        return e.code, "", ""
    except Exception:                          # noqa: BLE001
        return -1, "", ""


def strip_html(h: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", h, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&[a-z]+;", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    out: list[str] = []
    recs: dict = {}

    def P(s: str = "") -> None:
        out.append(s)
        print(s, flush=True)

    P("=" * 104)
    P("  数据核验（二）· 逐字提取官方条款")
    P("=" * 104)

    for city, url in URLS.items():
        st, html, ct = raw(url)
        txt = strip_html(html)
        rec: dict = {"url": url, "status": st, "content_type": ct,
                     "正文": len(txt)}
        P(f"\n{'━'*104}")
        P(f"  【{city}】status={st}  ct={ct}")
        P(f"  {url}")
        P("━" * 104)

        if city == "北京":
            # 找附件链接
            links = re.findall(
                r'href=["\']([^"\']+\.(?:pdf|doc|docx|xls|xlsx|jpg|png))["\']',
                html, flags=re.I)
            rec["附件链接"] = links
            P(f"    页面内附件/图片链接 {len(links)} 个：")
            for l in links[:12]:
                P(f"      · {l}")
            # 也找"附件"附近的链接
            for m in re.finditer(r"附件", html):
                seg = html[m.start():m.start() + 400]
                for l in re.findall(r'href=["\']([^"\']+)["\']', seg):
                    if l not in links:
                        links.append(l)
            rec["附件链接_扩展"] = links
            P(f"    展开后共 {len(links)} 个链接")

        if city == "广州":
            i = txt.find("业主可以参考以下分摊比例")
            if i >= 0:
                rec["条款原文"] = txt[i:i + 340]
                P(f"    ★【第八条 分摊系数】原文：")
                P(f"      {txt[i:i+340]}")
            j = txt.find("受影响业主")
            if j >= 0:
                rec["受影响业主原文"] = txt[max(0, j - 300):j + 220]
                P(f"\n    ★【受影响业主条款】原文：")
                P(f"      {txt[max(0,j-300):j+220]}")

        if city == "武汉":
            for kw in ("从三楼开始分摊", "每户承担总金额", "每增加一层"):
                i = txt.find(kw)
                if i >= 0:
                    rec.setdefault("条款原文", []).append(txt[max(0, i - 90):i + 260])
                    P(f"    ★【{kw}】原文：")
                    P(f"      {txt[max(0,i-90):i+260]}")
        recs[city] = rec
        time.sleep(1.5)

    (RES / "v2_extract_clauses.txt").write_text("\n".join(out), encoding="utf-8")
    (RES / "v2_extract_clauses.json").write_text(
        json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  log -> {RES / 'v2_extract_clauses.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
