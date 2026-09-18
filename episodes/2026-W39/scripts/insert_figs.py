"""把生成的插图插入论文对应位置，并修正字体缺失的下标字符。

插图路径必须是**绝对路径**（项目 md2docx 的硬性要求，见 01_操作手册.md 第 ⑦ 步）。
"""
import re
from pathlib import Path

EP = Path(r".\episodes\2026-W39")
PAPER = EP / "paper" / "论文.md"
FIG = EP / "results" / "figs"

# (插入点：紧跟该小节标题之后, 图片文件名, 图注)
INSERTS = [
    ("### 5.4 频域可实现区间（问题一的回答）",
     "fig01_transmissibility.png",
     "图 1-1　可调阻尼带来的传递率可实现区间"),
    ("### 5.5 被动悬架的\"设计点折中\"",
     "fig04_tradeoff.png",
     "图 1-2　三个目标的最优阻尼互不相同（相差 13 倍）"),
    ("**结论 2.1：决定隔振性能的是作动器的力域，而非响应速度。**",
     "fig02_force_bandwidth.png",
     "图 2-1　力域 × 带宽二维扫描：带宽提高 10 倍仅改善约 2%"),
    ("### 6.5 半主动可达集与帕累托前沿",
     "fig03_reachable.png",
     "图 2-2　半主动可达集与帕累托前沿"),
    ("### 7.3 分频段优势",
     "fig05_band.png",
     "图 3-1　分频段优势：半主动优势集中在 2.5 Hz 以上"),
    ("**排序翻转 0/10 次**",
     "fig06_sensitivity.png",
     "图 3-2　灵敏度分析：排序翻转 0 次，幅度波动显著"),
    ("**结论 8.3**：**半主动的真实价值在于\"免于为不同工况重新标定\"**。",
     "fig07_control_layers.png",
     "图 4-1　控制权限层级与性能阶梯"),
]


def main() -> int:
    t = PAPER.read_text(encoding="utf-8")
    n = 0
    for anchor, fname, caption in INSERTS:
        img = FIG / fname
        if not img.exists():
            print(f"  [!] 缺图 {fname}")
            continue
        if fname in t:
            print(f"  [skip] {fname} 已插入")
            continue
        idx = t.find(anchor)
        if idx < 0:
            print(f"  [!] 找不到锚点：{anchor[:30]}")
            continue
        # 插到锚点所在行之后
        eol = t.find("\n", idx)
        block = f"\n\n![{caption}]({img.as_posix()})\n"
        t = t[:eol] + block + t[eol:]
        n += 1
        print(f"  [ok] 插入 {fname}")

    # 修正字体缺失字符：下标 ₀ → 普通 0
    before = t.count("₀")
    t = t.replace("c₀", "c0").replace("n₀", "n0").replace("u₀", "u0")
    t = t.replace("₀", "0")
    print(f"  [font] 替换下标 ₀ 共 {before} 处（Matplotlib 中文字体无此字形）")

    PAPER.write_text(t, encoding="utf-8")
    print(f"\n完成 {n} 处插入 → {PAPER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
