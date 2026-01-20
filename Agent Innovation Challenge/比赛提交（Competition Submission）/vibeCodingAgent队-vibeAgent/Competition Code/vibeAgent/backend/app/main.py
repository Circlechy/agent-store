"""
Backend V3 - 基于 openJiuwen 的多 Agent 系统

主入口文件
"""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# 确保项目根目录在 Python 路径中
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 添加 openjiuwen 本地路径到 Python 路径（必须在导入 openjiuwen 之前）
# 路径：../../agent-core（包含 openjiuwen 包的父目录）
workspace_root = project_root.parent.parent  # D:\demo\vibe\vibe0116
openjiuwen_parent = workspace_root / "agent-core"
if openjiuwen_parent.exists() and str(openjiuwen_parent) not in sys.path:
    sys.path.insert(0, str(openjiuwen_parent))

# ========== SSL 验证配置（必须在导入 openJiuwen 相关模块之前设置）==========
# 如果环境变量未设置，则默认禁用 SSL 验证（仅用于开发/测试环境）
# 生产环境请确保设置正确的 SSL 证书或启用 SSL 验证
if "LLM_SSL_VERIFY" not in os.environ:
    os.environ["LLM_SSL_VERIFY"] = "False"
if "RESTFUL_SSL_VERIFY" not in os.environ:
    os.environ["RESTFUL_SSL_VERIFY"] = "False"
# ========== SSL 验证配置结束 ==========

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# 加载 .env 文件
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)

from app.api.v1 import router as api_v1_router
from app.config.settings import get_settings


# 配置日志
logger.remove()  # 移除默认处理器
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG" if get_settings().debug else "INFO",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    settings = get_settings()
    logger.info("=" * 60)
    logger.info(f"{settings.app_name} v{settings.app_version} 正在启动...")
    logger.info("=" * 60)
    logger.info(f"调试模式: {settings.debug}")
    logger.info(f"模型提供商: {settings.model.provider}")
    logger.info(f"模型名称: {settings.model.model_name}")
    logger.info(f"最大迭代次数: {settings.agent.max_iterations}")
    logger.info("=" * 60)
    
    yield
    
    logger.info("应用正在关闭...")


# 创建 FastAPI 应用
settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
Backend V3 - 基于 openJiuwen 的多 Agent 系统

支持三种智能体生成模式：
- **ReAct Agent**: 通过思考-行动-观察循环完成任务
- **Workflow**: 预定义的多步骤任务流程
- **Multi-Agent**: 多个 Agent 协作完成任务

## API 接口

### 构建智能体
- `POST /api/v1/agent/build` - 流式构建（SSE）

### 执行工作流
- `POST /api/v1/agent/execute` - 执行工作流

### 其他
- `GET /api/v1/health` - 健康检查
- `GET /api/v1/agent/modes` - 列出支持的模式
    """,
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/")
async def root():
    """根路径"""
    settings = get_settings()
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "api": "/api/v1",
    }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.debug,
    )
