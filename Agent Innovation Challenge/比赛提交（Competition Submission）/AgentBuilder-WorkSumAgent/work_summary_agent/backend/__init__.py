# -*- coding: utf-8 -*-
"""
工作总结 Agent - 后端模块

提供核心功能：
- WorkSummaryAgentAdapter: 工作总结适配器（向后兼容）
- WorkSummaryWorkflowAgent: 基于 WorkflowAgent 的工作流Agent
- InputProcessor: 输入处理模块
"""

from .work_summary_agent_adapter import WorkSummaryAgentAdapter
from .input_processor import InputType, InputProcessor

# 向后兼容：提供 WorkSummaryAgent 别名
WorkSummaryAgent = WorkSummaryAgentAdapter

__all__ = [
    'WorkSummaryAgent',
    'WorkSummaryAgentAdapter',
    'InputType',
    'InputProcessor',
]
