"""
Night Agent 工厂模块
创建基于 Workflow 的 Night Agent（造梦 Agent）
"""

from openjiuwen.agent.workflow_agent.workflow_agent import WorkflowAgent
from openjiuwen.agent.config.workflow_config import WorkflowAgentConfig
from openjiuwen.agent.common.schema import WorkflowSchema
from src.workflows.night_workflow import build_night_workflow


def create_night_agent(model_config):
    """
    创建 Night Agent 实例
    
    Night Agent 执行"造梦"流程：
        1. 从 Inbox 提取碎片
        2. 加载长期记忆索引
        3. LLM 蒸馏：分析意图 + 关联记忆
        4. 归档：保存卡片 + 删除碎片（熵减）
    
    Args:
        model_config: LLM 配置对象
    
    Returns:
        WorkflowAgent 实例
    
    Usage:
        >>> from src.config import get_model_config
        >>> from src.agents.night_agent import create_night_agent
        >>> 
        >>> config = get_model_config()
        >>> agent = create_night_agent(config)
        >>> result = await agent.invoke()
    """
    
    # 构建工作流
    workflow = build_night_workflow(model_config)
    
    # 创建 WorkflowSchema
    workflow_schema = WorkflowSchema(
        id=workflow.config().metadata.id,
        name=workflow.config().metadata.name,
        version=workflow.config().metadata.version,
        description="Night Agent: 将碎片蒸馏为知识卡片，关联记忆并完成熵减清理",
        inputs={}
    )
    
    # 创建 WorkflowAgentConfig
    agent_config = WorkflowAgentConfig(
        name="NightAgent",
        description="Night Agent: 将碎片蒸馏为知识卡片，关联记忆并完成熵减清理",
        workflows=[workflow_schema]
    )
    
    # 创建 WorkflowAgent 并绑定 workflow
    agent = WorkflowAgent(agent_config)
    agent.bind_workflows([workflow])
    
    return agent
