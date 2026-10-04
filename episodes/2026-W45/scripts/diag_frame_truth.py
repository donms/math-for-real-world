#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""精确复现：按 `render_video.py` 的**真实配置**渲一屏，数实际帧数。

## 已排除的可能

上一轮实验给每种写法都加了 `-frames:v N` 兜底 ⇒ 全部"达标"，
**说明输入侧能产出足够帧**。所以丢帧发生在**别处**。

## 本轮

完全照 `render_video.py` 的写法（不带任何兜底）渲单屏，直接数帧，
定位"写进去的时长"与"吐出来的帧数"的关系。

用法：
    $PY diag_frame_truth.py
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TMP = REPO / ".workbuddy" / "tmp" / "frametruth"
FPS = 30


def frames(p: Path) -> int:
    r = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                        "-select_streams", "v:0", "-show_entries",
                        "stream=nb_read_frames", "-of", "json", str(p)],
                       capture_output=True, text=True)
    try:
        return int(json.loads(r.stdout)["streams"][0]["nb_read_frames"])
    except Exception:                                            # noqa: BLE001
        return -1


def render_one(img: Path, dur: float, out: Path, w=1920, h=1080) -> None:
    """完全照 render_video.py 的单屏写法（无 -frames:v 兜底）。"""
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
          f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x1F3B63,setsar=1,"
          f"fps={FPS},format=yuv420p")
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-loop", "1", "-t", f"{dur:.6f}", "-i", str(img),
           "-vf", vf, "-r", str(FPS), str(out)]
    subprocess.run(cmd, check=True)


def main() -> int:
    TMP.mkdir(parents=True, exist_ok=True)
    img = TMP / "card.png"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=0x1F3B63:s=1920x1080:d=1",
                    "-frames:v", "1", str(img)], check=True)

    # 用本期真实的前若干屏时长（吸附后的值就是 N/fps）
    man = json.loads((REPO / "episodes" / "2026-W45" / "publish" /
                      "video_manifest_bili.json").read_text(encoding="utf-8"))
    durs = [float(s["dur"]) for s in man["scenes"]]
    print("=" * 88)
    print(f"  真实配置下单屏取帧（{FPS} fps，无 -frames:v 兜底）")
    print("=" * 88)

    cum, prev = 0.0, 0
    tot_want = tot_got = 0
    for i, d in enumerate(durs, 1):
        cum += d
        cur = round(cum * FPS)
        want = max(cur - prev, 1)
        prev = cur
        out = TMP / f"s{i:02d}.mp4"
        render_one(img, d, out)
        got = frames(out)
        tot_want += want
        tot_got += got
        flag = "" if got == want else f"  <<< 差 {got - want}"
        if i <= 6 or got != want:
            print(f"  屏{i:>2}  d={d:>9.6f}  期望 {want:>5}  实得 {got:>5}{flag}")
    print(f"\n  合计：期望 {tot_want} 帧，实得 {tot_got} 帧，"
          f"差 {tot_got - tot_want:+d} 帧（{(tot_got-tot_want)/FPS:+.3f}s）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
