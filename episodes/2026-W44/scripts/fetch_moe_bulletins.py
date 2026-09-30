#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W44 取数 · 教育部逐年《全国教育事业发展统计公报》**全文**（A 级来源）。

## 为什么这样做

媒体报道（芥末堆/华经）给的逐年数字只能当**线索**（C 级），
论文里引用的每个数字都必须来自**教育部原文**（A 级）。

`moe.gov.cn/jyb_sjzl/sjzl_fztjgb/` 列表页**实测可达**，含 2022–2025 多期链接。
本脚本：抓列表 → 逐篇抓全文 → 落盘 → 抽「幼儿园/在园幼儿/学前」相关句子。

## 产出

```
episodes/2026-W44/data/raw/moe_bulletins/<id>.html    原始页（永不修改）
episodes/2026-W44/data/raw/moe_bulletins/index.json   清单
episodes/2026-W44/results/moe_公报原文摘录.txt         人可读摘录
```

用法：
    $PY fetch_moe_bulletins.py
"""
from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]          # → .
EP = ROOT / "episodes" / "2026-W44"
RAW = EP / "data" / "raw" / "moe_bulletins"
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

INDEX = "http://www.moe.gov.cn/jyb_sjzl/sjzl_fztjgb/"
BASE = "http://www.moe.gov.cn/jyb_sjzl/sjzl_fztjgb/"

KEYS = ("幼儿园", "在园幼儿", "学前教育", "毛入园率", "普惠",
        "民办幼儿园", "学前三年")


def get(url: str, timeout: int = 30) -> tuple[int, str]:
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=timeout,
            context=_CTX)
        b = r.read()
        st = r.status
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:                          # noqa: BLE001
        return -1, ""
    for enc in ("utf-8", "gb18030"):
        try:
            return st, b.decode(enc)
        except UnicodeDecodeError:
            continue
    return st, b.decode("utf-8", "ignore")


def strip_tags(html: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", t)


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    RES.mkdir(parents=True, exist_ok=True)

    out: list[str] = []
    summary: list[dict] = []

    def P(s: str = "") -> None:
        out.append(s)
        print(s, flush=True)

    P("=" * 100)
    P("  W44 取数 · 教育部逐年统计公报全文")
    P("=" * 100)

    st, html = get(INDEX)
    P(f"\n  列表页 status={st}  {len(html):,} 字符")
    if st != 200:
        P("  ❌ 列表页取不到")
        return 1

    # 抽出所有 ./YYYYMM/tYYYYMMDD_xxxxxxx.html 形式的公报链接
    links = re.findall(r'href="(\./\d{6}/t\d{8}_\d+\.html)"', html)
    links = list(dict.fromkeys(links))
    P(f"  候选公报链接 {len(links)} 条")

    # 同时抓取列表页上的锚文本，便于识别年份
    anchors = re.findall(
        r'href="(\./\d{6}/t\d{8}_\d+\.html)"[^>]*>(.*?)</a>', html, re.S)

    for rel, raw_title in anchors:
        title = re.sub(r"\s+", " ", strip_tags(raw_title)).strip()
        url = BASE + rel[2:] if rel.startswith("./") else rel
        bid = re.search(r"(t\d{8}_\d+)", rel).group(1)
        P(f"\n{'━'*100}")
        P(f"  {title[:70]}")
        P(f"  {url}")
        st2, h2 = get(url)
        if st2 != 200 or len(h2) < 1000:
            P(f"  ❌ status={st2} len={len(h2)}")
            time.sleep(1.0)
            continue
        fp = RAW / f"{bid}.html"
        fp.write_text(h2, encoding="utf-8")
        txt = strip_tags(h2)
        # 定位正文起点，去掉导航噪声
        m = re.search(r"(全国共有|全国共有各级各类学校|一、综合)", txt)
        body = txt[m.start():] if m else txt
        P(f"  ✅ {len(h2):,}B  正文 {len(body):,} 字")

        # 抽与幼儿园相关的句子
        sents = [s.strip() for s in re.split(r"[。；]", body)
                 if any(k in s for k in KEYS) and re.search(r"\d", s)]
        P(f"  含「幼儿/学前+数字」的句子 {len(sents)} 条")
        for s in sents[:8]:
            P(f"    ▸ {s[:160]}")

        # 抽所有 "X万所 / X万人" 与年份
        nums = re.findall(r"([\d,]+(?:\.\d+)?)\s*(万所|万人|所|人)", body)
        summary.append({
            "文件": fp.name, "标题": title, "url": url,
            "正文字数": len(body), "句子数": len(sents),
            "句子": sents[:40],
            "数值对": nums[:60],
        })
        time.sleep(1.2)

    # ---- 落盘 ----
    (RAW / "index.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 教育部逐年统计公报 · 原文摘录（A 级来源）", "",
             f"> 抓取日：2026-09-26　｜　列表页：{INDEX}", ""]
    for s in summary:
        lines += [f"## {s['标题']}", "",
                  f"- 原始文件：`data/raw/moe_bulletins/{s['文件']}`",
                  f"- 来源：{s['url']}",
                  f"- 正文 {s['正文字数']:,} 字，含数值句 {s['句子数']} 条", ""]
        for x in s["句子"]:
            lines.append(f"- {x}")
        lines.append("")
    (RES / "moe_公报原文摘录.md").write_text("\n".join(lines),
                                             encoding="utf-8")
    (Path(__file__).resolve().parents[1] / "runs").mkdir(
        parents=True, exist_ok=True)

    P(f"\n{'='*100}")
    P(f"  抓到 {len(summary)} 篇公报")
    for s in summary:
        P(f"    {s['标题'][:52]:<54} 数值对 {len(s['数值对']):>3}")
    P(f"\n  原始页 → {RAW}")
    P(f"  摘录   → {RES / 'moe_公报原文摘录.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
