#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第 ④ 步：抓取本期所需数据（可重复运行，带缓存）。

数据源
------
1. 统计局发布稿附件 Excel（分项同比/环比/累计）—— 当期
2. 发布稿列表分页 → 历史各月发布稿 → 逐个下载附件 → 拼出历史月度序列
   （国家数据 API `data.stats.gov.cn/easyquery.htm` 已对脚本返回 403，故不走 API）

用法
----
    $env:PYTHONUTF8=1
    $PY = "python"
    $PY episodes\\2026-W38\\scripts\\fetch_data.py --probe        # 只探测，不下载
    $PY episodes\\2026-W38\\scripts\\fetch_data.py --months 24    # 抓最近 24 个月
    $PY episodes\\2026-W38\\scripts\\fetch_data.py --months 24 --force

产出
----
    data/raw/*.xlsx            原始附件（只读，永不修改）
    data/clean/cpi_monthly.csv 拼接后的历史月度序列
    data/_fetch_log.txt        抓取日志（哪些拿到、哪些失败）
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import requests

EP = Path(__file__).resolve().parent.parent
RAW = EP / "data" / "raw"
CLEAN = EP / "data" / "clean"
LOG = EP / "data" / "_fetch_log.txt"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
H = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}
BASE = "https://www.stats.gov.cn"
LIST = BASE + "/sj/zxfb/"

for d in (RAW, CLEAN):
    d.mkdir(parents=True, exist_ok=True)

_log_lines: list[str] = []


def log(msg: str) -> None:
    print(msg)
    _log_lines.append(msg)


def flush_log() -> None:
    LOG.write_text("\n".join(_log_lines), encoding="utf-8")


def get(url: str, timeout: int = 30, binary: bool = False):
    r = requests.get(url, headers=H, timeout=timeout)
    if not binary:
        r.encoding = "utf-8"
    return r


# ------------------------------------------------------------------ 列表页
def list_releases(pages: int = 30) -> list[dict]:
    """翻发布稿列表（静态分页 `index_N.html`），收集 CPI/PPI 发布稿链接。

    实测：该栏目共 67 页，`index.html`、`index_1.html`、`index_2.html`… 均为静态页，
    每页约 45 条链接，其中每月 CPI/PPI 各 1 条。取前若干页即可覆盖历史序列。

    注意：`data.stats.gov.cn`（国家数据）已被 WAF 按 URL 规则整体拦截（403 UrlACL），
    因此**不走 API**，改为从发布稿附件逐个解析 —— 好处是口径与当期完全一致。
    """
    seen: dict[str, dict] = {}
    for i in range(pages):
        u = LIST + ("index.html" if i == 0 else f"index_{i}.html")
        try:
            r = get(u)
        except Exception as e:
            log(f"  [list] {u} 失败 {type(e).__name__}")
            continue
        for href, title in re.findall(
                r'href="(\./\d{6}/t\d{8}_\d+\.html)"[^>]*>\s*([^<]{6,120})', r.text):
            t = title.strip()
            if "居民消费价格" in t or "工业生产者出厂价格" in t:
                full = BASE + "/sj/zxfb/" + href.lstrip("./")
                seen[full] = {"url": full, "title": t}
        if i and i % 5 == 0:
            log(f"  已扫 {i + 1} 页，累计发现 {len(seen)} 条 CPI/PPI 发布稿")
        time.sleep(0.3)
    return list(seen.values())


def discover_via_search() -> list[dict]:
    """兜底：借助发布稿页面内的‘相关链接’与统计局检索页。

    若列表页拿不到足够历史，可在 sourcing/ 下手工放入 release_urls.txt
    （每行一个发布稿 URL），本函数会读取它。
    """
    out = []
    f = EP.parent.parent / "sourcing" / "release_urls.txt"
    if f.exists():
        for ln in f.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln.startswith("http"):
                out.append({"url": ln, "title": "(来自 release_urls.txt)"})
    return out


# ------------------------------------------------------------------ 附件下载
def attachments_of(page_url: str) -> list[str]:
    """取发布稿页面上的 xlsx 附件链接。"""
    r = get(page_url)
    links = re.findall(r'href="([^"]*P0\d+\.xlsx)"', r.text, re.I)
    out = []
    for l in dict.fromkeys(links):          # 去重保序
        if l.startswith("http"):
            out.append(l)
        else:
            out.append(page_url.rsplit("/", 1)[0] + "/" + l.lstrip("./"))
    return out


def download(url: str, dst: Path, force: bool = False) -> bool:
    if dst.exists() and not force and dst.stat().st_size > 2000:
        log(f"    [skip] {dst.name} 已存在")
        return True
    try:
        r = get(url, binary=True)
        if r.status_code != 200 or len(r.content) < 1000:
            log(f"    [fail] {url.split('/')[-1]} HTTP {r.status_code} {len(r.content)}B")
            return False
        dst.write_bytes(r.content)
        log(f"    [ok  ] {dst.name}  {len(r.content)}B")
        return True
    except Exception as e:
        log(f"    [fail] {url.split('/')[-1]} {type(e).__name__}")
        return False


# ------------------------------------------------------------------ 解析
def parse_attachment(path: Path) -> dict | None:
    """解析 CPI 附件 → {指标名: (环比, 同比, 累计)}。

    ⚠️ **数据陷阱（实测）**：1 月份的发布稿附件**只有 3 列**（环比、同比，无"1—N月累计"），
    其余月份是 4 列。若统一按 4 列解析，1 月会被静默丢弃，导致序列出现"每年 1 月缺失"的假象。
    这里按实际列数自适应：不足的字段置 None。
    """
    try:
        import openpyxl
    except ImportError:
        log("  [!] 需要 openpyxl")
        return None
    try:
        wb = openpyxl.load_workbook(path, data_only=True)
    except Exception as e:
        log(f"  [parse fail] {path.name}: {e}")
        return None
    ws = wb.worksheets[0]
    out: dict[str, tuple] = {}
    title = ""
    ncol = 0
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        cells = [("" if c is None else str(c).replace("\xa0", " ").strip()) for c in row]
        if i == 0:
            title = cells[0] if cells else ""
            continue
        if len(cells) < 3:               # 至少要有 指标名 + 环比 + 同比
            continue
        if cells[1].startswith("环比"):   # 表头行，用它确定列数
            ncol = len(cells)
            continue
        name = re.sub(r"\s+", "", cells[0])
        name = re.sub(r"^其中[:：]", "", name)
        if not name or name in ("按类别分",):
            continue
        vals = []
        for x in cells[1:4]:
            try:
                vals.append(float(x) if x not in ("", "-", "—", "…") else None)
            except ValueError:
                vals.append(None)
        while len(vals) < 3:
            vals.append(None)
        out[name] = tuple(vals)
    return {"title": title, "data": out, "file": path.name, "ncol": ncol}


def period_of(title: str, fallback: str) -> str:
    """从附件标题解析期间。

    ⚠️ CPI 标题为"…年N月份居民消费价格主要数据"，PPI 标题为"…年N月工业生产者价格主要数据"
    （**无"份"字**）。两种都要能解析，否则 PPI 会全部落到 fallback 而无法入库。
    """
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月份?", title or "")
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    return fallback


# ------------------------------------------------------------------ 主流程
def main() -> int:
    ap = argparse.ArgumentParser(description="用数学看世界 第④步 数据抓取")
    ap.add_argument("--months", type=int, default=24, help="目标历史月数（按发布稿数量近似）")
    ap.add_argument("--pages", type=int, default=30, help="列表页翻页数（每页约 1 个月）")
    ap.add_argument("--probe", action="store_true", help="只探测可达性，不下载历史")
    ap.add_argument("--force", action="store_true", help="覆盖已下载文件")
    args = ap.parse_args()

    log("=" * 68)
    log(f"第④步 数据抓取 · {EP.name}")
    log("=" * 68)

    # --- 1. 当期发布稿（已知链接） ---
    log("\n[1] 当期发布稿附件（2026-08 CPI）")
    cur = ("https://www.stats.gov.cn/sj/zxfb/202609/t20260909_1965263.html")
    got_cur = False
    for a in attachments_of(cur):
        dst = RAW / f"cpi_{Path(a).name}"
        if download(a, dst, args.force):
            got_cur = True
    if not got_cur:
        log("  [!] 当期附件未获取，检查网络或页面结构")

    # PPI 当期
    log("\n[2] 当期 PPI 发布稿附件（2026-08）")
    ppi_url = "https://www.stats.gov.cn/sj/zxfb/202609/t20260909_1965262.html"
    for a in attachments_of(ppi_url):
        download(a, RAW / f"ppi_{Path(a).name}", args.force)

    # --- 3. 历史序列 ---
    log(f"\n[3] 历史发布稿（目标 ≈{args.months} 个月）")
    rels = list_releases(args.pages) + discover_via_search()
    cpi_rels, ppi_rels = [], []
    for r in rels:
        (cpi_rels if "居民消费价格" in r["title"] else ppi_rels).append(r)
    log(f"  列表页发现：CPI {len(cpi_rels)} 条，PPI {len(ppi_rels)} 条")
    if not cpi_rels:
        log("  [!] 列表页未发现历史发布稿。")
        log("      对策：把历史发布稿 URL 手工写入 sourcing/release_urls.txt（每行一个），重跑本脚本。")
        log("      或在浏览器打开 https://www.stats.gov.cn/sj/zxfb/ 翻页，复制链接。")

    if not args.probe:
        for tag, lst in (("cpi", cpi_rels), ("ppi", ppi_rels)):
            log(f"\n  --- 下载 {tag.upper()} 历史附件 ---")
            for i, r in enumerate(lst[: args.months], 1):
                atts = attachments_of(r["url"])
                if not atts:
                    log(f"   [{i}] 无附件：{r['title'][:40]}")
                    continue
                for a in atts[:1]:
                    download(a, RAW / f"{tag}_hist_{Path(a).name}", args.force)
                time.sleep(0.5)

    # --- 4. 汇总为序列 ---
    log("\n[4] 汇总为历史月度序列")
    import csv as _csv

    CPI_KEYS = ["居民消费价格", "城市", "农村", "食品", "非食品", "消费品", "服务",
                "不包括食品和能源",
                "一、食品烟酒及在外餐饮", "粮食", "食用油", "鲜菜", "畜肉类", "猪肉",
                "牛肉", "羊肉", "水产品", "蛋类", "奶类", "鲜果", "卷烟", "酒类",
                "二、衣着", "服装", "鞋类",
                "三、居住", "租赁房房租", "水电燃料",
                "四、生活用品及服务", "家用器具", "家庭服务",
                "五、交通通信", "小汽车", "交通工具用能源", "交通工具使用和维修",
                "通信工具", "通信服务", "邮递服务",
                "六、教育文化娱乐", "教育服务", "旅行社及其他旅游服务",
                "七、医疗保健", "中药", "西药", "医疗服务",
                "八、其他用品及服务"]

    def series_from(prefix: str, keys: list[str], out_name: str, label: str) -> list[str]:
        """把 RAW 下某前缀的附件汇总成月度序列表。返回覆盖的月份列表。

        **按期去重**：当期附件与历史抓取可能覆盖同一月份（如 2026-08 同时来自
        `cpi_*.xlsx` 与 `cpi_hist_*.xlsx`），每期只保留一份，避免 (period,item) 重复。
        """
        by_period: dict[str, dict] = {}
        for p in sorted(RAW.glob(f"{prefix}*.xlsx")):
            rec = parse_attachment(p)
            if not rec:
                continue
            per = period_of(rec["title"], p.stem)
            if not re.match(r"^\d{4}-\d{2}$", per):
                log(f"  [skip] 无法识别期间：{p.name}（title={rec['title'][:24]!r}）")
                continue
            # 同一期多份文件时，取列数更多的（信息更全）
            old = by_period.get(per)
            if old is None or rec.get("ncol", 0) > old.get("ncol", 0):
                by_period[per] = rec
        if not by_period:
            log(f"  [!] {label}：没有可解析的附件")
            return []
        recs = sorted(by_period.items(), key=lambda x: x[0])
        rows = [["period", "item", "mom", "yoy", "ytd"]]
        got: dict[str, set] = {}
        for per, rec in recs:
            for k in keys:
                if k in rec["data"]:
                    mom, yoy, ytd = rec["data"][k]
                    rows.append([per, k, mom, yoy, ytd])
                    got.setdefault(k, set()).add(per)
        with (CLEAN / out_name).open("w", encoding="utf-8-sig", newline="") as f:
            _csv.writer(f).writerows(rows)
        months = [p for p, _ in recs]
        log(f"  -> data/clean/{out_name}（{len(rows)-1} 行，{len(months)} 个月）")
        log(f"     指标覆盖 Top5：" + "、".join(
            f"{k}({len(v)}月)" for k, v in sorted(got.items(), key=lambda x: -len(x[1]))[:5]))
        log(f"     月份：{months[0]} … {months[-1]}（{len(months)} 个）")
        # 连续性检查
        gaps = [m for m in months if f"{int(m[:4])}-{int(m[5:])-1:02d}" not in months
                and m[5:] != "01"]
        if gaps:
            log(f"     ⚠️ 与上月不连续的月份（除 1 月外）：{gaps}")
        return months

    cpi_months = series_from("cpi_", CPI_KEYS, "cpi_monthly.csv", "CPI")

    # PPI 附件：指标名与 CPI 不同，用同一套自适应解析
    recs_by_period: dict[str, dict] = {}
    for p in sorted(RAW.glob("ppi_*.xlsx")):
        rec = parse_attachment(p)
        if not rec:
            continue
        per = period_of(rec["title"], p.stem)
        if not re.match(r"^\d{4}-\d{2}$", per):
            continue
        old = recs_by_period.get(per)
        if old is None or rec.get("ncol", 0) > old.get("ncol", 0):
            recs_by_period[per] = rec
    if recs_by_period:
        recs = sorted(recs_by_period.items(), key=lambda x: x[0])
        rows = [["period", "item", "mom", "yoy", "ytd"]]
        for per, rec in recs:
            for k, v in rec["data"].items():
                rows.append([per, k, v[0], v[1], v[2]])
        with (CLEAN / "ppi_monthly.csv").open("w", encoding="utf-8-sig", newline="") as f:
            _csv.writer(f).writerows(rows)
        log(f"  -> data/clean/ppi_monthly.csv（{len(rows)-1} 行，{len(recs)} 个月）")
        log(f"     月份：{recs[0][0]} … {recs[-1][0]}")

    if not cpi_months:
        log("  [!] CPI 历史序列为空。对策见下方提示。")

    flush_log()
    log(f"\n日志 -> {LOG}")
    log("\n下一步：阅读 data/来源清单.md 的核查表，把实际结果回填；")
    log("        若历史序列不足，见上面的对策（release_urls.txt）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
