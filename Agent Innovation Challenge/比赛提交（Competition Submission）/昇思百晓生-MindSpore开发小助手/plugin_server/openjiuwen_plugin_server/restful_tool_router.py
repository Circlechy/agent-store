#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.

"""
Plugin Server - 主应用文件
模块化插件路由架构
"""
import datetime
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# 导入模块化路由
from openjiuwen_plugin_server.routers.demo_router import demo_router
from openjiuwen_plugin_server.routers.system_router import system_router
from openjiuwen_plugin_server.routers.search_router import search_router
from openjiuwen_plugin_server.routers.torch2mindspore.mindspore_router import mindspore_router
from openjiuwen_plugin_server.routers.torch2mindspore.msadapter_router import msadapter_router
from openjiuwen_plugin_server.routers.googlesearch_router import google_search

# 创建FastAPI应用
app = FastAPI(
    title="Plugin Server",
    description="plugin server",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    全局异常处理器
    """
    error_id = f"error_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}"

    # 记录错误信息（实际项目中应该使用日志系统）
    error_info = {
        "error_id": error_id,
        "timestamp": datetime.datetime.now().isoformat(),
        "path": str(request.url),
        "method": request.method,
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "traceback": traceback.format_exc()
    }

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error_id": error_id,
            "error": "Internal Server Error",
            "message": "internal server error",
            "timestamp": datetime.datetime.now().isoformat()
        }
    )

# 根路径
@app.get("/")
async def root():
    """API根路径，返回服务基本信息"""
    return {
        "service": "Plugin Server",
        "version": "1.0.0",
        "description": "plugin server",
        "protocols": ["RESTful API"],
        "plugins": [
            {
                "name": "system",
                "description": "系统管理和监控",
                "base_path": "/system"
            },
            {
                "name": "demo",
                "description": "demo plugin",
                "base_path": "/demo"
            },
            {
                "name": "search",
                "description": "search plugin",
                "base_path": "/search"
            },
            {
                "name": "mindspore",
                "description": "mindspore plugin",
                "base_path": "/mindspore"
            },
            {
                "name": "msadapter",
                "description": "demo plugin",
                "base_path": "/msadapter"
            },
            {
                "name": "google",
                "description": "google search plugin",
                "base_path": "/google"
            },
        ],
        "total_plugins": 5,
        "timestamp": datetime.datetime.now().isoformat(),
        "status": "operational"
    }

# plugin router
app.include_router(system_router.router, prefix="/system")
app.include_router(demo_router.router, prefix="/demo")
app.include_router(search_router.router, prefix="/search")
app.include_router(mindspore_router.router, prefix="/mindspore")
app.include_router(msadapter_router.router, prefix="/msadapter")
app.include_router(google_search.router, prefix="/google")