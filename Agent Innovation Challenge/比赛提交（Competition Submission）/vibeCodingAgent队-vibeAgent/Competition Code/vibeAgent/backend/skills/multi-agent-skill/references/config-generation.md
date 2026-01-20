# Multi-Agent Config 生成规则

## 概述
生成 Multi-Agent Group 的配置文件 `config.py`，包含 LLM 模型配置和 Group 配置。

## 关键要求

### 1. 导入必要的模块
```python
import setup_path  # 必须在导入 openjiuwen 之前
import os
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo
from openjiuwen.agent_group.hierarchical_group.config import HierarchicalGroupConfig
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

```python
def create_model_config() -> ModelConfig:
    """创建模型配置（供 leader_agent.py 和 worker_agents.py 导入使用）"""
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

**重要**：这个函数将被 `leader_agent.py` 和 `worker_agents.py` 导入使用。

### 3. Group 配置
定义常量：
- `GROUP_ID`: Group ID（基于 Group 名称生成）
- `LEADER_AGENT_ID`: Leader Agent ID（如 "leader_001"）
- `MAX_AGENTS`: 最大 Agent 数量（默认 10）

```python
def create_group_config() -> HierarchicalGroupConfig:
    """创建 Group 配置"""
    return HierarchicalGroupConfig(
        group_id=GROUP_ID,
        leader_agent_id=LEADER_AGENT_ID,
        max_agents=MAX_AGENTS
    )
```

## 代码结构

1. 导入必要的模块（包括 `setup_path`，必须在导入 openjiuwen 之前）
2. LLM 配置常量（从环境变量读取，如果未设置则使用默认值）
3. SSL 验证设置（必须）
4. SSRF 保护设置（必须）
5. LLM 配置创建函数（供其他文件导入使用）
6. Group 配置常量
7. Group 配置创建函数

## 重要约束

- **必须**包含 `import setup_path`（必须在导入 openjiuwen 之前）
- **重要**：`config.py` 是所有配置的集中管理文件，其他文件都必须从 `config.py` 导入配置函数
- 必须使用系统提供的默认值
- 如果环境变量设置了这些值，则优先使用环境变量
- 必须设置 `os.environ["LLM_SSL_VERIFY"] = "False"`
- 必须设置 `os.environ["SSRF_PROTECT_ENABLED"] = "False"`
- 代码要清晰、模块化，符合高质量代码标准
