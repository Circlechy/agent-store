"""
智慧相册后端系统 - FastAPI主应用
基于语义检索的智能图片管理系统
"""

import logging
import torch
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings, ensure_directories
from .services import (
    get_embedding_service,
    get_vector_db_service,
    get_storage_service,
    get_search_service,
)
from .routers import (
    embedding_router,
    vector_db_router,
    search_router,
    storage_router,
    agent_router,
)
from .models import SystemStatus

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    在应用启动时初始化所有服务，关闭时清理资源
    """
    settings = get_settings()
    logger.info("="*50)
    logger.info("智慧相册后端系统启动中...")
    logger.info("="*50)

    # 确保必要目录存在
    ensure_directories()

    # 初始化存储服务
    logger.info("初始化存储服务...")
    storage_service = get_storage_service()
    storage_service.initialize(
        storage_path=settings.STORAGE_PATH,
        allowed_extensions=settings.ALLOWED_EXTENSIONS,
        max_file_size=settings.MAX_FILE_SIZE
    )

    # 初始化向量数据库服务
    logger.info("初始化向量数据库服务...")
    vector_db_service = get_vector_db_service()
    vector_db_service.initialize(
        mode=settings.QDRANT_MODE,
        path=settings.QDRANT_PATH,
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_PORT,
        api_key=settings.QDRANT_API_KEY,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        vector_dimension=settings.VECTOR_DIMENSION
    )

    # 初始化Embedding服务（可选，如果模型路径有效）
    logger.info("初始化Embedding服务...")
    embedding_service = get_embedding_service()
    try:
        # 构建设备字符串，只有在CUDA可用时才应用CUDA设备号
        device = None
        if torch.cuda.is_available():
            device = f"cuda:{settings.CUDA_DEVICE}"

        embedding_service.initialize(
            model_path=settings.MODEL_PATH,
            max_length=settings.MAX_LENGTH,
            min_pixels=settings.MIN_PIXELS,
            max_pixels=settings.MAX_PIXELS,
            default_instruction=settings.DEFAULT_INSTRUCTION,
            device=device
        )
        logger.info(f"Embedding模型加载成功 (Device: {device or 'Auto'})")
    except Exception as e:
        logger.warning(f"Embedding模型加载失败: {e}")
        logger.warning("系统将在没有Embedding服务的情况下运行")

    # 初始化搜索服务
    logger.info("初始化搜索服务...")
    search_service = get_search_service()
    search_service.initialize()

    logger.info("="*50)
    logger.info("所有服务初始化完成!")
    logger.info(f"API文档地址: http://localhost:8000/docs")
    logger.info("="*50)

    yield

    # 清理资源
    logger.info("智慧相册后端系统关闭中...")


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="""
# 智慧相册后端API

基于语义检索的智能图片管理系统，支持：

## 核心功能

- **多模态Embedding生成**: 支持文本、图片、图文混合输入
- **语义化图片检索**: 通过自然语言描述搜索图片
- **以图搜图**: 查找相似图片
- **向量数据库管理**: 完整的CRUD操作
- **图片存储管理**: 上传、下载、删除图片

## 技术特点

- 基于Qwen3-VL多模态模型生成Embedding
- 使用Qdrant向量数据库存储和检索
- 支持本地和Docker部署模式切换
- 预留AI Agent框架集成接口

## API模块

- `/api/v1/embedding` - Embedding生成接口
- `/api/v1/vectors` - 向量数据库操作接口  
- `/api/v1/search` - 智能搜索接口
- `/api/v1/storage` - 图片存储接口
- `/api/v1/agent` - AI Agent集成接口
        """,
        openapi_tags=[
            {"name": "Embedding", "description": "多模态Embedding生成"},
            {"name": "Vector Database", "description": "向量数据库CRUD操作"},
            {"name": "Search", "description": "智能图像检索"},
            {"name": "Storage", "description": "图片存储管理"},
            {"name": "Agent Integration", "description": "AI Agent框架集成（预留）"},
            {"name": "System", "description": "系统状态和健康检查"},
        ],
        lifespan=lifespan
    )

    # 配置CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应限制为具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    api_prefix = settings.API_PREFIX
    app.include_router(embedding_router, prefix=api_prefix)
    app.include_router(vector_db_router, prefix=api_prefix)
    app.include_router(search_router, prefix=api_prefix)
    app.include_router(storage_router, prefix=api_prefix)
    app.include_router(agent_router, prefix=api_prefix)

    # 全局异常处理
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"未处理的异常: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(exc),
                "detail": "服务器内部错误"
            }
        )

    # 根路由
    @app.get("/", tags=["System"])
    async def root():
        """API根路由，返回基本信息"""
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "redoc": "/redoc"
        }

    # 健康检查
    @app.get("/health", tags=["System"])
    async def health_check():
        """健康检查接口"""
        return {"status": "healthy"}

    # 系统状态
    @app.get("/status", response_model=SystemStatus, tags=["System"])
    async def system_status():
        """获取系统状态"""
        embedding_svc = get_embedding_service()
        vector_db_svc = get_vector_db_service()
        storage_svc = get_storage_service()

        total_images = 0
        total_vectors = 0

        if storage_svc.is_initialized:
            stats = storage_svc.get_storage_stats()
            total_images = stats.get("total_images", 0)

        if vector_db_svc.is_initialized:
            total_vectors = vector_db_svc.count()

        return SystemStatus(
            status="running",
            version=settings.APP_VERSION,
            model_loaded=embedding_svc.is_initialized,
            vector_db_connected=vector_db_svc.is_initialized,
            storage_available=storage_svc.is_initialized,
            total_images=total_images,
            total_vectors=total_vectors
        )

    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
