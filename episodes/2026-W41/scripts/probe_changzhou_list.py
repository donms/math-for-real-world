#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""探测长洲船闸简报的列表页与 URL 规律（为抓时间序列做准备）。

## 背景

选题 A（平陆运河分流效应）依赖**长洲船闸简报的逐月时间序列**。
单篇简报 URL 形如
`.../jigou/hdgc/202607/t20260716_4209773.html`
（路径里有年月、文件名里有年月日 + 文章 ID），
但**文章 ID 无法推算** —— 所以必须找到**列表页**来枚举。

## 用法

    $PY probe_changzhou_list.py
"""
from __future__ import annotations

import re
import socket
import ssl
import urllib.request

socket.setdefaulttimeout(25)
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE          # 该站证书链在本机不被信任

CANDIDATES = [
    "https://zjhy.mot.gov.cn/zzhxxgk/",
    "https://zjhy.mot.gov.cn/zzhxxgk/index_2.html",
    "https://zjhy.mot.gov.cn/zzhxxgk/index_3.html",
]


def get(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, context=CTX) as r:
        return r.status, r.read().decode("utf-8", "ignore")


def main() -> int:
    seen = 0
    for url in CANDIDATES:
        try:
            code, html = get(url)
        except Exception as e:                                 # noqa: BLE001
            print(f"  ❌ {url}\n     {type(e).__name__}: {str(e)[:60]}")
            continue
        links = re.findall(r'href="([^"]*t\d{8}_\d+\.html)"', html)
        # 标题通常在 <a ... title="..."> 或紧跟链接的文本里
        titles = re.findall(r'title="([^"]{6,80})"', html)
        cz = [t for t in titles if "长洲" in t or "船闸" in t]
        # 也扫正文里出现的「长洲」
        if "长洲" in html:
            seen += 1
        print(f"  ✅ {url}")
        print(f"     HTTP {code}  长度 {len(html)}  文章链接 {len(links)} 个"
              f"  含「长洲/船闸」的标题 {len(cz)} 个")
        for t in cz[:8]:
            print(f"       · {t}")
        if links:
            for l in links[:3]:
                print(f"     样例链接：{l}")
        print()
    print(f"  含「长洲」字样的页数：{seen}/{len(CANDIDATES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
