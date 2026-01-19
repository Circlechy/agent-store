import logging
import os

from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory

from nodes.base_node import BaseNode
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


class RouterNode(BaseNode):
    """根据上下文和用户输入，决定下一步应该执行哪个节点"""
    def __init__(self):
        super().__init__()

    def _post_handle(self, inputs, runtime, context):
        query = inputs.get("query", "")
        runtime.update_global_state({"query": query})

        return dict()

    async def _do_invoke(self, inputs, runtime, context):
        agent_input = {
            "current_input": inputs.get("query", ""),
        }

        router_prompt = apply_template("router", agent_input)

        response = await model.ainvoke(model_name=model_name, messages=router_prompt)
        raw_content = response.model_dump(exclude_none=True).get("content", "").strip()
        
        raw_lower = raw_content.lower()
        if raw_lower == "map" or raw_lower.startswith("map"):
            next_node = "map_node"
        elif raw_lower == "car" or (raw_lower.startswith("car") and "agent" not in raw_lower and "map" not in raw_lower):
            next_node = "car_node"
        elif raw_lower == "weather" or raw_lower.startswith("weather"):
            next_node = "weather_node"
        elif "agent" in raw_lower:
            next_node = "agent_node"
        else:
            logger.warning(f"路由节点返回了意外的内容: {raw_content}，将使用默认值 'agent_node'")
            next_node = "agent_node"
        
        logger.info(f"路由到节点: {next_node} (原始输出: {raw_content})")

        _ = self._post_handle({"query": inputs.get("query", "")}, runtime, context)

        return dict(next_node=next_node)