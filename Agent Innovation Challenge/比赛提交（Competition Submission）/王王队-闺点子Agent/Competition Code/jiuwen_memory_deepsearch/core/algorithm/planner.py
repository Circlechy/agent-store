import json
import logging
import re
import ast

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
            logger.info(f'[generate_plan] prompts: {prompts}')
            response = await llm_astream(prompts, need_stream_out=True, agent_name="planner")
            logger.info(f'[generate_plan] response: {response}')

            content = response.get("content", "")

            # 尝试解析 JSON
            try:
                if isinstance(content, str):
                    try:
                        generated_plan = json.loads(content)
                    except json.JSONDecodeError:
                        logger.warning("[generate_plan] JSON parse failed, trying ast.literal_eval fallback.")
                        # 尝试使用 ast.literal_eval 这种更宽松的解析（支持单引号）
                        # 处理 JSON 特有的 true/false/null 关键字
                        fixed_content = content.replace("true", "True").replace("false", "False").replace("null", "None")
                        try:
                            generated_plan = ast.literal_eval(fixed_content)
                        except Exception as ast_e:
                            logger.error(f"[generate_plan] ast.literal_eval also failed: {ast_e}")
                            raise json.JSONDecodeError("Failed to parse LLM response as JSON or Python literal", content, 0)
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
