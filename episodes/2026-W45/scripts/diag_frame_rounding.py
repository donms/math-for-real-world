#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""诊断：`render_video.py` 的**逐屏取帧**为什么会累积丢失约 0.9 秒。

## 现象（W45 实测）

```
清单累计      562.610s
mp4 音频流    562.610s   ← 与清单一致
mp4 视频流    561.700s   ← 少 0.910s
```

22 屏、30 fps、9.4 分钟 ⇒ 累计超前实测 0.80s（线性增长）。

## 假设

`render_video.py` 用 `-loop 1 -t {dur:.3f} -i {img}` 逐屏生成视频，
再用 `concat` 拼接。若每屏实际产出的**帧数**是
$\lfloor dur_i \times fps\rfloor$，则总帧数
$\sum\lfloor dur_i\cdot fps\rfloor$ 会**小于**
$\lfloor(\sum dur_i)\cdot fps\rfloor$，误差上限 $n/fps$。

22 屏 ÷ 30 fps = **0.73s** —— 与实测 0.91s 同量级。

## 本脚本做什么

对几种候选写法各渲一小段，**数实际帧数**，找出"帧数 = round(dur×fps)"的写法。

用法：
    $PY diag_frame_rounding.py
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TMP = REPO / ".workbuddy" / "tmp" / "framediag"
FPS = 30
# 取本期真实的前 6 屏时长（含小数，能暴露取整问题）
DURS = [49.28, 18.16, 20.23, 30.29, 58.12, 2.89]


def make_img(p: Path, w: int = 320, h: int = 180) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", f"color=c=0x1F3B63:s={w}x{h}:d=1",
                    "-frames:v", "1", str(p)], check=True)


def frames_of(p: Path) -> int:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-count_frames", "-show_entries",
                        "stream=nb_read_frames", "-of", "json", str(p)],
                       capture_output=True, text=True)
    try:
        return int(json.loads(r.stdout)["streams"][0]["nb_read_frames"])
    except Exception:                                            # noqa: BLE001
        return -1


def dur_of(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "json", str(p)],
                       capture_output=True, text=True)
    try:
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:                                            # noqa: BLE001
        return -1.0


def variant(name: str, img_args, vf_extra: str = "") -> None:
    """img_args(dur) -> 该屏的输入参数列表。"""
    out = TMP / f"{name}.mp4"
    cmd = ["ffmpeg", "-y", "-v", "error"]
    n = len(DURS)
    for i, dur in enumerate(DURS):
        cmd += img_args(dur, i)
    parts = []
    for i in range(n):
        parts.append(f"[{i}:v]scale=320:180,setsar=1,fps={FPS}"
                     + (f",{vf_extra}" if vf_extra else "") + f",format=yuv420p[v{i}]")
    # ⚠️ filter_complex 各段之间必须用 `;` 分隔，包括 concat 那一段
    #    （漏了会报 `Invalid argument`，实测踩过）。
    cmd += ["-filter_complex",
            ";".join(parts) + ";"
            + "".join(f"[v{i}]" for i in range(n))
            + f"concat=n={n}:v=1:a=0[vout]",
            "-map", "[vout]", "-r", str(FPS), str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"    [!] {name} 失败: {r.stderr.strip()[-200:]}")
        return
    tot = sum(DURS)
    f = frames_of(out)
    d = dur_of(out)
    exp = round(tot * FPS)
    print(f"  {name:<22} 帧 {f:>6}  时长 {d:>8.3f}s  "
          f"（期望帧 {exp}，清单时长 {tot:.3f}s）  差 {f-exp:+d} 帧 / "
          f"{d-tot:+.3f}s")


def main() -> int:
    TMP.mkdir(parents=True, exist_ok=True)
    img = TMP / "card.png"
    make_img(img)
    print("=" * 92)
    print(f"  逐屏取帧诊断（{len(DURS)} 屏 / {FPS} fps / 清单合计 "
          f"{sum(DURS):.3f}s）")
    print("=" * 92)
    print(f"  期望帧数 = round({sum(DURS):.3f} × {FPS}) = "
          f"{round(sum(DURS)*FPS)}\n")

    # ① 现状：-loop 1 -t dur
    variant("A 现状 -loop1 -t",
            lambda dur, i: ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(img)])

    # ② 加 -r fps（输入按帧率解释，t 按帧对齐）
    variant("B 加输入 -r fps",
            lambda dur, i: ["-loop", "1", "-t", f"{dur:.3f}",
                            "-r", str(FPS), "-i", str(img)])

    # ③ 帧数精确：-frames:v N（放在 -i **之前**，作为该输入的 output 选项）
    #    ⚠️ `-frames:v` 是**输出**选项；要限制某个输入的产出帧数，
    #       必须写在 `-i` 之前（实测写在后面会报 "Move this option before
    #       the file it belongs to"）。
    cum = 0.0
    counts = []
    for dur in DURS:
        prev = round(cum * FPS)
        cum += dur
        counts.append(round(cum * FPS) - prev)

    def by_frames(dur, i):
        return ["-loop", "1", "-frames:v", str(counts[i]), "-i", str(img)]

    variant("C -frames:v N", by_frames)

    print(f"\n  ── 方案 C 的逐屏帧数（累积取整的差分）──")
    print(f"     {counts}  合计 {sum(counts)}")
    print(f"     （逐屏 floor 会是 "
          f"{[int(d*FPS) for d in DURS]}，合计 {sum(int(d*FPS) for d in DURS)}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
