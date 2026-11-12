#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""**反向验证**用：往手术计划里注入一个**假窗口**，看核对脚本能不能把它拦下来。

## 为什么必须做这一步

`build_episode_video.py` 的判据③是"成片里真的有仿真"：它拿成片与**术前备份**
在同一时刻比像素，仿真窗口必须**大幅不同**、对照窗口必须**基本一致**。
但这个判据**从来没有被反证过** —— 万一它永远返回"通过"呢？
（W52/W53/W54 反复出现的形态：检查器自身失效，而输出全绿。）

⇒ 注入一个**根本不存在仿真**的窗口：若核对仍然通过，说明判据是假的；
若它报"屏03 与术前备份差 0.0x < 12.0 ⇒ 仿真没进成片"并以 **exit 3** 退出，
才说明这道闸门真的会拦人。

## 用法

    $PY episodes\2026-W57\scripts\inject_fake_splice.py --variant bili
    & $PY scripts\build_episode_video.py --ep 2026-W57 --verify-only   # 期望 exit 3
    $PY episodes\2026-W57\scripts\inject_fake_splice.py --variant bili --restore
    & $PY scripts\build_episode_video.py --ep 2026-W57 --verify-only   # 期望 exit 0
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

EP = Path(__file__).resolve().parents[1]
TMP = EP / "_logs" / "_splice_tmp"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="bili")
    ap.add_argument("--screen", type=int, default=3)
    ap.add_argument("--t0", type=float, default=60.0)
    ap.add_argument("--t1", type=float, default=62.0)
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()

    plan_p = TMP / f"plan_{args.variant}.json"
    bak_p = TMP / f"plan_{args.variant}.json.bak_reverse"
    if not plan_p.exists():
        print(f"[X] 找不到手术计划 {plan_p}（先跑一次 splice）")
        return 2

    if args.restore:
        if not bak_p.exists():
            print(f"[X] 没有备份 {bak_p.name}，无法还原")
            return 2
        shutil.copy2(bak_p, plan_p)
        bak_p.unlink()
        plan = json.loads(plan_p.read_text(encoding="utf-8"))
        print(f"  [restore] 计划已还原：{len(plan['clips'])} 处仿真")
        for c in plan["clips"]:
            print(f"    屏{c['screen']:02d} {c['t0']:.3f}–{c['t1']:.3f}s "
                  f"← {c['file']}")
        return 0

    shutil.copy2(plan_p, bak_p)
    plan = json.loads(plan_p.read_text(encoding="utf-8"))
    n0 = len(plan["clips"])
    plan["clips"].append({
        "screen": args.screen, "head": "(注入的假窗口，此段本来没有仿真)",
        "file": "(none)", "src_dur": args.t1 - args.t0,
        "screen_dur": args.t1 - args.t0,
        "t0": args.t0, "t1": args.t1, "dur": args.t1 - args.t0,
        "frames": int(round((args.t1 - args.t0) * plan.get("fps", 30))),
    })
    plan_p.write_text(json.dumps(plan, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    print(f"  [inject] 计划里的仿真从 {n0} 处变成 {len(plan['clips'])} 处：")
    print(f"    新增假窗口：屏{args.screen:02d} t={args.t0}–{args.t1}s"
          f"（这一段成片与术前备份**应当完全一样**）")
    print(f"    备份：{bak_p.name}")
    print("  下一步：跑 build_episode_video --verify-only，"
          "**期望 exit 3**（判据要能拦下它）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
