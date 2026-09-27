#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""补齐加装电梯选题的**多城市分摊表**与**更多判例**。

已完成：北京官方分摊表 + 5 个判例（`加装电梯_数据源实测结果.md`）。
本脚本去取：上海、广州、深圳等地的分摊规则，以及法院系统的判例。

用法：
    $PY elevator_deep.py
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
    ("上海·房管局提案答复",
     "https://fgj.sh.gov.cn/bljg/20250605/3aa7d841d9924858af7803f0bbe008eb.html"),
    ("上海法治报·按家还是按室",
     "http://www.shfzb.com.cn/shfzb/h5/html5/2025-06/06/content_150507_2258935.htm"),
    ("阜新中院·加装电梯判例",
     "https://fx.lncourt.gov.cn/article/detail/2026/01/id/9165916.shtml"),
    ("广州增设电梯办法2025（转载）",
     "http://www.thnet.gov.cn/zfxxgkml/content/post_10509320.html"),
    ("中国电梯工程服务网·难点与办法",
     "https://www.zgdtgcfw.cn/news_deatil/1096.html"),
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
        return r.status, strip_html(r.read().decode("utf-8", "ignore"))
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
    P("  加装电梯 · 多城市分摊表 + 更多判例")
    P("=" * 104)

    for name, url in TARGETS:
        st, txt = get(url)
        rec = {"名称": name, "url": url, "status": st, "正文": len(txt)}
        recs.append(rec)
        P(f"\n{'━'*104}")
        P(f"  【{name}】  status={st}  正文 {len(txt):,} 字")
        P(f"  {url}")
        P("━" * 104)
        if st != 200 or not txt:
            P("  ❌ 取不到")
            time.sleep(SLEEP)
            continue

        # 关键词计数
        for kw in ("分摊", "出资", "补偿", "比例", "万元", "楼层"):
            n = len(re.findall(kw, txt))
            if n:
                P(f"    [{kw}] {n} 次")
        # 是否有"百分比分摊"表格痕迹
        pcts = re.findall(r"\d{1,3}(?:\.\d+)?%", txt)
        if pcts:
            P(f"    百分比数值 {len(pcts)} 个，例：{pcts[:14]}")
        amts = re.findall(r"\d+(?:\.\d+)?\s*万元", txt)
        if amts:
            P(f"    金额（万元）{len(amts)} 个，例：{amts[:10]}")

        # 打印关键片段
        shown = 0
        for kw in ("分摊", "出资比例", "补偿"):
            for m in re.finditer(kw, txt):
                i = m.start()
                seg = txt[max(0, i - 100):i + 200]
                P(f"    ·[{kw}] …{seg}…")
                shown += 1
                break
            if shown >= 3:
                break
        time.sleep(SLEEP)

    P(f"\n{'='*104}")
    P("  小结")
    P("=" * 104)
    ok = [r for r in recs if r["status"] == 200 and r["正文"] > 500]
    P(f"  可达 {len(ok)}/{len(recs)}")
    for r in ok:
        P(f"    ✓ {r['名称']}  {r['正文']:,} 字")

    (RES / "elevator_deep.txt").write_text("\n".join(out), encoding="utf-8")
    (RES / "elevator_deep.json").write_text(
        json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ndone: {len(recs)} targets")
    print(f"  log -> {RES / 'elevator_deep.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
