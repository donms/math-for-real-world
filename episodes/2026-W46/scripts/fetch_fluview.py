#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W46 · 抓取 Delphi Epidata 的流感监测长序列（**主数据源**）。

## 决策记录（用户 2026-09-29 拍板）

* **数据基座**：双源 —— **Delphi 长序列建方法** + **中国 CDC 周报做当期案例**；
* **模型族**：双亚型 SIR + 季节性强迫；
* **不确定性**：Bayes 变点 + 粒子滤波，**全部给区间**。

## 为什么主数据源换成 Delphi

实测（`probe_flu_history.py`）：
* 中国 CDC 栏目页**只有 12–14 期**（2024-07 起），无分页、无年份归档、站内搜索取不到
  => **不足一个完整流行季，建不了季节性项**；
* Delphi `fluview`（ILI 门诊监测）**2000 年至今 ≈1300 周**；
* Delphi `fluview_clinical`（实验室确诊）2024 年至今，**含 A/B 分型**
  => 补足"亚型更替"这一层。

## 两个端点

| 端点 | 字段 | 用途 |
|---|---|---|
| `fluview` | `ili` `num_ili` `num_patients` `wili` + 分年龄 | 长序列动力学、$R_t$、变点 |
| `fluview_clinical` | `total_specimens` `total_a` `total_b` `percent_a` `percent_b` | 亚型更替 |

## 纪律

* **原样落盘**（`data/raw/`），解析产物放 `data/clean/`；
* **缺失周不插值**，显式留空并在体检报告里说明。

用法：
    $PY fetch_fluview.py                 # 全量(2000–今)
    $PY fetch_fluview.py --start 2015    # 指定起始年
"""
from __future__ import annotations

import argparse
import csv
import json
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120 Safari/537.36"}
API = "https://api.delphi.cmu.edu/epidata/{ep}/?regions=nat&epiweeks={a}-{b}"

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "delphi"
CLEAN = ROOT / "data" / "clean"


def api(ep: str, a: str, b: str, tries: int = 4):
    url = API.format(ep=ep, a=a, b=b)
    last = ""
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=90, context=CTX) as r:
                d = json.loads(r.read().decode("utf-8", "ignore"))
            if d.get("result") == 1:
                return d.get("epidata") or [], ""
            last = f"result={d.get('result')} {d.get('message')}"
            if d.get("result") == -2:          # no results：该区间无数据，不必重试
                return [], last
        except Exception as e:                                   # noqa: BLE001
            last = f"{type(e).__name__}: {str(e)[:60]}"
        time.sleep(1.5 * (k + 1))
    return [], last


def weeks(y0: int, y1: int) -> list[str]:
    return [f"{y}{w:02d}" for y in range(y0, y1 + 1) for w in range(1, 54)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2000)
    ap.add_argument("--end", type=int, default=2026)
    ap.add_argument("--chunk", type=int, default=104)      # 每次请求 2 年
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    CLEAN.mkdir(parents=True, exist_ok=True)
    print("=" * 92)
    print(f"  W46 · Delphi 流感长序列 {args.start}–{args.end}")
    print("=" * 92)

    all_w = weeks(args.start, args.end)
    out: dict[str, list] = {}
    for ep in ("fluview", "fluview_clinical"):
        rows: list[dict] = []
        print(f"\n  ── {ep} ──")
        for i in range(0, len(all_w), args.chunk):
            a, b = all_w[i], all_w[min(i + args.chunk - 1, len(all_w) - 1)]
            got, err = api(ep, a, b)
            rows.extend(got)
            print(f"     {a}-{b}  +{len(got):>4} 行  累计 {len(rows):>5}"
                  f"{'  ' + err if err else ''}")
            time.sleep(0.6)
        # 去重（同 epiweek 取最新 release_date）
        by: dict[int, dict] = {}
        for r in rows:
            k = int(r["epiweek"])
            if k not in by or r.get("release_date", "") >= \
                    by[k].get("release_date", ""):
                by[k] = r
        ser = [by[k] for k in sorted(by)]
        out[ep] = ser
        print(f"     => 去重后 {len(ser)} 周"
              f"（{ser[0]['epiweek'] if ser else '—'} ~ "
              f"{ser[-1]['epiweek'] if ser else '—'}）")
        (RAW / f"{ep}.json").write_text(
            json.dumps(ser, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 落 CSV ----
    fv = out["fluview"]
    if fv:
        cols = ["epiweek", "release_date", "ili", "num_ili", "num_patients",
                "wili", "num_providers", "num_age_0", "num_age_1",
                "num_age_2", "num_age_3", "num_age_4", "num_age_5"]
        cols = [c for c in cols if c in fv[0]]
        p = CLEAN / "ili_weekly.csv"
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r in fv:
                w.writerow({c: r.get(c, "") for c in cols})
        print(f"\n  -> {p}  ({len(fv)} 周)")

    fc = out["fluview_clinical"]
    if fc:
        cols = ["epiweek", "release_date", "total_specimens", "total_a",
                "total_b", "percent_a", "percent_b", "percent_positive"]
        cols = [c for c in cols if c in fc[0]]
        p2 = CLEAN / "clinical_weekly.csv"
        with open(p2, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r in fc:
                w.writerow({c: r.get(c, "") for c in cols})
        print(f"  -> {p2}  ({len(fc)} 周)")

    # ---- 体检 ----
    rep = {"source": "Delphi Epidata (CMU) / api.delphi.cmu.edu",
           "fetched": time.strftime("%Y-%m-%d %H:%M"),
           "fluview": {"weeks": len(fv),
                       "range": [fv[0]["epiweek"], fv[-1]["epiweek"]]
                       if fv else None},
           "fluview_clinical": {"weeks": len(fc),
                                "range": [fc[0]["epiweek"], fc[-1]["epiweek"]]
                                if fc else None},
           "note": "按 epiweek 去重（保留最新 release_date）；缺失周不插值"}
    (CLEAN / "delphi_体检.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  -> {CLEAN/'delphi_体检.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
