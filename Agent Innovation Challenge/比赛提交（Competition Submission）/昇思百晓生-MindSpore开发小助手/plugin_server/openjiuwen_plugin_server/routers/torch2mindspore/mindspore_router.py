# -*- coding: UTF-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.

"""
天气查询插件路由
"""
import base64
import io
import os
import requests
import zipfile
from fastapi import HTTPException, Query, Request
import aiohttp
from datetime import datetime

from openjiuwen_plugin_server.routers import BasePluginRouter

mindspore_router = BasePluginRouter(
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

def make_zip_based64(files:dict):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            if isinstance(content, str):
                content = content.encode('utf-8')
            z.writestr(name, content)
    zip_bytes = buf.getvalue()
    return base64.b64encode(zip_bytes).decode('ascii')

@mindspore_router.router.get("/run")
async def run_msconvert(
    request: Request,
    query: str = Query(..., description="query parameter description")
):
    # try:
    from openjiuwen_plugin_server.routers.torch2mindspore.torch2ms import handler_plugin
    print("********", query, flush=True)
    # input_url = "http://10.174.243.240:8894/demo/files/20260115104231802824/torch"
    # response = requests.get(query, verify=False)
    async with aiohttp.ClientSession() as session:
        async with session.get(query) as response:
            image_data = await response.read()

    # print("********", response, flush=True)
    # doc_content = io.BytesIO(response.content)
    in_memory_files = unzip_to_memory(image_data)
    new_out = {}
    new_list = []
    torch_zip_name = query.split('/')[-1]
    ms_zip_name = torch_zip_name[:-4] + "_mindspore.zip"
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
    converted_code, not_converted_api = handler_plugin(new_out)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    base_dir = os.path.join("upload_files", timestamp)
    os.makedirs(base_dir, exist_ok=True)
    zip_file_paths = os.path.join(base_dir, ms_zip_name)

    # zip_file_paths = f'D:\\work\\agent_file\\openjiuwen\\agent-studio\\plugin_server\\openjiuwen_plugin_server\\output\\{zip_name}.zip'
    target_code_zipped = make_zip_based64(converted_code)
    zipped_bytes = base64.b64decode(target_code_zipped)
    with open(zip_file_paths, "wb") as zip_file:
        zip_file.write(zipped_bytes)
    
    host = request.url.hostname
    port = request.url.port
    scheme = request.url.scheme
    
    ms_file_paths = f"{scheme}://{host}:{port}/demo/files/{timestamp}/{ms_zip_name}"
    return {
        "result": ms_file_paths,
        "zip_name": ms_zip_name,
        "not_converted_api": str(not_converted_api),
    }
    # except Exception as e:
    #     raise HTTPException(
    #         status_code=500,
    #         detail=f"run failed: {str(e)}"
    #     ) from e

# 注册端点信息
mindspore_router.register_endpoint("GET", "/run", run_msconvert, "run mindspore converter")