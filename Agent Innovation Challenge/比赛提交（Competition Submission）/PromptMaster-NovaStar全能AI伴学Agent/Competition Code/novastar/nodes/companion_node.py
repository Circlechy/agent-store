"""Companion节点模块 - 基于openjiuwen的陪伴闲聊节点."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.graph.executable import Input, Output
from openjiuwen.core.runtime.runtime import Runtime

from novastar.core.base_node import NovaStarBaseNode

logger = logging.getLogger(__name__)


class CompanionNode(NovaStarBaseNode):
    """陪伴闲聊节点.

    仅负责简单聊天陪伴。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="CompanionNode", config=config)
        self._system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        prompt_path = Path(__file__).parent.parent / "prompts" / "companion.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "你是启明星（NovaStar）的陪伴闲聊Agent，负责轻松聊天。"

    async def _do_invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        query = self.get_input_value(inputs, "query", "")
        user_id = self.get_input_value(inputs, "user_id", "")
        user_context = self.get_input_value(inputs, "context", {})

        logger.info("[CompanionNode] 闲聊请求: user_id=%s", user_id)

        prompt = f"""和孩子进行轻松闲聊。

孩子的话：{query}
年龄：{user_context.get("age", 6)}岁

要求：
- 语气温暖、友好
- 句子简短
- 适度提问，引导继续聊天
"""
        try:
            response = await self.chat(prompt, system_prompt=self._system_prompt)
        except Exception as e:
            logger.error("[CompanionNode] 闲聊生成失败: %s", e)
            response = "我在这里陪你聊天呀！你今天想聊点什么？"

        return {
            "query": query,
            "user_id": user_id,
            "response": response,
            "handled_by": "companion",
        }

    async def stream_response(
        self, query: str, user_id: str, user_context: Dict[str, Any], intent: Optional[str] = None
    ):
        """流式生成陪伴回复."""
        prompt = f"""和孩子进行轻松闲聊。

孩子的话：{query}
年龄：{user_context.get("age", 6)}岁

要求：
- 语气温暖、友好
- 句子简短
- 适度提问，引导继续聊天
"""
        yield {
            "query": query,
            "user_id": user_id,
            "intent": intent or "chat",
            "handled_by": "companion",
            "agents": ["companion"],
        }

        async for chunk in self.stream_chat(prompt, system_prompt=self._system_prompt):
            if chunk:
                yield {"response": chunk}