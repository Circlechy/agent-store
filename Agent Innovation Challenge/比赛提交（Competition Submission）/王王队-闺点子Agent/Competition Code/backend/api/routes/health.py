from __future__ import annotations

import logging
import tomllib
from pathlib import Path

from fastapi import APIRouter

from backend.api.models.schemas import HealthResponse

logger = logging.getLogger("jiuwen_memory_deepsearch.backend.routes.health")

router = APIRouter(prefix="/health", tags=["health"])


def _load_version() -> str:
    try:
        with Path("pyproject.toml").open("rb") as stream:
            config = tomllib.load(stream)
        return config.get("project", {}).get("version", "0.1.0")
    except FileNotFoundError:
        logger.warning("pyproject.toml 未找到，使用默认版本号")
        return "0.1.0"
    except Exception as exc:
        logger.warning("读取版本信息失败：%s", exc)
        return "0.1.0"


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """健康检查接口"""
    version = _load_version()
    return HealthResponse(version=version)
