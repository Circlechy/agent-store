"""
Task 子代理工具实现

提供 Task 工具，允许主 Agent 启动子代理执行独立任务
"""

import os
import asyncio
import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

# 从本地 agent-core 导入
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'agent-core'))

from openjiuwen.core.utils.tool.base import Tool
from openjiuwen.core.utils.tool.schema import ToolInfo, Parameters
from openjiuwen.core.utils.tool.param import Param

from ..agents.mode_manager import AgentModeManager, AgentMode


# ==================== 子代理类型 ====================

class SubAgentType(Enum):
    """子代理类型"""
    EXPLORE = "Explore"      # 代码探索
    PLAN = "Plan"            # 实现规划
    BASH = "Bash"            # 命令执行
    GENERAL = "general-purpose"  # 通用代理
    RESEARCH = "Research"    # 调研代理


# ==================== 子代理配置 ====================

@dataclass
class SubAgentConfig:
    """子代理配置"""
    agent_type: SubAgentType
    description: str
    allowed_tools: List[str]
    max_turns: int = 10


# 子代理配置映射
SUBAGENT_CONFIGS: Dict[str, SubAgentConfig] = {
    "Explore": SubAgentConfig(
        agent_type=SubAgentType.EXPLORE,
        description="快速探索代码库，查找文件、搜索代码、回答代码库相关问题",
        allowed_tools=["read_file", "grep", "glob", "ls"],
        max_turns=50
    ),
    "Plan": SubAgentConfig(
        agent_type=SubAgentType.PLAN,
        description="设计实现方案，识别关键文件，考虑架构权衡",
        allowed_tools=["read_file", "grep", "glob", "ls", "todo_write"],
        max_turns=50
    ),
    "Bash": SubAgentConfig(
        agent_type=SubAgentType.BASH,
        description="执行命令行任务，如 git 操作、构建、测试等",
        allowed_tools=["bash", "read_file"],
        max_turns=50
    ),
    "general-purpose": SubAgentConfig(
        agent_type=SubAgentType.GENERAL,
        description="通用代理，可执行复杂的多步骤任务",
        allowed_tools=["read_file", "write_file", "edit_file", "bash", "grep", "glob", "ls", "todo_write"],
        max_turns=50
    ),
    "Research": SubAgentConfig(
        agent_type=SubAgentType.RESEARCH,
        description="调研代理，具备网络搜索、网页抓取、浏览器自动化能力，用于竞品分析、技术调研等",
        allowed_tools=["web_search", "web_fetch", "browser_open", "browser_snapshot", "browser_scroll", "browser_screenshot"],
        max_turns=80  # 调研任务需要更多轮次
    ),
}


# ==================== Task 工具 ====================

class TaskTool(Tool):
    """Task 子代理工具

    启动子代理执行独立任务，返回执行结果。
    子代理有独立的上下文，不会污染主对话。
    """

    def __init__(
        self,
        mode_manager: Optional[AgentModeManager] = None,
        session_id: Optional[str] = None,
        model_provider: str = "openai",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model_name: str = "gpt-4o"
    ):
        super().__init__()
        self.mode_manager = mode_manager
        self.session_id = session_id
        # LLM 配置（传递给子代理）
        self.model_provider = model_provider
        self.api_key = api_key
        self.api_base = api_base
        self.model_name = model_name

        self.name = "task"
        self.description = """启动子代理执行独立任务。

子代理类型:
- Explore: 快速探索代码库，查找文件和搜索代码
- Plan: 设计实现方案，识别关键文件
- Bash: 执行命令行任务
- general-purpose: 通用代理，执行复杂多步骤任务
- Research: 调研代理，具备网络搜索、网页抓取、浏览器自动化能力

使用场景:
- 需要并行执行多个独立任务
- 需要隔离的上下文执行复杂操作
- 需要专门的代理处理特定类型任务
- 需要进行竞品分析、技术调研等网络调研任务

参数:
- description: 任务简短描述（3-5 词）
- prompt: 详细的任务说明
- subagent_type: 子代理类型

注意:
- 子代理执行完成后返回结果
- 子代理的中间步骤对用户不可见
- 最多支持 1 层嵌套（子代理不能再启动子代理）
"""
        self.params = [
            Param(
                name="description",
                description="任务简短描述（3-5 词）",
                param_type="string",
                required=True
            ),
            Param(
                name="prompt",
                description="详细的任务说明",
                param_type="string",
                required=True
            ),
            Param(
                name="subagent_type",
                description="子代理类型: Explore, Plan, Bash, general-purpose",
                param_type="string",
                required=True
            ),
            Param(
                name="max_turns",
                description="最大执行轮数（可选）",
                param_type="integer",
                required=False
            ),
        ]

    def invoke(self, inputs: dict, **kwargs) -> str:
        """同步调用"""
        return asyncio.run(self.ainvoke(inputs, **kwargs))

    async def ainvoke(self, inputs: dict, **kwargs) -> str:
        """异步调用"""
        description = inputs.get("description", "")
        prompt = inputs.get("prompt", "")
        subagent_type = inputs.get("subagent_type", "general-purpose")
        max_turns = inputs.get("max_turns")

        if not description:
            return "错误: 未提供任务描述"

        if not prompt:
            return "错误: 未提供任务说明"

        # 获取子代理配置
        config = SUBAGENT_CONFIGS.get(subagent_type)
        if not config:
            available_types = ", ".join(SUBAGENT_CONFIGS.keys())
            return f"错误: 无效的子代理类型 '{subagent_type}'。可用类型: {available_types}"

        # 使用配置的 max_turns 或用户指定的值
        actual_max_turns = max_turns if max_turns else config.max_turns

        # 检查模式限制
        if self.mode_manager:
            current_mode = self.mode_manager.get_current_mode()
            if current_mode == AgentMode.PLAN:
                # PLAN 模式下只允许 Explore 和 Plan 子代理
                if subagent_type not in ["Explore", "Plan"]:
                    return f"错误: 在 PLAN 模式下只能使用 Explore 或 Plan 子代理，不能使用 {subagent_type}。"
            elif current_mode == AgentMode.REVIEW:
                # REVIEW 模式下允许 Explore 和 Bash 子代理（Bash 用于执行只读命令如 gh pr list）
                if subagent_type not in ["Explore", "Bash"]:
                    return f"错误: 在 REVIEW 模式下只能使用 Explore 或 Bash 子代理，不能使用 {subagent_type}。"

        # 执行子代理任务
        try:
            result = await self._execute_subagent(
                description=description,
                prompt=prompt,
                config=config,
                max_turns=actual_max_turns
            )
            return result
        except Exception as e:
            return f"错误: 子代理执行失败 - {str(e)}"

    async def _execute_subagent(
        self,
        description: str,
        prompt: str,
        config: SubAgentConfig,
        max_turns: int
    ) -> str:
        """执行子代理任务

        注意：这是一个简化实现。完整实现需要：
        1. 创建独立的 Agent 实例
        2. 配置允许的工具
        3. 执行任务并收集结果
        4. 返回最终结果

        当前实现使用模拟方式，实际集成需要与 openjiuwen SDK 的 Agent 系统对接。
        """
        # 构建子代理系统提示词
        system_prompt = f"""你是一个 {config.agent_type.value} 子代理。

任务描述: {description}

你的职责:
{config.description}

可用工具: {', '.join(config.allowed_tools)}

限制:
- 最多执行 {max_turns} 轮
- 不能启动其他子代理
- 完成任务后立即返回结果

请执行以下任务:
{prompt}
"""

        # 尝试使用 openjiuwen SDK 创建子代理
        try:
            from ..agents.openjiuwen_agent import JiuwenCodeAgent

            # 创建子代理（使用受限的工具集）
            sub_agent = JiuwenCodeAgent(
                model_provider=self.model_provider,
                api_key=self.api_key,
                api_base=self.api_base,
                model_name=self.model_name,
                mode_manager=self.mode_manager,
                max_iterations=max_turns,
                system_prompt=system_prompt,
                session_id=f"{self.session_id}_sub_{config.agent_type.value}" if self.session_id else None
            )

            # 执行任务
            result = await sub_agent.invoke(prompt)

            if isinstance(result, dict):
                return result.get("output", str(result))
            return str(result)

        except ImportError:
            # SDK 不可用，返回模拟结果
            return f"""## 子代理执行结果

**类型**: {config.agent_type.value}
**任务**: {description}

**说明**: 子代理功能需要完整的 openjiuwen SDK 支持。
当前为模拟模式，实际执行需要配置 LLM API。

**任务提示**:
{prompt[:500]}{'...' if len(prompt) > 500 else ''}

**建议**: 请手动执行上述任务，或配置 LLM API 后重试。
"""

        except Exception as e:
            return f"子代理执行异常: {str(e)}"

    def get_tool_info(self) -> ToolInfo:
        """获取工具信息"""
        return ToolInfo(
            type="function",
            name=self.name,
            description=self.description,
            parameters=Parameters(
                type="object",
                properties={
                    "description": {
                        "type": "string",
                        "description": "任务简短描述（3-5 词）"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "详细的任务说明"
                    },
                    "subagent_type": {
                        "type": "string",
                        "description": "子代理类型",
                        "enum": list(SUBAGENT_CONFIGS.keys())
                    },
                    "max_turns": {
                        "type": "integer",
                        "description": "最大执行轮数"
                    }
                },
                required=["description", "prompt", "subagent_type"]
            )
        )


# ==================== 工具工厂 ====================

def create_task_tool(
    mode_manager: Optional[AgentModeManager] = None,
    session_id: Optional[str] = None,
    model_provider: str = "openai",
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model_name: str = "gpt-4o"
) -> Tool:
    """创建 Task 工具

    Args:
        mode_manager: 模式管理器
        session_id: 会话 ID
        model_provider: 模型提供商
        api_key: API 密钥
        api_base: API Base URL
        model_name: 模型名称

    Returns:
        Task 工具实例
    """
    return TaskTool(
        mode_manager=mode_manager,
        session_id=session_id,
        model_provider=model_provider,
        api_key=api_key,
        api_base=api_base,
        model_name=model_name
    )
