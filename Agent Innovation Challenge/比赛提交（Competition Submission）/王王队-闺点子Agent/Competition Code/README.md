# 闺点子

## 📖 项目简介

闺点子 是一个智能深度搜索系统,专为个人记忆检索和决策支持而设计。系统扮演「闺点子」——用户的贴心手机助手,能够理解用户的偏好、习惯和个人记忆,在购物决策、健康干预等场景中提供精准、个性化的建议。

由王王队开发,基于 OpenJiuwen Agent 框架构建。

### ✨ 核心特性

- 🧠 **个人记忆融合**: 结合用户历史浏览、截图、便签等个人数据进行智能检索，打造个性化“数字大脑”。
- 🔍 **多源数据聚合**: 完美整合 MetaEngine (本地记忆) 与外部平台 (如小红书) 数据。
- 🎯 **场景化决策**: 针对购物口碑、比价选品、健康禁忌等真实生活场景深度优化。
- 🤖 **ReAct 智能规划**: 自动分解复杂查询，动态执行工具调用、查询重写与结果过滤。
- 💬 **流式响应**: 基于 SSE 协议，实时展示 Agent 的思考过程与搜索进度。
- 🎨 **现代化界面**: 响应式的 Vue3 界面，支持文本与图像的双模态输入。

## 🌟 核心应用场景

### 1. 购物决策 (口碑透视)
> **用户问**: "我最近在看这款面霜,适合我吗?"
- **系统工作**: 检索用户历史截图和便签中的肤质记录（如“混合偏干、敏感肌”），同时在外部平台搜索该面霜的成分分析与用户反馈。
- **反馈**: "记得你是**敏感肌**哦,这款面霜含有酒精成分可能会刺激,建议先买小样试试~" [来源:个人记忆, 小红书]

### 2. 多平台比价与对比 (高效选品)
> **用户问**: "蓝牙耳机我在看小米和华为的,哪个性价比高?"
- **系统工作**: 自动提取两款耳机的价格、续航和降噪参数，并结合真实用户评价提供横向对比矩阵。
- **反馈**: 提供两款产品的优劣势分析及基于预算的购买建议。 [来源:淘宝, 京东, 小红书]

### 3. 个人健康干预 (场景化关怀)
> **用户正在浏览含特定食材的菜品 (截图)**
- **系统工作**: 识别菜品成分（如“花生”），并关联用户记忆中的健康档案（如“对花生过敏”）。
- **反馈**: ⚠️ **温馨提醒**: "你正在看的宫保鸡丁含有花生,你之前提到过对花生过敏,上次吃了之后有不良反应,不建议下单哦。" [来源:外卖截图, 微信聊天]

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                       前端层 (Frontend)                      │
│  Vue3 + Naive UI | SSE 流式交互 | 多模态输入 (文本/图像)       │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP / SSE (实时进度与答案)
┌────────────────────────▼────────────────────────────────────┐
│                   API 网关层 (FastAPI Gateway)               │
│        /api/v1/search (POST) | /api/v1/search/image (POST)  │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                工作流引擎层 (Workflow Engine)                │
│  DeepsearchAgent (OpenJiuwen)                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 节点执行流:                                             │ │
│  │ Start ──► [Image Recognition] ──► Entry ──► Team       │ │
│  │ (入口)       (图像意图识别分支)   (分类路由)  (核心搜索)  │ │
│  │                                                 │      │ │
│  │ End ◄── ShowImage ◄── Answer ◄──────────────────┘      │ │
│  │ (结束)   (图片展示)   (答案生成)                         │ │
│  └──────────────────────────────────────────┬─────────────┘ │
└─────────────────────────────────────────────┼───────────────┘
                                              │ 逻辑驱动
┌─────────────────────────────────────────────▼───────────────┐
│                 核心算法层 (Core Algorithms)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Planner    │  │InfoCollector │  │    Answer    │       │
│  │  (智能规划)   │  │ (信息收集)   │  │  (答案生成)   │       │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤       │
│  │• 场景识别分类 │  │• ReAct 循环  │  │• 强制引用溯源  │       │
│  │• 步骤逻辑分解 │  │• 查询改写     │  │• 个人画像融合 │       │
│  │• 内外源优先级 │  │• 相关性过滤   │  │• 语言风格适配 │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└────────────────────────┬──────────────────────┬─────────────┘
                         │ 调用工具              │
┌────────────────────────▼──────────────────────▼─────────────┐
│                        工具层 (Tools)                       │
│  ┌──────────────────────────┐    ┌─────────────────────────┐│
│  │ MetaEngine (本地个人记忆) │    │ Xiaohongshu (外部口碑)   ││
│  │ • 截图 OCR / 便签 / 浏览史│    │ • 商品评价 / 避坑指南     ││
│  │ • 聊天记录 (本地向量检索)  │    │ • 测评文章 / 真实体验    ││
│  └──────────────────────────┘    └─────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 环境要求

- **Python**: >= 3.11
- **Node.js**: >= 16.0
- **操作系统**: Windows / Linux

### 安装步骤

#### 1. 克隆项目

```bash
git clone <repository-url>
cd jiuwen_memory_deepSearch
```

#### 2. 配置环境

复制配置文件模板:

```bash
cp configs/config.yaml.example configs/config.yaml
```

编辑 `configs/config.yaml`,填入必要的配置:

```yaml
# 大模型配置
model:
  provider: openai
  api_base: YOUR_API_BASE_HERE
  api_key: YOUR_API_KEY_HERE
  model_name: YOUR_MODEL_NAME_HERE
  vision_model_name: YOUR_VISION_MODEL_NAME_HERE

# 搜索引擎配置
meta_engine:
  api_url: YOUR_META_ENGINE_URL # 例如 http://localhost:9182

xiaohongshu_engine:
  api_url: YOUR_XIAOHONGSHU_ENGINE_URL # 例如 http://localhost:9183
```

#### 3. 安装依赖

**后端依赖** (使用 uv 包管理器):

```bash
# 安装 uv (如果尚未安装)
pip install uv

# 同步依赖
uv sync
```

**前端依赖**:

```bash
cd frontend
npm install
cd ..
```

### 启动服务

#### 方式一: 一键启动 (推荐)

**Windows**:
```bash
scripts\start_all.bat
```

**Linux**:
```bash
bash scripts/start_all.sh
```

#### 方式二: 分别启动

**启动后端**:

```bash
# Windows
scripts\start_backend.bat

# Linux
bash scripts/start_backend.sh
```

**启动前端**:

```bash
# Windows
scripts\start_frontend.bat

# Linux
bash scripts/start_frontend.sh
```

### 访问应用

- **前端界面**: http://localhost:5173
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/api/v1/docs

## 📚 使用示例

### 方式一: 直接调用 Agent

```python
import asyncio
from jiuwen_memory_deepsearch.core.workflow import DeepsearchAgent

async def example():
    agent = DeepsearchAgent()
    
    # 文本查询
    inputs = {
        "query": "最近在看口红,有哪些牌子性价比高?",
        "is_image": False
    }

    async for chunk in agent.run(inputs):
        print(chunk)

    # 基于图片的查询
    inputs = {
        "image_path": "temp/image.png",
        "is_image": True
    }

    async for chunk in agent.run(inputs):
        print(chunk)

asyncio.run(example())
```

### 方式二: 通过后端 API 调用

**1. 文本搜索**

```python
import requests
import json

# 发起文本搜索
url = "http://localhost:8000/api/v1/search"
data = {"query": "这款面霜适合我吗?"}

response = requests.post(url, json=data, stream=True)

# 解析 SSE 流式响应
for line in response.iter_lines():
    if line:
        line = line.decode('utf-8')
        if line.startswith('data: '):
            data = json.loads(line[6:])
            print(data)
```

**2. 图像上传搜索**

```python
import requests

# 上传图片进行搜索
url = "http://localhost:8000/api/v1/search/image"
files = {"file": open("image.png", "rb")}

response = requests.post(url, files=files, stream=True)

# 解析流式响应
for line in response.iter_lines():
    if line:
        line = line.decode('utf-8')
        if line.startswith('data: '):
            print(line[6:])
```

**使用 curl 调用**:

```bash
# 文本搜索
curl -X POST "http://localhost:8000/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "这款面霜适合我吗?"}'

# 图像搜索
curl -X POST "http://localhost:8000/api/v1/search/image" \
  -F "file=@image.png"
```

### 支持的场景示例

1. **购物决策**: "这款面霜适合我吗?" (结合用户肤质记忆)
2. **商品比价**: "这个耳机在哪个平台最便宜?"
3. **健康干预**: "我能吃这个外卖吗?" (结合过敏史)
4. **口碑查询**: "这款手机有什么坑点?"

## 🛠️ 开发指南

### 项目结构

```
jiuwen_memory_deepSearch/
├── backend/                      # 后端服务
│   ├── api/                     # FastAPI 路由和中间件
│   ├── config/                  # 后端配置
│   └── start_backend.py         # 启动脚本
├── frontend/                    # 前端应用
│   ├── src/
│   │   ├── components/          # Vue 组件
│   │   ├── views/               # 页面视图
│   │   ├── utils/               # 工具函数
│   │   └── App.vue              # 主应用
│   └── package.json
├── jiuwen_memory_deepsearch/    # 核心算法包
│   ├── core/                    # 核心逻辑
│   │   ├── algorithm/           # 算法实现
│   │   ├── workflow.py          # 工作流定义
│   │   └── node.py              # 节点定义
│   ├── prompts/                 # 提示词模板
│   ├── tools/                   # 工具集成
│   └── utils/                   # 工具函数
├── configs/                     # 配置文件
├── scripts/                     # 启动脚本
├── main.py                      # 主程序入口
├── pyproject.toml               # Python 项目配置
└── README.md                    # 本文件
```

### 核心模块说明

#### 1. Workflow Agent

基于 OpenJiuwen 框架的工作流引擎，定义了完整的深度搜索流程：

**主工作流节点**：

- **StartNode**: 入口节点，识别输入模式（文本/图像），初始化搜索上下文并路由。
- **ImageIntentRecognitionNode**: 图像意图识别，利用视觉大模型理解截图内容并自动生成候选查询语句。
- **SearchEntryNode**: 智能路由节点，对查询进行分类并判断是否需要启动深度搜索流程。
- **SearchTeamNode**: 核心搜索节点，封装了规划与信息收集的子工作流。
- **SearchAnswerNode**: 答案生成节点，基于检索结果进行引用溯源，生成个性化且可信的回答。
- **ShowImageNode**: 图片展示节点，从搜索结果中提取相关商品图片进行展示。
- **SearchEndNode**: 结束节点，返回最终结果并清理状态。

**SearchTeam 子工作流**：

负责执行复杂的 ReAct 循环以获取深层信息：

- **SearchPlanReasoningNode (规划节点)**:
  - 使用 Planner 算法分析查询，遵循**逻辑链条最短化**原则。
  - 将问题分解为 2-3 个核心信息收集步骤。
  - 明确区分**内部记忆**与**外部网络**的数据采集优先级。

- **SearchInfoCollectorNode (执行节点)**:
  - 对每个步骤执行 **ReAct 循环** (最大 2 轮)。
  - **工具选择**: 调用 LLM 根据步骤描述选择最合适的搜索工具。
  - **查询重写**: 执行 Query Rewrite，将原始查询扩展为 3-5 个语义相关的查询组。
  - **并行搜索**: 并行调用 MetaEngine/Xiaohongshu 工具获取原始数据。
  - **结果过滤**: 通过 Answerability Filter 剔除无关信息。
  - **发现总结**: 生成该步骤的 **Summarize Findings**，提取核心信息供后续节点使用。

#### 2. 工具系统

- **MetaEngine**: 本地记忆检索(截图、便签、浏览历史)
- **XiaohongshuEngine**: 外部平台数据检索

### 添加新工具

```python
from jiuwen_memory_deepsearch.tools.meta_engine.meta_engine_search import MetaEngineSearchTool

# 注册新搜索引擎
MetaEngineSearchWrapper.register(
    engine_name="your_engine",
    search_url="http://your-api-url",
    max_search_results=5
)

# 创建工具实例
your_tool = MetaEngineSearchTool(
    name="your_tool_name",
    description="Tool description for LLM",
    engine_name="your_engine"
)
```

### 自定义提示词

提示词模板位于 `jiuwen_memory_deepsearch/prompts/` 目录:

- `entry.md`: 入口分类,判断是否需要深度搜索
- `image_intent_recognition.md`: 图像意图识别,生成候选查询
- `planner.md`: 规划生成,分解查询为 2-3 个步骤
- `tool_select.md`: 工具选择,ReAct 模式的工具调用
- `query_rewrite.md`: 查询重写,扩展为多个语义相关查询
- `answerability.md`: 结果相关性判断,过滤无关信息
- `summarize_findings.md`: 发现总结,提取关键信息
- `answer.md`: 答案生成,强制引用溯源,禁止编造信息

## 📊 性能优化

- **流式响应**: 使用 SSE 实现实时进度展示
- **并发搜索**: 多个搜索任务并行执行
- **结果过滤**: 基于可回答性自动过滤无关结果
- **查询重写**: 自动扩展和优化搜索关键词

## 🔧 配置说明

### 主要配置项

```yaml
# 工作流配置
workflow:
  execution_timeout: 7200  # workflow执行超时时间(秒)

# 规划器配置
planner:
  max_step_num: 2          # 最大规划步骤数

# 信息收集器配置
info_collector:
  max_search_results: 5    # 每个工具最大搜索结果数
  max_react_recursion_limit: 2  # ReAct 最大循环次数

# Web API 配置
web_api:
  host: "0.0.0.0"
  port: 8000
  log_level: "INFO"
```

## 🐛 调试与日志

日志文件位于 `logs/` 目录:

- `deepsearch.log`: 主日志
- `deepsearch_error.log`: 错误日志

启用详细日志:

```python
import logging
logging.getLogger('jiuwen_memory_deepsearch').setLevel(logging.DEBUG)
```
