<p align="center">
  <img src="img.png" width="180" alt="MovieGen Logo">
</p>
<h1 align="center">MovieGen</h1>

<p align="center">
  <b>🎬短剧生成 Agent —— 多 Agent 结构化规划 · Seedance(方舟) 音画渲染 · ffmpeg 一键装配</b>
</p>

<p align="center">
  <a href="#-使用场景">使用场景</a> •
  <a href="#-核心能力">核心能力</a> •
  <a href="#-快速开始">快速开始</a> •
  <a href="#-架构详解">架构详解</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/framework-OpenJiuwen-orange.svg" alt="OpenJiuwen">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
</p>

---

## 💡 项目简介

**MovieGen** 是一套面向「**60 秒短剧**」的可运行工程骨架：  
你只需要输入 **风格 + 剧情**，系统会自动完成 **“导演统筹 → 编剧 → 分镜 → 提示词编译 → 剪辑装配”** 的生产链路，逐段调用 **Seedance(方舟)** 生成 **视频+音频**，最后用 **ffmpeg** 拼接成成片并输出字幕。

> 🎯 **告诉它你想拍什么，它会自己拆分成 10 段×6 秒的可执行计划，并生成可复现的中间产物。**

> 背景：多数视频生成模型更擅长生成 **几秒到十几秒** 的短片段，直接生成「长视频」往往会遇到 **成本高、失败重试代价大、角色/风格难以长程一致** 等问题。  
> MovieGen 的价值在于把“长视频”拆解为 **可控的分段生产**（默认 10×6s），用 **结构化规划 + 段间连贯策略（可选 i2v）+ 可复现中间产物** 把长程生成变得更稳定、更可迭代。


---

## 🎯 使用场景

MovieGen 适合下面这些“需要快、需要稳定、需要可复现”的短剧生产场景：

### 1) 产品/方案验证（强需求：可解释 + 可复现）
- 多 Agent 分工清晰：导演/编剧/分镜/提示词/剪辑  
- 自动落盘 `draft.json`：风格圣经、分段节拍、台词、镜头、prompt 全部可追溯  
- 支持 **先审稿再渲染**（省钱）：先生成草稿再决定是否渲染

### 2) 短视频内容批量生产（强需求：流程标准化）
- 固定结构：默认 **10 段 × 6 秒**  
- 输出单段 `seg_XX.mp4`，便于后期二剪/替换某一段重新生成  
- 输出 `subtitles.srt`，适配平台字幕流程

### 3) 追求段间连贯的剧情短片（强需求：连续动作/镜头延续）
- 支持 **链式 i2v（尾帧续首帧）** 做段间连贯  
- 内置“安全护栏”避免角色漂移/身份互换：遇到切场/新增角色/单人特写→多人同框等情况自动降级 t2v

---

## ✨ 核心能力

### 1️⃣ 一次输入，自动生产 60 秒短剧
- 默认 **10 段 × 6 秒**（可通过环境变量调整）
- 每段 Seedance 生成 **视频+音频**
- 最终输出：`final.mp4 + subtitles.srt + draft.json`

### 2️⃣ 多 Agent 结构化规划（可解释生成）
- 所有 Agent **只输出 JSON**（有解析失败重试机制）
- 分段节拍明确：钩子 → 推进 → 加压 → 反转 → 收束 → 尾巴

### 3️⃣ PromptCompiler 对齐 Seedance 提示词规范
- 强制 prompt 结构：**主体 + 运动 + 环境 + 运镜/切镜 + 美学 + 声音**
- 强制 **Subject Lock + On-screen 映射**，多人同框按左右/前后定位，降低混淆

### 4️⃣ 成本控制与可复现
- `draft.json`：渲染前的完整快照，可复现、可审稿
- `DRY_RUN=true`：不调用 Seedance，只产出草稿和结构化产物
- `RESUME_EDIT=true`：已有分段视频时仅重新拼接出 `final.mp4`

---

## 🚀 快速开始

### 环境要求
- Python 3.10+
- 本机安装 ffmpeg（用于拼接与尾帧抽帧兜底）

### 1) 安装依赖

```bash
pip install -r requirements.txt
```

### 2) 配置环境变量

项目会自动读取 `.env`（如安装了 `python-dotenv`）或系统环境变量。

#### A) 文本 LLM（Agent 规划必填）
- `LLM_API_BASE`
- `LLM_API_KEY`
- `LLM_MODEL_PROVIDER`
- `LLM_MODEL_NAME`

#### B) Ark / Seedance（必填）
- `ARK_SEEDANCE_CREATE_URL`
- `ARK_SEEDANCE_QUERY_URL_TEMPLATE`（必须包含 `{task_id}`）
- `ARK_SEEDANCE_MODEL`
- `ARK_API_KEY`

#### C) 生成行为与输出（可选）
- `SEGMENTS`（默认 10）
- `SEGMENT_DURATION_SEC`（默认 6）
- `CHAIN_MODE`（默认 true）
- `WITH_AUDIO`（默认 true）
- `OUTPUT_DIR`（默认 `./outputs`）

#### D) 调试/省钱开关（强烈建议）
- `DRY_RUN=true`：跳过 Seedance 渲染，只生成 `draft.json`
- `RESUME_EDIT=true`：跳过 Agent 与渲染，直接把已存在的 `seg_XX.mp4` 拼接成 `final.mp4`
- `REQUIRE_DRAFT_CONFIRM=true`：渲染前强制输出 draft 预览并询问是否继续
- `DRAFT_CONFIRM_MODE=auto`：只生成 draft 并退出（不询问）
- `AGENT_JSON_MAX_RETRIES`：JSON 解析重试次数（默认 4）

> Windows 可用 `FFMPEG_BIN` 指定 ffmpeg.exe 绝对路径。

### 3) 一键运行

```bash
python main.py --input "风格:动漫搞笑\n内容:我参加了一个九问 agent大赛...最终获得冠军，结果是梦境"
```

完成后会打印：
- `final_video_path: outputs/final.mp4`
- `subtitles_path: outputs/subtitles.srt`

查看完整状态（含所有中间 JSON）：

```bash
python main.py --input "..." --json
```

### 4) 输入格式

`--input` 支持两种形态：

**A. 纯文本（推荐）**
```text
风格:港风悬疑
内容:一个外卖员发现客户家...
```

**B. JSON**
```json
{
  "style": "动漫搞笑",
  "brief": "...",
  "segments": 10,
  "segment_duration_sec": 6
}
```

---

## 🏗️ 架构详解

### 系统框图

<p align="center">
  <img src="img_1.png" alt="MovieGen System Diagram" width="900">
</p>

### 多 Agent 生产链路（5 段式）

1) **ShowrunnerAgent（总导演）**  
   - 产出：`style_bible`（风格圣经/角色锚点/镜头语言） + `outline.beats`（10 段节拍）

2) **WriterAgent（编剧）**  
   - 产出：每段 6 秒可完成的对白/情绪/语速/停顿 + 动作 + 环境音

3) **ShotAgent（分镜）**  
   - 产出：每段最多 2 镜头的镜头语言、站位、连续性标签  
   - 输出 `use_tail_frame_as_next_first_frame` 控制是否允许段间 i2v

4) **PromptCompiler（提示词编译器）**  
   - 把结构化剧本/分镜编译为 Seedance prompt  
   - 决定每段 `mode=t2v/i2v`，并写入 Subject Lock / On-screen 映射 / 切镜时间点

5) **EditorAgent（装配剪辑）**  
   - 产出：段落顺序 `segment_order` + `subtitles.srt`

### 段间连贯：CHAIN_MODE + 安全护栏（避免角色漂移）
- 只有在“上一段明确允许续帧”且“角色集合安全不变化”等条件满足时才启用 i2v  
- 优先使用 Seedance 返回的 `last_frame_url` 作为下一段首帧；若缺失则用 ffmpeg 抽尾帧兜底
