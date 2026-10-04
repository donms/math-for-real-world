#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""找出能**逐屏拿到恰好 N 帧**的写法（按 render_video.py 的真实结构）。

## 已确认

按真实配置（`-loop 1 -t d -i img` + `fps=30` 滤镜）单屏渲，
**每屏稳定少 1–2 帧**，22 屏合计 **少 27 帧 = 0.900s**
—— 与成片实测的视频/音频时长差**完全吻合**。

根因：`-loop 1` 的 image2 输入按**默认 25 fps** 出帧，再被 `fps=30` 重采样，
边界上必然丢零头。

## 本脚本试 4 种"精确帧数"写法（都利用"输入侧多给，输出侧截断"）

`-frames:v N` 要用**输出选项绑定到该输入**的写法：
`-loop 1 -t d -i img -frames:v N`（`-i` 之后、下一个 `-i` 之前）。

用法：
    $PY diag_frame_fix.py
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TMP = REPO / ".workbuddy" / "tmp" / "framefix"
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


def render(img: Path, n: int, out: Path, mode: str, dur: float) -> bool:
    vf = (f"scale=1920:1080:force_original_aspect_ratio=decrease,"
          f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x1F3B63,setsar=1,"
          f"fps={FPS},format=yuv420p")
    if mode == "A_t":
        args = ["-loop", "1", "-t", f"{dur + 0.5/FPS:.6f}", "-i", str(img)]
    elif mode == "B_frames_after_i":
        args = ["-loop", "1", "-t", f"{dur + 0.5/FPS:.6f}", "-i", str(img),
                "-frames:v", str(n)]
    elif mode == "C_frames_before_i":
        # `-frames:v` 是**输出**选项：要限制某个输入的产出帧数，
        # 必须写在 `-i` **之前**（写在后面会报 "Move this option before
        # the file it belongs to" —— W45 踩过）。
        args = ["-loop", "1", "-frames:v", str(n), "-i", str(img)]
    elif mode == "E_only_frames":
        # ★ 完全不用 `-t`：让 `-loop 1` 无限出帧，用**输入侧帧数上限**截断，
        #   再靠 `fps=30` 滤镜补齐/对齐。数学上应恰好 N 帧。
        args = ["-loop", "1", "-frames:v", str(n), "-i", str(img)]
    elif mode == "F_frames_plus_t":
        # 给**充裕**时长（+2 帧），再用输入侧 `-frames:v N` 截断
        args = ["-loop", "1", "-t", f"{dur + 2.0/FPS:.6f}", "-i", str(img),
                "-frames:v", str(n)]
    else:
        args = ["-r", str(FPS), "-loop", "1", "-t",
                f"{dur + 0.5/FPS:.6f}", "-i", str(img)]
    cmd = ["ffmpeg", "-y", "-v", "error"] + args + ["-vf", vf, "-r", str(FPS),
                                                    str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"      {mode}: 失败 {r.stderr.strip()[-110:]}")
        return False
    return True


def main() -> int:
    TMP.mkdir(parents=True, exist_ok=True)
    img = TMP / "card.png"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=0x1F3B63:s=1920x1080:d=1",
                    "-frames:v", "1", str(img)], check=True)
    man = json.loads((REPO / "episodes" / "2026-W45" / "publish" /
                      "video_manifest_bili.json").read_text(encoding="utf-8"))
    durs = [float(s["dur"]) for s in man["scenes"]]

    cum, prev, wants = 0.0, 0, []
    for d in durs:
        cum += d
        cur = round(cum * FPS)
        wants.append(max(cur - prev, 1))
        prev = cur

    print("=" * 92)
    print(f"  逐屏精确取帧：共 {len(durs)} 屏，目标 {sum(wants)} 帧")
    print("=" * 92)
    for mode in ("A_t", "C_frames_before_i", "E_only_frames", "F_frames_plus_t",
                 "D_r_fps"):
        tot = 0
        ok = True
        for i, (d, n) in enumerate(zip(durs, wants), 1):
            out = TMP / f"{mode}_{i:02d}.mp4"
            if not render(img, n, out, mode, d):
                ok = False
                break
            tot += frames(out)
        if ok:
            print(f"  {mode:<22} 合计 {tot:>6} 帧  目标 {sum(wants)}  "
                  f"差 {tot - sum(wants):+d} 帧  "
                  f"{'✅ 完全一致' if tot == sum(wants) else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
