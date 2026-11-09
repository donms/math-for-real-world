"""重渲两条竖屏并把 3D 镜头重新嵌回去（W59）。

为什么要整条重渲：大字自动缩字号的修复在 stage.html 里，
影响的是**渲染期**的排版，已成片的帧改不了。

用法
----
    python rebuild_vertical.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

EP = Path(r".\episodes\2026-W59")
MOTION = Path(r"<LOCAL_PATH>")
OUT = MOTION / "out"
CLIP = Path(r"<LOCAL_PATH>")
PY = sys.executable
VID = EP / "publish" / "视频"

# variant, 3D 起点秒, 3D 目标时长
JOBS = [("douyin", 51.02, 12.02), ("xhs", 153.94, 11.49)]


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    for variant, t0, d in JOBS:
        html = OUT / f"w59_{variant}.html"
        run([PY, str(MOTION / "build_scenes.py"), "--ep", "2026-W59",
             "--variant", variant, "--portrait", "--no-img", "--out", str(html)])
        silent = OUT / f"w59_{variant}_motion.mp4"
        run([PY, str(MOTION / "render_html.py"), "--html", str(html), "--out", str(silent)])
        voiced = OUT / f"w59_{variant}_voiced.mp4"
        run([PY, str(MOTION / "mux_audio.py"), "--ep", str(EP), "--variant", variant,
             "--video", str(silent), "--out", str(voiced)])

        total = json.loads((EP / "publish" / f"video_manifest_{variant}.json")
                           .read_text(encoding="utf-8"))
        dur_all = sum(s["dur"] for s in total["scenes"])
        final = OUT / f"w59_{variant}_final.mp4"
        t1 = t0 + d
        vf = (f"[0:v]trim=0:{t0:.2f},setpts=PTS-STARTPTS[v1];"
              f"[1:v]setpts=PTS-STARTPTS,setpts=PTS*{d:.2f}/12.0,scale=1080:1920[v2];"
              f"[0:v]trim={t1:.2f},setpts=PTS-STARTPTS[v3];"
              f"[v1][v2][v3]concat=n=3:v=1:a=0[v]")
        run(["ffmpeg", "-y", "-i", str(voiced), "-i", str(CLIP), "-filter_complex", vf,
             "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-crf", "18",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", str(final)])
        subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(final)], check=False)
        VID.mkdir(parents=True, exist_ok=True)
        target = VID / f"2026-W59_{variant}.mp4"
        target.write_bytes(final.read_bytes())
        print(f"[{variant}] {dur_all:.1f}s → {target} {target.stat().st_size/1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
