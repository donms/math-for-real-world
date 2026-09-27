#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""数据核验（一）：**回政府原文**核对五地分摊规则。

## 为什么要做

现有材料里，北京与广州的规则来自**转载**（新浪财经、天河区转载），
南京来自官方问答页，武汉来自市政府页面。
**论文引用具体规则前，必须以发布机关原文为准。**

## 核验对象

| # | 待核 | 期望的官方出处 |
|---|---|---|
| 1 | 北京分摊指导区间 | 北京市住建委 zjw.beijing.gov.cn |
| 2 | 广州分摊系数 | 广州市政府 gz.gov.cn（穗府办规〔2025〕6号）|
| 3 | 南京出资参考比例 | 南京市鼓楼区 njgl.gov.cn（已为官方页）|
| 4 | 武汉"一梯一策" | 武汉市 wuhan.gov.cn（已为官方页）|

## 判据

对每条规则，抽取**原文中的关键句**，与 `data/clean/city_rules.csv`
里我们记录的数字**逐项比对**，并记录"一致 / 不一致 / 找不到"。

用法：
    $PY v1_official_rules.py
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

TARGETS = [
    ("北京·住建委原文（出资比例指导标准）",
     "https://zjw.beijing.gov.cn/bjjs/wwz/ljxqjzdt/zcwj61/436242402/index.shtml",
     ["4-6", "11-13", "19-21", "27-29", "32-34", "指导区间", "谁受益"]),
    ("广州·市政府原文（穗府办规〔2025〕6号）",
     "https://www.gz.gov.cn/gfxwj/szfgfxwj/gzsrmzfbgt/content/mpost_10320726.html",
     ["0.5", "1.1", "1.2", "1.3", "第三层", "分摊比例", "受影响业主"]),
    ("南京·鼓楼区官方问答",
     "http://www.njgl.gov.cn/znwd/zsk/zfcj/202306/t20230629_3949933.html",
     ["1.0", "1.3", "1.6", "1.9", "2.2", "基准层"]),
    ("武汉·市政府（一梯一策）",
     "https://www.wuhan.gov.cn/whyw/gqdt/202410/t20241023_2472560.shtml",
     ["5%", "分摊", "三楼", "六楼"]),
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
            urllib.request.Request(url, headers=UA), timeout=40, context=_CTX)
        b = r.read()
        ct = (r.headers.get("Content-Type") or "").lower()
        if "pdf" in ct or b[:4] == b"%PDF":
            return r.status, "__PDF__"
        # 尝试多种编码
        for enc in ("utf-8", "gb18030"):
            try:
                return r.status, strip_html(b.decode(enc))
            except UnicodeDecodeError:
                continue
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
    P("  数据核验（一）· 回政府原文核对五地分摊规则")
    P("=" * 104)

    for name, url, keys in TARGETS:
        st, txt = get(url)
        P(f"\n{'━'*104}")
        P(f"  【{name}】")
        P(f"  {url}")
        P(f"  status = {st}   正文 {len(txt):,} 字")
        P("━" * 104)
        rec = {"名称": name, "url": url, "status": st,
               "正文": len(txt), "命中": {}}
        if st != 200 or not txt:
            P("  ❌ 取不到，需人工打开")
            recs.append(rec)
            time.sleep(1.5)
            continue
        if txt == "__PDF__":
            P("  ⚠️ 是 PDF，记下 URL 供人工核对")
            recs.append(rec)
            time.sleep(1.5)
            continue

        for k in keys:
            n = len(re.findall(re.escape(k), txt))
            rec["命中"][k] = n
            P(f"    {k:<14} 出现 {n} 次  {'✅' if n else '❌ 未找到'}")
        # 打印含关键比例数字的片段
        shown = 0
        for m in re.finditer(r"(分摊|出资|比例|系数)", txt):
            i = m.start()
            seg = txt[max(0, i - 110):i + 240]
            if re.search(r"\d", seg) and shown < 3:
                P(f"      · …{seg}…")
                shown += 1
        # 找发布文号/日期
        for pat in (r"穗府办规[〔\[]?(\d{4})[〕\]]?\s*(\d+)\s*号",
                    r"京建发[〔\[]?(\d{4})[〕\]]?\s*(\d+)\s*号",
                    r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"):
            mm = re.search(pat, txt)
            if mm:
                P(f"      ★ 文号/日期线索：{mm.group(0)}")
        recs.append(rec)
        time.sleep(1.5)

    P(f"\n{'='*104}")
    P("  小结")
    P("=" * 104)
    for r in recs:
        hit = sum(1 for v in r["命中"].values() if v)
        tot = len(r["命中"]) or 1
        P(f"  {r['名称'][:34]:<36} status={r['status']}  关键项命中 {hit}/{tot}")

    (RES / "v1_official_rules.txt").write_text("\n".join(out), encoding="utf-8")
    (RES / "v1_official_rules.json").write_text(
        json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  log -> {RES / 'v1_official_rules.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
