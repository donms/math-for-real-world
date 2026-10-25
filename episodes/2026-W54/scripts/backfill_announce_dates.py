#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W54 · **给第一批数据补齐「公告发布时间」**（否则新旧数据无法合并按月分析）。

## 为什么需要

第一批（`fetch_jiangsu_land.py`，100 宗）**没有写 `季度` / `采集批次`**，
只有宗地自己的「挂牌起始时间」。而**挂牌起始 ≠ 公告发布**，
且两批记录的字段集不同 ⇒ 合并分析会出错。

**修法**：回查每个公告的 `tdsc_getTdcrxx.action` 详情（只有首次抓到才需要），
把**公告发布日期**补进一条独立的映射表 `data/公告日期.json`，
后续分析统一按它分季度。

## 纪律

* **只补已有公告，不新增抓取范围**；
* 请求间隔 0.4s；
* 结果落盘成 `{公告ID: 发布日期}`，**与宗地数据分离**（不修改原始 jsonl）。
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from net_resolve import open_url                                  # noqa: E402

EP = ROOT / "episodes" / "2026-W54"
JSONL = EP / "data" / "江苏宗地.jsonl"
MAP = EP / "data" / "公告日期.json"
TXT = ("http://zrzy.jiangsu.gov.cn/gtapp/xxgk/"
       "tdsc_getTdcrxx.action")


def main() -> int:
    rows = []
    for ln in JSONL.open(encoding="utf-8"):
        try:
            rows.append(json.loads(ln))
        except Exception:                                         # noqa: BLE001
            continue
    # 已有映射（断点续跑）
    m: dict[str, str] = {}
    if MAP.exists():
        m = json.loads(MAP.read_text(encoding="utf-8"))

    pairs = sorted({(r["公告ID"], r["区划码"]) for r in rows})
    todo = [(a, d) for a, d in pairs if a not in m]
    print("=" * 94)
    print("  W54 · 补齐公告发布日期")
    print("=" * 94)
    print(f"  宗地 {len(rows)} 宗｜公告 {len(pairs)} 个｜"
          f"已有映射 {len(m)}｜待补 {len(todo)}")

    if todo:
        print(f"\n  开始回查（间隔 0.4s，约 {len(todo)*0.4/60:.1f} 分钟）…")
        for i, (aid, dm) in enumerate(todo, 1):
            try:
                t = open_url(f"{TXT}?lx=0&id={aid}&xzqhdm={dm}",
                             timeout=25, tries=2).read(
                    900000).decode("utf-8", "ignore")
            except Exception:                                     # noqa: BLE001
                m[aid] = ""
                continue
            # 公告发布日期：页面上一般在标题下方或"发布日期"标签旁
            d = ""
            for pat in (r"发布日期[^0-9]{0,20}(20[0-9]{2}[-/][0-9]{2}[-/][0-9]{2})",
                        r"(20[0-9]{2}-[0-9]{2}-[0-9]{2})"):
                mm = re.search(pat, t)
                if mm:
                    d = mm.group(1).replace("/", "-")
                    break
            m[aid] = d
            if i % 20 == 0 or i == len(todo):
                print(f"   {i}/{len(todo)} …")
                MAP.write_text(json.dumps(m, ensure_ascii=False, indent=1),
                               encoding="utf-8")
            time.sleep(0.4)
        MAP.write_text(json.dumps(m, ensure_ascii=False, indent=1),
                       encoding="utf-8")

    # 统计覆盖
    got = sum(1 for a, _d in pairs if m.get(a))
    print(f"\n  ⇒ 拿到发布日期 {got}/{len(pairs)} 个公告")
    if got:
        from collections import Counter
        q = Counter()
        for a, _d in pairs:
            ds = m.get(a, "")
            if len(ds) >= 7:
                y, mo = ds[:4], int(ds[5:7])
                q[f"{y}Q{(mo-1)//3+1}"] += 1
        print("  -- 公告的季度分布 --")
        for k in sorted(q):
            print(f"     {k}  {q[k]:>3} 个公告  {'█'*q[k]}")
    print(f"\n  [落盘] {MAP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
