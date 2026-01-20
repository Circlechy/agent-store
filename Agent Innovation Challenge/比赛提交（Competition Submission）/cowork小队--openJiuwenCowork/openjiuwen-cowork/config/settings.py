"""配置管理模块"""

import os
from typing import Optional
from dotenv import load_dotenv

try:
    from pydantic_settings import BaseSettings
    from pydantic import Field
except ImportError:
    # 兼容旧版本的 pydantic
    from pydantic import BaseSettings, Field


# 加载环境变量
load_dotenv()


class Settings(BaseSettings):
    """应用配置类"""
    
    # LLM 提供商选择
    llm_provider: str = Field(
        default="openai",
        env="LLM_PROVIDER",
        description="LLM 提供商: 'openai', 'dashscope' 或 'anthropic'"
    )
    
    # openjiuwen 配置
    api_base: Optional[str] = Field(
        default=None,
        env="API_BASE",
        description="大模型服务地址（openjiuwen 使用）"
    )
    
    model_provider: Optional[str] = Field(
        default=None,
        env="MODEL_PROVIDER",
        description="模型提供商标识（openjiuwen 使用）"
    )
    
    # OpenAI 配置
    openai_api_key: Optional[str] = Field(
        default=None,
        env="OPENAI_API_KEY",
        description="OpenAI API 密钥"
    )
    
    # 阿里云百炼 (DashScope) 配置
    dashscope_api_key: Optional[str] = Field(
        default=None,
        env="DASHSCOPE_API_KEY",
        description="阿里云百炼 DashScope API 密钥"
    )
    
    llm_model: str = Field(
        default="gpt-4",
        env="LLM_MODEL",
        description="使用的 LLM 模型名称（OpenAI: gpt-4, gpt-3.5-turbo; DashScope: qwen-turbo, qwen-plus, qwen-max 等）"
    )
    
    llm_ssl_verify: bool = Field(
        default=True,
        env="LLM_SSL_VERIFY",
        description="是否校验证书（openjiuwen 使用）"
    )
    
    # 其他 LLM 提供商配置（可选）
    anthropic_api_key: Optional[str] = Field(
        default=None,
        env="ANTHROPIC_API_KEY",
        description="Anthropic API 密钥"
    )
    
    local_model_url: Optional[str] = Field(
        default=None,
        env="LOCAL_MODEL_URL",
        description="本地模型 API URL"
    )
    
    # Agent 配置
    max_iterations: int = Field(
        default=15,
        env="MAX_ITERATIONS",
        description="Agent 最大迭代次数"
    )
    
    verbose: bool = Field(
        default=True,
        env="VERBOSE",
        description="是否显示详细日志"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例。
    
    Returns:
        Settings 实例
    """
    return settings


def validate_config() -> tuple[bool, str]:
    """验证配置是否有效。
    
    Returns:
        (是否有效, 错误消息)
    """
    provider = settings.llm_provider.lower()
    
    # 为 openjiuwen 设置默认值
    # 根据 test.py 的成功配置，DashScope 使用 compatible-mode 端点
    if not settings.api_base:
        if provider == "openai":
            settings.api_base = "https://api.openai.com/v1"
        elif provider == "dashscope":
            # 使用 compatible-mode 端点（与 test.py 一致）
            settings.api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    if not settings.model_provider:
        # 根据 test.py，使用 "OpenAI"（首字母大写）
        if provider == "dashscope":
            settings.model_provider = "OpenAI"
        else:
            settings.model_provider = provider.capitalize()
    
    if provider == "openai":
        if not settings.openai_api_key:
            return False, "错误: 使用 OpenAI 提供商时，必须配置 OPENAI_API_KEY"
        if settings.openai_api_key == "your_openai_api_key_here":
            return False, "错误: 请设置有效的 OPENAI_API_KEY"
    elif provider == "dashscope":
        if not settings.dashscope_api_key:
            return False, "错误: 使用 DashScope 提供商时，必须配置 DASHSCOPE_API_KEY"
        if settings.dashscope_api_key == "your_dashscope_api_key_here":
            return False, "错误: 请设置有效的 DASHSCOPE_API_KEY"
    elif provider == "anthropic":
        if not settings.anthropic_api_key:
            return False, "错误: 使用 Anthropic 提供商时，必须配置 ANTHROPIC_API_KEY"
    elif provider == "local":
        if not settings.local_model_url:
            return False, "错误: 使用本地模型时，必须配置 LOCAL_MODEL_URL"
    else:
        return False, f"错误: 不支持的 LLM 提供商 '{provider}'，支持: 'openai', 'dashscope', 'anthropic', 'local'"
    
    return True, "配置验证通过"
