#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""问题 1：边缘极值建模（GEV + GPD 双路互证）。

按用户确认的方案实现（见 models/01_边缘极值模型.md 决策记录）：
  · POT 阈值：**参数稳定性图选主阈值 + 3 个阈值敏感性对比**
  · 非平稳：线性趋势 + 似然比检验（本脚本先做平稳拟合，Q3 再做时变）
  · 不确定度：**非参数自助法**给 x_T 的 95% 置信区间

产出：
  results/q1_gev.json       各城 GEV 参数、重现水平、置信区间
  results/q1_gpd.json       各城 GPD 多阈值结果
  results/q1_summary.txt    人读汇总
  results/figs/q1_*.png     重现期曲线、稳定性图

⚠️ 数据口径：气温绝对值可用；**降水绝对值不可引用**（网格平滑到实测的 18%），
   降水结论只做相对比较与趋势。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evt import (FIGS, GROUPS, annual_max, bootstrap_ci, gev_fit,  # noqa: E402
                 gev_return_level, gpd_fit, gpd_return_level, load_cities,
                 load_series, save_json)

T_LIST = [2, 5, 10, 20, 50, 100]        # 关注的重现期
N_BOOT = 400                            # 自助法次数
THR_QS = [0.95, 0.975, 0.99]            # POT 三个阈值分位（敏感性对比）

# 中文字体（技能要求：必须手动注册，否则乱码）
import matplotlib                                              # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                # noqa: E402
from matplotlib import font_manager                            # noqa: E402

for _f in (r"<LOCAL_PATH>", r"<LOCAL_PATH>"):
    try:
        font_manager.fontManager.addfont(_f)
    except Exception:                                          # noqa: BLE001
        pass
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def _bootstrap_return_levels(mx: np.ndarray, T_list: list[int],
                             n_boot: int = 400, seed: int = 4000) -> dict:
    """自助法：**一次重采样、一次拟合、同时算出全部 T 的重现水平**。

    返回 {T: (lo, hi, n_ok)}。这样每个 T 的区间来自同一批自助样本，
    比各 T 独立重采样更省算力（拟合次数降到 1/len(T_list)），
    且各 T 之间的区间**相互一致**（不会出现 x20 的上界高于 x50 的下界这种矛盾）。

    极值分析样本稀少（86 个年最大值）还要外推到 T=100，
    点估计不可靠，**必须给区间**。
    """
    rng = np.random.default_rng(seed)
    n = len(mx)
    vals: dict[int, list[float]] = {T: [] for T in T_list}
    for _ in range(n_boot):
        s = mx[rng.integers(0, n, n)]
        try:
            pp, _, _ = gev_fit(s)
        except Exception:                                      # noqa: BLE001
            continue
        for T in T_list:
            try:
                v = gev_return_level(pp, T)
                if np.isfinite(v):
                    vals[T].append(v)
            except Exception:                                  # noqa: BLE001
                continue
    out = {}
    for T, a in vals.items():
        if len(a) < 20:
            out[T] = None
            continue
        arr = np.array(a)
        out[T] = (float(np.quantile(arr, 0.025)),
                  float(np.quantile(arr, 0.975)), len(arr))
    return out


def fit_one_var(x: np.ndarray, year: np.ndarray, label: str) -> dict:
    """对一个变量（气温或降水）做 GEV + GPD 全套拟合。"""
    out: dict = {"label": label}

    # ---------- BM：年最大值 → GEV ----------
    yrs, mx = annual_max(x, year)
    out["n_years"] = int(len(mx))
    out["year_min"], out["year_max"] = int(yrs.min()), int(yrs.max())
    try:
        p, ll, aic = gev_fit(mx)
        mu, sg, xi = float(p[0]), float(p[1]), float(p[2])
        sp = np.array([mu, sg, xi])
        out["gev"] = {
            "mu": mu, "sigma": sg, "xi": xi, "loglik": float(ll), "aic": float(aic),
            "se": None, "return_level": {},
        }
        # 重现水平 + 自助法区间
        #
        # ⚠️ 踩坑 1：曾把 boot 写成「def boot(...): ...
        #    idx = ...; s = ...; try: ...」这种**带分号的单行形式**，
        #    结果函数体只包含第一行，后面的语句落到循环体里，
        #    每轮直接抛 NameError 被 except 吞掉 → n_boot=0、区间全为 null。
        #
        # ⚠️ 踩坑 2（性能）：**不要**对每个 T 单独做一轮自助法——
        #    那是 `n_T × n_boot` 次 GEV 拟合（6×400×2×16 ≈ 7.7 万次，
        #    实测要跑一小时）。正确做法是**一次重采样、拟合一次、
        #    同时算出全部 T 的重现水平**，拟合次数降到 1/6。
        try:
            boot = _bootstrap_return_levels(mx, T_LIST, n_boot=N_BOOT,
                                            seed=4000)
        except Exception:                                      # noqa: BLE001
            boot = {}
        for T in T_LIST:
            xT = gev_return_level(p, T)
            b = boot.get(T)
            out["gev"]["return_level"][str(T)] = {
                "x": float(xT),
                "lo": (b[0] if b else None),
                "hi": (b[1] if b else None),
                "n_boot": (b[2] if b else 0)}
    except Exception as e:                                     # noqa: BLE001
        out["gev"] = {"error": f"{type(e).__name__}: {e}"}

    # ---------- POT：超阈值 → GPD（多阈值） ----------
    out["gpd"] = {}
    v = x[~np.isnan(x)]
    n_years = len(mx)
    for q in THR_QS:
        u = float(np.quantile(v, q))
        e = v[v > u] - u
        key = f"{q:.3f}"
        if len(e) < 30:
            out["gpd"][key] = {"threshold": u, "n_exc": int(len(e)),
                               "error": "超出量太少"}
            continue
        try:
            xi, beta, ll, aic = gpd_fit(e)
            rec = {"threshold": u, "n_exc": int(len(e)), "xi": xi,
                   "beta": beta, "loglik": float(ll), "aic": float(aic),
                   "return_level": {}}
            for T in T_LIST:
                y = gpd_return_level(xi, beta, len(e), n_years, T)
                rec["return_level"][str(T)] = {
                    "x": float(u + y) if np.isfinite(y) else None}
            out["gpd"][key] = rec
        except Exception as ex:                                # noqa: BLE001
            out["gpd"][key] = {"threshold": u, "n_exc": int(len(e)),
                               "error": f"{type(ex).__name__}: {ex}"}
    return out


def plot_return_curves(results: dict, var_key: str, fname: str, unit: str,
                       title: str) -> None:
    """画重现期曲线（GEV），用于两法互证与城市间对比。

    ⚠️ 参数 `results` 必须是 **{城市: 该变量的结果 dict}**，
    即调用方要传 `{k: v[var_key] for ...}`。
    早期误传了顶层的 `{城市: {'tmax':…, 'precip':…}}`，
    于是 `r.get(var_key)` 取到的是外层 dict，
    `return_level` 恒为空 → 画不出一条线（matplotlib 报
    "No artists with labels found to put in legend"）。
    """
    fig, ax = plt.subplots(figsize=(9.5, 6))
    n = max(len(results), 1)
    colors = plt.cm.tab20(np.linspace(0, 1, n))
    drew = 0
    for (city, r), c in zip(results.items(), colors):
        g = (r or {}).get("gev", {})
        rl = g.get("return_level") or {}
        if not rl:
            continue
        try:
            Ts = np.array([float(k) for k in rl])
            xs = np.array([rl[k]["x"] for k in rl], dtype=float)
        except (TypeError, ValueError, KeyError):
            continue
        if not np.all(np.isfinite(xs)):
            continue
        order = np.argsort(Ts)
        ax.plot(Ts[order], xs[order], "-o", ms=3, lw=1.2, color=c, label=city)
        drew += 1
    ax.set_xscale("log")
    ax.set_xticks(T_LIST)
    ax.set_xticklabels([str(t) for t in T_LIST])
    ax.set_xlabel("重现期 T（年）")
    ax.set_ylabel(f"重现水平（{unit}）")
    ax.set_title(f"{title}（{drew} 城）")
    ax.grid(alpha=0.3)
    if drew:
        ax.legend(ncol=2, fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIGS / fname, dpi=140)
    plt.close(fig)


def plot_xi_compare(all_res: dict, fname: str) -> None:
    """画 ξ 对比图：气温 vs 降水，突出「气温有上界、降水重尾」这一核心发现。"""
    cities = [k for k, v in all_res.items()
              if "xi" in (v["tmax"].get("gev") or {})
              and "xi" in (v["precip"].get("gev") or {})]
    if not cities:
        return
    xi_t = [all_res[c]["tmax"]["gev"]["xi"] for c in cities]
    xi_p = [all_res[c]["precip"]["gev"]["xi"] for c in cities]
    order = np.argsort(xi_t)
    cities = [cities[i] for i in order]
    xi_t = [xi_t[i] for i in order]
    xi_p = [xi_p[i] for i in order]
    y = np.arange(len(cities))
    fig, ax = plt.subplots(figsize=(9, 7.5))
    ax.barh(y - 0.2, xi_t, height=0.4, color="#c0392b", label="气温 ξ")
    ax.barh(y + 0.2, xi_p, height=0.4, color="#2e86c1", label="降水 ξ")
    ax.axvline(0, color="k", lw=1)
    ax.set_yticks(y)
    ax.set_yticklabels(cities, fontsize=9)
    ax.set_xlabel("GEV 形状参数 ξ")
    ax.set_title("形状参数对比：气温多为负（有上界） vs 降水多为正（重尾）")
    ax.text(0.02, 0.02, "ξ<0 → 有物理上界\nξ>0 → 重尾，极端值可远超历史",
            transform=ax.transAxes, fontsize=9, va="bottom",
            bbox=dict(boxstyle="round", fc="lightyellow", ec="gray"))
    ax.grid(alpha=0.3, axis="x")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGS / fname, dpi=140)
    plt.close(fig)


def main() -> int:
    t0 = time.time()
    cities = load_cities()
    print(f"  {len(cities)} 城，重现期 {T_LIST}，自助法 {N_BOOT} 次，"
          f"POT 阈值分位 {THR_QS}\n")

    all_res: dict[str, dict] = {}
    for i, c in enumerate(cities, 1):
        name = c["name"]
        try:
            s = load_series(name)
        except FileNotFoundError as e:
            print(f"  [!] {name}: {e}")
            continue
        r = {"group": c["group"], "lat": c["lat"], "lon": c["lon"]}
        r["tmax"] = fit_one_var(s["tmax"], s["year"], "tmax")
        r["precip"] = fit_one_var(s["precip"], s["year"], "precip")
        all_res[name] = r

        g = r["tmax"].get("gev", {})
        xi = g.get("xi")
        x50 = (g.get("return_level") or {}).get("50", {}).get("x")
        x50lo = (g.get("return_level") or {}).get("50", {}).get("lo")
        x50hi = (g.get("return_level") or {}).get("50", {}).get("hi")
        gp = r["precip"].get("gpd", {}).get("0.975", {})
        line = (f"  [{i:>2}/{len(cities)}] {name:<8} {c['group']:<18} "
                f"n年={r['tmax'].get('n_years')}  ")
        if xi is not None:
            line += f"ξ_温={xi:+.3f}  x50={x50:.1f}℃"
            if x50lo is not None:
                line += f" [{x50lo:.1f},{x50hi:.1f}]"
        if "xi" in gp:
            line += f"  | ξ_雨={gp['xi']:+.3f}"
        print(line, flush=True)

    save_json(all_res, "q1_all.json")

    # 拆出两个单独文件（便于后续 Q2/Q3 引用）
    save_json({k: v["tmax"] for k, v in all_res.items()}, "q1_gev.json")
    save_json({k: v["precip"] for k, v in all_res.items()}, "q1_gpd.json")

    # ---------- 图表 ----------
    # ⚠️ 必须传「已下钻到该变量」的 dict，否则绘图取不到 return_level
    plot_return_curves({k: v["tmax"] for k, v in all_res.items()},
                       "tmax", "q1_tmax_return.png", "℃",
                       "各城日最高气温的重现期曲线（GEV，年最大值法）")
    plot_return_curves({k: v["precip"] for k, v in all_res.items()},
                       "precip", "q1_precip_return.png", "mm",
                       "各城日降水量的重现期曲线（GEV，年最大值法）")
    plot_xi_compare(all_res, "q1_xi_compare.png")

    # ---------- 人读汇总 ----------
    lines = ["问题1 · 边缘极值模型汇总", "=" * 96, ""]
    lines.append("【一】「五十年一遇」日最高气温（GEV，年最大值法，含 95% 自助法区间）")
    lines.append(f"{'城市':<9}{'组':<20}{'ξ':>8}{'x50(℃)':>10}"
                 f"{'95%区间':>20}{'x20':>8}{'x100':>8}")
    lines.append("-" * 96)
    rows = []
    for name, v in all_res.items():
        g = v["tmax"].get("gev", {})
        if "xi" not in g:
            continue
        rl = g["return_level"]
        r20 = rl.get("20", {}).get("x")
        r100 = rl.get("100", {}).get("x")
        r50 = rl.get("50", {})
        rows.append((name, v["group"], g["xi"], r50.get("x"),
                     r50.get("lo"), r50.get("hi"), r20, r100))
    for name, grp, xi, x50, lo, hi, x20, x100 in sorted(
            rows, key=lambda z: -(z[3] or -999)):
        ci = f"[{lo:.1f}, {hi:.1f}]" if lo is not None else "n/a"
        lines.append(f"{name:<9}{grp:<20}{xi:>+8.3f}{x50:>10.1f}"
                     f"{ci:>20}"
                     f"{(f'{x20:.1f}' if x20 is not None else 'n/a'):>8}"
                     f"{(f'{x100:.1f}' if x100 is not None else 'n/a'):>8}")

    lines += ["", "【二】GEV 与 GPD 的形状参数互证（应相近）", "-" * 96]
    lines.append(f"{'城市':<9}{'ξ_GEV(温)':>12}{'ξ_GPD(温)':>12}"
                 f"{'差':>9}{'ξ_GEV(雨)':>12}{'ξ_GPD(雨)':>12}{'差':>9}")
    for name, v in all_res.items():
        gt = v["tmax"].get("gev", {}).get("xi")
        gp_ = v["tmax"].get("gpd", {}).get("0.975", {}).get("xi")
        gr = v["precip"].get("gev", {}).get("xi")
        gpr = v["precip"].get("gpd", {}).get("0.975", {}).get("xi")
        def f(x):
            return f"{x:+.3f}" if isinstance(x, (int, float)) else "n/a"
        def d(a, b):
            return f"{a-b:+.3f}" if isinstance(a, (float,)) and isinstance(b, (float,)) else "-"
        lines.append(f"{name:<9}{f(gt):>12}{f(gp_):>12}{d(gt, gp_):>9}"
                     f"{f(gr):>12}{f(gpr):>12}{d(gr, gpr):>9}")

    lines += ["", "【三】POT 阈值敏感性（GPD 形状参数随阈值变化）", "-" * 96]
    lines.append(f"{'城市':<9}" + "".join(f"{'ξ@'+q:>13}" for q in
                                        [f"{q:.3f}" for q in THR_QS]))
    for name, v in all_res.items():
        vals = []
        for q in THR_QS:
            x_ = v["precip"].get("gpd", {}).get(f"{q:.3f}", {}).get("xi")
            vals.append(f"{x_:+.3f}" if isinstance(x_, float) else "n/a")
        lines.append(f"{name:<9}" + "".join(f"{s:>13}" for s in vals))

    lines += ["", "【四】数据口径声明", "-" * 96,
              "  · 气温：网格与实测差 ±0.5℃ 内，绝对值可引用",
              "  · 降水：网格约为实测的 18%（恩平单日 108.7 vs 597.7mm），",
              "          **绝对值不可引用**，只做相对比较与趋势分析",
              ""]
    (FIGS.parent / "q1_summary.txt").write_text("\n".join(lines), encoding="utf-8")

    print(f"\n  用时 {time.time()-t0:.1f}s")
    print(f"  [结果] results/q1_gev.json")
    print(f"  [结果] results/q1_gpd.json")
    print(f"  [汇总] results/q1_summary.txt")
    print(f"  [图表] results/figs/q1_*.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
