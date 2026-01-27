import asyncio
import logging
import os
import uuid

from jiuwen_memory_deepsearch.core.workflow import DeepsearchAgent
from jiuwen_memory_deepsearch.utils.config import deepsearch_config
from jiuwen_memory_deepsearch.utils.logging import setup_global_logger
from openjiuwen.core.runtime.interaction.interactive_input import InteractiveInput
from openjiuwen.core.runtime.workflow import WorkflowRuntime

# 配置全局日志记录器
setup_global_logger()

logger = logging.getLogger('jiuwen_memory_deepsearch.main')

os.environ.setdefault("LLM_SSL_VERIFY", "false")
os.environ["WORKFLOW_EXECUTE_TIMEOUT"] = str(deepsearch_config.get("workflow.execution_timeout", 7200))

def _build_interactive_input(interactions):
    if not interactions:
        return InteractiveInput()
    if len(interactions) == 1:
        answer = input("请输入搜索方式：").strip()
        return InteractiveInput(answer)
    user_input = InteractiveInput()
    for item in interactions:
        payload = getattr(item, "payload", None)
        node_id = getattr(payload, "id", None)
        if not node_id and isinstance(item, dict):
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            node_id = payload.get("id")
        answer = input(f"请输入 {node_id or '未知组件'} 的回答：").strip()
        if node_id:
            user_input.update(node_id, answer)
    return user_input


async def run_deepsearch_agent():
    # query = "用户正在浏览口红，目前口红有哪些牌子，哪个牌子性价比高？"
    query = "你是谁？"
    image_path = "temp/17.png"
    inputs = {
        "image_path": image_path,
        "is_image": True
        # "query": query,
        # "is_image": False
    }
    deepsearch_agent = DeepsearchAgent()
    workflow = deepsearch_agent._create_search_workflow()
    session_id = uuid.uuid4().hex

    output = await workflow.invoke(inputs, WorkflowRuntime(session_id=session_id))
    logger.info(f"首次执行输出: {output}")

    if "INPUT_REQUIRED" in str(getattr(output, "state", "")):
        interactions = getattr(output, "result", []) or []
        user_input = _build_interactive_input(interactions)
        output = await workflow.invoke(user_input, WorkflowRuntime(session_id=session_id))
        logger.info(f"恢复后输出: {output}")

if __name__ == "__main__":
    logger.info("Main function started")
    asyncio.run(run_deepsearch_agent())
    logger.info("Main function completed")