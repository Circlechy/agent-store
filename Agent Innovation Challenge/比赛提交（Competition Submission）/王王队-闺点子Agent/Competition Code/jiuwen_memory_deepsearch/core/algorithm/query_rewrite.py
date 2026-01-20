import json
import logging

from jiuwen_memory_deepsearch.prompts.prompts_utils import apply_system_prompt
from jiuwen_memory_deepsearch.utils.llm_utils import llm_astream

logger = logging.getLogger('jiuwen_memory_deepsearch.query_rewrite')


async def query_rewrite(query: str, extra_metadata: dict = None) -> list:
    inputs = {
        "query": query
    }
    prompts = apply_system_prompt("query_rewrite", inputs)
    try:
        response = await llm_astream(prompts,
                                     need_stream_out=True,
                                     agent_name="query_rewrite",
                                     extra_metadata=extra_metadata)
        content = response.get("content", "")
        try:
            content = json.loads(content)
        except Exception as e:
            logger.error(f'query_rewrite content is not json: {e}')
            return [query]
        query_list = content.get("query", [])
        if not query_list:
            logger.warning(f'query_rewrite query_list is empty, return original query: {query}')
            return [query]
        logger.info(f'query_rewrite query_list: {query_list}, original query: {query}')
        return query_list
    except Exception as e:
        logger.error(f'query_rewrite error: {e}')
        return [query]
    return query
