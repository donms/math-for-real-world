#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""W48 选题探源：**光遗传学**（2026 年诺贝尔生理学或医学奖）。

## 已确认的事实（2026-10-06）

2026 年诺贝尔生理学或医学奖授予 **Karl Deisseroth、Peter Hegemann、
Georg Nagel**，表彰「**光门控离子通道与光遗传学的发现**」。

| 关键事实 | 数值 |
|---|---|
| 衣藻趋光反应潜伏期 | **0.5 ms**（人眼需 ≥10 ms）|
| 通道视紫红质-2（ChR2）在蛙卵上的响应 | **0.2 ms** |
| Hegemann 提出"同一蛋白既捕光又当通道" | 1990 年代初 |
| Nagel + Hegemann 发表 ChR2 | **2003** |
| Deisseroth 在神经元中表达 | **2005** |
| 活体小鼠激活（运动皮层→胡须）| **2007** |
| "光遗传学"命名 | **2006** |
| 与利根川进合作激活记忆印迹 | **2012** |
| 成人脑神经元数 | **约 900 亿** |
| ChR2 激发波长 | 蓝光（约 **470 nm**）|

来源：诺贝尔奖委员会 2026 年科普材料（中文转述见新浪财经）。

## ★ 本选题的**核心数学机会**：光在脑组织里的传播

这是光遗传学里**最可计算**的一环，而且**不依赖实验数据**：

$$
\frac{\partial \Phi(\mathbf r,t)}{\partial t}
= \nabla\!\cdot\!\big[D(\mathbf r)\nabla\Phi\big]
- \mu_a(\mathbf r)\Phi + S(\mathbf r,t)
$$

* $\Phi$：光通量率；$D = 1/[3(\mu_a+\mu_s')]$：扩散系数；
* $\mu_a$：吸收系数；$\mu_s'$：**约化散射系数**（脑组织里散射远大于吸收）；
* $S$：光纤光源。

**为什么这题好**：
1. **参数有公认范围**（脑组织在 470 nm 下
   $\mu_a\approx0.1\text{–}0.3\ \text{cm}^{-1}$、
   $\mu_s'\approx10\text{–}20\ \text{cm}^{-1}$）⇒ **不必有实验数据也能算**；
2. **散射主导**（$\mu_s'\gg\mu_a$）⇒ **光被"糊"开**，
   这解释了"为什么光遗传学只能控制光源附近一小块" —— 一个真实的工程限制；
3. **可回答的关键问题**：
   * 光纤插到多深、多大功率，才能覆盖**指定的脑区体积**？
   * **单细胞精度**在什么深度上失效？
   * 蓝光（470 nm）vs 红光（630 nm）：**穿透深度差多少**？
     （这是把 ChR2 换成红移变体 CrR 的**定量理由**）

## 本脚本探什么

按 skill 的规矩（**先探数据源再评分**），实测三类：
1. **光学参数库**（组织光学、OCT）
2. **神经科学数据仓**（Allen Brain Atlas、MICrONS、Neurodata）
3. **通用数据集平台**（VPN 后新开的：OWID/AWS/HuggingFace/Figshare）

用法：
    $PY probe_w48.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# 脚本在 `episodes/2026-W48/scripts/`：
#   parents[0] = scripts  parents[1] = 2026-W48  parents[2] = episodes
#   parents[3] = 仓库根  ← 这个才对
# [!] 我先后写成 parents[1] 与 parents[2]，都少了一层，
#     两次报 `ModuleNotFoundError: net_resolve`。
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from net_resolve import open_url                                 # noqa: E402

OUT = ROOT / "episodes" / "2026-W48" / "sourcing"
OUT.mkdir(parents=True, exist_ok=True)

CANDS: list[tuple[str, str, str]] = [
    # ── A. 神经科学数据仓 ──
    ("A 神经数据", "Allen Brain Atlas API（小鼠脑图谱）",
     "https://api.brain-map.org/api/v2/data/Structure/query.json"
     "?criteria=model::Structure,rma::criteria,[ontology_id$eq1]"
     "&num_rows=20"),
    ("A 神经数据", "Allen Cell Types 检索",
     "https://api.brain-map.org/api/v2/data/query.json"
     "?criteria=model::ApiCellTypesSpecimenDetail,num_rows=5"),
    ("A 神经数据", "MICrONS 数据集（HuggingFace）",
     "https://huggingface.co/api/datasets?search=microns&limit=5"),
    ("A 神经数据", "Neurodata / DANDI 检索",
     "https://api.dandiarchive.org/api/dandisets/?page_size=5"),
    ("A 神经数据", "OpenNeuro 检索",
     "https://openneuro.org/crn/graphql"),
    # ── B. 光学 / 组织参数 ──
    ("B 光学参数", "OMLC 组织光学参数（俄勒冈医学激光中心）",
     "https://omlc.org/spectra/"),
    ("B 光学参数", "NIST 光谱数据库（ChR2 激发/发射参考）",
     "https://physics.nist.gov/cgi-bin/ASD/lines1.pl?spectra=H"
     "&limits_type=0&low_w=400&upp_w=500&unit=1&submit=Retrieve+Data"
     "&format=2&line_out=0&en_unit=0&output=0&bibrefs=1&page_size=15"),
    ("B 光学参数", "ChR2 吸收光谱（FPbase 荧光蛋白库）",
     "https://www.fpbase.org/api/proteins/?name__icontains=channelrhodopsin"
     "&format=json"),
    ("B 光学参数", "FPbase 全库（荧光蛋白分光参数）",
     "https://www.fpbase.org/api/proteins/?format=json&page_size=20"),
    # ── C. 通用平台（VPN 后新开）──
    ("C 通用", "HuggingFace 检索 optogenetics",
     "https://huggingface.co/api/datasets?search=optogenetics&limit=10"),
    ("C 通用", "HuggingFace 检索 neuroscience",
     "https://huggingface.co/api/datasets?search=neuroscience&limit=10"),
    ("C 通用", "Figshare 检索 optogenetics",
     "https://api.figshare.com/v2/articles/search?search_for=optogenetics"
     "&page_size=10"),
    ("C 通用", "Zenodo 检索 optogenetics",
     "https://zenodo.org/api/records?q=optogenetics&size=5"),
    ("C 通用", "PubMed E-utilities（文献计数）",
     "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
     "?db=pubmed&term=optogenetics&retmode=json&retmax=5"),
    ("C 通用", "World Bank（对照：生物医学 R&D 支出）",
     "https://api.worldbank.org/v2/country/CHN;USA;DEU/indicator/"
     "GB.XPD.RSDV.GD.ZS?format=json&per_page=200&date=2000:2023"),
]


def rows(body: bytes) -> int:
    try:
        d = json.loads(body.decode("utf-8", "ignore"))
    except Exception:                                            # noqa: BLE001
        return body.decode("utf-8", "ignore").count("\n")
    if isinstance(d, list):
        if len(d) == 2 and isinstance(d[1], list):
            return len(d[1])
        return len(d)
    if isinstance(d, dict):
        for k in ("value", "data", "msg", "results", "records", "items",
                  "datasets", "esearchresult"):
            v = d.get(k)
            if isinstance(v, list):
                return len(v)
            if isinstance(v, dict):
                return len(v)
        return len(d)
    return 0


def main() -> int:
    print("=" * 96)
    print("  W48 选题探源 · 光遗传学（2026 诺贝尔生理学或医学奖）")
    print("=" * 96)
    res = []
    cur = None
    for grp, name, url in CANDS:
        if grp != cur:
            print(f"\n  ── {grp} ──")
            cur = grp
        t0 = time.time()
        st, n, err = 0, 0, ""
        try:
            r = open_url(url, timeout=40, tries=2)
            b = r.read()
            st, n = r.status, rows(b)
        except Exception as e:                                   # noqa: BLE001
            err = f"{type(e).__name__}: {str(e)[:44]}"
        ok = st == 200 and n >= 1
        el = time.time() - t0
        print(f"  [{'OK ' if ok else 'X  '}] {name:<40}{st:>4} "
              f"{n:>7} 行 {el:>5.1f}s {err}")
        res.append({"grp": grp, "name": name, "url": url, "status": st,
                    "rows": n, "ok": ok, "sec": round(el, 1), "err": err})

    ok = [r for r in res if r["ok"]]
    print(f"\n{'='*96}")
    print(f"  可用 {len(ok)} / {len(res)}")
    for g in dict.fromkeys(r["grp"] for r in res):
        good = [r for r in ok if r["grp"] == g]
        print(f"     {g}: {len(good)}/{sum(1 for r in res if r['grp']==g)}")
        for r in good:
            print(f"        [OK] {r['name']}")
    p = OUT / "w48_probe.json"
    p.write_text(json.dumps(res, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    print(f"\n  -> {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
