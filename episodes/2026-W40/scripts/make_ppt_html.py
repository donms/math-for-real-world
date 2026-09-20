#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""生成答辩幻灯片 HTML 版（路线 C：MathJax 完整公式）。

为什么要单独出一份 HTML：
    技能记录 WPS 会拒绝 PPT 里的 OMML 数学运行（报「需要修复」），
    故 PPTX 走路线 B（块级公式转 PNG）。
    但 PNG 公式**不可编辑、且行内公式只能降级为 Unicode**，
    会丢失部分符号的精确性。
    本 HTML 用 MathJax v3 完整渲染 LaTeX，作为「可编辑/完整公式」的补充版本。

用法：浏览器直接打开，← / → 翻页，F 全屏。
图表用相对路径引用 results/figs/，故本文件须留在 答辩材料/ 目录下。
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "答辩材料" / "答辩PPT.html"

# 每页：标题 + 若干块。块类型：h(小标题) / p(段落) / f(块级公式) / img(图) / li(列表项)
SLIDES: list[dict] = [
    {"t": "用数学看世界 · 第 40 期", "cover": True,
     "sub": "越来越热，也越来越涝？",
     "sub2": "—— 高温与暴雨的联合极值风险",
     "box": "核心结论：风险主要来自单独的极端，而非叠加的极端。",
     "foot": "16 个中国城市 · 1940–2026 年 · 约 50 万条逐日记录"},

    {"t": "一、问题重述", "blocks": [
        {"k": "li", "v": "<b>「五十年一遇」到底怎么算出来的？</b>"},
        {"k": "li", "v": "换个算法，「五十年一遇」可能变成「二十年一遇」或「八十年一遇」"},
        {"k": "li", "v": "<b>更少被讨论的是：高温和暴雨是两件独立的事吗？</b>"},
        {"k": "li", "v": "若二者倾向于同时发生，「又热又涝」的概率会远高于把两者当作独立事件相乘 → 设防标准需相应提高"},
        {"k": "h", "v": "四问设置"},
        {"k": "li", "v": "① 边缘极值建模：五十年一遇是多少度？"},
        {"k": "li", "v": "② 联合分布：高温与暴雨相关吗？"},
        {"k": "li", "v": "③ 非平稳检验：门槛是否在移动？"},
        {"k": "li", "v": "④ 复合事件识别与城市风险排序"},
        {"k": "h", "v": "数据"},
        {"k": "li", "v": "16 城 × 1940-01-01 ~ 2026-09-18，每城 31,673 天"},
        {"k": "li", "v": "A 基准：北京/上海/广州/成都　B 多雨：防城港/恩平/南宁/荆州/澧县"},
        {"k": "li", "v": "C 高温：吐鲁番/重庆/乌鲁木齐/石家庄　D 对照：哈尔滨/拉萨/昆明"},
        {"k": "warn", "v": "数据为再分析网格产品，非站点实测；极端降水被显著平滑"},
    ]},

    {"t": "二、数据质量：必须交代的前提", "blocks": [
        {"k": "h", "v": "气温：吻合良好 ✅"},
        {"k": "li", "v": "吐鲁番　网格 50.3℃　vs　实测 49.8℃"},
        {"k": "li", "v": "重庆　　网格 41.7℃　vs　实测 41.6℃"},
        {"k": "li", "v": "→ 误差在 ±0.5℃ 内，绝对值可引用"},
        {"k": "h", "v": "降水：被严重平滑 ⚠"},
        {"k": "li", "v": "恩平单日降水：网格 108.7 mm　vs　实测 597.7 mm"},
        {"k": "li", "v": "→ 网格只有实测的 <b>18%</b>。原因是网格点为面积平均，而暴雨是强局地现象"},
        {"k": "h", "v": "处置：划定结论边界"},
        {"k": "li", "v": "✅ 可用：气温绝对值；降水的城市间相对比较与时间趋势"},
        {"k": "li", "v": "❌ 不可用：降水的绝对量（如「五十年一遇是 X 毫米」）"},
        {"k": "h", "v": "关键：核心结论不受影响"},
        {"k": "p", "v": "Copula 只依赖「秩」，对单调变换不变。平滑把降水压扁了，却不改变城市内「哪天雨大、哪天雨小」的相对次序。"},
        {"k": "p", "v": "唯一需谨慎处：平滑会削弱极端共现信号，故报告的排斥程度应视为「下界」。"},
    ]},

    {"t": "三、模型核心：三个数学对象", "blocks": [
        {"k": "h", "v": "① 极值分布"},
        {"k": "p", "v": "极大值的极限分布只有三种形态，由形状参数 $\\xi$ 决定："},
        {"k": "f", "v": r"H(x)=\exp\left\{-\left[1+\xi\frac{x-\mu}{\sigma}\right]^{-1/\xi}\right\}"},
        {"k": "li", "v": "$\\xi>0$：重尾，无上界　　$\\xi<0$：有上界"},
        {"k": "h", "v": "② Copula"},
        {"k": "p", "v": "把联合分布拆成「各自的强度」+「依赖结构」："},
        {"k": "f", "v": r"F(x,y)=C\big(F_X(x),\,F_Y(y)\big)"},
        {"k": "li", "v": "只依赖「秩」，对单调变换不变"},
        {"k": "h", "v": "③ 风险倍数"},
        {"k": "f", "v": r"R=\frac{P(X>x,\,Y>y)}{P(X>x)\,P(Y>y)}"},
        {"k": "li", "v": "$R>1$：极端倾向同时发生　$R<1$：倾向不同时发生　$R=1$：与独立无异"},
    ]},

    {"t": "四、问题一：气温有上界，降水没有", "blocks": [
        {"k": "p", "v": "双路互证：区组极大值法（GEV）vs 超阈值法（GPD），12/16 城形状参数差异 $<0.15$"},
        {"k": "img", "v": "../results/figs/q1_xi_compare.png", "w": 640},
        {"k": "h", "v": "两个相反的分布类型"},
        {"k": "li", "v": "<b>气温 $\\xi<0$（14/16 城）</b>：Weibull 型，存在物理上界 →「破纪录」会越来越难"},
        {"k": "li", "v": "<b>降水 $\\xi>0$（14/16 城）</b>：Fréchet 型，重尾 →「破纪录」可以不断发生"},
        {"k": "warn", "v": "公众常把两类破纪录新闻等同看待，但它们在数学上是相反的分布。"},
    ]},

    {"t": "五、问题二：假设被数据推翻（核心）", "blocks": [
        {"k": "p", "v": "原始假设：高温与暴雨同源 → 联合风险<b>高于</b>独立假设。"},
        {"k": "warn", "v": "数据：越极端，越互相排斥。"},
        {"k": "li", "v": "$q=0.90$ → $R=0.72$　　$q=0.95$ → $R=0.42$　　<b>$q=0.99$ → $R=0.32$</b>"},
        {"k": "h", "v": "三条独立证据"},
        {"k": "li", "v": "<b>① 季节性错开</b>：全期正相关（$+0.14\\sim+0.32$，因热季与雨季整体重合），但夏季层内转负：北京 $-0.294$、拉萨 $-0.360$、防城港 $-0.394$；最热月与最多雨月错开约一个月"},
        {"k": "li", "v": "<b>② 物理抑制</b>：最热 1% 日的平均降水仅为全期的 43%（北京）、39%（上海）、54%（拉萨）。机制：极端高温由下沉气流造成，而下沉恰恰压制对流"},
        {"k": "li", "v": "<b>③ Copula 拟合不出尾部</b>：$q=0.99$ 处经验 copula 一致低于所有拟合族"},
        {"k": "h", "v": "原因：依赖结构非单调"},
        {"k": "p", "v": "整体正相关、尾部负相关。而单一 copula 族（Gumbel 只能上尾正相关、Clayton 只能下尾正相关）<b>强制结构单调</b>，表达不了这种结构。"},
        {"k": "warn", "v": "→ 方法论结论：多变量极值分析必须同时报告经验联合概率。"},
    ]},

    {"t": "六、问题三：门槛在移动", "blocks": [
        {"k": "img", "v": "../results/figs/q3_trend.png", "w": 620},
        {"k": "h", "v": "16/16 城显著升温"},
        {"k": "li", "v": "中位速率约 $+0.24$ ℃/10 年。若为随机波动，出现这种一致性的概率约 $2^{-16}$（十万分之一）"},
        {"k": "li", "v": "多重检验校正：32 次检验，未校正显著 19 项，BH-FDR 校正后仍 14 项"},
        {"k": "h", "v": "门槛移动（等效重现期）"},
        {"k": "li", "v": "北京　50 年 → <b>6.1 年</b>　　昆明 50 年 → 9.1 年　　防城港 50 年 → 13.9 年"},
        {"k": "li", "v": "北京 1940 年的五十年一遇是 40.9℃，2026 年已只相当于约 6 年一遇"},
        {"k": "p", "v": "反直觉细节：拉萨移动幅度最大（$+4.23$℃），但等效重现期几乎没变（49.6 年）——因为基线低，分布上界与门槛的相对位置变化不大。<b>「移动幅度」与「等效重现期」是两个不同的量。</b>"},
    ]},

    {"t": "七、问题四：复合事件与风险排序", "blocks": [
        {"k": "img", "v": "../results/figs/q4_risk.png", "w": 620},
        {"k": "h", "v": "四个窗口全部 $<1$"},
        {"k": "li", "v": "1 日 → 0.69（排斥最强）　3 日 → 0.86　7 日 → 0.93　15 日 → 0.97（趋向独立）"},
        {"k": "li", "v": "→ 结论不依赖窗口定义"},
        {"k": "h", "v": "风险排序"},
        {"k": "li", "v": "成都、北京、重庆、石家庄居前"},
        {"k": "warn", "v": "但不宜公布精确名次：9 种设定秩相关中位 0.929（稳健），而防城港名次在 3~12 间波动。"},
    ]},

    {"t": "八、模型检验与灵敏度分析", "blocks": [
        {"k": "h", "v": "灵敏度分析（所有主观选择都做了检验）"},
        {"k": "li", "v": "POT 阈值：0.95 / 0.975 / 0.99 三档对比"},
        {"k": "li", "v": "Copula 族：拟合全部 5 族，报告跨族区间"},
        {"k": "li", "v": "非平稳：线性趋势 vs 前后 40 年分段验证"},
        {"k": "li", "v": "复合窗口：1 / 3 / 7 / 15 日　　排序权重：3 标准化 × 3 权重 = 9 种设定"},
        {"k": "h", "v": "交叉验证"},
        {"k": "li", "v": "① 问题一 ↔ 问题二：两种边缘变换口径结论一致"},
        {"k": "li", "v": "② 问题二 ↔ 问题四：两种独立方法同向（copula 联合超越 vs 连通性计数）"},
        {"k": "li", "v": "③ 与外部数据：网格-实测比对、2026 实测与公开报道吻合"},
        {"k": "h", "v": "三项容易被忽略的技术处理"},
        {"k": "li", "v": "<b>① 边界检验问题</b>：$H_0$ 的趋势系数为零，落在参数空间边界，标准 $\\chi^2_1$ 检验偏保守 → 同时报告标准临界值 3.841 与边界修正 2.706（Self & Liang, 1987）"},
        {"k": "li", "v": "<b>② 多重检验校正</b>：32 次检验不校正则期望 1.6 个假阳性 → 用 BH-FDR 并同时报告未校正结果"},
        {"k": "li", "v": "<b>③ 不确定度</b>：所有重现水平带 95% 自助法区间，绝不只报点估计"},
    ]},

    {"t": "九、模型局限与结论边界", "blocks": [
        {"k": "h", "v": "四条主要局限"},
        {"k": "li", "v": "① 只含气温与降水两变量，未考虑湿度、风速、持续时间"},
        {"k": "li", "v": "② 未建模次生链：高温致旱 → 地表硬化 → 后续暴雨产流加剧。这不是同日联合超越，模型覆盖不到，而它是真实风险路径"},
        {"k": "li", "v": "③ 降水被网格平滑，极端共现信号被削弱 → 报告的排斥程度应视为下界"},
        {"k": "li", "v": "④ 风险指标含主观权重，虽作 9 种设定敏感性但无法完全消除"},
        {"k": "warn", "v": "一条重要的结论边界：本文给出的是「气候风险」，不是「灾害损失风险」。二者之间还差一个「暴露度」——人口密度与资产分布。"},
        {"k": "h", "v": "推广方向"},
        {"k": "li", "v": "① 数据层：用站点实测替代网格数据　② 变量层：加入湿度/风速/持续时间，用 Vine copula 处理高维"},
        {"k": "li", "v": "③ 空间层：max-stable process 建模城市间空间依赖　④ 应用层：结合暴露度转为损失风险"},
        {"k": "li", "v": "方法学推广：「单一 copula 无法表达非单调依赖」在金融、水文、保险领域同样存在"},
    ]},

    {"t": "十、结论：三句话", "blocks": [
        {"k": "warn", "v": "一、气温有上界，降水没有 —— 二者是相反的分布类型"},
        {"k": "warn", "v": "二、高温与暴雨在日尺度互相排斥 —— 风险主要来自单独的极端"},
        {"k": "warn", "v": "三、北京历史「五十年一遇」门槛已降至约 6 年一遇"},
        {"k": "h", "v": "防灾含义"},
        {"k": "li", "v": "设防标准须用末期分位（北京平稳 42.2℃ vs 时变 2026 年 45.0℃，差 2.8℃）"},
        {"k": "li", "v": "规范修订周期须短于趋势显著期（$+0.24$℃/10 年，30 年一修订已落后约 0.7℃）"},
        {"k": "li", "v": "暴雨为重尾，历史极值不是上界，设计须留超出历史的余量"},
    ]},

    {"t": "谢谢各位老师", "cover": True, "sub": "请批评指正",
     "foot": "用数学看世界 · 第 40 期　|　风险主要来自单独的极端，而非叠加的极端"},
]


def k2html(k: str, v: str) -> str:
    """块 → HTML。

    ⚠️ 两个坑：
    1. **公式块不能做 HTML 转义**。MathJax 直接读文本节点，
       若把 `>` 转成 `&gt;`、`&` 转成 `&amp;`，
       公式会解析失败（`P(X&gt;x)` 不是合法 LaTeX）。
       故 `f` 分支直接用原始字符串，只把 `\\[`/`\\]` 定界符降级为 `$$`。
    2. **行内 `$..$` 也不能转义**，同理。故正文里只对
       **不含 `$` 的行**做 html.escape，含 `$` 的行原样输出
       （这些行是我们自己写的固定文案，无 XSS 风险）。
    """
    if k == "f":
        # 统一用 $$ 定界，避免 \\[ 与转义交互出问题
        return f'<div class="formula">$${v}$$</div>'
    if "$" in v:
        body = v                                   # 含公式，不转义
    else:
        body = html.escape(v)
    if k == "h":
        return f"<h2>{body}</h2>"
    if k == "p":
        return f"<p>{body}</p>"
    if k == "img":
        return f'<div class="fig"><img src="{v}"></div>'
    if k == "warn":
        return f'<div class="warn">{body}</div>'
    # li：文案里用 <b>（不是 **），故无需还原转义
    return f"<li>{body}</li>"


def build_slide(sd: dict, idx: int, total: int) -> str:
    if sd.get("cover"):
        parts = [f'<section class="slide cover">',
                 f'<div class="kicker">用数学看世界 · 第 40 期</div>',
                 f'<h1>{html.escape(sd["t"])}</h1>']
        if sd.get("sub"):
            parts.append(f'<div class="sub">{html.escape(sd["sub"])}</div>')
        if sd.get("sub2"):
            parts.append(f'<div class="sub2">{html.escape(sd["sub2"])}</div>')
        if sd.get("box"):
            parts.append(f'<div class="box">{html.escape(sd["box"])}</div>')
        if sd.get("foot"):
            parts.append(f'<div class="foot">{html.escape(sd["foot"])}</div>')
        parts.append("</section>")
        return "\n".join(parts)

    body, buf = [], []
    for b in sd["blocks"]:
        if b["k"] == "li":
            buf.append(b)
            continue
        if buf:
            body.append("<ul>" + "".join(k2html("li", x["v"]) for x in buf)
                        + "</ul>")
            buf = []
        body.append(k2html(b["k"], b["v"]))
    if buf:
        body.append("<ul>" + "".join(k2html("li", x["v"]) for x in buf) + "</ul>")

    return (f'<section class="slide">'
            f'<div class="hd"><h1>{html.escape(sd["t"])}</h1>'
            f'<span class="pg">{idx}/{total}</span></div>'
            f'<div class="body">{"".join(body)}</div>'
            f'<div class="ft">用数学看世界 · 越来越热，也越来越涝？</div>'
            f'</section>')


SLIDES_W = 560

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#1f3b63;--blue:#2e86c1;--red:#c0392b;--light:#f2f6fa}
html,body{height:100%;font-family:"Microsoft YaHei","PingFang SC",sans-serif;
  background:#0d1b2a;color:#1f3b63;overflow:hidden}
#deck{position:relative;width:100%;height:100vh}
.slide{display:none;position:absolute;inset:0;background:#fff;
  padding:clamp(14px,2.4vh,34px) clamp(18px,3vw,54px);flex-direction:column}
.slide.active{display:flex}
.hd{display:flex;justify-content:space-between;align-items:baseline;
  border-bottom:3px solid var(--navy);padding-bottom:.5vh;flex:0 0 auto}
.hd h1{font-size:clamp(17px,2.5vh,28px);color:var(--navy)}
.pg{font-size:clamp(11px,1.4vh,15px);color:#8899aa}
.body{flex:1;overflow-y:auto;padding-top:1.4vh;font-size:clamp(12px,1.85vh,18px);
  line-height:1.65}
.body h2{font-size:clamp(13px,2.0vh,20px);color:var(--blue);
  margin:1.4vh 0 .6vh;padding-left:10px;border-left:4px solid var(--blue)}
.body p{margin:.6vh 0}
.body ul{margin:.4vh 0 .8vh 1.3em}
.body li{margin:.45vh 0}
.warn{background:#fdecea;border-left:4px solid var(--red);color:var(--red);
  font-weight:600;padding:.7vh 1em;margin:.9vh 0;border-radius:4px}
.formula{text-align:center;margin:1.2vh 0;overflow-x:auto}
.fig{text-align:center;margin:.8vh 0}
.fig img{max-width:100%;height:auto}
.ft{flex:0 0 auto;font-size:clamp(9px,1.15vh,12px);color:#9aa7b4;
  padding-top:.5vh;border-top:1px solid #e3e9ef}
.cover{background:var(--navy);color:#fff;justify-content:center;
  border-left:10px solid var(--red)}
.cover .kicker{font-size:clamp(12px,1.8vh,17px);color:#9ec5e8;margin-bottom:2vh}
.cover h1{font-size:clamp(26px,5.2vh,50px);color:#fff;line-height:1.2}
.cover .sub{font-size:clamp(16px,3.0vh,28px);color:#bbccdd;margin-top:1.4vh}
.cover .sub2{font-size:clamp(13px,2.2vh,21px);color:#9ec5e8;margin-top:.6vh}
.cover .box{background:#2a4a73;border-radius:8px;padding:1.8vh 1.6em;
  margin-top:3vh;font-size:clamp(14px,2.4vh,23px);color:#ffd966;font-weight:700}
.cover .foot{margin-top:3vh;color:#9ec5e8;font-size:clamp(11px,1.6vh,15px)}
#hint{position:fixed;right:12px;bottom:8px;color:#66788a;font-size:12px;
  z-index:99}
@media print{.slide{display:flex!important;position:relative;height:auto;
  page-break-after:always}#hint{display:none}}
"""

JS = """
const slides=[...document.querySelectorAll('.slide')];let cur=0;
function show(i){slides[cur].classList.remove('active');cur=(i+slides.length)%slides.length;
  slides[cur].classList.add('active');slides[cur].querySelector('.body')?.scrollTo(0,0);}
document.addEventListener('keydown',e=>{
  if(e.key==='ArrowRight'||e.key==='PageDown'||e.key===' ')show(cur+1);
  else if(e.key==='ArrowLeft'||e.key==='PageUp')show(cur-1);
  else if(e.key==='Home')show(0);
  else if(e.key==='End')show(slides.length-1);
  else if(e.key==='f'||e.key==='F'){document.fullscreenElement?
    document.exitFullscreen():document.documentElement.requestFullscreen();}});
show(0);
"""

head = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>答辩 · 越来越热，也越来越涝？</title>
<script>
MathJax={tex:{inlineMath:[['$','$']],displayMath:[['$$','$$'],['\\\\[','\\\\]']]},
  svg:{fontCache:'global'}};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" async></script>
<style>%s</style></head><body>
<div id="deck">
""" % CSS

body = "\n".join(build_slide(sd, i, len(SLIDES))
                 for i, sd in enumerate(SLIDES, 1))

tail = f"""</div>
<div id="hint">← / → 翻页　F 全屏</div>
<script>{JS}</script>
</body></html>"""

OUT.write_text(head + body + tail, encoding="utf-8")
print(f"  saved: {OUT}  {OUT.stat().st_size} bytes  ({len(SLIDES)} 页)")
