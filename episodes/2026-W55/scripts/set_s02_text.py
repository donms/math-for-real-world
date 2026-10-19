#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · 把屏 02 的新口播写进两个 manifest（**只改第 2 屏的 text**）。

## 为什么要单独一步

`add_voice.py --pages 2` 只重合成第 2 屏，但它的切分来源是 `scenes[i]["text"]`
⇒ 必须**先把新口播写进 text**，否则它照旧稿重合成。
其余 15 屏的 text 一个字节都不动。

## A 方案（保帧数）在下一步

`add_voice` 结束时会用 `sc["dur"] = Σ字幕时长 + gap_after` **重算屏时长**（见 add_voice 第 534 行）。
那样屏 02 会变长 ⇒ 后面的屏全部平移 ⇒ 帧数不再是 15947。
所以本脚本先把 **原屏时长快照** 存进 `_logs/_s02_slot.json`，
`fit_s02_audio.py` 再按这个槽位把新音频等比塞回去、并把 dur 还原。

用法：
    $PY episodes/2026-W55/scripts/set_s02_text.py            # 只打印
    $PY episodes/2026-W55/scripts/set_s02_text.py --apply
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

EP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EP / "scripts"))
sys.path.insert(0, str(EP / "scripts"))
from split_caption_s02 import TEXT, TEXT_DOUYIN      # noqa: E402

PUB = EP / "publish"
SLOT = EP / "_logs" / "_s02_slot.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    texts = {"bili": TEXT, "douyin": TEXT_DOUYIN}
    slot: dict[str, dict] = {}
    for v, txt in texts.items():
        p = PUB / f"video_manifest_{v}.json"
        man = json.loads(p.read_text(encoding="utf-8"))
        sc = man["scenes"][1]
        old = sc.get("text", "")
        caps = sc.get("captions") or []
        old_sum = sum(float(c.get("dur") or 0) for c in caps)
        slot[v] = {
            "dur": float(sc["dur"]),
            "gap_after": float(sc.get("gap_after") or 0.0),
            "caps_sum": round(old_sum, 6),
            "n_caps": len(caps),
        }
        print(f"=== {v} ===")
        print(f"  原 text {len(old)} 字 / {len(caps)} 条字幕 / "
              f"Σ字幕 {old_sum:.3f}s / 屏时长 {sc['dur']:.3f}s / "
              f"gap {sc.get('gap_after')}")
        print(f"  新 text {len(txt)} 字")
        print(f"  新稿预览：{txt[:60]}…")
        if args.apply:
            bak = p.with_suffix(".json.bak_s02")
            if not bak.exists():
                shutil.copy2(p, bak)
                print(f"  [bak] {bak.name}")
            sc["text"] = txt
            sc["tts"] = ""          # 让 add_voice 重新生成
            p.write_text(json.dumps(man, ensure_ascii=False, indent=1),
                         encoding="utf-8")
            print(f"  [写回] {p.name}")

    if args.apply:
        SLOT.write_text(json.dumps(slot, ensure_ascii=False, indent=1),
                        encoding="utf-8")
        print(f"\n  [slot] 原槽位快照 -> {SLOT.relative_to(EP)}")
        print(f"  {json.dumps(slot, ensure_ascii=False)}")
    else:
        print("\n  （未加 --apply，什么都没改）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
