import logging
import os
import uuid

from jiuwen_memory_deepsearch.utils.config import deepsearch_config

os.environ.setdefault("LLM_SSL_VERIFY", "false")
os.environ["WORKFLOW_EXECUTE_TIMEOUT"] = str(deepsearch_config.get("workflow.execution_timeout", 7200))
os.environ["NO_PROXY"] = "127.0.0.1,7.242.109.94"

from openjiuwen.agent.common.schema import WorkflowSchema
from openjiuwen.agent.config.workflow_config import WorkflowAgentConfig
from openjiuwen.agent.workflow_agent.workflow_agent import WorkflowAgent
from openjiuwen.core.runner.runner import Runner
from openjiuwen.core.workflow.base import BranchRouter, Workflow
from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata

from jiuwen_memory_deepsearch.core.node import FeedbackSearchWayNode, ImageIntentRecognitionNode, SearchAnswerNode, SearchEndNode, \
    SearchEntryNode, SearchTeamNode, ShowImageNode, \
    StartNode

logger = logging.getLogger(__name__)


class DeepsearchAgent:
    def __init__(self):
        self.agent_name = "deepsearch"
        self.version = "1.0"
        self.agent = None
        self.description = "deepsearch demo for memory"
        self.search_workflow = None
        self._create_search_workflow_agent()

    async def run(self, inputs):
        try:
            session_id = inputs.get("session_id") or f"ds-{uuid.uuid4().hex[:8]}"
            interactive_input = inputs.get("interactive_input")
            logger.info(f'[DeepsearchAgent] run: session_id: {session_id}')
            logger.info(f'[DeepsearchAgent] run: interactive_input: {interactive_input}')
            if interactive_input is not None:
                run_inputs = {
                    "query": interactive_input,
                    "conversation_id": session_id
                }
            else:
                is_image = inputs.get("is_image", False)
                if is_image:
                    run_inputs = {
                        "image_path": inputs.get("image_path", ""),
                        "conversation_id": session_id
                    }
                else:
                    run_inputs = {
                        "query": inputs.get("query", ""),
                        "conversation_id": session_id
                    }
            async for chunk in Runner.run_agent_streaming(agent=self.agent, inputs=run_inputs):
                # logger.error(f"{chunk}")
                yield chunk
        except Exception as e:
            logger.exception(e)

    def _create_search_workflow_agent(self):
        search_workflow = self._create_search_workflow()
        workflow_schema = WorkflowSchema(
            id=self.agent_name,
            version=self.version,
            description=self.description,
            name=self.agent_name
        )
        workflow_config = WorkflowAgentConfig(
            id=self.agent_name,
            version=self.version,
            description=self.description,
            workflows=[workflow_schema]
        )
        self.agent = WorkflowAgent(workflow_config)
        self.agent.add_workflows([search_workflow])

    def _create_search_workflow(self):
        workflow_config = WorkflowConfig(
            metadata=WorkflowMetadata(
                id=self.agent_name,
                name=self.agent_name,
                version=self.version,
                description=self.description
            )
        )
        flow = Workflow(workflow_config=workflow_config)

        flow.set_start_comp(
            "start",
            StartNode(
                {
                    "inputs": [
                        {"id": "image_path", "type": "String",
                         "required": "true", "sourceType": "ref"},
                        {"id": "query", "type": "String",
                         "required": "true", "sourceType": "ref"},
                    ]
                }
            ),
            inputs_schema={"image_path": "${image_path}", "query": "${query}"}
        )

        flow.add_workflow_comp("image_intent_recognition", ImageIntentRecognitionNode())
        flow.add_workflow_comp("feedback_search_way", FeedbackSearchWayNode())
        flow.add_workflow_comp("entry", SearchEntryNode())
        flow.add_workflow_comp("team", SearchTeamNode())
        flow.add_workflow_comp("answer", SearchAnswerNode())
        flow.add_workflow_comp("show_image", ShowImageNode())

        flow.set_end_comp("end", SearchEndNode())

        flow.add_conditional_connection("start", router=self._conditional_router("start", ["image_intent_recognition", "entry", "end"]))
        flow.add_conditional_connection("image_intent_recognition", router=self._conditional_router("image_intent_recognition", ["feedback_search_way", "end"]))
        flow.add_connection("feedback_search_way", "entry")
        flow.add_conditional_connection("entry", router=self._conditional_router("entry", ["team", "end"]))
        # flow.add_connection("entry", "team")
        flow.add_connection("team", "answer")
        flow.add_connection("answer", "show_image")
        flow.add_connection("show_image", "end")

        return flow

    def _conditional_router(self, current_node: str, next_nodes: list[str]):
        router = BranchRouter()
        for next_node in next_nodes:
            condition = f"${{{current_node}.next_node}} == {next_node!r}"
            router.add_branch(condition, next_node)

        return router
