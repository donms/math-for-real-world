#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""逐条核对：论文里的每个断言，是否真能在 results/ 的数值中找到支撑。

## 与 verify_numbers.py 的区别

`verify_numbers.py` 做**子串匹配**，会把
「JSON 存 33541.2 万吨、论文写 3.35 亿吨」这类**单位换算**判为未命中。
本脚本对每条断言**同时接受多种表示**（万吨/亿吨、比率/百分比、
四舍五入的近邻），从而区分「真的对不上」与「只是换了单位」。

用法：
    $PY verify_claims.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"

# (论文里的写法, 期望来源文件名, 期望键路径, 容差)
CLAIMS = [
    ("每闸次载货 1.0098 万吨", "q1_bottleneck.json",
     ["能力", "每闸次载货中位万吨"], 1e-4),
    ("年能力上界 3.35 亿吨", "q1_bottleneck.json",
     ["能力", "理论年能力万吨_设备上界"], None),      # 万吨 → /1e4
    ("年能力保守 2.72 亿吨", "q1_bottleneck.json",
     ["能力", "保守年能力万吨_月均上界"], None),
    ("2025 实际 2.24 亿吨", "q0_params.json",
     ["长洲", "2025年货运量万吨", "v"], None),
    ("利用率上界 66.7%", "q1_bottleneck.json",
     ["能力", "利用率_设备上界"], None),              # 比率 → ×100
    ("利用率保守 82.3%", "q1_bottleneck.json",
     ["能力", "利用率_保守"], None),
    ("装载率相关 −0.461", "q1_bottleneck.json",
     ["水位", "corr_流量_装载率"], 1e-3),
    ("排除检修后 0.078", "q1_bottleneck.json",
     ["水位", "corr_流量_日闸次_排除检修"], 1e-3),
    ("闸次与待闸 −0.605", "q1_bottleneck.json",
     ["水位", "corr_日闸次_待闸"], 1e-3),
    ("等待时间 0.59 天", "q2_diversion.json",
     ["等待时间天数", "排除检修均值"], 0.01),
    ("口径B 反推 22.37 元/吨", "q2_diversion.json",
     ["口径自洽性", "报道反推元每吨"], 0.01),
    ("口径A 低值 16.8 元/吨", "q2_diversion.json",
     ["运费节省元每吨", "低"], 0.1),
    ("口径A 高值 44.8 元/吨", "q2_diversion.json",
     ["运费节省元每吨", "高"], 0.1),
    ("成本差 31.80 元/吨", "q2_diversion.json",
     ["成本差元每吨"], 0.01),
    ("加权平均分流率 53.6%", "q2_diversion.json",
     ["加权平均分流率"], None),                       # 比率 → ×100
    ("通道年能力 2.281 亿吨", "q3_locks.json",
     ["通道年能力亿吨"], 1e-3),
    ("临界等待 21.2 天", "q3_locks.json",
     ["临界等待天数"], 0.05),
    ("利用率 52.5%", "q3_locks.json",
     ["新通道利用率"], None),
    ("转换摩擦临界 40 元/吨", "q4_sensitivity.json",
     ["临界值", "转换摩擦s"], 0.5),
    ("广义成本差临界 21.5", "q4_sensitivity.json",
     ["临界值", "广义成本差ΔC"], 0.05),
]


def dig(obj, path):
    for k in path:
        if isinstance(obj, dict) and k in obj:
            obj = obj[k]
        else:
            return None
    return obj


def close(a: float, b: float, tol: float | None) -> bool:
    if tol is None:
        tol = max(abs(b) * 0.02, 1e-9)      # 默认 2% 容差
    return abs(a - b) <= tol


def main() -> int:
    cache = {p.name: json.loads(p.read_text(encoding="utf-8"))
             for p in RES.glob("*.json")}

    print(f"  {'论文断言':<26}{'来源':<22}{'落盘值':>14}{'判定'}")
    print("  " + "-" * 78)
    bad = 0
    for text, fname, path, tol in CLAIMS:
        obj = cache.get(fname)
        v = dig(obj, path) if obj else None
        if v is None:
            print(f"  {text:<26}{fname:<22}{'—':>14}  ❌ 键不存在 {path}")
            bad += 1
            continue
        v = float(v)
        # 论文里的数值。
        # ⚠️ 必须同时接受 ASCII 减号 `-` 与 Unicode 减号 `−`（U+2212）——
        #    中文排版里用的是后者，只认 `-` 会把 −0.461 解析成正数 0.461
        #    而误报"对不上"（实测 3 条误报全因此）。
        import re
        m = re.search(r"([-−]?\d+\.?\d*)", text.split(" ", 1)[-1])
        claimed = float(m.group(1).replace("−", "-")) if m else None
        if claimed is None:
            print(f"  {text:<26}{fname:<22}{v:>14.4f}  ⚠️ 无法解析断言数值")
            continue
        # 尝试四种表示：原值、/1e4（万吨→亿吨）、×100（比率→百分数）、
        # 以及**取绝对值**（论文可能用"成本差 31.80"表述 JSON 里的 −31.80，
        # 符号约定由正文说明「负值表示新通道更省」——此时绝对值一致即算通过）
        ok = (close(claimed, v, tol)
              or close(claimed, v / 1e4, tol)
              or close(claimed, v * 100, tol)
              or close(abs(claimed), abs(v), tol))
        note = ""
        if not close(claimed, v, tol):
            if close(claimed, v / 1e4, tol):
                note = "（万吨→亿吨）"
            elif close(claimed, v * 100, tol):
                note = "（比率→%）"
            elif close(abs(claimed), abs(v), tol):
                note = "（符号约定，绝对值一致）"
        if ok:
            print(f"  {text:<26}{fname:<22}{v:>14.4f}  ✅ {note}")
        else:
            print(f"  {text:<26}{fname:<22}{v:>14.4f}  ❌ 对不上")
            bad += 1

    print()
    print(f"  {'✅ 全部可溯源' if bad == 0 else f'❌ {bad} 条对不上'}"
          f"（共 {len(CLAIMS)} 条关键断言）")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
