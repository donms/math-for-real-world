"""Q1：口径代数 —— 把每个标称算力做因式分解。

核心检验
--------
业界共识的倍率只有两种：
    稀疏（2:4）        ×2
    精度每降一档       ×2   （INT8 → FP8/INT4 → FP4）
以及多芯片           ×N

所以任何标称数 ÷ 基准数，**必须能写成 2 的幂**。
拆不成 2 的幂 ⇒ 中间混进了不属于"技术倍率"的东西。

输出
----
    results/q1_algebra.json
    results/q1_口径表.md
"""
from __future__ import annotations

import json
import math
from pathlib import Path

EP = Path(__file__).resolve().parents[1]
RES = EP / "results"
RES.mkdir(parents=True, exist_ok=True)

# 每条都带来源等级：① 公开报道 ② 官方规格 ③ 发布会口径（无第三方复现）
SPECS = [
    dict(model="NVIDIA Orin-X", base=127, base_prec="INT8", claimed=254, claim_prec="INT8",
         chips=1, sparse=True, src="①余凯微博/IT之家：稠密 127 → 标称 254", level="①"),
    dict(model="NVIDIA Thor", base=1000, base_prec="INT8", claimed=2000, claim_prec="FP4",
         chips=1, sparse=False, src="①华勤方案页/GTC2026：1000 INT8 TOPS、2000 FP4 FLOPS", level="①"),
    # ★ 2026-11-02 查证修正：1960 **不是地平线的宣称**，是余凯的反讽示例
    #   （网友问"能不能做几千 TOPS"，他答"口径一起放大，1960 也行，芯片没变"）。
    #   560 才是官方数（= 稠密 ×2 稀疏，故稠密 = 280）。
    dict(model="地平线 征程 6P（560）", base=280, base_prec="INT8 稠密", claimed=560,
         claim_prec="INT8 稀疏", chips=1, sparse=True,
         src="②地平线官网 560 TOPS + 百科「等效 1/2 稀疏」⇒ 稠密 280", level="②"),
    dict(model="「等效算力」1960（行业口径示例）", base=280, base_prec="INT8 稠密",
         claimed=1960, claim_prec="任意", chips=1, sparse=True, hypothetical=True,
         src="①余凯微博反讽：口径一起放大即可 560→1960，芯片没变", level="①"),
    dict(model="Mobileye EyeQ6 High", base=34, base_prec="INT8", claimed=34, claim_prec="INT8",
         chips=1, sparse=False, src="②Mobileye 官方：34 DL TOPS (INT8)", level="②"),
    dict(model="Tesla AI4（HW4）", base=300, base_prec="INT8", claimed=500, claim_prec="?",
         chips=2, sparse=False, src="①多家二手：300–500 TOPS，口径不明", level="③",
         explicit=False),
    dict(model="NVIDIA NVL144（数据中心对照）", base=1.2e15, base_prec="FP8",
         claimed=3.5e15, claim_prec="FP4", chips=144, sparse=False,
         src="①NVIDIA/媒体：FP8 1.2 EFLOPS、NVFP4 3.5 EFLOPS（是否含稀疏未说明）",
         level="①", explicit=False),
]


def fmt(v: float) -> str:
    if v >= 1e15:
        return f"{v/1e15:.2f} EF"
    if v >= 1000:
        return f"{v:,.0f}"
    return f"{v:.0f}"


def nearest_pow2(x: float) -> tuple[int, float]:
    """最接近的 2 的幂指数，以及残差比（claimed / 2^k）。"""
    if x <= 0:
        return 0, 1.0
    k = round(math.log2(x))
    return k, x / (2 ** k)


def main() -> int:
    rows, flags = [], []
    for s in SPECS:
        ratio = s["claimed"] / s["base"]
        k, resid = nearest_pow2(ratio)
        is_pow2 = abs(math.log2(ratio) - round(math.log2(ratio))) < 1e-6
        rows.append({
            "model": s["model"], "base": s["base"], "base_prec": s["base_prec"],
            "claimed": s["claimed"], "claim_prec": s["claim_prec"],
            "chips": s["chips"], "sparse": s["sparse"],
            "ratio": round(ratio, 4),
            "log2": round(math.log2(ratio), 4),
            "nearest_pow2": 2 ** k,
            "residual": round(resid, 4),
            "is_pow2": is_pow2,
            "source": s["src"], "level": s["level"],
            "explicit": s.get("explicit", True),
            "hypothetical": s.get("hypothetical", False),
        })
        if s.get("hypothetical"):
            pass
        elif not is_pow2 and s.get("explicit", True):
            flags.append((s["model"], ratio, resid))

    out = {"specs": rows, "non_pow2": [
        {"model": m, "ratio": round(r, 4), "residual": round(res, 4)} for m, r, res in flags]}
    (RES / "q1_algebra.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                        encoding="utf-8")

    # ---- 表
    lines = ["# W60 · 口径代数对账表", "",
             "> 判据：**标称 ÷ 基准 必须是 2 的幂**（稀疏 ×2、精度每档 ×2、芯片 ×N）。",
             "> 拆不成 2 的幂 ⇒ 中间混进了不属于技术倍率的东西。", "",
             "| 型号 | 基准 | 标称 | 倍数 | log₂ | 最近的 2 的幂 | 残差 | 判定 |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["hypothetical"]:
            verdict = "※ 反讽示例，非产品宣称"
        elif not r["explicit"]:
            verdict = "— 口径不明，不判定"
        elif r["is_pow2"]:
            verdict = "✅ 干净"
        else:
            verdict = f"❌ 残差 **{r['residual']}×**"
        lines.append(f"| {r['model']} | {fmt(r['base'])} {r['base_prec']} "
                     f"| {fmt(r['claimed'])} {r['claim_prec']} | ×{r['ratio']} "
                     f"| {r['log2']} | ×{r['nearest_pow2']} | {r['residual']}× | {verdict} |")
    lines += ["", "## 拆不开的", ""]
    for m, ratio, res in flags:
        lines.append(f"- **{m}**：×{ratio:.2f}（log₂ = {math.log2(ratio):.3f}），"
                     f"最接近 ×{2**round(math.log2(ratio))}，多出 **{res:.3f}×**")
    (RES / "q1_口径表.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- 可辩护上限：稠密 × 稀疏(2) × INT4(2) = ×4
    dense = 280.0
    doc_ceiling = dense * 4
    lines += ["", "## 征程 6P 的可辩护上限", "",
              f"- 若稠密 INT8 为 **{dense:.0f} TOPS**（560 ÷ 2 稀疏）：",
              f"  - 稀疏 ×2 → **560**（厂商的「NV 算力」）",
              f"  - 再乘 INT4 ×2 → **{doc_ceiling:.0f}**（业界口径能辩护的上限）",
              f"  - 余凯反讽口径的 **1960** = 稠密 ×{1960/dense:.1f}，比可辩护上限高 **{(1960/doc_ceiling-1)*100:.0f}%**",
              "  - ⚠️ 这个 1960 **不是地平线的宣称**，是他用来讽刺行业的示例数",
              f"- 多出来的 ×{1960/doc_ceiling:.2f} 不属于任何已公开的 2× 倍率"]
    (RES / "q1_口径表.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines[5:]))
    print(f"\n[落盘] {RES / 'q1_algebra.json'} / {RES / 'q1_口径表.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
