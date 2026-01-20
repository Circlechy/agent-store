import asyncio
import logging
import os

from jiuwen_memory_deepsearch.core.workflow import DeepsearchAgent
from jiuwen_memory_deepsearch.utils.config import deepsearch_config
from jiuwen_memory_deepsearch.utils.logging import setup_global_logger

# 配置全局日志记录器
setup_global_logger()

logger = logging.getLogger('jiuwen_memory_deepsearch.main')

os.environ.setdefault("LLM_SSL_VERIFY", "false")
os.environ["WORKFLOW_EXECUTE_TIMEOUT"] = str(deepsearch_config.get("workflow.execution_timeout", 7200))

async def run_deepsearch_agent():
    query = "用户正在浏览口红，目前口红有哪些牌子，哪个牌子性价比高？"
    image_path = "temp/1.png"
    inputs = {
        "image_path": image_path,
        "is_image": True
        # "query": query,
        # "is_image": False
    }
    deepsearch_agent = DeepsearchAgent()
    async for chunk in deepsearch_agent.run(inputs):
        # logger.error(f"{chunk}")
        pass

if __name__ == "__main__":
    logger.info("Main function started")
    asyncio.run(run_deepsearch_agent())
    logger.info("Main function completed")