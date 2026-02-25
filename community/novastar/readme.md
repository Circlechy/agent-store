<h1 align="center" style="margin: 0 0 4px; padding:0; line-height:1.1; color: #9370db;">
  NovaStar
</h1>

<p align="center" style="margin-top: 0;">
  <b> 儿童伴学 Agent —— 多 Agent 协作 · 启蒙陪伴一体化 · 多模态交互</b>
</p>

<p align="center">
  <a href="#-项目简介">项目简介</a> •
  <a href="#-核心功能">核心功能</a> •
  <a href="#-使用方式">使用方式</a> •
  <a href="#-架构详解">架构详解</a> •
  <a href="#-快速上手">快速上手</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11.4-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/framework-OpenJiuwen-orange.svg" alt="OpenJiuwen">
  <img src="https://img.shields.io/badge/license-Apache--2.0-blue.svg" alt="License">
</p>

---

## 💡 项目简介

**项目地址**：https://gitcode.com/hanmeng950809/NovaStar

**NovaStar** 是一套面向**儿童伴学**的AI智能体，适用于3-12岁儿童的AI学习与情感陪伴系统，可用于聊天，陪伴，语言和百科学习等。

**兼容性**：openJiuwen v0.1.3

---

## ✨ 核心功能

- 智能用户管理（注册、账号设置和管理、内容推荐等）
- 多模态交互（文字、语音输入，文字、语音和图像输出）
- 会话历史管理（提供会话历史与清理接口）
- 多agents协作：4个agent分工明确，意图识别与路由至各子agent
- 儿童陪伴子agent（闲聊、十万个为什么、睡前故事）
- 儿童启蒙子agent（每日成语、汉字学习）
- 儿童百科子agent（动植物百科，人文地理百科）

## 🔧 使用方式

- 每日推荐入口（点击推荐卡片中感兴趣的功能）
- 子模块单点入口（点击对应功能模块）
- 聊天窗口触发（通过文字或语音输入查询，触发对应功能）

---

## 🏗️ 架构详解

### NovaStar多agents协作流程

![img_1.png](img_1.png)

- 用户请求（文本或语音）→ 若为语音则先调 `/api/voice/transcribe` 转文本。
- FastAPI 调用 `NovaStarWorkflow.run()` 或 `process_message()`。
- 工作流：Start → **IntentRouter** 识别意图 → 按意图路由到 **Commander / Mentor / Companion / Encyclopedia** 之一。
- 对应节点调用 LLM，必要时通过 `novastar/utils/multimodal_utils` 生成图片或 TTS。
- 结果以 JSON 或 SSE 流返回前端，前端按 `content_type` 等做多模态展示。

### 项目结构

```
js/                         # 前端逻辑
novastar/
├── __init__.py             # 模块入口
├── agents/                 # 多agents
│   ├── __init__.py         # 模块入口
│   ├── commander.py        # 多agents意图识别和路由,协调兜底策略
│   ├── companion.py        # 陪伴agent，包括闲聊、十万个为什么和睡前故事
│   ├── encyclopedia.py     # 百科agent，包括动植物百科和人文地理
│   └── mentor.py           # 启蒙agent，每日成语和汉字学习
├── core/                   # 基础功能支撑
│   ├── __init__.py         # 模块入口
│   ├── base_node.py        # node基类
│   ├── global_context.py   # 上下文管理
│   ├── history_store.py    # 历史消息管理
│   └── llm_wrapper.py      # LLM组件（多模态）
├── nodes/                  # 工作流nodes
│   ├── __init__.py         # 模块入口
│   ├── commander_node.py   # 主控，多agents意图识别和路由node，兜底
│   ├── companion_node.py   # 陪伴node
│   ├── encyclopedia_node.py# 百科node
│   └── mentor_node.py      # 启蒙node
├── prompts/                # 提示词管理
├── utils/                  # 工具管理
│   ├── __init__.py         # 模块入口
│   ├── config.py           # 配置管理
│   ├── error_utils.py      # 统一错误处理
│   ├── multimodal_utils.py # 图像和语音多模态统一工具
│   └── text_utils.py       # 文本处理统一工具
└── workflow/               # 工作流
    ├── __init__.py         # 模块入口
    └── novastar_workflow.py# 主工作流
styles/                     # 前端样式
api_server.py               # 前后端交互接口
env.example                 # 环境变量配置
index.html                  # 前端静态页面
main.py                     # 主入口
pyproject.toml              # 依赖声明
uv.lock                     # 依赖锁文件
```

### 主要API

| 方法 | 路径 | 说明                                                |
|------|------|---------------------------------------------------|
| POST | `/api/chat` | 非流式聊天，支持 `intent`、`context`（如 `age`、`child_name`） |
| POST | `/api/chat/stream` | SSE 流式聊天                                          |
| POST | `/api/voice/transcribe` | 语音转文本（ASR）                                        |
| GET | `/api/chat/history` | 获取聊天历史（可选 `child_name` 隔离）                        |
| POST | `/api/chat/history/clear` | 清空当前用户/游客历史                                       |
| POST | `/api/profile/register` | 注册儿童档案                                            |
| POST | `/api/profile/login` | 用户登录                                              |
| POST | `/api/profile/update` | 更新用户档案                                            |
| POST | `/api/profile/delete` | 用户注销并清理历史                                         |

---

## 🚀 快速上手

### 环境要求

- Python 3.11.4+
- openjiuwen v0.1.3

### 1)同步依赖

```bash
# 同步所有依赖（包括开发依赖）
uv sync
# 仅安装生产依赖
uv sync --no-dev
```

### 2) 配置环境变量

```bash
# 编辑 .env，配置API_BASE和API_KEY
cp env.example .env
```

### 3) 后端服务启动

```bash
# 方式1: 直接运行
uv run python api_server.py

# 方式2: 使用uvicorn
uv run uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```
### 4) 前端服务启动

```
# 推荐通过后端静态资源访问（避免 file:// 的跨域限制）
http://localhost:8000/static/index.html
```