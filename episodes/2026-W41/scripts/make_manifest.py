#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""生成某期的视频清单（video_manifest_<variant>.json）—— **通用版，期号参数化**。

## 设计：口播与素材**同源**

```
内容/讲稿.md
   ↓ make_video_spec.py（DP 切段）
publish/segments.json          ← 边界（唯一事实来源）
   ├→ publish/slides16x9.json  ← 画面（同一份边界派生）
   └→ 本脚本                    ← 口播（同一份边界派生）
```

⚠️ **这是 W40 六轮返工换来的架构**：早期幻灯片与口播是两份手工维护的
清单、靠"逐屏对齐"，任何一处改动都会导致整体错位一格。
现在两者都从 `segments.json` 派生，不可能错位。

## 与 W40 版的区别

W40 的 `make_manifest_platforms.py` 把切点（`BOUNDS`）和抖音口播
（`DOUYIN_LINES`）**硬编码在脚本里**，换一期就得改脚本。
本版全部从 `publish/segments.json` 读，**期号只作参数**。

## 用法

    $PY make_manifest.py --ep 2026-W41                # 只做 B站
    $PY make_manifest.py --ep 2026-W41 --with-douyin  # 同时做抖音
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent   # 仓库根
SPEED_CPS = 6.7


def load_sections(md: Path) -> dict[int, list[str]]:
    """讲稿 → {节号: [自然段, …]}，与 make_video_spec.py **保持同一套口径**。

    ⚠️ W40 踩过的坑：两处加载器用了**不同的切法**（一个按句号、
    一个按空行），下标混用导致 `secs[sec][a:b]` 取到**单个汉字**，
    清单只有 129 字（应为 4728）。故此处实现保持一致：
    **按空行切自然段**，不按句号重切。
    """
    t = md.read_text(encoding="utf-8")
    parts = re.split(r"^##\s*第\s*(\d+)\s*节\s*·?\s*(.*)$", t, flags=re.M)
    out: dict[int, list[str]] = {}
    for i in range(1, len(parts), 3):
        n = int(parts[i])
        paras = []
        for raw in re.split(r"\n\s*\n", parts[i + 2]):
            p = raw.strip()
            p = re.sub(r"^---\s*$", "", p, flags=re.M).strip()
            p = p.replace("**", "")
            if p:
                paras.append(p)
        out[n] = paras
    return out


def build_manifest(ep: str, variant: str, scenes: list[dict],
                   w: int, h: int, sub: dict, note: str) -> Path:
    d = ROOT / "episodes" / ep
    man = {"week": ep, "brand": "用数学看世界",
           "fps": 30, "w": w, "h": h, "bgm": None,
           "sub": sub, "_note": note, "scenes": scenes, "voice": {}}
    p = d / "publish" / f"video_manifest_{variant}.json"
    p.write_text(json.dumps(man, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    tot = sum(len(s["text"].replace("\n", "")) for s in scenes)
    print(f"  [{variant}] {len(scenes)} 屏 / {tot} 字 → {p.name}"
          f"（预计 {tot/SPEED_CPS/60:.1f} 分钟）")
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", required=True)
    ap.add_argument("--with-douyin", action="store_true")
    args = ap.parse_args()

    d = ROOT / "episodes" / args.ep
    seg_p = d / "publish" / "segments.json"
    if not seg_p.exists():
        print(f"  [!] 缺 {seg_p} —— 先跑 make_video_spec.py --export")
        return 2
    segs = json.loads(seg_p.read_text(encoding="utf-8"))["segments"]
    secs = load_sections(d / "内容" / "讲稿.md")

    # ---------- B站：16:9 ----------
    slides = sorted((d / "publish" / "视频" / "素材16x9").glob("slide_*.png"))
    if not slides:
        print("  [!] 缺 16:9 素材，先跑 render_slides16x9.py")
        return 2
    if len(segs) != len(slides):
        print(f"  [!] 口播 {len(segs)} 段 ≠ 素材 {len(slides)} 张")
        return 2
    scenes = []
    for r, img in zip(segs, slides):
        a, b = r["paras"]
        scenes.append({
            "img": f"publish/视频/素材16x9/{img.name}",
            "dur": 0.0,
            "text": "\n".join(secs[r["sec"]][a:b]),
            "_page": r["page"],
            "captions": [], "audio": None, "gap_after": 0.15,
        })
    # ⚠️ 自检一：清单里的图片必须**真实存在**。
    #    W40 踩过：版式从 bullets 改成 compare 后文件名跟着变，
    #    只重渲素材、忘重建清单 → 渲染器找不到图就**静默跳过**，
    #    成片里那一屏是纯背景色。
    missing = [s["img"] for s in scenes if not (d / s["img"]).exists()]
    if missing:
        print(f"  [!] 清单里有 {len(missing)} 张图不存在：")
        for m in missing[:5]:
            print(f"      {m}")
        return 2

    # ⚠️ 自检二：素材必须**比画面清单新**。
    #    W41 踩过：改了屏数（15→16）后重跑了清单，
    #    但素材是更早渲的；**文件名相同**（slide_07_bullets.png），
    #    所以内容对不上却看不出来 —— 用户截图才发现第 7 屏图文不符。
    #    判据：素材目录里最旧的文件必须晚于 slides16x9.json。
    spec_p = d / "publish" / "slides16x9.json"
    if spec_p.exists() and slides:
        # 用**最旧**的素材：只要有一张比清单旧，就说明没重渲干净
        # （用最新会永远通过 —— 重渲时总有文件刚被写）
        oldest_asset = min(p.stat().st_mtime for p in slides)
        if oldest_asset < spec_p.stat().st_mtime:
            print("  [!] 素材比画面清单旧 —— 画面可能已改但素材未重渲：")
            print(f"      slides16x9.json 改于 "
                  f"{__import__('datetime').datetime.fromtimestamp(spec_p.stat().st_mtime):%H:%M:%S}")
            print(f"      最旧素材改于     "
                  f"{__import__('datetime').datetime.fromtimestamp(oldest_asset):%H:%M:%S}")
            print("      → 先跑 render_slides16x9.py --ep "
                  f"{args.ep} 重渲素材")
            return 2

    build_manifest(args.ep, "bili", scenes, 1920, 1080,
                   {"fontsize": 46, "margin_v": 58, "outline": 3,
                    "font": "Microsoft YaHei", "wrap": 30,
                    "max_caption": 46, "one_line": True},
                   f"B站 16:9。{len(scenes)} 屏 = segments.json 的 {len(segs)} 段"
                   f"（DP 校准边界）；幻灯片由 make_video_spec.py 从同一份"
                   f"segments.json 派生 —— 口播与素材同源，不会错位。")

    if args.with_douyin:
        print("  [i] 抖音变体需另备 9:16 素材与短口播，本期暂未生成")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
