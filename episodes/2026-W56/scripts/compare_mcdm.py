#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W56 · 多准则决策：给帕累托前沿，不给单一冠军。

## 为什么不能只比检出率

`roc_daily.py` 算出的检出率只在一维上排序。但选型要同时看六件事：

| 准则 | 为什么它不能省 |
|---|---|
| 检出率（0.1 次/天约束下）| 主指标，但不唯一 |
| **三年总成本** | 硬件只是其中一项，可穿戴还有**每天充电的人力** |
| 安装人时 | 老人家里装摄像头要打孔、要走线 |
| **隐私** | 摄像头能数清你脸上的皱纹；点云能还原轮廓 |
| **依从性** | 可穿戴要人戴，不戴就归零（见 q2 的佩戴率折扣）|
| **多人辨识** | 养老院多人间必须回答"是谁摔了" |

$$\boxed{\text{没有单一冠军，只有「在什么条件下选什么」}}$$

## 帕累托怎么给

两个准则 $x$（成本，越小越好）、$y$（有效检出率，越大越好）下，
点 $i$ 被点 $j$ **支配**当且仅当

$$C_j\le C_i\ \wedge\ D_j\ge D_i\ \wedge\ (C_j<C_i\ \vee\ D_j>D_i)$$

不被任何人支配的点构成**帕累托前沿**。本脚本给两个前沿：

1. **成本 vs 有效检出率**（二维，能画）；
2. **六准则全部参与**（$2^6$ 维，只用非支配判定，画不出来但能列）。

## 用法

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"
$PY scripts\\compare_mcdm.py
$PY scripts\\compare_mcdm.py --scenario nh --fig --json
$PY scripts\\compare_mcdm.py --weights 检出=2.0,隐私=2.0
$PY scripts\\compare_mcdm.py --selftest
```
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sig_fall as SF                                     # noqa: E402
import roc_daily as RD                                    # noqa: E402

# ============================================================
# 0. 六准则的数据（③ 全部自定假设，量级来自公开电商报价）
# ============================================================
# tco3：三年总成本（元/间）。可穿戴含"每天充电 3 分钟"的人力
#       0.05 h/天 × 365 × 3 年 × 30 元/h ≈ 1644 元。
# install：安装人时（走线、打孔、调试）。
# privacy：0=最差 10=最好（可识别度越低越高分）。
# wear：是否需要佩戴（1=需要）。
# ident：多人场景能否回答"是谁摔了"（0=不能 3=能且可再识别）。
# note：一句话的隐藏成本，必须随结论出现。
OPTIONS = {
    "camera": dict(label="摄像头", cap="普通 IPC 约几百元，边缘算力盒另计",
                   hw=(300, 800), hw_mid=550, install=0.5,
                   privacy=2.0, wear=0, ident=3,
                   note="可数人脸（5 m 处人脸约 73 px）⇒ 隐私最差，卧室装它要另签同意"),
    "mmwave": dict(label="毫米波雷达", cap="60/77 GHz FMCW 模组数十到数百元",
                   hw=(80, 300), hw_mid=190, install=0.3,
                   privacy=6.0, wear=0, ident=1,
                   note="无图像，但角度分辨决定它在多人间分不清并排两张床"),
    "wifi": dict(label="WiFi CSI", cap="硬件零增量，但要能取 CSI",
                 hw=(0, 300), hw_mid=150, install=0.2,
                 privacy=4.0, wear=0, ident=0,
                 note="★ 隐藏成本：多数商用路由器取不到 CSI，需专用网卡或刷机"),
    "ble": dict(label="蓝牙 RSSI", cap="网关 + 4 个信标",
                hw=(150, 400), hw_mid=275, install=0.5,
                privacy=8.0, wear=0, ident=1,
                note="最便宜，但 RSSI 分不出'有人挡链路'与'人倒在地上'"),
    "lidar": dict(label="激光雷达", cap="千元级起，扫描式更贵",
                  hw=(1500, 6000), hw_mid=3750, install=0.5,
                  privacy=3.0, wear=0, ident=3,
                  note="点云仍可还原人体轮廓（3 m 处约 4500 个可见点）⇒ '无图像'不等于隐私安全"),
    "imu": dict(label="可穿戴 IMU", cap="手环 200–600 元/人 + 每天充电",
                hw=(200, 600), hw_mid=400, install=0.1,
                privacy=9.0, wear=1, ident=3,
                note="★ 硬件最便宜之一，但每天充电是长期人力：三年约 1644 元/人"),
}

WEAR_LABOR_YUAN_PER_YEAR = 0.05 * 365 * 30.0      # ③ 每天 3 分钟 × 30 元/时
YEARS = 3.0

# 六准则的默认权重（③，可被 --weights 覆盖）
W_DEFAULT = {"det": 0.35, "cost": 0.15, "install": 0.05,
             "privacy": 0.20, "wear": 0.10, "ident": 0.15}


def tco3(key: str) -> float:
    r"""三年总成本。可穿戴含充电人力。"""
    o = OPTIONS[key]
    return float(o["hw_mid"]) + YEARS * (WEAR_LABOR_YUAN_PER_YEAR if o["wear"] else 0.0)


# ============================================================
# 1. 六准则矩阵
# ============================================================
def criteria(roc: dict, wear_rate: float = 0.60) -> dict:
    r"""把检出率与五项非检出准则拼成一张表。

    有效检出率 = 模型检出率 × 佩戴率（只对需要佩戴的方案打折）。
    """
    rows = {}
    for k, o in OPTIONS.items():
        if k not in roc:
            continue
        pd = roc[k]["pd"]
        pd_eff = pd * (wear_rate if o["wear"] else 1.0)
        rows[k] = dict(
            label=o["label"], pd=pd, pd_eff=pd_eff,
            cost=tco3(k), cost_lo=o["hw"][0] + (YEARS * WEAR_LABOR_YUAN_PER_YEAR
                                                if o["wear"] else 0.0),
            cost_hi=o["hw"][1] + (YEARS * WEAR_LABOR_YUAN_PER_YEAR
                                  if o["wear"] else 0.0),
            install=o["install"], privacy=o["privacy"], wear=o["wear"],
            ident=o["ident"], note=o["note"], cap=o["cap"],
            respond=roc[k]["respond"], d=roc[k]["d"],
            worst=roc[k]["worst"],
        )
    return rows


# ============================================================
# 2. 帕累托
# ============================================================
def pareto2(rows: dict, xkey: str = "cost", ykey: str = "pd_eff",
            x_better: str = "min") -> list[str]:
    r"""二维帕累托前沿：$x$ 越小越好、$y$ 越大越好。"""
    ks = list(rows)
    front = []
    for a in ks:
        dom = False
        for b in ks:
            if a == b:
                continue
            xa, xb = rows[a][xkey], rows[b][xkey]
            ya, yb = rows[a][ykey], rows[b][ykey]
            if x_better == "min":
                better_x = xb <= xa
                strict_x = xb < xa
            else:
                better_x = xb >= xa
                strict_x = xb > xa
            if better_x and yb >= ya and (strict_x or yb > ya):
                dom = True
                break
        if not dom:
            front.append(a)
    return sorted(front, key=lambda k: rows[k][xkey])


def pareto_nd(rows: dict, vec: dict) -> list[str]:
    r"""$n$ 维非支配集：`vec[k]` 是"越大越好"的六准则向量。"""
    ks = list(rows)
    front = []
    for a in ks:
        dom = False
        for b in ks:
            if a == b:
                continue
            va, vb = vec[a], vec[b]
            if all(vb[i] >= va[i] for i in range(len(va))) and any(
                    vb[i] > va[i] for i in range(len(va))):
                dom = True
                break
        if not dom:
            front.append(a)
    return front


def normalize(rows: dict, wear_rate: float) -> dict:
    r"""每个准则归一到 [0,1]，方向统一成"越大越好"。"""
    keys = list(rows)
    out = {k: {} for k in keys}

    def nz(vals, better="max"):
        lo, hi = min(vals), max(vals)
        if hi - lo < 1e-12:
            return [0.5] * len(vals)
        return [((v - lo) / (hi - lo)) if better == "max"
                else ((hi - v) / (hi - lo)) for v in vals]

    for name, get, better in (("det", lambda k: rows[k]["pd_eff"], "max"),
                              ("cost", lambda k: rows[k]["cost"], "min"),
                              ("install", lambda k: rows[k]["install"], "min"),
                              ("privacy", lambda k: rows[k]["privacy"], "max"),
                              ("wear", lambda k: rows[k]["wear"], "min"),
                              ("ident", lambda k: rows[k]["ident"], "max")):
        vs = nz([get(k) for k in keys], better)
        for k, v in zip(keys, vs):
            out[k][name] = float(v)
    return out


def weighted(norm: dict, w: dict) -> dict:
    tot = sum(w.values())
    return {k: sum(norm[k][c] * w[c] for c in w) / tot for k in norm}


# ============================================================
# 3. 出图
# ============================================================
def make_fig(rows: dict, front: list[str], path: Path,
             scenario: str = "bedroom", wear_rate: float = 0.6) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    C = dict(bg="#0e1117", fg="#e8e8e8", grid="#2a2f3a",
             c={"lidar": "#3f9bd8", "camera": "#39c07a", "imu": "#9b6bd8",
                "mmwave": "#f0a02a", "wifi": "#e8465a", "ble": "#7a8394"})

    fig, ax = plt.subplots(figsize=(10.6, 6.4))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.tick_params(colors=C["fg"], labelsize=9)
    for sp in ax.spines.values():
        sp.set_color(C["grid"])
    ax.grid(alpha=.22, color=C["grid"], lw=.6)

    for k, r in rows.items():
        on = k in front
        ax.scatter(r["cost"], r["pd_eff"] * 100, s=190 if on else 120,
                   color=C["c"][k], edgecolor="#fff" if on else "#111",
                   linewidth=2.0 if on else .8, zorder=5 if on else 3)
        ax.annotate(f"{r['label']}\n{r['pd_eff']*100:.0f}%  {r['cost']:.0f} 元",
                    (r["cost"], r["pd_eff"] * 100),
                    textcoords="offset points", xytext=(9, -4),
                    color=C["fg"], fontsize=8.4)
    fr = sorted(front, key=lambda k: rows[k]["cost"])
    if len(fr) >= 2:
        ax.plot([rows[k]["cost"] for k in fr], [rows[k]["pd_eff"] * 100 for k in fr],
                color="#ffd479", lw=1.6, ls="--", zorder=2,
                label="帕累托前沿（成本 vs 有效检出）")
        ax.legend(fontsize=8.5, facecolor=C["bg"], edgecolor=C["grid"],
                  labelcolor=C["fg"], loc="lower right")

    ax.set_xscale("log")
    ax.set_xlabel("三年总成本（元/间，对数轴；可穿戴含每天充电人力）",
                  color=C["fg"], fontsize=10)
    ax.set_ylabel(f"有效检出率（佩戴率 {wear_rate:.0%} 后，%）", color=C["fg"],
                  fontsize=10)
    ax.set_ylim(0, 108)
    nm = {"bedroom": "独居老人卧室", "nh": "养老院多人间"}[scenario]
    ax.set_title(f"W56 · {nm}：成本与有效检出的帕累托前沿（白边 = 不被支配）",
                 color=C["fg"], fontsize=11.5)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140, facecolor=C["bg"])
    plt.close(fig)
    return path


# ============================================================
# 4. 自检
# ============================================================
def selftest() -> int:
    k = 0

    def ck(c: bool, m: str) -> None:
        nonlocal k
        if not c:
            raise AssertionError("[X] " + m)
        k += 1
        print(f"  [OK] {m}")

    rows = {
        "a": dict(cost=100.0, pd_eff=0.5, install=1, privacy=5, wear=0, ident=1),
        "b": dict(cost=200.0, pd_eff=0.7, install=1, privacy=5, wear=0, ident=1),
        "c": dict(cost=300.0, pd_eff=0.4, install=1, privacy=5, wear=0, ident=1),
        "d": dict(cost=400.0, pd_eff=0.9, install=1, privacy=5, wear=0, ident=1),
    }
    f = pareto2(rows)
    ck("a" in f and "c" not in f, f"① c(300 元,40%) 被 a(100 元,50%) 支配 ⇒ {f}")
    ck("b" in f and "d" in f, "② b 与 d 都不被支配")

    o = dict(OPTIONS)
    ck(tco3("imu") > OPTIONS["imu"]["hw_mid"] * 3,
       f"③ 可穿戴三年总成本 {tco3('imu'):.0f} 元 ≫ 硬件 {OPTIONS['imu']['hw_mid']} 元")
    ck(tco3("mmwave") == OPTIONS["mmwave"]["hw_mid"],
       "④ 不需要佩戴的方案，三年成本 = 硬件成本")

    vs = {kk: (rows[kk]["pd_eff"], -rows[kk]["cost"]) for kk in rows}
    nd = pareto_nd(rows, vs)
    ck("c" not in nd, "⑤ 二维非支配集也剔掉被支配的 c")
    print(f"\n  自检通过：{k} 条断言")
    return k


# ============================================================
# 5. CLI
# ============================================================
def main() -> int:
    ap = argparse.ArgumentParser(
        description="六准则决策：给帕累托前沿与「在什么条件下选什么」，不给单一冠军。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="权重可改；帕累托前沿不依赖权重。")
    ap.add_argument("--scenario", default="bedroom", choices=sorted(RD.N_PER_DAY))
    ap.add_argument("--wear-rate", type=float, default=0.60,
                    help="可穿戴佩戴率（默认 0.60）")
    ap.add_argument("--weights", default="",
                    help="覆盖权重，如 检出=2.0,隐私=2.0")
    ap.add_argument("--n", type=int, default=120, help="特征统计蒙特卡洛次数")
    ap.add_argument("--unknown-n", type=float, default=0.0,
                    help="每天未建模活动次数（0=上界口径；60=工程实际口径）")
    ap.add_argument("--unknown-rel", type=float, default=0.45,
                    help="未知活动的相对可分性（默认 0.45）")
    ap.add_argument("--fig", nargs="?", const="", default=None, help="出帕累托图")
    ap.add_argument("--json", nargs="?", const="", default=None)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]

    if args.selftest:
        print("=" * 80)
        print("  compare_mcdm.py 自检")
        print("=" * 80)
        selftest()
        return 0

    st = RD.load_stats(root, n=args.n)
    RD.N_SCEN = dict(RD.N_PER_DAY[args.scenario])
    gate = RD.GATE_BY_SCEN[args.scenario]
    roc = RD.report(st, args.scenario, RD.TARGET_FA, gate,
                    args.unknown_n, args.unknown_rel, verbose=False)
    rows = criteria(roc, args.wear_rate)

    print("=" * 96)
    print(f"  六准则表（场景：{args.scenario}，佩戴率 {args.wear_rate:.0%}，"
          f"未知活动 {args.unknown_n:.0f} 次/天、相似度 {args.unknown_rel:.2f}）")
    print("=" * 96)
    print(f"  {'方案':<11}{'检出':>7}{'有效检出':>9}{'d′':>6}{'三年成本':>9}"
          f"{'安装人时':>9}{'隐私':>6}{'需佩戴':>7}{'多人辨识':>9}")
    print("  " + "-" * 92)
    for k, r in sorted(rows.items(), key=lambda kv: -kv[1]["pd_eff"]):
        print(f"  {r['label']:<11}{r['pd']*100:>6.1f}%{r['pd_eff']*100:>8.1f}%"
              f"{r['d']:>6.2f}{r['cost']:>8.0f}元{r['install']:>9.1f}"
              f"{r['privacy']:>6.1f}{'是' if r['wear'] else '否':>7}{r['ident']:>9.0f}")
    print()
    for k, r in rows.items():
        print(f"  · {r['label']}：{r['note']}")
    print()

    front = pareto2(rows)
    print("=" * 96)
    print("  帕累托前沿（成本 × 有效检出）：不被任何其他方案同时做到更便宜且更准")
    print("=" * 96)
    for k in front:
        r = rows[k]
        print(f"  ★ {r['label']:<11} {r['cost']:>6.0f} 元  {r['pd_eff']*100:>5.1f}%"
              f"  隐私 {r['privacy']:.1f}  多人辨识 {r['ident']:.0f}")
    print()

    norm = normalize(rows, args.wear_rate)
    w = dict(W_DEFAULT)
    if args.weights:
        for seg in args.weights.split(","):
            if "=" in seg:
                nm, v = seg.split("=")
                nm = nm.strip()
                alias = {"检出": "det", "成本": "cost", "安装": "install",
                         "隐私": "privacy", "依从": "wear", "辨识": "ident"}
                w[alias.get(nm, nm)] = float(v)
    sc = weighted(norm, w)
    nd = pareto_nd(rows, {k: tuple(norm[k][c] for c in w) for k in rows})
    print("=" * 96)
    print(f"  六准则加权得分（权重 {w}）与六维非支配集")
    print("=" * 96)
    for k in sorted(sc, key=lambda x: -sc[x]):
        mark = "★非支配" if k in nd else "  被支配"
        print(f"  {mark}  {rows[k]['label']:<11} 得分 {sc[k]:.4f}")
    print()
    print("  ⚠ 权重要影响排序，所以本表**不能当唯一推荐**用。")
    print("    要据场景取值：卧室重隐私，养老院重多人辨识。")
    print()

    if args.fig is not None:
        p = Path(args.fig) if args.fig else root / "results" / "figs" / "fig_pareto.png"
        make_fig(rows, front, p, args.scenario, args.wear_rate)
        print(f"  [OK] 图：{p}")
    if args.json is not None:
        p = Path(args.json) if args.json else root / "results" / "mcdm.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(dict(rows={k: {kk: vv for kk, vv in v.items()}
                                          for k, v in rows.items()},
                                     front=front, weights=w, score=sc,
                                     nondominated=nd, scenario=args.scenario,
                                     wear_rate=args.wear_rate,
                                     unknown_n=args.unknown_n,
                                     unknown_rel=args.unknown_rel),
                                ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [OK] JSON：{p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
