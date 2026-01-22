# ========== config.py示例代码 ==========
# 1. 环境配置
import os

API_BASE = os.getenv("API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
API_KEY = os.getenv("API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen3-max")
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai")

# SSL 验证设置 和 SSRF保护设置（必须）
os.environ["LLM_SSL_VERIFY"] = "False"
os.environ["SSRF_PROTECT_ENABLED"] = "False"

# 2. 模型Client创建函数
from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory
from openjiuwen.core.utils.llm.base import BaseModelClient

def create_llm_client() -> BaseModelClient:
    """创建模型Client"""
    return ModelFactory().get_model(
        model_provider=MODEL_PROVIDER,
        api_key=API_KEY,
        api_base=API_BASE,
        timeout=120,
        temperature=0.7,
        top_p=0.9
    )

# 3. LLM 配置创建函数
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo

def create_model_config() -> ModelConfig:
    """创建模型配置"""
    return ModelConfig(
        model_provider=MODEL_PROVIDER,
        model_info=BaseModelInfo(
            model=MODEL_NAME,
            api_base=API_BASE,
            api_key=API_KEY,
            temperature=0.7,
            top_p=0.9,
            timeout=120,
        ),
    )

# 4. 工作流配置示例
from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata

# 工作流配置常量
WORKFLOW_ID = "test_weather_workflow"  # 工作流ID（不带版本号）
WORKFLOW_VERSION = "1.0"  # 工作流版本
WORKFLOW_NAME = "weather"
WORKFLOW_DESCRIPTION = """天气查询工作流"""  # 为避免语法错误，使用三重引号

def create_workflow_config() -> WorkflowConfig:
    """创建工作流配置"""
    return WorkflowConfig(
        metadata=WorkflowMetadata(
            id=WORKFLOW_ID,  # 使用WORKFLOW_ID
            name=WORKFLOW_NAME,
            version=WORKFLOW_VERSION,
            description=WORKFLOW_DESCRIPTION
        )
    )

# 5. Agent 配置示例
AGENT_ID = "test_weather_workflow_agent"
AGENT_VERSION = "0.1.0"
AGENT_DESCRIPTION = """天气查询工作流Agent"""  # 为避免语法错误，使用三重引号
