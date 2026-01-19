import asyncio
import logging
import dotenv
import uuid

from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata, WorkflowInputsSchema
from openjiuwen.core.workflow.base import Workflow
from openjiuwen.core.graph.executable import Input, Output
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.runtime.workflow import WorkflowRuntime
from openjiuwen.core.runtime.interaction.interactive_input import InteractiveInput

from nodes.car_node import CarNode
from nodes.interactive_node import InteractiveNode
from nodes.router_node import RouterNode
from nodes.agent_node import AgentNode
from nodes.map_node import MapNode
from nodes.weather_node import WeatherNode
from nodes.base_node import init_router

dotenv.load_dotenv(dotenv_path=".env")

# Configure logger to output to run.log in root directory
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('run.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class StartNode(Start):
    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        logger.info("Start Node Invoked")
        runtime.update_global_state({"language": "Chinese"})
        messages = runtime.get_global_state("messages") or []
        logger.info(f"Initial Message count: {len(messages)}")
        return inputs

class EndNode(End):
    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        logger.info(f"Conversation Result: {runtime.get_global_state('result')}")
        logger.info("End Node Invoked")
        return inputs

def build_workflow() -> Workflow:

    config = WorkflowConfig(
        metadata=WorkflowMetadata(
            name="Car Workflow",
            description="A car cabin agent workflow with Start, Interactive, Router, MapNode, CarNode, WeatherNode, AgentNode, and End nodes"
        ),
        inputs_schema=WorkflowInputsSchema(
            properties={},
            required=[]
        )
    )

    workflow = Workflow(workflow_config=config)
    workflow.set_start_comp("start", StartNode())
    workflow.add_workflow_comp("interactive_node", InteractiveNode(),
                               outputs_schema={"query": "${query}"})
    workflow.add_workflow_comp("router_node", RouterNode(),
                               inputs_schema={"query": "${interactive_node.query}"})
    workflow.add_workflow_comp("map_node", MapNode())
    workflow.add_workflow_comp("car_node", CarNode())
    workflow.add_workflow_comp("weather_node", WeatherNode())
    workflow.add_workflow_comp("agent_node", AgentNode())
    workflow.set_end_comp("end", EndNode())

    workflow.add_connection("start", "interactive_node")
    workflow.add_connection("interactive_node", "router_node")
    router = init_router("router_node", ["map_node", "agent_node", "car_node", "weather_node"])
    workflow.add_conditional_connection("router_node", router=router)
    workflow.add_connection("map_node", "end")
    workflow.add_connection("agent_node", "end")
    workflow.add_connection("car_node", "end")
    workflow.add_connection("weather_node", "end")

    return workflow

if __name__ == "__main__":
    async def main():
        workflow = build_workflow()
        session_id = uuid.uuid4().hex

        # 第一次调用，启动对话
        await workflow.invoke(inputs={}, runtime=WorkflowRuntime(session_id=session_id), context=None)
        
        while True:
            query = input("请输入您想对车载助手说的话 (输入 'exit' 退出): ")
            if query.lower() in ['exit', '退出', 'quit']:
                logger.info("用户退出对话")
                return

            user_input = InteractiveInput(str(query))

            await workflow.invoke(inputs=user_input, runtime=WorkflowRuntime(session_id=session_id), context=None)

    asyncio.run(main())
