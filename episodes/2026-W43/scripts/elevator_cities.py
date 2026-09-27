#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""补齐更多城市的**官方分摊规则**（目标：把两城对照做厚）。

已有：北京（区间表）、广州（系数法）。本脚本去取：南京、南昌、湛江、衡阳等。

判据：页面上是否有"分摊/出资"的**具体比例或系数**（而非泛泛表述）。

用法：
    $PY elevator_cities.py
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
EP = ROOT / "episodes" / "2026-W42"
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
SLEEP = 1.5

TARGETS = [
    ("南京·出资参考比例（官方问答）",
     "http://www.njgl.gov.cn/znwd/zsk/zfcj/202306/t20230629_3949933.html"),
    ("南昌高新区·政策解答",
     "https://nchdz.nc.gov.cn/ncgxq/zcjd/202101/78c58dffd70447068e3ff640328d24d9.shtml"),
    ("衡阳·专项维修资金（湖南住建厅）",
     "http://zjt.hunan.gov.cn/zjt/gzdt/dfdt/202109/t20210910_29273143.html"),
    ("北京标准（行业协会转载）",
     "http://www.bcda.org.cn/beizhuangxie/wap_doc/24459063.html"),
    ("武汉·一梯一策",
     "https://www.wuhan.gov.cn/whyw/gqdt/202410/t20241023_2472560.shtml"),
]


def strip_html(h: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", h, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&[a-z]+;", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def get(url: str) -> tuple[int, str]:
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=30, context=_CTX)
        ct = (r.headers.get("Content-Type") or "")
        b = r.read()
        if "pdf" in ct.lower() or b[:4] == b"%PDF":
            return 200, "__PDF__"
        return r.status, strip_html(b.decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:                          # noqa: BLE001
        return -1, ""


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    out: list[str] = []
    recs = []

    def P(s: str = "") -> None:
        out.append(s)
        print(s, flush=True)

    P("=" * 104)
    P("  加装电梯 · 更多城市分摊规则")
    P("=" * 104)

    for name, url in TARGETS:
        st, txt = get(url)
        recs.append({"名称": name, "url": url, "status": st, "正文": len(txt)})
        P(f"\n{'━'*104}")
        P(f"  【{name}】  status={st}  正文 {len(txt):,}")
        P(f"  {url}")
        P("━" * 104)
        if st != 200 or not txt:
            P("  ❌ 取不到")
            time.sleep(SLEEP)
            continue
        if txt == "__PDF__":
            P("  ⚠️ 是 PDF，本工具不解析（记录 URL 供人工）")
            time.sleep(SLEEP)
            continue

        # 找"分摊/出资"附近的比例与系数
        found_any = False
        for kw in ("分摊", "出资", "系数", "比例"):
            for m in list(re.finditer(kw, txt))[:2]:
                i = m.start()
                seg = txt[max(0, i - 120):i + 260]
                if re.search(r"\d", seg):
                    P(f"    ·[{kw}] …{seg}…")
                    found_any = True
        # 直接抽"X层 Y%"或"第X层 Y"的序列
        seq = re.findall(r"第?([一二三四五六七八九1-9])\s*层[^。；，]{0,12}?"
                         r"(\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?)", txt)
        if seq:
            P(f"    ★ 抽到「层-数值」序列 {len(seq)} 组：{seq[:14]}")
            found_any = True
        pcts = re.findall(r"\d{1,3}(?:\.\d+)?%", txt)
        if len(pcts) >= 4:
            P(f"    百分比 {len(pcts)} 个：{pcts[:18]}")
            found_any = True
        if not found_any:
            P("    （未见具体比例/系数）")
        time.sleep(SLEEP)

    P(f"\n{'='*104}")
    P("  小结")
    P("=" * 104)
    ok = [r for r in recs if r["status"] == 200 and r["正文"] > 500]
    P(f"  可达 {len(ok)}/{len(recs)}")
    for r in ok:
        P(f"    ✓ {r['名称']}  {r['正文']:,} 字")

    (RES / "elevator_cities.txt").write_text("\n".join(out), encoding="utf-8")
    (RES / "elevator_cities.json").write_text(
        json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ndone: {len(recs)}")
    print(f"  log -> {RES / 'elevator_cities.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
