#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""配音小样标定：用**同一段讲稿**在 3 个 `duration_factor` 下各合成一遍，
量出**去静音后**的语速（字/秒），挑落在 6.2 字/秒附近的那一档。

## 为什么必须每期标定，不能沿用往期常数

`duration_factor` 的实际效果**随参考音而变**：W56 用 0.78 得到 7.00 字/秒，
W55 用 0.84。同一个数字换一期就偏。⇒ 只能拿**当期参考音**实测。

## 量的是什么

合成出的 wav **两头带静音**，而字幕/成片用的是 `add_voice` 裁过静音的版本。
直接量原始 wav 会把静音算进"朗读时长"，把语速系统性压低。
⇒ 这里用**振幅阈值**找出首尾有效样本，只量中间那一段。

## 用法

    $PY episodes\2026-W57\scripts\calibrate_duration_factor.py
    $PY episodes\2026-W57\scripts\calibrate_duration_factor.py --factors 0.84 0.90 0.96
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import wave
from pathlib import Path

import numpy as np

EP = Path(__file__).resolve().parents[1]
ROOT = EP.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(EP / "scripts"))

from make_storyboard import parse_screens          # noqa: E402
from tts_text import clean_caption, to_tts         # noqa: E402

REF = ROOT / "media" / "audio" / "ref" / "s02_06_norm.wav"
TARGET_CPS = 6.2
TMP = ROOT / ".workbuddy" / "tmp" / "w57_calib"
OUT_MD = EP / "publish" / "_配音小样标定.md"


def spoken_of(screens: dict[int, str], picks: tuple[int, ...]) -> list[str]:
    """取指定几屏的**口播读法**（数字已转汉字），按句切成若干段。

    ⚠️ 必须把**实际送进 TTS 的每一段**一起返回并据此数字数 ——
    第一版只送了前两句、却拿整屏的字数去除，量出「81 字/秒」这种荒唐值
    （W54-8 的同类错：分子的口径与分母不是同一批样本）。
    """
    out: list[str] = []
    for k in picks:
        body = screens[k]
        caps = [clean_caption(c) for c in re.split(r"(?<=[。！？；])", body)
                if c.strip()]
        out += [to_tts(c) for c in caps]
    return [c for c in out if c.strip()]


def trimmed_dur(p: Path, rel: float = 0.02) -> float:
    """去静音后的时长：首尾各找到第一个 |x| > rel×峰值 的样本。"""
    with wave.open(str(p), "rb") as w:
        sr, n = w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
    if x.size == 0:
        return 0.0
    thr = rel * float(np.abs(x).max())
    idx = np.where(np.abs(x) > thr)[0]
    if idx.size == 0:
        return 0.0
    return float(idx[-1] - idx[0] + 1) / sr


def main() -> int:
    ap = argparse.ArgumentParser(description="配音语速标定（3 档小样）")
    ap.add_argument("--factors", nargs="+", type=float,
                    default=[0.74, 0.79, 0.84])
    ap.add_argument("--screens", nargs="+", type=int, default=[5],
                    help="用哪一屏的讲稿作样本（默认第 5 屏：含大量小数与百分号）")
    ap.add_argument("--ref", default=str(REF))
    args = ap.parse_args()

    txt = (EP / "内容" / "讲稿.md").read_text(encoding="utf-8")
    screens = dict(parse_screens(txt))
    chunks = spoken_of(screens, tuple(args.screens))
    n_chars = len(re.sub(r"\s", "", "".join(chunks)))
    print(f"  样本：第 {'、'.join(map(str, args.screens))} 屏，"
          f"{len(chunks)} 段，口播读法 {n_chars} 字")
    print(f"  参考音：{args.ref}")
    assert Path(args.ref).exists(), f"参考音不存在：{args.ref}"

    from indextts_engine import Engine

    TMP.mkdir(parents=True, exist_ok=True)
    rows = []
    for f in args.factors:
        print("\n" + "=" * 70)
        print(f"  duration_factor = {f}")
        print("=" * 70)
        eng = Engine(ref=Path(args.ref), duration_factor=f)
        outs = [TMP / f"calib_{f}_{i}.wav" for i in range(1, len(chunks) + 1)]
        ok = eng.synthesize(chunks, outs)
        if not all(ok):
            print(f"[X] 合成失败：{ok}")
            return 2
        durs = [trimmed_dur(p) for p in outs]
        tot = sum(durs)
        cps = n_chars / tot
        rows.append({"factor": f, "chars": n_chars, "dur": round(tot, 3),
                     "cps": round(cps, 3)})
        print(f"  -> {len(outs)} 段，去静音总时长 {tot:.3f}s  "
              f"语速 {cps:.2f} 字/秒")

    best = min(rows, key=lambda r: abs(r["cps"] - TARGET_CPS))
    print("\n" + "=" * 70)
    print(f"  {'factor':>8} {'字数':>6} {'时长(s)':>9} {'字/秒':>7} {'偏离目标':>9}")
    for r in rows:
        print(f"  {r['factor']:>8.2f} {r['chars']:>6d} {r['dur']:>9.3f} "
              f"{r['cps']:>7.2f} {r['cps']-TARGET_CPS:>+9.2f}")
    print(f"\n  ★ 选定：duration_factor = {best['factor']}"
          f"（{best['cps']:.2f} 字/秒，目标 {TARGET_CPS}）")

    lines = ["# 2026-W57 配音小样标定", "",
             f"> 参考音：`{args.ref}`",
             f"> 样本：第 {'、'.join(map(str, args.screens))} 屏讲稿，"
             f"口播读法 {n_chars} 字（数字已转汉字）",
             "> 口径：**去静音后**的时长（振幅阈值 2% 峰值），"
             "与 `add_voice` 的裁剪口径一致。", "",
             "| duration_factor | 字数 | 去静音时长 (s) | 语速 (字/秒) | 偏离 6.2 |",
             "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['factor']:.2f} | {r['chars']} | {r['dur']:.3f} | "
                     f"{r['cps']:.2f} | {r['cps']-TARGET_CPS:+.2f} |")
    lines += ["", f"**选定 `duration_factor = {best['factor']}`**"
                  f"（{best['cps']:.2f} 字/秒）。", ""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"  -> {OUT_MD}")
    (TMP / "calib.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
