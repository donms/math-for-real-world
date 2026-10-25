#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W54 · 诊断：**为什么分层批次"住宅宗地 +0"**？

## 症状

分层抓取 v2 报告：
```
2024Q3  公告  15｜新  14｜住宅宗地 +0
2024Q4  公告  22｜新  16｜住宅宗地 +0
...
```
**公告都找到了（新 14–21 条），但一宗住宅都没解析出来。**

## 单步查

| 步 | 应该发生什么 |
|---|---|
| 1 | POST 列表 ⇒ 得到公告 ID |
| 2 | GET `tdsc_getTdcrxx.action?lx=0&id=<ID>&xzqhdm=<码>` ⇒ 页里含**宗地 GUID** |
| 3 | GET `tdsc_getDkxx.action?id=<GUID>&tid=<ID>&xzqhdm=<码>` ⇒ 含**出让面积/建筑面积/规划用途** |

**逐条打印**：GUID 提没提到、`规划用途` 字段读到什么。
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from net_resolve import open_url                                  # noqa: E402

RAW = ROOT / "episodes" / "2026-W54" / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
HOST = "http://zrzy.jiangsu.gov.cn/gtapp/xxgk/"
LIST_POST = HOST + "tdsc_getTdcrList.action"
TXT = HOST + "tdsc_getTdcrxx.action"
DK = HOST + "tdsc_getDkxx.action"


def post(data: dict, timeout: int = 15) -> str:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        LIST_POST, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": "Mozilla/5.0 (research)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return raw.decode("utf-8", "ignore")


def get(url: str, timeout: int = 15) -> str:
    return open_url(url, timeout=timeout, tries=1).read(
        900000).decode("utf-8", "ignore")


def kv_of(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in re.finditer(r"<tr.*?</tr>", html, re.S | re.I):
        tds = [re.sub(r"\s+", " ",
                      re.sub(r"<[^>]+>", "", x)).replace("&nbsp;", " ").strip()
               for x in re.findall(r"<td.*?</td>", m.group(0), re.S | re.I)]
        tds = [x for x in tds if x]
        if len(tds) >= 2 and len(tds) % 2 == 0:
            for i in range(0, len(tds), 2):
                out.setdefault(tds[i], tds[i + 1])
        elif tds:
            out.setdefault(tds[0], " ".join(tds[1:]))
    return out


def main() -> int:
    print("=" * 94)
    print("  W54 · 诊断：分层批次为什么「住宅宗地 +0」")
    print("=" * 94)

    # 1) 取一个已知「未抓过」的季度（2024Q3 苏州市区）
    r = post({"start": 1, "limit": 18, "xzqhdm": "320500", "lx": "",
              "affiche_no": "", "remise_type": "",
              "starttime": "2024-07-01", "endtime": "2024-09-30"})
    try:
        table = json.loads(r).get("tableHtml") or ""
    except Exception:                                             # noqa: BLE001
        table = r
    aids = sorted(set(re.findall(
        r"tdsc_getTdcrxx\.action\?[^\"'<>\s]*id=([0-9]+)", table)))
    print(f"\n-- 1. 列表：2024Q3 苏州市区 公告 {len(aids)} 条")
    print(f"   {aids[:8]}")

    # 2) 逐个取公告，看 GUID 情况
    print(f"\n-- 2. 公告页 → 宗地 GUID（前 4 条）--")
    allg: list[tuple[str, str]] = []
    for aid in aids[:4]:
        url = f"{TXT}?lx=0&id={aid}&xzqhdm=320500"
        try:
            t = get(url)
        except Exception as e:                                    # noqa: BLE001
            print(f"   id={aid}  [X] {type(e).__name__}: {str(e)[:40]}")
            continue
        g1 = sorted(set(re.findall(
            r"tdsc_getDkxx\.action\?id=([0-9a-f]{16,})", t)))
        g2 = re.findall(r"tdsc_getDkxx\.action[^\"'<>\s]{0,120}", t)
        print(f"   id={aid}  {len(t):>7,}B  "
              f"GUID(hex16+)={len(g1)}  dkxx链接={len(g2)}")
        if g2:
            print(f"      示例: {g2[0][:100]}")
        if not g1 and g2:
            print(f"      ★ GUID 正则没匹配上！实际形态见上")
        for x in g1:
            allg.append((aid, x))
        time.sleep(0.3)

    # 3) 宗地页解析
    print(f"\n-- 3. 宗地页字段（前 3 宗）--")
    for aid, gid in allg[:3]:
        url = f"{DK}?id={gid}&tid={aid}&xzqhdm=320500"
        try:
            t = get(url)
        except Exception as e:                                    # noqa: BLE001
            print(f"   gid={gid[:10]}  [X] {type(e).__name__}")
            continue
        kv = kv_of(t)
        use = kv.get("规划用途", "（无此字段）")
        print(f"   gid={gid[:10]}…  {len(t):>7,}B  字段 {len(kv)}  "
              f"用途=【{use}】")
        for k in ("出让面积（平方米）", "建筑面积（平方米）", "容积率",
                  "公告地块编号"):
            if k in kv:
                print(f"       {k} = {kv[k][:40]}")
        if "规划用途" not in kv:
            print(f"       ⚠️ 没有「规划用途」字段 ⇒ "
                  f"`\"住宅\" in \"\"` 恒为 False ⇒ 全部被过滤掉！")
            print(f"       实际字段名样例：{sorted(kv)[:12]}")
        time.sleep(0.3)

    print(f"\n{'='*94}")
    print("  判定")
    print(f"{'='*94}")
    print(f"  公告页提到 GUID：{'是' if allg else '★ 否 —— 断在第 2 步'}")
    print(f"  宗地页有「规划用途」：见上")

    (RAW / "diag_stratified.json").write_text(
        json.dumps({"aids": aids[:8],
                    "guids": [{"公告": a, "gid": g} for a, g in allg[:12]]},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
