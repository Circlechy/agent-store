import logging

from nodes.base_node import BaseNode

logger = logging.getLogger(__name__)


class InteractiveNode(BaseNode):
    """交互节点，用于向用户提问并等待用户确认"""
    def __init__(self):
        super().__init__()

    async def _do_invoke(self, inputs, runtime, context):
        prompt = "你好！我是你的智能助理，有什么我可以帮你的?"

        logger.info(f"助手询问: {prompt}")
        user_response = await runtime.interact(prompt)
        logger.info(f"用户回答: {user_response}")
        
        return dict(query=user_response)
