# -*- coding: UTF-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.

"""
系统管理路由 - 健康检查、文档、测试工具等
"""
import datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from . import BasePluginRouter

# 创建系统路由器
system_router = BasePluginRouter(
    name="system",
    description="系统管理和监控相关接口"
)

@system_router.router.get("/health")
async def health_check():
    """系统健康检查"""
    return {
        "status": "healthy",
        "service": "openJiuwen Plugin Server",
        "version": "1.0.0",
        "timestamp": datetime.datetime.now().isoformat(),
        "uptime": "running",
        "checks": {
            "api_server": "ok",
            "database": "not_applicable",
            "external_services": "partial"  # 部分外部服务可能需要API密钥
        }
    }

@system_router.router.get("/info")
async def system_info():
    """系统信息"""
    return {
        "name": "openJiuwen Plugin Server",
        "version": "1.0.0",
        "description": "AI工具插件服务器",
        "architecture": "FastAPI",
        "protocols": [
            "RESTful API"
        ],
        "python_version": "3.11+",
        "author": "Huawei Technologies Co., Ltd.",
        "startup_time": datetime.datetime.now().isoformat()
    }

@system_router.router.get("/docs")
async def api_docs():
    """API文档导航"""
    return {
        "message": "API documentation available",
        "documentation": {
            "api_reference": "/docs/api/README.md",
            "usage_examples": "/docs/api/使用示例/README.md",
            "issue_analysis": "/docs/api/问题分析/README.md",
            "improvement_suggestions": "/docs/api/改进建议.md",
            "index": "/docs/api/INDEX.md"
        },
        "endpoints_summary": {
            "system": "/system/* - 系统管理",
            "demo": "/demo/* - demo",
            "torch2msa": "/torch2msa/* - torch2msa",
            "search": "/search/* - search"
        }
    }

@system_router.router.get("/test")
async def test_center():
    """API测试中心"""
    return {
        "message": "API Testing Center",
        "test_commands": [
            {
                "category": "系统测试",
                "tests": [
                    {
                        "name": "Health Check",
                        "command": "curl \"http://localhost:8185/system/health\"",
                        "description": "检查服务运行状态",
                        "expected_status": 200
                    },
                    {
                        "name": "System Info",
                        "command": "curl \"http://localhost:8185/system/info\"",
                        "description": "获取系统信息",
                        "expected_status": 200
                    }
                ]
            }
        ],
        "note": "中文参数需要进行URL编码，使用%20代替空格",
        "troubleshooting": {
            "404_error": "检查URL路径是否正确",
            "405_error": "检查HTTP方法是否正确",
            "timeout": "检查网络连接和服务状态"
        }
    }

@system_router.router.get("/endpoints")
async def list_all_endpoints():
    """获取所有可用端点列表"""
    from . import ALL_ROUTERS

    all_endpoints = []

    for router in ALL_ROUTERS:
        if hasattr(router, 'get_info'):
            info = router.get_info()
            all_endpoints.append(info)

    return {
        "total_plugins": len(all_endpoints),
        "plugins": all_endpoints,
        "total_endpoints": sum(len(plugin['endpoints']) for plugin in all_endpoints)
    }

# 注册端点信息
system_router.register_endpoint("GET", "/health", health_check, "系统健康检查")
system_router.register_endpoint("GET", "/info", system_info, "获取系统信息")
system_router.register_endpoint("GET", "/docs", api_docs, "API文档导航")
system_router.register_endpoint("GET", "/test", test_center, "API测试中心")
system_router.register_endpoint("GET", "/endpoints", list_all_endpoints, "获取所有端点")