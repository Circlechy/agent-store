import os
import warnings
import dotenv

# 抑制 langchain_tavily 库中的字段名冲突警告
# 这是库本身的问题，不影响功能使用
warnings.filterwarnings(
    "ignore",
    message=".*Field name.*shadows an attribute in parent.*",
    category=UserWarning
)

from langchain_tavily import TavilySearch, TavilyExtract
from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.utils.tool.tool import tool

dotenv.load_dotenv(dotenv_path=".env")

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
search_tool = TavilySearch(max_results=5, topic="general")
extract_tool = TavilyExtract(extract_depth="basic", include_images=False)

@tool(name="tavily_search",
      description="使用Tavily在互联网上搜索信息",
      params=[
        Param(name="query", description="搜索关键字", type="str", required=True),
      ])
async def tavily_search(query: str):
    results = await search_tool.ainvoke({"query": query})
    return results

@tool(name="tavily_extract",
      description="使用Tavily从一系列URLs中提取关键信息",
      params=[
        Param(name="urls", description="要提取信息的URLs，输入必须是个list", type="list", required=True),
      ])
async def tavily_extract(urls: list):
    if isinstance(urls, str):
        urls = [urls]
    results = await extract_tool.ainvoke({"urls": urls})
    return results