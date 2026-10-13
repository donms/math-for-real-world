#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W50 探源：**流式抽取 Lean 源码里的 `import` 依赖**。

## 为什么需要"流式"

`openai/math` 的 `lean/` 目录有：

| 项 | 值 |
|---|---|
| 文件数 | **60209** |
| 合计 | **1071.2 MB** |

⇒ **不能直接下载**（前面 git fetch 拉到 9 分钟被远端断开）。
GitHub API 逐个取文件也不行（6 万次请求会打爆限额）。

## 方案：**边下边解析，只留结果**

`codeload.github.com` 的 tarball 是 **tar.gz 流**。
用 `tarfile` 的 **stream 模式**（`r|gz`）顺序读取：

* 遇到 `/lean/**.lean` ⇒ **只抠出 `import` 行**，正文丢弃；
* 遇到 `reasoning_traces/`、`preprints/` ⇒ **直接跳过**（不读入内存）；
* 全程**不落盘**，内存里只累积依赖边。

⇒ 拿到**完整依赖图**（这就是本期的核心数据），磁盘占用接近 0。

## [!] 已知风险

前面试过 `git fetch`（SSH，538s 后 `early EOF`）与 HTTPS tarball
（SSL 超时）⇒ **本机到 GitHub 的大文件传输不稳定**。
故本脚本：

1. **带断点重试**（多次尝试，每次从头流，但已解析的模块做增量合并）；
2. **分模块统计进度**，即使中途断开也能看到已完成多少；
3. 结果**边解析边落盘**（`data/imports.jsonl`），断掉不用重来。

用法：
    $PY fetch_lean_imports.py
    $PY fetch_lean_imports.py --tries 5
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EP = ROOT / "episodes" / "2026-W50"
DATA = EP / "data"
DATA.mkdir(parents=True, exist_ok=True)

TARBALL = "https://codeload.github.com/openai/math/tar.gz/refs/heads/main"
OUT = DATA / "imports.jsonl"
STATE = DATA / "fetch_state.json"

# Lean 的 import 行形如：`import OAI.Combinatorics.Foo.Bar`
# [!] 必须是**字符串**正则，不能是 `rb"..."` ——
#     字节串字面量只允许 ASCII，而 Lean 标识符可能含 `«»`（guillemet）。
IMP_RE = re.compile(r"^\s*import\s+([A-Za-z0-9_.«»]+)\s*$", re.M)


def open_stream(url: str, timeout: int = 120):
    r"""打开裸流（不走 net_resolve 的 text 解码）。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    from net_resolve import open_url
    return open_url(url, timeout=timeout, tries=1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tries", type=int, default=4)
    ap.add_argument("--max-mb", type=float, default=0,
                    help=">0 时只读到这么多 MB 就停（冒烟测试）")
    args = ap.parse_args()

    print("=" * 94)
    print("  W50 探源：流式抽取 Lean import 依赖")
    print("=" * 94)
    print(f"\n  源：{TARBALL}")
    print(f"  输出：{OUT.relative_to(ROOT)}（每行一个模块）\n")

    done: dict[str, list[str]] = {}
    if STATE.exists():
        try:
            done = json.loads(STATE.read_text(encoding="utf-8")).get(
                "modules", {})
            print(f"  [续跑] 已有 {len(done)} 个模块")
        except Exception:                                        # noqa: BLE001
            done = {}

    n_lean = n_other = 0
    n_bytes = 0
    t0 = time.time()
    last_err = ""
    for attempt in range(1, args.tries + 1):
        print(f"\n  ── 第 {attempt}/{args.tries} 次尝试 ──")
        try:
            r = open_stream(TARBALL)
            # tarfile 的流模式：顺序读，不能 seek
            tf = tarfile.open(fileobj=r, mode="r|gz")
            for m in tf:
                if not m.isfile():
                    continue
                name = m.name
                if not name.endswith(".lean"):
                    n_other += 1
                    continue
                n_lean += 1
                f = tf.extractfile(m)
                if f is None:
                    continue
                body = f.read()
                n_bytes += len(body)
                if args.max_mb and n_bytes > args.max_mb * 1e6:
                    print(f"    [冒烟] 读到 {n_bytes/1e6:.1f} MB，停止")
                    raise StopIteration
                # 模块名 = tar 内路径去掉顶层目录与 .lean，斜杠换点
                mod = name.split("/", 1)[-1][:-5].replace("/", ".")
                deps = IMP_RE.findall(body.decode("utf-8", "ignore"))
                done[mod] = deps
                if n_lean % 2000 == 0:
                    el = time.time() - t0
                    print(f"    {n_lean:>6} 个 .lean  "
                          f"{n_bytes/1e6:>7.1f} MB  {el:>6.0f}s  "
                          f"当前 {mod[:52]}")
            break
        except StopIteration:
            break
        except Exception as e:                                   # noqa: BLE001
            last_err = f"{type(e).__name__}: {str(e)[:60]}"
            print(f"    [!] 中断：{last_err}")
            # 边解析边落盘 —— 断掉不用重来
            with OUT.open("w", encoding="utf-8") as fo:
                for k, v in done.items():
                    fo.write(json.dumps({"mod": k, "deps": v},
                                        ensure_ascii=False) + "\n")
            STATE.write_text(json.dumps(
                {"modules": done, "n_lean": n_lean,
                 "bytes": n_bytes, "last_err": last_err},
                ensure_ascii=False), encoding="utf-8")
            print(f"    [存] 已落盘 {len(done)} 个模块")
            time.sleep(5)

    # 落盘
    with OUT.open("w", encoding="utf-8") as fo:
        for k, v in done.items():
            fo.write(json.dumps({"mod": k, "deps": v},
                                ensure_ascii=False) + "\n")
    n_edges = sum(len(v) for v in done.values())
    print(f"\n  {'='*90}")
    print(f"  .lean 文件 {n_lean}  读过 {n_bytes/1e6:.1f} MB  "
          f"耗时 {time.time()-t0:.0f}s")
    print(f"  **模块 {len(done)}  依赖边 {n_edges}**")
    print(f"  -> {OUT.relative_to(ROOT)}")
    if last_err:
        print(f"  [!] 最后一次错误：{last_err}（结果可能不完整）")
    STATE.write_text(json.dumps(
        {"modules": done, "n_lean": n_lean, "bytes": n_bytes,
         "n_edges": n_edges, "last_err": last_err},
        ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
