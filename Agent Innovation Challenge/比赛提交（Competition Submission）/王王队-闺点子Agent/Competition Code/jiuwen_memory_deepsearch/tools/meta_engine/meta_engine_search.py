import json
import logging
from typing import Any, Dict, List, Optional

import httpx
import requests
from pydantic import BaseModel, ConfigDict, SecretStr

from jiuwen_memory_deepsearch.utils.config import deepsearch_config

logger = logging.getLogger(__name__)


# ============================================================================
# MetaEngine API Wrapper
# ============================================================================


class MetaEngineSearchAPIWrapper(BaseModel):
    """Wrapper class for MetaEngine Search API"""

    search_url: SecretStr = None
    max_search_results: int = 5

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra='allow'
    )

    def raw_search_results(
            self,
            query: str,
            max_results: Optional[int] = 5,
            enable_rewrite: Optional[bool] = False,
    ) -> Dict:
        """Run query through MetaEngine Search API and return raw result."""

        url = f"{self.search_url.get_secret_value()}/search"
        params = {
            "text": query,
            "enable_rewrite": enable_rewrite
        }
        response = requests.post(url, json=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def results(
            self,
            query: str,
            max_results: Optional[int] = None,
            enable_rewrite: Optional[bool] = False,
    ) -> List[Dict]:
        """Run query through MetaEngine Search API and return cleaned result"""

        max_results = max_results or self.max_search_results
        raw_search_results = self.raw_search_results(
            query,
            max_results=max_results,
            enable_rewrite=enable_rewrite,
        )
        data = raw_search_results.get("data", [])[:max_results]
        return self.clean_results(data)

    async def raw_search_results_async(
            self,
            query: str,
            max_results: Optional[int] = 5,
            enable_rewrite: Optional[bool] = False,
    ) -> Dict:
        """Run query through MetaEngine Search API asynchronously."""

        async def fetch() -> str:
            url = f"{self.search_url.get_secret_value()}/search"
            params = {
                "text": query,
                "enable_rewrite": enable_rewrite
            }

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, json=params)
                if response.status_code not in (200, 201):
                    raise Exception(f"Error {response.status_code}: {response.reason_phrase}")
                return response.text

        results_json_str = await fetch()
        return json.loads(results_json_str)

    async def aresults(
            self,
            query: str,
            max_results: Optional[int] = None,
            enable_rewrite: Optional[bool] = False,
    ) -> List[Dict]:
        """Run query through MetaEngine Search API asynchronously and return cleaned result."""

        max_results = max_results or self.max_search_results
        results_json = await self.raw_search_results_async(
            query=query,
            max_results=max_results,
            enable_rewrite=enable_rewrite,
        )
        data = results_json.get("data", [])[:max_results]
        return self.clean_results(data)

    def clean_results(self, results: List[Dict]) -> List[Dict]:
        """Clean results from MetaEngine Search API with structured json."""

        clean_results = []
        for result in results:
            clean_result = {
                "group_id": result.get("group_id"),
                "timestamp": result.get("timestamp"),
                "location": result.get("location"),
                "app_name": result.get("app_name"),
                "page_category": result.get("page_category"),
                "primary_action": result.get("primary_action"),
                "main_entities": result.get("main_entities"),
                "title": result.get("title"),
                "keywords": result.get("keywords"),
                "caption": result.get("caption"),
                "score": result.get("score", 0.0),
            }
            clean_results.append(clean_result)
        return clean_results


# ============================================================================
# MetaEngine Search Wrapper (Registry Pattern)
# ============================================================================


class MetaEngineSearchWrapper:
    """MetaEngine搜索引擎注册管理类"""

    _registry: dict[str, MetaEngineSearchAPIWrapper] = {}

    def __new__(cls, **kwargs):
        logger.info(f"MetaEngineSearchWrapper 已注册：{list(cls._registry.keys())}")
        logger.error("MetaEngineSearchWrapper 不允许实例化，请使用类方法访问注册表")
        raise RuntimeError("MetaEngineSearchWrapper 不允许实例化，请使用类方法访问注册表")

    @classmethod
    def get_registry(cls) -> dict[str, MetaEngineSearchAPIWrapper]:
        """获取所有注册的meta_engine实例"""
        if not cls._registry:
            raise RuntimeError("MetaEngineSearchWrapper 注册表为空，请先调用 register 方法注册实例")
        return cls._registry

    @classmethod
    def get_engine(cls, engine_name: str = "default") -> MetaEngineSearchAPIWrapper:
        """根据名称获取指定的meta_engine实例"""
        if engine_name not in cls._registry:
            logger.error(f"MetaEngineSearchWrapper 注册表中无引擎 {engine_name} 对应的api_wrapper实例")
            raise RuntimeError(f"MetaEngineSearchWrapper 注册表中无引擎 {engine_name}")
        return cls._registry[engine_name]

    @classmethod
    def register(
            cls,
            engine_name: str = "default",
            search_url: str = None,
            max_search_results: int = 5,
            **kwargs
    ):
        """注册meta_engine实例"""
        if search_url is None:
            search_url = deepsearch_config.get("meta_engine.api_url")

        if not search_url:
            raise ValueError("MetaEngine search_url 未配置")

        cls._registry[engine_name] = MetaEngineSearchAPIWrapper(
            search_url=SecretStr(search_url),
            max_search_results=max_search_results,
            **kwargs
        )
        logger.info(f"MetaEngineSearchWrapper 注册成功：{engine_name}")

    @classmethod
    def is_registered(cls, engine_name: str = "default") -> bool:
        """检查引擎是否已注册"""
        return engine_name in cls._registry

    @classmethod
    def clear_registry(cls):
        """清空注册表"""
        cls._registry.clear()


# ============================================================================
# MetaEngine Search Tool Functions
# ============================================================================


async def run_meta_engine_search(query: str, engine_name: str = "default") -> Dict[str, Any]:
    """运行MetaEngine搜索"""

    # 自动注册默认引擎（如果未注册）
    if not MetaEngineSearchWrapper.is_registered(engine_name):
        MetaEngineSearchWrapper.register(engine_name)

    api_wrapper = MetaEngineSearchWrapper.get_engine(engine_name)
    try:
        result = await api_wrapper.aresults(query)
    except Exception as e:
        logger.exception(f"Error when run meta engine search {engine_name}: {e}")
        return dict(search_engine=engine_name, search_results=[repr(e)])
    return dict(search_engine=engine_name, search_results=result)


# ============================================================================
# MetaEngine Search Tool Class
# ============================================================================


class MetaEngineSearchTool:
    """MetaEngine 搜索工具封装类，提供 LLM 可调用的工具接口"""

    def __init__(self, name: str = "meta_engine_search_tool",
                 description: str = "Use MetaEngine to search user's local memory/history data. Input should be a search query string.",
                 max_search_results: int = 5,
                 engine_name: str = "default"):
        self.name = name
        self.description = description
        self.max_search_results = max_search_results
        self.engine_name = engine_name

    def get_tool_info(self) -> dict:
        """获取工具信息，供 LLM 调用（OpenAI 兼容格式）"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for MetaEngine to find relevant memory/history data."
                        }
                    },
                    "required": ["query"]
                }
            }
        }

    async def ainvoke(self, args: dict) -> List[Dict]:
        """异步调用工具"""
        query = args.get("query", "")
        if not query:
            logger.warning("MetaEngineSearchTool: Empty query provided")
            return []

        result = await run_meta_engine_search(query, self.engine_name)
        return result.get("search_results", [])


def create_meta_engine_search_tool():
    """获取MetaEngine搜索工具（使用 openjiuwen LocalFunction）"""
    from openjiuwen.core.utils.tool.function.function import LocalFunction
    from openjiuwen.core.utils.tool.param import Param

    meta_engine_search_tool = LocalFunction(
        name="meta_engine_search_tool",
        description="Use MetaEngine to search user's local memory/history data.",
        params=[
            Param(
                name="query",
                description="Search query for MetaEngine.",
                param_type="String",
                required=True
            )
        ],
        func=run_meta_engine_search
    )
    return meta_engine_search_tool
