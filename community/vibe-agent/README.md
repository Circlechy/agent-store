# Vibe Agent

基于 **多 Agent 架构** 的工作流 / 代码生成系统，包含 **后端智能体服务** 和 **可视化前端界面**。

本仓库的目标：**让第一次接触该项目的用户，可以在本机快速启动前后端服务并体验完整功能。**
---

## 📁 项目简介
**项目地址**：https://gitcode.com/taojianjun/openJiuwen-vibeCoding

**VibeAgent** 是基于 openJiuwen 框架的智能 Agent 自动生成系统，通过自然语言描述自动生成完整的、可运行的 openJiuwen 代码。系统采用多 Agent 协作架构，支持三种生成模式：ReAct Agent、Workflow 和 Multi-Agent。
![img.png](img.png)


## ⚙️ 环境要求

- **操作系统**
  - Windows 10+
- **后端**
  - Python **3.11**（建议使用 3.11，更高版本未作测试）
  - `pip` 或 `pip3`
- **前端**
  - Node.js **18+**
  - npm（随 Node 一起安装）

---

## 🔑 快速上手（最简单的路径）

1. **conda 创建环境**
   ```powershell
   conda create --name vibe_agent python=3.11
   conda activate vibe_agent
   ```

2. **克隆仓库并进入**（示例路径，按你的实际路径替换）
   ```powershell
   git clone <your-repo-url>
   cd vibeAgent
   ```

3. **安装依赖**
   - **后端（backend）**
     ```powershell
     conda activate vibe_agent
     cd vibeAgent\backend
     pip install -r requirements.txt
     ```

   - **前端**
     ```powershell
     cd vibeAgent\frontend
     npm install
     ```

4. **配置 LLM 服务（必需）**
   - 进入 `vibeAgent/backend/` 目录，复制 `.env.example` 为 `.env`
   - 配置你的 API Key 和模型服务地址：
     ```env
     # 模型提供商：openai / dashscope / others
     MODEL_PROVIDER=dashscope

     # API 服务地址
     API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1

     # API Key（请替换为你的实际密钥）
     API_KEY=your_api_key_here

     # 默认使用的模型名称
     MODEL_NAME=qwen3-coder-plus
     ```

5. **启动服务**
   - **终端 1：启动后端（backend）**
     ```powershell
     cd vibeAgent\backend
     .\start.bat
     # 或手动：python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
     ```

   - **终端 2：启动前端**
     ```powershell
     cd vibeAgent\frontend
     .\start.bat
     # 或手动：npm run dev
     ```

6. **访问地址**
   - **前端界面**：`http://localhost:3000`
   - **后端 API 文档**：`http://localhost:8000/docs`
   - **健康检查**：`http://localhost:8000/api/v1/health`

到这里，你已经完成了**前后端联通的基本运行**。

---

## 🏗️ 系统架构概览
VibeAgent 采用**主协调器-执行器（Master-Executor）**架构模式

![img_1.png](img_1.png)

### 核心组件

**后端（backend）**
- 基于 **openJiuwen** 的多 Agent 架构
- 支持三种运行模式：**ReAct Agent**、**Workflow**、**Multi-Agent**
- 采用 FastAPI 构建 RESTful API，提供标准化的服务接口

**前端（frontend）**
- 基于 **React + TypeScript + Vite + Ant Design**
- 提供可视化工作流构建界面
- 实时展示 Agent 执行过程和结果

### 工作流程

```text
用户请求 → 前端界面 → 后端 API → Agent 编排 → 技能执行 → 结果返回
```

三种模式（ReAct、Workflow、Multi-Agent）采用统一的生成流程：

![img_2.png](img_2.png)

---

### 核心价值

- 降低技术门槛：让非技术人员也能构建 AI 应用
- 提升开发效率：从数小时缩短至数分钟
- 确保代码质量：自动化测试和修复机制
- 支持持续迭代：智慧积累和迭代式修改


