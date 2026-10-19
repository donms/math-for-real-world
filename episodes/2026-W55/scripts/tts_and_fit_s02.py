#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · 只重录"屏 02"，并把新音频**逐条**塞回原槽位（A 方案，保帧数）。

## 为什么自己写，不用 `add_voice.py --pages 2 --force`

2026-10-18 实测：`--force` 会先"清理 211 个旧音频文件"——**把其余 15 屏的配音全删了**，
然后自校验把 99 条字幕时长改成 -1.0，清单总时长变成 -48.2 s。
⇒ **局部重跑不能用 `--force`。** 本脚本直接调 `indextts_engine.Engine`，
**只合成屏 02 的 6 段（抖音 4 段）**，其余文件一概不碰。

## A 方案（保帧数）

1. 按 `split_caption` 切出新字幕；
2. 逐条合成，逐条实测时长 `d_i`；
3. `k = 原槽位Σ字幕 / Σd_i`；若 `k` 不在 0.92–1.08 → **停下报告**，不硬塞；
4. **逐条**按同一个 `k` 重采样（`atempo`，保音高），再补齐到 `k·d_i`；
5. 按字幕起点把 6 段摆进一条长 `dur` 的 wav（尾部留 `gap_after` 静音）；
6. 把新字幕（文本 + `k·d_i`）写回 manifest 的**屏 02**，`sc["dur"]` 保持原值。

用法：
    $PY episodes/2026-W55/scripts/tts_and_fit_s02.py --variant bili --dry-run
    $PY episodes/2026-W55/scripts/tts_and_fit_s02.py --variant bili --apply
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

EP = Path(__file__).resolve().parents[1]
ROOT = EP.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(EP / "scripts"))

from render_video import split_caption            # noqa: E402
from split_caption_s02 import TEXT, TEXT_DOUYIN   # noqa: E402

TMP = ROOT / ".workbuddy" / "tmp" / "w55_s02"
FF = shutil.which("ffmpeg")


def wav_dur(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / float(w.getframerate())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, choices=["bili", "douyin"])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--k-min", type=float, default=0.92)
    ap.add_argument("--k-max", type=float, default=1.08)
    ap.add_argument("--duration-factor", type=float, default=0.66,
                    help="语速系数（IndexTTS：1.0 是自然慢速）。★ 必须与全片一致："
                         "原片实测 215 字 / 34.68s = 6.20 字每秒，"
                         "而 df=1.0 只有 4.25 字每秒 ⇒ 原片的 df≈0.685。"
                         "取 0.66 让新稿落进 k 区间，且与其余 15 屏只差约 4% 语速。")
    args = ap.parse_args()

    slot_all = json.loads((EP / "_logs" / "_s02_slot.json").read_text("utf-8"))
    slot = slot_all[args.variant]
    man_p = EP / "publish" / f"video_manifest_{args.variant}.json"
    man = json.loads(man_p.read_text(encoding="utf-8"))
    sc = man["scenes"][1]
    maxcap = int(man.get("sub", {}).get("max_caption", 46))
    text = TEXT if args.variant == "bili" else TEXT_DOUYIN
    caps = split_caption(text, maxcap)

    print("=" * 78)
    print(f"  屏 02 重录 · {args.variant}  槽位 {slot['dur']:.3f}s"
          f"（Σ字幕 {slot['caps_sum']:.3f}s + 留白 {slot['gap_after']:.3f}s）")
    print("=" * 78)
    for i, c in enumerate(caps, 1):
        print(f"  {i:02d} [{len(c):2d}] {c}")
    if args.dry_run:
        print("\n  （--dry-run，不合成）")
        return 0

    work = TMP / args.variant
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    outs = [work / f"raw_{i:02d}.wav" for i in range(1, len(caps) + 1)]

    import indextts_engine as IE
    eng = IE.Engine(duration_factor=args.duration_factor)
    oks = eng.synthesize(caps, outs)
    if not all(oks):
        print(f"[X] 有段落没合成出来：{oks}")
        return 1

    ds = [wav_dur(p) for p in outs]
    S = sum(ds)
    k = slot["caps_sum"] / S
    print(f"\n  逐条实测：{[round(d, 2) for d in ds]}  合计 {S:.3f}s")
    print(f"  ★ k = {slot['caps_sum']:.3f} / {S:.3f} = {k:.4f}"
          f"（允许 {args.k_min} 到 {args.k_max}）")
    if not (args.k_min <= k <= args.k_max):
        print(f"  [X] k={k:.4f} 超出允许区间 ⇒ **不硬塞**。"
              f"稿子{'偏长' if k < 1 else '偏短'}，请改措辞后重来。")
        return 2

    # 逐条重采样到 k·d_i
    fitted: list[Path] = []
    for i, (p, d) in enumerate(zip(outs, ds), 1):
        target = k * d
        q = work / f"fit_{i:02d}.wav"
        # atempo 保音高；再 apad + atrim 把长度**精确**锁到 target
        vf = (f"atempo={k:.6f},apad,atrim=0:{target:.6f},"
              f"asetpts=PTS-STARTPTS")
        r = subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                            "-i", str(p), "-af", vf,
                            "-ar", "22050", "-ac", "1", str(q)],
                           capture_output=True, text=True, errors="ignore")
        if r.returncode != 0 or not q.exists():
            print(f"[X] 第{i}条重采样失败：{r.stderr[-400:]}")
            return 1
        fitted.append(q)
        print(f"   fit {i:02d}: {d:.3f}s → {wav_dur(q):.3f}s（目标 {target:.3f}s）")

    # 摆进一条长 dur 的 wav
    whole = work / "s02_full.wav"
    with wave.open(str(fitted[0])) as w0:
        sr, ch, sw = w0.getframerate(), w0.getnchannels(), w0.getsampwidth()
    import numpy as np
    total = int(round(slot["dur"] * sr))
    buf = np.zeros(total, dtype=np.int16)
    cum = 0.0
    times = []
    for q in fitted:
        with wave.open(str(q)) as w:
            n = w.getnframes()
            data = np.frombuffer(w.readframes(n), dtype=np.int16)
        a = int(round(cum * sr))
        b = min(a + len(data), total)
        buf[a:b] = data[:b - a]
        times.append((cum, cum + len(data) / sr))
        cum += len(data) / sr
    with wave.open(str(whole), "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(sw)
        w.setframerate(sr)
        w.writeframes(buf.tobytes())
    print(f"\n  屏 02 声轨 {whole.name}：{wav_dur(whole):.3f}s"
          f"（槽位 {slot['dur']:.3f}s，尾部静音 "
          f"{slot['dur'] - wav_dur(whole) + 0:.3f}s）")

    if not args.apply:
        print("\n  （未加 --apply：只合成与试算，清单和成片都没动）")
        print(f"  k = {k:.4f}")
        return 0

    # 写回清单（只改屏 02 的字幕与时长）
    new_caps = []
    for c, (a, b) in zip(caps, times):
        new_caps.append({"text": c, "say": c, "audio": None,
                         "dur": round(b - a, 3), "raw_dur": None})
    sc["captions"] = new_caps
    sc["text"] = text
    sc["tts"] = ""
    sc["dur"] = slot["dur"]              # ★ 还原槽位，保帧数
    man_p.write_text(json.dumps(man, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print(f"  [写回] {man_p.name}：屏 02 6 条字幕，Σ="
          f"{sum(c['dur'] for c in new_caps):.3f}s，dur 还原 {slot['dur']}")

    meta = work / "fit_meta.json"
    meta.write_text(json.dumps({"k": k, "durs": [c["dur"] for c in new_caps],
                                "wav": str(whole), "times": times},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  [meta] {meta}   k={k:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
