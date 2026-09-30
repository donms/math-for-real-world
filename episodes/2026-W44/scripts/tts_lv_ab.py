#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W44 · 「率」读音 A/B/C 测试：确定 lǜ 的正确写法。

## 背景（用户实测反馈）

> 「有两个『率』读错了，应该是 lǜ，而不是 shuài，
>   一个在园率，一个入园率，**也不是都错**」

「率」是多音字：`lǜ`（效率、入园率、概率）/ `shuài`（率领、轻率）。
本文稿里 9 处「率」**全部是 lǜ 义**（在园率 / 入园率 / 退出率 / 效率）。

## 三种候选写法

| 代号 | 写法 | 说明 |
|---|---|---|
| **A** | `在园率` | 裸文本（现状）|
| **B** | `在园<率\|LÜ4>` | 用 `ü` 标注（front.py 只对 j/q/x 把 ü→v，l 不转换）|
| **C** | `在园<率\|LV4>` | 用 `v` 代替 ü（拼音输入法惯例）|

合成后比较时长：`shuài`（sh-u-ai，3 音素）比 `lǜ`（l-ü，2 音素）**长**。
⇒ 音频**较短**的那个是正确读法（与年份测试同一判据）。

用法：
    $PY tts_lv_ab.py
"""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
OUT = EP / "publish" / "_tmp_lv_ab"
REF = ROOT / "media" / "audio" / "ref" / "voice_ref_Don.wav"

CASES = {
    # 一句里放 5 个「率」⇒ 读法差异被放大 5 倍，便于用时长效判
    "A_裸文本": "入园率、在园率、毛入园率、退出率、效率，这五个率都要读对。",
    "B_ü标注": ("入园<率|LÜ4>、在园<率|LÜ4>、毛入园<率|LÜ4>、"
                "退出<率|LÜ4>、效<率|LÜ4>，这五个率都要读对。"),
    "C_v标注": ("入园<率|LV4>、在园<率|LV4>、毛入园<率|LV4>、"
                "退出<率|LV4>、效<率|LV4>，这五个率都要读对。"),
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / "scripts"))
    print("=" * 88)
    print("  W44 · 「率」读音 A/B/C 测试")
    print("=" * 88)

    from indextts_engine import Engine
    eng = Engine(ref=REF, use_lock=False)   # 关锁定表，只测我们给的写法
    names = list(CASES)
    paths = [OUT / f"{n}.wav" for n in names]
    print(f"\n  合成 {len(names)} 条…")
    eng.synthesize([CASES[n] for n in names], paths)

    rows = []
    for n, p in zip(names, paths):
        if not p.exists():
            print(f"  {n:<12} 失败")
            continue
        with wave.open(str(p)) as w:
            dur = w.getnframes() / w.getframerate()
        rows.append((n, dur))
        print(f"  {n:<12}{dur:>7.2f}s   {CASES[n][:34]}")

    if len(rows) >= 2:
        rows.sort(key=lambda r: r[1])
        print(f"\n  ⇒ 最短 = {rows[0][0]}（{rows[0][1]:.2f}s）")
        print(f"     最长 = {rows[-1][0]}（{rows[-1][1]:.2f}s）")
        print("     shuài（sh-u-ai，3 音素）比 lǜ（l-ü，2 音素）长 ⇒ **较短者正确**")
    print(f"\n  试听：{OUT}")
    print(f"  结果 JSON：{OUT/'result.json'}")
    (OUT / "result.json").write_text(
        json.dumps(dict(rows), ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
