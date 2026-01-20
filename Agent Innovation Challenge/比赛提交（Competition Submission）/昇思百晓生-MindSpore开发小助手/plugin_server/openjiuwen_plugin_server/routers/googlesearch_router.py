# -*- coding: UTF-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.

"""
天气查询插件路由
"""
import requests
import json
from bs4 import BeautifulSoup
from fastapi import HTTPException, Query

from . import BasePluginRouter


def search_apis(query):

    url = "https://www.searchapi.io/api/v1/search"
    params = {
        "engine": "google",
        "q": query,
        "api_key": "sAAoHV6fLGuZBBsMJ1pmNK8j"
    }

    response = requests.get(url, params=params)
    # print(response.text)
    datajs = json.loads(response.text)
    print(datajs)
    organic_results = datajs['organic_results']
    content = []
    for result in organic_results:
        try:
            web_res = requests.get(result['link'], timeout=3)
            soups = BeautifulSoup(web_res.text, 'html.parser')
            paragraphs = soups.find_all('p')
            paragraph_content = [p.get_text(strip=True) for p in paragraphs]
            content.append(paragraph_content)
        except:
            print(result['link'], flush=True)
            continue


    print("="*30, content, flush=True)    
    return content
    # return response.json()

google_search = BasePluginRouter(
    name="google",
    description="your_demo_tool_description",
)

@google_search.router.get("/run")
async def run_google_search(
    query: str = Query(..., description="query parameter description")
):
    # try:
    new_query = f'{query}对应的MindSpore API映射'
    # new_query = "在MindSpore官网搜索torch.arcsin, torch.arctan,torch.BCELoss,torch.nn.functional.mish,torch.nn.functional.mish 对应的MindSpore接口""在MindSpore官网搜索torch.arcsin, torch.arctan,torch.BCELoss,torch.nn.functional.mish,torch.nn.functional.mish 对应的MindSpore接口"
    search_result = search_apis(new_query)
    return {
        "result": str(search_result),
    }
    # except Exception as e:
    #     raise HTTPException(
    #         status_code=500,
    #         detail=f"run failed: {str(e)}"
    #     ) from e

# 注册端点信息
google_search.register_endpoint("GET", "/run", run_google_search, "run demo")