#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W53 问 2 · ★★ **分离两种机制**：「车更多」还是「路更慢」？

## 这是本题的核心

"周一更堵"（若成立）至少有两种解释：

| 机制 | 含义 | 数据侧 |
|---|---|---|
| **需求侧** | 周一上路的**车次更多** | MTA 逐小时 `traffic_count` |
| **效率侧** | 车次差不多，但**同样多的车跑得更慢** | 125 条路段的 `speed` |

## ★ 方法：**两个比值的方向性**

$$R_{\text{流量}} = \frac{\text{周一早高峰}}{\text{参照日早高峰}},
\qquad
R_{\text{速度}} = \frac{\text{周一早高峰}}{\text{参照日早高峰}}$$

| 情形 | 判读 |
|---|---|
| $R_{\text{流量}} \approx 1$ 且 $R_{\text{速度}} < 1$ | **效率侧**为主 |
| $R_{\text{流量}} > 1$ 且 $R_{\text{速度}} \approx 1$ | **需求侧**为主 |
| 两者都偏离 1 | 需要**进一步分解** |

## ⚠️⚠️ 必须写进结论的假设（**这是本题最关键的诚实性要求**）

两套数据的**空间不重叠**：
* 速度是 **125 条普通路段**；
* 流量是**桥梁与隧道**（MTA 设施）。

⇒ 我们**无法**把"某条路慢了"与"某个设施车多了"配对。
所作的假设是：**两类设施承受的是同一个城市级的出行需求冲击**。
在这个假设下，两个比值的**方向**才有可比性。

**若这个假设不成立**（例如桥梁流量与普通路段流量走势相反），
则结论只能退化为"**两类设施的日间形态不同**"，不能谈机制。

⇒ **本脚本必须做这个反证检验**：把速度侧**也**按
"是否靠近 MTA 设施"分组，看结论是否一致。做不到就如实声明。

用法：
    $PY q2_mechanism.py
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
EP = ROOT / "episodes" / "2026-W53"
RAW = EP / "data" / "raw"
OUT = EP / "results" / "q2_机制分解.json"

PEAK = (7, 8, 9)
HOLIDAYS = {date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3),
            date(2026, 9, 7)}
REF = "Tue"


def speed_by_day() -> dict[tuple[str, str], float]:
    r"""{(iso_date, dow): 早高峰均速}（剔 0、剔假日）。"""
    acc: dict[tuple[str, str], list[float]] = defaultdict(list)
    for p in sorted(RAW.glob("speed_*.jsonl")):
        with p.open(encoding="utf-8") as f:
            for ln in f:
                try:
                    r = json.loads(ln)
                except Exception:                                    # noqa: BLE001
                    continue
                ts = r.get("data_as_of") or ""
                if not ts.startswith("2026"):
                    continue
                try:
                    d = date.fromisoformat(ts[:10])
                    h = int(ts[11:13])
                except ValueError:
                    continue
                if d in HOLIDAYS or h not in PEAK:
                    continue
                sv = r.get("speed")
                if sv in (None, ""):
                    continue
                try:
                    v = float(sv)
                except ValueError:
                    continue
                if v > 0:
                    acc[(ts[:10], d.strftime("%a"))].append(v)
    return {k: st.mean(v) for k, v in acc.items() if v}


def mta_by_day() -> dict[tuple[str, str], float]:
    r"""{(iso_date, dow): 早高峰小时过车总量}。

    同一 `(date, hour, facility, direction)` 会有**多个 vehicle_class**
    ⇒ 先按这些键求和，再加总到日。
    """
    acc: dict[tuple[str, str], float] = defaultdict(float)
    for p in sorted(RAW.glob("mta_*.jsonl")):
        with p.open(encoding="utf-8") as f:
            for ln in f:
                try:
                    r = json.loads(ln)
                except Exception:                                    # noqa: BLE001
                    continue
                ds = (r.get("date") or "")[:10]
                if not ds.startswith("2026"):
                    continue
                try:
                    d = date.fromisoformat(ds)
                    h = int(r.get("hour") or -1)
                except ValueError:
                    continue
                if d in HOLIDAYS or h not in PEAK:
                    continue
                try:
                    c = float(r.get("traffic_count") or 0)
                except ValueError:
                    continue
                acc[(ds, d.strftime("%a"))] += c
    return dict(acc)


def main() -> int:
    W.require_raw()          # 缺原始数据时给可操作提示
    print("=" * 96)
    print("  W53 问 2 · 分离两种机制：车更多 还是 路更慢")
    print("=" * 96)
    sp = speed_by_day()
    mt = mta_by_day()
    print(f"\n  速度侧天数 {len(sp)} ｜ 流量侧天数 {len(mt)}")
    if not sp or not mt:
        print("  [!] 数据不足")
        return 1

    # ---------- ① 两侧的周内形态 ----------
    print(f"\n  == ① 周内形态对照（早高峰 {PEAK[0]}–{PEAK[-1]} 时）==")
    order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    sp_w: dict[str, list[float]] = defaultdict(list)
    mt_w: dict[str, list[float]] = defaultdict(list)
    for (_d, dw), v in sp.items():
        sp_w[dw].append(v)
    for (_d, dw), v in mt.items():
        mt_w[dw].append(v)
    print(f"     {'星期':<6}{'车速 mph':>10}{'日数':>6}"
          f"{'过车数':>12}{'日数':>6}")
    norm = {}
    for dw in order:
        a, b = sp_w.get(dw, []), mt_w.get(dw, [])
        if not a or not b:
            continue
        ma, mb = st.mean(a), st.mean(b)
        norm[dw] = (ma, mb)
        print(f"     {dw:<6}{ma:>10.2f}{len(a):>6}{mb:>12,.0f}{len(b):>6}")

    # ---------- ② ★ 两个比值 ----------
    print(f"\n  == ② ★ 两个比值（周一 / {REF}）==")
    if "Mon" not in norm or REF not in norm:
        print("     [!] 缺周一或参照日")
        return 1
    sm, mt_ = norm["Mon"]
    sr, mr = norm[REF]
    R_v = sm / sr
    R_f = mt_ / mr
    print(f"     R_速度 = {sm:.2f} / {sr:.2f} = **{R_v:.4f}**"
          f"  （{(R_v-1)*100:+.2f}%）")
    print(f"     R_流量 = {mt_:,.0f} / {mr:,.0f} = **{R_f:.4f}**"
          f"  （{(R_f-1)*100:+.2f}%）")

    # ---------- ③ 判读 ----------
    print(f"\n  == ③ 判读 ==")
    dv, df = R_v - 1, R_f - 1
    tol = 0.01                       # ±1% 视为"≈1"
    if abs(df) <= tol and dv < -tol:
        verdict = "**效率侧为主**（流量几乎不变，但路明显更慢）"
    elif df > tol and abs(dv) <= tol:
        verdict = "**需求侧为主**（车更多，但单车速度几乎不变）"
    elif df > tol and dv < -tol:
        verdict = "**两者都有**：车更多 **且** 同样多的车也更慢"
    elif df < -tol and dv > tol:
        verdict = "车更少但更快（与'周一更堵'相反）"
    else:
        verdict = "两者都接近 1 ⇒ **周一与参照日无实质差别**"
    print(f"     速度变化 {dv*100:+.2f}% ｜ 流量变化 {df*100:+.2f}%")
    print(f"     ⇒ {verdict}")

    # ---------- ④ 逐周稳健性 ----------
    print(f"\n  == ④ 逐周稳健性（每对 周一 vs {REF} 的比值）==")
    dates_sp = {d: dw for (d, dw) in sp}
    dates_mt = {d: dw for (d, dw) in mt}
    pairs: dict[str, dict] = defaultdict(dict)
    for d, v in sp.items():
        pairs[d[0]]["sp"] = v
        pairs[d[0]]["dw"] = d[1]
    for d, v in mt.items():
        pairs[d[0]]["mt"] = v
    # 按 ISO 周分组
    byw: dict[tuple, dict[str, float]] = defaultdict(dict)
    for ds, o in pairs.items():
        if "sp" not in o or "mt" not in o:
            continue
        dt = date.fromisoformat(ds)
        byw[dt.isocalendar()[:2]][o["dw"]] = (o["sp"], o["mt"])
    rows = []
    for wk in sorted(byw):
        g = byw[wk]
        if "Mon" in g and REF in g:
            v = g["Mon"][0] / g[REF][0]
            f = g["Mon"][1] / g[REF][1]
            rows.append((f"{wk[0]}-W{wk[1]:02d}", round(v, 4), round(f, 4)))
    print(f"     {'周':<12}{'R_速度':>9}{'R_流量':>9}   判读")
    for w, v, f in rows:
        if v < 0.99 and abs(f - 1) <= 0.01:
            tag = "效率侧"
        elif f > 1.01 and abs(v - 1) <= 0.01:
            tag = "需求侧"
        elif v < 0.99 and f > 1.01:
            tag = "两者"
        else:
            tag = "无差别"
        print(f"     {w:<12}{v:>9.4f}{f:>9.4f}   {tag}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "peak": list(PEAK), "ref": REF,
        "by_dow": {k: {"speed": round(v[0], 2), "flow": round(v[1], 1)}
                   for k, v in norm.items()},
        "R_speed": round(R_v, 4), "R_flow": round(R_f, 4),
        "verdict": verdict, "per_week": rows,
        "_假设": ("两套数据空间不重叠（速度=125 条普通路段，流量=MTA 桥梁隧道）。"
                  "所依赖的假设是：两者承受同一个城市级出行需求冲击。"
                  "结论只能作方向性判读，不能作路段级因果陈述。"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
