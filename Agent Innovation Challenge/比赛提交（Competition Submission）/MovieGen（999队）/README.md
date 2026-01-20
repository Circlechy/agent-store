#  MovieGen(短剧生成agent)

一套面向「60 秒短剧」的 **多 Agent → Seedance(方舟) 渲染 → ffmpeg 装配** 的可运行工程骨架。

- 默认 **10 段 × 6 秒**（60s），每段由 Seedance 生成 **视频+音频**
- 支持 **链式 i2v（尾帧续首帧）** 做段间连贯（可开关，并提供“安全护栏”避免角色漂移）
- 输出 **final.mp4 + subtitles.srt + draft.json（可复现的中间产物）**


---
## 系统框图
![img.png](img.png)
## 1. 快速开始

### 1.1 安装依赖

```bash
pip install -r requirements.txt
# 需要系统安装 ffmpeg（用于拼接与抽帧兜底）
```

### 1.2 配置环境变量

项目会自动读取 `.env`（如果安装了 `python-dotenv`）或系统环境变量。

#### A) Agent 规划用的文本 LLM

必填：

- `LLM_API_BASE`
- `LLM_API_KEY`
- `LLM_MODEL_PROVIDER`（ModelFactory provider 名称，例如 `openai`）
- `LLM_MODEL_NAME`（文本模型名）

#### B) Ark / Seedance 1.5 Pro

必填：

- `ARK_SEEDANCE_CREATE_URL`
- `ARK_SEEDANCE_QUERY_URL_TEMPLATE`（必须包含 `{task_id}`）
- `ARK_SEEDANCE_MODEL`（例如 `doubao-seedance-1-5-pro-251215`）
- `ARK_API_KEY`（用于方舟鉴权）

可选：

- `ARK_AUTH_HEADER_NAME`（默认 `Authorization`）
- `ARK_AUTH_HEADER_VALUE_TEMPLATE`（默认 `Bearer {api_key}`）

#### C) 生成行为与输出

- `SEGMENTS`（默认 10）
- `SEGMENT_DURATION_SEC`（默认 6）
- `CHAIN_MODE`（默认 true，启用尾帧续首帧）
- `WITH_AUDIO`（默认 true）
- `OUTPUT_DIR`（默认 `./outputs`）

#### D) 开发/调试开关（强烈建议比赛前熟悉）

- `DRY_RUN=true`：跳过 Seedance 渲染，只生成 `draft.json` 等中间产物
- `RESUME_EDIT=true`：跳过 Agent 与渲染，直接把已存在的 `seg_XX.mp4` 重新拼接成 `final.mp4`
- `REQUIRE_DRAFT_CONFIRM=true`：渲染前强制输出 draft 预览并询问是否继续
- `DRAFT_CONFIRM_MODE=auto`：只生成 draft 并退出（不询问），适合“先审稿再烧钱”
- `AGENT_JSON_MAX_RETRIES`：Agent JSON 解析/重试次数（默认 4）


### 2.3 一键运行

```bash
python main.py --input "风格:动漫搞笑\n内容:我参加了一个九问 agent大赛...最终获得冠军，结果是梦境"
```

输出完成后会打印：

- `final_video_path: outputs/final.mp4`
- `subtitles_path: outputs/subtitles.srt`

如需查看完整 JSON 状态：

```bash
python main.py --input "..." --json
```

---

## 3. 输入格式

`--input` 支持两种形态：

1) **纯文本**（最推荐）：

```text
风格:港风悬疑
内容:一个外卖员发现客户家...
```

2) **JSON 文本**（如果你要把细粒度参数显式传给 Showrunner）：

```json
{
  "style": "动漫搞笑",
  "brief": "...",
  "segments": 10,
  "segment_duration_sec": 6
}
```

---

## 3. 多 Agent 架构

本项目把“短剧生产”拆成 5 个清晰环节，所有中间产物结构化落盘：

1) **ShowrunnerAgent（总导演）**
   - 产出：`style_bible`（风格圣经、角色定义） + `outline.beats`（10 段节拍）

2) **WriterAgent（编剧）**
   - 产出：每段 6 秒可完成的对白/情绪/停顿 + 动作 + 环境音

3) **ShotAgent（分镜）**
   - 产出：每段最多 2 个镜头的镜头语言、站位、以及 continuity 策略

4) **PromptCompiler（提示词编译器）**
   - 把结构化剧本/分镜编译为 Seedance 友好的 prompt（见下一节）

5) **EditorAgent（装配剪辑）**
   - 产出：段落顺序 + `subtitles.srt`

---

## 5. PromptCompiler：对齐 Seedance 提示词指南的关键点

PromptCompiler 的核心是把每段提示词写成：

**主体 + 运动 + 环境(可选) + 运镜/切镜(可选) + 美学(可选) + 声音(可选)**

并严格执行三个基础原则：

1) **必要信息**：主体+运动必须清晰
2) **清晰信息**：用“特征指定主体”，并全程一致；多人同框用“从左到右/前景到背景”映射
3) **精准切镜**：明确“镜头1/镜头2”，给出切镜时间点，且景别/内容差异明显


