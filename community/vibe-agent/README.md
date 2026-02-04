# Vibe Agent

基于 **多 Agent 架构** 的工作流 / 代码生成系统，包含 **后端智能体服务** 和 **可视化前端界面**。

本仓库的目标：**让第一次接触该项目的用户，可以在本机快速启动前后端服务并体验完整功能。**

---

## 📁 顶层目录结构（当前 README 所在位置）

你现在所在的目录是：`vibeAgent/`（相对于仓库根目录）。核心子项目如下：

```text
vibeAgent/
  ├── agent-core/             # openJiuwen agent-core 代码
  ├── vibeAgent/
  │   ├── backend/            # ✅ 基于 openJiuwen 的多 Agent 后端（本 README 重点）
  │   │   ├── app/            # 后端应用核心代码
  │   │   ├── skills/         # 技能配置与示例
  │   │   ├── logs/           # 日志文件
  │   │   ├── requirements.txt # Python 依赖
  │   │   └── start.bat       # Windows 启动脚本
  │   ├── frontend/           # ✅ React + TS 前端，可视化工作流构建界面
  │   │   ├── src/            # 前端源代码
  │   │   ├── package.json    # Node.js 依赖
  │   │   └── vite.config.ts  # Vite 配置
  │   ├── experiments/        # 实验性工作流
  │   └── sandboxes/          # 沙箱环境
  └── README.md               # 本文件：统一的新手指南
```

> **说明**：本 README 以 `backend + frontend` 为组合进行讲解。

---

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

接下来，本指南将帮助你深入理解系统架构、配置高级功能，并解决常见问题。

---

## 🎯 下一步：开始使用系统

### 验证系统运行状态

1. **检查后端服务**
   - 访问 `http://localhost:8000/api/v1/health` 确认健康状态

2. **检查前端界面**
   - 访问 `http://localhost:3000` 打开可视化界面
   - 确认界面正常加载，无控制台错误

---

## 🏗️ 系统架构概览

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

---

## ❓ 故障排查

### 常见问题与解决方案

#### 问题 1：前端无法连接后端

**症状**：打开前端页面后提示网络错误或无法获取数据

**排查步骤**：
1. 确认后端服务已启动（访问 `http://localhost:8000/docs` 验证）
2. 检查后端端口是否为 `8000`（查看启动日志）
3. 验证 `vibeAgent/frontend/vite.config.ts` 中的代理配置：
   ```typescript
   proxy: {
     '/api': {
       target: 'http://localhost:8000',
       changeOrigin: true,
     },
   }
   ```
4. 检查防火墙或代理设置是否阻止了本地端口通信

#### 问题 2：Python 模块导入错误

**症状**：`ModuleNotFoundError: No module named 'app'`

**解决方案**：
- 确保在 `vibeAgent/backend/` 目录下运行命令
- 检查 Python 环境是否正确（`python --version` 应为 3.11+）
- 重新安装依赖：`pip install -r requirements.txt`
- 如使用虚拟环境，确保已激活：`.\venv\Scripts\activate`（Windows）

#### 问题 3：依赖安装失败或速度慢

**解决方案**：

**Python（pip）**：
```powershell
# 使用清华镜像源
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**Node.js（npm）**：
```powershell
# 使用淘宝镜像
npm config set registry https://registry.npmmirror.com
npm install
```

#### 问题 4：端口被占用

**Windows**：
```powershell
# 查找占用 8000 端口的进程
netstat -ano | findstr :8000

# 终止进程（替换 PID 为实际进程 ID）
taskkill /PID <PID> /F
```

**Linux/macOS**：
```bash
# 查找占用端口的进程
lsof -i :8000

# 终止进程
kill -9 <PID>
```

**或者修改端口**：
- 后端：修改 `vibeAgent/backend/.env` 中的 `PORT=8000` 或启动参数
- 前端：修改 `vibeAgent/frontend/vite.config.ts` 中的 `port: 3000`

#### 问题 5：LLM API 调用失败

**排查步骤**：
1. 验证 `vibeAgent/backend/.env` 中的 `API_KEY` 是否正确
2. 检查 `API_BASE` 地址是否正确
3. 确认模型名称 `MODEL_NAME` 是否支持
4. 查看后端日志中的详细错误信息
5. 测试网络连接和 API 服务可用性

---

## 🚀 进阶使用

### 自定义技能开发

技能文件位于 `vibeAgent/backend/skills/` 目录，每个模式都有对应的技能配置。参考现有技能文件的结构，可以添加自定义技能。

### 智慧积累功能

在 `vibeAgent/backend/.env` 中启用 `ENABLE_WISDOM=true` 后，系统会将执行经验保存到 `.wisdom` 目录，用于优化后续任务执行。

### 多环境部署

- **开发环境**：使用默认配置，启用调试日志
- **生产环境**：建议设置 `DEBUG=false`，启用 SSL 验证，配置 SSRF 防护

---

## 📞 获取帮助

如果按照本文档操作仍无法解决问题：

1. **检查详细文档**：参考上述文档索引中的专项文档
2. **查看日志**：后端日志通常包含详细的错误信息（位于 `vibeAgent/backend/logs/`）
3. **验证环境**：确认 Python 3.11+、Node.js 18+ 版本要求
4. **检查配置**：重点检查 `vibeAgent/backend/.env` 文件和端口配置

---

祝你使用愉快！🎉
