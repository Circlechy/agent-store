# OpenJiuwen 自动化 Agent

一个基于 OpenJiuwen 的智能文件操作助手，可以通过自然语言指令执行各种文件系统操作。


## 功能特性

- 📁 **文件读取**: 读取任意文件内容
- ✍️ **文件写入**: 创建和写入文件
- 📂 **目录操作**: 列出目录内容、创建目录
- 🗑️ **文件删除**: 安全删除文件
- 📦 **文件夹压缩**: 将文件夹压缩为 ZIP 文件
- 🤖 **智能理解**: 使用 LLM 理解自然语言指令
- 🔄 **ReAct 模式**: 推理-行动循环，自动规划任务步骤

## 架构设计

本项目采用 **前后端分离架构**，结合了桌面应用和 AI 能力：

### 整体架构

```
┌─────────────────┐    HTTP/SSE    ┌─────────────────┐
│   Electron      │◄─────────────►│   Flask API     │
│   Desktop App   │                │   Server        │
│   - 前端界面     │                │   - Python 后端 │
│   - 文件管理     │                │   - Agent 引擎   │
│   - 实时通信     │                │   - 文件操作     │
└─────────────────┘                └─────────────────┘
                                      │
                                      ▼
                               ┌─────────────────┐
                               │ OpenJiuwen      │
                               │ AI Agent        │
                               │ - 自然语言理解  │
                               │ - 工具执行      │
                               │ - ReAct 推理    │
                               └─────────────────┘
```

### 核心组件

#### 1. **前端 (Electron 桌面应用)**
- **技术栈**: Electron + HTML + CSS + JavaScript
- **功能**:
    - 文件浏览器侧边栏
    - AI 聊天界面
    - 实时执行流显示
    - 工具执行状态跟踪
    - 文件预览功能
- **端口**: 前端通过 HTTP 5001 端口连接后端

#### 2. **后端 (Flask API 服务器)**
- **技术栈**: Python + Flask + OpenJiuwen
- **功能**:
    - 提供 RESTful API 接口
    - 处理 AI Agent 请求
    - 支持流式响应 (SSE)
    - 文件操作代理
- **端口**: 5001
- **主要接口**:
    - `GET /health` - 健康检查
    - `POST /execute` - 执行 AI 查询
    - `POST /stream` - 流式执行 AI 查询
    - `POST /list-directory` - 列出目录内容
    - `POST /read-file` - 读取文件内容

#### 3. **AI Agent (OpenJiuwen 引擎)**
- **框架**: OpenJiuwen ReAct Agent
- **能力**:
    - 理解自然语言指令
    - 自动规划执行步骤
    - 调用文件操作工具
    - 多轮对话推理

## 项目结构

```
openjiuwen-cowork/
├── electron-app/          # Electron 前端应用
│   ├── index.html         # 主界面
│   ├── main.js            # Electron 主进程
│   ├── renderer.js        # 前端逻辑
│   ├── preload.js         # 预加载脚本
│   └── package.json       # Node.js 依赖
├── agent/                # AI Agent 后端
│   ├── __init__.py        # 模块初始化
│   ├── agent.py           # Agent 核心类
│   ├── tools.py           # 工具定义
│   └── prompts.py         # 提示词模板
├── config/               # 配置管理
│   ├── __init__.py
│   └── settings.py        # 环境变量配置
├── api_server.py         # Flask API 服务器
├── main.py               # 命令行入口
├── requirements.txt      # Python 依赖
├── .env.example          # 环境变量示例
└── README.md            # 项目文档
```

## 安装步骤

### 1. 克隆或下载项目

```bash
cd openjiuwen-cowork
```

### 2. 环境配置

#### Python 虚拟环境配置（推荐）

**Windows:**
```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
venv\Scripts\activate

# 安装 Python 依赖
pip install -r requirements.txt
```

**Linux/Mac:**
```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装 Python 依赖
pip install -r requirements.txt
```

#### Node.js 环境配置（前端）

```bash
# 进入 Electron 应用目录
cd electron-app

# 安装 Node.js 依赖
npm install
```

### 3. 配置环境变量

复制 `.env.example` 文件为 `.env`：

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

编辑 `.env` 文件，设置你的 API 密钥：

**使用 OpenAI：**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
LLM_MODEL=gpt-4
```

**使用阿里云百炼（DashScope）：**
```env
LLM_PROVIDER=dashscope
DASHSCOPE_API_KEY=your_dashscope_api_key_here
LLM_MODEL=qwen-turbo
```

可用的 DashScope 模型：
- `qwen-turbo` - 快速响应，8K 上下文
- `qwen-plus` - 平衡性能，32K 上下文
- `qwen-max` - 最强性能，8K 上下文
- `qwen-max-longcontext` - 长上下文版本，30K 上下文

## 启动方法

### 方式一：完整桌面应用（推荐）

启动步骤：

**1. 启动后端服务**
```bash
# 确保 Python 虚拟环境已激活
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# 启动 Flask API 服务器
python api_server.py
```

**2. 启动前端应用（新终端）**
```bash
# 进入 Electron 应用目录
cd electron-app

# 启动桌面应用
npm start
```

### 方式二：命令行模式

如果只需要使用命令行界面，可以直接运行：

```bash
# 确保 Python 虚拟环境已激活
python main.py
```

### 方式三：分别启动前后端进行调试

**调试后端：**
```bash
# 激活虚拟环境后，使用 debug 模式启动
# Windows
venv\Scripts\activate && python api_server.py

# Linux/Mac
source venv/bin/activate && python api_server.py
```

**调试前端：**
```bash
cd electron-app
npm run dev
```

### 服务验证

启动后端服务后，可以访问以下地址验证服务状态：

- **健康检查**: http://localhost:5001/health
- **API 文档**: 访问 http://localhost:5001 查看可用接口

## 端口说明

- **5001**: Flask API 服务器端口
- **Electron**: 默认使用系统默认端口，通过 HTTP 连接到后端的 5001 端口

## 常见问题

### 1. 端口冲突

如果 5001 端口被占用，可以修改 `api_server.py` 中的端口号：

```python
# 修改第 215 行
app.run(host='0.0.0.0', port=5002, debug=False)  # 改为其他端口
```

同时需要相应修改前端的 API 地址配置。

### 2. 虚拟环境问题

如果遇到依赖包问题，可以尝试：

```bash
# 重新创建虚拟环境
rm -rf venv
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 3. 前端启动失败

确保 Node.js 版本 >= 16，并尝试：

```bash
cd electron-app
rm -rf node_modules package-lock.json
npm install
npm start
```

## 使用方法

### 交互式使用

启动程序后，你可以使用自然语言与 Agent 交互：

```
🤖 > 列出当前目录的内容
🤖 > 读取文件 example.txt
🤖 > 创建一个名为 test.txt 的文件，内容为 'Hello World'
🤖 > 在项目根目录创建一个名为 data 的目录
🤖 > 压缩文件夹 data 为 data.zip
```

### 可用命令

- `help` 或 `h`: 显示帮助信息
- `exit` 或 `quit`: 退出程序
- `clear`: 清屏

## 工具说明

Agent 可以使用以下工具：

1. **read_file**: 读取文件内容
    - 参数: `file_path` (文件路径)

2. **write_file**: 写入文件内容
    - 参数: `file_path` (文件路径), `content` (内容), `append` (是否追加)

3. **list_directory**: 列出目录内容
    - 参数: `directory_path` (目录路径，默认为当前目录)

4. **create_directory**: 创建目录
    - 参数: `directory_path` (目录路径)

5. **delete_file**: 删除文件
    - 参数: `file_path` (文件路径)

6. **compress_directory**: 压缩文件夹为 ZIP 文件
    - 参数: `directory_path` (要压缩的文件夹路径), `output_path` (输出的 ZIP 文件路径，可选)

## 配置选项

在 `.env` 文件中可以配置以下选项：

- `LLM_PROVIDER`: LLM 提供商，可选值：`openai`、`dashscope`（默认: `openai`）
- `OPENAI_API_KEY`: OpenAI API 密钥（使用 OpenAI 时必需）
- `DASHSCOPE_API_KEY`: 阿里云百炼 API 密钥（使用 DashScope 时必需）
- `LLM_MODEL`: 使用的模型名称
    - OpenAI: `gpt-4`, `gpt-3.5-turbo` 等（默认: `gpt-4`）
    - DashScope: `qwen-turbo`, `qwen-plus`, `qwen-max` 等（默认: `qwen-turbo`）
- `MAX_ITERATIONS`: Agent 最大迭代次数（默认: 15）
- `VERBOSE`: 是否显示详细日志（默认: `true`）

## 示例场景

### 场景 1: 读取并分析文件

```
🤖 > 读取 requirements.txt 文件，告诉我里面有哪些依赖包
```

### 场景 2: 创建项目结构

```
🤖 > 创建一个名为 src 的目录，然后在里面创建一个 main.py 文件，内容为 'print("Hello World")'
```

### 场景 3: 批量操作

```
🤖 > 列出当前目录，然后读取所有 .txt 文件的内容
```

### 场景 4：整理目录

```
🤖 > 整理下我的目录文件：openjiuwen-cowork\test\case1-模拟教师界面
```

### 场景 5：总结目录下文件

```
🤖 > 帮我总结下这个文件夹openjiuwen-cowork\test\case2-模拟笔记，并在当前目录下生成makedown格式文件：总结文档.md 
```

## 技术栈

- **OpenJiuwen**: Agent 框架和工具集成
- **OpenAI**: LLM 提供商
- **Pydantic**: 数据验证和配置管理
- **python-dotenv**: 环境变量管理

## 注意事项

1. **API 密钥安全**: 请勿将 `.env` 文件提交到版本控制系统
2. **文件路径**: 支持相对路径和绝对路径
3. **权限**: 确保 Agent 有足够的文件系统权限
4. **错误处理**: Agent 会自动处理常见错误并报告

## 故障排除

### 问题: "未配置 OPENAI_API_KEY" 或 "未配置 DASHSCOPE_API_KEY"

**解决方案**:
- 确保 `.env` 文件存在
- 根据选择的 `LLM_PROVIDER` 设置对应的 API 密钥
- 如果使用 OpenAI，设置 `OPENAI_API_KEY`
- 如果使用 DashScope，设置 `DASHSCOPE_API_KEY`

### 问题: "配置验证失败"

**解决方案**: 检查 `.env` 文件中的配置是否正确，确保：
- `LLM_PROVIDER` 设置为 `openai` 或 `dashscope`
- API 密钥不是示例值（不是 "your_xxx_api_key_here"）
- 模型名称与选择的提供商匹配

### 问题: "Request timed out"

**解决方案**:
- 如果使用 OpenAI 遇到超时，可以尝试切换到阿里云百炼（DashScope）
- 检查网络连接
- 尝试使用更快的模型（如 `qwen-turbo` 或 `gpt-3.5-turbo`）

### 问题: "文件操作权限错误"

**解决方案**: 确保程序有足够的文件系统权限，在 Windows 上可能需要以管理员身份运行

## 开发

### 添加新工具

在 `agent/tools.py` 中添加新的工具函数，使用 `@tool` 装饰器：

```python
@tool
def my_new_tool(param: str) -> str:
    """工具描述"""
    # 工具实现
    return "结果"
```

然后在 `get_tools()` 函数中注册新工具。

### 自定义提示词

编辑 `agent/prompts.py` 中的 `SYSTEM_PROMPT` 来修改 Agent 的行为。

## 许可证

本项目采用 MIT 许可证。

## 贡献

欢迎提交 Issue 和 Pull Request！
