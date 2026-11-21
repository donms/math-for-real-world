"""行情数据与回撤工具。

数据源（均为公开接口）
--------------------
* Yahoo Finance `GC=F`：美元金价（COMEX 期货主力连续），日线
* 上海黄金交易所 `Au99.99`：人民币金价（元/克），日线
* Yahoo Finance `CNY=X`：美元兑人民币

缓存到 data/*.json，避免重复请求。
"""
from __future__ import annotations

import json
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

EP = Path(__file__).resolve().parents[1]
DATA = EP / "data"
DATA.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
OZ_TO_G = 31.1035


def _get_json(url: str, timeout: int = 40) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


YAHOO_HOSTS = ("query2.finance.yahoo.com", "query1.finance.yahoo.com")


def yahoo(sym: str, rng: str = "10y", interval: str = "1d") -> list[list]:
    """返回 [[YYYY-MM-DD, close], ...]。

    两个节点轮流试：Yahoo 会对单个节点限流，换一个往往就通了。
    """
    d, last_err = None, None
    for host in YAHOO_HOSTS:
        url = (f"https://{host}/v8/finance/chart/{sym}"
               f"?range={rng}&interval={interval}")
        try:
            d = _get_json(url)
            break
        except Exception as e:      # noqa: BLE001
            last_err = e
    if d is None:
        raise RuntimeError(f"Yahoo 取数失败（两个节点都不通）：{last_err}")
    res = d["chart"]["result"][0]
    ts, q = res["timestamp"], res["indicators"]["quote"][0]
    out = []
    for t, c in zip(ts, q["close"]):
        if c is None:
            continue
        dt = datetime.fromtimestamp(t, timezone.utc).date()
        out.append([dt.isoformat(), round(float(c), 4)])
    return out


def sge(inst: str = "Au99.99") -> list[list]:
    """上金所日线，返回 [[YYYY-MM-DD, 收盘], ...]。

    接口返回 [日期, 开, 收, 低, 高]（据末条与公开行情比对确认）。
    """
    url = f"https://www.sge.com.cn/graph/Dailyhq?instid={inst}"
    d = _get_json(url)
    rows = d.get("time", [])
    out = []
    for row in rows:
        if len(row) < 3 or not row[1]:
            continue
        out.append([row[0], round(float(row[2]), 4)])
    return out


def load_cached(name: str, fetcher, *args, **kw) -> list[list]:
    p = DATA / f"{name}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    data = fetcher(*args, **kw)
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


# ---------------------------------------------------------------- 回撤
def drawdown_series(px: list[float]) -> list[float]:
    """从峰值算起的回撤序列（负数）。"""
    out, peak = [], px[0]
    for p in px:
        peak = max(peak, p)
        out.append(p / peak - 1.0)
    return out


def max_drawdown(px: list[float]) -> float:
    return min(drawdown_series(px))


def episodes(dates: list[str], px: list[float],
             start_th: float = -0.15, end_th: float = -0.05) -> list[dict]:
    """带滞回的回撤事件切分。

    跌破 start_th 开事件；回升到 end_th 以上结案。
    """
    dd = drawdown_series(px)
    out, cur = [], None
    for i, (d, v) in enumerate(zip(dates, dd)):
        if cur is None:
            if v <= start_th:
                cur = {"start": d, "start_i": i, "trough": v,
                       "trough_d": d, "trough_i": i}
        else:
            if v < cur["trough"]:
                cur.update(trough=v, trough_d=d, trough_i=i)
            if v >= end_th:
                cur["end"] = d
                cur["end_i"] = i
                cur["days"] = (date.fromisoformat(d) - date.fromisoformat(cur["start"])).days
                out.append(cur)
                cur = None
    if cur is not None:
        cur["end"] = None
        cur["end_i"] = len(dates) - 1
        cur["days"] = (date.fromisoformat(dates[-1])
                       - date.fromisoformat(cur["start"])).days
        out.append(cur)
    return out


def align(series_a: dict, series_b: dict) -> list[str]:
    """两个 {date: value} 的交集日期（升序）。"""
    return sorted(set(series_a) & set(series_b))


def to_dict(rows: list[list]) -> dict:
    return {d: v for d, v in rows}


if __name__ == "__main__":
    gold = load_cached("gold_usd", yahoo, "GC=F")
    cny = load_cached("gold_cny", sge, "Au99.99")
    fx = load_cached("fx_usdcny", yahoo, "CNY=X")

    print(f"GC=F   {len(gold)} 点  {gold[0][0]} → {gold[-1][0]}  末 {gold[-1][1]:.2f}")
    print(f"Au9999 {len(cny)} 点  {cny[0][0]} → {cny[-1][0]}  末 {cny[-1][1]:.2f}")
    print(f"CNY=X  {len(fx)} 点  {fx[0][0]} → {fx[-1][0]}  末 {fx[-1][1]:.4f}")

    px = [v for _, v in gold]
    print(f"\n美元金：历史最高 {max(px):.1f}，当前 {px[-1]:.1f}，"
          f"回撤 {max_drawdown(px)*100:.1f}%")

    eps = episodes([d for d, _ in gold], px)
    print(f"回撤事件（≤-15%）：{len(eps)} 次")
    for e in eps:
        print(f"   {e['start']} → 最深 {e['trough']*100:.1f}% @ {e['trough_d']}"
              f"，{e['days']} 天，{e['end'] or '未结束'}")
