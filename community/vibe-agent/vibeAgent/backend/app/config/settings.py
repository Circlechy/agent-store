"""
配置管理模块

集中管理所有配置项，支持环境变量覆盖
"""
import os
from typing import Optional
from pydantic import BaseModel, Field
from functools import lru_cache


class ModelSettings(BaseModel):
    """模型配置"""
    provider: str = Field(default="openai", description="模型提供商")
    api_base: str = Field(default="", description="API 基础 URL")
    api_key: str = Field(default="", description="API 密钥")
    model_name: str = Field(default="qwen3-coder-plus", description="默认模型名称")
    temperature: float = Field(default=0.3, ge=0.0, le=2.0, description="温度参数")
    top_p: float = Field(default=0.9, ge=0.0, le=1.0, description="Top P 参数")
    timeout: int = Field(default=120, ge=10, description="超时时间（秒）")


class AgentSettings(BaseModel):
    """Agent 配置"""
    max_iterations: int = Field(default=3, ge=1, le=10, description="最大迭代次数")
    test_timeout: int = Field(default=300, ge=30, description="测试超时时间（秒）")
    enable_wisdom: bool = Field(default=True, description="是否启用智慧积累")
    max_plan_retries: int = Field(default=2, ge=1, le=5, description="规划最大重试次数")
    max_fix_iterations: int = Field(default=3, ge=1, le=5, description="修复最大迭代次数")


class Settings(BaseModel):
    """全局配置"""
    # 应用配置
    app_name: str = "OpenJiuwen Agent Generator V3"
    app_version: str = "3.0.0"
    debug: bool = Field(default=False)
    
    # 模型配置
    model: ModelSettings = Field(default_factory=ModelSettings)
    
    # Agent 配置
    agent: AgentSettings = Field(default_factory=AgentSettings)
    
    # 路径配置
    experiments_dir: str = Field(default="experiments", description="实验输出目录")
    skills_dir: str = Field(default="skills", description="技能目录")
    wisdom_dir: str = Field(default=".wisdom", description="智慧目录")
    
    class Config:
        env_prefix = "VIBE_"
        env_nested_delimiter = "__"


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    # 从环境变量加载配置
    model_settings = ModelSettings(
        provider=os.getenv("MODEL_PROVIDER", "openai"),
        api_base=os.getenv("API_BASE", ""),
        api_key=os.getenv("API_KEY", ""),
        model_name=os.getenv("MODEL_NAME", "qwen3-coder-plus"),
        temperature=float(os.getenv("MODEL_TEMPERATURE", "0.3")),
        top_p=float(os.getenv("MODEL_TOP_P", "0.9")),
        timeout=int(os.getenv("MODEL_TIMEOUT", "120")),
    )
    
    agent_settings = AgentSettings(
        max_iterations=int(os.getenv("MAX_ITERATIONS", "3")),
        test_timeout=int(os.getenv("TEST_TIMEOUT", "300")),
        enable_wisdom=os.getenv("ENABLE_WISDOM", "true").lower() == "true",
        max_plan_retries=int(os.getenv("MAX_PLAN_RETRIES", "2")),
        max_fix_iterations=int(os.getenv("MAX_FIX_ITERATIONS", "3")),
    )
    
    return Settings(
        debug=os.getenv("DEBUG", "false").lower() == "true",
        model=model_settings,
        agent=agent_settings,
        experiments_dir=os.getenv("EXPERIMENTS_DIR", "experiments"),
        skills_dir=os.getenv("SKILLS_DIR", "skills"),
        wisdom_dir=os.getenv("WISDOM_DIR", ".wisdom"),
    )


# 导出配置实例
settings = get_settings()
