#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""B站配音音频的**内容寻址复用**：同样的口播文本，沿用旧音频。

## 为什么需要

重建清单后，`captions` 被**重新切分**过（坏清单里 `add_voice` 是按
口播重切的，条数与正确版不同：**116 -> 109**）。
⇒ **编号对不上**，不能按 `s07_03.wav` 这种编号复用。

但**同一段口播文本的音频是可以复用的** —— 内容没变，重配只是浪费。

## 做法

1. 从**旧清单**建 `say 文本 -> audio 路径` 的映射；
2. 遍历**新清单**的每条 caption，若其 `say` 在映射里且音频文件存在，
   **复制**该音频到新编号的文件名，并把 `audio`/`dur` 写进新清单；
3. 报告哪些条**没有**可复用音频（这些才需要真正重配）。

> [!] 只按**完整 say 文本**精确匹配，不做模糊匹配 ——
> 宁可多配几条，也不要让音频和字幕错位。

用法（须先 `make_render_specs.py` 重建清单，且旧清单已备份）：
    $PY reuse_audio_by_text.py --ep 2026-W46 --variant bili \
        --old .workbuddy/tmp/cmp46/bili_old.json
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def probe(p: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return -1.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", required=True)
    ap.add_argument("--variant", required=True)
    ap.add_argument("--old", required=True, help="旧清单 JSON（备份）")
    a = ap.parse_args()

    ep = ROOT / "episodes" / a.ep
    man_p = ep / "publish" / f"video_manifest_{a.variant}.json"
    old_p = Path(a.old)
    if not old_p.is_absolute():
        old_p = ROOT / old_p
    new = json.loads(man_p.read_text(encoding="utf-8"))
    old = json.loads(old_p.read_text(encoding="utf-8"))

    # ① 建「say 文本 -> 音频文件」映射（旧清单里已实测过的）
    pool: dict[str, list[Path]] = {}
    for sc in old.get("scenes", []):
        for c in sc.get("captions") or []:
            if not isinstance(c, dict) or not c.get("audio"):
                continue
            p = ep / c["audio"]
            if p.exists():
                pool.setdefault(str(c.get("say") or "").strip(), []).append(p)
    tot_pool = sum(len(v) for v in pool.values())
    print(f"  旧清单可复用音频池：{tot_pool} 段 / {len(pool)} 种文本")

    # ② 逐条匹配
    vdir = ep / "publish" / "配音" / f"{a.variant}"
    vdir.mkdir(parents=True, exist_ok=True)
    reused = missing = 0
    miss_list: list[tuple[int, int, str]] = []
    for sc in new.get("scenes", []):
        for j, c in enumerate(sc.get("captions") or [], 1):
            if not isinstance(c, dict):
                continue
            key = str(c.get("say") or "").strip()
            dst = vdir / f"s{sc['idx']:02d}_{j:02d}.wav"
            src = pool.get(key, [])
            if src:
                shutil.copyfile(src.pop(0), dst)
                c["audio"] = str(dst.relative_to(ep)).replace("\\", "/")
                c["dur"] = round(probe(dst), 3)
                reused += 1
            else:
                missing += 1
                miss_list.append((sc["idx"], j, key[:40]))
        caps = [c for c in (sc.get("captions") or []) if isinstance(c, dict)]
        if caps and all(c.get("dur") for c in caps):
            sc["dur"] = round(sum(float(c["dur"]) for c in caps)
                              + float(sc.get("gap_after", 0.0)), 2)

    man_p.write_text(json.dumps(new, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"  复用 {reused} 段 / 待重配 {missing} 段")
    if miss_list:
        print("  === 待重配（屏, 序号, 文本）===")
        for i, j, t in miss_list[:20]:
            print(f"    屏{i} #{j}  {t}")
    ids = sorted({i for i, _j, _t in miss_list})
    print(f"  需要重配的屏：{ids if ids else '无'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
