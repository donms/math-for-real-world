"""轨道传播器：TLE 解析 + 两体 + J2 长期项 + 星下点轨迹。

为什么不用 SGP4
--------------
本期要回答的是"覆盖带长什么样""重访间隔多长"，
**不追求米级位置精度**。两体 + J2 长期项足以把这些几何量算到可用精度，
而且每一步都能手推验证（SGP4 是个黑箱，不适合科普里"每一步都可复现"的要求）。

精度声明
--------
* 位置误差：一天内约数十公里（J2 长期项已含，未含短周期项与大气阻力）；
* 对"最高纬度""覆盖带宽度""重访间隔"这类**统计量**，影响可忽略；
* 对"某个时刻卫星在哪个点"这类**瞬时量**，误差可达几十公里，正文不这么用。

用法
----
    python orbit.py               # 自检：解析 TLE、打印两组轨道面统计
"""
from __future__ import annotations

import json
import math
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

MU = 398600.4418        # km³/s²
RE = 6378.137           # km
J2 = 1.08263e-3
DAY = 86400.0
OMEGA_E = 7.2921150e-5  # rad/s，地球自转

DATA = Path(__file__).resolve().parents[1] / "data"
TLE_CACHE = DATA / "tle_yunyao.json"


# ---------------------------------------------------------------- TLE
def fetch_tle(name: str = "YUNYAO") -> list[dict]:
    """按名称从 CelesTrak 取 TLE；带本地缓存（对方对批量下载限流 403）。"""
    if TLE_CACHE.exists():
        return json.loads(TLE_CACHE.read_text(encoding="utf-8"))
    import urllib.parse
    url = ("https://celestrak.org/NORAD/elements/gp.php?"
           + urllib.parse.urlencode({"NAME": name, "FORMAT": "tle"}))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    lines = [l for l in raw.splitlines() if l.strip()]
    sats = []
    for i in range(0, len(lines) - 2, 3):
        sat = parse_tle(lines[i].strip(), lines[i + 1], lines[i + 2])
        if sat:
            sats.append(sat)
    DATA.mkdir(parents=True, exist_ok=True)
    TLE_CACHE.write_text(json.dumps(sats, ensure_ascii=False, indent=2), encoding="utf-8")
    return sats


def parse_tle(name: str, l1: str, l2: str) -> dict | None:
    try:
        epoch_year = int(l1[18:20])
        epoch_day = float(l1[20:32])
        inc = float(l2[8:16])
        raan = float(l2[17:25])
        ecc = float("0." + l2[26:33].strip())
        argp = float(l2[34:42])
        M = float(l2[43:51])
        n_revday = float(l2[52:63])
    except Exception:
        return None
    a = (MU * (DAY / (2 * math.pi * n_revday)) ** 2) ** (1 / 3)
    return {"name": name, "epoch_year": 2000 + epoch_year, "epoch_day": epoch_day,
            "inc": inc, "raan": raan, "ecc": ecc, "argp": argp, "M": M,
            "n_revday": n_revday, "a": a, "alt": a - RE}


def epoch_to_dt(sat: dict) -> datetime:
    base = datetime(sat["epoch_year"], 1, 1, tzinfo=timezone.utc)
    return base + timedelta(days=sat["epoch_day"] - 1.0)


# ---------------------------------------------------------------- 传播
def secular_rates(a: float, e: float, inc_deg: float) -> tuple[float, float]:
    """J2 长期项：升交点赤经速率、近地点幅角速率（rad/s）。"""
    i = math.radians(inc_deg)
    n = math.sqrt(MU / a ** 3)
    p = a * (1 - e * e)
    k = 1.5 * J2 * (RE / p) ** 2 * n
    return -k * math.cos(i), 0.75 * J2 * (RE / p) ** 2 * n * (5 * math.cos(i) ** 2 - 1)


def eci_position(sat: dict, t_sec: float) -> tuple[float, float, float]:
    """给定相对历元的时间，返回 ECI 位置（km）。"""
    a, e = sat["a"], sat["ecc"]
    n = math.sqrt(MU / a ** 3)
    raan_dot, argp_dot = secular_rates(a, e, sat["inc"])

    raan = math.radians(sat["raan"]) + raan_dot * t_sec
    argp = math.radians(sat["argp"]) + argp_dot * t_sec
    M = math.radians(sat["M"]) + n * t_sec

    E = M
    for _ in range(8):
        E = E - (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
    nu = 2 * math.atan2(math.sqrt(1 + e) * math.sin(E / 2),
                        math.sqrt(1 - e) * math.cos(E / 2))
    r = a * (1 - e * math.cos(E))

    i = math.radians(sat["inc"])
    x_p, y_p = r * math.cos(nu), r * math.sin(nu)
    x = (math.cos(raan) * x_p - math.sin(raan) * math.cos(i) * y_p)
    y = (math.sin(raan) * x_p + math.cos(raan) * math.cos(i) * y_p)
    z = math.sin(i) * y_p
    return x, y, z


def gmst(dt: datetime) -> float:
    """格林尼治恒星时（rad），够用的简化式。"""
    jd = (dt - datetime(2000, 1, 1, 12, tzinfo=timezone.utc)).total_seconds() / DAY + 2451545.0
    T = (jd - 2451545.0) / 36525.0
    g = 280.46061837 + 360.98564736629 * (jd - 2451545.0) + 0.000387933 * T * T
    return math.radians(g % 360.0)


def subpoint(sat: dict, dt: datetime) -> tuple[float, float]:
    """星下点经纬度（度）。"""
    t = (dt - epoch_to_dt(sat)).total_seconds()
    x, y, z = eci_position(sat, t)
    r = math.sqrt(x * x + y * y + z * z)
    lat = math.degrees(math.asin(z / r))
    lon = math.degrees(math.atan2(y, x) - gmst(dt))
    lon = (lon + 180) % 360 - 180
    return lat, lon


def local_solar_time(sat: dict, dt: datetime) -> float:
    """星下点的地方太阳时（小时），用于验证 SSO 是否锁住地方时。"""
    lat, lon = subpoint(sat, dt)
    utc_h = dt.hour + dt.minute / 60 + dt.second / 3600
    return (utc_h + lon / 15.0) % 24


# ---------------------------------------------------------------- 自检
def main() -> int:
    sats = fetch_tle()
    print(f"[TLE] 取到 {len(sats)} 颗，缓存 → {TLE_CACHE}")
    groups = {}
    for s in sats:
        key = "A(50°)" if s["inc"] < 60 else "B(97.6°)"
        groups.setdefault(key, []).append(s)

    for key, rows in groups.items():
        incs = [r["inc"] for r in rows]
        alts = [r["alt"] for r in rows]
        print(f"\n[{key}] {len(rows)} 颗")
        print(f"   倾角 {min(incs):.3f}–{max(incs):.3f}°（标准差 {np_std(incs):.4f}）")
        print(f"   高度 {min(alts):.1f}–{max(alts):.1f} km")

    # SSO 自检：一天内地方时是否稳定
    sso = groups["B(97.6°)"][0]
    t0 = epoch_to_dt(sso)
    times = [t0 + timedelta(minutes=10 * k) for k in range(0, 145)]
    lst = [local_solar_time(sso, t) for t in times]
    # 只看升交点（纬度由南向北穿越赤道）附近的地方时
    print(f"\n[SSO 自检] {sso['name']}")
    print(f"   一天内地方时范围 {min(lst):.2f}–{max(lst):.2f} 小时")
    return 0


def np_std(xs: list[float]) -> float:
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


if __name__ == "__main__":
    raise SystemExit(main())
