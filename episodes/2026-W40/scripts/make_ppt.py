#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""生成答辩 PPT（11 页）。

⚠️ 公式路线：**路线 B（WPS 兼容）**

技能明确记录：WPS 会拒绝 PPT 里的 OMML 数学运行，报「需要修复」——
即使 XML 结构完全合法（`m:oMath` 包 `a:r`、`lang` 无命名空间、
无 `oMathPara`、用 `add_r`）。2019 D 题实测三连踩坑。
故本 PPT：
  · **块级公式** → matplotlib mathtext 渲染为透明 PNG 插入
  · **行内公式** → 转 Unicode 普通文本（Δᵢ、γᵢⱼ、λ_U、R² 这类）
另交付 MathJax HTML 版作为「可编辑/完整公式」版本（路线 C）。

⚠️ 另一个坑：字体缺字形时 PIL/matplotlib **静默出豆腐块**。
本项目已确认下标 ᵢ 与部分符号有缺失风险，故 PPT 内一律用
ASCII 下划线写法（mu1、x50、lambda_U）而非 Unicode 下标。
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from PIL import Image as _Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Cm, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
FIGS = ROOT / "results" / "figs"
OUT_DIR = ROOT / "答辩材料"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PPTX = OUT_DIR / "答辩PPT.pptx"

# 主题色
NAVY = RGBColor(0x1F, 0x3B, 0x63)
BLUE = RGBColor(0x2E, 0x86, 0xC1)
RED = RGBColor(0xC0, 0x39, 0x2B)
GRAY = RGBColor(0x55, 0x55, 0x55)
LIGHT = RGBColor(0xF2, 0xF6, 0xFA)

# 中文字体（否则乱码）
for _f in (r"<LOCAL_PATH>", r"<LOCAL_PATH>"):
    try:
        font_manager.fontManager.addfont(_f)
    except Exception:                                          # noqa: BLE001
        pass
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

_SUBS = {"0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅",
         "6": "₆", "7": "₇", "8": "₈", "9": "₉",
         "i": "ᵢ", "j": "ⱼ", "m": "ₘ", "t": "ₜ", "n": "ₙ", "s": "ₛ",
         "r": "ᵣ", "x": "ₓ", "a": "ₐ", "e": "ₑ", "o": "ₒ", "T": "ᵀ"}
_SUPS = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵",
         "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "+": "⁺", "-": "⁻"}
_CMD = {"\\Delta": "Δ", "\\lambda": "λ", "\\xi": "ξ", "\\mu": "μ",
        "\\sigma": "σ", "\\tau": "τ", "\\cdot": "·", "\\times": "×",
        "\\ge": "≥", "\\le": "≤", "\\approx": "≈", "\\to": "→",
        "\\infty": "∞", "\\pm": "±", "\\alpha": "α", "\\beta": "β",
        "\\quad": " ", "\\qquad": " ", "\\,": " ", "\\;": " ", "\\ ": " "}


def latex_to_plain(tex: str) -> str:
    """行内 LaTeX → Unicode 普通文本（不依赖字体是否有下标字形）。"""
    tex = re.sub(r"\\mathrm\{([^{}]*)\}", r"\1", tex)
    tex = re.sub(r"\\text\{([^{}]*)\}", r"\1", tex)
    for k, v in _CMD.items():
        tex = tex.replace(k, v)
    tex = re.sub(r"_\{([^{}]*)\}", lambda m: "_" + m.group(1), tex)
    tex = re.sub(r"\^\{([^{}]*)\}", lambda m: "^" + m.group(1), tex)
    return tex


def render_math_png(tex: str, fs: int, rgb: tuple[int, int, int]) -> str:
    """块级公式 → 透明 PNG。

    ⚠️ matplotlib 的 mathtext **不是完整 LaTeX**，它不认 `\\big` / `\\Big`
    （报 `ParseFatalException: Unknown symbol: \\big`），
    而 latex2mathml 是认的——两者支持集**不同**，不能直接复用同一份源码。
    这里统一预处理成 mathtext 支持的形式。
    """
    for k in (r"\Big", r"\big", r"\Bigg", r"\bigg", r"\left", r"\right"):
        tex = tex.replace(k, "")
    tex = tex.replace(r"\{", "(").replace(r"\}", ")")
    tex = tex.replace(r"\,", " ").replace(r"\;", " ").replace(r"\ ", " ")
    fig = plt.figure(figsize=(0.1, 0.1))
    fig.text(0.5, 0.5, "$" + tex + "$", fontsize=fs,
             color="#%02x%02x%02x" % rgb, ha="center", va="center")
    tmp = str(Path(tempfile.gettempdir()) / f"fml_{abs(hash(tex)) % 10**8}.png")
    fig.savefig(tmp, dpi=300, bbox_inches="tight", transparent=True,
                pad_inches=0.03)
    plt.close(fig)
    return tmp


# ───────────────────────── PPT 基础操作 ─────────────────────────

prs = Presentation()
prs.slide_width = Cm(33.87)      # 16:9
prs.slide_height = Cm(19.05)
BLANK = prs.slide_layouts[6]
SW, SH = prs.slide_width, prs.slide_height


def slide():
    return prs.slides.add_slide(BLANK)


def rect(s, l, t, w, h, fill=None, line=None):
    from pptx.enum.shapes import MSO_SHAPE
    sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, l, t, w, h)
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
    sh.shadow.inherit = False
    return sh


def text(s, l, t, w, h, runs, size=16, color=NAVY, bold=False,
         align=PP_ALIGN.LEFT, spacing=1.15):
    """runs: str 或 [(文本, 是否加粗, 颜色或None), ...]"""
    tb = s.shapes.add_textbox(l, t, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    if isinstance(runs, str):
        runs = [(runs, bold, None)]
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = spacing
    for i, (txt, b, c) in enumerate(runs):
        r = p.add_run()
        r.text = latex_to_plain(txt)
        r.font.size = Pt(size)
        r.font.bold = b
        r.font.color.rgb = c if c is not None else color
        r.font.name = "Microsoft YaHei"
    return tb


def bullets(s, l, t, w, h, items, size=15, color=NAVY):
    tb = s.shapes.add_textbox(l, t, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = 1.25
        p.space_after = Pt(6)
        if isinstance(it, str):
            it = [(it, False, None)]
        for txt, b, c in it:
            r = p.add_run()
            r.text = latex_to_plain(txt)
            r.font.size = Pt(size)
            r.font.bold = b
            r.font.color.rgb = c if c is not None else color
            r.font.name = "Microsoft YaHei"
    return tb


def add_formula(s, tex, l, t, w, color="navy", fs=22):
    rgb = {"navy": (31, 59, 99), "blue": (46, 134, 193),
           "red": (192, 57, 43)}.get(color, (31, 59, 99))
    tmp = render_math_png(tex, fs, rgb)
    iw, _ih = _Image.open(tmp).size
    placed = min(w, iw / 300.0)          # 居中放入宽度 w 的区域，避免被拉伸
    left = l + (w - placed) / 2.0
    s.shapes.add_picture(tmp, Inches(left / 914400), Inches(t / 914400),
                         width=Inches(placed / 914400))


def header(s, title, idx):
    rect(s, 0, 0, SW, Cm(2.1), fill=NAVY)
    text(s, Cm(1.2), Cm(0.45), Cm(26), Cm(1.2), title, size=22,
         color=RGBColor(0xFF, 0xFF, 0xFF), bold=True)
    text(s, SW - Cm(4.5), Cm(0.5), Cm(3.5), Cm(1.2),
         f"{idx}/12", size=13, color=RGBColor(0xBB, 0xCC, 0xDD),
         align=PP_ALIGN.RIGHT)
    text(s, Cm(1.2), SH - Cm(1.1), Cm(30), Cm(0.8),
         "用数学看世界 · 越来越热，也越来越涝？", size=10, color=GRAY)


def add_fig(s, name, l, t, w):
    p = FIGS / name
    if not p.exists():
        text(s, l, t, w, Cm(1), f"[缺图 {name}]", size=12, color=RED)
        return
    iw, ih = _Image.open(p).size
    h = w * ih / iw
    if t + h > SH - Cm(1.2):
        h = SH - Cm(1.2) - t
        w = h * iw / ih
    s.shapes.add_picture(str(p), l, t, width=w, height=h)


# ═════════════════════════ 第 1 页 封面 ═════════════════════════
s = slide()
rect(s, 0, 0, SW, SH, fill=NAVY)
rect(s, 0, 0, Cm(0.5), SH, fill=RED)
text(s, Cm(2.5), Cm(3.2), Cm(29), Cm(1),
     "用数学看世界 · 第 40 期", size=16,
     color=RGBColor(0x9E, 0xC5, 0xE8))
text(s, Cm(2.5), Cm(5.2), Cm(29), Cm(3.2),
     "越来越热，也越来越涝？", size=44,
     color=RGBColor(0xFF, 0xFF, 0xFF), bold=True)
text(s, Cm(2.5), Cm(8.6), Cm(29), Cm(1.6),
     "—— 高温与暴雨的联合极值风险", size=24,
     color=RGBColor(0xBB, 0xCC, 0xDD))
rect(s, Cm(2.5), Cm(11.2), Cm(28.5), Cm(3.4),
     fill=RGBColor(0x2A, 0x4A, 0x73))
text(s, Cm(3.2), Cm(11.7), Cm(27), Cm(2.4),
     "核心结论：风险主要来自单独的极端，而非叠加的极端。", size=19,
     color=RGBColor(0xFF, 0xD9, 0x66), bold=True)
text(s, Cm(2.5), SH - Cm(2.6), Cm(29), Cm(1),
     "16 个中国城市 · 1940–2026 年 · 约 50 万条逐日记录",
     size=13, color=RGBColor(0x9E, 0xC5, 0xE8))
text(s, Cm(2.5), SH - Cm(1.7), Cm(29), Cm(1),
     "答辩人：__________　　队伍编号：__________", size=13,
     color=RGBColor(0x9E, 0xC5, 0xE8))

# ═════════════════════════ 第 2 页 问题重述 ═════════════════════════
s = slide()
header(s, "一、问题重述", 2)
bullets(s, Cm(1.2), Cm(2.9), Cm(15.4), Cm(12), [
    [("「五十年一遇」到底怎么算出来的？", True, RED)],
    "换个算法，「五十年一遇」可能变成「二十年一遇」或「八十年一遇」",
    "",
    [("更少被讨论的是：", False, None),
     ("高温和暴雨是两件独立的事吗？", True, RED)],
    "若二者倾向于同时发生，「又热又涝」的概率会远高于把两者当作独立事件相乘",
    "→ 设防标准需要相应提高",
    "",
    [("四问设置", True, NAVY)],
    "① 边缘极值建模：五十年一遇是多少度？",
    "② 联合分布：高温与暴雨相关吗？",
    "③ 非平稳检验：门槛是否在移动？",
    "④ 复合事件识别与城市风险排序",
], size=15)
rect(s, Cm(17.4), Cm(2.9), Cm(15.2), Cm(13.2), fill=LIGHT)
text(s, Cm(18.2), Cm(3.3), Cm(13.6), Cm(1), "数据说明", size=17,
     color=NAVY, bold=True)
bullets(s, Cm(18.2), Cm(4.6), Cm(13.6), Cm(11), [
    "16 个中国城市 · 1940-01-01 ~ 2026-09-18",
    "每城 31,673 天，共约 50 万条记录",
    "变量：日最高气温、日降水量",
    "",
    [("城市分四组", True, NAVY)],
    "A 基准大城市：北京、上海、广州、成都",
    "B 降雨破纪录：防城港、恩平、南宁、荆州、澧县",
    "C 高温破纪录：吐鲁番、重庆、乌鲁木齐、石家庄",
    "D 对照组：哈尔滨、拉萨、昆明",
    "",
    [("⚠ 数据性质", True, RED)],
    "再分析网格产品，非站点实测；",
    "极端降水被显著平滑（详见后页）",
], size=13)

# ═════════════════════════ 第 3 页 数据质量 ═════════════════════════
s = slide()
header(s, "二、数据质量：必须交代的前提", 3)
text(s, Cm(1.2), Cm(2.8), Cm(31), Cm(1),
     "我们用公开气象报道对网格数据做了逐一比对", size=15, color=GRAY)
bullets(s, Cm(1.2), Cm(4.2), Cm(15.4), Cm(6), [
    [("气温：吻合良好 ✅", True, BLUE)],
    "吐鲁番　网格 50.3℃　vs　实测 49.8℃",
    "重庆　　网格 41.7℃　vs　实测 41.6℃",
    "→ 误差在 ±0.5℃ 内，绝对值可引用",
], size=14)
bullets(s, Cm(1.2), Cm(10.4), Cm(15.4), Cm(6), [
    [("降水：被严重平滑 ⚠", True, RED)],
    "恩平单日降水：",
    "　网格 108.7 mm　vs　实测 597.7 mm",
    "　→ 网格只有实测的 18%",
    "原因：网格点是面积平均，而暴雨是强局地现象",
], size=14)
rect(s, Cm(17.4), Cm(2.8), Cm(15.2), Cm(13.4), fill=LIGHT)
text(s, Cm(18.2), Cm(3.2), Cm(13.6), Cm(1),
     "处置：划定结论边界", size=17, color=NAVY, bold=True)
bullets(s, Cm(18.2), Cm(4.5), Cm(13.6), Cm(11.6), [
    [("✅ 可用", True, BLUE)],
    "气温绝对值；降水的城市间相对比较、时间趋势",
    "",
    [("❌ 不可用", True, RED)],
    "降水的绝对量（如「五十年一遇是 X 毫米」）",
    "",
    [("关键：核心结论不受影响", True, NAVY)],
    "Copula 只依赖「秩」，对单调变换不变。",
    "平滑把降水压扁了，却不改变城市内",
    "「哪天雨大、哪天雨小」的相对次序。",
    "",
    "唯一需谨慎处：平滑会削弱极端共现信号，",
    "故报告的排斥程度应视为「下界」。",
], size=13)

# ═════════════════════════ 第 4 页 模型核心 ═════════════════════════
s = slide()
header(s, "三、模型核心：三个数学对象", 4)
rect(s, Cm(1.2), Cm(2.8), Cm(10.1), Cm(13.4), fill=LIGHT)
text(s, Cm(1.8), Cm(3.2), Cm(9), Cm(1), "① 极值分布", size=17,
     color=NAVY, bold=True)
text(s, Cm(1.8), Cm(4.4), Cm(9), Cm(4),
     "极大值的极限分布只有三种形态，由形状参数 ξ 决定", size=13)
add_formula(s, r"H(x)=\exp\left\{-\left[1+\xi\frac{x-\mu}{\sigma}\right]^{-1/\xi}\right\}",
            Cm(1.8), Cm(7.0), Cm(9), fs=17)
bullets(s, Cm(1.8), Cm(9.6), Cm(9), Cm(6), [
    "ξ > 0：重尾，无上界",
    "ξ < 0：有上界",
    "",
    "用于：五十年一遇是多少度",
], size=13)

rect(s, Cm(11.9), Cm(2.8), Cm(10.1), Cm(13.4), fill=LIGHT)
text(s, Cm(12.5), Cm(3.2), Cm(9), Cm(1), "② Copula", size=17,
     color=NAVY, bold=True)
text(s, Cm(12.5), Cm(4.4), Cm(9), Cm(3),
     "把联合分布拆成「各自的强度」+「依赖结构」", size=13)
add_formula(s, r"F(x,y)=C\big(F_X(x),\,F_Y(y)\big)",
            Cm(12.5), Cm(7.0), Cm(9), fs=17)
bullets(s, Cm(12.5), Cm(9.6), Cm(9), Cm(6), [
    "只依赖「秩」，对单调变换不变",
    "",
    "用于：高温与暴雨相关吗",
], size=13)

rect(s, Cm(22.6), Cm(2.8), Cm(10.1), Cm(13.4), fill=LIGHT)
text(s, Cm(23.2), Cm(3.2), Cm(9), Cm(1), "③ 风险倍数 R", size=17,
     color=NAVY, bold=True)
text(s, Cm(23.2), Cm(4.4), Cm(9), Cm(3),
     "实际联合超越概率 ÷ 独立假设下的乘积", size=13)
add_formula(s, r"R=\frac{P(X>x,\,Y>y)}{P(X>x)\,P(Y>y)}",
            Cm(23.2), Cm(7.0), Cm(9), fs=17)
bullets(s, Cm(23.2), Cm(9.6), Cm(9), Cm(6), [
    "R > 1：极端倾向同时发生",
    "R < 1：极端倾向不同时发生",
    "R = 1：与独立无异",
], size=13)

# ═════════════════════════ 第 5 页 问题一结果 ═════════════════════════
s = slide()
header(s, "四、问题一：气温有上界，降水没有", 5)
text(s, Cm(1.2), Cm(2.7), Cm(31), Cm(1),
     "双路互证：区组极大值法（GEV）vs 超阈值法（GPD），12/16 城形状参数差异 < 0.15",
     size=14, color=GRAY)
add_fig(s, "q1_xi_compare.png", Cm(0.8), Cm(4.0), Cm(18.2))
rect(s, Cm(20.0), Cm(4.0), Cm(12.6), Cm(12.2), fill=LIGHT)
text(s, Cm(20.7), Cm(4.4), Cm(11.2), Cm(1),
     "两个相反的分布类型", size=17, color=NAVY, bold=True)
bullets(s, Cm(20.7), Cm(5.7), Cm(11.2), Cm(10), [
    [("气温 ξ < 0（14/16 城）", True, RED)],
    "Weibull 型，存在物理上界",
    "→「破纪录」会越来越难",
    "",
    [("降水 ξ > 0（14/16 城）", True, BLUE)],
    "Fréchet 型，重尾",
    "→「破纪录」可以不断发生",
    "",
    [("公众常把两类破纪录新闻等同看待，", False, RED)],
    [("但它们在数学上是相反的分布。", True, RED)],
], size=13)

# ═════════════════════════ 第 6 页 问题二核心 ═════════════════════════
s = slide()
header(s, "五、问题二：假设被数据推翻（核心）", 6)
rect(s, Cm(1.2), Cm(2.8), Cm(15.2), Cm(4.4),
     fill=RGBColor(0xFD, 0xED, 0xEC))
text(s, Cm(1.8), Cm(3.1), Cm(14), Cm(1),
     "原始假设：高温与暴雨同源 → 联合风险高于独立", size=14,
     color=GRAY)
text(s, Cm(1.8), Cm(4.3), Cm(14), Cm(2.4),
     "数据：越极端，越互相排斥", size=22, color=RED, bold=True)
text(s, Cm(1.8), Cm(6.2), Cm(14), Cm(1),
     "风险倍数 R 的中位数随分位升高而下降", size=13, color=GRAY)
bullets(s, Cm(17.4), Cm(2.8), Cm(15.2), Cm(4.4), [
    "q = 0.90　→　R = 0.72",
    "q = 0.95　→　R = 0.42",
    [("q = 0.99　→　R = 0.32", True, RED)],
], size=16)
text(s, Cm(1.2), Cm(7.6), Cm(31), Cm(1),
     "三条独立证据", size=17, color=NAVY, bold=True)
bullets(s, Cm(1.2), Cm(8.9), Cm(10.1), Cm(8), [
    [("① 季节性错开", True, NAVY)],
    "全期正相关（+0.14~+0.32）",
    "因为热季与雨季整体重合",
    "",
    [("但夏季层内转为负相关", True, RED)],
    "北京 -0.294",
    "拉萨 -0.360",
    "防城港 -0.394",
    "",
    "最热月与最多雨月错开约一个月",
], size=13)
bullets(s, Cm(11.9), Cm(8.9), Cm(10.1), Cm(8), [
    [("② 物理抑制", True, NAVY)],
    "最热 1% 日的平均降水：",
    "北京 0.81mm（全期 1.89）→ 43%",
    "上海 1.43mm（全期 3.65）→ 39%",
    "拉萨 1.26mm（全期 2.35）→ 54%",
    "",
    [("机制", True, RED)],
    "极端高温由下沉气流造成，",
    "而下沉恰恰压制对流",
], size=13)
bullets(s, Cm(22.6), Cm(8.9), Cm(10.1), Cm(8), [
    [("③ Copula 拟合不出尾部", True, NAVY)],
    "q=0.99 处经验 copula 一致低于",
    "所有拟合族（Gumbel/Frank/Gaussian）",
    "",
    [("原因：依赖结构非单调", True, RED)],
    "整体正相关、尾部负相关",
    "而单一 copula 族强制结构单调",
    "",
    [("→ 必须同时报告经验联合概率", True, BLUE)],
], size=13)

# ═════════════════════════ 第 7 页 问题三 ═════════════════════════
s = slide()
header(s, "六、问题三：门槛在移动", 7)
add_fig(s, "q3_trend.png", Cm(0.8), Cm(3.0), Cm(17.6))
rect(s, Cm(19.4), Cm(2.8), Cm(13.2), Cm(13.4), fill=LIGHT)
text(s, Cm(20.1), Cm(3.2), Cm(11.8), Cm(1),
     "16/16 城显著升温", size=18, color=RED, bold=True)
bullets(s, Cm(20.1), Cm(4.5), Cm(11.8), Cm(11.4), [
    "中位速率约 +0.24 ℃/10 年",
    "若为随机波动，出现这种一致性的",
    "概率约 2⁻¹⁶ ≈ 十万分之一",
    "",
    "多重检验校正：32 次检验",
    "　未校正显著 19 项",
    "　BH-FDR 校正后仍 14 项",
    "",
    [("门槛移动（等效重现期）", True, NAVY)],
    "北京　50年 → 6.1 年",
    "昆明　50年 → 9.1 年",
    "防城港 50年 → 13.9 年",
    "",
    [("北京 1940 年的五十年一遇是 40.9℃，", False, RED)],
    [("2026 年已只相当于约 6 年一遇。", True, RED)],
], size=13)

# ═════════════════════════ 第 8 页 问题四 ═════════════════════════
s = slide()
header(s, "七、问题四：复合事件与风险排序", 8)
add_fig(s, "q4_risk.png", Cm(0.8), Cm(3.0), Cm(17.6))
rect(s, Cm(19.4), Cm(2.8), Cm(13.2), Cm(13.4), fill=LIGHT)
text(s, Cm(20.1), Cm(3.2), Cm(11.8), Cm(1),
     "四个窗口全部 < 1", size=18, color=RED, bold=True)
bullets(s, Cm(20.1), Cm(4.5), Cm(11.8), Cm(6), [
    "1 日 → 0.69（排斥最强）",
    "3 日 → 0.86",
    "7 日 → 0.93",
    "15 日 → 0.97（趋向独立）",
    "",
    "→ 结论不依赖窗口定义",
], size=13)
text(s, Cm(20.1), Cm(10.6), Cm(11.8), Cm(5.4),
     "排序：成都、北京、重庆、石家庄居前", size=13, color=NAVY)
bullets(s, Cm(20.1), Cm(11.8), Cm(11.8), Cm(4.4), [
    [("但不宜公布精确名次", True, RED)],
    "9 种设定秩相关中位 0.929（稳健）",
    "但防城港名次在 3~12 间波动",
], size=13)

# ═════════════════════════ 第 9 页 模型检验 ═════════════════════════
s = slide()
header(s, "八、模型检验与灵敏度分析", 9)
bullets(s, Cm(1.2), Cm(3.0), Cm(15.4), Cm(13), [
    [("灵敏度分析（全部主观选择都做了检验）", True, NAVY)],
    "· POT 阈值：0.95 / 0.975 / 0.99 三档对比",
    "· Copula 族：拟合全部 5 族，报告跨族区间",
    "· 非平稳：线性趋势 vs 前后 40 年分段验证",
    "· 复合窗口：1 / 3 / 7 / 15 日",
    "· 排序权重：3 种标准化 × 3 档权重 = 9 种设定",
    "",
    [("交叉验证", True, NAVY)],
    "① 问题一 ↔ 问题二：两种边缘变换口径结论一致",
    "② 问题二 ↔ 问题四：两种独立方法同向",
    "　（copula 联合超越 vs 连通性计数）",
    "③ 与外部数据：网格-实测比对、2026 实测与报道吻合",
], size=13)
rect(s, Cm(17.4), Cm(3.0), Cm(15.2), Cm(13.2),
     fill=RGBColor(0xFD, 0xED, 0xEC))
text(s, Cm(18.2), Cm(3.4), Cm(13.6), Cm(1),
     "三项技术处理（容易被忽略）", size=17, color=RED, bold=True)
bullets(s, Cm(18.2), Cm(4.7), Cm(13.6), Cm(11), [
    [("① 边界检验问题", True, NAVY)],
    "H₀ 的趋势系数为零，落在参数空间边界，",
    "标准 χ²₁ 检验偏保守。",
    "故同时报告两个临界值：",
    "　标准 3.841　/　边界修正 2.706",
    "（Self & Liang, 1987）",
    "",
    [("② 多重检验校正", True, NAVY)],
    "32 次检验不校正则期望 1.6 个假阳性",
    "→ 用 BH-FDR 校正，并同时报告未校正结果",
    "",
    [("③ 不确定度", True, NAVY)],
    "所有重现水平带 95% 自助法区间，",
    "绝不只报点估计",
], size=13)

# ═════════════════════════ 第 10 页 局限与推广 ═════════════════════════
s = slide()
header(s, "九、模型局限与结论边界", 10)
bullets(s, Cm(1.2), Cm(3.0), Cm(15.4), Cm(13), [
    [("四条主要局限", True, RED)],
    "① 只含气温与降水两变量，未考虑湿度、风速、持续时间",
    "② 未建模次生链：高温致旱 → 地表硬化 → 后续暴雨产流加剧。",
    "　　这不是同日联合超越，模型覆盖不到，而它是真实风险路径",
    "③ 降水被网格平滑，极端共现信号被削弱",
    "　　→ 报告的排斥程度应视为下界",
    "④ 风险指标含主观权重，虽作 9 种设定敏感性但无法完全消除",
    "",
    [("一条重要的结论边界", True, RED)],
    "本文给出的是「气候风险」，不是「灾害损失风险」。",
    "二者之间还差一个「暴露度」——人口密度与资产分布。",
], size=13)
rect(s, Cm(17.4), Cm(3.0), Cm(15.2), Cm(13.2), fill=LIGHT)
text(s, Cm(18.2), Cm(3.4), Cm(13.6), Cm(1),
     "推广方向", size=17, color=NAVY, bold=True)
bullets(s, Cm(18.2), Cm(4.7), Cm(13.6), Cm(11), [
    [("① 数据层", True, BLUE)],
    "用站点实测替代网格数据，解决降水平滑问题",
    "",
    [("② 变量层", True, BLUE)],
    "加入湿度、风速、持续时间；用 Vine copula 处理高维",
    "",
    [("③ 空间层", True, BLUE)],
    "max-stable process 建模城市间空间依赖，",
    "回答「区域性同步极端」",
    "",
    [("④ 应用层", True, BLUE)],
    "结合暴露度，把气候风险转为损失风险",
    "",
    [("方法学推广", True, RED)],
    "「单一 copula 无法表达非单调依赖」这一问题",
    "在金融、水文、保险领域同样存在",
], size=12)

# ═════════════════════════ 第 11 页 结论 ═════════════════════════
s = slide()
header(s, "十、结论：三句话", 11)
rect(s, Cm(1.2), Cm(3.0), Cm(31.4), Cm(3.0),
     fill=RGBColor(0xFD, 0xED, 0xEC))
text(s, Cm(2.0), Cm(3.5), Cm(29.8), Cm(2.2),
     "一、气温有上界，降水没有 —— 二者是相反的分布类型", size=19,
     color=RED, bold=True)
rect(s, Cm(1.2), Cm(6.6), Cm(31.4), Cm(3.0),
     fill=RGBColor(0xFD, 0xED, 0xEC))
text(s, Cm(2.0), Cm(7.1), Cm(29.8), Cm(2.2),
     "二、高温与暴雨在日尺度互相排斥 —— 风险主要来自单独的极端", size=19,
     color=RED, bold=True)
rect(s, Cm(1.2), Cm(10.2), Cm(31.4), Cm(3.0),
     fill=RGBColor(0xFD, 0xED, 0xEC))
text(s, Cm(2.0), Cm(10.7), Cm(29.8), Cm(2.2),
     "三、北京历史「五十年一遇」门槛已降至约 6 年一遇", size=19,
     color=RED, bold=True)
rect(s, Cm(1.2), Cm(13.8), Cm(31.4), Cm(3.4), fill=LIGHT)
text(s, Cm(2.0), Cm(14.2), Cm(29.8), Cm(1),
     "防灾含义", size=15, color=NAVY, bold=True)
bullets(s, Cm(2.0), Cm(15.2), Cm(29.8), Cm(1.8), [
    "设防标准须用末期分位（北京平稳 42.2℃ vs 时变 2026 年 45.0℃，差 2.8℃）；"
    "规范修订周期须短于趋势显著期；"
    "暴雨为重尾，历史极值不是上界，设计须留超出历史的余量。",
], size=12)

# ═════════════════════════ 第 12 页 致谢 ═════════════════════════
s = slide()
rect(s, 0, 0, SW, SH, fill=NAVY)
rect(s, 0, 0, Cm(0.5), SH, fill=RED)
text(s, Cm(2.5), Cm(6.5), Cm(29), Cm(2.5), "谢谢各位老师", size=44,
     color=RGBColor(0xFF, 0xFF, 0xFF), bold=True)
text(s, Cm(2.5), Cm(10.0), Cm(29), Cm(1.5),
     "请批评指正", size=22, color=RGBColor(0x9E, 0xC5, 0xE8))
text(s, Cm(2.5), SH - Cm(2.6), Cm(29), Cm(1.6),
     "用数学看世界 · 第 40 期　|　风险主要来自单独的极端，而非叠加的极端",
     size=13, color=RGBColor(0x9E, 0xC5, 0xE8))

prs.save(str(PPTX))
print(f"  saved: {PPTX}  {PPTX.stat().st_size} bytes  ({len(prs.slides.__iter__.__self__._sldIdLst)} 页)")
