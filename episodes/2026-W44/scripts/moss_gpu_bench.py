#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""MOSS-TTS-Nano **CPU vs GPU** 测速对照。

## 为什么测这个

MOSS 官方推荐 CPU 推理（"4 核可流式"），但本机有 **RTX 4060 8 GB** 闲置，
而 `gsv310` 环境里的 `onnxruntime 1.23.2` **自带 CUDAExecutionProvider**。
若 GPU 明显更快，就用 GPU。

## 做法

用 W44 讲稿的**前 N 条字幕**（默认 20 条，约占总量的 27%）分别跑
`--execution-provider cpu` 与 `cuda`，比端到端耗时与 RTF。
取子集是为了快（每次都要加载模型）。

用法：
    $PY moss_gpu_bench.py [条数]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
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


def dur(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    OUT.mkdir(parents=True, exist_ok=True)
    man = json.loads((EP / "publish" / "video_manifest_bili.json")
                     .read_text(encoding="utf-8"))
    caps = [c["text"].replace("\n", "")
            for s in man["scenes"] for c in (s.get("captions") or [])][:n]
    chars = sum(len(c) for c in caps)
    txt = OUT / f"bench_{n}.txt"
    txt.write_text("\n".join(caps), encoding="utf-8")

    env = dict(os.environ)
    env["HF_ENDPOINT"] = "https://hf-mirror.com"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"          # 只能取 1/0
    env["TMP"] = env["TEMP"] = str(TMP)

    print("=" * 84)
    print(f"  MOSS-TTS-Nano CPU vs GPU（前 {n} 条字幕 / {chars} 字）")
    print("=" * 84)

    rows = []
    for prov in ("cpu", "cuda"):
        out = OUT / f"bench_{n}_{prov}.wav"
        cmd = [str(PY_MOSS), "infer_onnx.py",
               "--text-file", str(txt),
               "--prompt-audio-path", str(REF),
               "--output-audio-path", str(out),
               "--disable-wetext-processing",
               "--execution-provider", prov,
               "--cpu-threads", "8"]
        t0 = time.time()
        r = subprocess.run(cmd, cwd=str(MOSS), env=env, capture_output=True,
                           text=True, errors="ignore")
        el = time.time() - t0
        if out.exists():
            d = dur(out)
            rows.append((prov, el, d, el / d, chars / el))
            print(f"  {prov:<5} 耗时 {el:>7.1f}s  音频 {d:>6.1f}s  "
                  f"RTF {el/d:>5.2f}x  {chars/el:>4.1f} 字/秒")
        else:
            print(f"  {prov:<5} 失败 rc={r.returncode}")
            tail = (r.stderr or r.stdout or "").strip().splitlines()
            for ln in tail[-4:]:
                print(f"        {ln[:110]}")

    if len(rows) == 2:
        (p1, t1, _d1, _r1, _s1), (p2, t2, *_rest) = rows
        sp = t1 / t2
        print(f"\n  ⇒ {p2} 相对 {p1} "
              f"{'快' if sp > 1 else '慢'} {abs(sp):.2f} 倍")
        full = 2554 / (rows[0][4] if p2 == 'cpu' else rows[1][4])
        print(f"     按此速度，W44 全部 2554 字约需 {full/60:.1f} 分钟")
    (OUT / "gpu_bench.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
