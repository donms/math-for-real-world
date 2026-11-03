"""Q3 v2：多芯片扩展（**区分两种并行**）。

★ 修正（2026-11-02 用户质疑后重做）
-------------------------------
原版把**训练的数据并行（全参数 AllReduce）**套到了车载推理上，得出"效率约 0"。
但车载多芯实际是**模型切分 / 功能分工**，芯片之间传的是**激活值**，不是梯度。

两种模式差着好几个数量级，必须分开算：

A. 数据并行（AllReduce 全参数）—— 训练用
     c = (N-1)/N · w·peak / (B·BW)

B. 模型切分（流水线，传激活）—— 车载推理用
     c = H·w·peak·N / (2·P·BW)

其中 H 隐层维度、P 模型参数量、w 每元素字节数。

输出
----
    results/q3_scaling.json
    figs/q3_scaling.png
"""
from __future__ import annotations

import json
from pathlib import Path

EP = Path(__file__).resolve().parents[1]
RES = EP / "results"
FIGS = RES / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

PEAK = 280e12               # ops/s
H, P, W = 1024, 50e6, 2.0   # 隐层、参数量、fp16 字节

LINKS = {
    "车载万兆以太网": 1.25,     # GB/s
    "PCIe 4.0 x16": 32.0,
    "NVLink（数据中心）": 900.0,
}


def eff_dataparallel(n: int, batch: float, bw_gbps: float) -> float:
    c = (n - 1) / n * W * PEAK / (batch * bw_gbps * 1e9)
    return 1.0 / (1.0 + (n - 1) * c)


def eff_pipeline(n: int, bw_gbps: float) -> float:
    """模型切分：每跳传一次激活，计算量按层分。"""
    c = H * W * PEAK * n / (2 * P * bw_gbps * 1e9)
    return 1.0 / (1.0 + c)


def main() -> int:
    out = {"peak_tops": PEAK / 1e12, "hidden": H, "params_m": P / 1e6,
           "dataparallel": {}, "pipeline": {}}

    for name, bw in LINKS.items():
        out["dataparallel"][name] = {
            "bw_gbps": bw,
            "N2_B1": round(eff_dataparallel(2, 1, bw), 6),
            "N8_B4096": round(eff_dataparallel(8, 4096, bw), 4),
        }
        out["pipeline"][name] = {
            "bw_gbps": bw,
            **{f"N{n}": round(eff_pipeline(n, bw), 4) for n in (2, 4, 8)},
        }

    (RES / "q3_scaling.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                         encoding="utf-8")

    print("[A] 数据并行（全参数 AllReduce，训练口径）")
    for name, v in out["dataparallel"].items():
        print(f"   {name:16s} N=2,B=1 → {v['N2_B1']:.2%}   N=8,B=4096 → {v['N8_B4096']:.1%}")
    print("\n[B] 模型切分（传激活，车载推理口径）")
    for name, v in out["pipeline"].items():
        vals = "  ".join(f"N={k[1:]}→{v[k]:.0%}" for k in v if k.startswith("N"))
        print(f"   {name:16s} {vals}")

    plot(out)
    return 0


def plot(out: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import rcParams
    rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    rcParams["axes.unicode_minus"] = False

    colors = {"车载万兆以太网": "#e8604a", "PCIe 4.0 x16": "#deac5c",
              "NVLink（数据中心）": "#569cd6"}
    ns = [1, 2, 4, 8, 16]

    fig, ax = plt.subplots(1, 2, figsize=(13.0, 4.5), dpi=160)
    for name, bw in LINKS.items():
        ax[0].plot(ns, [eff_pipeline(n, bw) for n in ns], "-o", ms=4,
                   color=colors[name], label=name)
    ax[0].set_xlabel("芯片数 N")
    ax[0].set_ylabel("模型切分效率")
    ax[0].set_title("车载推理（传激活）：PCIe 下切分仍可行", fontsize=12)
    ax[0].set_ylim(0, 1.05)
    ax[0].grid(alpha=0.25)
    ax[0].legend(frameon=False, fontsize=9)

    labels = list(LINKS)
    vals = [out["dataparallel"][k]["N2_B1"] for k in labels]
    bars = ax[1].bar(range(len(labels)), [max(v, 1e-6) for v in vals],
                     color=[colors[k] for k in labels], width=0.55)
    ax[1].set_yscale("log")
    ax[1].set_ylim(1e-7, 2e-2)
    for b, v in zip(bars, vals):
        ax[1].text(b.get_x() + b.get_width() / 2, min(max(v, 1e-7) * 2.2, 8e-3),
                   f"{v:.1e}" if v < 0.01 else f"{v:.1%}", ha="center", fontsize=9)
    ax[1].set_xticks(range(len(labels)))
    ax[1].set_xticklabels([k.replace("（数据中心）", "") for k in labels], fontsize=9)
    ax[1].set_ylabel("效率（对数轴）")
    ax[1].set_title("对照：数据并行在车载链路上不可行", fontsize=12)
    ax[1].grid(alpha=0.25, axis="y")

    fig.tight_layout()
    fig.savefig(FIGS / "q3_scaling.png")
    print(f"\n[图] {FIGS / 'q3_scaling.png'}")


if __name__ == "__main__":
    raise SystemExit(main())
