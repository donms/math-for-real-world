#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""合成前检查：口播里**不该有阿拉伯数字**（会被 TTS 按基数读错）。

## 为什么需要（W41 真实事故）

讲稿第 1 节写的是「2026 年 9 月 16 日，平陆运河建成通航」——
**阿拉伯数字**。IndexTTS 把它读成「**两千零二十六年**」，
而正确读法是「二零二六年」。

而同一份讲稿的别处写的是「二零二五年实际二点二四亿吨」（汉字），
所以**两类写法混在一份稿子里**，人工很难发现。

根因：口播是为**发音**写的，数字必须写成汉字；
画面是为**阅读**写的，数字用阿拉伯。**两条路径有意分开** ——
但没有任何东西强制这一点。

## 判据

扫 `内容/讲稿.md` 的**节正文**（跳过文件头的说明块），
只查**口播会念到的部分**：
* 出现阿拉伯数字 → **报错**（除非在白名单里，如公式性的 "1.0 元/总吨·次"）
* 同时报告该处属于哪一屏，便于定位

用法：
    $PY check_narration_numbers.py --ep 2026-W41
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(r".")

# 允许保留阿拉伯数字的情况（如确需按数字读的量纲），逐期登记
ALLOW: dict[str, list[str]] = {
    "2026-W41": [],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", default="2026-W41")
    args = ap.parse_args()
    d = ROOT / "episodes" / args.ep
    sys.path.insert(0, str(d / "scripts"))
    from make_video_spec import load_sections

    secs = load_sections(d / "内容" / "讲稿.md")

    # 段 → 屏号（用分屏表）
    page_of: dict[tuple[int, int], int] = {}
    sb = d / "publish" / "分屏表.json"
    if sb.exists():
        for s in json.loads(sb.read_text(encoding="utf-8"))["screens"]:
            a, b = s["paras"]
            for i in range(a, b):
                page_of[(s["sec"], i)] = s["page"]

    allow = ALLOW.get(args.ep, [])
    hits = []
    for n in sorted(secs):
        for i, p in enumerate(secs[n]):
            for m in re.finditer(r"\d[\d.]*", p):
                tok = m.group(0)
                if any(tok == a or tok.startswith(a) for a in allow):
                    continue
                ctx = p[max(0, m.start() - 14):m.end() + 12]
                hits.append({"sec": n, "para": i, "tok": tok,
                             "page": page_of.get((n, i)), "ctx": ctx})

    print(f"  {args.ep}：扫节正文（跳过文件头说明块）")
    if not hits:
        print("  ✅ 口播里没有阿拉伯数字 —— 不会出现"
              "「2026 读成两千零二十六」这类错读")
        return 0

    print(f"\n  ❌ 发现 {len(hits)} 处阿拉伯数字（TTS 会按基数读，很可能读错）：\n")
    print(f"  {'屏':>4} {'节':>3} {'段':>3}  {'数字':<8} 上下文")
    print("  " + "-" * 76)
    for h in hits:
        pg = h["page"] if h["page"] else "—"
        print(f"  {pg:>4} {h['sec']:>3} {h['para']:>3}  {h['tok']:<8} "
              f"…{h['ctx']}…")
    print()
    print("  改法：口播里把数字写成**汉字**（二零二六年、二点二四亿吨…）；")
    print("        画面要点才用阿拉伯数字 —— 两条路径有意分开。")
    if not allow:
        print(f"  （若确需保留，登记到本脚本的 ALLOW['{args.ep}']）")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
