# Multi-Agent Worker Agents 生成规则

## 概述
生成 `worker_agents.py` 文件，包含 Worker Agents 的创建逻辑。

## 关键要求

### 1. 导入必要的模块

**必须**从 `config.py` 导入配置函数：
```python
from config import create_model_config
```

**禁止**：
- ❌ 不要包含任何 LLM 配置常量（API_BASE, API_KEY, MODEL_NAME, MODEL_PROVIDER等）
- ❌ 不要定义 `_create_model_config()` 或 `create_model_config()` 函数

**必须**：统一使用 ReActAgent（不再支持 WorkflowAgent）
```python
from openjiuwen.agent.react_agent import create_react_agent_config, ReActAgent
```

### 2. 创建 `create_worker_agents()` 函数

函数签名：
```python
def create_worker_agents() -> dict[str, ReActAgent]:
```

#### 步骤 1：获取模型配置
```python
model_config = create_model_config()  # 从 config.py 导入
```

#### 步骤 2：为每个 Worker 生成 ReActAgent

根据 `workers_info` 为每个 Worker 生成 ReActAgent：

```python
# 创建各个 ReActAgent
agent1_config = create_react_agent_config(
    agent_id="worker_1",
    agent_version="1.0",
    description="Worker Agent 1 的描述",
    model=model_config,
    prompt_template=[{"role": "system", "content": "你是一个..."}]
)
agent1 = ReActAgent(agent1_config)
```

#### 步骤 3：返回字典
```python
return {
    "worker_1": agent1,
    "worker_2": agent2,
    ...
}
```

**重要**：为每个 Worker Agent 生成合适的 `prompt_template`：
- 根据 worker 的 `description` 和 `responsibilities` 生成系统提示词
- `prompt_template` 格式：`List[Dict]`，例如 `[{"role": "system", "content": "你是一个..."}]`

## 完整示例

```python
"""
Worker Agents 实现
"""
from openjiuwen.agent.react_agent import create_react_agent_config, ReActAgent
from config import create_model_config

def create_worker_agents() -> dict[str, ReActAgent]:
    """
    创建所有 Worker Agents
    
    Returns:
        Worker Agents 字典，key 为 agent_id，value 为 ReActAgent 实例
    """
    # 获取模型配置（从 config.py 导入）
    model_config = create_model_config()
    
    # 创建各个 Worker ReActAgent
    # Worker 1
    agent1_config = create_react_agent_config(
        agent_id="worker_001",
        agent_version="1.0",
        description="Worker Agent 1 的描述",
        model=model_config,
        prompt_template=[
            {"role": "system", "content": "你是一个 Worker Agent 1，负责执行具体任务1。"}
        ]
    )
    agent1 = ReActAgent(agent1_config)
    
    # Worker 2
    agent2_config = create_react_agent_config(
        agent_id="worker_002",
        agent_version="1.0",
        description="Worker Agent 2 的描述",
        model=model_config,
        prompt_template=[
            {"role": "system", "content": "你是一个 Worker Agent 2，负责执行具体任务2。"}
        ]
    )
    agent2 = ReActAgent(agent2_config)
    
    return {
        "worker_001": agent1,
        "worker_002": agent2,
    }
```

## 重要注意事项

- **必须**从 `config.py` 导入 `create_model_config()`，不要在这里重复定义配置逻辑
- **禁止**包含任何 LLM 配置常量
- **必须**统一使用 `ReActAgent`（不再支持 `WorkflowAgent`）
- **重要**：为每个 Worker Agent 生成合适的 `prompt_template`，根据 worker 的 `description` 和 `responsibilities` 生成系统提示词
- 代码要清晰、模块化，符合高质量代码标准
