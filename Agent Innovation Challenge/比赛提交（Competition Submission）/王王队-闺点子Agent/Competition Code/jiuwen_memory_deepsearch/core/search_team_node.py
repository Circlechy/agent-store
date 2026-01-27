import asyncio
import logging

from openjiuwen.core.component.base import WorkflowComponent
from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.runtime.base import ComponentExecutable, Input, Output
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.workflow.base import Workflow

from jiuwen_memory_deepsearch.core.algorithm.info_collector import InfoCollector
from jiuwen_memory_deepsearch.core.algorithm.planner import Planner
from jiuwen_memory_deepsearch.core.search_context import Message
from jiuwen_memory_deepsearch.utils.config import deepsearch_config
from jiuwen_memory_deepsearch.utils.llm_utils import runtime_var

logger = logging.getLogger(__name__)


class SearchPlanReasoningNode(WorkflowComponent, ComponentExecutable):
    def __init__(self):
        super().__init__()

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        runtime_var.set(runtime)
        logger.info(f'[SearchPlanReasoningNode] invoke')
        search_context = runtime.get_global_state("search_context")
        logger.info(
            f'[SearchPlanReasoningNode] search_context: {search_context}')
        messages = search_context.get("messages", "")
        algorithm_inputs = {
            "messages": messages,
            "max_step_num": deepsearch_config.get("planner.max_step_num", 5),
            "language": search_context.get("language", "zh-CN"),
            "search_way": search_context.get("search_way", "memory")
        }
        logger.info(
            f'[SearchPlanReasoningNode] algorithm_inputs: {algorithm_inputs}')
        planner_result = await Planner().generate_plan(algorithm_inputs)
        logger.info(
            f'[SearchPlanReasoningNode] planner_result: {planner_result}')

        runtime.update_global_state({
            "search_context.current_plan": planner_result.plan,
            "search_context.messages": [*messages, Message(role="assistant", content=planner_result.llm_result)]
        })


class SearchInfoCollectorNode(WorkflowComponent, ComponentExecutable):
    def __init__(self):
        super().__init__()

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        runtime_var.set(runtime)
        logger.info(f'[SearchInfoCollectorNode] invoke')
        search_context = runtime.get_global_state("search_context")
        current_plan = search_context.get("current_plan", "")
        query = search_context.get("query", "")
        search_way = search_context.get("search_way", "memory")
        collected_infos = search_context.get("collected_infos", [])
        logger.info(f'[SearchInfoCollectorNode] query: {query}')
        logger.info(f'[SearchInfoCollectorNode] current_plan: {current_plan}')
        current_inputs = {
            "query": query,
            "language": search_context.get("language", "zh-CN")
        }

        async_collecting_tasks = []
        collect_steps = []

        for step in current_plan.steps:
            if not step.step_result:
                info_collector = InfoCollector(current_inputs)
                await info_collector.init_tools(search_way)
                async_collecting_tasks.append(info_collector.get_info(step))
                collect_steps.append(step)
        await asyncio.gather(*async_collecting_tasks)

        for i, step in enumerate(collect_steps):
            collected_infos.append(step.step_result)
            logger.info(f'[SearchInfoCollectorNode] info {i}: {step.step_result}')

        runtime.update_global_state({
            "search_context.collected_infos": collected_infos
        })


class SearchEndNode(WorkflowComponent, ComponentExecutable):
    def __init__(self):
        super().__init__()

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        runtime_var.set(runtime)
        logger.info(f'[SearchEndNode] invoke')
        search_context = runtime.get_global_state("search_context")
        collected_infos = search_context.get("collected_infos", [])
        logger.info(f'[SearchEndNode] collected_infos: {collected_infos}')
        return collected_infos


def build_search_team_node_sub_workflow():
    sub_workflow = Workflow()
    sub_workflow.set_start_comp("start", Start())

    sub_workflow.add_workflow_comp("plan_reasoning", SearchPlanReasoningNode())
    sub_workflow.add_workflow_comp("info_collector", SearchInfoCollectorNode())

    sub_workflow.set_end_comp("end", SearchEndNode())

    sub_workflow.add_connection("start", "plan_reasoning")
    sub_workflow.add_connection("plan_reasoning", "info_collector")
    sub_workflow.add_connection("info_collector", "end")

    return sub_workflow
