import json
import logging

from pydantic import BaseModel, Field

from jiuwen_memory_deepsearch.core.search_context import Plan
from jiuwen_memory_deepsearch.prompts.prompts_utils import apply_system_prompt
from jiuwen_memory_deepsearch.utils.llm_utils import llm_astream

logger = logging.getLogger(__name__)


class PlannerResult(BaseModel):
    plan_success: bool = Field(default=False, description="生成计划是否成功")
    plan: Plan | None = Field(default=None, description="生成的计划实例")
    llm_result: list = Field(default=[], description="响应的消息列表")


class Planner:
    def __init__(self):
        pass

    async def generate_plan(self, current_inputs: dict) -> PlannerResult:
        """Generating a complete plan."""
        logger.info("[generate_plan] Begin plan generation operation.")

        planner_result = PlannerResult()
        prompts = apply_system_prompt("planner", current_inputs)

        try:
            response = await llm_astream(prompts, need_stream_out=True, agent_name="planner")
            logger.info(f'[generate_plan] response: {response}')

            content = response.get("content", "")

            # 尝试解析 JSON
            try:
                if isinstance(content, str):
                    generated_plan = json.loads(content)
                else:
                    generated_plan = content

                # 验证为 Plan 模型
                plan = Plan.model_validate(generated_plan)
                llm_result = json.dumps(response, indent=4, ensure_ascii=False)
                planner_result.llm_result = llm_result
                planner_result.plan = plan
                planner_result.plan_success = True

                logger.info("[generate_plan] Plan generation succeeded.")

            except json.JSONDecodeError as e:
                error_msg = f"Planner LLM response failed JSON deserialization. error: {e}"
                logger.error(f"[generate_plan] {error_msg}")
            except Exception as e:
                error_msg = f"Planner LLM does not follow the structured output. error: {e}"
                logger.error(f"[generate_plan] {error_msg}")

        except Exception as e:
            error_msg = f"Planner LLM invocation failed. error: {e}"
            logger.exception(f"[generate_plan] {error_msg}")

        return planner_result
