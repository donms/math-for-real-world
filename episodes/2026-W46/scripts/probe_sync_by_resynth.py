#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""决定性实验：**当前音频与当前 `say` 文本是否一致**。

## 为什么需要这个实验

`_timing.txt` 的字段语义无法可靠解析（它是历史累积的，
且"字数"栏与实际合成条数、当前 `captions` 都不严格对应），
按它推断会得出自相矛盾的结论。
**时长反推也被证伪**（`百分之五点四` 读作 7 个音节、`R_t` 读作 2–3 个，
字数模型必然失真）。

⇒ 唯一可靠办法：**把当前 `say` 重新合成一遍，与现有音频比时长**。

* 时长接近（±1.5s，因 IndexTTS 生成非确定）⇒ 音频与文本一致 ⇒ **同步**；
* 时长差很多 ⇒ 现有音频是**别的文本**合成的 ⇒ **错位**。

只抽样若干段（含"未重配"与"已重配"两类），避免全量耗时。

用法：
    $PY probe_sync_by_resynth.py --ep 2026-W46 --variant bili
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))


def probe(p: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    try:
        return round(float(r.stdout.strip()), 3)
    except ValueError:
        return -1.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", required=True)
    ap.add_argument("--variant", default="bili")
    ap.add_argument("--duration-factor", type=float, default=1.0,
                    help="必须与配音频时用的一致，否则有系统性偏差")
    a = ap.parse_args()
    ep = ROOT / "episodes" / a.ep
    man = json.loads((ep / "publish"
                      / f"video_manifest_{a.variant}.json").read_text("utf-8"))

    # 抽样：屏1（未重配）、屏6（已重配）、屏20（时长最可疑）、屏11
    if a.variant == "douyin":
        want = {1: [1], 2: [1], 4: [1, 2], 6: [1]}
    else:
        want = {1: [1, 3], 20: [1, 2], 11: [2], 12: [4]}
    picks = []
    for sc in man["scenes"]:
        if sc["idx"] not in want:
            continue
        for j, c in enumerate(sc["captions"], 1):
            if j not in want[sc["idx"]]:
                continue
            p = ep / str(c.get("audio"))
            if p.exists():
                picks.append((sc["idx"], j, str(c.get("say") or ""),
                              float(c.get("dur") or 0), p))

    print(f"  抽样 {len(picks)} 段，开始重合成…")
    from indextts_engine import Engine as _ITE                    # noqa: E402
    ref = ROOT / "media" / "audio" / "ref" / "voice_ref_Don_norm.wav"
    eng = _ITE(ref=ref if ref.exists() else None,
               duration_factor=a.duration_factor)
    # [!] 输出必须落在**工作区内**：沙箱禁止写系统临时目录
    tmp = ROOT / ".workbuddy" / "tmp" / "syncprobe"
    if tmp.exists():
        import shutil as _sh
        _sh.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    outs = [tmp / f"p{i:02d}_{j:02d}.wav" for i, j, _s, _d, _p in picks]
    oks = eng.synthesize([s for _i, _j, s, _d, _p in picks],
                         [o for o in outs])
    if not all(oks):
        print("  [!] 部分合成失败")

    print(f"\n  {'屏':>3} {'序':>3} {'现有':>8} {'重合成':>8} {'差':>8}  判定")
    n_same = n_diff = 0
    for (i, j, say, d_old, _p), o in zip(picks, outs):
        d_new = probe(o) if o.exists() else -1
        diff = d_new - d_old
        if abs(diff) <= 1.5:
            n_same += 1
            tag = "一致"
        else:
            n_diff += 1
            tag = "**不一致**"
        print(f"  {i:>3} {j:>3} {d_old:>8.2f} {d_new:>8.2f} {diff:>+8.2f}  {tag}")
        if tag != "一致":
            print(f"        say: {say[:58]}")

    print(f"\n  一致 {n_same} / 不一致 {n_diff}")
    if n_diff == 0:
        print("  => **音频与文本同步** [OK]")
    elif n_same == 0:
        print("  => **全部错位，必须重配**")
    else:
        print("  => **部分错位** —— 需按屏定位后重配")
    print(f"  （临时目录：{tmp}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
