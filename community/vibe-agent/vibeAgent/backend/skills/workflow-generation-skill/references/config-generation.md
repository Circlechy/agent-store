# Config Generation Reference

## 任务
生成工作流的配置文件config.py的代码

## config.py包含内容

1. 环境变量配置
2. 模型Client创建函数：定义 create_llm_client() 函数，用以创建模型Client实例
3. LLM配置创建函数：定义 create_model_config() 函数，用以创建 ModelConfig 实例
4. 工作流创建函数及相关常量定义：定义 create_workflow_config() 函数，用以创建 WorkflowConfig 实例

## 完整示例代码

```python
import os

# 1. 环境变量配置
API_BASE = os.getenv("API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
API_KEY = os.getenv("API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen3-max")
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai")

# SSL 验证设置和 SSRF保护设置（必须）
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
        temperature=0.1,
        top_p=0.9
    )

# 3. LLM 配置创建函数
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo

def create_model_config() -> ModelConfig:
    """创建模型配置"""
    model_info = BaseModelInfo(
        api_key=API_KEY,
        api_base=API_BASE,
        model=MODEL_NAME,
        temperature=0.1,
        top_p=0.9,
        timeout=120
    )
    
    return ModelConfig(
        model_provider=MODEL_PROVIDER,
        model_info=model_info
    )

# 4. 工作流配置示例
from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata

# 工作流配置常量
WORKFLOW_ID = "music_recommendation"
WORKFLOW_VERSION = "0.1.0"
WORKFLOW_NAME = "音乐推荐工作流"
WORKFLOW_DESCRIPTION = """根据用户偏好推荐音乐"""  # 为避免语法错误，使用三重引号

# Agent 配置常量
AGENT_ID = WORKFLOW_ID
AGENT_VERSION = "0.1.0"
AGENT_DESCRIPTION = WORKFLOW_DESCRIPTION

def create_workflow_config() -> WorkflowConfig:
    """创建工作流配置"""
    return WorkflowConfig(
        metadata=WorkflowMetadata(
            id=WORKFLOW_ID,
            name=WORKFLOW_NAME,
            version=WORKFLOW_VERSION,
            description=WORKFLOW_DESCRIPTION
        )
    )
```

## 代码生成要求
1. 严格参考示例代码，保留示例代码中的所有内容，不要遗漏任何内容
2. 调整import语句的顺序，将import语句放在代码的开始位置，但不要删除或额外添加任何import语句
3. 需要根据工作流的相关信息，调整代码中的WORKFLOW_ID、WORKFLOW_NAME、WORKFLOW_VERSION、WORKFLOW_DESCRIPTION常量
4. 需要根据工作流的相关信息，调整代码中的AGENT_ID、AGENT_VERSION、AGENT_DESCRIPTION常量
5. 不要更改create_llm_client()、create_model_config()、create_workflow_config()函数的结构，不要删除或添加任何内容，按照示例代码中的生成即可

## 输出格式
请直接输出Python代码，不要包含markdown代码块标记。
