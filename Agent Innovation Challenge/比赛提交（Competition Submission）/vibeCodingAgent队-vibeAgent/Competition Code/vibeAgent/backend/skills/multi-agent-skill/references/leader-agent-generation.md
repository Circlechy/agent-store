# Multi-Agent Leader Agent 生成规则

## 概述
生成 `leader_agent.py` 文件，包含 Leader Agent 的创建逻辑。

## 关键要求

### 1. 导入必要的模块

**必须**从 `config.py` 导入配置函数：
```python
from config import create_model_config
```

**禁止**：
- ❌ 不要包含任何 LLM 配置常量（API_BASE, API_KEY等）
- ❌ 不要定义 `create_model_config()` 函数

其他导入：
```python
from openjiuwen.agent.config.base import AgentConfig
from openjiuwen.core.agent.agent import ControllerAgent
from openjiuwen.agent_group.hierarchical_group.agents.main_controller import HierarchicalMainController
```

### 2. 创建 `create_leader_agent()` 函数

函数签名：
```python
def create_leader_agent(agent_id: str, agent_version: str, description: str) -> tuple[str, ControllerAgent]:
```

#### 步骤 1：获取模型配置
```python
model_config = create_model_config()  # 从 config.py 导入
```

#### 步骤 2：创建 Agent 配置
使用 `AgentConfig` 创建配置：
```python
leader_config = AgentConfig(
    id=agent_id,
    version=agent_version,
    description=description,
    model=model_config
)
```

#### 步骤 3：创建 Main Controller
```python
main_controller = HierarchicalMainController()
```

#### 步骤 4：创建 Leader Agent
```python
leader_agent = ControllerAgent(leader_config, controller=main_controller)
```

#### 步骤 5：返回元组
```python
return agent_id, leader_agent
```

**关键**：Leader Agent 必须使用 `ControllerAgent + HierarchicalMainController`，不是 `ReActAgent`。

### 3. Leader Agent 的职责

- 识别用户意图并分发任务
- 协调 Worker Agents
- 根据 `leader_info` 生成合适的 description

## 完整示例

```python
"""
Leader Agent 实现
"""
from openjiuwen.agent.config.base import AgentConfig
from openjiuwen.core.agent.agent import ControllerAgent
from openjiuwen.agent_group.hierarchical_group.agents.main_controller import HierarchicalMainController
from config import create_model_config

def create_leader_agent(agent_id: str, agent_version: str, description: str) -> tuple[str, ControllerAgent]:
    """
    创建 Leader Agent
    
    Args:
        agent_id: Agent ID
        agent_version: Agent 版本
        description: Agent 描述
        
    Returns:
        (agent_id, leader_agent) 元组
    """
    # 获取模型配置（从 config.py 导入）
    model_config = create_model_config()
    
    # 创建 Leader Agent 配置
    leader_config = AgentConfig(
        id=agent_id,
        version=agent_version,
        description=description,
        model=model_config
    )
    
    # 创建 Main Controller
    main_controller = HierarchicalMainController()
    
    # 创建 Leader Agent
    leader_agent = ControllerAgent(leader_config, controller=main_controller)
    
    return agent_id, leader_agent
```

## 重要注意事项

- **必须**从 `config.py` 导入 `create_model_config()`，不要在这里重复定义配置逻辑
- **禁止**包含任何 LLM 配置常量
- **关键**：Leader Agent 必须使用 `ControllerAgent + HierarchicalMainController`，不是 `ReActAgent`
- 代码要清晰、模块化，符合高质量代码标准
