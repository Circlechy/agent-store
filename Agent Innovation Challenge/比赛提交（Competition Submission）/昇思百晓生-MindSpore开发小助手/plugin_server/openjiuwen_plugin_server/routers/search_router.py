# -*- coding: UTF-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.

"""
天气查询插件路由
"""

from fastapi import HTTPException, Query, Request, UploadFile, File
from fastapi.responses import FileResponse
import aiohttp
import os
import requests
import base64

import os
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkocr.v1.region.ocr_region import OcrRegion
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkocr.v1 import *
from urllib.parse import unquote, unquote_plus
import json


from . import BasePluginRouter

search_router = BasePluginRouter(
    name="search",
    description="search tool description",
)

@search_router.router.get("/run")
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

@search_router.router.get("/image_ocr")
async def run_image_ocr(
    request: Request,
    image_url: str = Query(..., description="torch 文件压缩包地址"),
):
    try:
        ak = "XXXXX" # os.environ["CLOUD_SDK_AK"]
        sk = "XXXXXX" #os.environ["CLOUD_SDK_SK"]
    
        credentials = BasicCredentials(ak, sk)
    
        client = OcrClient.new_builder() \
            .with_credentials(credentials) \
            .with_region(OcrRegion.value_of("cn-north-4")) \
            .build()
        image_url = unquote(image_url)
        # 下载图片数据
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                image_data = await response.read()

        base64_encoded = base64.b64encode(image_data).decode('utf-8')
 
        request = RecognizeGeneralTextRequest()
        request.body = GeneralTextRequestBody(
            return_markdown_result=True,
            image=base64_encoded,
            # url=unquote(image_url) # "https://mindspore-website.obs.cn-north-4.myhuaweicloud.com/website-images/r2.7.1/docs/mindspore/source_zh_cn/features/images/arch_zh.png"
        )
        response = client.recognize_general_text(request)
        image_content = response.to_dict()["result"]["markdown_result"]
        return {
            "image_content": image_content,
        }

    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"run failed: {str(e)}"
        ) from e


# 注册端点信息
search_router.register_endpoint("GET", "/run", run_demo, "run demo")
search_router.register_endpoint("GET", "/image_ocr", run_image_ocr, "run image ocr")