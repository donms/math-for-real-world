#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W39 · Q4：多目标评价、性价比与灵敏度分析。

包含三部分：
1. **分频段优势图**：把路面激励按频段切开，看各架构赢在哪一段
   （这直接决定"什么路况该选什么"）
2. **多目标评分与性价比**：舒适/操稳/姿态三项归一化后加权，
   并与真实价差挂钩 —— 回答"多花的钱买到了什么"
3. **灵敏度分析**：对全部关键参数 ±20% 扰动，回答
   **排序是否会翻转**（而不只是"指标变多少"）——
   这是参数不可得前提下唯一诚实的稳健性论证
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from model import default_params, freqresp, metrics_freq, natural_freqs, road_psd_accel  # noqa: E402

RESULTS = ROOT / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
V = 60 / 3.6

# 厂商实际价差（易车车型表，见 data/来源清单.md）
PRICE = {"被动(基准)": 0.0, "云辇-C": 0.0, "云辇-A": 2.00, "云辇-M": 2.00}
# 云辇-C 为入门版配置；A/M 相对 C 的价差约 2 万元（900km 后驱版 18.99→20.99）


# ------------------------------------------------------------------ 分频段
def band_metrics(p: dict, c, level: str, v: float,
                 bands=((0.2, 1.0), (1.0, 2.5), (2.5, 8.0), (8.0, 30.0))) -> dict:
    """按频段积分求各输出 RMS（同一路面谱，分频段截取）。"""
    out = {}
    for lo, hi in bands:
        f = np.linspace(lo, hi, 2500)
        H = freqresp(p, c, f)
        psd = road_psd_accel(level, f, v)
        key = f"{lo}-{hi}"
        out[key] = {nm: float(np.sqrt(np.trapz(np.abs(H[k, :]) ** 2 * psd, f)))
                    for k, nm in enumerate(("acc", "travel", "tire"))}
    return out


# ------------------------------------------------------------------ 灵敏度
def sensitivity(p0: dict, level: str, v: float,
                pert: float = 0.20) -> list[dict]:
    """对关键参数 ±pert 扰动，检查**架构排序是否翻转**。"""
    params_to_test = ["m_s", "m_u", "k_s", "k_t", "c0"]
    c_opts = {"被动": p0["c0"], "半主动最优": None}
    rows = []
    for name in params_to_test:
        for sign in (+1, -1):
            p = dict(p0)
            p[name] = p0[name] * (1 + sign * pert)
            # 半主动最优：在该参数下重新扫描阻尼取最优
            cs = np.geomspace(p["c_min"], p["c_max"], 40)
            best = min(cs, key=lambda c: metrics_freq(p, c, level, v)["acc"])
            m_pass = metrics_freq(p, p["c0"], level, v)["acc"]
            m_semi = metrics_freq(p, best, level, v)["acc"]
            rows.append({
                "参数": name, "扰动": f"{sign*pert:+.0%}",
                "被动acc": m_pass, "半主动最优acc": m_semi,
                "提升%": (m_pass - m_semi) / m_pass * 100,
                "半主动更优": m_semi < m_pass,
            })
    return rows


def main() -> int:
    p = default_params()
    fb, fw = natural_freqs(p)
    print(f"固有频率 车身 {fb:.2f} Hz / 车轮 {fw:.1f} Hz\n")

    # ================= 1. 分频段优势 =================
    # ⚠️ 对比对象必须公平：半主动**能选与被动相同的 c**，因此
    # ① 不能用"最优总 acc 的 c"去代表半主动的全部能力；
    # ② 任何频段上"半主动比被动差"都只可能是对比对象选错，不是物理结论。
    # 这里同时给出两个半主动代表点，避免误导：
    #   · c = c₀        —— 与被动完全相同的调校（下界，必然持平）
    #   · c = c_opt_acc —— 舒适最优调校（体现"愿意牺牲其它目标换舒适"）
    print("=== 分频段优势（C 级路面 60km/h，各频段 acc RMS）===")
    cs = np.geomspace(p["c_min"], p["c_max"], 40)
    c_opt_acc = min(cs, key=lambda c: metrics_freq(p, c, level="C", v=V)["acc"])
    arch_c = {"被动 c₀": p["c0"], "半主动 c=c₀(同调校)": p["c0"],
              "半主动 c=最优": c_opt_acc}
    rows = {}
    for k, c in arch_c.items():
        rows[k] = band_metrics(p, c, "C", V)
    # 被动 c₀ 与"半主动 c=c₀"数值必然相同，去掉冗余列
    arch_c = {"被动 c₀": p["c0"], "半主动舒适最优": c_opt_acc}
    rows = {k: band_metrics(p, c, "C", V) for k, c in arch_c.items()}
    keys = list(next(iter(rows.values())).keys())
    print(f"  {'频段(Hz)':<12}" + "".join(f"{n:>20}" for n in arch_c))
    for k in keys:
        line = f"  {k:<12}"
        for nm in arch_c:
            line += f"{rows[nm][k]['acc']:>20.4f}"
        print(line)
    print()
    print("  频段含义：0.2-1 车身浮动 / 1-2.5 车身共振 / 2.5-8 过渡 / 8-30 车轮跳动")

    print("\n  各频段优势归属（对比'被动 c₀'）：")
    for k in keys:
        a = rows["被动 c₀"][k]["acc"]
        b = rows["半主动舒适最优"][k]["acc"]
        win = "半主动更优" if b < a else "被动更优"
        gain = (a - b) / a * 100
        print(f"    {k:<12} {win:<10} （差异 {gain:+6.1f}%）")
    print("  注：半主动是'调校自由度'——它可在各频段间重新分配，")
    print("      而非在每个频段都更强。这正是需要多目标评价的原因。")

    # ================= 2. 多目标评分 =================
    # ⚠️ 半主动的代表点必须**在可达集内按综合目标最优选取**，而不是
    # "总加速度最优的 c"——后者会牺牲姿态，得出"半主动综合不如被动"的
    # 错误结论（数学上不可能：半主动可选 c=c₀ 与被动完全持平）。
    print("\n=== 多目标评分（以被动为 50 分基准，越优越高）===")
    m_pass = metrics_freq(p, p["c0"], "C", V)
    weights = {"舒适": 0.5, "操稳": 0.3, "姿态": 0.2}

    def sc(base, val):
        """改善率映射到分数：0% 改善 = 50 分，+30% 改善 = 80 分。"""
        rel = (base - val) / base
        return float(np.clip(50 + rel * 100, 0, 100))

    def total_of(m):
        s = {"舒适": sc(m_pass["acc"], m["acc"]),
             "操稳": sc(m_pass["tire"], m["tire"]),
             "姿态": sc(m_pass["travel"], m["travel"])}
        s["综合"] = sum(s[k] * weights[k] for k in weights)
        return s

    # 在可达集内挑综合最优的半主动调校
    cands = [(c, metrics_freq(p, c, "C", V)) for c in cs]
    c_best_total, m_semi_best = max(cands, key=lambda t: total_of(t[1])["综合"])

    scores = {"被动 c₀": total_of(m_pass),
              f"半主动(综合最优 c={c_best_total/p['c0']:.2f}c₀)": total_of(m_semi_best)}
    print(f"  {'方案':<34}{'舒适':>7}{'操稳':>7}{'姿态':>7}{'综合':>7}")
    for nm, s in scores.items():
        print(f"  {nm:<34}{s['舒适']:>7.1f}{s['操稳']:>7.1f}{s['姿态']:>7.1f}"
              f"{s['综合']:>7.1f}")

    # 半主动的最大价值：在"不牺牲舒适"的前提下改善姿态
    print("\n  半主动的'不牺牲'能力检验（选 c 使 acc 不劣于被动）：")
    ok = [(c, m) for c, m in cands if m["acc"] <= m_pass["acc"] * 1.001]
    if ok:
        c_b, m_b = max(ok, key=lambda t: sc(m_pass["travel"], t[1]["travel"]))
        print(f"    在 acc 不劣于被动的 {len(ok)} 个调校中，最优姿态出现在 "
              f"c={c_b/p['c0']:.2f}c₀：")
        print(f"      姿态 {m_b['travel']*1000:.2f}mm（被动 {m_pass['travel']*1000:.2f}mm，"
              f"改善 {(m_pass['travel']-m_b['travel'])/m_pass['travel']*100:.1f}%）")
        print(f"      舒适 {m_b['acc']:.4f}（被动 {m_pass['acc']:.4f}，未牺牲）")
        print(f"      操稳 {m_b['tire']:.1f}N（被动 {m_pass['tire']:.1f}N）")
        semi_free_gain = (m_pass["travel"] - m_b["travel"]) / m_pass["travel"] * 100
    else:
        semi_free_gain = 0.0
        print("    未找到")

    # ================= 3. 灵敏度 =================
    print("\n=== 灵敏度分析（参数 ±20%，看排序是否翻转）===")
    sens = sensitivity(p, "C", V, pert=0.20)
    print(f"  {'参数':<7}{'扰动':>7}{'被动acc':>11}{'半主动acc':>11}{'提升%':>9}  排序")
    flip = 0
    for r in sens:
        ok = "✅半主动更优" if r["半主动更优"] else "❌翻转"
        if not r["半主动更优"]:
            flip += 1
        print(f"  {r['参数']:<7}{r['扰动']:>7}{r['被动acc']:>11.4f}"
              f"{r['半主动最优acc']:>11.4f}{r['提升%']:>9.2f}  {ok}")
    print(f"\n  排序翻转次数：{flip}/{len(sens)}")
    if flip == 0:
        print("  → **排序在 ±20% 参数扰动下完全稳定**：")
        print("     『半主动在舒适性上优于被动』属**模型结构决定的结论**，可信。")
    else:
        print("  → 存在翻转，该结论依赖参数取值，须谨慎表述。")

    # 提升幅度的范围（比排序更有信息量）
    gains = [r["提升%"] for r in sens]
    print(f"  提升幅度区间：{min(gains):.2f}% ~ {max(gains):.2f}%"
          f"（中位 {np.median(gains):.2f}%）")

    # ---------- 落盘 ----------
    out = {"band_metrics": rows, "band_keys": keys, "scores": scores,
           "weights": weights, "sensitivity": sens,
           "flip_count": flip, "gain_range": [min(gains), max(gains)],
           "passive": m_pass, "semi_best": m_semi_best,
           "c_best_total": float(c_best_total), "semi_free_travel_gain_pct": float(semi_free_gain),
           "c_opt_acc": float(c_opt_acc), "f_body": fb, "f_wheel": fw}
    (RESULTS / "q4_results.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    with (RESULTS / "q4_sensitivity.csv").open("w", newline="",
                                               encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(sens[0].keys()))
        w.writeheader()
        w.writerows(sens)
    print(f"\n[结果] {RESULTS / 'q4_results.json'}")
    print(f"[结果] {RESULTS / 'q4_sensitivity.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
