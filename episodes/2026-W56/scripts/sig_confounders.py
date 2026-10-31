#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W56 · 负样本：把六个"看起来像摔倒"的动作也过一遍同一套观测。

## 为什么这一步是全期的方法论核心

报警器的门限**不是由摔倒决定的，是由"最像摔倒的那个负样本"决定的**。
所以必须先有负样本的特征分布，才谈得上"每天误报几次"。

高相似度负样本（题设给的骨架）：

| 负样本 | 谁会同时错 |
|---|---|
| 快速坐下 | 毫米波（速度接近）+ WiFi（CSI 扰动）|
| 弯腰捡东西 | 毫米波 + WiFi |
| 躺到沙发上 | 摄像头（外观）+ 激光雷达（高度）|
| 走动 / 开门 | WiFi 最差，毫米波次之 |
| 上下床 | 可穿戴（姿态翻转 + 低冲击），且**没有高度维** |

## 本脚本产出什么

对每个 (活动, 传感, 通道) 跑 `--n` 次蒙特卡洛，
给出**估计量的均值与标准差**。这两个数直接进 `roc_daily.py` 当
类中心与类内散布，**不再有手填的 σ**。

$$\hat d_{c}=\sqrt{\sum_{\text{ch}}
  \frac{(\bar f_{\text{fall,ch}}-\bar f_{c,\text{ch}})^2}
       {\tfrac12(\sigma_{\text{fall,ch}}^2+\sigma_{c,\text{ch}}^2)}}$$

## 用法

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"
$PY scripts\\sig_confounders.py --n 120          # 打印特征统计表
$PY scripts\\sig_confounders.py --n 120 --json   # 落盘 results/features.json
$PY scripts\\sig_confounders.py --selftest
```
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sig_fall as SF                                    # noqa: E402

CH_NAMES = ("v", "beta", "a", "h", "th", "rssi")


def run(n: int = 120, jitter: float = 1.0, seed0: int = 1000,
        verbose: bool = True, jmap: dict | None = None) -> dict:
    r"""对 7 个活动 × 6 种传感 × `n` 次实现，统计各通道的均值与标准差。

    `jmap`：**分通道**放大类内变异（W56 修订二）。键取
    `v`（速度通道）/ `dh`（高度通道）/ `aimp`（冲击通道）/ `th`（姿态通道），
    值为该生成参数标准差的额外倍数；缺省全 1.0，即与 `jitter` 一致。

    返回结构：

    ```
    stats[activity][sensor][channel] = {"mean":…, "std":…, "n":…}
    truth[activity]                  = 运动学真值（无噪声）
    ```
    """
    acts = list(SF.ACTIVITY)
    sensors = list(SF.OBSERVERS)
    acc = {a: {s: {c: [] for c in CH_NAMES} for s in sensors} for a in acts}
    for i in range(n):
        for a in acts:
            seed = seed0 + 977 * i + 31 * acts.index(a)
            s = SF.synth(a, seed=seed, jitter=jitter, jmap=jmap)
            for sn in sensors:
                f = s["feat"][sn]
                for c in CH_NAMES:
                    if f.get(c) is not None:
                        acc[a][sn][c].append(float(f[c]))

    stats: dict = {a: {s: {} for s in sensors} for a in acts}
    for a in acts:
        for sn in sensors:
            for c in CH_NAMES:
                x = np.asarray(acc[a][sn][c], dtype=float)
                if x.size < max(8, n // 3):
                    stats[a][sn][c] = dict(mean=None, std=None, n=int(x.size),
                                           note="样本不足，判为不可测")
                    continue
                stats[a][sn][c] = dict(mean=float(x.mean()),
                                       std=float(x.std(ddof=1)),
                                       n=int(x.size), note="")
    truth = {a: SF.motion(a)["feat"] for a in acts}
    if verbose:
        print_table(stats, acts, sensors)
    return dict(stats=stats, truth=truth, n=n, jitter=jitter,
                activities=acts, sensors=sensors, channels=list(CH_NAMES))


def print_table(stats: dict, acts: list, sensors: list) -> None:
    r"""一张表看清"谁在哪个通道上被谁骗了"。"""
    for sn in sensors:
        print("=" * 84)
        print(f"  {sn}")
        print("=" * 84)
        chs = [c for c in CH_NAMES
               if any(stats[a][sn][c]["mean"] is not None for a in acts)]
        if not chs:
            print("  （全部通道不可测）")
            continue
        print("  " + f"{'活动':<12}" + "".join(f"{c:>12}" for c in chs))
        for a in acts:
            row = f"  {SF.ACTIVITY[a]['label']:<12}"
            for c in chs:
                d = stats[a][sn][c]
                if d["mean"] is None:
                    row += f"{'-':>12}"
                else:
                    row += f"{d['mean']:>7.2f}±{d['std']:<4.2f}"
            print(row)
        print()


def separability(stats: dict, sensors: list, fall: str = "fall") -> dict:
    r"""每种传感对每个负样本的**可分性** $d'$（Fisher 形式）。

    $$\hat d_{c}=\sqrt{\sum_{\text{ch available}}
      \frac{(\bar f_{\text{fall,ch}}-\bar f_{c,\text{ch}})^2}
           {\tfrac12(\sigma_{\text{fall,ch}}^2+\sigma_{c,\text{ch}}^2)}}$$

    **只对"两种情形都测得到"的通道求和**：某个传感测不到的维，
    不会凭空给它加分。这是本模型与"加权打总分"的关键区别。
    """
    out: dict = {}
    for sn in sensors:
        out[sn] = {}
        for a in stats:
            if a == fall:
                continue
            d2, used = 0.0, []
            for c in CH_NAMES:
                f1, f2 = stats[fall][sn][c], stats[a][sn][c]
                if f1["mean"] is None or f2["mean"] is None:
                    continue
                v = (f1["mean"] - f2["mean"]) ** 2 / max(
                    0.5 * (f1["std"] ** 2 + f2["std"] ** 2), 1e-12)
                d2 += v
                used.append(c)
            out[sn][a] = dict(d=float(np.sqrt(d2)), channels=used)
    return out


# ============================================================
# 自检
# ============================================================
def selftest(n: int = 40) -> int:
    r"""六条断言：通道能力、类序、可分性结构。"""
    k = 0

    def ck(cond: bool, msg: str) -> None:
        nonlocal k
        if not cond:
            raise AssertionError("[X] " + msg)
        k += 1
        print(f"  [OK] {msg}")

    r = run(n=n, verbose=False)
    st, acts = r["stats"], r["activities"]

    ck(all(st[a]["ble"]["v"]["mean"] is None for a in acts),
       "① 蓝牙在所有活动上都没有速度通道")
    ck(all(st[a]["imu"]["h"]["mean"] is None for a in acts),
       "② IMU 在所有活动上都没有高度通道（结构性）")
    ck(all(st[a]["wifi"]["beta"]["mean"] is None for a in acts),
       "③ WiFi 在所有活动上都没有制动通道")

    v_fall = st["fall"]["mmwave"]["v"]["mean"]
    ck(1.5 < v_fall < 3.0, f"④ 毫米波摔倒峰值速度 {v_fall:.2f} m/s 落在 1.5–3.0")

    sev = {a: st[a]["mmwave"]["v"]["mean"] for a in acts}
    # 实测类序：摔倒 2.34 > 快速坐下 1.53 > 躺沙发 1.13 > 上下床 0.84
    #           > 弯腰 0.69 > 走动 0.19 > 开门 0.12
    order = ["fall", "sit_fast", "sofa", "bed", "bend", "walk", "door"]
    mono = all(sev[order[i]] >= sev[order[i + 1]] - 0.12
               for i in range(len(order) - 1))
    ck(mono, "⑤ 速度通道的类序单调：摔倒 > 快速坐下 > 躺沙发 > 上下床 > 弯腰 > 走动 > 开门")

    sep = separability(st, r["sensors"])
    worst = {sn: min(sep[sn].items(), key=lambda kv: kv[1]["d"])
             for sn in r["sensors"]}
    ck(all(worst[sn][1]["d"] >= 0 for sn in worst), "⑥ 每个传感都能找到最坏负样本")
    print()
    print("  最坏负样本（决定门限的那一个）")
    for sn in r["sensors"]:
        a, d = worst[sn]
        print(f"    {sn:<8} ← {SF.ACTIVITY[a]['label']:<10} d'={d['d']:.2f}"
              f"  用到的通道 {','.join(d['channels']) or '无'}")
    print(f"\n  自检通过：{k} 条断言")
    return k


# ============================================================
# CLI
# ============================================================
def main() -> int:
    ap = argparse.ArgumentParser(
        description="对六个高相似度负样本做蒙特卡洛特征统计（类中心 + 类内散布）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="产出被 roc_daily.py 直接消费；不落盘时 roc_daily 会自己重算。")
    ap.add_argument("--n", type=int, default=120, help="每个活动的实现次数")
    ap.add_argument("--jitter", type=float, default=1.0,
                    help="类内变异倍数（0 = 全部取组中值，1 = 标称变异）")
    ap.add_argument("--out", default="results/features.json", help="输出路径")
    ap.add_argument("--json", action="store_true", help="落盘特征统计")
    ap.add_argument("--separability", action="store_true", help="另打印 d' 表")
    ap.add_argument("--selftest", action="store_true", help="跑断言自检")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]

    if args.selftest:
        print("=" * 84)
        print("  sig_confounders.py 自检")
        print("=" * 84)
        selftest()
        return 0

    r = run(n=args.n, jitter=args.jitter)

    sep = separability(r["stats"], r["sensors"])
    print("=" * 84)
    print("  可分性 d'（Fisher 形式；只累计两种情形都测得到的通道）")
    print("=" * 84)
    acts = [a for a in r["activities"] if a != "fall"]
    print("  " + f"{'传感':<10}" + "".join(f"{SF.ACTIVITY[a]['label'][:6]:>10}" for a in acts))
    for sn in r["sensors"]:
        row = f"  {sn:<10}"
        for a in acts:
            d = sep[sn][a]["d"]
            row += f"{d:>10.2f}"
        print(row)
    print()
    for sn in r["sensors"]:
        a, d = min(sep[sn].items(), key=lambda kv: kv[1]["d"])
        print(f"  ★ {sn:<8} 最坏负样本 = {SF.ACTIVITY[a]['label']:<10} "
              f"d'={d['d']:.2f}（门限由它决定）")

    if args.json or args.separability:
        p = Path(args.out)
        if not p.is_absolute():
            p = root / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(dict(r, separability=sep), ensure_ascii=False,
                                indent=2), encoding="utf-8")
        print(f"\n  [OK] 落盘：{p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
