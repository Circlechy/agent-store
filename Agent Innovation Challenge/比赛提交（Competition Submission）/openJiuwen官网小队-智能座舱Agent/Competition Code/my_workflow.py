import asyncio
import logging
import dotenv

from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata, WorkflowInputsSchema
from openjiuwen.core.workflow.base import Workflow
from openjiuwen.core.graph.executable import Input, Output
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.runtime.workflow import WorkflowRuntime

from nodes.agent_node import AgentNode

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
query = "C罗和梅西现在分别加盟过哪些球队？请你搜索并总结最新的信息回答我。"
# query = "帮我在gitcode上查询openJiuwen组织下一个叫studio的项目，并介绍一下。"

class StartNode(Start):
    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        logger.info("Start Node Invoked")
        runtime.update_global_state({"language": "Chinese"})
        runtime.update_global_state({"query": query})
        return inputs

class EndNode(End):
    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        logger.info(f"Conversation Result: {runtime.get_global_state('result')}")
        logger.info("End Node Invoked")
        return inputs
    
def build_workflow() -> Workflow:

    config = WorkflowConfig(
        metadata=WorkflowMetadata(
            name="Test Workflow",
            description="A test workflow with Start, TestNode, and End nodes"
        ),
        inputs_schema=WorkflowInputsSchema(
            properties={},
            required=[]
        )
    )

    workflow = Workflow(workflow_config=config)
    workflow.set_start_comp("start", StartNode())
    workflow.add_workflow_comp("invoke_node", AgentNode())
    workflow.set_end_comp("end", EndNode())

    workflow.add_connection("start", "invoke_node")
    workflow.add_connection("invoke_node", "end")

    return workflow

if __name__ == "__main__":
    async def main():
        workflow = build_workflow()
        runtime = WorkflowRuntime()
        await workflow.invoke(inputs={}, runtime=runtime, context=None)

    asyncio.run(main())
