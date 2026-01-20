# -*- coding: UTF-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.

"""
天气查询插件路由
"""
import os
import io
import zipfile
import requests
from fastapi import HTTPException, Query, Request
import aiohttp
from datetime import datetime

from openjiuwen_plugin_server.routers import BasePluginRouter
from .torch2msadapter import api_warning_list

msadapter_router = BasePluginRouter(
    name="demo",
    description="your_demo_tool_description",
)
def unzip_to_memory(zip_bytes):
    """
    将ZIP文件的二进制数据解压到内存中
    :param zip_bytes: ZIP文件的二进制数据（bytes类型）
    :return: 字典 {文件名: 文件内容字节流}
    """
    in_memory_files = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zip_ref:
        for file_name in zip_ref.namelist():
            if not file_name.endswith('.py'):
                continue
            with zip_ref.open(file_name) as file:
                in_memory_files[file_name] = io.BytesIO(file.read())
    return in_memory_files

@msadapter_router.router.get("/run")
async def run_msadapter_router(
    request: Request,
    query: str = Query(..., description="query parameter description")
):
    # try:
    from openjiuwen_plugin_server.routers.torch2mindspore.torch2msadapter import handler_plugin
    print("********", query, flush=True)
    # input_url = "http://10.174.243.240:8894/demo/files/20260115104231802824/torch"

    async with aiohttp.ClientSession() as session:
        async with session.get(query) as response:
            image_data = await response.read()

    # response = requests.get(query, verify=False)
    # print("********", response, flush=True)
    doc_content = io.BytesIO(image_data)
    in_memory_files = unzip_to_memory(doc_content.getvalue())
    new_out = {}
    new_list = []
    zip_name = query.split('/')[-1]
    for name in in_memory_files.keys():
        content = in_memory_files[name].read().decode('utf-8')
        file_name = os.path.basename(name)
        dir_name = os.path.dirname(name)
        res_out = {
            "file_name": file_name,
            "file_context": content,
            "file_path": dir_name
        }
        new_out[name] = content
        new_list.append(res_out)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    base_dir = os.path.join("upload_files", timestamp)
    os.makedirs(base_dir, exist_ok=True)
    zip_file_paths = os.path.join(base_dir, zip_name)
    api_warning_list, msadapter_new_files = handler_plugin(new_out, zip_file_paths)

    host = request.url.hostname
    port = request.url.port
    scheme = request.url.scheme
    return {
        "result": str(api_warning_list),
        "file_name": f"{scheme}://{host}:{port}/demo/files/{timestamp}/{zip_name}"
    }
    # except Exception as e:
    #     raise HTTPException(
    #         status_code=500,
    #         detail=f"run failed: {str(e)}"
    #     ) from e

# 注册端点信息
msadapter_router.register_endpoint("GET", "/run", run_msadapter_router, "run msadapter demo")