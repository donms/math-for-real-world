#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W54 · 路 B：从东方财富数据中心取**港股上市物企的财务指标**。

## 数据源实测结论（见 `data/probe_确认.json`）

| 接口 | 状态 |
|---|---|
| `datacenter-web.eastmoney.com/api/data/v1/get` | ✓ **可用**（返回真实数据行）|
| `reportName=RPT_HKF10_FN_MAININDICATOR` | ✓ 89 字段（EPS/BPS/毛利率/净利率/资产负债率…）|
| `reportName=RPT_HKF10_FN_INCOME` | ✓ 22 字段 |
| `reportName=RPT_HKF10_FN_BALANCE` | ✓ 21 字段 |
| `reportName=RPT_HKF10_INFO_ORGPROFILE` | ✓ 35 字段 |
| **能不能拿到「在管面积」** | ✗ **不能** —— 试遍 7 个 reportName 均无面积类字段 |

**⇒ 结论：财务指标可从东财批量取；「在管面积/项目数」必须另找**
（年报正文、或 HKEX 公告 PDF）—— 这一条写进来源清单的"被拒用的数字及理由"。

## 本脚本做什么

1. 用一份**物企证券清单**（人工整理，标注来源），逐个取主要指标；
2. 落盘成 `data/上市公司财务.jsonl`；
3. 打印一张速览表（2025 / 2024 的毛利率与净利率）。

★ **证券清单是"我整理的"**，所以每个代码都要能被独立验证
（脚本会打印"取到的 SECURITY_CODE 与我给的是否一致"）。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from net_resolve import open_url                                  # noqa: E402

EP = ROOT / "episodes" / "2026-W54"
OUT = EP / "data"
OUT.mkdir(parents=True, exist_ok=True)
EM = "https://datacenter-web.eastmoney.com/api/data/v1/get"

# ★ 港股上市物业管理公司清单（代码 + 名称）
#   来源：证券时报/界面新闻《多家民营物企 2025 财年扭亏》提到的公司
#        + 本项目已知的头部物企。**代码需由接口回验**。
FIRMS: list[tuple[str, str]] = [
    ("06098", "碧桂园服务"),
    ("01209", "华润万象生活"),
    ("06049", "保利物业"),
    ("02869", "绿城服务"),
    ("06666", "恒大物业"),
    ("03319", "雅生活服务"),
    ("01995", "永升服务"),
    ("00873", "世茂服务"),
    ("01516", "融创服务"),
    ("03316", "滨江服务"),
    ("02602", "万物云"),
    ("02669", "中海物业"),
    ("01778", "彩生活"),
    ("01965", "朗诗绿色生活"),
    ("02152", "苏新服务"),
    ("09979", "绿城管理控股"),
    ("03658", "新希望服务"),
    ("06958", "正荣服务"),
    ("09983", "建业新生活"),
    ("01971", "弘阳服务"),
    ("09916", "兴业物联"),        # 我原写成"时代邻里"，接口回验纠正
    ("06677", "远洋服务"),
    ("02107", "第一服务控股"),
    ("09928", "时代邻里"),
]

FIELDS = ["SECUCODE", "SECURITY_CODE", "SECURITY_NAME_ABBR", "REPORT_DATE",
          "DATE_TYPE_CODE", "BASIC_EPS", "BPS", "GROSS_PROFIT_RATIO",
          "NET_PROFIT_RATIO", "DEBT_ASSET_RATIO", "ROE_AVG",
          "TOTAL_ASSETS", "TOTAL_LIABILITIES", "CURRENCY"]


def fetch(code: str) -> list[dict]:
    u = (f"{EM}?reportName=RPT_HKF10_FN_MAININDICATOR&columns=ALL"
         f"&filter=(SECUCODE%3D%22{code}.HK%22)&pageSize=40"
         f"&pageNumber=1&source=F10&client=PC&sortColumns=REPORT_DATE"
         f"&sortTypes=-1")
    r = open_url(u, timeout=25, tries=2)
    d = json.loads(r.read().decode("utf-8", "ignore"))
    return (d.get("result") or {}).get("data") or []


def main() -> int:
    print("=" * 100)
    print("  W54 · 路 B：港股上市物企财务指标（东方财富数据中心）")
    print("=" * 100)
    all_recs: list[dict] = []
    print(f"\n  {'代码':<7}{'名称':<12}{'接口回验码':<11}{'报告期数':>7}"
          f"{'最新报告期':>13}{'毛利率':>9}{'净利率':>9}  名称是否一致")
    for code, name in FIRMS:
        try:
            rows = fetch(code)
        except Exception as e:                                    # noqa: BLE001
            print(f"  {code:<7}{name:<12}[X] {type(e).__name__}: "
                  f"{str(e)[:40]}")
            continue
        if not rows:
            print(f"  {code:<7}{name:<12}{'—':<11}{0:>7}"
                  f"{'（无数据）':>13}")
            continue
        rows.sort(key=lambda r: r.get("REPORT_DATE") or "", reverse=True)
        r0 = rows[0]
        got = str(r0.get("SECURITY_CODE") or "")
        nm = str(r0.get("SECURITY_NAME_ABBR") or "")
        ok = "✓" if got.zfill(5) == code else f"✗({got})"
        gp = r0.get("GROSS_PROFIT_RATIO")
        np_ = r0.get("NET_PROFIT_RATIO")
        print(f"  {code:<7}{name:<12}{got:<11}{len(rows):>7}"
              f"{str(r0.get('REPORT_DATE'))[:10]:>13}"
              f"{(f'{gp:.2f}' if isinstance(gp, (int, float)) else '—'):>9}"
              f"{(f'{np_:.2f}' if isinstance(np_, (int, float)) else '—'):>9}"
              f"  {ok} {nm}")
        for r in rows:
            r["_我给的名称"] = name
            all_recs.append({k: r.get(k) for k in FIELDS} | {
                "_最新": r is rows[0]})
        time.sleep(0.35)          # 礼貌间隔，避免被限流

    # 落盘
    p = OUT / "上市公司财务.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for r in all_recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n  [落盘] {p}  （{len(all_recs)} 条记录）")

    # ---- 2025 vs 2024 速览 ----
    print(f"\n  -- 2025 年报 vs 2024（毛利率 / 净利率，%）--")
    print(f"  {'代码':<7}{'名称':<12}{'2025毛利率':>11}{'2024毛利率':>11}"
          f"{'2025净利率':>11}{'2024净利率':>11}")
    for code, name in FIRMS:
        rs = [r for r in all_recs if r["SECURITY_CODE"]
              and str(r["SECURITY_CODE"]).zfill(5) == code]
        def pick(y: str) -> dict | None:
            for r in rs:
                if str(r.get("REPORT_DATE", "")).startswith(y) \
                        and str(r.get("DATE_TYPE_CODE")) == "001":
                    return r
            return None
        a, b = pick("2025"), pick("2024")
        if not a and not b:
            continue
        def fmt(d, k):
            v = (d or {}).get(k)
            return f"{v:.2f}" if isinstance(v, (int, float)) else "—"
        print(f"  {code:<7}{name:<12}{fmt(a,'GROSS_PROFIT_RATIO'):>11}"
              f"{fmt(b,'GROSS_PROFIT_RATIO'):>11}"
              f"{fmt(a,'NET_PROFIT_RATIO'):>11}"
              f"{fmt(b,'NET_PROFIT_RATIO'):>11}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
