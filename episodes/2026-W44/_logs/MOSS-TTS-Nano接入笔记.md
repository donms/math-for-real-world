# MOSS-TTS-Nano 接入笔记（2026-09）

> 起因：用户反馈「**原来的 IndexTTS 有点慢**」，要求试试 MOSS-TTS-Nano。
>
> # ★ 最终结论：**不采用，继续用 IndexTTS**
>
> **用户试听后判定：「出来的音频不行」。** 故本线终止，W44 成片仍用 IndexTTS。
> 下面记录**实测数据**与**本机环境踩坑** —— 后者（网络/沙箱/环境复用）有长期价值，
> 下次换任何引擎都会再遇到。

---

## 一、实测结果（W44 全部 73 条 / 2554 字 / 参考音 Don）

| 指标 | IndexTTS-2.5（现用，GPU） | MOSS-TTS-Nano（ONNX，CPU） |
|---|---|---|
| 端到端耗时 | 约 **28 分钟** | **15.93 分钟** |
| 产出音频时长 | 528.3 s | **698.5 s** |
| RTF（耗时/音频） | 3.18× | **1.37×** |
| 速率 | 1.5 字/秒 | **2.7 字/秒** |
| **相对速度** | 基准 | **快 1.76 倍** |

**速度上 MOSS 确实快 1.76 倍** —— 用户的直觉是对的。

**但两项否决因素**：

1. **音质不行**（用户试听判定，最终否决理由）。
2. **节奏偏慢 32%**：同一段文字，MOSS 产出 **698.5 s** 而 IndexTTS 是 **528.3 s**
   ⇒ 成片会从 9 分钟变成 **11.6 分钟**，且**每屏时长全部要重排**。
3. **没有拼音级读音控制**（见第二节）⇒ 已修好的「率」读音会退回去。

> 注：MOSS 那次跑的是 **CPU**。`gsv310` 的 onnxruntime **自带 CUDAExecutionProvider**，
> GPU 版可能更快（未测完，用户叫停）。但既然音质已否决，速度不再相关。

---

## 二、★★ 硬限制：**没有拼音级读音控制**

`infer_onnx.py` 的完整参数表里**没有任何发音标注入口**，
只有 `--enable-wetext-processing`（文本归一化）与 `--enable-normalize-tts-text`。

⇒ **W44 用来修「率」读成 shuài 的手段（`<率|LV4>`）在 MOSS 上不可用。**
换引擎就会丢掉这项能力 —— 而这是 W44 花了两轮才修好的。

可替代的路子（本仓库已有先例，见 `media/audio/tts_读音修正表.json`）：
**同音字替换** —— 把「入园率」写成「入园律」之类。
副作用：① 可能改变停顿；② 多音字在词里时改单字会牵动整词。
（W43 的「涨幅→涨浮」就是这个办法。）

**年份问题不受影响**：W44 的修法是把 `2025` 写成 `二零二五`（纯文本替换，
在 `indextts_engine.years_to_cn()`），**与引擎无关**。

---

## 三、本机网络：`github.com` 不通

实测（2026-09）：

| 主机 | 状态 |
|---|---|
| `github.com:443` | ❌ **不通**（`git clone` 超时、`codeload` 的 zip 也拿不到） |
| `api.github.com` | ✅ 通（urllib 可用） |
| `raw.githubusercontent.com` | ✅ 通 |
| `pypi.org` / 清华镜像 | ✅ 通 |
| `hf-mirror.com` | ✅ 通 |
| `modelscope.cn` | ✅ 通 |

**绕过办法**：`scripts/fetch_moss_repo.py` ——
用 **GitHub API 列文件树 + raw 逐文件下载**（都用 Python urllib，不依赖 git/curl）。
`curl.exe` 在本机沙箱里报告 `schannel: SEC_E_NO_CREDENTIALS`，下载 0 字节，**不可用**。

模型走 **hf-mirror**（`HF_ENDPOINT=https://hf-mirror.com`）：
两个 ONNX 仓库共约 30 秒下完。

---

## 四、环境：不要新建 venv，**复用 `<LOCAL_PATH>

新建的 venv 里 `import torch` 报 `WinError 1114`（`c10.dll` 初始化失败）、
`import onnxruntime` 直接**访问违例**（`0xC0000005`）——
排错代价高且原因在 DLL 层，不是 Python 层。

而 **`<LOCAL_PATH> 已具备全部依赖**：

```
py 3.10.21
torch 2.8.0+cu128   torchaudio 2.8.0+cu128
onnxruntime 1.23.2  numpy 1.26.4
sentencepiece 0.2.2 soundfile 0.14.0
transformers 4.43.4 huggingface_hub 0.25.2
providers: Tensorrt / CUDA / CPU
```

⇒ 直接用它跑 `infer_onnx.py`，**一次通过**。

> ★ **教训：装新引擎前先探测现有环境。**
> `scripts/probe_envs.py` 会逐个环境列出这些包的版本，
> 一秒看出能不能复用 —— 比从零装 torch（几个 GB + DLL 风险）划算得多。
> 这次为此白花了约 30 分钟。

---

## 五、`WeTextProcessing` 装不上 → 用官方开关关掉

`text_normalization_pipeline.py` 需要 `tn`（来自 `WeTextProcessing`），
而它依赖 `pynini`（Windows 上很难装，官方 README 也专门给了 conda 方案）。

**解决**：加 `--disable-wetext-processing`（官方参数）。
文本归一化由 `tts_robust_normalizer_single_script.py` 兜底（它无第三方依赖）。

---

## 六、踩坑记录

1. **`PYTHONUTF8` 只能取 `1`/`0`** ——
   写成 `"utf-8"` 会让 Python 在 **preinit 阶段** Fatal error 退出：
   ```
   Fatal Python error: preconfig_init_utf8_mode:
       invalid PYTHONUTF8 environment variable value
   ```
   看起来像原生崩溃，其实是**环境变量取值非法**。

2. **本机沙箱禁止 pip 写临时目录** ——
   `pip install` 报 `PermissionError: ... pip-unpack-xxx.whl`，
   连**工作区内**的临时目录也拒。需 `danger-full-access` 才能装包。
   （同一限制也让 `venv` 的 `ensurepip` 失败、`torch` 装不全。）

3. **`conda create` 在本机不可用** ——
   libmamba solver 报 `CondaValueError: You have chosen a non-default solver backend
   (libmamba) but it was not recognized`，另有 notices 缓存 `Permission denied`。

4. **系统临时目录不可写** ——
   `os.chmod` 被拒（`WinError 5`），故 `TMP`/`TEMP` 必须指向工作区。

---

## 七、复现命令

```powershell
# 1) 取代码（github.com 不通，走 API + raw）
$PY NewsMCM\scripts\fetch_moss_repo.py            # -> <LOCAL_PATH>

# 2) 取模型（走 hf-mirror）
$env:HF_ENDPOINT = "https://hf-mirror.com"
# snapshot_download 两个仓库到 <LOCAL_PATH>

# 3) 单句试跑（注意用 gsv310 解释器 + 关掉 WeTextProcessing）
& python <LOCAL_PATH> `
    --text "测试一句话。" `
    --prompt-audio-path .\media\audio\ref\voice_ref_Don_norm.wav `
    --output-audio-path out.wav --disable-wetext-processing

# 4) 批量测速（W44 全部口播）
$PY NewsMCM\episodes\2026-W44\scripts\moss_batch_bench.py

# 5) CPU vs GPU 对照（未跑完）
$PY NewsMCM\episodes\2026-W44\scripts\moss_gpu_bench.py 20
```

---

## 八、结论：什么情况下还值得再考虑 MOSS

* 需要**极轻量部署**（0.1B、CPU 可跑、48 kHz）而不追求音色还原度时；
* 素材**不含多音字与复杂数字**、或可接受同音字替换时；
* **无需**克隆特定音色到很高质量时。

本项目**不符合**以上任何一条 —— 我们要克隆 Don 音色、有大量数字与多音字、
且音质是发布级要求。⇒ **继续用 IndexTTS，接受它的速度。**

