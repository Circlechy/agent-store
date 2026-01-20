<p align="center">
  <img src="assets/openjiuwen.png" width="180" alt="Deep Memory Agent">
</p>

<h1 align="center">DeepMemory Agent</h1>

<p align="center">
  <strong style="font-size: 2em; font-family: 'Arial Black', sans-serif;;">
    ✨ 越 用 越 懂 你 ✨
  </strong>
</p>

<p align="center">
  <b>🧠 新一代记忆系统 —— 深度搜索和文件系统的结合</b>
</p>

<p align="center">
  <a href="#-演示视频">演示视频</a> •
  <a href="#-核心功能">核心功能</a> •
  <a href="#-快速开始">快速开始</a> •
  <a href="#-架构详解">架构详解</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/framework-OpenJiuwen-orange.svg" alt="OpenJiuwen">
  <img src="https://img.shields.io/badge/license-Apache%202.0-green.svg" alt="License">
</p>

---

## 📌 项目简介

**DeepMemory Agent** 是一款基于 [OpenJiuwen Agent Framework](https://gitcode.com/openJiuwen/agent-core) 构建的情感陪伴类智能对话助手，具备长期记忆能力。核心特点是将深度搜索和文件系统的特点融合在记忆系统中，解决了传统记忆系统在记忆提取，记忆检索方面，大模型效果差和容易产生幻觉的问题。

> 🎯 **越用越懂你：倾诉你的苦恼，分享你的快乐，它可以记住有关你的任何事情，是你生活的贴心伴侣。**

### 它能做什么？

| 💼 记忆保存     | 💼 记忆检索 | 🛒 情感陪伴 | 🛒 情感分析 |
|:---------------|:----------|:----------|:--------|
| 无损保存       | 原始记忆翻阅 | 分享生活   | 出谋划策    |
| 按时间线整理   | 关键字查询   | 贴心助手   | 人际关系    |

### 核心亮点：

传统基于大语言模型的记忆系统存在下面几个问题：

- **记忆概念定义模糊**：现有主流记忆系统通常将记忆划分为情景记忆、语义记忆、程序性记忆等类别。然而，这些类别之间的边界不够清晰，同一记忆内容可能同时归属多个类别，导致定义交叉与重叠。

- **记忆使用过程割裂**：当前不同类别的记忆往往独立存储和检索，使用过程中难以有效实现跨类别记忆的关联与整合，导致模型生成回复时出现断裂感，显著影响用户体验。

- **记忆提取与使用存在幻觉问题**：基于大模型的传统记忆系统存在两方面主要问题：一是在记忆提取阶段准确率有限，二是在记忆提取与使用过程中出现语义匹配偏差，从而导致记忆内容误用或输出错误。

本项目采用基于深度搜索与文件系统的记忆系统，有效应对并解决了上述传统记忆系统的痛点：

- **无损记忆保存**：本系统直接基于原始对话历史进行记忆存储，彻底避免了因大模型提取记忆而可能引发的信息幻觉或内容损失。

- **时序化记忆管理**：系统严格按时间顺序组织记忆内容，具备对历史事件的长期视角，有助于避免局部记忆干扰整体对话的连贯性。

- **深度记忆检索**：结合深度搜索技术，集成多种记忆检索工具，支持智能体在对话过程中自主调用并动态修正错误，从而持续优化交互体验。
---

## 🎥 演示视频

[🎥 Demo 1: 记忆效果展示](assets/demo-deep_memory_agent.mp4)

## 📐 方案设计

### 整体架构

DeepMemory Agent 采用分层架构设计，主要包含以下几个层次：

```
┌─────────────────────────────────────┐
│     用户交互层 (Web GUI / CLI)       │
├─────────────────────────────────────┤
│     API 服务层 (FastAPI + Flask)     │
├─────────────────────────────────────┤
│     核心代理层 (DeepMemoryAgent)     │
├─────────────────────────────────────┤
│   MCP 工具层 (Memory Read/Write)     │
├─────────────────────────────────────┤
│     存储层 (文件系统 memory_dir)     │
└─────────────────────────────────────┘
```

### 核心工作流程

1. **对话处理流程**
   - 用户输入消息
   - Agent 接收消息并添加到对话历史
   - 执行 React 循环（LLM 自动判断是否需要调用记忆工具）
   - LLM 可以通过工具搜索、读取历史记忆
   - 基于记忆内容生成自然回复
   - 自动保存对话到记忆系统

2. **记忆存储策略**
   - 原始对话：按日期存储为 `conversation_YYYYMMDD_HHMMSS.txt`
   - 摘要记忆：支持日/月/年三个层级的摘要
   - 文件组织：`memory_dir/YYYY-M/YYYY-M-D/` 的层次结构

3. **记忆检索机制**
   - 关键词搜索：支持跨文件的全文搜索
   - 日期过滤：可按日期或日期范围查询
   - 自动联想：Agent 在回复前会主动检索相关记忆

## ⚡ 核心功能

### 智能对话与记忆联想

Agent 被设计为"知心好友"角色，具备以下特性：

- **自然对话风格**：使用口语化表达，避免暴露技术细节
- **联想式记忆**：基于历史对话的具体细节直接接话
- **深度记忆检索**：在回复前尽可能收集相关记忆信息
- **时间感知**：自然地融入时间相关的表达

### 2️⃣ 记忆管理工具集（MCP Tools）

#### a. 记忆写入工具
- `write_raw_conversation`: 保存原始对话记录
- `write_summarized_memory`: 写入摘要记忆（日/月/年）
- `modify_memory_file`: 修改现有记忆文件（追加/替换）

#### b. 记忆读取工具
- `list_memory_files`: 列出所有记忆文件（支持日期过滤）
- `read_memory_file`: 读取指定记忆文件内容
- `search_memory_files`: 关键词搜索所有记忆文件

#### c. 记忆统计工具
- `get_memory_statistics`: 获取记忆系统统计信息
- `delete_memory_file`: 删除指定记忆文件
- `get_memory_by_date_range`: 按日期范围查询记忆

### 多端交互方式

- **Web 图形界面**：React + Vite 构建的现代化 Web 应用
  - 实时对话界面
  - 记忆文件树形浏览器
  - 文件内容查看器
  
- **命令行界面**：交互式 CLI 工具
  - 简单直观的对话体验
  - 支持异步处理
  - 自动保存对话

### 记忆存储结构

记忆文件按照以下层次结构组织：

```
memory_dir/
├── summary_year_2025.txt          # 年度摘要
├── 2025-1/                         # 月份目录
│   ├── summary_month_202501.txt   # 月度摘要
│   ├── 2025-1-11/                 # 日期目录
│   │   ├── conversation_20250111_101929.txt
│   │   └── summary_day_20250111.txt
│   └── 2025-1-12/
│       └── conversation_20250112_103419.txt
└── 2025-2/
    └── ...
```
---
## 快速开始

### 前置要求

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) 包管理器
- Node.js 16+ 
---
### 环境变量配置

在项目根目录创建 `.env` 文件，配置以下环境变量：

```bash
# LLM 配置
DS_MODEL_NAME=your-model-name
DS_API_KEY=your-api-key
DS_BASE_URL=https://api.example.com/v1

# 可选：自定义记忆目录路径（默认为 ./memory_dir）
MEMORY_DIR=./memory_dir
```
---
### 一键启动 Web GUI

这是最简单快捷的启动方式，适用于日常使用：

#### 步骤 1: 构建前端

**Windows 系统：**
```bash
build_frontend.bat
```

**Linux/Mac 系统：**
```bash
chmod +x build_frontend.sh
./build_frontend.sh
```

**或者手动构建：**
```bash
cd frontend
npm install
npm run build
cd ..
```

#### 步骤 2: 安装 Python 依赖

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -e .
```

#### 步骤 3: 一键启动

```bash
python gui.py
```

启动后会自动：
- 启动 FastAPI 后端服务器（端口 8000）
- 启动 Flask 前端服务器（端口 5000）
- 自动打开浏览器访问 `http://127.0.0.1:5000`

## 🔧 前后端环境配置方法

### 后端环境配置

#### 1. Python 环境

推荐使用 Python 3.12 或更高版本。可以使用虚拟环境：

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

#### 2. 安装依赖

项目使用 `pyproject.toml` 管理依赖，支持多种安装方式：

**使用 uv（推荐，速度快）：**
```bash
# 安装 uv（如果未安装）
pip install uv

# 同步依赖
uv sync
```

**使用 pip：**
```bash
pip install -e .
```

**主要依赖包括：**
- `fastmcp>=0.1.0`: MCP 服务器框架
- `openjiuwen>=0.1.3`: LLM 客户端封装
- `fastapi>=0.104.0`: API 服务器
- `flask>=3.0.0`: 前端静态文件服务器
- `uvicorn>=0.24.0`: ASGI 服务器

#### 3. 环境变量配置

确保已配置 `.env` 文件（见上方"快速开始"部分）。

---
### 前端环境配置

#### 1. Node.js 环境

确保已安装 Node.js 16+ 和 npm：

```bash
node --version  # 应 >= 16.0.0
npm --version
```

#### 2. 安装前端依赖

```bash
cd frontend
npm install
```

**主要依赖包括：**
- `react ^18.2.0`: UI 框架
- `react-markdown ^9.0.0`: Markdown 渲染
- `vite ^5.0.8`: 构建工具

#### 3. 开发模式运行

开发模式下支持热重载：

```bash
cd frontend
npm run dev
```

前端将在 `http://localhost:3000` 运行，并自动代理 API 请求到后端。

#### 4. 生产构建

```bash
cd frontend
npm run build
```

构建产物将输出到 `frontend/dist` 目录，供 `gui.py` 使用。

---
## 📱 使用方式

### 方式一：Web GUI（推荐）

1. 运行 `python gui.py`
2. 浏览器自动打开，或手动访问 `http://127.0.0.1:5000`
3. 在左侧文件树中浏览记忆文件
4. 在中间对话区域输入消息与 Agent 交流
5. 点击"New Conversation"可开始新的对话（会保存当前对话）

### 方式二：命令行 CLI

```bash
python main_cli.py
```

在终端中直接与 Agent 对话，输入 `\exit` 退出并保存对话。

### 方式三：独立 API 服务器

```bash
# 启动 FastAPI 服务器
python api_server.py

# 或使用 uvicorn
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

然后在前端目录运行开发服务器：

```bash
cd frontend
npm run dev
```

## 📦 架构详解

### 1. 核心组件

#### DeepMemoryAgent (`src/deep_memory_agent.py`)

核心 Agent 类，负责：
- 管理对话历史
- 执行 React 循环（推理-行动-观察循环）
- 自动调用 MCP 工具进行记忆操作
- 保存对话到记忆系统

**关键方法：**
- `invoke(query)`: 处理用户查询，返回回复
- `save_conversation_to_memory()`: 保存当前对话到记忆
- `clear_conversation_history()`: 清空对话历史

#### MCP Server (`deep_memory_mcp/main.py`)

基于 FastMCP 框架的 MCP 服务器，提供 9 个记忆管理工具。通过 stdio 协议与 Agent 通信。

**工具分类：**
- 写入工具：`memory_writer.py`
- 读取工具：`memory_reader.py`
- 统计工具：`memory_stats.py`

### 2. 记忆存储设计

#### 文件组织策略

记忆文件采用三级目录结构：
- **年份/月份目录** (`YYYY-M/`): 存储月度摘要
- **日期目录** (`YYYY-M/YYYY-M-D/`): 存储每日的对话和摘要
- **根目录**: 存储年度摘要

这种设计的优势：
- 按时间自然组织，便于查找
- 支持按日期范围快速检索
- 摘要文件分层存储，便于生成不同粒度的总结

#### 文件命名规范

- 对话文件：`conversation_YYYYMMDD_HHMMSS.txt`
- 日摘要：`summary_day_YYYYMMDD.txt`
- 月摘要：`summary_month_YYYYMM.txt`
- 年摘要：`summary_year_YYYY.txt`

---

## ✏️ 自定义 Agent 行为

修改 `src/deep_memory_agent.py` 中的 `system_prompt` 可以调整 Agent 的对话风格和策略。

## 十、常见问题

### Q: 前端构建失败怎么办？

A: 确保 Node.js 版本 >= 16，删除 `node_modules` 和 `package-lock.json` 后重新安装：

**Linux / Mac：**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

**Windows（PowerShell 或 CMD）：**
```bash
cd frontend
rmdir /s /q node_modules
del package-lock.json
npm install
npm run build
```

### Q: API 服务器无法启动？

A: 检查：
1. 端口 8000 是否被占用
2. 环境变量是否正确配置
3. Python 依赖是否完整安装

### Q: Agent 无法调用工具？

A: 检查：
1. MCP 服务器路径是否正确（`deep_memory_mcp/main.py`）
2. `openjiuwen` 库是否正确安装
3. Python 执行路径是否正确

### Q: 记忆文件没有自动保存？

A: 确保：
1. `memory_dir` 目录有写入权限
2. Agent 的 `invoke()` 方法正常返回（没有异常中断）
3. 在 CLI 中使用 `\exit` 正常退出

## 📂 项目结构

```
deep-memory/
├── src/                          # 核心源代码
│   ├── deep_memory_agent.py     # Agent 核心类
│   ├── openai_client.py         # LLM 客户端封装
│   └── utils.py                 # React 循环等工具函数
├── deep_memory_mcp/             # MCP 服务器
│   ├── main.py                  # MCP 服务器入口
│   ├── memory_writer.py         # 记忆写入工具
│   ├── memory_reader.py         # 记忆读取工具
│   ├── memory_stats.py          # 记忆统计工具
│   ├── utils.py                 # 工具函数
│   └── API.md                   # MCP 工具文档
├── frontend/                     # 前端应用
│   ├── src/
│   │   ├── App.jsx              # 主应用组件
│   │   └── main.jsx             # 入口文件
│   ├── dist/                    # 构建产物
│   └── package.json             # 前端依赖
├── memory_dir/                  # 记忆存储目录（自动创建）
├── api_server.py                # FastAPI 服务器
├── gui.py                       # 一键启动 GUI
├── main.py                      # 演示脚本
├── main_cli.py                  # CLI 交互界面
├── pyproject.toml               # Python 项目配置
└── DeepMemoryAgent.md                   # 文档文件
```

## 📜 许可证

[Apache License 2.0](LICENSE)

## 🙌 贡献指南

欢迎参与贡献！

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/new-feature`)
3. 提交更改 (`git commit -m 'Add new feature'`)
4. 推送分支 (`git push origin feature/new-feature`)
5. 提交 Pull Request

## 🔗 相关链接

- [OpenJiuwen Agent Framework](https://gitcode.com/openJiuwen/agent-core) - 底层 Agent 框架

---

**DeepMemory Agent** - 让 AI 记住我们的每一次对话 💬