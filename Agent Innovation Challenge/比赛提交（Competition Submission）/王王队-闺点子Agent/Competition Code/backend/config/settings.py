from typing import List

from jiuwen_memory_deepsearch.utils.config import deepsearch_config


class Settings:
    """后端配置管理，从现有 config.yaml 中读取 Web API 相关配置信息."""

    def __init__(self) -> None:
        web_api = deepsearch_config.get("web_api", {}) or {}
        frontend = deepsearch_config.get("frontend", {}) or {}

        self.host: str = web_api.get("host", "0.0.0.0")
        self.port: int = web_api.get("port", 8000)
        self.log_level: str = web_api.get("log_level", "INFO")
        self.enable_concurrent_limit: bool = web_api.get("enable_concurrent_limit", True)
        self.frontend_port: int = frontend.get("port", 5173)
        self.api_base_url: str = frontend.get("api_base_url", "http://localhost:8000")


settings = Settings()
