# -*- coding: UTF-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.

"""
天气查询插件路由
"""

from fastapi import HTTPException, Query, Request, UploadFile, File
from fastapi.responses import FileResponse
import os
import requests
from . import BasePluginRouter

demo_router = BasePluginRouter(
    name="demo",
    description="your_demo_tool_description",
)

@demo_router.router.get("/run")
async def run_demo(
    query: str = Query(..., description="query parameter description")
):
    try:
        return {
            "result": "success",
            "query": query,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"run failed: {str(e)}"
        ) from e

@demo_router.router.get("/torch2msa")
async def run_torch2msa(
    request: Request,
    torch_file_url: str = Query(..., description="torch 文件压缩包地址"),
):
    try:
        from datetime import datetime
        from openjiuwen_plugin_server.torch2msadapter.torch2msadapter import convert
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        base_dir = os.path.join("upload_files", timestamp)
        os.makedirs(base_dir, exist_ok=True)
        torch_file_name = torch_file_url.split("/")[-1]
        torch_file = os.path.join(base_dir, torch_file_name)
        response = requests.get(torch_file_url, stream=True)
        with open(torch_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        result_file = convert(torch_file)
        msa_file_name = os.path.basename(result_file)
        host = request.url.hostname
        prot = request.url.port
        scheme = request.url.scheme
        return {
            "torch_file_url": trorch_file_url,
            "result_file_url": f"{scheme}://{host}:{port}/demo/files/{timestamp}/{msa_file_name}"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"run failed: {str(e)}"
        ) from e

@demo_router.router.post("/upload")
async def run_upload(
    request: Request,
    file: UploadFile = File(...)
):
    if True:       
    # try:
        file_info = {

            "filename": file.filename,
            "content_type": file.content_type,
            "size": 0
        }
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        base_dir = os.path.join("upload_files", timestamp)
        os.makedirs(base_dir, exist_ok=True)
        torch_file = os.path.join(base_dir, file.filename)
        with open(torch_file, "wb") as f:
            f.write(file.file.read())
        file_info["saved_path"] = str(torch_file)
        
        host = request.url.hostname
        port = request.url.port
        scheme = request.url.scheme
        return {
            "message": "文件上传成功",
            "torch_file_url": f"{scheme}://{host}:{port}/demo/files/{timestamp}/{file.filename}"
        }

    # except Exception as e:
    #     raise HTTPException(
    #         status_code=500,
    #         detail=f"run failed: {str(e)}"
    #     ) from e

@demo_router.router.get("/files/{timestamp}/{filename}")
async def run_get_file(
    timestamp: str,
    filename: str
):
    try:
        torch_file = os.path.join("upload_files", timestamp, filename)
        
        # Check if file exists
        if not os.path.exists(torch_file):
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )
        
        # Return the file content using FileResponse
        return FileResponse(
            path=torch_file,
            media_type='application/zip',
            filename=os.path.basename(torch_file)
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"run failed: {str(e)}"
        ) from e

@demo_router.router.post("/image/error")
async def run_get_image_ocr_file(
    request: Request,
):
    pass


# 注册端点信息
demo_router.register_endpoint("GET", "/run", run_demo, "run demo")
demo_router.register_endpoint("POST", "/upload", run_upload, "run demo")
demo_router.register_endpoint("GET", "/files/{timestamp}/{filename}", run_get_file, "run demo")
demo_router.register_endpoint("GET", "/torch2msa", run_torch2msa, "run demo")