#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W44 · 年份读音 A/B 测试：确认「2025 年」的正确写法。

## 背景（用户实测反馈）

> 「年份的读音都有问题，2025 年不应该发音成两千零二十五年」

## 已定位到的机制

`indextts_engine.preprocess()` 的执行顺序是：

```
① pronounce_numbers()   —— 数字归一化（0.18 → 零点一八）
② lock_digit_sequence() —— 「逐位读」锁定（403 → <4|SI4><0|LING2><3|SAN1>）
```

问题：`pronounce_numbers()` **不动四位年份**（实测 `2025 年` → `2025 年`），
于是 `2025` 以**裸整数**形式进入 IndexTTS ⇒ 被当**数量词**读成「两千零二十五」。
（仓库自己的注释已记录同类现象：`403` 默认读成「四百零三」。）

而锁定表 `media/audio/tts_拼音锁定表.json` 的 `digits` 里**只有 `403`，没有年份**。

## 本测试的三种候选写法

| 代号 | 写法 | 说明 |
|---|---|---|
| **A** | `2025 年` | 现状（裸整数） |
| **B** | `二零二五 年` | 预先把年份转成汉字数字 |
| **C** | `<2\|ER4><0\|LING2><2\|ER4><5\|WU3> 年` | 用逐位锁定标注 |

合成后比较**音素数量变化**：正确读法「二零二五年」是 **5 个音节**，
误读「两千零二十五年」是 **7 个音节** ⇒ 同长度文本下**正确写法的音频应明显更短**。

用法：
    $PY tts_year_ab.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W44"
OUT = EP / "publish" / "_tmp_year_ab"
ITE_PY = ROOT / "envs" / "indextts" / "Scripts" / "python.exe"
REF = ROOT / "media" / "audio" / "ref" / "voice_ref_Don.wav"

# 同一句话，只有年份写法不同 ⇒ 音频长度可直接比较
CASES = {
    "A_裸整数": "2025 年，全国幼儿园二十三点一九万所。",
    "B_汉字年": "二零二五 年，全国幼儿园二十三点一九万所。",
    "C_逐位锁定": "<2|ER4><0|LING2><2|ER4><5|WU3> 年，全国幼儿园二十三点一九万所。",
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("=" * 88)
    print("  W44 · 年份读音 A/B 测试")
    print("=" * 88)
    print(f"\n  IndexTTS 解释器：{ITE_PY.exists()}")
    print(f"  Don 参考音：{REF.exists()}")

    # 用 indextts_engine 直接合成（它会套用锁定表）
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from indextts_engine import Engine
    except Exception as e:                             # noqa: BLE001
        print(f"  [!] 无法导入 Engine：{e}")
        return 2

    eng = Engine(ref=REF, use_lock=False)   # ★ 关掉锁定表，只用我们给的写法
    names = list(CASES)
    texts = [CASES[n] for n in names]
    paths = [OUT / f"{n}.wav" for n in names]

    print(f"\n  正在合成 {len(texts)} 条…")
    ok = eng.synthesize(texts, paths)

    print(f"\n  {'写法':<14}{'时长(s)':>9}{'KB':>8}   说明")
    rows = []
    for n, p, o in zip(names, paths, ok):
        if not p.exists():
            print(f"  {n:<14}{'失败':>9}")
            continue
        try:
            import wave
            with wave.open(str(p)) as w:
                dur = w.getnframes() / w.getframerate()
        except Exception:                              # noqa: BLE001
            dur = -1
        rows.append((n, dur, p.stat().st_size / 1024))
        print(f"  {n:<14}{dur:>9.2f}{p.stat().st_size/1024:>8.1f}   "
              f"{CASES[n][:30]}")

    if len(rows) >= 2:
        rows_sorted = sorted(rows, key=lambda r: r[1])
        print(f"\n  ⇒ 最短 = {rows_sorted[0][0]}（{rows_sorted[0][1]:.2f}s）")
        print(f"     最长 = {rows_sorted[-1][0]}（{rows_sorted[-1][1]:.2f}s）")
        print("     正确读法『二零二五年』5 个音节；误读『两千零二十五年』7 个音节")
        print("     ⇒ **更短的那个才是对的**")
    print(f"\n  试听文件：{OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
