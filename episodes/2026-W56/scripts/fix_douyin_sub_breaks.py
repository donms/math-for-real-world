# -*- coding: utf-8 -*-
"""给抖音清单的每条字幕**插入显式换行**，让折点落在标点或空格上。

## 为什么需要

抖音字幕 `wrap=13`、`fontsize=62`。`wrap_cjk` 在第 13 个字宽处硬折，
实测出现三类难看的结果：

* `两个最好的传感器合起来` / `，会更差。`（**逗号落在行首**）
* `因为它们错在同一个地方：最` / `像摔倒的负样本都是躺到沙发上` / `。`（**孤零零一个句号**）
* `工程实际是 67.` / `6 和 79.1。`（**从数字中间劈开**）

`wrap_sub` 会**保留原文里的换行**（先按 `\\n` 切段、每段独立折行），
所以只要在**标点之后**插入 `\\n`，并且每段都 ≤13 字，就不会再被二次折行。

## 切点优先级（依次尝试）

1. **标点之后**（最靠后、又不超宽的那个）；
2. **空格之后**（避免把「只有 36.8%」切成「36.8% 的」）；
3. **CJK 字符边界**（不允许切在 ASCII 串中间 ⇒ 数字/单位不被拆开）；
4. 兜底：按字宽硬切。

并且：剩余段若以标点开头，把标点**挂回上一行**（允许略超宽，
与 `wrap_cjk` 的"标点不另起行"同一策略）。

## 只改字幕，不改音频

`captions[].text` 只用于**显示**；音频按 `dur` 排列、文件已生成。
`tts_captions` / `say` 一个字都不动。
"""
import json
import re
from pathlib import Path

EP = Path(r".\episodes\2026-W56")
MAN = EP / "publish" / "video_manifest_douyin.json"
BAK = EP / "publish" / "video_manifest_douyin.json.bak_sub"
MAXW = 13
PUNCT = "，。；：、！？"
TOK_ASCII = re.compile(r"[0-9A-Za-z%.\-+]")


def width(s: str) -> float:
    return sum(1.0 if ord(c) > 0x2E80 else 0.55 for c in s)


def _balanced(t: str) -> list[str]:
    r"""两行时按**接近等宽**切，避免留下 2–3 字宽的孤行。

    ## 为什么需要（2026-10-19 实测）

    `split_line` 的策略是"尽量靠后切"，于是句子里**没有标点**时会切在
    第 13 个字宽处，尾巴只剩两三个字：

    | 原句 | 旧切法 | 问题 |
    |---|---|---|
    | 南京一个社区给十户老人装了雷达。 | `南京一个社区给十户老人装了` / `雷达。` | 尾巴 3 宽 |
    | 比激光雷达单打低 9.7 个点。 | `比激光雷达单打低 9.7` / `个点。` | 尾巴 3 宽 |

    ⇒ 只在「两行且尾巴 < 4 宽」时改成**在宽度中点附近**切，
    这样 `南京一个社区给十户` / `老人装了雷达。` 是 9 / 7，读起来正常。

    ⚠️ 只处理**恰好两行**的句子；三行以上仍走原逻辑（改它会牵动太多）。
    """
    if width(t) > 2 * MAXW + 2:
        return [t]
    # 断得**略长一点**在上一行（0.55 而不是 0.5）：
    # 0.5 时「南京一个社区给十户老人装了雷达。」会切成 8/8 ⇒
    # 「南京一个社区给十 / 户老人装了雷达。」把「十户」劈开；
    # 0.55 给 9/7 ⇒「南京一个社区给十户 / 老人装了雷达。」
    target = width(t) * 0.55
    best, best_score = 0, 1e9
    for i in range(1, len(t)):
        w = width(t[:i])
        if w > MAXW:
            break
        # ★★ 不许切在**数字/ASCII 串**上或其边上。
        #    实测：没有这条守卫时，「只有 36.8% 的报警」会被切成
        #    「只有 36.」/「8% 的报警」，一个百分数被劈成两半。
        if TOK_ASCII.match(t[i - 1]) or TOK_ASCII.match(t[i]):
            continue
        # 优先级：标点之后 > 空格之后 > 任意 CJK 边界
        bonus = 2.0 if t[i - 1] in PUNCT else (1.0 if t[i - 1] == " " else 0.0)
        score = abs(w - target) - bonus
        if score < best_score:
            best, best_score = i, score
    if not best:
        return [t]
    head, rest = t[:best].strip(), t[best:].strip()
    while rest and rest[0] in PUNCT:
        head += rest[0]
        rest = rest[1:].lstrip()
    return [head, rest] if rest else [head]


def split_line(t: str) -> list[str]:
    orig = t                      # ★ 保留原串：`"".join(out)` 会丢掉被 strip 掉的分隔空格
    out: list[str] = []
    while width(t) > MAXW:
        cut = 0
        # ① 标点之后
        cand = [i + 1 for i, c in enumerate(t) if c in PUNCT
                and width(t[:i + 1]) <= MAXW]
        if cand:
            cut = cand[-1]
        else:
            # ② 空格之后（最靠后的、且不超宽的）
            sp = [i + 1 for i, c in enumerate(t) if c == " "
                  and width(t[:i + 1]) <= MAXW]
            if sp:
                cut = sp[-1]
            else:
                # ③ CJK 边界（不切 ASCII 串）
                for i in range(len(t)):
                    if width(t[:i + 1]) <= MAXW:
                        cut = i + 1
                    else:
                        break
            # ④ 兜底
            if cut <= 0:
                cut = MAXW
        head, rest = t[:cut].strip(), t[cut:].strip()
        # 剩余段以标点开头 ⇒ 挂回上一行
        while rest and rest[0] in PUNCT:
            head += rest[0]
            rest = rest[1:].lstrip()
        out.append(head)
        t = rest
    if t:
        out.append(t)
    # ★ 两行 + 孤尾（< 4 宽）⇒ 改成接近等宽的两行
    # ★★ 以及：**明明两行装得下却切成了三行**（宽度 ≤ 2×MAXW 时）⇒ 也改成两行。
    #    实测：「每天误报一次，只有 36.8% 的报警会被当真。」宽度 14.85，
    #    贪心先切在逗号、再切在空格 ⇒ 三行（7 / 5.3 / 8），
    #    而两行 9 / 11.3 完全装得下，且读起来正常。
    # ⚠️ 必须把**原串**传给 `_balanced`：`out` 的各行已经 strip 过，
    #    重新 join 会吃掉「9.7 个点」中间那个空格（实测切出 `9.7个点。`）。
    if (len(out) >= 2 and width(orig) <= 2 * MAXW + 2
            and (len(out) > 2 or width(out[-1]) < 4)):
        return _balanced(orig)
    return out or [""]


def main() -> int:
    src = BAK if BAK.exists() else MAN          # 永远从**未改动**的那份出发
    d = json.loads(src.read_text(encoding="utf-8"))
    n_chg = 0
    for sc in d["scenes"]:
        for cap in sc["captions"]:
            t = cap["text"].replace("\n", "")
            parts = split_line(t)
            if len(parts) > 1:
                cap["text"] = "\n".join(parts)
                n_chg += 1
            else:
                cap["text"] = t
    MAN.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [OK] 已给 {n_chg} 条字幕插入显式换行")
    bad = 0
    for sc in d["scenes"]:
        for cap in sc["captions"]:
            for ln in cap["text"].split("\n"):
                w = width(ln)
                flag = ""
                if w > MAXW + 1.2:
                    flag = "  <== 超宽"
                    bad += 1
                if ln[:1] in PUNCT:
                    flag += "  <== 标点开头"
                    bad += 1
                print(f"      {w:5.2f}  {ln}{flag}")
    print(f"  自检：超宽/标点开头的行 {bad} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
