"""抓 2026 季台风的实况轨迹 + 当时发布的预报点。

数据源（公开、免密钥）
----------------------
    https://typhoon.nmc.cn/weatherservice/typhoon/jsons/list_2026      # 全季列表
    https://typhoon.nmc.cn/weatherservice/typhoon/jsons/view_<id>     # 单个台风

返回的是 **JSONP**（`typhoon_jsons_view_123({...})`），所以要先剥壳再 `json.loads`。

★ 三个坑（W59 实测）
--------------------
1. **`list_default` 是双括号 `((...))`，`list_2026` 是单括号** —— 按括号切片会挂，
   统一改成"取第一个 `{` 到最后一个 `}`"。
2. **直连偶发 `SSL: UNEXPECTED_EOF_WHILE_READING`** —— 必须重试（3–4 次）。
3. **只有 2026 季带预报字段**（2019–2025 抽查 28 个台风，含预报 0 个）。
   本脚本默认只取 2026；加 `--year` 可以取历年轨迹（但不会有预报）。

产量
----
    data/raw/<id>_<NAME>.json     每个台风一份（meta + points）
    data/raw/index.json           索引（含每个台风的点数/预报数）
    data/来源清单.md              来源与口径
"""
from __future__ import annotations

import argparse
import json
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://typhoon.nmc.cn/web.html",
}
BASE = "https://typhoon.nmc.cn/weatherservice/typhoon/jsons/"
EP = Path(__file__).resolve().parents[1]
RAW = EP / "data" / "raw"

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def get(url: str, tries: int = 4, timeout: int = 25) -> str:
    """带重试的 GET（SSL 偶发 EOF，见坑 2）。"""
    last: Exception | None = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:                       # noqa: BLE001
            last = e
            time.sleep(0.8 * (k + 1))
    raise RuntimeError(f"取数失败 {url}: {type(last).__name__}: {last}")


def unwrap(raw: str) -> dict:
    """剥 JSONP：取第一个 `{` 到最后一个 `}`（见坑 1）。"""
    i, j = raw.find("{"), raw.rfind("}")
    if i < 0 or j < 0:
        raise ValueError(f"不是 JSONP：{raw[:80]!r}")
    return json.loads(raw[i:j + 1])


def fetch_year(year: int) -> list[dict]:
    d = unwrap(get(BASE + f"list_{year}"))
    return d.get("typhoonList", [])


def parse_points(entry: list) -> list[dict]:
    """把 `typhoon` 数组解析成结构化点。

    结构（实测）：
        typhoon = [id, name_en, name_cn, year_code, num, ?, meaning, status, points]
        每个 point = [pid, "YYYYMMDDHHMM", epoch_ms, 等级, 经度, 纬度, 气压,
                      风速, 移向, 移速, 风圈, 预报字典, 展示元组]
    """
    pts = entry[8] if len(entry) > 8 else []
    out = []
    for p in pts:
        f = p[11] or {}
        fc = []
        for agency, rows in f.items():
            for r in rows:
                # r = [提前量h, 起报时, 经度, 纬度, 气压, 风速, 机构, 等级]
                fc.append({"lead": r[0], "valid_from": r[1], "lon": r[2], "lat": r[3],
                           "pressure": r[4], "wind": r[5], "agency": r[6] or agency,
                           "grade": r[7] if len(r) > 7 else None})
        out.append({"pid": p[0], "time": p[1], "epoch_ms": p[2], "grade": p[3],
                    "lon": p[4], "lat": p[5], "pressure": p[6], "wind": p[7],
                    "move_dir": p[8], "move_speed": p[9], "forecasts": fc})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--all-years", action="store_true",
                    help="额外抓 2015–2025 的轨迹（无预报，仅供气候对照）")
    a = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    years = [a.year] + ([y for y in range(2015, a.year)] if a.all_years else [])

    index = []
    for year in years:
        rows = fetch_year(year)
        named = [r for r in rows if r[1] and r[1] != "nameless"]
        print(f"[{year}] 列表 {len(rows)} 条，命名 {len(named)} 个")
        for r in named:
            tid, name_en, name_cn = r[0], r[1], r[2]
            try:
                d = unwrap(get(BASE + f"view_{tid}"))
                t = d["typhoon"]
                pts = parse_points(t)
            except Exception as e:                   # noqa: BLE001
                print(f"   [!] {name_en} 取详情失败：{type(e).__name__} {e}")
                continue
            nfc = sum(len(p["forecasts"]) for p in pts)
            meta = {"id": tid, "name_en": name_en, "name_cn": name_cn,
                    "year": year, "num": r[4] if len(r) > 4 else None,
                    "status": r[7] if len(r) > 7 else None,
                    "n_points": len(pts), "n_forecasts": nfc}
            out = RAW / f"{tid}_{name_en}.json"
            out.write_text(json.dumps({"meta": meta, "points": pts}, ensure_ascii=False),
                           encoding="utf-8")
            index.append(meta)
            print(f"   {name_en:12s} 点 {len(pts):4d}  预报 {nfc:4d}")
            time.sleep(0.15)

    (RAW / "index.json").write_text(
        json.dumps({"year": a.year, "count": len(index), "items": index},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    total_fc = sum(m["n_forecasts"] for m in index)
    (EP / "data" / "来源清单.md").write_text(f"""# 2026-W59 数据来源清单

## 主数据源

| 项 | 值 |
|---|---|
| 机构 | 中央气象台（NMC）台风网 |
| 端点 | `https://typhoon.nmc.cn/weatherservice/typhoon/jsons/list_{a.year}` / `view_<id>` |
| 协议 | 公开网页接口，**免密钥**；返回 JSONP，需剥壳 |
| 抓取时间 | {time.strftime('%Y-%m-%d %H:%M')} |
| 样本 | **{len(index)} 个命名台风**，实况点 {sum(m['n_points'] for m in index)} 个，预报点 {total_fc} 个 |

## 口径

- **实况**：逐点轨迹，时间戳为北京时间 `YYYYMMDDHHMM`，经纬度为十进制度；
- **预报**：每个实况点附当时发布的预报，字段 `[提前量, 起报时, 经度, 纬度, 气压, 风速, 机构, 等级]`；
- **提前量**：6/12/18/24/36/48/60/72/96/120 h；
- **机构**：仅 `BABJ`（中央气象台）。

## 三条限制（必须随结论出现）

1. **只有 {a.year} 季带预报存档** —— 2019–2025 抽查 28 个台风，含预报 0 个
   ⇒ 做不了跨年"预报进步"曲线；
2. **只有 BABJ 一个机构** ⇒ 不做机构对比；
3. **实况分辨率 6 h**（个别 3 h）⇒ 配对必须声明匹配规则与容差。

## 复现

```powershell
python scripts/fetch_typhoon.py --year {a.year}
```
""", encoding="utf-8")

    print(f"\n[完成] {len(index)} 个台风，预报点 {total_fc} 个 -> {RAW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
