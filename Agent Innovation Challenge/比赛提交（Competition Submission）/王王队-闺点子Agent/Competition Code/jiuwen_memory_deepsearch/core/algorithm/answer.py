import logging

from jiuwen_memory_deepsearch.prompts.prompts_utils import apply_system_prompt
from jiuwen_memory_deepsearch.utils.llm_utils import llm_astream

logger = logging.getLogger(__name__)


class Answer:
    def __init__(self):
        pass

    async def answer(self, algorithm_input: dict) -> str:

        try:
            llm_input = apply_system_prompt("answer", algorithm_input)

            logger.info(f'[Answer] answer, llm_input: {llm_input}')

            llm_output = await llm_astream(llm_input, need_stream_out=True, agent_name="answer")
            logger.info(f'[Answer] answer, llm_output: {llm_output}')
            answer = llm_output.get("content", "")
            
            # 清理可能出现的代码块标记
            answer = answer.strip()
            if answer.startswith("```"):
                answer = answer.lstrip("`").strip()
            if answer.endswith("```"):
                answer = answer.rstrip("`").strip()

            return answer
        except Exception as e:
            logger.error(f'[Answer] answer error: {e}')
            return ""
