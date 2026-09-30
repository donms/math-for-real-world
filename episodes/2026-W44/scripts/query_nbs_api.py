# -*- coding: utf-8 -*-
"""Query the NBS national data API (data.stats.gov.cn) for the annual
birth-population series.  Prints ASCII-only status; writes JSON to disk."""
import os, ssl, gzip, json, re, urllib.request, urllib.parse, urllib.error

BASE = r".\episodes\2026-W44"
RAW = os.path.join(BASE, "data", "raw", "stats")
os.makedirs(RAW, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://data.stats.gov.cn/easyquery.htm?cn=C01",
    "Connection": "close",
}


def ctx():
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    try: c.set_ciphers("DEFAULT@SECLEVEL=1")
    except Exception: pass
    return c


def get(url, timeout=60):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS),
                                    timeout=timeout, context=ctx()) as r:
            d = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                try: d = gzip.decompress(d)
                except Exception: pass
            return r.status, d
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:
        return None, repr(e).encode("utf-8", "replace")


BASEURL = "https://data.stats.gov.cn/easyquery.htm"

# 1) get the indicator tree under 人口 (A03)
q = {"id": "A03", "dbcode": "hgnd", "wdcode": "zb", "m": "getTree"}
st, d = get(BASEURL + "?" + urllib.parse.urlencode(q))
print("tree A03 status=%s bytes=%d" % (st, len(d)))
tree = None
try:
    tree = json.loads(d.decode("utf-8"))
except Exception as e:
    print("  parse fail:", repr(e), d[:200])
if tree:
    with open(os.path.join(RAW, "_nbs_api_tree_A03.json"), "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=2)
    for node in tree if isinstance(tree, list) else []:
        print("  id=%-10s name=%s" % (node.get("id"), node.get("name")))
        for ch in node.get("children", []) or []:
            if ch.get("children"):
                for g in ch["children"]:
                    print("      id=%-12s name=%s" % (g.get("id"), g.get("name")))
            else:
                print("      id=%-12s name=%s" % (ch.get("id"), ch.get("name")))
