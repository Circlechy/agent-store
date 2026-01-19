import json
import logging
import os

from pydantic import BaseModel, Field
from openjiuwen.core.workflow.base import Workflow
from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata, WorkflowInputsSchema
from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.graph.executable import Input, Output
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory

from nodes.base_node import init_router
from nodes.plan_node import PlanNode
from nodes.car_node import CarNode
from nodes.car_agents.ac_node import AcNode
from nodes.car_agents.light_node import LightNode
from nodes.car_agents.media_node import MediaNode
from nodes.car_agents.seat_node import SeatNode
from nodes.car_agents.tyre_node import TyreNode
from nodes.car_agents.window_node import WindowNode
from nodes.weather_node import WeatherNode
from nodes.agent_node import AgentNode
from nodes.map_node import MapNode
from prompts.template import apply_template
from tools.carTools.get_all_state import _get_all_state
from nodes.utils.utils import build_environment_alerts_section

logger = logging.getLogger(__name__)
factory = ModelFactory()
model_name = os.getenv("MODEL_NAME")
model = factory.get_model(
    model_provider=os.getenv("MODEL_PROVIDER"),
    api_base=os.getenv("API_BASE"),
    api_key=os.getenv("API_KEY"),
    max_retries=3,
    timeout=600,
)
node_list = [
    "car_node",
    "ac_node",
    "light_node",
    "seat_node",
    "window_node",
    "media_node",
    "tyre_node",
    "weather_node",
    "agent_node",
    "map_node",
    "end",
]


class MultiAgentState(BaseModel):
    plan: list[dict] = Field(default=[], description="PlanAgent生成的任务计划")
    query: str = Field(default="", description="用户查询")
    external_messages: list[dict] = Field(default=[], description="外部历史消息，记录用户与Agent的交互历史")
    internal_messages: list[dict] = Field(default=[], description="内部历史消息，记录Agent内部执行的逻辑和结果")
    result: str = Field(default="", description="Plan计划的执行结果")


class StartNode(Start):
    """启动节点"""
    
    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        logger.info("Multi Agent Start Node Invoked")
        self._validate_inputs(inputs)
        inputs = self._fill_default_values(inputs)

        sub_context = MultiAgentState(
            query=inputs.get("query"),
            external_messages=inputs.get("messages"),
            internal_messages=[],
            plan=[],
            result="",
        )
        runtime.update_global_state({"sub_context": sub_context.model_dump(exclude_none=True)})

        return inputs


class EndNode(End):
    """结束节点"""

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        logger.info("Multi Agent End Node Invoked")
        plan = runtime.get_global_state("sub_context.plan")
        internal_messages = runtime.get_global_state("sub_context.internal_messages")
        unfinished_tasks = []
        finished_tasks = []
        for item in plan:
            if item.get("node") == "end":
                continue
            if not item.get("is_finished"):
                logger.warning(f"任务 {item.get('task')} 未完成")
                unfinished_tasks.append(item.get("task"))
            else:
                logger.info(f"任务 {item.get('task')} 已完成")
                finished_tasks.append(item.get("task"))
        result = f"🚗 智能车载助手任务完成情况："
        result += f"总计 {len(plan)} 个任务，其中未完成 {len(unfinished_tasks)} 个，已完成 {len(finished_tasks)} 个 \n"
        result += f"未完成任务：{unfinished_tasks}, \n"
        result += f"已完成任务：{finished_tasks}。"
        logger.info(result)
        final_response = await self._generate_final_response(plan, result, internal_messages)
        runtime.update_global_state({"sub_context.result": final_response})

        return inputs

    async def _generate_final_response(self, plan: list[dict], result: str, internal_messages: list[dict]) -> str:
        all_state = _get_all_state()
        
        # 生成环境感知提醒（形成闭环）
        environment_alerts_section = build_environment_alerts_section()
        
        final_response_prompt = apply_template("final_response", {
            "plan": plan,
            "result": result,
            "all_state": json.dumps(all_state, ensure_ascii=False),
            "sub_agent_messages": internal_messages,
            "environment_alerts": environment_alerts_section
        })
        response = await model.ainvoke(model_name=model_name, messages=final_response_prompt)
        return response.model_dump(exclude_none=True).get("content", "")
    

def build_multi_agent_sub_graph() -> Workflow:
    config = WorkflowConfig(
        metadata=WorkflowMetadata(
            name="Multi Agent Sub Graph",
            description="A multi agent sub graph with PlanAgent, CarNode, WeatherNode, AgentNode, and MapNode"
        ),
        inputs_schema=WorkflowInputsSchema(
            properties={},
            required=[]
        )
    )
    workflow = Workflow(workflow_config=config)
    workflow.set_start_comp(
        "start", 
        StartNode(
            {"inputs": [
                {"id": "query", "type": "string", "required": True, "sourceType": "ref"},
                {"id": "messages", "type": "list", "required": True, "sourceType": "ref"}
            ]}
        ),
        inputs_schema={
            "query": "${query}",
            "messages": "${messages}"
        }
    )
    workflow.add_workflow_comp("plan_agent", PlanNode())
    workflow.add_workflow_comp("car_node", CarNode())
    workflow.add_workflow_comp("ac_node", AcNode())
    workflow.add_workflow_comp("light_node", LightNode())
    workflow.add_workflow_comp("seat_node", SeatNode())
    workflow.add_workflow_comp("window_node", WindowNode())
    workflow.add_workflow_comp("media_node", MediaNode())
    workflow.add_workflow_comp("tyre_node", TyreNode())
    workflow.add_workflow_comp("weather_node", WeatherNode())
    workflow.add_workflow_comp("agent_node", AgentNode())
    workflow.add_workflow_comp("map_node", MapNode())
    workflow.set_end_comp("end", EndNode())

    workflow.add_connection("start", "plan_agent")
    plan_router = init_router("plan_agent", node_list)
    workflow.add_conditional_connection("plan_agent", router=plan_router)
    for node in node_list:
        if node == "end":
            continue
        node_router = init_router(node, node_list)
        workflow.add_conditional_connection(node, router=node_router)

    return workflow