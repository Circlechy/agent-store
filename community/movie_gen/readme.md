<h1 align="center" style="margin: 0 0 4px; padding:0; line-height:1.1;">
  <img src="img_2.png" width="400" alt="MovieGen Logo" style="display:block; margin:0 auto;" />
  MovieGen
</h1>

<p align="center" style="margin-top: 0;">
  <b>🎬短剧生成 Agent —— 多 Agent 结构化规划 · Seedance(方舟) 音画渲染 · ffmpeg 一键装配</b>
</p>

<p align="center">
  <a href="#-使用场景">使用场景</a> •
  <a href="#-核心能力">核心能力</a> •
  <a href="#-快速开始">快速开始</a> •
  <a href="#-架构详解">架构详解</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/framework-OpenJiuwen-orange.svg" alt="OpenJiuwen">
  <img src="https://img.shields.io/badge/license-Apache--2.0-blue.svg" alt="License">
</p>

---

## 💡 项目简介
**项目地址**：https://gitcode.com/AFSDFASD/MovieGen

**MovieGen** 是一套面向「**短剧生成**」的可运行工程骨架：  
你只需要输入 **风格 + 剧情**，系统会自动完成 **“导演统筹 → 编剧 → 分镜 → 提示词编译 → 剪辑装配”** 的生产链路，逐段调用 **Seedance(方舟)** 生成 **视频+音频**，最后用 **ffmpeg** 拼接成成片。

> 🎯 **告诉它你想拍什么，它会自己拆分成多段的可执行计划，并生成可复现的中间产物。**

> 背景：多数视频生成模型更擅长生成 **几秒到十几秒** 的短片段，无法直接生成「长视频」，分段生成往往会遇到 **角色/风格难以长程一致** 等问题。  
> MovieGen 的价值在于把“长视频”拆解为 **可控的分段生产**，用 **结构化规划 + 段间连贯策略（可选 i2v）+ 可复现中间产物** 把长程生成变得更稳定、更可迭代。


---

## 🎯 使用场景

MovieGen 面向个人创作者、内容团队，适合所有「希望把长视频拆解为可控、可复现生产流程」的场景。

### 👤 个人创作者 / AI 玩家

当你只有一个想法，却不想花时间反复打磨镜头与剪辑时：

- 一句话剧情即可生成完整短剧
- 自动拆分节奏与分镜，直接得到成片
- 支持反复试错与快速重做某一段
- 低成本探索不同风格与题材

**典型场景：**  
AI 短剧创作、剧情脑洞实验、比赛作品、作品集 Demo、自媒体尝试

---

### 👥 内容团队 / 工作室

当你需要 **稳定批量产出内容**，而不是一次性手工制作：

- 标准化流程，批量生成多条视频
- 结构统一，方便分工协作
- 单段可替换重做，提高修改效率
- 适合系列化与持续更新

**典型场景：**  
短视频矩阵号、剧情连载、品牌内容日更、广告创意批量生成、MCN 工作流


---

## ✨ 核心能力

### 1️⃣ 跨段一致性设计
由于当前视频生成模型单次稳定时长通常仅为 **几秒到十几秒**，直接生成长视频容易出现：

- 角色外观漂移（换脸 / 换发型 / 服装变色）
- 场景突变（光线 / 布景 / 道具不连续）
- 动作断裂（姿态跳变 / 时序不连贯）
- 音画重置（环境声、氛围不连续）

MovieGen 采用 **「叙事切分 + 结构化约束 + 段间续帧」** 的工程方案，保障长视频的一致性与可控性。

### 2️⃣ 多 Agent 结构化规划（可解释生成）
- 所有 Agent **只输出 JSON**（有解析失败重试机制）
- 分段节拍明确：钩子 → 推进 → 加压 → 反转 → 收束 → 尾巴

### 3️⃣ PromptCompiler 对齐视频生成提示词规范
- 强制 prompt 结构：**主体 + 运动 + 环境 + 运镜/切镜 + 美学 + 声音**
- 强制 **Subject Lock + On-screen 映射**，多人同框按左右/前后定位，降低混淆

### 4️⃣ 成本控制与可复现
- `draft.json`：渲染前的完整快照，可复现、可审稿
- `DRY_RUN=true`：不调用 Seedance，只产出草稿和结构化产物
- `RESUME_EDIT=true`：已有分段视频时仅重新拼接出 `final.mp4`

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
   - 产出：每段规定时长的可完成的对白/情绪/语速/停顿 + 动作 + 环境音

3) **ShotAgent（分镜）**  
   - 产出：每段最多 2 镜头的镜头语言、站位、连续性标签  
   - 输出 `use_tail_frame_as_next_first_frame` 控制是否允许段间 i2v

4) **PromptCompiler/finalizer（提示词编译器）**  
   - 把结构化剧本/分镜编译为 Seedance prompt  
   - 决定每段 `mode=t2v/i2v`，并写入 Subject Lock / On-screen 映射 / 切镜时间点

5) **EditorAgent（装配剪辑）**  
   - 产出：段落顺序 `segment_order` + `subtitles.srt`

---

## 🚀 快速开始

### 环境要求
MovieGen 基于 **openJiuwen v0.1.3** 运行。  
⚠️ 必须先安装 openJiuwen，再运行本项目。

- openjiuwen v0.1.3
- 本机安装 ffmpeg

### 1) 安装依赖
### ① 克隆 openJiuwen（主仓库）

```bash
git clone https://github.com/your-org/openjiuwen.git
cd openjiuwen
pip install -U openjiuwen
```

### ② 放置目录结构（必须同级）

```
workspace/
├─ openjiuwen/
└─ MovieGen/   ← 本项目
```
③ MovieGen 环境

```powershell
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

### 3) 安装 ffmpeg（必须）

#### ✅ 方式一：通过系统 PATH 安装（推荐）

##### Windows（推荐：winget 或 chocolatey）

**A) 使用 winget（Windows 10/11 常见自带）**
```powershell
winget install Gyan.FFmpeg
```

安装后重开终端，检查：
```powershell
ffmpeg -version
```

**B) 使用 Chocolatey（已装 choco 的用户）**
```powershell
choco install ffmpeg -y
```

检查：
```powershell
ffmpeg -version
```

##### macOS（Homebrew）
```powershell
brew install ffmpeg
ffmpeg -version
```

##### Ubuntu / Debian
```powershell
sudo apt update
sudo apt install -y ffmpeg
ffmpeg -version
```

##### CentOS / RHEL（常见做法）
```powershell
sudo yum install -y ffmpeg
# 或者 dnf install -y ffmpeg
ffmpeg -version
```

---

#### ✅ 方式二：手动下载

如果你无法用 winget/choco，可以手动下载 ffmpeg 并指定路径：

1) 下载 ffmpeg（任意发行版均可），解压后找到：
`...\ffmpeg\bin\ffmpeg.exe`

2) 用环境变量指定 ffmpeg 路径（推荐写到 `.env`）：

**在 `.env` 里添加：**
```powershell
FFMPEG_BIN=...（填写你的路径）\ffmpeg\bin\ffmpeg.exe
```

或在 PowerShell 临时设置（仅当前窗口有效）：
```powershell
$env:FFMPEG_BIN="...（填写你的路径）\ffmpeg\bin\ffmpeg.exe"
```

3) 验证是否可用（MovieGen 会优先使用 `FFMPEG_BIN`）：
```powershell
...（填写你的路径）\ffmpeg\bin\ffmpeg.exe -version
```

---

### 4) 一键运行

```powershell
python main.py --input "风格:xxx\n内容:xxx"
```

完成后会打印：
- `final_video_path: outputs/final.mp4`
- `subtitles_path: outputs/subtitles.srt`

### 5) 输入格式

`--input` 支持两种形态：

**A. 纯文本（推荐）**
```text
风格:xxx
内容:xxx
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


