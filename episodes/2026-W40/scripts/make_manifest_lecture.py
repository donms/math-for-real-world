#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""为 W40 教学视频建配音清单（10 节 → 10 屏）。

从 内容/讲稿.md 按「## 第 N 节」切分，生成 video_manifest_lecture.json：
每节一个场景，text 为配音文本（去掉 markdown 标记与括号提示）。

⚠️ W39 的经验：
  · text 里的换行会**原样进入字幕**，故这里按句号切分，
    让字幕自然断行（渲染阶段还会按 max_caption 再切一次）；
  · 字幕折行必须按 \n 先分段再折（render_video.py 已修）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "内容" / "讲稿.md"
OUT = ROOT / "publish" / "video_manifest_lecture.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

# 每节对应哪张素材（先用答辩 PPT 导出的图占位，正式版会换成教学幻灯片）
# 说明：教学幻灯片待做，这里先保证音频管线可跑通
IMG_TMPL = "publish/视频/素材16x9/sec_{n:02d}.png"


def clean(body: str) -> str:
    """把 Markdown 正文清成纯口播文本。"""
    body = re.sub(r"^\s*---\s*$", "", body, flags=re.M)
    body = re.sub(r"^\s*[>#].*$", "", body, flags=re.M)     # 引用/标题行
    body = body.replace("**", "")
    body = re.sub(r"（[^）]*）", "", body)                    # （停顿）这类舞台提示
    body = re.sub(r"^\s*[-*]\s+", "", body, flags=re.M)      # 列表符号
    # 按句号/问号/感叹号断句，每句一行 —— 字幕会照此行断行
    lines = []
    for para in body.split("\n"):
        para = para.strip()
        if not para:
            continue
        for seg in re.split(r"(?<=[。？！])", para):
            seg = seg.strip()
            if seg:
                lines.append(seg)
    return "\n".join(lines)


def main() -> int:
    t = SRC.read_text(encoding="utf-8")
    parts = re.split(r"^##\s*第\s*(\d+)\s*节\s*·?\s*(.*)$", t, flags=re.M)

    scenes = []
    for i in range(1, len(parts), 3):
        n = int(parts[i])
        title = parts[i + 1].strip()
        body = parts[i + 2]
        text = clean(body)
        if not text:
            print(f"  [!] 第 {n} 节文本为空，跳过")
            continue
        scenes.append({
            "img": IMG_TMPL.format(n=n),
            "dur": 0.0,
            "text": text,
            "_sec": n,
            "_page": n,
            "_title": title,
            "captions": [],
            "audio": None,
            "gap_after": 0.25,
        })

    man = {
        "week": "2026-W40",
        "brand": "用数学看世界",
        "fps": 30,
        "w": 1920,
        "h": 1080,
        "bgm": None,
        "sub": {"fontsize": 46, "margin_v": 58, "outline": 3,
                "font": "Microsoft YaHei", "wrap": 20, "max_caption": 60},
        "_note": "W40 教学片：高温与暴雨的联合极值风险。"
                 "配音先走 edge-tts 草稿供审稿，确认后换 IndexTTS 克隆。",
        "scenes": scenes,
        # ⚠️ 必须是 dict 而不是 None —— add_voice.py 会调 man["voice"].update(...)，
        #    写成 None 会抛 AttributeError。
        "voice": {},
    }
    OUT.write_text(json.dumps(man, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    tot = sum(len(s["text"].replace("\n", "")) for s in scenes)
    print(f"  {len(scenes)} 节 → {OUT.name}")
    print(f"  总字数 {tot}")
    for s in scenes:
        print(f"    第{s['_sec']:>2}节  {len(s['text'].replace(chr(10),'')):>4} 字"
              f"  {s['text'].count(chr(10))+1:>3} 行  {s['_title'][:22]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
