---
name: multi-agent-skill
description: 基于 openJiuwen 框架生成 Multi-Agent（HierarchicalGroup）代码。使用场景：需要多个 Agent 协作、分工明确、层级管理的复杂任务。生成包含 config.py、leader_agent.py、worker_agent.py、main.py 等文件。
---

# Multi-Agent 生成技能

## 概述

Multi-Agent 模式采用层级组（HierarchicalGroup）架构，由 Leader 协调多个 Worker 协作完成复杂任务。

## 核心特点

- **分工协作**：不同 Agent 负责不同职责
- **层级管理**：Leader 负责任务分配和结果整合
- **灵活扩展**：可以动态添加 Worker
- **复杂任务处理**：适合需要多种能力的任务

## 必需文件

1. **config.py** - 模型配置
2. **leader_agent.py** - Leader Agent 实现
3. **worker_agent.py** - Worker Agent 实现
4. **main.py** - 入口文件

## 生成要求

### 1. config.py

必须使用 openJiuwen 的 ModelConfig：

```python
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo

def get_model_config() -> ModelConfig:
    return ModelConfig(
        model_provider="openai",
        model_info=BaseModelInfo(
            api_key=os.getenv("API_KEY", ""),
            api_base=os.getenv("API_BASE", ""),
            model_name=os.getenv("MODEL_NAME", "qwen3-coder-plus"),
            temperature=0.7,
            top_p=0.9,
            timeout=120
        )
    )
```

### 2. leader_agent.py

Leader 可以使用 ReActAgent 或自定义 Agent：

```python
from openjiuwen.agent.react_agent import create_react_agent_config, ReActAgent
from config import get_model_config

def create_leader_agent():
    agent_config = create_react_agent_config(
        agent_id="leader_agent",
        agent_version="1.0.0",
        description="Leader Agent，负责任务规划和分配",
        model=get_model_config(),
        prompt_template=[
            {"role": "system", "content": "你是 Leader Agent，负责协调 Worker Agent 完成任务。"}
        ]
    )
    
    agent = ReActAgent(agent_config)
    # TODO: 添加工具和 Worker 调用能力
    
    return agent
```

### 3. worker_agent.py

Worker 可以使用 ReActAgent：

```python
from openjiuwen.agent.react_agent import create_react_agent_config, ReActAgent
from config import get_model_config

def create_worker_agent(worker_id: str, description: str):
    agent_config = create_react_agent_config(
        agent_id=worker_id,
        agent_version="1.0.0",
        description=description,
        model=get_model_config(),
        prompt_template=[
            {"role": "system", "content": f"你是 {worker_id}，负责执行具体任务。"}
        ]
    )
    
    agent = ReActAgent(agent_config)
    # TODO: 添加工具
    
    return agent
```

### 4. main.py

使用 openJiuwen 的 HierarchicalGroup（如果可用）：

```python
import asyncio
from leader_agent import create_leader_agent
from worker_agent import create_worker_agent

async def main():
    # 创建 Leader
    leader = create_leader_agent()
    
    # 创建 Workers
    workers = [
        create_worker_agent("worker1", "Worker 1 描述"),
        create_worker_agent("worker2", "Worker 2 描述"),
    ]
    
    # 使用 HierarchicalGroup（如果 openJiuwen 提供）
    # from openjiuwen.agent.hierarchical_group import HierarchicalGroup
    # group = HierarchicalGroup(leader=leader, workers=workers)
    # result = await group.invoke({"query": "用户查询"})
    
    # 或者手动协调
    # TODO: 实现 Leader 和 Workers 的协调逻辑
    
    print("Multi-Agent 执行完成")

if __name__ == "__main__":
    asyncio.run(main())
```

## 关键约束

1. **Leader 和 Worker 都使用 ReActAgent**（或自定义 BaseAgent）
2. **使用 openJiuwen 的 HierarchicalGroup**（如果框架提供）
3. **确保 Agent 之间的通信机制正确**
4. **Leader 负责任务分解和结果整合**

## 参考文档

详见 `references/` 目录下的文档。
