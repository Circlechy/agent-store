# ReAct Agent Config 生成规则

## 概述
生成 ReActAgent 的配置文件 `config.py`，包含 LLM 模型配置。

## 关键要求

### 1. 导入必要的模块
```python
import os
import setup_path  # 必须在导入 openjiuwen 之前
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo
```

### 2. LLM 配置常量（从环境变量读取）

```python
# LLM 配置常量（从环境变量读取，如果未设置则使用默认值）
API_BASE = os.getenv("API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
API_KEY = os.getenv("API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen-turbo")
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai")

# SSL 验证设置（必须）
os.environ["LLM_SSL_VERIFY"] = "False"

# SSRF 保护设置（必须）
os.environ["SSRF_PROTECT_ENABLED"] = "False"
```

**重要**：
- 默认值应该与系统配置保持一致
- MODEL_NAME 默认使用 "qwen-turbo"
- MODEL_PROVIDER 默认使用 "openai"（兼容 OpenAI 和 Qwen 等）
- 必须设置 `os.environ["LLM_SSL_VERIFY"] = "False"`
- 必须设置 `os.environ["SSRF_PROTECT_ENABLED"] = "False"`

### 3. LLM 配置创建函数
```python
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
```

**重要**：创建 `BaseModelInfo` 时，`api_base` 字段是必需的（Pydantic 验证要求），必须使用上面定义的 `API_BASE` 值。

## 代码结构

1. 导入必要的模块（包括 `setup_path`，必须在导入 openjiuwen 之前）
2. LLM 配置常量（从环境变量读取，如果未设置则使用默认值）
3. SSL 验证设置（必须）
4. SSRF 保护设置（必须）
5. LLM 配置创建函数

## 重要约束

- 必须使用系统提供的默认值
- 如果环境变量设置了这些值，则优先使用环境变量
- 必须设置 `os.environ["LLM_SSL_VERIFY"] = "False"`
- 必须设置 `os.environ["SSRF_PROTECT_ENABLED"] = "False"`
- 不要包含 Agent 创建代码（应该在 `local_agent.py` 中）
- 不要包含执行代码（应该在 `main.py` 中）
- 代码要清晰、模块化，符合高质量代码标准
- 每个函数都要有详细的文档字符串
