#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""扫描 epsilon：找出能让 `-t (N/fps + eps)` 恰好产出 **N 帧**的最小值。

## 已知

* 吸附后每屏时长恰为 `N/fps`，算术上 ΣN = 1114 帧；
* 实际渲染只出 **1108 帧** ⇒ ffmpeg 在有理时间基转换时把 `N/30`
  **截成了 `N−1` 帧**（`N/30` 不可精确表示）。
* 试过 `eps=1e-4`（0.003 帧）—— **不够**。

## 本脚本

对若干有代表性的时长，扫 `eps ∈ {0, 1e-5, 1e-4, 1e-3, 2e-3, 5e-3, 1e-2}`，
直接数帧，找出**能拿满 N 帧且不越到 N+1** 的 eps 范围。

用法：
    $PY diag_eps_scan.py
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TMP = REPO / ".workbuddy" / "tmp" / "epsscan"
FPS = 30
# 覆盖"整除 / 不整除 / 二进制不可表示"三类
CASES = [5.0, 6.9, 7.2, 7.866667, 3.566667, 6.6, 49.266667, 18.133333]
EPS = [0.0, 1e-5, 1e-4, 5e-4, 1e-3, 2e-3, 5e-3, 1e-2]


def frames(p: Path) -> int:
    r = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                        "-select_streams", "v:0", "-show_entries",
                        "stream=nb_read_frames", "-of", "json", str(p)],
                       capture_output=True, text=True)
    try:
        return int(json.loads(r.stdout)["streams"][0]["nb_read_frames"])
    except Exception:                                            # noqa: BLE001
        return -1


def main() -> int:
    TMP.mkdir(parents=True, exist_ok=True)
    img = TMP / "c.png"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=0x1F3B63:s=320x180:d=1",
                    "-frames:v", "1", str(img)], check=True)
    print("=" * 84)
    print(f"  epsilon 扫描（{FPS} fps）：单元格 = 实得帧数 − 目标帧数")
    print("=" * 84)
    hdr = "  时长(N/fps)   N  " + "".join(f"{e:>9}" for e in EPS)
    print(hdr)
    for d in CASES:
        n = round(d * FPS)
        row = []
        for e in EPS:
            out = TMP / f"o_{n}_{e}.mp4"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1",
                            "-t", f"{d + e:.8f}", "-i", str(img),
                            "-vf", f"fps={FPS},format=yuv420p",
                            "-r", str(FPS), str(out)],
                           capture_output=True)
            row.append(frames(out) - n)
        star = "  ←"
        print(f"  {d:>12.6f}{n:>5}  " + "".join(f"{v:>+9d}" for v in row) + star)
    print(f"\n  理想：全部为 0（不多不少）。"
          f"若某 eps 使某行为 +1，说明越到了下一帧。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
