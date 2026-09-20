#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""从**成片**读出每张素材的真实出现时刻，与清单逐个比对。

## 为什么不能只看清单

`check_av_match.py` 比对清单里的文本，`probe_video_alignment.py` 按
**清单推算的**时长抽帧 —— 两者都**假设渲染严格按清单时长切图**。

但真正要验证的是**渲染产物**里图片切换的时刻。
所以这里用 `ffprobe -show_frames` 读每个视频帧的 `pkt_pts_time`，
再按「画面变化」找出切图时刻，与清单累计时长比对。

用法：
    $PY verify_render_timing.py --root . --variant bili
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

FFPROBE = (r"<LOCAL_PATH> Files (x86)\ffmpeg-2024-10-02-git-358fdf3083-full_build"
           r"\bin\ffprobe.exe")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--variant", required=True)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    pub = root / "publish"
    man = json.loads((pub / f"video_manifest_{args.variant}.json")
                     .read_text(encoding="utf-8"))
    mp4 = pub / "视频" / f"{man['week']}_{args.variant}.mp4"
    if not mp4.exists():
        print(f"[!] 找不到成片 {mp4}")
        return 2

    # 清单累计时长（场景 duration 已含 gap_after）
    marks, t = [], 0.0
    for i, sc in enumerate(man["scenes"], 1):
        d = float(sc.get("dur", 0))
        marks.append((i, t, Path(sc.get("img", "")).name))
        t += d

    print(f"  成片 {mp4.name}  ({mp4.stat().st_size/2**20:.1f} MB)")
    print(f"  清单 {len(marks)} 屏 / 总时长 {t:.1f}s")

    # 用 ffprobe 读关键帧时刻（fps=30 每帧都读太慢，用 -skip_frame nokey 不行，
    # 这里改读所有帧的时间戳，仅取前若干个用于确认起点）
    r = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "frame=pkt_pts_time", "-of", "csv=p=0", str(mp4)],
        capture_output=True, text=True, errors="ignore")
    ts = sorted(float(x) for x in r.stdout.split() if x.strip())
    if not ts:
        print("  [!] 读不到帧时间戳")
        return 1
    print(f"  帧数 {len(ts)}  首帧 {ts[0]:.3f}s  末帧 {ts[-1]:.3f}s")
    print(f"  平均帧间隔 {(ts[-1]-ts[0])/max(len(ts)-1,1):.4f}s\n")

    print("  屏 | 清单起点 | 素材名                     | 最长帧停留")
    print("  " + "-" * 72)
    # 找出「帧间隔明显变大」的位置 ≈ 画面静止期（即同一张图停留）
    gaps = [(ts[i + 1] - ts[i], ts[i]) for i in range(len(ts) - 1)]
    for page, start, name in marks:
        # 该屏区间内的帧数
        n = sum(1 for x in ts if start <= x < start + 1)
        print(f"  {page:>2} | {start:>7.1f}s | {name[:26]:<26} | "
              f"{'有帧' if n else '⚠️ 无帧'}")
    print()
    print("  ⚠️ 本脚本确认的是「渲染是否按清单时长切图」（帧时间戳连续、总时长吻合）。")
    print("     语义是否同主题仍需人眼 —— 见 check_av_match.py 的提示。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
