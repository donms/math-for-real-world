#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""精确定位：`-loop 1 -t d -i img` 到底产出几帧，以及怎么拿到**恰好 N 帧**。

## 已知

* 现状（`-t {dur:.3f}` 逐屏）总帧数比期望少约 1 帧/屏；
* W45 实测：清单 562.610s（16878 帧期望）→ 视频只剩 **16851 帧**（少 27 帧）。

## 本脚本

对**单屏**逐一试 5 种写法，直接数帧数，找出能拿到 `round(d*fps)` 的那一种。

用法：
    $PY diag_frame_exact.py
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TMP = REPO / ".workbuddy" / "tmp" / "frameexact"
FPS = 30
# 用本期真实时长，覆盖"整除/不整除"两类
CASES = [49.28, 18.16, 20.23, 2.89, 58.12]


def frames(p: Path) -> int:
    r = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                        "-select_streams", "v:0", "-show_entries",
                        "stream=nb_read_frames", "-of", "json", str(p)],
                       capture_output=True, text=True)
    try:
        return int(json.loads(r.stdout)["streams"][0]["nb_read_frames"])
    except Exception:                                            # noqa: BLE001
        return -1


def run(name: str, d: float, want: int, args: list[str], img: Path) -> None:
    out = TMP / f"{name}_{want}.mp4"
    cmd = (["ffmpeg", "-y", "-v", "error"] + args
           + ["-i", str(img), "-vf", f"fps={FPS},format=yuv420p",
              "-frames:v", str(want), "-r", str(FPS), str(out)])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"    {name:<26} 失败: {r.stderr.strip()[-120:]}")
        return
    got = frames(out)
    print(f"    {name:<26} d={d:<8.4f} 期望 {want:>5}  实得 {got:>5}  "
          f"{'✅' if got == want else '差 ' + str(got - want)}")


def main() -> int:
    TMP.mkdir(parents=True, exist_ok=True)
    img = TMP / "card.png"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=0x1F3B63:s=320x180:d=1",
                    "-frames:v", "1", str(img)], check=True)
    print("=" * 88)
    print(f"  单屏取帧精确性（{FPS} fps）")
    print("=" * 88)

    for d in CASES:
        want = round(d * FPS)
        print(f"\n  ── d = {d}  期望 {want} 帧（d×fps = {d*FPS:.4f}）──")
        run("A -loop1 -t d", d, want,
            ["-loop", "1", "-t", f"{d:.6f}"], img)
        run("B -r fps -loop1 -t d", d, want,
            ["-r", str(FPS), "-loop", "1", "-t", f"{d:.6f}"], img)
        run("C -t (d+半帧)", d, want,
            ["-loop", "1", "-t", f"{d + 0.5/FPS:.6f}"], img)
        run("D -r fps -t (d+半帧)", d, want,
            ["-r", str(FPS), "-loop", "1", "-t", f"{d + 0.5/FPS:.6f}"], img)

    print(f"\n{'='*88}")
    print("  说明：所有写法都额外加了 `-frames:v {want}` 兜底，")
    print("        所以差异只反映**输入侧能否产出足够帧**。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
