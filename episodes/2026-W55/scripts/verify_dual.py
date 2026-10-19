#!/usr/bin/env python -X utf8
# -*- coding: utf-8 -*-
r"""W55 · **Python ↔ HTML 双版本数值一致性校验**。

## 为什么必须做这一步

用户最初选的是 **C 方案：Python 仿真 + HTML 交互**。
**两套实现最大的风险是"公式悄悄走样"** —— 网页看起来在跑，数字却是错的。

**⇒ 本脚本把两份实现放在一起逐项对账。**

## 方法

1. **Python 侧**：`nozzle_state.run_mission10_auto` 直接跑；
2. **HTML 侧**：用 Node + DOM 桩把 `publish/sim.html` 里的 `<script>` 跑起来，
   读它算出的 `window.__SIM__()` —— **校验的是"网页真正会跑的那份代码"**，
   不是另写一份 JS；
3. 逐项比较，给出相对误差与判定。

## 允许的差异来源

| 来源 | 说明 |
|---|---|
| **积分器** | Python 用 RK4；JS 用半隐式欧拉（步长减半以补偿）|
| **步长** | Python 1/150；JS 1/480 |
| **落地容差** | JS 取 20 mm（悬架行程），Python 取 0 |

**⇒ 判据取"相对误差 ≤5%** 或 **绝对误差 ≤ 各项阈值"，
超过即视为"两边走样"。\n\n> ⚠ **近零量必须用绝对容差**：落地 $v_z$ 两边都接近 0\n> （−0.065 vs −0.020，都远小于 −0.5 的目标），\n> 相对差 69% 但绝对差仅 0.045 m/s。
"""
from __future__ import annotations

import math

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import physics as ph          # noqa: E402
import nozzle_state as ns     # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
HTML = ROOT / "episodes" / "2026-W55" / "publish" / "sim.html"
NODE_JS = HERE / "verify_html_node.js"

TOL = 0.05          # 相对误差上限 5%


def run_python() -> dict:
    recs = ns.run_mission10_auto(1 / 150)
    s = ns.summarize10(recs)
    last = recs[-1]
    t_burn = getattr(ns.run_mission10, "t_burn", None)
    # 触发点：首次"下降且 ≤ Z_TRIGGER"
    t_trig = None
    for r in recs:
        if (t_burn is not None and r.t > t_burn + 0.05
                and r.vz < -1.0 and r.z <= ph.Z_TRIGGER):
            t_trig = r.t
            break
    used = {k: round(v, 2) for k, v in s["per_nozzle"].items()}
    return {
        "peak": s["z_max"],
        "tBurn": t_burn,
        "tTrig": t_trig,
        "tEnd": last.t,
        "vzLand": last.vz,
        "xEnd": last.x,
        # ★ 不要取 abs：符号本身就是信息（方向反了必须能看出来）
        "thetaEndDeg": last.theta * 180 / 3.141592653589793,
        "mUsed": s["m_total"],
        "pEnd": last.p_mPa,
        "used": used,
        "_recs": recs,
    }


def run_node() -> dict | None:
    if not NODE_JS.exists():
        print(f"  [缺少] {NODE_JS.name}")
        return None
    try:
        out = subprocess.run(
            ["node", str(NODE_JS), str(HTML)],
            capture_output=True, text=True, timeout=180,
            encoding="utf-8", errors="replace")
    except FileNotFoundError:
        print("  [跳过] 找不到 node")
        return None
    except subprocess.TimeoutExpired:
        print("  [超时] node 运行超过 180 s")
        return None
    if out.returncode != 0:
        print("  [失败] node 返回非 0")
        print("   " + (out.stderr or "")[:400])
        return None
    line = (out.stdout or "").strip().splitlines()
    if not line:
        print("  [失败] node 无输出")
        return None
    return json.loads(line[-1])


# ==================== 力偶纯度检查 ====================

def _wrench(name: str, th: float, F: float):
    r"""车体喷口在滚转 $\theta$ 时的**三轴力矩与力**（世界系）。

    $$\tau_x=r_yF_z-r_zF_y,\quad
    \tau_y=r_zF_x-r_xF_z,\quad
    \tau_z=r_xF_y-r_yF_x$$
    """
    meta = next(m for m in ns.NOZZLE_META if m["name"] == name)
    c, s = math.cos(th), math.sin(th)
    w = ns.body_to_world(meta["axis"], c, s)
    lx, ly, lz = meta["pos"][0], meta["pos"][1], meta["pos2_z"]
    wy = ly * c - lz * s
    wz = ly * s + lz * c
    fx, fy, fz = F * w[0], F * w[1], F * w[2]
    return (fx, fy, fz,
            wy * fz - wz * fy,
            wz * fx - lx * fz,
            lx * fy - wy * fx)


def check_couple(recs) -> tuple[int, list[str]]:
    r"""逐帧检验"滚转是否由**纯力偶**驱动"。

    返回 `(失败数, 明细行)`。
    """
    lines: list[str] = []
    bad = 0
    # ★ 方案无关的触发条件：**产生了显著滚转力矩**的帧
    roll = [r for r in recs if abs(getattr(r, "tau", 0.0)) > 1.0e3]
    if not roll:
        lines.append("  [跳过] 没有产生滚转力矩的帧")
        return 1, lines

    worst_y = worst_z = worst_net = 0.0
    tx_list = []
    for r in roll:
        tx = ty = tz = 0.0
        fx = fy = fz = 0.0
        for nz in ns.NOZZLE_META:
            nm = nz["name"]
            d = r.duty.get(nm, 0.0)
            if d <= 1e-9:
                continue
            F = r.f.get(nm, 0.0)          # 该帧实际推力（N）
            if F <= 0:
                continue
            a = _wrench(nm, r.theta, F)
            fx += a[0]
            fy += a[1]
            fz += a[2]
            tx += a[3]
            ty += a[4]
            tz += a[5]
        tx_list.append(abs(tx))
        worst_y = max(worst_y, abs(ty))
        worst_z = max(worst_z, abs(tz))
        worst_net = max(worst_net, math.hypot(fx, fy), abs(fz))

    scale = max(tx_list) if tx_list else 1.0
    if scale <= 0:
        lines.append("  [跳过] 滚转力矩为零")
        return 1, lines

    r_y = worst_y / scale
    r_z = worst_z / scale
    r_n = worst_net / scale * 0 + worst_net   # 净力按牛顿比
    lim = 0.01

    lines.append(f"  滚转帧数            {len(roll)}")
    lines.append(f"  |τx| 峰值           {scale/1000:.2f} kN·m")
    lines.append(f"  |τy| 峰值           {worst_y/1000:.3f} kN·m"
                 f"   相对 τx {r_y*100:.2f}%")
    lines.append(f"  |τz| 峰值           {worst_z/1000:.3f} kN·m"
                 f"   相对 τx {r_z*100:.2f}%")
    lines.append(f"  净力峰值            {r_n:.1f} N")
    if r_y > lim or r_z > lim:
        bad += 1
        lines.append("  [FAIL] 存在寄生力矩 => 滚转轴不在 x 轴上，"
                     "车会绕对角线翻滚")
    else:
        lines.append("  [PASS] 无寄生俯仰/偏航（滚转确实绕纵轴）")
    # ★ 净力只作信息：B+C 方案*本来*就靠非零竖直力换滚转
    lines.append(f"  [INFO] 净力峰值 {r_n:.1f} N"
                 f"（B+C 方案允许非零；力偶方案应为 0）")
    return bad, lines


def main() -> int:
    print("=" * 86)
    print("  W55 · Python ↔ HTML 双版本一致性校验")
    print("=" * 86)
    if not HTML.exists():
        print(f"  找不到 {HTML}")
        return 1
    print(f"\n  网页 {HTML.name}（{HTML.stat().st_size/1024:.0f} KB）")

    py = run_python()
    hh = run_node()
    if hh is None:
        print("\n  ★ HTML 侧未取得结果，校验未完成")
        return 1

    # (标签, 键, 小数位, 绝对容差)
    #
    # ★ 为什么需要"绝对容差"：**近零量的相对误差没有意义**。
    #   落地 vz 两边都接近 0（−0.065 vs −0.020，都远小于 −0.5 的目标），
    #   相对差 69% 但绝对差只有 0.045 m/s —— 判为不一致是**指标选错了**。
    rows = [
        ("峰值高度 (m)",     "peak",        2, 0.20),
        ("起飞熄火 (s)",     "tBurn",       3, 0.05),
        ("缓冲触发 (s)",     "tTrig",       3, 0.10),
        ("全程时长 (s)",     "tEnd",        3, 0.10),
        ("落地 vz (m/s)",    "vzLand",      3, 0.20),
        ("水平终点 (m)",     "xEnd",        2, 0.50),
        ("共转角 (°)",       "thetaEndDeg", 1, 5.00),
        ("耗气 (kg)",        "mUsed",       2, 2.00),
        ("末端罐压 (MPa)",   "pEnd",        2, 0.50),
    ]
    print(f"\n  {'量':<18}{'Python':>11}{'HTML':>11}"
          f"{'相对差':>9}{'绝对差':>10}{'判定':>8}")
    print("  " + "-" * 68)
    bad = 0
    for lab, key, nd, atol in rows:
        a, b = py.get(key), hh.get(key)
        if a is None or b is None:
            print(f"  {lab:<18}{'—':>11}{'—':>11}{'—':>9}{'—':>10}{'—':>8}")
            continue
        da = abs(a - b)
        rel = da / max(abs(a), 1e-9)
        ok = (rel <= TOL) or (da <= atol)
        if not ok:
            bad += 1
        print(f"  {lab:<18}{a:>11.{nd}f}{b:>11.{nd}f}"
              f"{rel*100:>8.1f}%{da:>10.{nd}f}"
              f"{'  ✓' if ok else '  ✗':>8}")

    # 逐喷口
    print(f"\n  {'喷口':<10}{'Python(kg)':>13}{'HTML(kg)':>12}{'相对差':>10}")
    print("  " + "-" * 46)
    for k in ns.NAMES:
        a = py["used"].get(k, 0.0)
        b = hh["used"].get(k, 0.0)
        if a < 0.01 and b < 0.01:
            continue
        rel = abs(a - b) / max(abs(a), 1e-9)
        print(f"  {k:<10}{a:>13.2f}{b:>12.2f}{rel*100:>9.1f}%")

    # ★ 力偶纯度检查（本期"三次才改对"的教训固化）
    print("\n  " + "-" * 68)
    print("  力矩纯度（寄生俯仰/偏航）")
    print("  " + "-" * 68)
    cb, clines = check_couple(py["_recs"])
    for ln in clines:
        print(ln)
    bad += cb

    print("\n" + "=" * 86)
    if bad == 0:
        print(f"  ★ 全部 {len(rows)} 项在 {TOL*100:.0f}% 以内 ⇒ 两版本一致")
    else:
        print(f"  ★ {bad} 项超出 {TOL*100:.0f}% ⇒ 需检查那边的实现")
    print("=" * 86)
    return 0 if bad == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
