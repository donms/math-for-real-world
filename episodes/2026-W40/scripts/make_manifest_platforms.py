#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""生成 B站 / 抖音 两条视频的配音清单（按「素材 → 字幕 → 配音」的顺序）。

与教学片的区别
--------------
教学片（`video_manifest_lecture.json`）用的是精确到「屏」的素材映射；
本次两条视频**按平台受众分别改写内容**：

* **B站**：16:9 长视频（约 12 分钟），讲稿 10 节 → 20 张幻灯片，逐屏映射。
* **抖音**：9:16 竖屏（30–40 秒），内容按短视频受众重写，
  7 张素材 + 短口播，单点打穿。

为什么先做素材
------------
用户明确要求顺序为「素材 → 字幕 → 配音」。
本脚本只负责**把素材与文案对应起来**并写出清单；
字幕由 `render_video.py --ass-only` 生成（它有无 captions 的回退路径，
故**不需要配音就能出字幕**），配音由 `add_voice.py` 最后补。

逐屏映射的写法
------------
B站的 20 张幻灯片与讲稿的 10 节不是一一对应（一节可能铺 2–3 屏），
故这里显式列出「第 N 屏 对应 讲稿第几节」，
避免 `split_for` 那种按字数自动切分导致的错位。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_MD = ROOT / "内容" / "讲稿.md"
PUB = ROOT / "publish"

# 段落加载器**复用** episode_spec 的实现，避免两套下标体系不一致
sys.path.insert(0, str(Path(__file__).resolve().parent))
from episode_spec import load_script_sections  # noqa: E402

# B站：20 屏，**每屏一段独立口播**（不交叉复用）。
#
# ⚠️ 旧版踩过的坑：`BILI_MAP` 让讲稿节号交叉复用（如第 7 节用了 4 次），
#    结果 20 屏总口播 9378 字 —— 是实际内容的 2 倍，
#    成片 23.5 分钟（目标 12 分钟）。而且幻灯片与讲稿节号本就不对齐
#    （「结论的边界」那屏配了第 9 节）。
#
#    现在的做法：把讲稿 10 节**各拆 2 段**（在句号处切），得到 20 段互不重复
#    的口播，与 20 屏一一对应。总字数仍是讲稿的 4728 字 → 约 12.2 分钟。
SPLIT_SECTIONS = True

# ---------- B站 分屏边界 ----------
# 每屏口播在讲稿各节中的**句区间切点**（按句号切分后的下标，左闭右开）。
#
# ⚠️ 本文件最容易错的地方。定法：**逐句读该节在讲什么，再按幻灯片主题定切点**，
#    不要按字数对半、也不要凭印象（前一版就是凭印象，结果整体错一格）。
#    逐句核对后的对应关系：
#   第1节 12句 → 屏1[0,10) 两组数字+会一起来吗+结论预告 ｜ 屏2[10,12) 引出下一节
#   第2节 18句 → 屏3[0,10) 五十年一遇=1/50 → 63.6%  ｜ 屏4[10,18) 取决于怎么算
#   第3节 18句 → 屏5[0,9)  为什么不能看历史最大值      ｜ 屏6[9,18) 极值理论两路径
#   第4节 21句 → 屏7[0,11) 两个相反的分布              ｜ 屏8[11,21) 为什么会这样
#   第5节 21句 → 屏9[0,11) 五十年一遇是多少度          ｜ 屏10[11,21) 技术细节
#   第6节 23句 → 屏11[0,12) copula 引入                ｜ 屏12[12,23) 风险倍数结果
#   第7节 28句 → 屏13[0,9) 证据一 ｜ 屏14[9,18) 证据二 ｜ 屏15[18,28) 证据三
#   第8节 21句 → 屏16[0,10) 方法论结论                 ｜ 屏17[10,21) 门槛移动
#   第9节 12句 → 屏18[0,8) 结论的边界                  ｜ 屏19[8,12) 地域例外
#  第10节 26句 → 屏20[0,26) 三句话总结
BOUNDS: dict[int, list[int]] = {
    1: [10],
    2: [10],
    3: [9],
    4: [11],
    5: [11],
    6: [12],
    7: [9, 18],
    8: [10],
    9: [8],
    10: [],
}


# 抖音：7 屏 → 短口播（按方案 B「纠错版」改写，单点打穿）
DOUYIN_LINES = [
    "高温和暴雨，会一起来吗？",
    "「五十年一遇」是每五十年一次吗？错。它的意思是：任何一年发生的概率是五十分之一。"
    "所以未来五十年里至少出现一次的概率，是百分之六十三点六。不是百分之百。",
    "直觉说，夏天又热又多雨，「又热又涝」的概率应该更高。"
    "但我算了十六个城市、八十六年的数据，结果是反的。",
    "风险倍数是实际概率除以独立假设。九十分位是零点七二，"
    "九十五分位零点四二，九十九分位只有零点三二。越小，越互相排斥。",
    "为什么？极端高温是下沉气流造成的。空气下沉、增温，同时把云驱散。"
    "所以最热的日子，雨只有平时的四成。",
    "还有一个数字：北京一九四零年的「五十年一遇」是四十点九度。"
    "到二零二六年，只相当于约六年一遇。十六个城市全部在升温。",
    "记住三句话：气温有上界，降水没有；高温与暴雨互相排斥；"
    "北京的五十年一遇，现在是六年一遇。",
]


def clean(text: str) -> str:
    """把讲稿正文清成纯口播文本（去 markdown 与舞台提示）。"""
    text = re.sub(r"^\s*---\s*$", "", text, flags=re.M)
    text = re.sub(r"^\s*[>#].*$", "", text, flags=re.M)
    text = text.replace("**", "")
    text = re.sub(r"（[^）]*）", "", text)
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.M)
    lines = []
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        for seg in re.split(r"(?<=[。？！])", para):
            if seg.strip():
                lines.append(seg.strip())
    return "\n".join(lines)


def split_in_two(text: str) -> tuple[str, str]:
    r"""把一段口播在**句号处**切成两半，尽量均分。

    为什么在句号处切：口播必须能独立朗读，从句子中间切开会让两段都读不顺。
    做法是先按句号拆句，再找累计字数最接近一半的那个切点。
    """
    lines = [x for x in text.split("\n") if x.strip()]
    if len(lines) < 2:
        return text, ""
    total = sum(len(x) for x in lines)
    best, acc = 0, 0
    for i, ln in enumerate(lines[:-1], 1):
        acc += len(ln)
        if acc >= total / 2:
            best = i
            break
    if best == 0:
        best = max(1, len(lines) // 2)
    return "\n".join(lines[:best]), "\n".join(lines[best:])


def load_sections() -> dict[int, list[str]]:
    r"""讲稿 → {节号: [自然段, …]}。

    ⚠️ **必须与 `episode_spec.load_script_sections` 一致**（都是「按空行切自然段」）。

    踩过的坑：本函数早期用 `clean()` 把每节**按句号重切成一行一句**，
    而 `calibrate_segments.py` / `episode_spec.py` 用的是**自然段**下标。
    两套下标体系混用时，`secs[sec][a:b]` 会取到**单个汉字**——
    实测 20 屏清单只有 129 字（应为 4728 字），
    字幕变成"最"、"长"、"单"、"行" 各一条。
    """
    return load_script_sections()


def build_bili_segments() -> list[str]:
    r"""把讲稿切成 20 段口播，**每段对应一屏幻灯片**。

    ⚠️ 惨痛教训：前一版用「在中点对半分」的机械切法，
       切出来的段与幻灯片内容**毫无关系** ——
       实测第 1 屏标题是「越极端，越不会一起来」，
       配的口播却是「先看两组数字」；第 9 屏标题是「意外发现：两个相反的分布」，
       配的口播却是「现在回到五十年一遇是多少度」。
       **每一屏都错配**，用户直接看出来了。

    正确做法：**按幻灯片的内容定切点**，而不是按字数对半分。
    下表 `BOUNDS` 给出每屏口播在讲稿各节中的**句区间**（左闭右开），
    是照着 `slides16x9.json` 的 20 个标题逐一对出来的。
    """
    secs = load_sections()
    segs: list[str] = []
    for n in sorted(secs):
        lines = [x for x in secs[n].split("\n") if x.strip()]
        cuts = BOUNDS[n]
        prev = 0
        for c in list(cuts) + [len(lines)]:
            segs.append("\n".join(lines[prev:c]))
            prev = c
    return [s for s in segs if s.strip()]


def build(week: str, variant: str, scenes: list[dict], w: int, h: int,
          sub: dict, note: str) -> Path:
    man = {
        "week": week, "brand": "用数学看世界",
        "fps": 30, "w": w, "h": h, "bgm": None,
        "sub": sub, "_note": note, "scenes": scenes, "voice": {},
    }
    p = PUB / f"video_manifest_{variant}.json"
    p.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    tot = sum(len(s["text"].replace("\n", "")) for s in scenes)
    print(f"  [{variant}] {len(scenes)} 屏 / {tot} 字 → {p.name}")
    return p


def main() -> int:
    secs = load_sections()
    print(f"  讲稿 {len(secs)} 节")

    # ---------- B站：16:9 ----------
    # 口播与素材都从 publish/segments.json 派生（DP 校准的 20 段边界），
    # 幻灯片由 episode_spec.py 从**同一份** segments.json 生成 —— 同源，不会错位。
    seg_p = PUB / "segments.json"
    if not seg_p.exists():
        print("  [!] 缺 publish/segments.json —— 先跑 calibrate_segments.py --export")
        return 2
    rows = json.loads(seg_p.read_text(encoding="utf-8"))["segments"]
    slides = sorted((PUB / "视频" / "素材16x9").glob("slide_*.png"))
    if not slides:
        print("  [!] 缺 16:9 素材，先跑 render_slides16x9.py")
        return 2
    if len(rows) != len(slides):
        print(f"  [!] 口播 {len(rows)} 段 ≠ 素材 {len(slides)} 张")
        return 2
    bili_scenes = []
    for row, img in zip(rows, slides):
        a, b = row["paras"]
        text = "\n".join(secs[row["sec"]][a:b])
        bili_scenes.append({
            "img": f"publish/视频/素材16x9/{img.name}",
            "dur": 0.0, "text": text, "_page": row["page"],
            "captions": [], "audio": None, "gap_after": 0.15,
        })
    # ⚠️ 自检：清单里的图片必须真实存在。
    #    踩过的坑：版式从 bullets 改成 compare 后，文件名从
    #    `slide_03_bullets.png` 变成 `slide_03_compare.png`，
    #    而我**只重渲了素材、忘了重建清单** —— 渲染器找不到图就不画内容，
    #    成片里那一屏变成**纯背景色**（用户截图问"这是啥"）。
    #    所以这里逐张核对存在性，缺图直接报错退出。
    missing = [s["img"] for s in bili_scenes
               if not (ROOT / s["img"]).exists()]
    if missing:
        print(f"  [!] 清单里有 {len(missing)} 张图不存在：")
        for m in missing[:5]:
            print(f"      {m}")
        print("      → 先跑 render_slides16x9.py 重渲素材，或核对 PAGES 的版式")
        return 2
    build("2026-W40", "bili", bili_scenes, 1920, 1080,
          # B站长视频：字号 46、每行 30 字、每条字幕 ≤46 字
          {"fontsize": 46, "margin_v": 58, "outline": 3,
           "font": "Microsoft YaHei", "wrap": 30, "max_caption": 46,
           "one_line": True},
          "B站 16:9 长视频。20 屏 = segments.json 的 20 段（calibrate_segments.py "
          "用动态规划校准的边界，字数均衡、落在自然段上）；"
          "幻灯片由 episode_spec.py 从同一份 segments.json 派生 —— 口播与素材同源。")

    # ---------- 抖音：9:16 ----------
    verts = sorted((PUB / "视频" / "素材9x16").glob("*.png"))
    if not verts:
        print("  [!] 缺 9:16 素材，先跑 render_cards.py --size 1080x1920")
        return 2
    if len(verts) != len(DOUYIN_LINES):
        print(f"  [!] 竖屏素材 {len(verts)} 张 ≠ 口播 {len(DOUYIN_LINES)} 条")
        return 2
    douyin_scenes = []
    for i, (img, line) in enumerate(zip(verts, DOUYIN_LINES), 1):
        douyin_scenes.append({
            "img": f"publish/视频/素材9x16/{img.name}",
            "dur": 0.0, "text": line, "_sec": i, "_page": i,
            "captions": [], "audio": None, "gap_after": 0.0,
        })
    build("2026-W40", "douyin", douyin_scenes, 1080, 1920,
          # 抖音竖屏：字号 62、每行 14 字、每条字幕 ≤42 字；底部留安全区
          {"fontsize": 62, "margin_v": 300, "outline": 3,
           "font": "Microsoft YaHei", "wrap": 14, "max_caption": 42,
           "one_line": True},
          "抖音 9:16 竖屏短视频（按方案 B「纠错版」改写）。"
          "口播 7 条写死在 make_manifest_platforms.py 的 DOUYIN_LINES。"
          "margin_v=300 为底部安全区（抖音 UI 占位）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
