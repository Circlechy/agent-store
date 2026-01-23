# ReAct Agent 生成规则

## 概述
生成 `local_agent.py` 文件，包含 ReActAgent 的创建逻辑。

## 关键要求

### 1. 导入必要的模块
```python
from openjiuwen.agent.react_agent import create_react_agent_config, ReActAgent
from config import create_model_config
```

**重要**：如果使用了工具，从 `tools_analysis` 导入工具函数：
```python
from tools_analysis import get_all_tools
```

### 2. 创建 `create_agent()` 函数

函数签名：
```python
def create_agent() -> ReActAgent:
```

#### 步骤 1：创建模型配置
使用从 `config.py` 导入的 `create_model_config()` 函数：
```python
model_config = create_model_config()
```

#### 步骤 2：使用 `create_react_agent_config()` 创建 Agent 配置

**重要**：`create_react_agent_config()` 只需要 5 个参数：
- `agent_id`: Agent ID（基于 workflow_name 生成，使用下划线命名，如 "emotion_counselor"）
- `agent_version`: "1.0"
- `description`: 使用 `plan.workflow_description`
- `model`: 使用 `create_model_config()` 的结果
- `prompt_template`: 根据用户需求生成合适的 system prompt（List[Dict] 格式）

**不要传递** `workflows` 和 `plugins` 参数（它们有默认值，不需要传递）。

示例：
```python
agent_config = create_react_agent_config(
    agent_id="emotion_counselor",
    agent_version="1.0",
    description="情绪咨询助手",
    model=model_config,
    prompt_template=[
        {"role": "system", "content": "你是一个专业的情绪咨询助手..."}
    ]
)
```

#### 步骤 3：创建 ReActAgent 实例
```python
agent = ReActAgent(agent_config)
```

#### 步骤 4：添加工具（如果使用工具）

**重要**：不要在这里创建工具实例，而是从 `tools_analysis.py` 导入：
```python
from tools_analysis import get_all_tools

tools = get_all_tools()
if tools:
    agent.add_tools(tools)
```

#### 步骤 5：返回 Agent 实例
```python
return agent
```

## Prompt Template 生成规则

`prompt_template` 应该根据用户需求和 Agent 描述生成合适的系统提示词：
- 格式：`List[Dict]`，例如 `[{"role": "system", "content": "..."}]`
- 内容应该清晰描述 Agent 的职责和能力
- 如果有特定任务要求，应该在提示词中说明

## 完整示例

```python
"""
ReAct Agent 实现
"""
from openjiuwen.agent.react_agent import create_react_agent_config, ReActAgent
from config import create_model_config

def create_agent() -> ReActAgent:
    """创建 ReAct Agent"""
    # 1. 创建模型配置
    model_config = create_model_config()
    
    # 2. 创建 Agent 配置
    agent_config = create_react_agent_config(
        agent_id="emotion_counselor",
        agent_version="1.0",
        description="情绪咨询助手，帮助用户处理情绪问题",
        model=model_config,
        prompt_template=[
            {"role": "system", "content": "你是一个专业的情绪咨询助手，能够倾听和理解用户的情绪，并提供专业的建议和支持。"}
        ]
    )
    
    # 3. 创建 Agent 实例
    agent = ReActAgent(agent_config)
    
    # 4. 添加工具（如果使用工具）
    # from tools_analysis import get_all_tools
    # tools = get_all_tools()
    # if tools:
    #     agent.add_tools(tools)
    
    return agent
```

## 重要注意事项

- **必须**从 `config.py` 导入 `create_model_config()`，不要在这里重复定义配置逻辑
- **必须**使用 `create_react_agent_config()` 创建配置，不要直接使用 `AgentConfig`
- **不要**传递 `workflows` 和 `plugins` 参数
- 工具应该从 `tools_analysis.py` 导入，不要在 `local_agent.py` 中创建工具实例
- 代码要清晰、模块化，符合高质量代码标准
