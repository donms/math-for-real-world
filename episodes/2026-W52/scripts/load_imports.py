#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""定位 `imports.jsonl`（Lean 依赖图），支持**单期包**与**完整仓库**两种布局。

## 为什么需要这个文件

W52（分支壁垒）与 W50（承重结构）用的是**同一份** `imports.jsonl`，
它由 W50 抓取（86924 模块 / 248871 条边）。

W52 的脚本最初把它硬编码成：

```python
SRC = ROOT / "episodes" / "2026-W50" / "data" / "imports.jsonl"
```

**这在完整仓库里能跑，但读者 clone 的是「单期包」** ——
单期包里没有 `episodes/2026-W50/` ⇒ 直接 `FileNotFoundError`。

> 这与 skill 记的 W46 教训同源：
> **"清洗后的 CSV 是分析脚本的必需输入，必须进包"** ——
> 那次漏的是 `data/clean/*.csv`，这次漏的是一整个数据文件。

## 查找顺序（**先本地、后跨期**）

| # | 位置 | 适用 |
|---|---|---|
| 1 | `<期目录>/data/imports.jsonl` | **单期包**（打包时把它放进本期 `data/`）|
| 2 | `<仓库根>/episodes/2026-W52/data/imports.jsonl` | 开发时的完整仓库 |
| 3 | `<仓库根>/episodes/2026-W50/data/imports.jsonl` | 完整仓库（原始出处）|
| 4 | `<仓库根>/data/imports.jsonl` | 扁平布局 |

找不到就给出**可操作的提示**，而不是抛一个光秃秃的 `FileNotFoundError`。

用法：
    from load_imports import find_imports
    SRC = find_imports(ROOT)          # ROOT = 仓库根（或期目录的祖先）
"""
from __future__ import annotations

from pathlib import Path

CANDIDATES = (
    ("episodes/{ep}/data/imports.jsonl", "本期的 data/（单期包 / 完整仓库）"),
    ("data/imports.jsonl", "平铺布局的 data/"),
)

HINT = """\
[X] 找不到 imports.jsonl（Lean 依赖图，约 19.5 MB / 86924 行）。

它由 W50 的 `fetch_lean_imports.py` 从 openai/math 仓库的 lean/ 目录抓取，
W50 与 W52 两期用的是**同一份**。

三个办法任选其一：

 ① 拿到的是**单期包**：确认 `episodes/2026-W52/data/imports.jsonl` 存在
    （本包应当自带它；若缺失说明打包漏了）。

 ② 拿到的是**完整仓库**：确认该期 `data/` 或根目录 `data/` 下有它。

 ③ 自己重抓（需要能访问 GitHub，耗时较长）：
    python episodes/2026-W50/scripts/fetch_lean_imports.py

注意：拿到这个文件后，本期的所有结果都能**本地复现**，不再需要联网。
"""


def find_imports(root: Path, ep: str = "2026-W52") -> Path:
    r"""按 `CANDIDATES` 的顺序找 `imports.jsonl`，找不到就 `SystemExit`。

    `root` 可以是**仓库根**，也可以是**期目录**（会自动向上试一层）。
    两处都能工作，是为了同时支持「完整仓库」与「单期包」两种布局。
    """
    roots = [root]
    if root.name.startswith("2026-"):
        roots.append(root.parent.parent)          # <期目录> -> 仓库根
    for r in roots:
        for tpl, _desc in CANDIDATES:
            p = r / tpl.format(ep=ep)
            if p.exists():
                return p
    print(HINT)
    raise SystemExit(2)
