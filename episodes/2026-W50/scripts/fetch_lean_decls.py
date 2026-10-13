#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W50 · 声明级抽取（theorem / lemma）—— 增量落盘版。

## 为什么有这一版（第一版的失败值得记下来）

第一版扫完全程（2016.7 MB / 115894 个 .lean，抽出
theorem 1101212 / lemma 1342346 = 244 万条声明），
但**落盘只有 29951 个模块** —— 丢了 73%。

**根因**：第一版只在两处写文件：① 捕获异常时；② 循环正常结束后。
而第 ② 处要序列化十几万模块的 JSON，耗时几十秒 ——
**超时恰好发生在写入期间**，内存里的成果大部分没落地。

### 修法：边抽边 append

* 维护 pending 列表（本批未落盘的模块）；
* 每 1500 个就 append 一模块一行（不重写整个文件）；
* 写放大 O(1)，中断最多丢 1500 个。

> 通用教训：长任务的落盘时机必须与超时风险匹配。
> 「结束时统一写」在大数据量下等于「不写」——
> 因为最可能中断的时刻，正是最需要写的时刻。

## 抽取规则（必须写明，否则不可复现）

按行首匹配（允许前导空白）：
  theorem NAME / lemma NAME
  private|protected|noncomputable theorem|lemma NAME
  @[attr] theorem|lemma NAME

不做的事（如实声明）：
* 不解析 namespace => 记的是局部名，非全限定名；
* 不抽 def/structure/instance/abbrev => 聚焦可被引用的定理与引理；
* 不做「定理 A 引用了引理 B」=> 推理链口径是【模块级】，论文必须写明。

用法：
    $PY fetch_lean_decls.py
"""
from __future__ import annotations

import argparse
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
OUT = DATA / "declarations.jsonl"
STATE = DATA / "decls_state.json"
IMP = DATA / "imports.jsonl"

DECL_RE = re.compile(
    r"^[ \t]*(?:@\[[^\]]*\][ \t]*)*"
    r"(?:(?:private|protected|noncomputable|unsafe|partial)[ \t]+)*"
    r"(theorem|lemma)[ \t]+"
    r"([A-Za-z_\u00c0-\u024f\u0370-\u03ff\u1e00-\u1eff'"
    r"\u2070-\u209f\u2100-\u214f][A-Za-z0-9_'!\?\u00c0-\u024f"
    r"\u0370-\u03ff\u1e00-\u1eff\u2070-\u209f\u2100-\u214f]*)",
    re.M)


def open_stream(url, timeout=150):
    sys.path.insert(0, str(ROOT / "scripts"))
    from net_resolve import open_url
    return open_url(url, timeout=timeout, tries=1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tries", type=int, default=4)
    ap.add_argument("--flush", type=int, default=1500)
    ap.add_argument("--max-mb", type=float, default=0)
    ap.add_argument("--fresh", action="store_true")
    args = ap.parse_args()

    print("=" * 96)
    print("  W50 声明级抽取（增量落盘版）")
    print("=" * 96)

    want = set()
    if IMP.exists():
        with IMP.open(encoding="utf-8") as f:
            for ln in f:
                want.add(json.loads(ln)["mod"])
        print("\n  只抽 import 图里的 %d 个模块（保证同口径）" % len(want))

    if args.fresh and OUT.exists():
        OUT.unlink()
        print("  [--fresh] 已清空旧结果")

    done = {}
    if OUT.exists():
        with OUT.open(encoding="utf-8") as f:
            for ln in f:
                try:
                    d = json.loads(ln)
                    done[d["mod"]] = {"decls": d["decls"],
                                      "n_theorem": d["n_theorem"],
                                      "n_lemma": d["n_lemma"]}
                except Exception:
                    pass
        print("  [续跑] 已落盘 %d 个模块" % len(done))

    pending = []

    def flush():
        if not pending:
            return
        with OUT.open("a", encoding="utf-8") as fa:
            for k in pending:
                v = done[k]
                fa.write(json.dumps({"mod": k, **v},
                                    ensure_ascii=False) + "\n")
        pending.clear()

    n_lean = n_new = n_bytes = 0
    tot_th = tot_lm = 0
    last_err = ""
    t0 = time.time()
    for attempt in range(1, args.tries + 1):
        print("\n  == 第 %d/%d 次 ==" % (attempt, args.tries))
        try:
            r = open_stream(TARBALL)
            tf = tarfile.open(fileobj=r, mode="r|gz")
            for m in tf:
                if not m.isfile() or not m.name.endswith(".lean"):
                    continue
                n_lean += 1
                mod = m.name.split("/", 1)[-1][:-5].replace("/", ".")
                if want and mod not in want:
                    continue
                if mod in done:
                    continue
                f = tf.extractfile(m)
                if f is None:
                    continue
                body = f.read()
                n_bytes += len(body)
                if args.max_mb and n_bytes > args.max_mb * 1e6:
                    print("    [冒烟] %.1f MB，停" % (n_bytes / 1e6))
                    raise StopIteration
                txt = body.decode("utf-8", "ignore")
                decls = [[mm.group(1), mm.group(2),
                          txt[:mm.start()].count("\n") + 1]
                         for mm in DECL_RE.finditer(txt)]
                th = sum(1 for d in decls if d[0] == "theorem")
                lm = len(decls) - th
                tot_th += th
                tot_lm += lm
                done[mod] = {"decls": decls, "n_theorem": th, "n_lemma": lm}
                pending.append(mod)
                n_new += 1
                if len(pending) >= args.flush:
                    flush()
                    print("    %6d .lean  新抽 %6d  累计落盘 %6d  "
                          "%7.1f MB  %5.0fs  th %d/lm %d"
                          % (n_lean, n_new, len(done), n_bytes / 1e6,
                             time.time() - t0, tot_th, tot_lm))
            flush()
            break
        except StopIteration:
            flush()
            break
        except Exception as e:
            last_err = "%s: %s" % (type(e).__name__, str(e)[:60])
            print("    [!] 中断：%s" % last_err)
            flush()
            print("    [存] 累计落盘 %d 个（增量写，成果已保住）" % len(done))
            time.sleep(5)

    flush()
    th_all = sum(v["n_theorem"] for v in done.values())
    lm_all = sum(v["n_lemma"] for v in done.values())
    print("\n  " + "=" * 88)
    print("  .lean 扫过 %d   本次新抽 %d   落盘模块 %d"
          % (n_lean, n_new, len(done)))
    print("  theorem %d  /  lemma %d  合计 %d" % (th_all, lm_all,
                                                  th_all + lm_all))
    print("  读取 %.1f MB  耗时 %.0fs" % (n_bytes / 1e6, time.time() - t0))
    print("  -> %s" % OUT.relative_to(ROOT))
    if last_err:
        print("  [!] 最后错误：%s（结果可能不完整）" % last_err)
    STATE.write_text(json.dumps(
        {"n_lean": n_lean, "bytes": n_bytes, "n_modules": len(done),
         "n_theorem": th_all, "n_lemma": lm_all, "last_err": last_err},
        ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
