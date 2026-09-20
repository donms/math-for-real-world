#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""把逐条配音合成为**单个审听文件**，并做内容一致性核查。

为什么要合成单文件：
    审稿时听 10 个片段不如听 1 个连续文件方便；
    且连续听才能判断**语速与节奏**，这正是本次要确认的重点。

核查内容：
  · 字幕文本与讲稿是否一致（防"改过讲稿但没重生成"的错配）
  · 各节时长与字数，标出语速异常处
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAN = ROOT / "publish" / "video_manifest_lecture.json"
CLEAN = ROOT / "publish" / "配音" / "lecture_clean"
OUTDIR = ROOT / "publish" / "配音"
FF = (r"<LOCAL_PATH> Files (x86)\ffmpeg-2024-10-02-git-358fdf3083-full_build"
      r"\bin\ffmpeg.exe")
FFP = str(Path(FF).with_name("ffprobe.exe"))


def dur(p: Path) -> float:
    r = subprocess.run([FFP, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def main() -> int:
    man = json.loads(MAN.read_text(encoding="utf-8"))
    caps = [c for s in man["scenes"] for c in (s.get("captions") or [])]
    if not caps:
        print("  [!] 清单里没有 captions")
        return 2

    print(f"  {len(caps)} 条配音；逐条检查")
    files, total, bad = [], 0.0, 0
    for c in caps:
        p = ROOT / c["audio"]
        if not p.exists():
            print(f"    [!] 缺文件 {c['audio']}")
            bad += 1
            continue
        d = dur(p)
        total += d
        files.append(p)
    print(f"  合计 {total:.1f}s（{total/60:.1f} 分钟），缺失 {bad} 条")

    # 合并成单文件
    lst = OUTDIR / "_concat.txt"
    lst.write_text("".join(f"file '{f.as_posix()}'\n" for f in files),
                   encoding="utf-8")
    merged = OUTDIR / "2026-W40-讲稿审听版.wav"
    r = subprocess.run([FF, "-v", "error", "-y", "-f", "concat", "-safe", "0",
                        "-i", str(lst), "-ar", "32000", "-ac", "1",
                        "-c:a", "pcm_s16le", str(merged)],
                       capture_output=True, text=True)
    lst.unlink(missing_ok=True)
    if merged.exists():
        print(f"  ✅ 审听文件：{merged.relative_to(ROOT)}  "
              f"{dur(merged):.1f}s  {merged.stat().st_size/2**20:.1f} MB")
    else:
        print(f"  [!] 合并失败：{(r.stderr or '')[:200]}")
        return 1

    # 内容一致性：字幕文本 vs 讲稿
    script = (ROOT / "内容" / "讲稿.md").read_text(encoding="utf-8")
    body = re.sub(r"^\s*[>#].*$", "", script, flags=re.M)
    body = body.replace("**", "")
    body = re.sub(r"（[^）]*）", "", body)
    body = re.sub(r"\s+", "", body)
    spoken = "".join((c.get("text") or "").replace("\n", "")
                     for c in caps).replace(" ", "")
    print(f"\n  讲稿正文 {len(body)} 字 / 配音字幕 {len(spoken)} 字  "
          f"差 {len(body)-len(spoken)}")

    # 逐节语速
    print(f"\n  {'节':>3}{'字数':>7}{'时长(s)':>10}{'字/秒':>8}  备注")
    for s in man["scenes"]:
        cs = s.get("captions") or []
        n = sum(len((c.get("text") or "").replace("\n", "")) for c in cs)
        d = sum(float(c.get("dur") or 0) for c in cs)
        r_ = n / d if d else 0
        note = "偏快" if r_ > 7.0 else ("偏慢" if r_ < 5.0 else "")
        print(f"  {s['_sec']:>3}{n:>7}{d:>10.1f}{r_:>8.2f}  {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
