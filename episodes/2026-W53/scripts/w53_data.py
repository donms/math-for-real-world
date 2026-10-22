#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W53 公共数据层 · **统一的质量门槛与读取接口**。

## 为什么要有这个模块

本期在分析过程中发现**三类会污染结论的数据问题**，
它们各自都需要在**每一个**分析脚本里处理 —— 复制粘贴必然漏掉某一处：

| # | 问题 | 证据 | 后果 |
|---|---|---|---|
| **1** | ★ **`speed = 0` 占 29.8%** | 体检：`zero_pct = 29.758` | 含 0 时早高峰均速 **24.3**，剔后 **33.4**（差 9 mph）|
| **2** | ★ **部分日子覆盖不全** | `q0b`：3 天覆盖 < 50%（最低 **3.5%**）| 该天均值只反映少数小时 ⇒ 不可比 |
| **3** | ★ **`link` 集合在 6 月扩容** | 5 月 **101** 条 → 6 月起 **125** 条（新增 24 条 `44564xx`）| 前后两段的"全网均值"组成不同 |

⇒ 本模块把这三件事**集中处理**，所有分析脚本一律经它读数据。

## 三条门槛（都可配置）

```python
MIN_DAY_COV   = 0.90   # 当天覆盖率低于此值 ⇒ 整天剔除
DROP_ZERO     = True   # speed<=0 视为"无读数"
COMMON_LINKS  = True   # 只用全程都出现的 link（消除扩容影响）
```

## ★ 为什么不直接改分析脚本里的过滤条件

因为**每个脚本各写一遍必然不一致**（本项目已实测：
`q1` 第一版漏了剔 0，算出 33.4 而配对用的是含 0 的数据）。
**把门槛集中到一层，是唯一能保证一致的做法。**

用法：
    from w53_data import load_speed, load_mta, QUALITY_NOTE
    cells = load_speed()        # {(iso_date, dow, link, hour): mean_speed}
    daily = load_speed_daily()  # {iso_date: {"mean":.., "dow":.., "n":..}}
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "episodes" / "2026-W53" / "data" / "raw"

# ---------------- 可配置门槛 ----------------
# ★ 0.75 是**实测选出来的**（见 q5_sensitivity.py）：
#   * 0.75 保留 110 天，每天最少 23 个小时（几乎完整），
#     且 18 周全覆盖（**含暑假前**）；
#   * 0.90 只剩 105 天，且周一从 15 天掉到 12 天（**星期分布变不均**）；
#   * 0.95 只剩 99 天，周一仅 10 天。
#   ==> 0.75 在“数据完整性”与“样本量与均衡性”之间最好。
MIN_DAY_COV = 0.75        # 当天覆盖率门槛（**归一化**分母，见 day_coverage）
DROP_ZERO = True          # speed<=0 视为无读数
COMMON_LINKS = True       # 只用全程都出现的 link
# [!] 保留此常量仅供外部引用；**不要**再拿它当覆盖率分母（见 day_coverage 的说明）
EXPECT_PER_DAY = 36000    # 125 link x 288 点（仅作参考值）

# 2026 年联邦假日（落在取数区间内）
HOLIDAYS = {
    date(2026, 5, 25): "Memorial Day",
    date(2026, 6, 19): "Juneteenth",
    date(2026, 7, 3): "Independence Day (observed)",
    date(2026, 7, 4): "Independence Day",
    date(2026, 9, 7): "Labor Day",
}

QUALITY_NOTE = (
    "数据质量门槛（w53_data.py）："
    f"(1) 剔除 speed<=0（占 29.76%，视为无读数）；"
    f"(2) 剔除当日覆盖率 < {MIN_DAY_COV:.0%} 的日子；"
    f"(3) 仅使用全程出现的 link（消除 6 月由 101 增至 125 条的组成变化）；"
    "(4) 剔除 2026 年联邦假日。"
)


HINT = """\
[X] 找不到原始数据：{raw}

本期 `data/raw/`（848 MB，按周切片的原始取数）**不在仓库里** ——
因为它可由两个公开 API 重新取到，且进包会让仓库从 43.6 MB 涨到约 890 MB。

请先取数（约 35 分钟）：
    python scripts/fetch_traffic.py --weeks 18 --anchor 2026-09-09

取数后 `data/raw/` 应有 36 个文件（speed_*.jsonl 与 mta_*.jsonl 各 18 个）。

如果你只想看结论：`results/*.json` 与 `paper/` 里已落盘全部数字，
**不需要原始数据**。
"""


def require_raw() -> None:
    r"""缺原始数据时给**可操作的提示**并退出（而不是让上层崩在别处）。

    为什么需要它：本期有四个脚本（`q2_mechanism` / `q3_nonlinear` /
    `q3b_hours_links` / `q5_sensitivity`）为了自己控制过滤口径，
    **直接读 `RAW` 目录**，没走 `load_speed()`。
    若不做这个检查，它们在无数据时会产出**空的中间结果**，
    然后在某个下标访问处崩掉 —— **报错完全不指向真正原因**
    （实测 `q2_weekend` 曾报 `IndexError: list index out of range`）。
    """
    if not RAW.exists() or not sorted(RAW.glob("speed_*.jsonl")):
        print(HINT.format(raw=RAW))
        raise SystemExit(2)


def _iter_speed():
    r"""遍历 `data/raw/speed_*.jsonl`。

    ## ★★ 缺原始数据时**必须明确报错**（不能静默返回空）

    本期的 `data/raw/`（848 MB 按周切片原始取数）**故意不进 GitHub 包**
    （进包会让仓库从 43.6 MB 涨到约 890 MB）。
    ⇒ 读者 clone 单期包后**必须先跑抓取脚本**：
    ```bash
    python scripts/fetch_traffic.py --weeks 18 --anchor 2026-09-09
    ```

    **原来的写法**是直接 `glob`，没有文件就产出空迭代器
    ⇒ 上层算出一个空的 `cells` 字典
    ⇒ 最后崩在 `days[0]` 上，报 **`IndexError: list index out of range`**
    —— **这个报错完全不指向真正的原因**（读者会以为是脚本 bug）。

    ⇒ 现在先检查文件是否存在，缺了就给**可操作的提示**并退出。
    """
    files = sorted(RAW.glob("speed_*.jsonl"))
    if not files:
        print(f"[X] 找不到原始数据：{RAW}")
        print("    本期 `data/raw/` **不在仓库里**（848 MB，且可由公开 API 重取）。")
        print("    请先取数（约 35 分钟）：")
        print("      python scripts/fetch_traffic.py --weeks 18 "
              "--anchor 2026-09-09")
        print("    取数后 `data/raw/` 会有 36 个文件"
              "（speed_*.jsonl 与 mta_*.jsonl 各 18 个）。")
        print("    若只想要结论，直接看 `results/*.json` 与 `paper/`，"
              "**不需要原始数据**。")
        raise SystemExit(2)
    for p in files:
        with p.open(encoding="utf-8") as f:
            for ln in f:
                try:
                    yield json.loads(ln)
                except Exception:                                    # noqa: BLE001
                    continue


def day_coverage() -> dict[str, float]:
    r"""逐日覆盖率，**分母 = 当天实际有多少 link 在报 x 288**。

    ## ★ 为什么不能用固定的 36000 作分母（本期最隐蔽的一个坑）

    数据集在 **2026-06 扩容**：5 月 **101** 条 link，6 月起 **125** 条。
    ⇒ 5 月的满覆盖只有 $101 \times 288 = 29088$ 行，固定分母下覆盖率**上限 80.8%**。

    **用固定分母的后果**：
    * 5 月的日子覆盖率恒为 0.81 ⇒ **整段被判"不合格"**；
    * 于是"覆盖率 >= 90%"这个门槛**实际等价于"只用 6 月以后的数据"**
      ⇒ **与季节完全混淆**。
    * 实测：门槛 75% → 90% 时，周一 vs 周二的中位差从 −0.052 变成 **−0.210
      (p=0.0002)**，看起来"周一效应出现了" —— **实则只是换了个季节窗口**。

    **并且**该门槛剔掉的星期分布**不均衡**（周一剔 6 天、周四只剔 4 天），
    所以这个假象还带有**星期偏差**，极难察觉。

    ⇒ 归一化后：90% 门槛下有 **105 天**（固定分母下只有 82 天），
    且周一效应回到 **−0.001 (p=0.736)**。
    """
    links_day: dict[str, set] = defaultdict(set)
    n_day: dict[str, int] = defaultdict(int)
    for r in _iter_speed():
        ts = r.get("data_as_of") or ""
        if not ts.startswith("2026"):
            continue
        links_day[ts[:10]].add(r.get("link_id"))
        n_day[ts[:10]] += 1
    return {ds: n_day[ds] / (len(links_day[ds]) * 288)
            for ds in n_day if links_day[ds]}


def common_links() -> set[str]:
    r"""**全程都出现**的 link 集合（按"每周都出现过"判定）。"""
    by_week: dict[tuple, set] = defaultdict(set)
    for r in _iter_speed():
        ts = r.get("data_as_of") or ""
        if not ts.startswith("2026"):
            continue
        try:
            d = date.fromisoformat(ts[:10])
        except ValueError:
            continue
        by_week[d.isocalendar()[:2]].add(r.get("link_id"))
    if not by_week:
        return set()
    keep = set.intersection(*by_week.values()) if by_week else set()
    return {x for x in keep if x}


def _good_days() -> set[str]:
    cov = day_coverage()
    good = {d for d, c in cov.items() if c >= MIN_DAY_COV}
    for h in HOLIDAYS:
        good.discard(h.isoformat())
    return good


def load_speed(peak_only: bool = False, hours: tuple = (7, 8, 9)):
    r"""{(iso_date, dow, link, hour): 均速}，已过全部门槛。"""
    good = _good_days()
    keep = common_links() if COMMON_LINKS else None
    acc: dict[tuple, list] = defaultdict(list)
    for r in _iter_speed():
        ts = r.get("data_as_of") or ""
        if not ts.startswith("2026") or ts[:10] not in good:
            continue
        try:
            d = date.fromisoformat(ts[:10])
            h = int(ts[11:13])
        except ValueError:
            continue
        if peak_only and h not in hours:
            continue
        sv = r.get("speed")
        if sv in (None, ""):
            continue
        try:
            v = float(sv)
        except ValueError:
            continue
        if DROP_ZERO and v <= 0:
            continue
        lid = r.get("link_id")
        if keep is not None and lid not in keep:
            continue
        acc[(ts[:10], d.strftime("%a"), lid, h)].append(v)
    return {k: st.mean(v) for k, v in acc.items()}


def load_speed_daily(hours: tuple | None = None):
    r"""{iso_date: {"mean":.., "sd":.., "n":.., "dow":..}}，已过门槛。

    `hours=None` 表示全天；否则只取给定小时。
    """
    good = _good_days()
    keep = common_links() if COMMON_LINKS else None
    acc: dict[str, list] = defaultdict(list)
    for r in _iter_speed():
        ts = r.get("data_as_of") or ""
        if not ts.startswith("2026") or ts[:10] not in good:
            continue
        if hours is not None:
            try:
                if int(ts[11:13]) not in hours:
                    continue
            except ValueError:
                continue
        sv = r.get("speed")
        if sv in (None, ""):
            continue
        try:
            v = float(sv)
        except ValueError:
            continue
        if DROP_ZERO and v <= 0:
            continue
        lid = r.get("link_id")
        if keep is not None and lid not in keep:
            continue
        acc[ts[:10]].append(v)
    out = {}
    for ds, v in acc.items():
        if len(v) < 100:
            continue
        d = date.fromisoformat(ds)
        out[ds] = {"mean": st.mean(v), "sd": st.pstdev(v), "n": len(v),
                   "dow": d.strftime("%a")}
    return out


def load_mta():
    r"""{(iso_date, dow, hour): 过车总量}，已剔假日与低覆盖日。"""
    good = _good_days()
    acc: dict[tuple, float] = defaultdict(float)
    for p in sorted(RAW.glob("mta_*.jsonl")):
        with p.open(encoding="utf-8") as f:
            for ln in f:
                try:
                    r = json.loads(ln)
                except Exception:                                    # noqa: BLE001
                    continue
                ds = (r.get("date") or "")[:10]
                if not ds.startswith("2026") or ds not in good:
                    continue
                try:
                    d = date.fromisoformat(ds)
                    h = int(r.get("hour") or -1)
                except ValueError:
                    continue
                try:
                    acc[(ds, d.strftime("%a"), h)] += float(
                        r.get("traffic_count") or 0)
                except ValueError:
                    continue
    return dict(acc)


def summary() -> dict:
    cov = day_coverage()
    good = _good_days()
    keep = common_links() if COMMON_LINKS else None
    return {
        "days_total": len(cov),
        "days_after_cov_filter": len(good),
        "days_dropped": len(cov) - len(good),
        "min_day_cov": round(min(cov.values()), 4) if cov else None,
        "common_links": len(keep) if keep else None,
        "holidays": {k.isoformat(): v for k, v in HOLIDAYS.items()},
        "note": QUALITY_NOTE,
    }


if __name__ == "__main__":
    print(json.dumps(summary(), ensure_ascii=False, indent=2))
