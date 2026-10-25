#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W54 · 路 A 分层抓取 **v2**：每格立刻打印，便于发现"空转"。

## v1 的问题（实测）

跑 4 分钟**一个字都不输出、也不写盘** ⇒ 无法判断是"在跑"还是"卡住"。
（API 实测 0.2s/请求，没有被限流 ⇒ 是脚本**静默空转**：
某些「区划×季度」的公告已在 `seen` 里，`new` 为空就 `break`，但**不打印**。）

## v2 的修法

1. **每个格子无条件打印一行**（含：查到几条公告、新几条、抓到几宗住宅）；
2. **每完成一个格子就 flush**；
3. 单请求超时降到 **12 秒**，失败只重试 2 次 ⇒ 不会长时间卡住；
4. 收尾时打印**汇总表**（格子 × 结果）。

用法：
    $PY fetch_jiangsu_stratified.py --pages-per-cell 2 --delay 0.25 \\
        --districts 320500,320584,320581
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
JSONL = EP / "data" / "江苏宗地.jsonl"
CSV = EP / "data" / "江苏宗地.csv"
HOST = "http://zrzy.jiangsu.gov.cn/gtapp/xxgk/"
LIST_POST = HOST + "tdsc_getTdcrList.action"
TXT = HOST + "tdsc_getTdcrxx.action"
DK = HOST + "tdsc_getDkxx.action"

DISTRICTS = [("320500", "苏州市区"), ("320584", "苏州吴江"),
             ("320581", "苏州常熟"), ("320582", "苏州张家港"),
             ("320583", "苏州昆山"), ("320585", "苏州太仓"),
             ("320100", "南京"), ("320200", "无锡"), ("320300", "徐州"),
             ("320400", "常州"), ("320600", "南通"), ("320700", "连云港"),
             ("320800", "淮安"), ("320900", "盐城"), ("321000", "扬州"),
             ("321100", "镇江"), ("321200", "泰州"), ("321300", "宿迁")]

QUARTERS = [("2024Q3", "2024-07-01", "2024-09-30"),
            ("2024Q4", "2024-10-01", "2024-12-31"),
            ("2025Q1", "2025-01-01", "2025-03-31"),
            ("2025Q2", "2025-04-01", "2025-06-30"),
            ("2025Q3", "2025-07-01", "2025-09-30"),
            ("2025Q4", "2025-10-01", "2025-12-31"),
            ("2026Q1", "2026-01-01", "2026-03-31"),
            ("2026Q2", "2026-04-01", "2026-06-30"),
            ("2026Q3", "2026-07-01", "2026-09-30"),
            ("2026Q4", "2026-10-01", "2026-12-31")]


def post(data: dict, timeout: int = 12) -> str:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        LIST_POST, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": "Mozilla/5.0 (research; land-data)"})
    last = None
    for att in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            for enc in ("utf-8", "gbk", "gb18030"):
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", "ignore")
        except Exception as e:                                    # noqa: BLE001
            last = e
            time.sleep(1.5)
    raise last                                                # type: ignore


def get(url: str, timeout: int = 12) -> str:
    return open_url(url, timeout=timeout, tries=1).read(
        900000).decode("utf-8", "ignore")


def ids_of(s: str) -> list[str]:
    return sorted(set(re.findall(
        r"tdsc_getTdcrxx\.action\?[^\"'<>\s]*id=([0-9]+)", s)))


def guids_of(s: str) -> list[str]:
    return sorted(set(re.findall(
        r"tdsc_getDkxx\.action\?id=([0-9a-f]{16,})", s)))


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


def num(s: str | None) -> float | None:
    if not s:
        return None
    m = re.search(r"[0-9][0-9,]*\.?[0-9]*", str(s).replace(",", ""))
    return float(m.group(0)) if m else None


def far_of(s: str | None) -> float | None:
    if not s:
        return None
    v = re.findall(r"[0-9]+\.?[0-9]*", str(s))
    return float(v[-1]) if v else None


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages-per-cell", type=int, default=2)
    ap.add_argument("--delay", type=float, default=0.25)
    ap.add_argument("--districts", default="")
    args = ap.parse_args()

    dists = DISTRICTS
    if args.districts:
        want = {x.strip() for x in args.districts.split(",") if x.strip()}
        dists = [d for d in DISTRICTS if d[0] in want]

    log("=" * 96)
    log("  W54 · 路 A 分层抓取 v2（每格打印）")
    log("=" * 96)
    log(f"  区划 {len(dists)} × 季度 {len(QUARTERS)} × 每格 "
        f"{args.pages_per_cell} 页｜间隔 {args.delay}s")

    seen: set[str] = set()
    if JSONL.exists():
        for ln in JSONL.open(encoding="utf-8"):
            try:
                seen.add(str(json.loads(ln)["公告ID"]))
            except Exception:                                     # noqa: BLE001
                pass
    log(f"  [续跑] 已有 {len(seen)} 个公告\n")

    n_new = 0
    summary: list[tuple[str, str, int, int, int]] = []
    fh = JSONL.open("a", encoding="utf-8")
    for code, nm in dists:
        log(f"== {nm}（{code}）==")
        for q, a, b in QUARTERS:
            t0 = time.time()
            found = newa = got = 0
            for page in range(1, args.pages_per_cell + 1):
                try:
                    resp = post({"start": page, "limit": 18, "xzqhdm": code,
                                 "lx": "", "affiche_no": "", "remise_type": "",
                                 "starttime": a, "endtime": b})
                except Exception as e:                            # noqa: BLE001
                    log(f"   {q} p{page} [POST X] {type(e).__name__}")
                    break
                try:
                    table = json.loads(resp).get("tableHtml") or ""
                except Exception:                                 # noqa: BLE001
                    table = resp
                aids = ids_of(table)
                found += len(aids)
                if not aids:
                    break
                new = [x for x in aids if x not in seen]
                if not new:
                    break
                newa += len(new)
                for aid in new:
                    seen.add(aid)
                    try:
                        t = get(f"{TXT}?lx=0&id={aid}&xzqhdm={code}")
                    except Exception:                             # noqa: BLE001
                        continue
                    for gid in guids_of(t):
                        try:
                            dk = get(f"{DK}?id={gid}&tid={aid}"
                                     f"&xzqhdm={code}")
                        except Exception:                         # noqa: BLE001
                            continue
                        kv = kv_of(dk)
                        if "住宅" not in kv.get("规划用途", ""):
                            continue
                        rec = {
                            "区划码": code, "地区": nm,
                            "采集批次": "分层-季度", "季度": q,
                            "公告ID": aid, "宗地GUID": gid,
                            "地块编号": kv.get(
                                "公告地块编号", "").replace(
                                " 查看公告", "").strip(),
                            "地块名称": kv.get("地块名称", ""),
                            "出让面积_m2": num(kv.get("出让面积（平方米）")),
                            "建筑面积_m2": num(kv.get("建筑面积（平方米）")),
                            "容积率": far_of(kv.get("容积率")),
                            "容积率原文": kv.get("容积率", ""),
                            "规划用途": kv.get("规划用途", ""),
                            "出让年限": num(kv.get("出让年限（年）")),
                            "起始价_万元": num(kv.get("起始价")),
                            "保证金_万元": num(
                                kv.get("竞买保证金（万元）")),
                            "建筑限高_m": num(kv.get("建筑限高（米）")),
                            "公告编号": kv.get("公告编号", ""),
                            "挂牌起始": kv.get("挂牌起始时间", ""),
                            "挂牌截止": kv.get("挂牌截止时间", ""),
                        }
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        fh.flush()
                        got += 1
                        n_new += 1
                        time.sleep(args.delay)
                time.sleep(args.delay)
            log(f"   {q}  公告 {found:>3}｜新 {newa:>3}｜"
                f"住宅宗地 +{got:<3}（{time.time()-t0:>5.1f}s）")
            summary.append((nm, q, found, newa, got))
        log("")
    fh.close()

    # 汇总
    tot = sum(s[4] for s in summary)
    log("=" * 96)
    log(f"  本次新增 {n_new} 宗（汇总 {tot}）")
    log(f"  {'地区':<12}{'季度':<9}{'公告':>6}{'新公告':>7}{'住宅宗地':>9}")
    for nm, q, f0, na, g in summary:
        if na:
            log(f"  {nm:<12}{q:<9}{f0:>6}{na:>7}{g:>9}")

    # 重建 CSV（列名取并集）
    rows = []
    for ln in JSONL.open(encoding="utf-8"):
        try:
            rows.append(json.loads(ln))
        except Exception:                                         # noqa: BLE001
            continue
    if rows:
        cols: list[str] = []
        for r in rows:
            for k in r:
                if k not in cols:
                    cols.append(k)
        for r in rows:
            for c in cols:
                r.setdefault(c, "")
        with CSV.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    log(f"\n  累计 **{len(rows)}** 宗  ⇒ {CSV.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
