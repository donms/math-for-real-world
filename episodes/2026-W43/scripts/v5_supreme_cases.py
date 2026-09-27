#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""数据核验（五）：用**最高法官方典型案例发布**核验判例。

## 为什么这是最有力的一步

最高人民法院发布的**典型案例**是官方文本，含**案件标题**，
比律所汇编与自媒体可靠得多。如果能对上，判例的可信度直接升到 A 级。

核验目标：
* 无锡案（范某 / 排除妨害 / 民法典 288 条）是否见于最高法典型案例
* 广州案（补缴后使用 / 共有权）是否见于最高法典型案例
* 梧州案（万秀区法院 / 14 户 × 1500 元）的细节与出处

用法：
    $PY v5_supreme_cases.py
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

SOURCES = [
    ("S1", "最高法·民法典五周年第二批典型案例（中国法院网）",
     "https://www.chinacourt.org/article/detail/2025/05/id/8848432.shtml"),
    ("S2", "最高法典型案例·加装电梯采光纠纷（河南政法网转载）",
     "https://www.hnzf.gov.cn/content/646949/61/14992160.html"),
    ("S3", "最高法·民法典五周年第二批典型案例（广东政法网）",
     "https://www.gdzf.org.cn/yasf/content/mpost_181550.html"),
    ("S4", "光明网·加装电梯纠纷怎么判",
     "https://m.gmw.cn/2026-01/26/content_1304318814.htm"),
]

KEYS = {
    "无锡": r"无锡",
    "范某": r"范某",
    "排除妨害": r"排除妨害|停止妨害",
    "288条": r"第二百八十八条|288\s*条",
    "278条": r"第二百七十八条|278\s*条",
    "广州案": r"补缴|共有部分|共有权",
    "梧州": r"梧州",
    "万秀区": r"万秀区",
    "1500元": r"1500\s*元",
    "2.1万": r"2\.1\s*万",
    "电梯": r"加装电梯|增设电梯",
}


def strip_html(h: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", h, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&[a-z]+;", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def get(url: str) -> tuple[int, str]:
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=45, context=_CTX)
        b = r.read()
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
    P("  数据核验（五）· 最高法典型案例核验")
    P("=" * 104)

    for sid, name, url in SOURCES:
        st, txt = get(url)
        rec = {"编号": sid, "来源": name, "url": url, "status": st,
               "正文": len(txt), "命中": {}}
        P(f"\n{'━'*104}")
        P(f"  【{sid}】{name}")
        P(f"  {url}   status={st}  正文 {len(txt):,} 字")
        P("━" * 104)
        if st != 200 or len(txt) < 300:
            P("  ❌ 取不到")
            recs.append(rec)
            time.sleep(1.5)
            continue

        for k, pat in KEYS.items():
            n = len(re.findall(pat, txt))
            rec["命中"][k] = n
        hit = {k: v for k, v in rec["命中"].items() if v}
        P(f"    命中：{hit}")

        # 抽取"案例N：…"标题
        titles = re.findall(r"案例[一二三四五六七八九十\d]+[：:]([^。；\n]{6,60})", txt)
        if titles:
            rec["案例标题"] = titles[:20]
            P(f"    案例标题 {len(titles)} 条：")
            for t in titles[:14]:
                P(f"      · {t.strip()}")
        # 含"电梯"的段落
        shown = 0
        for m in re.finditer(r"电梯", txt):
            i = m.start()
            seg = txt[max(0, i - 150):i + 260]
            if shown < 3:
                P(f"      ▸ …{seg}…")
                shown += 1
        recs.append(rec)
        time.sleep(1.5)

    P(f"\n{'='*104}")
    P("  小结")
    P("=" * 104)
    for r in recs:
        P(f"  {r['编号']} {r['来源'][:30]:<32} status={r['status']}  "
          f"命中 {len([v for v in r['命中'].values() if v])}/{len(KEYS)}")
    # 汇总：哪些关键词在任一官方源出现
    allhit: dict[str, int] = {}
    for r in recs:
        for k, v in r.get("命中", {}).items():
            allhit[k] = allhit.get(k, 0) + v
    P(f"\n  官方源中的关键词总命中：")
    for k, v in allhit.items():
        P(f"    {k:<12} {v:>4}  {'✅' if v else '❌'}")

    (RES / "v5_supreme_cases.txt").write_text("\n".join(out), encoding="utf-8")
    (RES / "v5_supreme_cases.json").write_text(
        json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  log -> {RES / 'v5_supreme_cases.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
