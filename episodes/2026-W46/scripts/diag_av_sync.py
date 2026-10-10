#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""诊断：B站 成片里**音频与字幕是否错位**。

## 疑点

我之前把清单的 `tts_captions` **重写成** `[to_tts(c) for c in captions]`
（为了让条数配对），**但没有重配音频**。

而 `add_voice --reuse` 当时是用**自己的 max_cap 重切** captions 的，
音频则是按**更早的切分**合成的。
⇒ **字幕条边界与音频段边界可能已经不重合**。

## 判据：用 `_timing.txt` 的**逐段字数与时长**反推

`_timing.txt` 每行是 `屏 序 字数 时长 文本`，那是**合成时**的真实记录。
把它与当前清单逐段比：

* **字数**：`_timing` 记的"字数"应等于该段 `say` 的字数（去空白）；
* **时长**：应等于该段音频实测时长。

若字数对不上 ⇒ **字幕切分与音频切分不同** ⇒ 成片会错位。

用法：
    $PY diag_av_sync.py --ep 2026-W46 --variant bili
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


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
    ap.add_argument("--variant", required=True)
    a = ap.parse_args()
    ep = ROOT / "episodes" / a.ep
    man = json.loads((ep / "publish"
                      / f"video_manifest_{a.variant}.json").read_text("utf-8"))
    tp = ep / "publish" / "配音" / a.variant / "_timing.txt"
    tmg: dict[tuple[int, int], tuple[int, float, str]] = {}
    for ln in tp.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+(.*)$", ln)
        if m:
            tmg[(int(m.group(1)), int(m.group(2)))] = (
                int(m.group(3)), float(m.group(4)), m.group(5))

    bad_n = bad_d = ok = 0
    rows = []
    for sc in man["scenes"]:
        for j, c in enumerate(sc["captions"], 1):
            t = tmg.get((sc["idx"], j))
            if t is None:
                continue
            n_t, d_t, txt_t = t
            say = re.sub(r"\s", "", str(c.get("say") or ""))
            d_man = float(c.get("dur") or 0)
            n_ok = (n_t == len(say))
            d_ok = abs(d_t - d_man) <= 0.02
            if n_ok and d_ok:
                ok += 1
            else:
                if not n_ok:
                    bad_n += 1
                if not d_ok:
                    bad_d += 1
                rows.append((sc["idx"], j, n_t, len(say), d_t, d_man,
                             say[:26], txt_t[:26]))

    print(f"  逐段一致 {ok} 段")
    print(f"  字数不符 {bad_n} 段 | 时长不符 {bad_d} 段")
    if rows:
        print("\n  === 不一致明细（前 14）===")
        print(f"     {'屏':>3} {'序':>3} {'timing字':>8} {'清单字':>7} "
              f"{'timing时长':>10} {'清单时长':>9}   文本")
        for i, j, nt, ns, dt, dm, say, tx in rows[:14]:
            print(f"     {i:>3} {j:>3} {nt:>8} {ns:>7} {dt:>10.2f} "
                  f"{dm:>9.2f}   {say}")
    verdict = "**错位**" if (bad_n or bad_d) else "**一致**"
    print(f"\n  => {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
