"""把横屏动效片段嵌进 B站成片的第 4 屏。

做法与 W59 的 3D 镜头一致：**替换画面，不动音轨**。
    50.59s 之前的画面保留
    50.59–65.59s 换成动效片段（15 秒）
    之后继续用原渲染
前提：那一屏的旁白 ≥ 15 秒（本屏 29.7 秒，够）。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

EP = Path(r".\episodes\2026-W60")
OUT = Path(r"<LOCAL_PATH>")
VID = OUT / "w60_bili_voiced.mp4"
CLIP = OUT / "w60_tree.mp4"
FINAL = OUT / "w60_bili_final.mp4"
DEST = EP / "publish" / "视频" / "2026-W60_bili.mp4"


def main() -> int:
    man = json.loads((EP / "publish" / "video_manifest_bili.json").read_text(encoding="utf-8"))
    t0, dur = 0.0, None
    for s in man["scenes"]:
        if s["layout"] == "clip":
            dur = s["dur"]
            break
        t0 += s["dur"]
    if dur is None:
        print("[!] 分屏表里没有 clip 屏，直接复制")
        DEST.write_bytes(VID.read_bytes())
        return 0

    clip_len = 15.0
    t1 = t0 + clip_len
    print(f"[插入] 第 4 屏 {t0:.2f}s 起，取动效 {clip_len}s（该屏旁白 {dur:.2f}s）")

    vf = (f"[0:v]trim=0:{t0:.2f},setpts=PTS-STARTPTS[v1];"
          f"[1:v]setpts=PTS-STARTPTS,scale=1920:1080[v2];"
          f"[0:v]trim={t1:.2f},setpts=PTS-STARTPTS[v3];"
          f"[v1][v2][v3]concat=n=3:v=1:a=0[v]")
    subprocess.run(["ffmpeg", "-y", "-i", str(VID), "-i", str(CLIP),
                    "-filter_complex", vf, "-map", "[v]", "-map", "0:a",
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "160k", str(FINAL)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_bytes(FINAL.read_bytes())
    print(f"[完成] {DEST}  {DEST.stat().st_size/1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
