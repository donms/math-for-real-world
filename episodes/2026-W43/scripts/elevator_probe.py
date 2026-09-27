#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""加装电梯选题 · 数据可达性实测（**开工前的止损检查**）。

## 要验证的三件事（决定这题是"数据+模型"还是"纯模型驱动"）

| # | 目标 | 为什么关键 |
|---|---|---|
| 1 | **各城市费用分摊比例表** | 有 ⇒ 可做"官方规则 vs Shapley 值"比较，是核心图 |
| 2 | **司法判例中的补偿金额** | 有 ⇒ 可标定"低层损失"量级，否则只能靠假设 |
| 3 | **加装数量/进度数据** | 有 ⇒ 可做宏观分布与优先级排序（方向 5）|

## 判据

只做**可达性与结构**判断：
* 状态码、字节数、是否含表格/数字
* 页面里有没有"分摊""补偿""比例"等关键词及具体数值
* **不做完整抓取**

低频只读：1.5 s/请求，遇 403/421 停手。

用法：
    $PY elevator_probe.py
"""
from __future__ import annotations

import contextlib
import io
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

# (编号, 目标, URL)
TARGETS: list[tuple[str, str, str]] = [
    # ---- 1 分摊比例表：各市加装电梯办法/问答 ----
    ("1", "广州·增设电梯办法",
     "https://ghzyj.gz.gov.cn/zwgk/ztzl/jzdt/zcfg/content/post_10600149.html"),
    ("1", "北京·加装电梯问答",
     "https://www.beijing.gov.cn/hudong/bmwd/jsjbmyyt/20222mwd/jzdt2023/"
     "lljzdt/202310/t20231010_3274186.html"),
    ("1", "上海·住建委加装电梯",
     "https://zjw.sh.gov.cn/"),
    ("1", "深圳·加装电梯政策",
     "https://zjj.sz.gov.cn/"),
    ("1", "武汉·一梯一策报道",
     "https://www.wuhan.gov.cn/whyw/gqdt/202410/t20241023_2472560.shtml"),
    # ---- 2 判例 ----
    ("2", "加装电梯判例汇编",
     "http://xinjielaw.com/article/1875.html"),
    ("2", "最高法·裁判文书网",
     "https://wenshu.court.gov.cn/"),
    ("2", "中国法院网·案例",
     "https://www.chinacourt.org/article/index/id/MzAwNAAAADA.shtml"),
    # ---- 3 数量/进度 ----
    ("3", "住建部·老旧小区改造",
     "https://www.mohurd.gov.cn/"),
    ("3", "中国建设报·湖北加梯",
     "http://www.chinajsb.cn/html/202411/05/44307.html"),
    ("3", "民政部·老龄事业公报",
     "https://www.mca.gov.cn/n1288/n1290/n1316/"
     "c1662004999980012271/content.html"),
]

KW = {
    "分摊": r"分摊",
    "补偿": r"补偿",
    "比例": r"比例",
    "楼层": r"楼层|层数|六层|七层|顶层",
    "金额_元": r"\d{3,6}\s*元",
    "万元": r"\d+(?:\.\d+)?\s*万元",
    "百分比": r"\d{1,3}(?:\.\d+)?\s*%",
}


def strip_html(h: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", h, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&[a-z]+;", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def probe(tag: str, name: str, url: str) -> dict:
    rec = {"目标": tag, "名称": name, "url": url, "status": None,
           "len": 0, "正文": 0, "命中": {}, "样例": []}
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=30, context=_CTX)
        b = r.read()
        rec["status"] = r.status
        rec["len"] = len(b)
        txt = strip_html(b.decode("utf-8", "ignore"))
        rec["正文"] = len(txt)
        for k, pat in KW.items():
            hits = re.findall(pat, txt)
            if hits:
                rec["命中"][k] = len(hits)
        # 抓几个"分摊/补偿"附近的数值样例
        for kw in ("分摊", "补偿"):
            i = txt.find(kw)
            if i >= 0:
                seg = txt[max(0, i - 60):i + 160]
                rec["样例"].append(f"[{kw}] …{seg}…")
    except urllib.error.HTTPError as e:
        rec["status"] = e.code
    except Exception as e:                     # noqa: BLE001
        rec["status"] = f"-1 {type(e).__name__}"
    return rec


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    rows = []
    with contextlib.redirect_stdout(buf):
        print("=" * 108)
        print("  加装电梯选题 · 数据可达性实测")
        print("=" * 108)
        cur = ""
        for tag, name, url in TARGETS:
            if tag != cur:
                cur = tag
                label = {"1": "费用分摊比例表", "2": "司法判例补偿金额",
                         "3": "加装数量/进度"}[tag]
                print(f"\n{'━'*108}\n  【{tag}】{label}\n{'━'*108}")
            r = probe(tag, name, url)
            rows.append(r)
            st = r["status"]
            mark = "✅" if st == 200 and r["len"] > 800 else "—"
            print(f"\n  {mark} {str(st):>8} {r['len']:>10,}  {name}")
            print(f"      {url}")
            if r["正文"]:
                print(f"      正文 {r['正文']:,} 字   命中：{r['命中']}")
            for s in r["样例"][:2]:
                print(f"      {s[:150]}")
            time.sleep(SLEEP)

        print(f"\n{'='*108}")
        print("  汇总")
        print("=" * 108)
        for tag, label in (("1", "费用分摊比例表"), ("2", "司法判例补偿金额"),
                           ("3", "加装数量/进度")):
            ok = [r for r in rows if r["目标"] == tag
                  and r["status"] == 200 and r["len"] > 800]
            rich = [r for r in ok
                    if r["命中"].get("分摊") or r["命中"].get("补偿")
                    or r["命中"].get("万元")]
            print(f"  【{tag}】{label}：可达 {len(ok)}/{len([r for r in rows if r['目标']==tag])}"
                  f"，其中含关键信息 {len(rich)}")
            for r in rich:
                print(f"      ✓ {r['名称']}  {r['命中']}")

    (RES / "elevator_probe.txt").write_text(buf.getvalue(), encoding="utf-8")
    (RES / "elevator_probe.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(buf.getvalue())
    print(f"done: {len(rows)} targets")
    print(f"  log -> {RES / 'elevator_probe.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
