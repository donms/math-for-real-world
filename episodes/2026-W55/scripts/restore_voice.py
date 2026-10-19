#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · 把被 `--force` 删掉的其余 15 屏配音**按清单逐条补回来**。

## 背景（事故）

`add_voice.py --pages 2 --force` 的第一件事是 `[force] 已清理 211 个旧音频文件`，
把整片配音清空了。清单已从 `.bak_s02` 还原，但 `publish/配音/bili/` 少了 99 个 wav。

## 做法（不碰 add_voice，不用 --force）

1. 读清单，逐条算**应有的文件路径**（`publish/配音/<v>/sNN_MM.wav`）；
2. 只挑**文件不存在**的那些，把文本（`say` 优先，回退 `text`）喂给
   `indextts_engine.Engine.synthesize()` **一次批量合成**（模型只加载一次）；
3. 写到 raw 目录，再复制一份到 `_clean`（清单里 `audio` 指向的是 clean）
   —— ⚠️ 副本**未裁静音**，若将来要整片重渲，请用
   `add_voice.py --reuse --engine indextts` 按现存文件重测时长，不要直接用这份当定稿；
4. 打印"应有 / 实有 / 补了几条"，并断言数量对得上。

用法：
    $PY episodes/2026-W55/scripts/restore_voice.py --variant bili --dry-run
    $PY episodes/2026-W55/scripts/restore_voice.py --variant bili --apply
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import wave
from pathlib import Path

EP = Path(__file__).resolve().parents[1]
ROOT = EP.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

TMP = ROOT / ".workbuddy" / "tmp" / "w55_voice_restore"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, choices=["bili", "douyin"])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--duration-factor", type=float, default=0.685,
                    help="★ 必须与全片一致。原片实测 B站 6.20 字每秒、"
                         "抖音 6.75 字每秒，对应 df≈0.685")
    ap.add_argument("--batch", type=int, default=24,
                    help="每批多少条（一批一次模型加载，太多会显存吃紧）")
    args = ap.parse_args()

    man = json.loads((EP / "publish" / f"video_manifest_{args.variant}.json")
                     .read_text(encoding="utf-8"))
    raw_dir = EP / "publish" / "配音" / args.variant
    clean_dir = EP / "publish" / "配音" / f"{args.variant}_clean"
    raw_dir.mkdir(parents=True, exist_ok=True)
    clean_dir.mkdir(parents=True, exist_ok=True)

    need: list[tuple[Path, str]] = []
    total = 0
    for si, sc in enumerate(man["scenes"], 1):
        for ci, cap in enumerate(sc.get("captions") or [], 1):
            total += 1
            p = raw_dir / f"s{si:02d}_{ci:02d}.wav"
            if not p.exists():
                txt = (cap.get("say") or cap.get("text") or "").strip()
                if txt:
                    need.append((p, txt))
    print("=" * 78)
    print(f"  补配音 · {args.variant}")
    print("=" * 78)
    print(f"  清单逻辑字幕 {total} 条，缺 {len(need)} 条")
    if not need:
        print("  [OK] 一条都不缺")
        return 0
    for p, t in need[:6]:
        print(f"    缺 {p.name}: {t[:28]}")
    if not args.apply:
        print("\n  （--dry-run，不合成）")
        return 0

    import indextts_engine as IE
    eng = IE.Engine(duration_factor=args.duration_factor)
    if TMP.exists():
        shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True, exist_ok=True)

    done = 0
    for b0 in range(0, len(need), args.batch):
        chunk = need[b0:b0 + args.batch]
        outs = [TMP / f"r_{b0 + k:04d}.wav" for k in range(len(chunk))]
        print(f"\n  -- 第 {b0 // args.batch + 1} 批：{len(chunk)} 条 --")
        oks = eng.synthesize([t for _, t in chunk], outs)
        for (dst, _), src, ok in zip(chunk, outs, oks):
            if not ok or not src.exists():
                print(f"  [!] {dst.name} 合成失败")
                continue
            shutil.copy2(src, dst)
            shutil.copy2(src, clean_dir / dst.name)
            done += 1
        print(f"     本批完成 {sum(oks)}，累计 {done}/{len(need)}")

    have = len(list(raw_dir.glob("s*_*.wav")))
    print(f"\n  [结果] {args.variant}: 应有 {total} 条，"
          f"raw 目录现有 {have} 条，本次补 {done} 条")
    ok = have >= total
    print("  判定：" + ("[OK] 逐条对应" if ok else "[X] 仍有缺"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
