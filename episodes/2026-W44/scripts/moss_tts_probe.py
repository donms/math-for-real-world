#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""MOSS-TTS-Nano 试跑：**速度对比 IndexTTS** + 读音检查。

## 为什么要先跑这个（而不是直接换引擎）

W44 实测 IndexTTS 的速度（用户反馈"有点慢"）：
* 73 条口播 / 约 28 分钟 ⇒ **约 23 秒/条**，约 **2.6 条/分钟**
* 按音频时长算，实时率（RTF = 生成耗时 / 音频时长）约 **3～4×**
  （即生成 1 秒音频要 3～4 秒）

MOSS-TTS-Nano 官方称 0.1B、CPU 可实时、ONNX 版再快近一倍。
⇒ 本脚本用**同一批 W44 真实句子 + 同一参考音（Don）**跑一遍，
   输出逐条耗时与 RTF，和 IndexTTS 直接可比。

## 关键风险（必须先验证）

MOSS-TTS-Nano **没有拼音/音素级控制**（`infer_onnx.py` 的参数表里没有），
只有 WeTextProcessing 文本归一化 ⇒ **修不了「率」这类多音字**。
（年份问题不受影响：那靠把 `2025` 写成 `二零二五`，是纯文本替换。）

故本脚本特意测两类句子：
* **含年份**的（应没问题 —— 文本已转汉字）
* **含「率」**的（预期会读错 —— 用来确认这个限制是否真实）

用法：
    $PY moss_tts_probe.py
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
MOSS = Path(r"<LOCAL_PATH>")
PY_MOSS = Path(r"python")
REF = ROOT / "media" / "audio" / "ref" / "voice_ref_Don_norm.wav"
OUT = ROOT / "episodes" / "2026-W44" / "publish" / "_tmp_moss"

# 取自 W44 真实讲稿（含年份 / 小数 / 百分数 / 多音字「率」）
CASES = [
    ("纯叙述", "我们小区旁边那家幼儿园，去年悄悄关了。"),
    ("含年份", "二零二五 年，全国幼儿园 二十三点一九 万所。"),
    ("含年份区间", "其中 二零一六 到 二零二五 是连续十年。"),
    ("含多音字率", "我把入园率顶到理论上限 百分之百 试了一下。"),
    ("含小数", "标定结果是 零点九七二七，相对误差都在 百分之三 以内。"),
]


def wav_dur(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("=" * 90)
    print("  MOSS-TTS-Nano 试跑（ONNX），对比 IndexTTS")
    print("=" * 90)
    print(f"  MOSS 仓库 : {MOSS}")
    print(f"  解释器    : {PY_MOSS}  ({PY_MOSS.exists()})")
    print(f"  参考音    : {REF.name}  ({REF.exists()})")
    print(f"  IndexTTS 基线：约 23 秒/条，RTF 约 3～4×\n")

    env = dict(os.environ)
    # HuggingFace 直连不通时走镜像（实测 hf-mirror.com 可达）
    env.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    # 临时目录必须在工作区（系统 temp 在本机沙箱不可写）
    tmp = r"<LOCAL_PATH>"
    env["TMP"] = env["TEMP"] = tmp

    rows = []
    print(f"  {'用例':<14}{'音频(s)':>9}{'耗时(s)':>9}{'RTF':>7}  说明")
    for i, (name, text) in enumerate(CASES, 1):
        out = OUT / f"{i:02d}_{name}.wav"
        cmd = [str(PY_MOSS), "infer_onnx.py",
               "--text", text,
               "--prompt-audio-path", str(REF),
               "--output-audio-path", str(out)]
        t0 = time.time()
        r = subprocess.run(cmd, cwd=str(MOSS), env=env,
                           capture_output=True, text=True, errors="ignore")
        el = time.time() - t0
        if not out.exists():
            print(f"  {name:<14}{'—':>9}{el:>9.1f}{'—':>7}  ❌ 失败")
            tail = (r.stderr or r.stdout or "")[-180:].replace("\n", " ")
            print(f"       {tail}")
            continue
        d = wav_dur(out)
        rtf = el / d if d > 0 else 0
        rows.append((name, d, el, rtf))
        print(f"  {name:<14}{d:>9.2f}{el:>9.1f}{rtf:>7.2f}  {text[:26]}")

    if rows:
        tot_a = sum(r[1] for r in rows)
        tot_t = sum(r[2] for r in rows)
        print(f"\n{'='*90}")
        print(f"  合计音频 {tot_a:.1f}s，合计耗时 {tot_t:.1f}s")
        print(f"  平均 RTF {tot_t/tot_a:.2f}×　"
              f"（IndexTTS 约 3～4×，越小越快）")
        print(f"  按此速度，73 条约需 "
              f"{tot_t/len(rows)*73/60:.1f} 分钟"
              f"（IndexTTS 实测约 28 分钟）")
    (OUT / "result.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  试听目录：{OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
