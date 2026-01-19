import json
import logging
import os

from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory

from nodes.base_node import BaseNode
from nodes.utils.utils import build_environment_alerts_section, extract_json_content, emit_plan_update
from prompts.template import apply_template

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


class PlanNode(BaseNode):
    """根据用户输入拆分任务计划"""
    def __init__(self):
        super().__init__()

    async def _do_invoke(self, inputs, runtime, context):
        query = runtime.get_global_state("sub_context.query") or ""
        external_messages = runtime.get_global_state("sub_context.external_messages") or []
        logger.info(f"PlanNode Invoked with query: {query}")

        environment_alerts = build_environment_alerts_section()
        runtime.update_global_state({"sub_context.environment_alerts": environment_alerts})

        agent_input = {
            "current_query": query,
            "external_messages": external_messages,
            "environment_alerts": environment_alerts,
        }

        plan_prompt = apply_template("plan_node", agent_input)

        response = await model.ainvoke(model_name=model_name, messages=plan_prompt)
        raw_content = response.model_dump(exclude_none=True).get("content", "").strip()

        logger.info(f"PlanNode Response: {raw_content}")

        plan = self._safe_parse_plan(raw_content, query)
        runtime.update_global_state({"sub_context.plan": plan})
        await emit_plan_update(runtime, plan)
        next_node = plan[0].get("node") if plan and len(plan) > 0 else "end"

        logger.info(f"🚗 智能车载助手计划生成完成: {plan}，将执行下一步: {next_node}")

        return {"next_node": next_node}

    def _safe_parse_plan(self, raw_content: str, fallback_query: str):
        raw_content = extract_json_content(raw_content)
        try:
            plan = json.loads(raw_content)
        except json.JSONDecodeError:
            logger.warning("计划解析失败，使用默认兜底计划")
            return [{"node": "agent_node", "task": fallback_query, "is_finished": False},
                {"node": "end", "task": "", "is_finished": True}]

        if not isinstance(plan, list):
            logger.warning("计划结构非列表，使用默认兜底计划")
            return [{"node": "agent_node", "task": fallback_query, "is_finished": False},
            {"node": "end", "task": "", "is_finished": True}]

        normalized = []
        for item in plan:
            if not isinstance(item, dict):
                continue
            node = item.get("node")
            task = item.get("task")
            is_finished = item.get("is_finished")
            if isinstance(node, str) and isinstance(task, str) and isinstance(is_finished, bool):
                normalized.append({"node": node, "task": task, "is_finished": is_finished})
            elif isinstance(node, str) and isinstance(task, str):
                normalized.append({"node": node, "task": task, "is_finished": False})

        if not normalized:
            logger.warning("计划为空或无效，使用默认兜底计划")
            return [{"node": "agent_node", "task": fallback_query, "is_finished": False},
                {"node": "end", "task": "", "is_finished": True}]

        end_tasks = [item for item in normalized if item.get("node") == "end"]
        agent_tasks = [item for item in normalized if item.get("node") == "agent_node"]
        other_tasks = [
            item for item in normalized
            if item.get("node") not in ["agent_node", "end"]
        ]
        if agent_tasks or end_tasks:
            normalized = agent_tasks + other_tasks
            if end_tasks:
                normalized += end_tasks

        return normalized
