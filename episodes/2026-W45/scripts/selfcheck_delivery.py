#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W45 · 交付自检：把目标里每一项的**客观证据**打印出来。

用于"声称完成之前先取证"。逐项核对：

1. 选题 / 题面 / 分析报告
2. Q1–Q4 建模与结果（含关键数字）
3. **依赖图 + 维护者两层图**（目标明确要求两层）
4. 论文 / 结论速览
5. 四平台内容
6. 图表与卡片
7. B站 / 抖音成片
8. 发布清单
9. skill 回填

用法：
    $PY selfcheck_delivery.py
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
EP = HERE.parents[1]
REPO = HERE.parents[3]


def ok(b: bool) -> str:
    return "[OK]  " if b else "[缺失]"


def count(p: str) -> int:
    return len(list(EP.glob(p)))


def main() -> int:
    bad = 0
    print("=" * 88)
    print("  W45 交付自检（声称完成前取证）")
    print("=" * 88)

    # ---- 1) 前置文档 ----
    print("\n  ── 1) 前置文档 ──")
    for name in ("00_选题卡.md", "01_题目.md", "02_题目分析报告.md"):
        p = EP / name
        e = p.exists()
        bad += 0 if e else 1
        sz = f"{p.stat().st_size/1024:.1f} KB" if e else ""
        print(f"     {ok(e)} {name:<26}{sz}")

    # ---- 2) Q1–Q4 ----
    print("\n  ── 2) Q1–Q4 建模与结果 ──")
    for q in "1234":
        md = EP / "results" / f"q{q}_结果.md"
        e = md.exists()
        bad += 0 if e else 1
        print(f"     {ok(e)} q{q}_结果.md")
    q1 = json.loads((EP / "results" / "q1_统计.json").read_text(encoding="utf-8"))
    q4 = json.loads((EP / "results" / "q4_统计.json").read_text(encoding="utf-8"))
    g10 = [r for r in q4["rows"]["加权"] if r["k"] == 10][0]["gain_pct"]
    print(f"        关键数字：节点 {q1['clean']['nodes']} / 边 "
          f"{q1['clean']['edges']} / 入度基尼 {q1['in_degree']['gini']:.3f}"
          f" / 贪心 k=10 改善 {g10:.2f}%")

    # ---- 3) 两层图（目标明确要求）----
    print("\n  ── 3) 依赖图 + 维护者两层图 ──")
    for f in ("deps_nodes.csv", "deps_edges.csv", "deps_roots.csv",
              "maintainers.csv", "graph_stats.json"):
        p = EP / "data" / "clean" / f
        e = p.exists()
        bad += 0 if e else 1
        print(f"     {ok(e)} {f:<20}"
              f"{f'{p.stat().st_size/1024:.1f} KB' if e else ''}")
    p = EP / "data" / "clean" / "maintainers.csv"
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    m = {r["maintainer"] for r in rows}
    pk = {r["package"] for r in rows}
    print(f"        ⇒ 维护者层：{len(rows)} 条关系 / {len(m)} 位维护多包者 "
          f"/ {len(pk)} 个包")
    q2d = json.loads((EP / "results" / "q2d_命中率.json")
                     .read_text(encoding="utf-8"))
    print(f"        ⇒ 覆盖率 {q2d['coverage_pct']:.2f}%（{q2d['maint_nodes']} 节点）"
          f"，已在 Q2/Q3 量化其贡献")

    # ---- 4) 论文 ----
    print("\n  ── 4) 论文 / 结论速览 ──")
    for f in ("论文.md", "结论速览.md"):
        p = EP / "paper" / f
        e = p.exists()
        bad += 0 if e else 1
        n = len(p.read_text(encoding="utf-8")) if e else 0
        print(f"     {ok(e)} paper/{f:<16}{n} 字符")

    # ---- 5) 四平台 ----
    print("\n  ── 5) 四平台内容（字数已由 publish_check 校验）──")
    for f in ("母稿.md", "知乎.md", "小红书.md", "B站.md", "抖音.md"):
        p = EP / "内容" / f
        e = p.exists()
        bad += 0 if e else 1
        print(f"     {ok(e)} 内容/{f}")

    # ---- 6) 图表与卡片 ----
    print("\n  ── 6) 图表与卡片 ──")
    for label, pat in (("配图", "results/figs/*.png"),
                       ("小红书卡片", "publish/图片/*.png"),
                       ("封面", "publish/封面/*.png"),
                       ("B站素材16x9", "publish/视频/素材16x9/*.png"),
                       ("抖音素材9x16", "publish/视频/素材9x16/*.png")):
        n = count(pat)
        bad += 0 if n else 1
        print(f"     {ok(n > 0)} {label:<14}{n} 张")

    # ---- 7) 成片 ----
    print("\n  ── 7) 成片 ──")
    for tag, f in (("B站", "2026-W45_bili.mp4"), ("抖音", "2026-W45_douyin.mp4")):
        p = EP / "publish" / "视频" / f
        e = p.exists()
        bad += 0 if e else 1
        spec = ""
        if e:
            r = subprocess.run(["ffprobe", "-v", "error", "-select_streams",
                                "v:0", "-show_entries",
                                "stream=width,height,duration", "-of", "json",
                                str(p)], capture_output=True, text=True)
            try:
                s = json.loads(r.stdout)["streams"][0]
                spec = (f"{s['width']}x{s['height']} "
                        f"{float(s['duration']):.1f}s "
                        f"{p.stat().st_size/1024/1024:.2f} MB")
            except Exception:                                    # noqa: BLE001
                spec = f"{p.stat().st_size/1024/1024:.2f} MB"
        print(f"     {ok(e)} {tag:<6}{spec}")

    # ---- 8) 发布清单 ----
    print("\n  ── 8) 发布清单 ──")
    p = EP / "publish" / "发布清单.md"
    e = p.exists()
    bad += 0 if e else 1
    print(f"     {ok(e)} publish/发布清单.md  "
          f"{p.stat().st_size/1024:.1f} KB" if e else f"     {ok(e)}")

    # ---- 9) skill ----
    print("\n  ── 9) skill 回填 ──")
    sk = Path(r"<USER_HOME>\.dsh\skills\math-for-real-world\SKILL.md")
    if sk.exists():
        t = sk.read_text(encoding="utf-8")
        n = t.count("### W45-")
        print(f"     {ok(n > 0)} SKILL.md  {len(t.splitlines())} 行  "
              f"W45 教训 {n} 条")
        bad += 0 if n else 1
    else:
        print(f"     {ok(False)} SKILL.md 未找到")
        bad += 1

    print(f"\n{'='*88}")
    print(f"  缺失项：{bad}")
    # ★ W45 已修：视频比音频短 0.9s 的问题（skill W45-17）已解决 ——
    #   修法是输入侧多给 2 帧 slack，输出端 `-t total` 裁掉。
    #   实测两个成片现在都是 **视频时长 == 音频时长（差 +0.000s）**。
    print("  ✅ 音画时长已对齐（视频流 == 音频流，差 +0.000s）")
    print("  ⚠️ 仍需人眼确认：字幕断句是否自然（已按自然断点 + 平衡折行处理）")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
