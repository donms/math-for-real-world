#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W54 · 路 A 批抓：**江苏省土地出让公告批量抓取器**。

## 完整的接口机制（7 轮探针的最终成果）

### ① 分页接口（**POST**，返回 JSON）

```javascript
function getPageList(start, limit) {
  var Param = {};
  Param.start   = start;        // ★ 页码（从 1 开始）
  Param.limit   = limit;        // 每页条数（实测 18）
  Param.xzqhdm  = $("#xzqhdm").val();       // 区划码
  Param.lx      = $("#lx").val();           // 类型（0/1/null）
  Param.affiche_no  = ...;      // 公告编号（模糊筛）
  Param.remise_type = ...;      // 出让方式
  Param.starttime   = ...;      // 起始时间
  Param.endtime     = ...;      // 结束时间
  $.post("tdsc_getTdcrList.action", Param, function(resp) {
      var result = eval("(" + resp + ")");
      $("#tdcrTableHtml").html(result.tableHtml);   // 表格 HTML
      $("#tdcrPagingHtml").html(result.pageHtml);   // 分页 HTML
  });
}
```

### ② 公告详情（GET）

```
tdsc_getTdcrxx.action?lx=0&id=<公告ID>&xzqhdm=<区划码>
```

### ③ 宗地详情（GET）—— ★ 面积/建面/容积率都在这里

```
tdsc_getDkxx.action?id=<GUID>&tid=<公告ID>&xzqhdm=<区划码>
```

## 本脚本做什么

1. **POST 翻页**取公告 ID 列表（吴江区 585 条 ⇒ 33 页）；
2. 对每个公告 GET 详情，**抽出其中所有宗地的 GUID**；
3. 对每个宗地 GET 详情，**解析出让面积 / 建筑面积 / 容积率 / 用途**；
4. 落盘成 CSV + JSONL。

**★ 纪律**：
* 只抓**住宅用途**的（本题只关心住宅）；
* **请求间隔 0.5s**（不给对方压力）；
* **可断点续跑**（已抓的跳过）；
* 先跑**小样本**确认无误，再放量。
"""
from __future__ import annotations

import argparse
import csv
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

EP = ROOT / "episodes" / "2026-W54"
RAW = EP / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
OUTJSONL = EP / "data" / "江苏宗地.jsonl"
OUTCSV = EP / "data" / "江苏宗地.csv"

HOST = "http://zrzy.jiangsu.gov.cn/gtapp/xxgk/"
LIST_POST = HOST + "tdsc_getTdcrList.action"
TXT = HOST + "tdsc_getTdcrxx.action"
DK = HOST + "tdsc_getDkxx.action"

# 江苏各市区划码
DISTRICTS: list[tuple[str, str]] = [
    ("320500", "苏州市区"),
    ("320584", "苏州吴江"),
    ("320581", "苏州常熟"),
    ("320582", "苏州张家港"),
    ("320583", "苏州昆山"),
    ("320585", "苏州太仓"),
    # 全省铺开（第二批）
    ("320100", "南京"), ("320200", "无锡"), ("320300", "徐州"),
    ("320400", "常州"), ("320600", "南通"), ("320700", "连云港"),
    ("320800", "淮安"), ("320900", "盐城"), ("321000", "扬州"),
    ("321100", "镇江"), ("321200", "泰州"), ("321300", "宿迁"),
]


def post(url: str, data: dict, timeout: int = 30) -> str:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": "Mozilla/5.0 (research; land-data)"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            break
        except Exception:                                         # noqa: BLE001
            if attempt == 2:
                raise
            time.sleep(2 + attempt * 3)
    for enc in ("utf-8", "gbk", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


def get(url: str, timeout: int = 30) -> str:
    return open_url(url, timeout=timeout, tries=2).read(
        900000).decode("utf-8", "ignore")


def ids_from(html: str) -> list[str]:
    return sorted(set(re.findall(
        r"tdsc_getTdcrxx\.action\?[^\"'<>\s]*id=([0-9]+)", html)))


def guids_from(html: str) -> list[str]:
    return sorted(set(re.findall(
        r"tdsc_getDkxx\.action\?id=([0-9a-f]{16,})", html)))


def kv_from(html: str) -> dict[str, str]:
    r"""把详情页的 `<tr>`/`<td>` 拆成 标签->值。"""
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


def num(s: str | None) -> float | None:
    if not s:
        return None
    m = re.search(r"[0-9][0-9,]*\.?[0-9]*", str(s).replace(",", ""))
    return float(m.group(0)) if m else None


def far_of(s: str | None) -> float | None:
    r"""从「1.02≤容积率≤1.05」这类串里取**上限**。"""
    if not s:
        return None
    v = re.findall(r"[0-9]+\.?[0-9]*", str(s))
    return float(v[-1]) if v else None


def crawl(district: str, name: str, max_pages: int, delay: float,
          seen: set[str], fh) -> dict:
    stat = {"地区": name, "公告数": 0, "住宅宗地": 0, "翻页": 0}
    for page in range(1, max_pages + 1):
        try:
            resp = post(LIST_POST, {"start": page, "limit": 18,
                                    "xzqhdm": district, "lx": "",
                                    "affiche_no": "", "remise_type": "",
                                    "starttime": "", "endtime": ""})
        except Exception as e:                                    # noqa: BLE001
            print(f"    [X] 第{page}页 POST 失败 {type(e).__name__}")
            break
        # 响应是 JSON（含 tableHtml）
        try:
            d = json.loads(resp)
            table = d.get("tableHtml") or ""
        except Exception:                                         # noqa: BLE001
            table = resp
        aids = ids_from(table)
        if not aids:
            print(f"    第{page}页无公告 ⇒ 停止")
            break
        stat["翻页"] += 1
        new = [a for a in aids if a not in seen]
        print(f"    第{page}页 {len(aids)} 条（新 {len(new)}）")
        if not new:
            break
        for aid in new:
            seen.add(aid)
            stat["公告数"] += 1
            try:
                t = get(f"{TXT}?lx=0&id={aid}&xzqhdm={district}")
            except Exception:                                     # noqa: BLE001
                continue
            for gid in guids_from(t):
                try:
                    dk = get(f"{DK}?id={gid}&tid={aid}&xzqhdm={district}")
                except Exception:                                 # noqa: BLE001
                    continue
                kv = kv_from(dk)
                use = kv.get("规划用途", "")
                if "住宅" not in use:
                    continue
                rec = {
                    "区划码": district, "地区": name, "公告ID": aid,
                    "宗地GUID": gid,
                    "地块编号": kv.get("公告地块编号", "").replace(
                        " 查看公告", "").strip(),
                    "地块名称": kv.get("地块名称", ""),
                    "出让面积_m2": num(kv.get("出让面积（平方米）")),
                    "建筑面积_m2": num(kv.get("建筑面积（平方米）")),
                    "容积率": far_of(kv.get("容积率")),
                    "容积率原文": kv.get("容积率", ""),
                    "规划用途": use,
                    "出让年限": num(kv.get("出让年限（年）")),
                    "起始价_万元": num(kv.get("起始价")),
                    "保证金_万元": num(kv.get("竞买保证金（万元）")),
                    "建筑限高_m": num(kv.get("建筑限高（米）")),
                    "公告编号": kv.get("公告编号", ""),
                    "挂牌起始": kv.get("挂牌起始时间", ""),
                    "挂牌截止": kv.get("挂牌截止时间", ""),
                }
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                stat["住宅宗地"] += 1
                time.sleep(delay)
        time.sleep(delay)
    return stat


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=2,
                    help="每个区划最多翻几页（每页 18 条公告）")
    ap.add_argument("--delay", type=float, default=0.5)
    args = ap.parse_args()

    print("=" * 96)
    print("  W54 · 路 A 批抓：江苏省土地出让公告（住宅宗地）")
    print("=" * 96)
    print(f"  每区划最多 {args.max_pages} 页（{args.max_pages*18} 条公告）"
          f"｜请求间隔 {args.delay}s")
    print(f"  输出 {OUTJSONL.name}\n")

    seen: set[str] = set()
    # 断点续跑：读已有
    if OUTJSONL.exists():
        for ln in OUTJSONL.open(encoding="utf-8"):
            try:
                seen.add(json.loads(ln)["公告ID"])
            except Exception:                                     # noqa: BLE001
                pass
        print(f"  [续跑] 已有 {len(seen)} 个公告\n")

    stats = []
    with OUTJSONL.open("a", encoding="utf-8") as fh:
        for code, nm in DISTRICTS:
            print(f"-- {nm}（{code}）--")
            st = crawl(code, nm, args.max_pages, args.delay, seen, fh)
            stats.append(st)
            print(f"   ⇒ 公告 {st['公告数']}｜住宅宗地 {st['住宅宗地']}\n")

    # 汇总
    rows = []
    if OUTJSONL.exists():
        for ln in OUTJSONL.open(encoding="utf-8"):
            try:
                rows.append(json.loads(ln))
            except Exception:                                     # noqa: BLE001
                pass
    print(f"{'='*96}")
    print(f"  累计住宅宗地 **{len(rows)}** 宗")
    if rows:
        cols = list(rows[0].keys())
        with OUTCSV.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"  [落盘] {OUTCSV}")
        areas = [r["建筑面积_m2"] for r in rows if r.get("建筑面积_m2")]
        if areas:
            areas.sort()
            print(f"\n  -- 建筑面积分布（㎡）--")
            print(f"     n={len(areas)}  最小 {areas[0]:,.0f}  "
                  f"中位 {areas[len(areas)//2]:,.0f}  最大 {areas[-1]:,.0f}")
            for lo, hi in ((0, 10000), (10000, 26000), (26000, 50000),
                           (50000, 100000), (100000, 10**9)):
                c = sum(1 for a in areas if lo <= a < hi)
                print(f"     {lo:>7,}–{hi if hi < 10**9 else '∞':>9} ㎡ : "
                      f"{c:>3} 宗（{c/len(areas)*100:>5.1f}%）")
            print(f"\n  -- 反推户数（÷130 ㎡）--")
            hh = sorted(a / 130 for a in areas)
            for lo, hi in ((0, 100), (100, 200), (200, 500), (500, 10**9)):
                c = sum(1 for x in hh if lo <= x < hi)
                print(f"     {lo:>4}–{hi if hi < 10**9 else '∞':>6} 户 : "
                      f"{c:>3} 宗（{c/len(hh)*100:>5.1f}%）")
    (RAW / "jiangsu_crawl_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
