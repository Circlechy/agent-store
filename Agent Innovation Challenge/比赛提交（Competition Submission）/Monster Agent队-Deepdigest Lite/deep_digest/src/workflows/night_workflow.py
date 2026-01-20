"""
Night Agent 工作流定义
实现碎片 → 卡片的蒸馏流程：Fetch → Recall → Brain → Archive
"""

from datetime import datetime
from openjiuwen.core.workflow.base import Workflow
from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.component.tool_comp import ToolComponent, ToolComponentConfig
from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata, WorkflowInputsSchema
from openjiuwen.core.utils.tool.function.function import LocalFunction, Param

from src.tools.inbox_tools import get_pending_fragments
from src.tools.memory_tools import load_memory_index
from src.prompts.night_prompts import DISTILLER_SYSTEM_PROMPT
from src.components.archiver_comp import ArchiverComponent
from src.components.brain_comp import BrainComponent


def build_night_workflow(model_config) -> Workflow:
    """
    构建 Night Agent 的核心工作流
    
    节点编排:
        1. Start: 工作流起点
        2. FetchNode: 从 Inbox 提取待处理碎片
        3. RecallNode: 加载长期记忆索引
        4. BrainNode: LLM 蒸馏知识（意图分析 + 记忆关联）
        5. ArchiverNode: 保存卡片 + 删除碎片
        6. End: 工作流终点
    
    Args:
        model_config: LLM 配置对象
    
    Returns:
        Workflow 实例
    """
    
    # === 创建 Workflow 配置 ===
    workflow_config = WorkflowConfig(
        metadata=WorkflowMetadata(
            id="night_workflow",
            name="NightWorkflow",
            version="1.0",
            description="Night Agent 工作流：碎片蒸馏为知识卡片"
        ),
        workflow_inputs_schema=WorkflowInputsSchema(
            type="object",
            properties={},
            required=[]
        )
    )
    
    # === 初始化工作流 ===
    workflow = Workflow(workflow_config=workflow_config)
    
    # === Start Node ===
    start_node = Start({})

    
    # === 节点 1: Fetch - 提取碎片 (使用 LocalFunction 包装) ===
    fetch_tool = LocalFunction(
        name="FetchFragments",
        description="从 Inbox 提取待处理的碎片",
        func=get_pending_fragments,
        params=[]
    )
    fetch_config = ToolComponentConfig()
    fetch_node = ToolComponent(fetch_config).bind_tool(fetch_tool)
    
    # === 节点 2: Recall - 加载记忆索引 (使用 LocalFunction 包装) ===
    recall_tool = LocalFunction(
        name="LoadMemoryIndex",
        description="加载长期记忆的轻量级索引",
        func=load_memory_index,
        params=[]
    )
    recall_config = ToolComponentConfig()
    recall_node = ToolComponent(recall_config).bind_tool(recall_tool)
    
    # === 节点 3: Brain - LLM 蒸馏 (使用自定义组件) ===
    brain_node = BrainComponent(model_config, DISTILLER_SYSTEM_PROMPT)
    
    # === 节点 4: Archiver - 归档与清理 ===
    archiver_node = ArchiverComponent()
    
    # === End Node ===
    end_node = End({})
    
    # === 添加节点到 Workflow ===
    workflow.set_start_comp("start", start_node)
    workflow.add_workflow_comp("FetchNode", fetch_node, inputs_schema={})
    workflow.add_workflow_comp("RecallNode", recall_node, inputs_schema={})
    
    # 获取当前日期和星期
    current_date = datetime.now().strftime('%Y-%m-%d %A')
    # 将英文星期转换为中文
    weekday_map = {'Monday': '星期一', 'Tuesday': '星期二', 'Wednesday': '星期三', 
                   'Thursday': '星期四', 'Friday': '星期五', 'Saturday': '星期六', 'Sunday': '星期日'}
    for en, zh in weekday_map.items():
        current_date = current_date.replace(en, zh)
    
    workflow.add_workflow_comp("BrainNode", brain_node, 
                              inputs_schema={
                                  "fragments": "${FetchNode.data.fragments}", 
                                  "memory_index": "${RecallNode.data.memory_index}",
                                  "current_date": current_date
                              })
    workflow.add_workflow_comp("ArchiverNode", archiver_node, 
                              inputs_schema={"llm_output": "${BrainNode.cards}"})
    workflow.set_end_comp("end", end_node, inputs_schema={"result": "${ArchiverNode}"})
    
    # === 定义边（数据流）===
    workflow.add_connection("start", "FetchNode")
    workflow.add_connection("start", "RecallNode")
    workflow.add_connection("FetchNode", "BrainNode")
    workflow.add_connection("RecallNode", "BrainNode")
    workflow.add_connection("BrainNode", "ArchiverNode")
    workflow.add_connection("ArchiverNode", "end")
    
    return workflow
