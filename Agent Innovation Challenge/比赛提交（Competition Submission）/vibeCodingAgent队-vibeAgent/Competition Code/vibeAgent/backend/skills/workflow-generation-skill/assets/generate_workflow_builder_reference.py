# ========== 参考workflow_builder.py示例代码 ==========
import setup_path

from config import create_workflow_config, WORKFLOW_ID, WORKFLOW_NAME, WORKFLOW_VERSION, WORKFLOW_DESCRIPTION, AGENT_ID, AGENT_VERSION, AGENT_DESCRIPTION
from components import (
    create_start_component,
    create_intent_detection_component,
    create_llm_component,
    create_questioner_component,
    create_plugin_component,
    create_end_component,
)
from openjiuwen.core.workflow.base import Workflow

def build_workflow():
    # 1. 创建工作流对象
    flow = Workflow(workflow_config=create_workflow_config())
    # 2. 实例化所有组件
    start = create_start_component()
    intent = create_intent_detection_component()
    llm = create_llm_component()
    questioner = create_questioner_component()
    plugin = create_plugin_component()
    end = create_end_component()

    # 3. 注册组件到工作流
    flow.set_start_comp("start", start, inputs_schema={"query": "${query}"})

    # 意图识别组件接收来自 start 组件的查询
    flow.add_workflow_comp("intent", intent, inputs_schema={"query": "${start.query}"})

    # LLM 组件接收来自 start 组件的查询
    flow.add_workflow_comp("llm", llm, inputs_schema={"query": "${start.query}"})

    # 参数提取组件接收改写后的查询，根据components.py中create_llm_component中的定义，llm的输出变量为rewritten_query，所以inputs_schema中的query引用设置为${llm.rewritten_query}
    flow.add_workflow_comp("questioner", questioner, inputs_schema={"query": "${llm.rewritten_query}"})

    # 插件组件接收提取的地点和日期参数
    flow.add_workflow_comp("plugin", plugin, inputs_schema={
        "location": "${questioner.location}",
        "date": "${questioner.date}",
    })

    # 结束组件接收插件调用的结果
    flow.set_end_comp("end", end, inputs_schema={"output": "${plugin.data}"})

    # 4. 连接工作流拓扑
    # **重要**：Start 只连接到 Intent Detection，不能同时连接到多个节点
    flow.add_connection("start", "intent")     # start -> intent
    intent.add_branch("${intent.classification_id} == 0", ["end"], "默认分支")  # 默认分支固定为0！！！
    intent.add_branch("${intent.classification_id} == 1", ["llm"], "查询某地天气")
    # Intent Detection 会根据分类结果自动路由到不同的分支（通过 add_branch 配置）
    
    flow.add_connection("llm", "questioner")   # llm -> questioner
    flow.add_connection("questioner", "plugin") # questioner -> plugin
    flow.add_connection("plugin", "end")       # plugin -> end
    return flow

from openjiuwen.agent.common.schema import WorkflowSchema
from openjiuwen.agent.config.workflow_config import WorkflowAgentConfig
from openjiuwen.agent.workflow_agent.workflow_agent import WorkflowAgent

def create_workflow_schema() -> WorkflowSchema:
    return WorkflowSchema(
        id=WORKFLOW_ID,
        name=WORKFLOW_NAME,
        description=WORKFLOW_DESCRIPTION,
        version=WORKFLOW_VERSION,
        inputs={"query": {
            "type": "string",
            }
        }
    )

def build_workflow_agent():
    """
    构建工作流 Agent
    """
    # 构建工作流
    flow = build_workflow()
    # 创建工作流 Schema
    schema = create_workflow_schema()
    # 创建 WorkflowAgentConfig
    workflow_agent_config = WorkflowAgentConfig(
        id=AGENT_ID,
        version=AGENT_VERSION,
        description=AGENT_DESCRIPTION,
        workflows=[schema]
    )
    # 创建 Agent 实例
    workflow_agent = WorkflowAgent(workflow_agent_config)
    # 绑定工作流到 Agent
    workflow_agent.bind_workflows([flow])

    return workflow_agent
