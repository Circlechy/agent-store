"""Star-Companion: 陪伴闲聊Agent的简化API封装."""

from typing import Any, Dict, Optional

from novastar.nodes.companion_node import CompanionNode
from novastar.core.llm_wrapper import LLMWrapper, create_llm_from_config
from novastar.utils.config import get_config


class StarCompanion:
    """陪伴闲聊Agent的简化API封装."""

    def __init__(
        self,
        name: str = "Star-Companion",
        model: Optional[str] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ):
        self.name = name
        self.model = model
        self.config = kwargs

        self._llm: Optional[LLMWrapper] = None
        if llm_config:
            self._llm = create_llm_from_config(llm_config)
            LLMWrapper.register("companion", self._llm)
        else:
            auto_llm_config = self._load_llm_config_from_env()
            if auto_llm_config:
                self._llm = create_llm_from_config(auto_llm_config)
                LLMWrapper.register("companion", self._llm)

        self._companion_node = CompanionNode(config=kwargs)
        if self._llm:
            self._companion_node.set_llm(self._llm)

    def _load_llm_config_from_env(self) -> Optional[Dict[str, Any]]:
        config = get_config()
        api_key = config.get_env("openai_api_key")
        api_base = config.get_env("openai_api_base")
        model_type = config.get_env("llm_model_type") or "openai"
        model_name = config.get_env("llm_model_name") or "qwen-plus"
        image_model_name = config.get_env("image_model_name") or "qwen-image-plus"
        tts_model_name = config.get_env("tts_model_name") or "qwen3-tts-flash"
        asr_model_name = config.get_env("asr_model_name") or "qwen3-asr-flash"
        if not api_key:
            return None
        return {
            "model_type": model_type,
            "model_name": model_name,
            "api_key": api_key,
            "api_base": api_base,
            "timeout": 60,
            "image_model_name": image_model_name,
            "tts_model_name": tts_model_name,
            "asr_model_name": asr_model_name,
        }

    async def process(
        self,
        user_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """处理闲聊请求."""
        context = context or {}
        inputs = {"query": message, "user_id": user_id, "context": context}
        result = await self._companion_node._do_invoke(inputs, None, None)
        return {
            "response": result.get("response", ""),
            "handled_by": "companion",
        }
