---
name: react-agent-skill
description: 基于 openJiuwen 框架生成 ReAct Agent 代码。使用场景：需要动态决策、工具调用、推理循环的场景。生成包含 config.py、local_agent.py、main.py 等文件。
---

# ReAct Agent 生成技能

## 概述

ReAct Agent 是一种基于 "思考-行动-观察" 循环的智能体模式。Agent 通过不断思考、执行动作、观察结果来解决问题。

## 核心特点

- **动态决策**：根据观察结果实时调整行动策略
- **工具调用**：可以调用外部工具完成任务
- **推理链条**：保留完整的思考和推理过程

## 必需文件

1. **config.py** - 模型配置
2. **local_agent.py** - Agent 实现
3. **main.py** - 入口文件

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

### 2. local_agent.py

使用 openJiuwen 的 ReActAgent：

```python
from openjiuwen.agent.react_agent import create_react_agent_config, ReActAgent
from openjiuwen.core.utils.tool.base import Tool
from config import get_model_config

def create_agent():
    agent_config = create_react_agent_config(
        agent_id="react_agent",
        agent_version="1.0.0",
        description="Agent 描述",
        model=get_model_config(),
        prompt_template=[
            {"role": "system", "content": "系统提示词"}
        ]
    )
    
    agent = ReActAgent(agent_config)
    # 添加工具
    # agent.add_tools([tool1, tool2])
    
    return agent
```

### 3. main.py

调用 ReActAgent：

```python
import asyncio
from local_agent import create_agent

async def main():
    agent = create_agent()
    result = await agent.invoke({"query": "用户查询"})
    print(result.get("output", ""))

if __name__ == "__main__":
    asyncio.run(main())
```

## 工具定义

工具必须继承 openJiuwen 的 Tool：

```python
from openjiuwen.core.utils.tool.base import Tool
from openjiuwen.core.utils.tool.schema import ToolInfo

class MyTool(Tool):
    def get_tool_info(self) -> ToolInfo:
        # 返回工具信息
        pass
    
    async def ainvoke(self, inputs: Dict, **kwargs) -> Dict:
        # 工具实现
        pass
```

## 关键约束

1. **必须使用 openJiuwen 的 ReActAgent 类**，不要自定义实现
2. **使用 create_react_agent_config 创建配置**
3. **工具必须继承 Tool 基类**
4. **使用 agent.add_tools() 注册工具**

## 参考文档

详见 `references/` 目录下的文档。
