import logging

from openjiuwen.core.utils.tool.function.function import LocalFunction
from openjiuwen.core.utils.tool.param import Param

from jiuwen_memory_deepsearch.prompts.prompts_utils import apply_system_prompt
from jiuwen_memory_deepsearch.utils.llm_utils import llm_astream

logger = logging.getLogger(__name__)


def _create_function_tool():
    send_to_planner = LocalFunction(
        name="send_to_planner",
        description="send_to_planner",
        params=[
            Param(name="query_title",
                  description="The title of the query to be handed off.",
                  param_type="string",
                  required=True),
            Param(name="language",
                  description="The user's detected language locale.",
                  param_type="string",
                  required=True)
        ],
        func=None
    )
    return send_to_planner


async def classify_query(inputs: dict) -> dict:
    """
        Query routing: Determine whether to enter the deep (re)search process.

        Args:
        context: Current agent context
        config: Current runtime configuration

        Returns:
            bool: whether to enter the deep (re)search process.
            str: language locale.
    """
    logger.info(f"[classify_query] Begin query classification operation.")

    prompts = apply_system_prompt("entry", inputs)
    tool_calls = []
    response = {}
    try:
        response = await llm_astream(prompts,
                                     tools=[_create_function_tool().get_tool_info()],
                                     need_stream_out=True,
                                     agent_name="entry")
        logger.info(f'[classify_query] response: {response}')
        tool_calls = response.get('tool_calls', [])

    except Exception as e:
        logger.exception(f"[classify_query] Exception: {e}")

    if tool_calls:
        logger.info(f"[classify_query] Get tool_calls: {tool_calls}")
        return {
            "go_deepsearch": True,
            "language": response.get('tool_calls', [])[0].get("args", {}).get("language", "zh-CN"),
            "llm_result": response.get("content", ""),
        }
    return {
        "go_deepsearch": False,
        "language": "zh-CN",
        "llm_result": response.get("content", ""),
    }
