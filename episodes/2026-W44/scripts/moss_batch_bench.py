#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""MOSS-TTS-Nano **批量**测速：用 W44 真实全部口播，测端到端总时长。

## 为什么不能按"单句"比

单句调用 = **模型加载 + 合成**。MOSS 单句实测 18.9s / 3.6s 音频，
但这 18.9s 里绝大部分是**模型加载**（一次性开销）。
IndexTTS 同样如此 —— 所以"每句耗时"这个指标对两者都不公平。

⇒ 本脚本把 **W44 讲稿全部 73 条字幕**拼成一个文本文件，
用 `--text-file` 一次喂给 MOSS（它支持长文本自动分块），
测量**端到端总耗时**。这才是与 `add_voice.py` 实际工作方式可比的数字。

用法：
    $PY moss_batch_bench.py
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
MOSS = Path(r"<LOCAL_PATH>")
PY_MOSS = Path(r"python")
REF = ROOT / "media" / "audio" / "ref" / "voice_ref_Don_norm.wav"
OUT = EP / "publish" / "_tmp_moss"
TMP = ROOT / ".workbuddy" / "tmp"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    man = json.loads((EP / "publish" / "video_manifest_bili.json")
                     .read_text(encoding="utf-8"))
    caps = [c["text"].replace("\n", "")
            for s in man["scenes"] for c in (s.get("captions") or [])]
    total_chars = sum(len(c) for c in caps)
    audio_expected = sum(c["dur"] for s in man["scenes"]
                         for c in (s.get("captions") or []))

    txt = OUT / "w44_all_captions.txt"
    txt.write_text("\n".join(caps), encoding="utf-8")

    print("=" * 88)
    print("  MOSS-TTS-Nano 批量测速（W44 全部口播）")
    print("=" * 88)
    print(f"  字幕条数 : {len(caps)}")
    print(f"  总字数   : {total_chars}")
    print(f"  原音频   : {audio_expected:.1f}s（IndexTTS 实测）")
    print(f"  参考音   : {REF.name}")
    print()

    env = dict(os.environ)
    env["HF_ENDPOINT"] = "https://hf-mirror.com"
    env["PYTHONIOENCODING"] = "utf-8"
    # ⚠️ `PYTHONUTF8` 只接受 "1"/"0" —— 写成 "utf-8" 会让 Python
    #    在 **preinit 阶段**直接 Fatal error 退出（实测踩过，报错在
    #    `preconfig_init_utf8_mode`，看起来像崩溃其实是取值非法）。
    env["PYTHONUTF8"] = "1"
    env["TMP"] = env["TEMP"] = str(TMP)

    out_wav = OUT / "w44_all.wav"
    cmd = [str(PY_MOSS), "infer_onnx.py",
           "--text-file", str(txt),
           "--prompt-audio-path", str(REF),
           "--output-audio-path", str(out_wav),
           "--disable-wetext-processing",
           "--cpu-threads", "8"]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=str(MOSS), env=env, capture_output=True,
                       text=True, errors="ignore")
    el = time.time() - t0

    print(f"  退出码   : {r.returncode}")
    print(f"  端到端   : {el:.1f}s = {el/60:.2f} 分钟")
    if out_wav.exists():
        with wave.open(str(out_wav)) as w:
            d = w.getnframes() / w.getframerate()
        print(f"  产出音频 : {d:.1f}s（{w.getframerate()} Hz）")
        print(f"  RTF      : {el/d:.2f}×")
        print(f"  字数/秒  : {total_chars/el:.1f}")
        print()
        print(f"  ── 对比 IndexTTS（W44 实测）──")
        print(f"  IndexTTS : 约 28 分钟，RTF 约 "
              f"{28*60/audio_expected:.2f}×，{total_chars/(28*60):.1f} 字/秒")
        print(f"  MOSS     : {el/60:.2f} 分钟，RTF {el/d:.2f}×，"
              f"{total_chars/el:.1f} 字/秒")
        sp = (28*60) / el
        print(f"  ⇒ MOSS 相对 IndexTTS **{'快' if sp > 1 else '慢'} "
              f"{abs(sp):.2f} 倍**")
    else:
        print("  ❌ 未产出音频")
        print((r.stderr or r.stdout or "")[-400:])
    (OUT / "bench.json").write_text(json.dumps(
        {"chars": total_chars, "elapsed": el,
         "index_sec": 28 * 60, "rc": r.returncode},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
