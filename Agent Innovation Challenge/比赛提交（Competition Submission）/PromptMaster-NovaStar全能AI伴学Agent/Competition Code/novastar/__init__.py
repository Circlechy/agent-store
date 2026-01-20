"""启明星（NovaStar）全能 AI 伴学 Agent.

基于openjiuwen框架构建的儿童AI伴学系统。

主要模块:
- core: 核心组件（LLM封装、节点基类、工作流构建器）
- nodes: Agent节点（Commander、Mentor、Artist、Companion）
- workflow: 主工作流
- agents: 原有Agent实现（兼容模式）
- utils: 工具模块
"""

__version__ = "0.1.0"

# 核心模块导出
from novastar.core import (
    # LLM封装
    LLMWrapper,
    NovaStarModelFactory,
    create_llm_from_config,
    # 节点基类
    NovaStarBaseNode,
    NovaStarStartNode,
    NovaStarEndNode,
)

# 节点模块导出
from novastar.nodes import (
    CommanderNode,
    IntentRouterNode,
    IntentType,
    AgentType,
    MentorNode,
    ArtistNode,
    CompanionNode,
)

# 工作流模块导出
from novastar.workflow import (
    NovaStarWorkflow,
    create_novastar_workflow,
)

__all__ = [
    # 版本
    "__version__",
    # LLM
    "LLMWrapper",
    "NovaStarModelFactory",
    "create_llm_from_config",
    # 节点基类
    "NovaStarBaseNode",
    "NovaStarStartNode",
    "NovaStarEndNode",
    # Commander节点
    "CommanderNode",
    "IntentRouterNode",
    "IntentType",
    "AgentType",
    # Mentor节点
    "MentorNode",
    # Artist节点
    "ArtistNode",
    # Companion节点
    "CompanionNode",
    # 工作流
    "NovaStarWorkflow",
    "create_novastar_workflow",
]
