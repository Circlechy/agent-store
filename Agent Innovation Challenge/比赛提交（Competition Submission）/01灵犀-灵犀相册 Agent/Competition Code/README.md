# 智慧相册（Smart Album）

一个“上传即索引、对话即找图”的多模态智能相册：

- **语义检索**：输入“海边日落/表格截图/红色跑车”直接找图
- **元数据检索**：按 `created_at/tags/...` 等字段筛选
- **组合检索**：支持“日期 + 语义”混合表达（例如 `1.18 海边`）
- **对话直出图片**：`/agent/chat` 返回 `results.images`，前端聊天直接展示缩略图

## 架构概览

```text
前端（React） ──HTTP──> 后端（FastAPI /api/v1）
                         ├─ Embedding（本地 Qwen3-VL，2048d）
                         ├─ Qdrant（向量检索 + payload 过滤）
                         ├─ Storage（本地落盘 + 预览）
                         └─ Agent（ReAct + OpenAI兼容 fallback）
```

## 快速开始

### 1) 后端（FastAPI）

#### 环境要求

- Python 3.10+
- 16GB+ 内存（首次加载模型较慢）
- 可选：CUDA 或 Apple Silicon（MPS）加速

#### 安装依赖

```bash
pip install -r requirements.txt
```

#### 配置 `.env`

复制模板并按需修改：

```bash
cp .env.template .env
```

关键变量：

- `MODEL_PATH`：指向本地 `qwen3-vl-embedding-2B/` 目录（项目根目录已内置一份，可保持默认）
- `OPENAI_API_KEY/OPENAI_BASE_URL/OPENAI_MODEL_NAME`：启用 Agent（OpenJiuwen / OpenAI兼容工具调用）时需要

#### 启动后端

推荐使用 factory 方式：

```bash
uvicorn app.main:create_app --reload --host 0.0.0.0 --port 8000
```

API 文档：

- Swagger: `http://localhost:8000/docs`

### 2) 前端（React + Vite）

```bash
cd frontend
npm install
npm run dev
```

打开：`http://localhost:5173/`（已配置代理 `/api -> http://localhost:8000`）。

## 关键用法

### 1) 上传并索引

- 页面：`/upload`
- 接口：`POST /api/v1/storage/upload`（支持异步索引）

### 2) 对话找图（推荐入口）

- 页面：`/chat`
- 接口：`POST /api/v1/agent/chat`

对话返回结构包含 `results.images`，前端会自动展示缩略图：

```json
{
  "answer": "...",
  "results": {"total": 3, "images": [{"id": "...", "preview_url": "/api/v1/storage/images/..."}]}
}
```

### 3) 画廊语义检索

- 页面：`/gallery`
- 接口：`GET /api/v1/search/text?query=...&top_k=...`

## 测试

```bash
python -m unittest -q
```

## 常见问题

- **首次搜索/对话很慢**：首次加载 embedding 模型耗时较长；后续会明显加快。
- **OpenAI兼容接口报 400: you must provide a model parameter**：检查 `.env` 的 `OPENAI_MODEL_NAME` 是否为空。
- **对话/检索提示网络错误但后端有日志**：通常是前端超时取消（已在聊天请求中将超时适配为更长时间）。

## 比赛提交文档

比赛用产品介绍与技术方案在：`比赛提交/智慧相册队+智慧相册Agent/`。
