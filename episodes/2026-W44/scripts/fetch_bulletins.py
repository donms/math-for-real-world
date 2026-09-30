# -*- coding: utf-8 -*-
"""Fetch full text of Chinese national Statistical Communiques (2016-2024).

stats.gov.cn returns 403 to scripts, so we try gov.cn / official mirrors /
provincial government sites / secondary media transcriptions.

Saves every successful fetch to data/raw/stats/bulletin_<year>__<tag>.html
and writes a fetch report (ASCII terminal output, UTF-8 files).
"""
import os
import ssl
import json
import gzip
import io
import time
import urllib.request
import urllib.error

BASE = r".\episodes\2026-W44"
RAW = os.path.join(BASE, "data", "raw", "stats")
REPORT = os.path.join(BASE, "data", "raw", "stats", "_fetch_report.json")
os.makedirs(RAW, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "close",
    "Upgrade-Insecure-Requests": "1",
}


def make_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
    except Exception:
        pass
    return ctx


def fetch(url, timeout=45):
    """Return (ok, status, bytes_or_error, final_url)."""
    req = urllib.request.Request(url, headers=HEADERS)
    ctx = make_ctx()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            data = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                try:
                    data = gzip.decompress(data)
                except Exception:
                    pass
            return True, r.status, data, r.geturl()
    except urllib.error.HTTPError as e:
        body = b""
        try:
            body = e.read()
        except Exception:
            pass
        return False, e.code, body, url
    except Exception as e:
        return False, None, repr(e).encode("utf-8", "replace"), url


def decode(data):
    for enc in ("utf-8", "gb18030", "gbk", "big5", "latin-1"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", "replace")


def sniff_meta_encoding(data):
    head = data[:4000].lower()
    i = head.find(b"charset=")
    if i >= 0:
        return head[i + 8:i + 30].split(b'"')[0].split(b"'")[0].split(b";")[0].split(b">")[0].strip()
    return None


# ---------------------------------------------------------------- candidates
CANDIDATES = {
    2016: [
        ("govcn", "https://www.gov.cn/shuju/2017-02/28/content_5171492.htm"),
        ("govcn_http", "http://www.gov.cn/shuju/2017-02/28/content_5171492.htm"),
        ("stats_http", "http://www.stats.gov.cn/tjsj/zxfb/201702/t20170228_1467424.html"),
        ("rmzxb", "http://www.rmzxb.com.cn/c/2017-03-01/1370289.shtml"),
        ("sina", "https://finance.sina.com.cn/roll/2017-01-20/doc-ifxzunxf1559245.shtml"),
    ],
    2017: [
        ("govcn", "https://www.gov.cn/xinwen/2018-02/28/content_5269506.htm"),
        ("govcn_http", "http://www.gov.cn/xinwen/2018-02/28/content_5269506.htm"),
        ("stats_http", "http://www.stats.gov.cn/tjsj/zxfb/201802/t20180228_1585631.html"),
        ("govcn_alt", "https://www.gov.cn/shuju/2018-02/28/content_5269506.htm"),
    ],
    2018: [
        ("govcn", "https://www.gov.cn/xinwen/2019-02/28/content_5369281.htm"),
        ("govcn_http", "http://www.gov.cn/xinwen/2019-02/28/content_5369281.htm"),
        ("stats_http", "http://www.stats.gov.cn/tjsj/zxfb/201902/t20190228_1651265.html"),
    ],
    2019: [
        ("govcn", "https://www.gov.cn/xinwen/2020-02/28/content_5484361.htm"),
        ("govcn_http", "http://www.gov.cn/xinwen/2020-02/28/content_5484361.htm"),
        ("stats_http", "http://www.stats.gov.cn/tjsj/zxfb/202002/t20200228_1728913.html"),
    ],
    2020: [
        ("govcn", "https://www.gov.cn/xinwen/2021-02/28/content_5589283.htm"),
        ("govcn_http", "http://www.gov.cn/xinwen/2021-02/28/content_5589283.htm"),
        ("stats_http", "http://www.stats.gov.cn/tjsj/zxfb/202102/t20210227_1814154.html"),
    ],
    2021: [
        ("govcn", "https://www.gov.cn/xinwen/2022-02/28/content_5676015.htm"),
        ("govcn_http", "http://www.gov.cn/xinwen/2022-02/28/content_5676015.htm"),
        ("stats_http", "http://www.stats.gov.cn/tjsj/zxfb/202202/t20220227_1827960.html"),
    ],
    2022: [
        ("govcn", "https://www.gov.cn/xinwen/2023-02/28/content_5743491.htm"),
        ("govcn_http", "http://www.gov.cn/xinwen/2023-02/28/content_5743491.htm"),
        ("stats_http", "http://www.stats.gov.cn/tjsj/zxfb/202302/t20230227_1918980.html"),
        ("crca_pdf", "http://www.crca.cn/images/2022.pdf"),
    ],
    2023: [
        ("govcn", "https://www.gov.cn/lianbo/bumen/2024-02/29/content_6911084.htm"),
        ("govcn2", "https://www.gov.cn/xinwen/2024-02/29/content_6911084.htm"),
        ("stats_http", "http://www.stats.gov.cn/sj/zxfb/202402/t20240228_1947915.html"),
        ("stats_http2", "http://www.stats.gov.cn/tjsj/zxfb/202402/t20240228_1947915.html"),
    ],
    2024: [
        ("govcn", "https://www.gov.cn/lianbo/bumen/2025-02/28/content_7004292.htm"),
        ("govcn2", "https://www.gov.cn/lianbo/bumen/2025-02/28/content_7004293.htm"),
        ("tqx", "http://tqx.gov.cn/gongkai/show/508dc7f99367db87d1d4831c1e1534c9.html"),
        ("stats_http", "http://www.stats.gov.cn/sj/zxfb/202502/t20250228_1958565.html"),
    ],
}

REQ_YEARS = list(range(2016, 2025))

report = {}
for year in REQ_YEARS:
    report[str(year)] = []
    for tag, url in CANDIDATES.get(year, []):
        ok, status, data, final = fetch(url)
        enc = sniff_meta_encoding(data) if ok and data else None
        text = decode(data) if ok and data else ""
        has_birth = ("出生人口" in text) or ("\u51fa\u751f\u4eba\u53e3" in text)
        has_bulletin = ("统计公报" in text) or ("\u7edf\u8ba1\u516c\u62a5" in text)
        rec = {
            "year": year, "tag": tag, "url": url, "final_url": final,
            "ok": ok, "status": status, "bytes": len(data) if ok else 0,
            "declared_charset": enc, "has_birth_kw": has_birth,
            "has_bulletin_kw": has_bulletin,
        }
        print("Y%d %-12s ok=%-5s status=%-5s bytes=%-8s birth=%-5s bulletin=%-5s" % (
            year, tag, ok, status, rec["bytes"], has_birth, has_bulletin), flush=True)
        if ok and data and len(data) > 3000:
            fn = os.path.join(RAW, "bulletin_%d__%s.html" % (year, tag))
            with open(fn, "wb") as f:
                f.write(data)
            rec["saved"] = fn
        report.setdefault(str(year), []).append(rec)
        time.sleep(0.6)

with open(REPORT, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print("\n=== SUMMARY ===")
for year in REQ_YEARS:
    hits = [r for r in report[str(year)] if r.get("ok") and r.get("has_birth_kw")]
    print("Y%d usable_with_birth_kw=%d" % (year, len(hits)))
