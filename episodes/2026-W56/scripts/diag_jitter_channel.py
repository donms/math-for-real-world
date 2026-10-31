#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W56 · 诊断：那处排序交换，是**哪一个通道**在驱动。

## 为什么要做这个诊断

`roc_daily.py --sweep` 的敏感性 D 只做**整体**类内变异放大（所有通道同乘一个倍数），
于是只能报出"排序交换了"，报不出"为什么"。
主管要求把它拆开：**对每种传感，一次只放大一个通道**，看是谁在驱动。

## 做法

`features.json` 里的每一格只有 `mean` 与 `std`，而判别投影（Fisher 方向）
与可分性（式 31）都只依赖这两个量。于是"把某通道的类内变异放大 $k$ 倍"
可以**精确地**实现为把该通道所有活动的 `std` 乘 $k$（类中心不动），
不必重跑蒙特卡洛。

**这个等价性要验**：把所有通道同乘 $k$ 的后缩放结果，与
`sig_confounders.run(jitter=k)` 真跑的结果对比，差异应当很小（见 `--selftest`）。

## 两套算子（论文表 21）

1. **std×k、类中心不动**：上面的做法，产出 `all`（整体）与 `single`（单通道）。
2. **生成参数级**：用 `sig_confounders.run(jitter=1.0, jmap={key: k})` 只放大
   驱动该通道的**生成参数**，**重跑**蒙特卡洛；信号是重新合成的，所以
   **类中心会跟着移动**（峰值检测的向上偏置就在这时进来）。产出 `gen`。

**两套不能混用**：同一个操作（速度通道 ×1.4）在 std×k 下给可穿戴 19.6%、
毫米波 19.0%（两路都掉），在生成参数级下给 20.1%、23.2%（毫米波**不降反升**）。
论文的挂法是"顶上"只挂生成参数级、"命门与份额"只挂 std×k。

## 用法

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"
$PY scripts\\diag_jitter_channel.py              # 表 + 落盘
$PY scripts\\diag_jitter_channel.py --selftest    # 断言
```
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roc_daily as RD                                     # noqa: E402
import sig_confounders as SC                              # noqa: E402

UNKNOWN_N = 60.0          # 工程实际口径（与论文主表一致）
UNKNOWN_REL = 0.45
JITTERS = (1.0, 1.4, 1.8)
# 通道 → 驱动它的生成参数（`sig_fall.JIT` 的键）。生成参数级算子按这张表放大：
# 放大 `v` 的参数 = 放大速度通道的类内变异，`aimp` → 冲击，`dh` → 高度，`th` → 姿态。
KEY_OF_CH = {"v": "v", "a": "aimp", "h": "dh", "th": "th"}


def scale_channels(stats: dict, sensor: str, channels: list[str],
                   k: float) -> dict:
    r"""把 `sensor` 的指定通道在所有活动上的 `std` 乘 $k$（类中心不动）。"""
    s = copy.deepcopy(stats)
    for a in s:
        for c in channels:
            d = s[a].get(sensor, {}).get(c)
            if d and d.get("std") is not None:
                d["std"] = float(d["std"]) * k
    return s


def run_report(stats: dict, sensor: str, unknown_n: float = UNKNOWN_N,
               unknown_rel: float = UNKNOWN_REL) -> dict:
    r"""在给定特征统计下，重算六种传感的主表并取 `sensor` 那一行。"""
    sensors = list(stats[next(iter(stats))])
    RD.N_SCEN = dict(RD.N_PER_DAY["bedroom"])
    out = RD.report({"stats": stats, "sensors": sensors}, "bedroom",
                    RD.TARGET_FA, RD.GATE_BY_SCEN["bedroom"],
                    unknown_n, unknown_rel, verbose=False)
    return out[sensor]


def gen_operator(stats: dict, sensors: list[str], n: int = 120) -> dict:
    r"""**生成参数级**算子：只把驱动某通道的生成参数标准差乘 $k$，重跑蒙特卡洛。

    与 `scale_channels` 的差别只有一处，但足以改变方向：这条路上信号是
    **重新合成**的，所以**类中心会跟着移动**（峰值检测的向上偏置就在这时进来）。
    论文表 21 的第一套就是它。
    """
    out: dict = {}
    for k in JITTERS:
        if abs(k - 1.0) < 1e-9:
            continue
        out[k] = {}
        for ch, key in KEY_OF_CH.items():
            st = SC.run(n=n, jitter=1.0, jmap={key: k}, verbose=False)
            row = {}
            for s in sensors:
                r = run_report(st["stats"], s)
                row[s] = dict(pd=r["pd"], d=r["d"], worst=r["worst"])
            out[k][ch] = row
    return out


def channel_shares(stats: dict, sensor: str, fall: str = "fall") -> dict:
    r"""$d'^2$ 按通道拆开：每个通道贡献了多少（%）。

    $$\hat d_{a^*}^2=\sum_{\text{ch}}\frac{(\bar f_{\text{fall,ch}}-\bar f_{a^*,\text{ch}})^2}
      {\tfrac12(\sigma_{\text{fall,ch}}^2+\sigma_{a^*,\text{ch}}^2)}$$

    "主维度"就是这个和为 100% 时占比最大的那一项。**谁的主维度被放大，谁就掉队。**
    """
    chs = [c for c in SC.CH_NAMES
           if stats[fall][sensor].get(c, {}).get("mean") is not None]
    acts = [a for a in stats if a != fall]

    def vec(a):
        return [stats[a][sensor][c]["mean"] for c in chs]

    def var(a):
        return [max(stats[a][sensor][c]["std"], 1e-9) ** 2 for c in chs]

    mf = vec(fall)
    dist = {}
    for a in acts:
        vt = [0.5 * (x + y) for x, y in zip(var(fall), var(a))]
        dist[a] = sum((p - q) ** 2 / v for p, q, v in zip(mf, vec(a), vt)) ** 0.5
    a_star = min(dist, key=dist.get)
    vt = [0.5 * (x + y) for x, y in zip(var(fall), var(a_star))]
    contrib = {c: (p - q) ** 2 / v
               for c, p, q, v in zip(chs, mf, vec(a_star), vt)}
    tot = sum(contrib.values())
    return dict(worst=a_star, d=tot ** 0.5,
                shares={c: contrib[c] / tot for c in chs})


def main_loop(stats: dict, sensors: list[str]) -> dict:
    r"""对每种传感：整体放大 + 逐个通道放大，记 $d'$、检出、最坏负样本。"""
    res: dict = {}
    for s in sensors:
        chs = [c for c in SC.CH_NAMES
               if stats["fall"][s].get(c, {}).get("mean") is not None]
        res[s] = dict(channels=chs, all={}, single={}, base=None)
        sh = channel_shares(stats, s)
        res[s]["shares"] = sh
        base = run_report(stats, s)
        res[s]["base"] = dict(k=1.0, pd=base["pd"], d=base["d"],
                              worst=base["worst"])
        for k in JITTERS:
            if abs(k - 1.0) < 1e-9:
                continue
            r = run_report(scale_channels(stats, s, chs, k), s)
            res[s]["all"][k] = dict(pd=r["pd"], d=r["d"], worst=r["worst"])
            res[s]["single"][k] = {}
            for c in chs:
                rc = run_report(scale_channels(stats, s, [c], k), s)
                res[s]["single"][k][c] = dict(pd=rc["pd"], d=rc["d"],
                                              worst=rc["worst"])
    return res


def print_table(res: dict, sensors: list[str]) -> None:
    print("=" * 96)
    print(f"  分通道放大类内变异（工程实际口径：未知活动 {UNKNOWN_N:.0f} 次/天，"
          f"相似度 {UNKNOWN_REL:.2f}）")
    print("=" * 96)
    for s in sensors:
        r = res[s]
        chs = r["channels"]
        print(f"\n  {s}（通道：{', '.join(chs)}）  基准 d′={r['base']['d']:.2f}"
              f"  检出={r['base']['pd']*100:.1f}%  最坏负样本={r['base']['worst']}")
        print(f"    {'放大倍数':<10}{'整体':>10}" +
              "".join(f"{'仅 ' + c:>12}" for c in chs))
        for k in JITTERS:
            if abs(k - 1.0) < 1e-9:
                print(f"    {'×1.0':<10}{r['base']['pd']*100:>9.1f}%" +
                      "".join(f"{'—':>12}" for c in chs))
                continue
            line = f"    {'×%.1f' % k:<10}{r['all'][k]['pd']*100:>9.1f}%"
            for c in chs:
                line += f"{r['single'][k][c]['pd']*100:>11.1f}%"
            print(line)
        # 谁掉得最多
        for k in (1.4, 1.8):
            drops = {c: r["single"][k][c]["pd"] - r["base"]["pd"] for c in chs}
            worst_ch = min(drops, key=drops.get)
            print(f"    ×{k:.1f} 掉幅最大的是「{worst_ch}」："
                  f"{drops[worst_ch]*100:+.1f} 点（整体 {r['all'][k]['pd']*100 - r['base']['pd']*100:+.1f} 点）")
        # d'^2 的通道构成
        sh = r["shares"]
        print(f"    d′² 构成（对最坏负样本 {sh['worst']}）：" + "，".join(
            f"{c} {sh['shares'][c]*100:.1f}%" for c in chs) +
            f"　（合计 d′={sh['d']:.2f}）")


def print_ops(res: dict, sensors: list[str]) -> None:
    r"""两套算子的对照：同一个操作（某通道 ×1.4），两种实现。"""
    print("\n" + "=" * 96)
    print("  两套「放大」算子（论文表 21）：同一个操作，两种实现，方向可能相反")
    print("=" * 96)
    for s in sensors:
        rows = []
        for c in res[s]["channels"]:
            g = res[s].get("gen", {}).get(1.4, {}).get(c)
            h = res[s]["single"].get(1.4, {}).get(c)
            if g and h:
                rows.append((c, g, h))
        if not rows:
            continue
        print(f"\n  {s}（基准检出 {res[s]['base']['pd']*100:.1f}%，"
              f"d′={res[s]['base']['d']:.2f}）")
        print(f"    {'通道':<6}{'生成参数级 ×1.4':>18}{'std×k（类中心不动）×1.4':>26}")
        for c, g, h in rows:
            print(f"    {c:<6}{g['pd']*100:>12.1f}%（d′{g['d']:.2f}）"
                  f"{h['pd']*100:>19.1f}%（d′{h['d']:.2f}）")


def selftest(stats: dict, sensors: list[str]) -> int:
    r"""断言：后缩放等价性、单调性、驱动通道唯一性。"""
    k = 0

    def ck(c: bool, m: str) -> None:
        nonlocal k
        if not c:
            raise AssertionError("[X] " + m)
        k += 1
        print(f"  [OK] {m}")

    # ① 放大 1.0 倍 == 基准
    a = run_report(stats, "imu")
    b = run_report(scale_channels(stats, "imu", ["v", "a", "th"], 1.0), "imu")
    ck(abs(a["pd"] - b["pd"]) < 1e-12, "① 乘 1.0 倍与基准完全相同")

    # ② 后缩放全体 ≈ 真跑 MC 的 jitter
    real = SC.run(n=stats["fall"]["imu"]["v"]["n"], jitter=1.4, verbose=False)
    fake = scale_channels(stats, "imu", ["v", "a", "th"], 1.4)
    pa = run_report(fake, "imu")["pd"]
    pb = run_report(real["stats"], "imu")["pd"]
    ck(abs(pa - pb) < 0.10,
       f"② 后缩放 ×1.4 与真跑 MC ×1.4 差 {abs(pa-pb)*100:.1f} 点（<10 点）")

    # ③ 放大必降（只对"有判别力"的传感成立；蓝牙 d′≈0.11 属退化，单独判）
    for s in sensors:
        chs = [c for c in SC.CH_NAMES
               if stats["fall"][s].get(c, {}).get("mean") is not None]
        p0 = run_report(stats, s)["pd"]
        p1 = run_report(scale_channels(stats, s, chs, 1.8), s)["pd"]
        if run_report(stats, s)["d"] < 0.5:
            ck(p0 < 0.01 and p1 < 0.01,
               f"③ {s}：d′={run_report(stats, s)['d']:.2f} 属退化，"
               f"放大前后都在 {max(p0, p1)*100:.1f}% 的噪声里")
            continue
        ck(p1 <= p0 + 1e-12, f"③ {s}：整体放大 ×1.8 后检出必降"
                            f"（{p0*100:.1f}% → {p1*100:.1f}%）")

    # ④ 驱动通道比非驱动通道更致命
    for s in ("imu", "mmwave"):
        chs = [c for c in SC.CH_NAMES
               if stats["fall"][s].get(c, {}).get("mean") is not None]
        p0 = run_report(stats, s)["pd"]
        d = {c: run_report(scale_channels(stats, s, [c], 1.8), s)["pd"] - p0
             for c in chs}
        worst = min(d, key=d.get)
        best = max(d, key=d.get)
        ck(d[worst] < d[best],
           f"④ {s}：最致命的通道「{worst}」（{d[worst]*100:+.1f} 点）"
           f"比最温和的「{best}」（{d[best]*100:+.1f} 点）更致命")
    print(f"\n  自检通过：{k} 条断言")
    return k


def main() -> int:
    ap = argparse.ArgumentParser(description="分通道放大类内变异，找排序交换的驱动通道。")
    ap.add_argument("--json", nargs="?", const="", default=None)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]

    st = RD.load_stats(root, n=120)
    stats, sensors = st["stats"], st["sensors"]

    if args.selftest:
        print("=" * 80)
        print("  diag_jitter_channel.py 自检")
        print("=" * 80)
        selftest(stats, sensors)
        return 0

    res = main_loop(stats, sensors)
    gen = gen_operator(stats, sensors, n=int(st.get("n", 120)))
    for s in sensors:
        res[s]["gen"] = {k: {c: gen[k][c][s] for c in gen[k]
                             if c in res[s]["channels"]} for k in gen}
    print_table(res, sensors)
    print_ops(res, sensors)
    p = Path(args.json) if args.json else root / "results" / "jitter_channel.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dict(unknown_n=UNKNOWN_N, unknown_rel=UNKNOWN_REL,
                                 jitters=list(JITTERS),
                                 operators={"gen": "生成参数级：jitter=1.0, jmap={key:k}，重跑 MC，类中心随噪声移动（表 21 第一套）",
                                            "stdk": "该通道所有活动 std 同乘 k、类中心不动（表 21 第二套）"},
                                 res=res),
                            ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  [OK] JSON：{p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
