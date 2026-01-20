from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from backend.api.middleware.cors import setup_cors
from backend.api.routes.health import router as health_router
from backend.api.routes.search import router as search_router
from backend.config.settings import settings
from jiuwen_memory_deepsearch.utils.logging import setup_global_logger

logger = logging.getLogger("jiuwen_memory_deepsearch.backend.api")

# 禁用 SSL 验证，解决某些环境下的 API 调用问题
os.environ["LLM_SSL_VERIFY"] = "false"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Jiuwen Memory Deepsearch API",
        version="0.1.0",
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json"
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        logger.info(f"Incoming request: {request.method} {request.url}")
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code}")
        return response

    setup_cors(app)
    # 挂载根目录下的 temp 文件夹作为静态资源
    os.makedirs("temp", exist_ok=True)
    app.mount("/temp", StaticFiles(directory="temp"), name="temp")
    
    # 挂载 search_image 目录，放在 /api/v1/search_images 下以便前端统一使用 getApiUrl
    os.makedirs("search_image", exist_ok=True)
    app.mount("/api/v1/search_images", StaticFiles(directory="search_image"), name="search_images")
    
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(search_router, prefix="/api/v1")
    return app


app = create_app()
setup_global_logger()


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("FastAPI backend is starting at %s:%s", settings.host, settings.port)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("FastAPI backend is shutting down")
