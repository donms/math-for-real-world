# -*- coding: utf-8 -*-
"""Fetch the official NBS Statistical Communiques (2016-2024) over http.

stats.gov.cn blocks https for scripts but serves http fine.
Falls back to official mirrors (gov.cn, provincial gov) and then media.
"""
import os
import ssl
import json
import gzip
import time
import urllib.request
import urllib.error

BASE = r".\episodes\2026-W44"
RAW = os.path.join(BASE, "data", "raw", "stats")
os.makedirs(RAW, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "close",
    "Referer": "http://www.stats.gov.cn/sj/tjgb/ndtjgb/",
}


def ctx():
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    try:
        c.set_ciphers("DEFAULT@SECLEVEL=1")
    except Exception:
        pass
    return c


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx()) as r:
            d = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                try:
                    d = gzip.decompress(d)
                except Exception:
                    pass
            return r.status, d, r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, b"", url
    except Exception as e:
        return None, repr(e).encode("utf-8", "replace"), url


def dec(d):
    for e in ("utf-8", "gb18030", "gbk"):
        try:
            return d.decode(e)
        except Exception:
            pass
    return d.decode("utf-8", "replace")


# year -> list of (tag, url).  tag prefix "OFFICIAL_" = 国家统计局/government
PLAN = {
    2016: [
        ("NBS_old", "http://www.stats.gov.cn/tjsj/zxfb/201702/t20170228_1467424.html"),
        ("NBS_old2", "http://www.stats.gov.cn/tjsj/zxfb/201702/t20170228_1467424.htm"),
        ("NBS_sj", "http://www.stats.gov.cn/sj/zxfb/201702/t20170228_1467424.html"),
        ("GOVCN", "http://www.gov.cn/shuju/2017-02/28/content_5171492.htm"),
        ("RMZXB", "http://www.rmzxb.com.cn/c/2017-03-01/1370289.shtml"),
        ("SINA", "https://finance.sina.com.cn/roll/2017-01-20/doc-ifxzunxf1559245.shtml"),
    ],
    2017: [
        ("NBS_old", "http://www.stats.gov.cn/tjsj/zxfb/201802/t20180228_1585631.html"),
        ("NBS_sj", "http://www.stats.gov.cn/sj/zxfb/201802/t20180228_1585631.html"),
        ("GOVCN", "http://www.gov.cn/xinwen/2018-02/28/content_5269506.htm"),
    ],
    2018: [
        ("NBS", "http://www.stats.gov.cn/sj/zxfb/202302/t20230203_1900241.html"),
        ("NBS_old", "http://www.stats.gov.cn/tjsj/zxfb/201902/t20190228_1651265.html"),
        ("GOVCN", "http://www.gov.cn/xinwen/2019-02/28/content_5369281.htm"),
    ],
    2019: [
        ("NBS", "http://www.stats.gov.cn/sj/zxfb/202302/t20230203_1900640.html"),
        ("NBS_old", "http://www.stats.gov.cn/tjsj/zxfb/202002/t20200228_1728913.html"),
        ("GOVCN", "http://www.gov.cn/xinwen/2020-02/28/content_5484361.htm"),
    ],
    2020: [
        ("NBS", "http://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901004.html"),
        ("NBS_old", "http://www.stats.gov.cn/tjsj/zxfb/202102/t20210227_1814154.html"),
        ("GOVCN", "http://www.gov.cn/xinwen/2021-02/28/content_5589283.htm"),
    ],
    2021: [
        ("NBS", "http://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901393.html"),
        ("NBS_old", "http://www.stats.gov.cn/tjsj/zxfb/202202/t20220227_1827960.html"),
        ("GOVCN", "http://www.gov.cn/xinwen/2022-02/28/content_5676015.htm"),
    ],
    2022: [
        ("NBS", "http://www.stats.gov.cn/sj/zxfb/202302/t20230228_1919011.html"),
        ("NBS_old", "http://www.stats.gov.cn/tjsj/zxfb/202302/t20230227_1918980.html"),
        ("GOVCN", "http://www.gov.cn/xinwen/2023-02/28/content_5743491.htm"),
    ],
    2023: [
        ("NBS", "http://www.stats.gov.cn/sj/zxfb/202402/t20240228_1947915.html"),
        ("GOVCN", "http://www.gov.cn/lianbo/bumen/2024-02/29/content_6911084.htm"),
    ],
    2024: [
        ("NBS", "http://www.stats.gov.cn/sj/zxfb/202502/t20250228_1958817.html"),
        ("GOVCN", "http://www.gov.cn/lianbo/bumen/2025-02/28/content_7004292.htm"),
        ("TQX", "http://tqx.gov.cn/gongkai/show/508dc7f99367db87d1d4831c1e1534c9.html"),
    ],
}

report = {}
for year in sorted(PLAN):
    report[str(year)] = []
    for tag, url in PLAN[year]:
        st, d, fu = get(url)
        t = dec(d) if d else ""
        nb = t.count("\u51fa\u751f\u4eba\u53e3")
        nb2 = t.count("\u5168\u5e74\u51fa\u751f\u4eba\u53e3")
        rec = {"year": year, "tag": tag, "url": url, "status": st,
               "bytes": len(d), "birth_kw": nb, "quanmian_kw": nb2,
               "is_bulletin": "\u7edf\u8ba1\u516c\u62a5" in t}
        print("Y%d %-9s %-6s bytes=%-8s 出生人口=%-3d 全年出生人口=%-2d bulletin=%s"
              % (year, tag, st, len(d), nb, nb2, rec["is_bulletin"]), flush=True)
        if st == 200 and len(d) > 3000:
            fn = os.path.join(RAW, "bulletin_%d__%s.html" % (year, tag))
            with open(fn, "wb") as f:
                f.write(d)
            rec["saved"] = fn.replace(BASE + os.sep, "")
        report[str(year)].append(rec)
        time.sleep(0.5)

with open(os.path.join(RAW, "_fetch_report.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print("\n=== YEARS WITH AN OFFICIAL PAGE CONTAINING 全年出生人口 ===")
for year in sorted(PLAN):
    hits = [r for r in report[str(year)] if r.get("quanmian_kw", 0) > 0]
    tags = ",".join(r["tag"] for r in hits) or "NONE"
    print("Y%d : %s" % (year, tags))
