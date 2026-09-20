#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""自动校准讲稿的 20 段切点 —— 不再手数自然段。

## 为什么不用手写段落下标

W40 在这一步反复失败：手写 `paras=(a,b)` 依赖我数对讲稿的自然段，
而讲稿一改、或我数错，切点就整体错位，且**错位后很难发现**
（每段都"有内容"，只是主题对不上屏）。

## 做法

1. 把讲稿按 `## 第 N 节` 切节，每节按空行切自然段（不可再分的最小单位）；
2. 目标：**总段数 = 20**，各段字数尽量均衡；
3. 用**动态规划**在自然段边界上切 —— 这是精确解，不是贪心近似：
   代价 = Σ(该段字数 − 目标字数)²，目标字数 = 总字数 / 20。
   自然段不可跨节，且每节至少切 1 段。

输出 `segments.json`，供 `episode_spec.py` 读取。
**标题仍由人写**（机器写不出好标题），但边界由 DP 定，不会因手数而错。

用法：
    $PY scripts/calibrate_segments.py            # 打印切点
    $PY scripts/calibrate_segments.py --export   # 写 segments.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_MD = ROOT / "内容" / "讲稿.md"
OUT = ROOT / "publish" / "segments.json"

# 目标段数由**目标时长**推出，不写死 —— 否则每期都被迫做成固定屏数。
#   实测语速 6.7 字/秒（IndexTTS, duration_factor=0.72）
#   教学视频一屏停留 30–40 秒比较舒服：太短则画面闪，
#   太长则观众盯着同一屏失去注意力。
#   （W40 实测：4728 字 / 6.7 = 706 秒；20 屏 → 35.3 秒/屏。）
SPEED_CPS = 6.7
SEC_PER_PAGE = 35.0


def target_pages(n_chars: int) -> int:
    """按总字数与目标时长算屏数，并夹在 10–30 屏之间。"""
    secs = n_chars / SPEED_CPS
    return max(10, min(30, round(secs / SEC_PER_PAGE)))


# ---------------------------------------------------------------------------
# ⚠️ **语义禁止切点**：某些自然段之间不允许切开。
#
# 为什么必须人工标注：DP 只按**字数均衡**切，不懂叙事 ——
# 它会把「那怎么办？这里就要用到数学里一个很漂亮的定理了。」
# 切在上一段末尾，于是**画面比配音慢半拍**：
# 字幕已经在引出极值理论，屏幕上还是「为什么不能直接看历史最大值」。
# （用户实测发现，2:02 处）
#
# 格式：{节号: [(a, b), …]}，表示第 a 段与第 b 段之间**不能切**（a 与 b 相邻）。
# 一般规律：**引出下一段内容的过渡句，要和它引出的内容在同一段**。
# ---------------------------------------------------------------------------
NO_CUT: dict[int, list[tuple[int, int]]] = {
    # 第 3 节的自然段（13 段）：
    #   [0] 那为什么不干脆看历史最大值呢？
    #   [1] 不行。它有三个问题
    #   [2] 第一，答不了「百年一遇」
    #   [3] 第二，给不出误差
    #   [4] 第三，它会变
    #   [5] 那怎么办？这里就要用到数学里一个很漂亮的定理了。   ← 收尾提问
    #   [6] 极值理论告诉我们：…只有三种形态                    ← 引入 + 定义
    #   [7]–[12] 三种形态/形状参数/定理的价值
    #
    # 段 5、6 是**引出极值理论**的部分，必须与 [7]–[12] 同段（第 5 屏）。
    # 若切在段 7 之前，上一屏（"历史最大值的问题"）就会多含这两句 →
    # 字幕已在引出极值理论，画面还停在上一屏（用户实测 2:02 处）。
    # 故**禁止在段 5、6 之前切**，切点只能落在段 5（即 [(0,5),(5,13)]）。
    3: [(4, 5), (5, 6)],
}


def load_sections() -> dict[int, list[str]]:
    """讲稿 → {节号: [自然段, …]}，只做最小清洗。"""
    t = SCRIPT_MD.read_text(encoding="utf-8")
    parts = re.split(r"^##\s*第\s*(\d+)\s*节\s*·?\s*(.*)$", t, flags=re.M)
    out: dict[int, list[str]] = {}
    for i in range(1, len(parts), 3):
        n = int(parts[i])
        paras = []
        for raw in re.split(r"\n\s*\n", parts[i + 2]):
            p = raw.strip()
            p = re.sub(r"^---\s*$", "", p, flags=re.M).strip()
            p = p.replace("**", "")
            p = re.sub(r"（停顿）", "", p)
            if p:
                paras.append(p)
        out[n] = paras
    return out


def split_section(paras: list[str], k: int,
                  forbid: set[int] | None = None) -> list[tuple[int, int]]:
    r"""把一节的自然段切成 k 段，最小化 Σ(段字数 − 目标)² —— 动态规划精确解。

    `forbid` 是**不允许切开**的位置集合（切点 = 该位置之前断开）。
    例如 `forbid={5}` 表示不能在 paras[5] 之前切。

    ⚠️ 为什么需要 forbid：DP 只按字数均衡，不懂叙事 ——
    它会把引出下一屏的过渡句切在上一屏末尾，导致**画面比配音慢半拍**。
    """
    m = len(paras)
    forbid = forbid or set()
    if k <= 1 or m <= 1:
        return [(0, m)]
    k = min(k, m)
    w = [len(p) for p in paras]
    total = sum(w)
    target = total / k

    INF = float("inf")
    dp = [[INF] * (k + 1) for _ in range(m + 1)]
    prev = [[-1] * (k + 1) for _ in range(m + 1)]
    dp[0][0] = 0.0
    for t in range(1, k + 1):
        for j in range(t, m + 1):
            for i in range(t - 1, j):          # 最后一段是 paras[i:j]
                if dp[i][t - 1] == INF:
                    continue
                if i in forbid:                # 不允许在 paras[i] 之前切
                    continue
                seg = sum(w[i:j])
                cost = dp[i][t - 1] + (seg - target) ** 2
                if cost < dp[j][t]:
                    dp[j][t] = cost
                    prev[j][t] = i
    cuts, j, t = [], m, k
    while t > 0:
        i = prev[j][t]
        if i < 0:
            return [(0, m)]                    # 无可行解：退化为不切
        cuts.append((i, j))
        j, t = i, t - 1
    return list(reversed(cuts))


def allocate(sections: dict[int, list[str]], target: int) -> list[tuple[int, int, int]]:
    r"""决定每节切几段：按自然段数占比分配，再补齐到 target。"""
    ns = sorted(sections)
    counts = {n: len(sections[n]) for n in ns}
    total_paras = sum(counts.values())
    # 初始按自然段数占比分配（每节至少 1 段）
    alloc = {n: max(1, round(counts[n] / total_paras * target)) for n in ns}
    # 收敛到恰好 TARGET_N：不足则给「每段自然段数最多」的节 +1
    while sum(alloc.values()) < target:
        cand = max(ns, key=lambda n: counts[n] / alloc[n])
        alloc[cand] += 1
    while sum(alloc.values()) > target:
        cand = max((n for n in ns if alloc[n] > 1),
                   key=lambda n: alloc[n])
        alloc[cand] -= 1

    out = []
    for n in ns:
        forbid = {b for a, b in NO_CUT.get(n, [])}
        for a, b in split_section(sections[n], alloc[n], forbid):
            out.append((n, a, b))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", action="store_true")
    args = ap.parse_args()

    secs = load_sections()
    total_chars = sum(len(p.replace(chr(10), "")) for n in secs for p in secs[n])
    TARGET_N = target_pages(total_chars)
    print(f"  讲稿 {total_chars} 字 → 目标 {TARGET_N} 屏"
          f"（语速 {SPEED_CPS} 字/秒，每屏 {SEC_PER_PAGE} 秒）\n")
    plan = allocate(secs, TARGET_N)
    print(f"  讲稿 {len(secs)} 节 → {len(plan)} 段\n")
    print("  屏 节 段     字数 | 口播开头")
    print("  " + "-" * 78)
    tot = 0
    rows = []
    for i, (n, a, b) in enumerate(plan, 1):
        text = "\n".join(secs[n][a:b])
        c = len(text.replace("\n", ""))
        tot += c
        rows.append({"page": i, "sec": n, "paras": [a, b], "chars": c})
        print(f"  {i:>2} {n:>2} {a}-{b - 1:<4}{c:>4} | {text.split(chr(10))[0][:40]}")
    print(f"\n  合计 {tot} 字 → 约 {tot/6.7/60:.1f} 分钟")

    if args.export:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(
            {"target": TARGET_N, "total_chars": tot, "segments": rows},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  ✅ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
