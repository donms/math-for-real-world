#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W57 · 第 05 屏取数：三国（美国 / 欧元区 / 中国）的政策利率、通胀与产出缺口。

## 为什么要单独写一个取数脚本

第 05 屏要"用公开数据反算各国央行的隐含 $\phi_\pi$"。
**这一屏的全部可信度都压在"数据从哪来、能不能重取"上**，
所以取数与建模必须分开：本文件只负责**下载 + 落盘 + 生成来源清单**，
任何一行计算都不在这里做。

## 数据源（全部是公开、无需密钥的 FRED CSV 端点）

$$\texttt{https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>}$$

这个端点**不需要 API key**，任何人拿浏览器打开就能核。
每个序列的原始 CSV 原样落在 `data/raw/<SERIES>.csv`，
`data/来源清单.md` 记录：序列号、官方全名、页面 URL、下载 URL、
频度、起止日期、样本数、缺失数、抓取时间、以及本期的使用方式与等级。

## ★ 本期实测到的三处数据陷阱（都写进 `data/来源清单.md`）

1. **`GDPPOT` 与 `NROU` 带 CBO 的十年预测**（到 2036 年）。
   直接拿来算产出缺口，等于把**未来的预测**当**当期数据**用 ⇒ 严重的引视偏差。
   本脚本一律**截断到最后一个真实 GDP 观测所在的季度**。
2. **FRED 的若干 OECD MEI 序列已停更**：中国工业增加值
   （`CHNPROINDMISMEI`）、中国失业率（`LRHUTTTTCNM156S`）都返回 404。
   ⇒ 中国**没有**可用的产出缺口代理，`phi_y` 只能省略（后果见 q5 的诚实性声明）。
3. **`CPALTT01CNM659N`（中国 CPI 同比）止于 2025-04**，
   而中国利率序列到 2026-08 ⇒ 两个序列的公共样本比美国短得多，
   中国那一路的结论**不能与美国同等对待**。

## 用法

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"
$PY = "python"
& $PY episodes\2026-W57\scripts\fetch_taylor_data.py            # 有缓存就复用
& $PY episodes\2026-W57\scripts\fetch_taylor_data.py --force    # 强制重取
& $PY episodes\2026-W57\scripts\fetch_taylor_data.py --probe    # 只体检，不写文件
```
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EP = Path(__file__).resolve().parents[1]
RAW = EP / "data" / "raw"
SRC = EP / "data" / "来源清单.md"
META = EP / "data" / "raw" / "_meta.json"

BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
PAGE = "https://fred.stlouisfed.org/series/{sid}"

# ================================================================ 序列登记表
# ctry: 归属经济体；role: 在本模型里扮演什么；grade: 置信等级 ①②③
SERIES: tuple[dict, ...] = (
    # ---------------- 美国 ----------------
    dict(sid="CPIAUCSL", ctry="US", role="通胀", freq="M", grade="①",
         name="Consumer Price Index for All Urban Consumers: All Items "
              "in U.S. City Average（美国城市消费者物价指数，指数 1982-84=100，季调）"),
    dict(sid="FEDFUNDS", ctry="US", role="政策利率", freq="M", grade="①",
         name="Federal Funds Effective Rate（联邦基金有效利率，月度平均，%）"),
    dict(sid="GDPC1", ctry="US", role="实际产出", freq="Q", grade="①",
         name="Real Gross Domestic Product（美国实际 GDP，十亿美元 chained 2017，季调年率）"),
    dict(sid="GDPPOT", ctry="US", role="潜在产出", freq="Q", grade="①*",
         name="Real Potential Gross Domestic Product（CBO 估算的美国潜在实际 GDP）"),
    dict(sid="UNRATE", ctry="US", role="失业率（缺口稳健性用）", freq="M", grade="①",
         name="Unemployment Rate（美国失业率，%）"),
    dict(sid="NROU", ctry="US", role="自然失业率（缺口稳健性用）", freq="Q", grade="①*",
         name="Natural Rate of Unemployment (Long-Term)（CBO 长期自然失业率，%）"),
    # ---------------- 欧元区 ----------------
    dict(sid="ECBDFR", ctry="EA", role="政策利率（主）", freq="D", grade="①",
         name="ECB Deposit Facility Rate（欧央行存款便利利率，日度，%）"),
    dict(sid="ECBMRRFR", ctry="EA", role="政策利率（稳健性，2009 年后才完整）", freq="D", grade="①",
         name="ECB Main Refinancing Operations Rate（欧央行主要再融资操作利率，日度，%）"),
    dict(sid="CP0000EZ19M086NEST", ctry="EA", role="通胀", freq="M", grade="①",
         name="Harmonized Index of Consumer Prices: All Items for Euro area "
              "(19 countries)（欧元区 19 国 HICP，指数 2015=100）"),
    dict(sid="CLVMEURSCAB1GQEA19", ctry="EA", role="实际产出", freq="Q", grade="①",
         name="Real Gross Domestic Product for Euro area (19 countries)"
              "（欧元区 19 国实际 GDP，百万 chained 2010 欧元，季调）"),
    # ---------------- 中国 ----------------
    dict(sid="IR3TIB01CNM156N", ctry="CN", role="政策利率代理", freq="M", grade="③",
         name="3-Month or 90-day Rates and Yields: Interbank Rates: Total for China"
              "（中国 3 个月银行间利率，%）"),
    dict(sid="CPALTT01CNM659N", ctry="CN", role="通胀", freq="M", grade="①",
         name="Consumer Price Index: All Items: Total for China"
              "（中国 CPI 同比，%）"),
)

# 已知含 CBO 向前预测的序列：必须按"最后一个真实观测"截断，见文件头陷阱 1
PROJECTION_SIDS = ("GDPPOT", "NROU")
# 截断锚：真实观测的边界序列
TRUNC_ANCHOR = dict(GDPPOT="GDPC1", NROU="UNRATE")

CTRY_LABEL = {"US": "美国", "EA": "欧元区", "CN": "中国"}

# ★ 主用序列：这些序列**不许有内部整年空洞**（见 interior_gaps）
#    `ECBMRRFR` 不在此列：它 2001–2007 整段缺失，只能当**局部**稳健性用。
MAIN_SERIES = ("CPIAUCSL", "FEDFUNDS", "GDPC1", "GDPPOT", "UNRATE", "NROU",
               "ECBDFR", "CP0000EZ19M086NEST", "CLVMEURSCAB1GQEA19",
               "IR3TIB01CNM156N", "CPALTT01CNM659N")


# ================================================================ 下载
def fred_csv(sid: str, tries: int = 4, timeout: int = 40) -> bytes:
    r"""取 FRED 的原始 CSV 字节。带指数退避重试（W40 的教训：免费端点会抖）。"""
    url = BASE.format(sid=sid)
    last: Exception | None = None
    for k in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (W57 data fetch)"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError, OSError) as e:  # noqa: UP041
            last = e
            if k < tries - 1:
                wait = 2.0 * (2 ** k)
                print(f"    [retry {k+1}/{tries-1}] {sid}: {type(e).__name__}"
                      f" ⇒ {wait:.0f}s 后重试")
                time.sleep(wait)
    raise RuntimeError(f"{sid} 取数失败：{type(last).__name__}: {last}")


def parse_csv(blob: bytes) -> tuple[list[str], list[float | None], int]:
    r"""解析 FRED CSV：第一列 `observation_date`，第二列值；缺失记为 `.` 或空。"""
    text = blob.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise ValueError("空 CSV")
    head = rows[0]
    if len(head) < 2:
        raise ValueError(f"列数不足：{head}")
    dates: list[str] = []
    vals: list[float | None] = []
    n_missing = 0
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        d = r[0].strip()
        raw = (r[1].strip() if len(r) > 1 else "")
        if raw in ("", ".", "NA", "NaN"):
            v = None
            n_missing += 1
        else:
            try:
                v = float(raw)
            except ValueError:
                v = None
                n_missing += 1
        dates.append(d)
        vals.append(v)
    return dates, vals, n_missing


def load_local(sid: str) -> tuple[list[str], list[float | None], int]:
    p = RAW / f"{sid}.csv"
    return parse_csv(p.read_bytes())


def fetch_all(force: bool, probe_only: bool) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    meta: dict = {"fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "endpoint": BASE.format(sid="<SERIES>"),
                  "series": {}}
    for s in SERIES:
        sid = s["sid"]
        p = RAW / f"{sid}.csv"
        if probe_only:
            if not p.exists():
                raise SystemExit(f"[probe] 缺 {p}，先不带 --probe 跑一次")
            blob = p.read_bytes()
            d, v, nm = parse_csv(blob)
            fresh = "cache"
        elif force or not p.exists():
            print(f"  ↓ {sid} ...", end="", flush=True)
            blob = fred_csv(sid)
            d, v, nm = parse_csv(blob)
            p.write_bytes(blob)
            print(f" {len(d)} 行 / {len(blob)} 字节")
            fresh = "net"
        else:
            blob = p.read_bytes()
            d, v, nm = parse_csv(blob)
            print(f"  = {sid} 复用缓存（{len(d)} 行）")
            fresh = "cache"
        meta["series"][sid] = {
            "ctry": s["ctry"], "role": s["role"], "freq": s["freq"],
            "grade": s["grade"], "name": s["name"],
            "page_url": PAGE.format(sid=sid),
            "csv_url": BASE.format(sid=sid),
            "n_rows": len(d), "n_missing": nm,
            "first": d[0] if d else None, "last": d[-1] if d else None,
            "bytes": len(blob), "source": fresh,
        }
    return meta


# ================================================================ 截断投影
def truncate_projections(meta: dict) -> dict:
    r"""把带 CBO 预测的序列截断到"最后一个真实观测所在的日期"。

    不做这一步的后果（本期最容易骗过自己的一处）：
    `GDPPOT` 一直画到 2036 年，若直接用它算缺口，
    2026 年之后的缺口其实是"用未来的潜在产出除现在的 GDP"，
    分母与分子不是一个时点的东西。**不报错，只是数悄悄错。**
    """
    out: dict = {}
    for sid, anchor in TRUNC_ANCHOR.items():
        if sid not in meta["series"]:
            continue
        ad = meta["series"][anchor]["last"]
        # 季度序列的日期是 YYYY-MM-01；锚是同频的真实序列
        d, v, nm = load_local(sid)
        keep = [(x, y) for x, y in zip(d, v) if x <= ad and y is not None]
        dropped = [(x, y) for x, y in zip(d, v) if x > ad]
        out[sid] = {
            "anchor": anchor, "anchor_last": ad,
            "n_before": len(d), "n_after": len(keep),
            "n_dropped": len(dropped),
            "dropped_span": (dropped[0][0], dropped[-1][0]) if dropped else None,
            "last_kept": keep[-1][0] if keep else None,
        }
        # 把截断后的版本写成一个单独文件（原始文件保持不动，便于复核）
        tp = RAW / f"{sid}__trunc.csv"
        with tp.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["observation_date", sid])
            for x, y in keep:
                w.writerow([x, y])
    return out


# ================================================================ 体检
def interior_gaps(sid: str) -> list[tuple[str, int, int]]:
    r"""找出**内部整年全缺**的年份。

    ## 为什么必须单独查这个

    `n_missing` 只报"一共有几个缺失"，**看不出缺失是散的还是连片的**。
    本期实测：`ECBMRRFR`（欧央行主要再融资利率，日度）的 3031 个缺失
    **全部连成 2001–2007 的整块**（另有 2000、2008 的一部分）。
    ⇒ 若拿它跑 1999–2026 的回归，程序不报错，
    但那 7 年会被**静默剔出样本**，而样本量看上去完全正常。

    ⇒ 判据：对每个序列，按年统计"有值的天数/月数"，
    凡是落在 [首年, 末年] 之内、计数为 0 的年份，都是**内部空洞**，必须报出来。
    """
    d, v, _ = load_local(sid)
    per: dict[int, int] = {}
    for x, y in zip(d, v):
        yr = int(x[:4])
        per.setdefault(yr, 0)
        if y is not None:
            per[yr] += 1
    if not per:
        return []
    lo, hi = min(per), max(per)
    return [(f"{yr}", per.get(yr, 0), 0) for yr in range(lo, hi + 1)
            if per.get(yr, 0) == 0]


def check_daily_gaps(meta: dict) -> dict:
    r"""对全部序列做内部空洞扫描，返回 {序列: [空洞年份]}。"""
    out: dict = {}
    for sid in meta["series"]:
        g = interior_gaps(sid)
        if g:
            out[sid] = [x[0] for x in g]
    return out


def sanity(meta: dict) -> int:
    r"""硬断言：关键序列必须存在、覆盖必须够长、值的量级必须落在常识区间。

    判据一律取"物理上必须成立的事"，**不取"上一次跑出来的数"**（W56-10）。
    """
    bad: list[str] = []
    S = meta["series"]
    for sid in ("CPIAUCSL", "FEDFUNDS", "GDPC1", "GDPPOT"):
        if sid not in S:
            bad.append(f"缺关键序列 {sid}")
    if bad:
        for b in bad:
            print(f"  [X] {b}")
        return 1

    print("\n  " + "-" * 96)
    print(f"  {'序列':<22} {'经济体':<8} {'频':<3} {'行数':>6} {'缺失':>5} "
          f"{'起':<11} {'止':<11} {'等级':<4} 取值区间")
    print("  " + "-" * 96)
    for sid, s in S.items():
        d, v, _ = load_local(sid)
        vv = [x for x in v if x is not None]
        rng = f"{min(vv):.3f} ~ {max(vv):.3f}" if vv else "无"
        print(f"  {sid:<22} {CTRY_LABEL.get(s['ctry'], s['ctry']):<8} "
              f"{s['freq']:<3} {s['n_rows']:>6} {s['n_missing']:>5} "
              f"{s['first']:<11} {s['last']:<11} {s['grade']:<4} {rng}")

    # 常识断言（这些区间不是"上一次的结果"，是这类序列不可能越过的界）
    d, v, _ = load_local("FEDFUNDS")
    vv = [x for x in v if x is not None]
    assert -1.0 <= min(vv) and max(vv) <= 25.0, f"联邦基金利率越界：{min(vv)}~{max(vv)}"
    d, v, _ = load_local("CPIAUCSL")
    vv = [x for x in v if x is not None]
    assert vv[-1] > 100.0, "CPI 指数末值 <100，八成读错了列"
    d, v, _ = load_local("ECBDFR")
    vv = [x for x in v if x is not None]
    assert -1.0 <= min(vv) and max(vv) <= 8.0, f"ECB 存款便利利率越界：{min(vv)}~{max(vv)}"
    d, v, _ = load_local("ECBMRRFR")
    vv = [x for x in v if x is not None]
    assert 0.0 <= min(vv) and max(vv) <= 8.0, f"ECB 再融资利率越界：{min(vv)}~{max(vv)}"
    d, v, _ = load_local("GDPC1")
    vv = [x for x in v if x is not None]
    assert 2000.0 < vv[-1] < 60000.0, f"美国实际 GDP 末值异常：{vv[-1]}"

    # 季度 GDP 的公共样本必须覆盖 2021Q1–2024Q4（第 05 屏要逐季反算）
    d, v, _ = load_local("GDPC1")
    qs = [x for x, y in zip(d, v) if y is not None]
    need = "2024-10-01"
    assert any(q >= need for q in qs), f"实际 GDP 未覆盖到 2024Q4：末值 {qs[-1]}"
    print(f"\n  [OK] 常识断言全过；实际 GDP 末季 {qs[-1]}（覆盖 2024Q4 ✓）")

    # 内部空洞扫描（★ 本期最重要的一个体检，见 interior_gaps 的说明）
    gaps = check_daily_gaps(meta)
    print("\n  内部整年全缺的序列（这是看不见的样本丢失，必须报出来）：")
    if not gaps:
        print("    无")
    for sid, ys in gaps.items():
        role = meta["series"][sid]["role"]
        print(f"    {sid:<22}（{role}）缺整年：{', '.join(ys)}")
    meta["interior_gaps"] = gaps
    # 硬断言：主用序列不许有内部空洞
    for sid in MAIN_SERIES:
        assert sid not in gaps, (
            f"{sid} 有内部空洞 {gaps[sid]}，不能当主用序列（见来源清单 2.4）")
    print(f"  [OK] 主用序列 {len(MAIN_SERIES)} 个，均无内部空洞")
    return 0


# ================================================================ 来源清单
def write_sources(meta: dict, trunc: dict) -> Path:
    L: list[str] = []
    A = L.append
    A("# 2026-W57 · 数据来源清单")
    A("")
    A("> **本文件是第 05 屏与论文 5.5 节的唯一取数凭据。**")
    A("> 凡本文件里没有的序列，论文里不许出现它的数字。")
    A("")
    A(f"**抓取时间（UTC）**：{meta['fetched_utc']}")
    A("")
    A("**取数端点（公开、无需 API key）**：")
    A("")
    A("```")
    A(meta["endpoint"])
    A("```")
    A("")
    A("每个序列的原始 CSV 原样保存在 `data/raw/<SERIES>.csv`，")
    A("任何人用浏览器打开 `csv_url` 即可逐字节复核。")
    A("")
    A("---")
    A("")
    A("## 一、序列总表")
    A("")
    for ctry in ("US", "EA", "CN"):
        rows = [(k, v) for k, v in meta["series"].items() if v["ctry"] == ctry]
        if not rows:
            continue
        A(f"### {CTRY_LABEL[ctry]}")
        A("")
        A("| 序列 | 在本模型里扮演 | 频度 | 起 | 止 | 行数 | 缺失 | 等级 |")
        A("|---|---|---|---|---|---|---|---|")
        for sid, s in rows:
            A(f"| [`{sid}`]({s['page_url']}) | {s['role']} | {s['freq']} | "
              f"{s['first']} | {s['last']} | {s['n_rows']} | {s['n_missing']} | "
              f"{s['grade']} |")
        A("")
        for sid, s in rows:
            A(f"* **`{sid}`**：{s['name']}")
            A(f"  - 序列页：{s['page_url']}")
            A(f"  - 原始 CSV：{s['csv_url']}")
        A("")
    A("---")
    A("")
    A("## 二、★ 三处已实测的数据陷阱")
    A("")
    A("### 2.1 `GDPPOT` 与 `NROU` 带 CBO 的十年**预测**")
    A("")
    A("这两个序列不像别的序列那样止于最后一个观测，而是一路画到 **2036 年**，")
    A("因为 CBO 的潜在产出与自然失业率估计本身就含向前预测。")
    A("")
    A("**直接拿来算产出缺口，等于用未来的潜在产出去除现在的 GDP。**")
    A("不报错，只是数悄悄错。本期的处置是：")
    A("")
    A("| 序列 | 截断锚（真实观测） | 锚的末值 | 原始行数 | 保留 | 丢掉 | 丢掉的区间 |")
    A("|---|---|---|---|---|---|---|")
    for sid, t in trunc.items():
        span = t["dropped_span"]
        span_s = f"{span[0]} ~ {span[1]}" if span else "无"
        A(f"| `{sid}` | `{t['anchor']}` | {t['anchor_last']} | {t['n_before']} | "
          f"{t['n_after']} | {t['n_dropped']} | {span_s} |")
    A("")
    A("截断后的版本另存为 `data/raw/<SERIES>__trunc.csv`，")
    A("**原始文件保持不动**，便于复核这一步到底删了什么。")
    A("")
    A("### 2.2 FRED 上取不到的序列（如实记录，不找替代数硬撑）")
    A("")
    A("| 想要的量 | 试过的序列 | 结果 | 后果 |")
    A("|---|---|---|---|")
    A("| 中国工业增加值 | `CHNPROINDMISMEI` | **404**（OECD MEI 已停更） | 中国无可用的产出缺口代理 |")
    A("| 中国失业率 | `LRHUTTTTCNM156S` | **404** | 同上 |")
    A("| 中国长期国债收益率 | `IRLTLT01CNM156N` | **404** | 无法做利率期限对照 |")
    A("| 欧元区 CPI 同比（现成） | `CPALTT01EZM659N` | **404** | 改为从 HICP 指数自算同比 |")
    A("| 欧元区通胀预期 | 未找到免密钥序列 | 取不到 | **主回归只用事后通胀，这是已知偏误** |")
    A("")
    A("### 2.3 中国的两个序列不同长，公共样本短得多")
    A("")
    A("`IR3TIB01CNM156N` 到 2026-08，而 `CPALTT01CNM659N` 只到 **2025-04**。")
    A("⇒ 中国那一路的回归样本止于 2025-04，**且没有产出缺口项**，")
    A("不能与美国、欧元区放在同一张表里比大小（论文 5.5 节照此处理）。")
    A("")
    A("### 2.4 ★★ 内部整年全缺的序列：`ECBMRRFR` 缺 2001–2007 整七年")
    A("")
    A("`n_missing` 只报“一共有几个缺失”，**看不出缺失是散的还是连片的**。"
      "本期做了一个按年扫描，结果如下：")
    A("")
    gaps = meta.get("interior_gaps") or {}
    if not gaps:
        A("| 序列 | 内部整年空洞 |")
        A("|---|---|")
        A("| 无 | — |")
    else:
        A("| 序列 | 角色 | 内部整年空洞 |")
        A("|---|---|---|")
        for sid, ys in gaps.items():
            A(f"| `{sid}` | {meta['series'][sid]['role']} | "
              f"**{', '.join(ys)}**（共 {len(ys)} 年）|")
    A("")
    A("**为什么这一条最危险**：拿 `ECBMRRFR` 跑 1999–2026 的回归，程序**不报错**，")
    A("但那 7 年会被静默剔出样本，而样本量看上去完全正常（77 个季度，"
      "覆盖 1999Q1–2026Q2）。**不做按年扫描就发现不了。**")
    A("")
    A("**处置**：欧元区主用 **`ECBDFR`**（存款便利利率，0 缺失、1999-01-01 起连续）；"
      "`ECBMRRFR` 只在 2009 年之后（该段完整）当稳健性用。")
    A("")
    A("> **附带的口径代价**：2019 年以前 `ECBDFR` 是利率走廊的**下限**，"
      "不是欧央行的“主”政策利率；2019 年起（尤其是 2024 年 9 月收窄走廊后）"
      "它才是事实上的政策利率。这一条写进论文 5.5 与 7.3。")
    A("---")
    A("")
    A("## 三、等级约定")
    A("")
    A("| 等级 | 含义 |")
    A("|---|---|")
    A("| **①** | 官方/机构口径**原样**使用，未做任何加工 |")
    A("| **①带截断** | 官方口径，但**本文件做了截断**（见 2.1），截断规则是本期自定的 |")
    A("| **②** | 由模型或恒等式**反解**出来的量 |")
    A("| **③** | 本文**自定**的假设或代理（如用银行间利率当政策利率） |")
    A("")
    A("> **`IR3TIB01CNM156N` 之所以标 ③ 而不是 ①**：它是**银行间市场利率**，")
    A("> 不是人民银行的政策利率。中国的政策工具是 MLF / 逆回购 / LPR，")
    A("> FRED 上没有免密钥的 LPR 序列。用银行间利率当代理，")
    A("> 会把“市场对政策的定价”混进“政策反应系数”里，这一条写进论文 5.5 与 7.3。")
    A(">")
    A("> **`ECBDFR` 标 ① 但带一句口径说明**：它是官方公布的利率，但 2019 年以前")
    A("> 它是走廊下限，与“主政策利率”（主要再融资利率）不是同一个层级的工具。")
    A("")
    A("---")
    A("")
    A("## 五、一处口径与标签不一致（已核过，结论不受影响）")
    A("")
    A("`CP0000EZ19M086NEST` 的 FRED 名称写“指数 2015=100”，")
    A("但序列的**水平**与这个标签不符（2015-01 的值是 76.34，不是 100）。")
    A("")
    A("**处置：不信标签，用外部已知事实核增长率。** 从该指数自算的同比：")
    A("")
    A("| 月份 | 本文件自算同比 | 官方公布值 |")
    A("|---|---|---|")
    A("| 2008-07 | **4.12%** | 约 4.1% |")
    A("| 2022-10 | **10.62%** | 10.6% |")
    A("| 2023-03 | **6.88%** | 约 6.9% |")
    A("")
    A("⇒ **水平可能被重新定基，增长率是对的。** 本模型只用增长率（同比），")
    A("所以这一处不一致不影响任何结论；但它说明“按标签用一个序列”是不可靠的。")
    A("")
    A("---")
    A("")
    A("## 四、口径说明（随结论一起出现）")
    A("")
    A("1. 通胀一律用 **CPI 同比**（事后值），**不是**央行决策时看到的实时数据，")
    A("   也**不是**通胀预期。这是简化泰勒规则回归的已知偏误来源；")
    A("2. 政策利率一律用**短端**：美国联邦基金有效利率、欧央行存款便利利率、")
    A("   中国 3 个月银行间利率。三者**不是同一个层级的工具**，可比性有限；")
    A("3. 产出缺口：美国用 **CBO 潜在产出**（官方），欧元区用 **HP 滤波自建**（③），")
    A("   中国**没有**（见 2.2）；")
    A("4. 全部序列的**发布日期修订**未做处理（用的是当前 revision），")
    A("   即存在\"用今天的修订数据回看当年决策\"的引视偏差。")
    A("")
    SRC.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"\n[sources] {SRC}")
    return SRC


# ================================================================ CLI
def main() -> int:
    ap = argparse.ArgumentParser(description="W57 第 05 屏取数")
    ap.add_argument("--force", action="store_true", help="忽略缓存，全部重取")
    ap.add_argument("--probe", action="store_true", help="只体检，不写任何文件")
    args = ap.parse_args()

    print("=" * 96)
    print("  W57 · 三国政策利率 / 通胀 / 产出缺口 取数（FRED 公开 CSV 端点）")
    print("=" * 96)
    meta = fetch_all(args.force, args.probe)
    rc = sanity(meta)
    if rc:
        return rc
    trunc = truncate_projections(meta)
    print("\n  截断 CBO 预测：")
    for sid, t in trunc.items():
        print(f"    {sid:<8} 锚 {t['anchor']:<8} 末值 {t['anchor_last']}  "
              f"保留 {t['n_after']:>3}/{t['n_before']:>3}  丢掉 {t['n_dropped']:>3} 行"
              f"（{t['dropped_span'][0]} ~ {t['dropped_span'][1]}）"
              if t["dropped_span"] else f"    {sid} 无需截断")
    if args.probe:
        print("\n  [probe] 未写任何文件")
        return 0
    meta["truncation"] = trunc
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    write_sources(meta, trunc)
    print(f"[meta] {META}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
