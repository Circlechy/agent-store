# DeepDigest — 快速部署指南

这是一个精简的部署说明，帮助你快速配置并运行 DeepDigest。

---

## 📋 目录

1. [系统要求](#系统要求)
2. [快速开始（5分钟）](#快速开始5分钟)
3. [环境变量配置](#环境变量配置)
4. [运行项目](#运行项目)
5. [浏览器采集功能](#浏览器采集功能)
6. [常见问题](#常见问题)

---

## 系统要求

| 项目 | 要求 |
|------|------|
| **操作系统** | Windows 10/11、macOS、Linux |
| **Python** | **3.11或更高** |
| **内存** | 最低 4GB，推荐 8GB+ |
| **网络** | 需要访问外网（安装依赖、调用LLM API） |

### 检查 Python 版本

```powershell
python --version
# 应输出 Python 3.11.x 或更高
```

---

## 快速开始（5分钟）

### Windows 用户

```powershell
# 1. 进入项目目录
cd E:\deepdigest_v0

# 2. 创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. 升级 pip
python -m pip install --upgrade pip

# 4. 安装所有依赖
pip install -r requirements_simple.txt

# 5. 配置环境变量
copy .env.example .env
# ⚠️ 重要：编辑 .env 文件，填入你的 LLM_API_KEY

# 6. 启动服务
python -m streamlit run deep_digest\src\ui\app.py
```

### macOS / Linux 用户

```bash
# 1. 进入项目目录
cd ~/deepdigest_v0

# 2. 创建并激活虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 3. 升级 pip
python -m pip install --upgrade pip

# 4. 安装所有依赖（一步搞定）
pip install -r requirements_simple.txt

# 5. 配置环境变量
cp .env.example .env
# ⚠️ 重要：编辑 .env 文件，填入你的 LLM_API_KEY

# 6. 启动服务
python -m streamlit run deep_digest/src/ui/app.py
```

浏览器会自动打开 http://localhost:8501

> **📝 注意事项：**
> - 使用 `requirements_simple.txt`（不是 `requirements.txt`）
> - 必须配置 `.env` 中的 API 密钥才能使用 LLM 功能

---

## 环境变量配置

### 🔑 获取 API 密钥（必需）

在使用前，你需要获取一个 LLM API 密钥（以OpenRouter为例）：
1. 访问 https://openrouter.ai/ 注册账号
2. 进入 Settings → API Keys 创建密钥
3. 复制密钥

#### 其他选择

| 提供商 | 获取地址 | 示例密钥 |
|--------|----------|--------------|
| OpenAI | https://platform.openai.com/api-keys | `sk-xxxxxx...` |
| 国内服务商 | 根据服务商官网 | 各不相同 |

### ⚙️ 配置 .env 文件

编辑项目根目录的 `.env` 文件，以下均为示例：

```bash
# ============ 必填配置 ============
LLM_API_KEY=你的真实密钥  # ⚠️ 必须替换！
LLM_API_BASE=https://openrouter.ai/api/v1
LLM_MODEL_NAME=bytedance-seed/seed-1.6-flash
LLM_MODEL_PROVIDER=openai

# ============ 可选配置 ============
# 音频转写（如需使用音频功能）
GROQ_API_KEY=你的真实密钥
GROQ_API_BASE=https://api.groq.com/openai/v1

# Embedding 模型（以seed-1.6-flash为例，如果你的模型支持Embedding）
EMBEDDING_MODEL=BAAI/bge-m3

# 超时设置
WORKFLOW_EXECUTE_TIMEOUT=120
```

### 常用 API Base 配置

| 服务 | LLM_API_BASE | LLM_MODEL_NAME |
|------|--------------|----------------|
| OpenRouter | `https://openrouter.ai/api/v1` | `bytedance-seed/seed-1.6-flash` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| 本地 Ollama | `http://localhost:11434/v1` | `qwen2.5` |

---

## 运行项目

> **⚠️ 重要提示：** 运行前必须先激活虚拟环境！
> 
> ```powershell
> # Windows
> .\.venv\Scripts\Activate.ps1
> 
> # macOS / Linux
> source .venv/bin/activate
> ```

DeepDigest 包含三个独立服务，根据需要启动：

### 1️⃣ Web UI（主界面）

**功能：** 查看、管理、整理碎片

```powershell
# Windows
python -m streamlit run deep_digest\src\ui\app.py

# macOS / Linux
python -m streamlit run deep_digest/src/ui/app.py
```

访问：http://localhost:8501

### 2️⃣ 浏览器采集 API（可选）

**功能：** 支持 Chrome 插件采集网页内容

```powershell
# Windows
python -m deep_digest.src.workflows.api_server

# macOS / Linux
python -m deep_digest.src.workflows.api_server
```

访问：http://127.0.0.1:8787  
API文档：http://127.0.0.1:8787/docs

### 3️⃣ 桌面通知服务（可选）

**功能：** 定时弹窗提醒待办事项

```powershell
# 生产模式（每天 09:00 和 14:00 提醒）
python -m deep_digest.src.services.notifier

# 演示模式（每 10 秒弹一次，用于测试）
python -m deep_digest.src.services.notifier --demo
```

> **💡 命令格式提示：**
> - 使用 `python -m` 运行时，用 **点号** `.` 分隔路径
> - **不要** 加 `.py` 扩展名
> - 例如：`python -m deep_digest.src.workflows.api_server` ✅
> - 错误示例：`python -m deep_digest\src\workflows\api_server.py` ❌

### 🚀 推荐启动方式

开三个终端窗口，**每个都要先激活虚拟环境**：

```powershell
# 每个终端都先执行：
.\.venv\Scripts\Activate.ps1  # 激活虚拟环境

# 然后分别运行：
# 终端 1：主界面
python -m streamlit run deep_digest\src\ui\app.py

# 终端 2：采集 API（如需浏览器插件）
python -m deep_digest.src.workflows.api_server

# 终端 3：通知服务（如需定时提醒）
python -m deep_digest.src.services.notifier
```

**或者使用完整路径（不需要激活虚拟环境）：**

```powershell
# 终端 1
E:\deepdigest_v0\.venv\Scripts\streamlit.exe run deep_digest\src\ui\app.py

# 终端 2
E:\deepdigest_v0\.venv\Scripts\python.exe -m deep_digest.src.workflows.api_server

# 终端 3
E:\deepdigest_v0\.venv\Scripts\python.exe -m deep_digest.src.services.notifier
```

---

## 浏览器采集功能

DeepDigest 提供 Chrome 浏览器插件，支持一键采集网页内容。

### 安装 Chrome 插件

1. 打开 Chrome/Edge 浏览器，访问 `chrome://extensions/`
2. 开启右上角的 **「开发者模式」**
3. 点击 **「加载已解压的扩展程序」**
4. 选择项目中的 `chrome_extension` 文件夹
5. 完成安装 ✅

> 详细使用说明请查看 [chrome_extension/README.md](chrome_extension/README.md)

---

## 常见问题
### ❌ SecurityError: (:) []，PSSecurityException
**原因**：通常在激活虚拟环境中产生该错误，这是由于Windows 系统默认将 PowerShell 执行策略设置为Restricted（受限模式），该模式会禁止运行任何.ps1 脚本文件（包括本地虚拟环境激活脚本），核心是系统安全策略限制了脚本执行权限，而非脚本本身存在语法或路径错误。

**解决：** 
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
在终端执行以上命令放宽当前用户的脚本执行权限，执行时可能会弹出确认提示，输入 Y 并回车确认，再次激活虚拟环境即可。

### ❌ 认证错误：401 - No cookie auth credentials found

**原因：** `.env` 文件中的 `LLM_API_KEY` 未配置或无效

**解决：**
1. 打开 `.env` 文件
2. 将 `LLM_API_KEY=your_llm_api_key_here` 替换为真实密钥
3. 重启所有服务

### ❌ ModuleNotFoundError: No module named 'xxx'

**原因：** 未激活虚拟环境，或依赖包未安装

**解决：**
```powershell
# 1. 检查是否在虚拟环境中
python -c "import sys; print(sys.executable)"
# 输出应包含 .venv，例如：E:\deepdigest_v0\.venv\Scripts\python.exe

# 2. 如果输出不包含 .venv，说明没激活虚拟环境
.\.venv\Scripts\Activate.ps1  # 激活虚拟环境

# 3. 确认提示符变成 (.venv) 而不是 (base)

# 4. 如果还是找不到包，重新安装
pip install -r requirements_simple.txt
```

### ❌ python -m 命令格式错误

**错误示例：**
```powershell
# ❌ 使用反斜杠
python -m deep_digest\src\workflows\api_server

# ❌ 包含 .py 扩展名
python -m deep_digest.src.workflows.api_server.py
```

**正确格式：**
```powershell
# ✅ 使用点号，不带 .py
python -m deep_digest.src.workflows.api_server
```

### ❌ PowerShell 禁止运行脚本

**解决：**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### ❌ 端口被占用

**解决：**
```powershell
# Streamlit 使用其他端口
python -m streamlit run deep_digest\src\ui\app.py --server.port 8502

# API 使用其他端口（需同步修改浏览器插件配置）
# 编辑 api_server.py 或使用环境变量
```

### ❌ 浏览器插件无法连接

**检查清单：**
1. API 服务是否启动？（终端应显示 `Uvicorn running on http://127.0.0.1:8787`）
2. 插件是否已加载？（访问 `chrome://extensions/` 确认）
3. 是否选中了文字？（右键菜单只在选中文字时显示）
4. 确保已激活虚拟环境后启动 API 服务

---


## 🆘 获取帮助

遇到问题？
1. 查看上方 [常见问题](#常见问题) 部分
2. 检查 `.env` 文件配置是否正确
3. 确认所有必需包已安装：`pip list`
4. 查看终端错误日志

---

## 📝 快速参考

### 常用命令

```powershell
# 启动 Web UI
python -m streamlit run deep_digest\src\ui\app.py

# 启动采集 API
python -m deep_digest.src.workflows.api_server

# 启动通知服务
python -m deep_digest.src.services.notifier

# 安装缺失的包
pip install <包名>
```

### 重要文件

- `.env` - API 密钥配置（必须修改）
- `requirements_simple.txt` - 精简依赖列表
- `deep_digest/data/notifier_config.json` - 通知时间配置

---

**Happy Using! 🚀**