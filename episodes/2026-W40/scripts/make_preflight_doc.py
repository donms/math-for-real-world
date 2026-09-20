#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""**配音之前**生成人工校对清单 —— 图文是否相符，先看这个再花钱花时间。

## 为什么要这一步

配音（IndexTTS 批量）约 25 分钟、渲染数分钟，**加起来半小时**。
而图文不搭这类问题**只有看到成品才发现** —— 于是「改一屏 → 等半小时 → 又发现问题」
反复循环（W40 就这样改了六轮）。

**本脚本把「图」与「文」在配音之前并排列出来**：
此时发现问题，改 `episode_spec.py` 的标题或 `NO_CUT` 切点，
**只要几秒**，不用重跑任何合成。

## 产出

`publish/_配音前校对.md`：每屏一节，含

* **该屏图片的路径**（可直接打开看）—— 清单里的 `img`
* **该屏要念的话**（配音文本，逐段）
* **预估时长**（按语速折算；此时还没有真音频）
* **该屏的画面文字**（标题 + 要点 + 图注）
* **自动检查**：要点过长 / 段落过短过长 / 术语不一致 / 缺图

## 用法

    $PY make_preflight_doc.py --root episodes\\2026-W40 --variant bili
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SPEED_CPS = 6.7          # 实测语速（IndexTTS, duration_factor=0.72）


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--variant", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--shortform", action="store_true",
                    help="短视频平台（抖音等）：不做「段落过短/过长」检查。"
                         "短视频每屏几秒、40–60 字本就正常，"
                         "套用长视频阈值会全是误报（实测抖音 7 屏全被误报）")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    pub = root / "publish"
    man = json.loads((pub / f"video_manifest_{args.variant}.json")
                     .read_text(encoding="utf-8"))
    scenes = man["scenes"]

    # 画面清单（可能有、也可能没有 —— 有就一起列出来对照）
    spec_name = ("slides16x9.json" if args.variant == "bili"
                 else f"cards_{args.variant}.json")
    spec_p = pub / spec_name
    slides = []
    if spec_p.exists():
        sp = json.loads(spec_p.read_text(encoding="utf-8"))
        slides = sp.get("slides") or sp.get("cards") or []

    lines: list[str] = []
    add = lines.append
    total_chars = sum(len(s.get("text", "").replace("\n", "")) for s in scenes)
    est_total = total_chars / SPEED_CPS

    add(f"# 配音前校对 · {man.get('week','')} · {args.variant}")
    add("")
    add(f"> 共 **{len(scenes)} 屏**，预计 **{est_total/60:.1f} 分钟**"
        f"（{total_chars} 字 ÷ {SPEED_CPS} 字/秒）。")
    add(">")
    add("> **这一步是为了省时间**：配音约 25 分钟、渲染数分钟，")
    add("> 而图文不搭只有看到成品才发现。请在**配音之前**核对下表的")
    add("> 「这一屏的图」与「这一屏念的话」是否讲同一件事。")
    add(">")
    add("> 发现问题改 `scripts/episode_spec.py` 的 `TITLES`/`FIGS`，")
    add("> 或改 `scripts/calibrate_segments.py` 的 `NO_CUT` 切点 —— **都是秒级**。")
    add("")
    add("**怎么读**：每屏先看图（打开 `publish/视频/素材16x9/xxx.png`），")
    add("再看「念的话」。**图上的标题与要点**是否就是这段话在说的？")
    add("")
    add("---")
    add("")

    warns: list[str] = []
    cum = 0.0
    for i, sc in enumerate(scenes, 1):
        text = (sc.get("text") or "").strip()
        chars = len(text.replace("\n", ""))
        dur = chars / SPEED_CPS
        t0, t1 = cum, cum + dur
        cum += dur

        img = sc.get("img", "")
        img_p = root / img
        sl = slides[i - 1] if i - 1 < len(slides) else {}
        head = sl.get("head") or sl.get("title") or "(画面无标题)"

        add(f"## 第 {i} 屏　{t0:.0f}s – {t1:.0f}s　（{chars} 字，约 {dur:.0f} 秒）")
        add("")
        add(f"**画面文件**：`{img}`"
            + ("" if img_p.exists() else "　⚠️ **文件不存在**"))
        add("")
        # 直接把图嵌进来（相对本文件的路径），省得来回开文件。
        # 本文件落在 `publish/` 下，而清单里 img 写的是
        # `publish/视频/素材16x9/xxx.png`（相对**期目录**），
        # 所以这里去掉开头的 `publish/` 才是相对本文件的正确路径。
        if img_p.exists():
            rel = str(img)
            if rel.startswith("publish/"):
                rel = rel[len("publish/"):]
            add(f"![第{i}屏]({rel})")
            add("")
        add(f"**画面标题**：{head}")
        add("")
        body = sl.get("lines") or sl.get("rows") or []
        if sl.get("kind") == "figure":
            add(f"**画面配图**：`{sl.get('img','')}`")
            add("")
            add(f"**图注**：{sl.get('note','')}")
        elif body:
            add("**画面要点**：")
            add("")
            for b in body:
                if isinstance(b, (list, tuple)):
                    b = "　".join(str(x) for x in b if x)
                add(f"- {b}")
        elif sl.get("sub"):
            add(f"**画面副标题**：{sl.get('sub','')}")
        add("")
        add("<details><summary>这一屏念的话（点开）</summary>")
        add("")
        for para in text.split("\n"):
            add(f"{para}")
            add("")
        add("</details>")
        add("")

        # ---- 自动检查 ----
        if not img_p.exists():
            warns.append(f"第 {i} 屏：图片文件不存在（{img}）")
        bl = [b for b in (sl.get("lines") or []) if isinstance(b, str)]
        for b in bl:
            if len(b) > 34:
                warns.append(f"第 {i} 屏：要点偏长（{len(b)} 字）「{b[:24]}…」")
        if chars < 90 and not args.shortform:
            warns.append(f"第 {i} 屏：这段口播偏短（{chars} 字），画面会一闪而过")
        if chars > 340 and not args.shortform:
            warns.append(f"第 {i} 屏：这段口播偏长（{chars} 字），"
                         f"同一屏停 {dur:.0f} 秒")
        add("---")
        add("")

    add("## 自动检查结果")
    add("")
    if warns:
        add(f"发现 **{len(warns)}** 条需要你留意（不一定都是问题）：")
        add("")
        for w in warns:
            add(f"- {w}")
    else:
        add("✅ 没有发现明显问题（要点长度、段落长度、图片文件均正常）。")
    add("")
    add("> ⚠️ **脚本查不出语义是否相符** —— 那正是需要你人眼判断的部分。")
    add("> 上面的自动检查只覆盖「要点是否过长」「段落是否过短/过长」"
        "「图片文件是否存在」这类机械问题。")

    out = Path(args.out) if args.out else pub / "_配音前校对.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  {len(scenes)} 屏 / {total_chars} 字 / 预计 {est_total/60:.1f} 分钟")
    print(f"  自动检查：{len(warns)} 条")
    print(f"  ✅ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
