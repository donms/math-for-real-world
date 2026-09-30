#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""把成片里**全部含「率」的片段**抽出来拼成一段，供用户复听。

## 为什么单独做这个

W44 用户实测反馈两个多音字问题：
* 年份读成「两千零二十五」（已用 `years_to_cn()` 修）
* 「率」读成 shuài（已用锁定表 `<率|LV4>` 修）

修完必须**逐处复听**。而「率」在 B站 讲稿里有 **9 处**，
散落在 148–529 秒之间 —— 让用户拖着找 9 个位置不现实。
⇒ 本脚本按清单算出每处的时间区间，用 ffmpeg **拼接成一段**，
   用户听一个文件即可核完全部 9 处。

用法：
    $PY extract_lv_clips.py
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
PUB = EP / "publish"
MP4 = PUB / "视频" / "2026-W44_bili.mp4"
OUTDIR = PUB / "试听_率"
OUT = OUTDIR / "成片_含率的全部片段_拼接.wav"

PAD_PRE, PAD_POST = 1.2, 1.2      # 前后各留一点，便于听清上下文
KEY = "率"


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    man = json.loads((PUB / "video_manifest_bili.json")
                     .read_text(encoding="utf-8"))

    # 算出每处「率」的绝对时间区间
    spans: list[tuple[float, float, str]] = []
    t = 0.0
    for i, s in enumerate(man["scenes"], 1):
        for c in s.get("captions") or []:
            txt = c["text"].replace("\n", "")
            if KEY in txt:
                spans.append((max(0.0, t - PAD_PRE), t + c["dur"] + PAD_POST,
                              f"屏{i} {txt[:34]}"))
            t += c["dur"]
        t += 0.25

    print("=" * 90)
    print(f"  抽出含「{KEY}」的片段：共 {len(spans)} 处")
    print("=" * 90)
    for k, (a, b, label) in enumerate(spans, 1):
        print(f"  {k:>2}  {a:>7.1f}s – {b:>7.1f}s   {label}")

    if not spans:
        return 1

    # 构造 filter_complex：逐段 atrim 后 concat
    #  ⚠️ `spans` 是三元组 (start, end, label)，解包要三个变量（实测漏了 label 报
    #     "too many values to unpack"）
    parts = []
    for k, (a, b, _label) in enumerate(spans):
        parts.append(f"[0:a]atrim=start={a:.2f}:end={b:.2f},"
                     f"asetpts=N/SR/TB[a{k}]")
    concat_in = "".join(f"[a{k}]" for k in range(len(spans)))
    filt = ";".join(parts) + f";{concat_in}concat=n={len(spans)}:v=0:a=1[out]"

    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(MP4),
           "-filter_complex", filt, "-map", "[out]", str(OUT)]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
    if r.returncode != 0 or not OUT.exists():
        print(f"  [!] ffmpeg 失败：{r.stderr[:300]}")
        return 2
    print(f"\n  [ok] {OUT}")
    print(f"       {OUT.stat().st_size/1024:.0f} KB　"
          f"（共 {len(spans)} 处，含前后 {PAD_PRE}s 上下文）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
