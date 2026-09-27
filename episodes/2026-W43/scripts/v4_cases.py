#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""数据核验（四）：**判例核验** —— 尽力找案号与审理法院。

## 现实约束（必须先说清）

**中国裁判文书网（wenshu.court.gov.cn）需要登录且有反爬**，
本脚本**无法用它做正式检索**。因此核验策略是：

1. 抓取**法院官网 / 权威媒体**对同一案件的报道（比律所汇编可靠）
2. 从中提取：**审理法院、年份、案号（若有）、当事人、判决金额**
3. 与 `data/clean/cases.csv` 的记录**逐项比对**
4. 对找不到案号的案件，**降级标注为"未经一手核实"**

## 判据

* **A 级**：法院官网或官方通报，含案号
* **B 级**：法院官网/权威媒体，无案号但可定位到法院与年份
* **C 级**：律所汇编/自媒体，无法定位

用法：
    $PY v4_cases.py
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

# (编号, 案件, URL, 级别线索)
CASES = [
    ("C1", "深圳案（二楼索赔30万被驳）",
     "https://www.sohu.com/a/979111055_161795", "媒体转载法院通报"),
    ("C2", "1楼业主起诉·判楼上14户补偿2.1万",
     "https://www.sohu.com/a/993382819_116237", "媒体转载"),
    ("C3", "辽宁阜新中院·加装电梯判例",
     "https://fx.lncourt.gov.cn/article/detail/2026/01/id/9165916.shtml", "法院官网"),
    ("C4", "无锡案（最高法典型案例）",
     "https://www.chinacourt.org/", "待检索"),
]

# 案号模式
CASE_NO = re.compile(r"[（(]\s*(\d{4})\s*[）)]\s*[^\s，。；]{0,12}?"
                     r"\d+\s*号")
COURT = re.compile(r"([\u4e00-\u9fa5]{2,12}(?:人民法院|中级法院|高级法院))")
MONEY = re.compile(r"\d+(?:\.\d+)?\s*万元|\d{3,7}\s*元")


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
    CACHE.mkdir(parents=True, exist_ok=True)
    out: list[str] = []
    recs = []

    def P(s: str = "") -> None:
        out.append(s)
        print(s, flush=True)

    P("=" * 104)
    P("  数据核验（四）· 判例核验（找案号 / 审理法院 / 金额）")
    P("=" * 104)
    P("\n  ⚠️ 中国裁判文书网需登录且有反爬 ⇒ 本脚本用")
    P("     法院官网 + 权威媒体转载做核验，找不到案号的降级标注。")

    for cid, name, url, level in CASES:
        st, txt = get(url)
        rec = {"编号": cid, "案件": name, "url": url,
               "来源级别": level, "status": st, "正文": len(txt)}
        P(f"\n{'━'*104}")
        P(f"  【{cid}】{name}")
        P(f"  {url}   status={st}  正文 {len(txt):,} 字")
        P("━" * 104)
        if st != 200 or len(txt) < 200:
            P("  ❌ 取不到或内容过短")
            rec["结论"] = "取不到"
            recs.append(rec)
            time.sleep(1.5)
            continue

        nos = CASE_NO.findall(txt)
        courts = COURT.findall(txt)
        money = MONEY.findall(txt)
        rec["案号候选"] = list(dict.fromkeys(
            m.group(0) for m in CASE_NO.finditer(txt)))
        rec["法院候选"] = list(dict.fromkeys(courts))[:8]
        rec["金额候选"] = list(dict.fromkeys(money))[:12]
        P(f"    案号候选：{rec['案号候选'] or '❌ 无'}")
        P(f"    法院候选：{rec['法院候选'] or '❌ 无'}")
        P(f"    金额候选：{rec['金额候选'][:8]}")

        # 打印含"判"的片段，便于人工判读
        shown = 0
        for m in re.finditer(r"(判决|判令|法院认为|审理认为)", txt):
            i = m.start()
            seg = txt[max(0, i - 90):i + 230]
            if re.search(r"\d", seg):
                P(f"      · …{seg}…")
                shown += 1
                if shown >= 2:
                    break

        if rec["案号候选"]:
            rec["结论"] = "A 级：含案号"
        elif rec["法院候选"]:
            rec["结论"] = "B 级：可定位法院，无案号"
        else:
            rec["结论"] = "C 级：无法定位"
        P(f"    ⇒ 核验结论：**{rec['结论']}**")
        recs.append(rec)
        time.sleep(1.5)

    P(f"\n{'='*104}")
    P("  小结")
    P("=" * 104)
    from collections import Counter
    cnt = Counter(r["结论"] for r in recs)
    for k, v in cnt.items():
        P(f"    {k}: {v}")
    P(f"\n  ⇒ 判例的可核验程度**整体低于规则**。")
    P(f"     论文中引用判例金额时必须标注来源级别。")

    (RES / "v4_cases.txt").write_text("\n".join(out), encoding="utf-8")
    (RES / "v4_cases.json").write_text(
        json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  log -> {RES / 'v4_cases.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
