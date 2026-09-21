#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""抓取「长洲船闸通航情况简报」时间序列（交通运输部珠江航务管理局）。

## 为什么这个数据源是本期选题的基石

选题 A（平陆运河分流效应）要回答「新运河开通后西江货流怎么重排」。
长洲是**西江干线主瓶颈**，而它的运营指标**逐月官方发布** ——
意味着模型给出的分流预测**半年后能被真实数据检验**。

## 站点结构（已实测）

* 列表页：`https://zjhy.mot.gov.cn/zzhxxgk/index_N.html`（N=1,2,3,…，共 67 页，每页 21 条）
* 文章页：`/zzhxxgk/jigou/<处室>/<年月>/t<年月日>_<ID>.html`
* ⚠️ **文章 ID 无法推算**，必须靠列表页枚举
* ⚠️ 列表页与文章页都需**关闭证书校验**（该站证书链在本机不被信任）
* ⚠️ 处室子目录（`/jigou/hdgc/` 等）是 **JS 渲染的空壳**，直接访问只有 6 字节

## 用法

    $PY fetch_changzhou.py --pages 12          # 扫前 12 页（足够覆盖近两年）
    $PY fetch_changzhou.py --pages 67          # 全扫
    $PY fetch_changzhou.py --pages 12 --parse  # 扫完并解析成一行一期的汇总
"""
from __future__ import annotations

import argparse
import json
import re
import socket
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
LIST = "https://zjhy.mot.gov.cn/zzhxxgk/index_{}.html"
BASE = "https://zjhy.mot.gov.cn"

socket.setdefaulttimeout(25)
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

TITLE_RE = re.compile(r'<a[^>]*href="([^"]+)"[^>]*title="([^"]*长洲[^"]*)"')


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, context=CTX) as r:
        return r.read().decode("utf-8", "ignore")


def fix_url(href: str) -> str:
    r"""把列表页里的相对链接补成完整 URL。

    ⚠️ 踩过的坑：列表页给的是 `/jigou/hdgc/202607/t...html`，
    但**正确的完整路径要带 `/zzhxxgk` 前缀**
    （`/zzhxxgk/jigou/hdgc/...`）—— 直接用 urljoin 会得到 404。
    实测：不带前缀一律 404，带上就 200。
    """
    if href.startswith("http"):
        return href
    if not href.startswith("/"):
        href = "/" + href
    if not href.startswith("/zzhxxgk/"):
        href = "/zzhxxgk" + href
    return urllib.parse.urljoin(BASE, href)


def crawl(pages: int, delay: float = 0.8) -> list[dict]:
    """扫列表页，收集「长洲」相关文章。**断点续跑**：已抓过的 URL 跳过。"""
    idx_p = ROOT / "data" / "_changzhou_index.json"
    found: dict[str, dict] = {}
    if idx_p.exists():
        for it in json.loads(idx_p.read_text(encoding="utf-8")):
            found[it["url"]] = it
        print(f"  续跑：已有 {len(found)} 条索引")

    for n in range(1, pages + 1):
        url = LIST.format(n) if n > 1 else LIST.format(1).replace("index_1", "index")
        try:
            html = get(url)
        except Exception as e:                                 # noqa: BLE001
            print(f"  [{n:>2}/{pages}] ❌ {type(e).__name__}")
            time.sleep(delay)
            continue
        hits = TITLE_RE.findall(html)
        # 列表页里还有不带 title 属性的链接，兜底用锚文本
        if not hits:
            hits = [(h, t) for h, t in re.findall(
                r'<a[^>]*href="([^"]+)"[^>]*>([^<]*长洲[^<]*)</a>', html)]
        new = 0
        for href, title in hits:
            full = fix_url(href)
            if full not in found:
                found[full] = {"url": full, "title": title.strip()}
                new += 1
        print(f"  [{n:>2}/{pages}] 命中 {len(hits)} 条（新增 {new}），"
              f"累计 {len(found)}")
        idx_p.parent.mkdir(parents=True, exist_ok=True)
        idx_p.write_text(json.dumps(list(found.values()), ensure_ascii=False,
                                    indent=2), encoding="utf-8")
        time.sleep(delay)
    return list(found.values())


def fetch_bodies(items: list[dict], delay: float = 0.8) -> None:
    """下载文章正文，落盘 `data/raw/changzhou/*.txt`。已有则跳过。"""
    out = RAW / "changzhou"
    out.mkdir(parents=True, exist_ok=True)
    for i, it in enumerate(items, 1):
        name = re.sub(r"[^\w\u4e00-\u9fff]+", "_", it["title"])[:60] + ".txt"
        p = out / name
        if p.exists():
            continue
        try:
            html = get(it["url"])
        except Exception as e:                                 # noqa: BLE001
            print(f"  [{i:>3}] ❌ {it['title'][:26]}  {type(e).__name__}")
            time.sleep(delay)
            continue
        # 去脚本/样式，正文提取
        body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html,
                      flags=re.S | re.I)
        body = re.sub(r"<[^>]+>", "\n", body)
        body = re.sub(r"&nbsp;?", " ", body)
        body = re.sub(r"\n{2,}", "\n", body).strip()
        p.write_text(f"# {it['title']}\n# {it['url']}\n\n{body}",
                     encoding="utf-8")
        print(f"  [{i:>3}] ✅ {it['title'][:34]}  ({len(body)} 字符)")
        time.sleep(delay)


NUMPAT = r"([\d,]+(?:\.\d+)?)"


def period_of(head: str) -> str:
    r"""从简报标题解析「期」，并**区分月报/季报/半年报/年报**。

    ⚠️ 踩过的坑：早期只写 `(\\d{4})年` 就当成期号，
    于是**年报、季报、半年报全部被标成「2025年」互相覆盖** ——
    汇总表里出现三行都叫「2025年」，无法判断哪行是哪期。
    """
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月", head)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"          # 月报
    m = re.search(r"(\d{4})\s*年\s*(?:第)?([一二三四1-4])\s*季度", head)
    if m:
        q = {"一": 1, "二": 2, "三": 3, "四": 4}.get(m.group(2), m.group(2))
        return f"{m.group(1)}Q{q}"                            # 季报
    m = re.search(r"(\d{4})\s*年\s*(上半年|下半年)", head)
    if m:
        return f"{m.group(1)}H1" if m.group(2) == "上半年" else f"{m.group(1)}H2"
    m = re.search(r"(\d{4})\s*年度?", head)
    if m:
        return f"{m.group(1)}年度"                            # 年报
    return head[:16]


def grab_metrics(t: str) -> dict:
    r"""按简报的**标准句式**抓指标，而不是"关键词就近取数"。

    ⚠️ 踩过的坑：早期用「关键词 + 附近第一个数字」，结果
    **2025-08 的货运量抓成 444.43 万吨**（那是**上行**的数字），
    而总量是上行 444.43 + 下行 1700.43 = **2144.86 万吨** ——
    量级差 5 倍，若不核对就会被当成真实异常值。

    简报的标准句式（月报/季报/半年报/年报通用）：
      「长洲船闸共运行 10617 闸次，过闸船舶 57534 艘次，
        过闸货运量 10766.66 万吨，过闸船舶总核载 17655.06 万吨，
        过闸船舶平均核载 3068.63 吨」「日均待闸船舶数为 324 艘」
    分货种段：
      「上行过闸船舶 28901 艘次，过闸货运量 2669.59 万吨…」
      「下行过闸船舶 28633 艘次，过闸货运量 8097.06 万吨…」

    故用「短语 + 同一句内的数字」精确匹配，并**用上+下校验总量**。
    """
    def num(pat: str) -> str:
        m = re.search(pat, t)
        return m.group(1).replace(",", "") if m else ""

    tot = num(r"过闸货运量\s*([\d,]+(?:\.\d+)?)\s*万吨")
    up = num(r"上行过闸船舶\s*[\d,]+\s*艘次，过闸货运量\s*([\d,]+(?:\.\d+)?)\s*万吨")
    dn = num(r"下行过闸船舶\s*[\d,]+\s*艘次，过闸货运量\s*([\d,]+(?:\.\d+)?)\s*万吨")
    # 上+下 合计，用于校验总量是否抓对（容差 2%）
    chk = ""
    try:
        if up and dn and tot:
            s = float(up) + float(dn)
            chk = "OK" if abs(s - float(tot)) / float(tot) < 0.02 else \
                  f"不符(上+下={s:.0f} vs 总={tot})"
    except ValueError:
        pass

    return {
        "闸次": num(r"共运行\s*([\d,]+)\s*闸次"),
        "艘次": num(r"过闸船舶\s*([\d,]+)\s*艘次"),
        "货运量万吨": tot,
        "总核载万吨": num(r"过闸船舶总核载\s*([\d,]+(?:\.\d+)?)\s*万吨"),
        "平均核载吨": num(r"平均核载\s*([\d,]+(?:\.\d+)?)\s*吨"),
        "日均待闸艘": num(r"日均待闸船舶数(?:为)?\s*([\d,]+)\s*艘"),
        "最高待闸艘": num(r"待闸船舶数最高值(?:为)?\s*([\d,]+)\s*艘"),
        "出库流量": num(r"日均出库流量(?:为)?\s*([\d,]+(?:\.\d+)?)\s*m"),
        "上行万吨": up, "下行万吨": dn, "校验": chk,
    }


def parse_all() -> None:
    """从已下载的简报里抽出关键指标，汇总成一行一期。

    只保留**含「…长洲船闸通航情况简报」字样**的简报；
    其余是新闻通稿（无完整指标），跳过并在表末列出。
    """
    d = RAW / "changzhou"
    files = sorted(d.glob("*.txt"))
    rows, skipped = [], []
    for f in files:
        t = f.read_text(encoding="utf-8")
        head = t.splitlines()[0].lstrip("# ").strip()
        if not re.search(r"(月|季度|上半年|下半年|年度)\s*长洲船闸通航情况简报", head):
            skipped.append(head)
            continue
        row = {"期": period_of(head)}
        row.update(grab_metrics(t))
        rows.append(row)
    rows.sort(key=lambda r: r["期"])
    out = ROOT / "data" / "长洲简报汇总.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return 0.0

    print(f"\n  解析 {len(rows)} 期 → {out}")
    print(f"  {'期':<10}{'闸次':>7}{'艘次':>8}{'货运量':>10}{'平均核载':>9}"
          f"{'日均待闸':>9}  校验")
    print("  " + "-" * 66)
    for r in rows:
        print(f"  {r['期']:<10}{num(r['闸次']):>7.0f}{num(r['艘次']):>8.0f}"
              f"{num(r['货运量万吨']):>10.1f}{num(r['平均核载吨']):>9.0f}"
              f"{num(r['日均待闸艘']):>9.0f}  {r['校验']}")
    bad = [r["期"] for r in rows if r["校验"] not in ("", "OK")]
    if bad:
        print(f"\n  ❌ 总量校验不符的期：{bad} —— 需回原文核对")
    if skipped:
        print(f"  跳过 {len(skipped)} 篇（新闻通稿，无完整指标）")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=12)
    ap.add_argument("--parse", action="store_true")
    ap.add_argument("--index-only", action="store_true")
    args = ap.parse_args()

    print(f"  扫描列表页 1..{args.pages}")
    items = crawl(args.pages)
    print(f"\n  共找到 {len(items)} 篇「长洲」相关文章")
    for it in items[:40]:
        print(f"    · {it['title']}")

    if not args.index_only:
        print(f"\n  下载正文（已存在的跳过）")
        fetch_bodies(items)
    if args.parse:
        parse_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
