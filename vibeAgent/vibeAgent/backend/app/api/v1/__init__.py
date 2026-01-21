"""API v1 模块"""

from fastapi import APIRouter
from app.api.v1.endpoints import router as agent_router
from app.api.v1.mermaid import router as mermaid_router

# 合并所有路由
router = APIRouter()
router.include_router(agent_router)
router.include_router(mermaid_router, prefix="/mermaid", tags=["mermaid"])

__all__ = ["router"]
