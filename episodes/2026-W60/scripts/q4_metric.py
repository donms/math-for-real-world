"""Q4：归一化指标 + 「算力说明卡」。

核心主张
--------
一个算力数字要可比，必须同时绑定四件事：**精度 / 稀疏 / 芯片数 / 工作负载**。
缺任何一项，这个数字就只能当营销语，不能当规格。

产出
----
    results/算力说明卡.md      模板 + 以征程 6P 为例的填法
    results/q4_metric.json     同一颗芯片的三种说法
    results/figs/q4_oneslide.png
"""
from __future__ import annotations

import json
from pathlib import Path

EP = Path(__file__).resolve().parents[1]
RES = EP / "results"
FIGS = RES / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

PEAK_DENSE = 280.0        # 稠密 INT8 TOPS（② 反推）
PEAK_SPARSE = 560.0       # 稀疏标称（② 官方）
BW = 102.4                # GB/s（③ 假设）
AI_LEVELS = {"带宽受限（AI=100）": 100, "中等（AI=500）": 500,
             "算力受限（AI=2000）": 2000}


def effective(ai: float) -> float:
    return min(PEAK_DENSE, ai * BW / 1000.0)


def main() -> int:
    eff = {k: round(effective(v), 1) for k, v in AI_LEVELS.items()}

    card = f"""# 算力说明卡（模板 · 以征程 6P 为例）

> 一个算力数字要可比，必须同时给出下面 **八个字段**。缺任何一项，它只能当营销语。

| # | 字段 | 本例填法 | 状态 |
|---|---|---|---|
| 1 | **峰值口径** | 单芯片 | ✅ 已知 |
| 2 | **基准精度** | INT8 稠密 | ✅ 由 560 = 稠密×2 反推 |
| 3 | **MAC 计数约定** | 1 MAC = 2 ops（业界默认） | ⚠️ 未明示 |
| 4 | **稀疏条件** | 支持 2:4；稠密 {PEAK_DENSE:.0f} / 稀疏 {PEAK_SPARSE:.0f} TOPS | ✅ 已知 |
| 5 | **覆盖范围** | BPU 峰值，不含 CPU/GPU/其他加速器 | ⚠️ 未明示 |
| 6 | **等效基准** | ❌ 厂商未给（"等效于哪颗芯片、哪个模型"） | ❌ 缺 |
| 7 | **真实运行** | ❌ 未给（有准确率约束下的 FPS / P99 时延） | ❌ 缺 |
| 8 | **功耗与散热** | 典型约 60 W（③ 媒体报道） | ⚠️ 已知量级 |

**结论**：8 个字段里，**只有 3 个是确定的**。所以"560 TOPS"是一个可核对的**峰值**，
但**不是一个可横向比较的"能力"数字**。

---

## 同一颗芯片，四种说法

| 说法 | 数值 | 含义 |
|---|---|---|
| 稀疏标称 | **560 TOPS** | 官方页面的数字 |
| 稠密峰值 | **280 TOPS** | 扣掉稀疏倍率 |
| 带宽受限下的有效值（AI=100） | **{eff['带宽受限（AI=100）']} TOPS** | 真实模型大概率落在这里 |
| 中等强度下的有效值（AI=500） | **{eff['中等（AI=500）']} TOPS** | 优化得不错才能达到 |

**560 → 280 → 10～51**：差的不只是口径，还有**工作负载**。

---

## 买方该问的五个问题（可直接照抄）

1. 这个数是**稠密还是稀疏**？稀疏倍率是否已经算进去？
2. **什么精度**？INT8 / FP8 / FP4 分别是多少？
3. **单芯片还是多芯片**？如果是多芯，是**功能分工**还是**同一模型的并行**？
4. **在什么模型、什么 batch 下实测**？有准确率约束的 FPS 和 P99 时延是多少？
5. **持续功耗**多少？跑 30 分钟后会不会降频？
"""
    (RES / "算力说明卡.md").write_text(card, encoding="utf-8")

    out = {"peak_sparse": PEAK_SPARSE, "peak_dense": PEAK_DENSE,
           "bw_gbps": BW, "effective_tops": eff,
           "ratio_effective_to_nominal": {k: round(v / PEAK_SPARSE, 4) for k, v in eff.items()}}
    (RES / "q4_metric.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                        encoding="utf-8")

    print(card)
    plot(eff)
    return 0


def plot(eff: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import rcParams
    rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    rcParams["axes.unicode_minus"] = False

    labels = ["稀疏标称\n（官方）", "稠密峰值\n（扣稀疏）", "有效\nAI=2000", "有效\nAI=500", "有效\nAI=100"]
    vals = [560, 280, eff["算力受限（AI=2000）"], eff["中等（AI=500）"], eff["带宽受限（AI=100）"]]
    colors = ["#e8604a", "#deac5c", "#7fb069", "#569cd6", "#8a9bb0"]

    fig, ax = plt.subplots(figsize=(9.6, 4.6), dpi=160)
    bars = ax.bar(labels, vals, color=colors, width=0.6)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 8, f"{v:.0f}", ha="center", fontsize=11)
    ax.set_ylabel("TOPS")
    ax.set_title("同一颗芯片，四种说法（征程 6P）", fontsize=13)
    ax.set_ylim(0, 640)
    ax.grid(alpha=0.25, axis="y")
    ax.annotate("差 56 倍", xy=(4, vals[-1]), xytext=(3.3, 200), fontsize=10, color="#c0392b",
                arrowprops=dict(arrowstyle="->", color="#c0392b"))
    fig.tight_layout()
    fig.savefig(FIGS / "q4_oneslide.png")
    print(f"[图] {FIGS / 'q4_oneslide.png'}")


if __name__ == "__main__":
    raise SystemExit(main())
