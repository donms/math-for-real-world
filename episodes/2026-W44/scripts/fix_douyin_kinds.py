#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""把 `分屏表_douyin.json` 里的 `kind: "bullets"` 改为 `"text"`。

## 为什么（W44 实测踩过的静默失败）

抖音分屏表里我写了 10 张 `kind: "bullets"`，
但**卡片渲染器 `render_cards.py` 只有这些版式**：
`cover / text / figure / compare / summary / cta / formula / exercise`。

`bullets` 是**长视频幻灯片**（`render_slides16x9.py`）的版式名，**两者不通用**。
未知 kind 会被**静默跳过** —— 实测 13 张卡只渲出 **3 张**，
而且渲染日志里那 10 张**连一行提示都没有**。

⇒ 用 `text` 替代 `bullets`（字段名 `head`/`lines` 完全一致）。

用法：
    $PY fix_douyin_kinds.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
P = ROOT / "episodes" / "2026-W44" / "publish" / "分屏表_douyin.json"

VALID = {"cover", "text", "figure", "compare", "summary", "cta",
         "formula", "exercise"}


def main() -> int:
    d = json.loads(P.read_text(encoding="utf-8"))
    n_fix = 0
    for s in d["screens"]:
        k = s.get("kind")
        if k == "bullets":
            s["kind"] = "text"
            n_fix += 1
        elif k not in VALID:
            print(f"  [!] 第 {s['page']} 屏 kind={k!r} 不是合法版式")
    P.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    kinds = sorted({s["kind"] for s in d["screens"]})
    print(f"[ok] 改掉 {n_fix} 个 bullets -> text")
    print(f"     现有版式：{kinds}")
    bad = [k for k in kinds if k not in VALID]
    if bad:
        print(f"     [!] 仍有非法版式：{bad}")
        return 1
    print("     ✓ 全部版式合法")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
