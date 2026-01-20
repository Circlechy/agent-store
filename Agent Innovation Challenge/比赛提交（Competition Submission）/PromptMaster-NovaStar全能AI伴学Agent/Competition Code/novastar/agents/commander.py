"""Star-Commander: 主控Agent的简化API封装.

这个模块提供对底层CommanderNode的简化封装，
保持向后兼容的同时使用openjiuwen框架。
"""

from enum import Enum
from typing import Any, Dict, Optional

from novastar.nodes.commander_node import IntentRouterNode
from novastar.core.llm_wrapper import LLMWrapper, create_llm_from_config
from novastar.utils.config import get_config


# 重新导出枚举类型以保持向后兼容
class IntentType(str, Enum):
    """意图类型枚举."""
    LEARNING = "learning"
    STORY = "story"
    GAME = "game"
    EMOTION = "emotion"
    CREATIVE = "creative"
    HABIT = "habit"
    UNKNOWN = "unknown"


class AgentType(str, Enum):
    """Agent类型枚举."""
    MENTOR = "mentor"
    ARTIST = "artist"
    COMMANDER = "commander"


class StarCommander:
    """主控Agent的简化API封装.

    提供意图识别与任务路由能力。

    Example:
        >>> commander = StarCommander()
        >>> result = await commander.process(
        ...     user_id="child_001",
        ...     message="为什么天空是蓝色的？",
        ...     context={"age": 6}
        ... )
        >>> print(result["response"])
    """

    def __init__(
        self,
        name: str = "Star-Commander",
        model: Optional[str] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ):
        """初始化主控Agent.

        Args:
            name: Agent名称
            model: 使用的模型名称
            llm_config: LLM配置
            **kwargs: 其他配置参数
        """
        self.name = name
        self.model = model
        self.config = kwargs

        # 初始化LLM
        self._llm: Optional[LLMWrapper] = None
        if llm_config:
            self._llm = create_llm_from_config(llm_config)
            LLMWrapper.register("commander", self._llm)
        else:
            # 尝试从环境变量和配置文件自动加载LLM配置
            auto_llm_config = self._load_llm_config_from_env()
            if auto_llm_config:
                self._llm = create_llm_from_config(auto_llm_config)
                LLMWrapper.register("commander", self._llm)

        # 初始化节点
        node_config = {}
        self._intent_node = IntentRouterNode(config=node_config)

        # 设置LLM
        if self._llm:
            self._intent_node.set_llm(self._llm)

    async def process(
        self,
        user_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """处理用户消息.

        Args:
            user_id: 用户ID
            message: 用户消息
            context: 上下文信息

        Returns:
            处理结果，包含response、intent、routed_to等字段
        """
        context = context or {}

        # 模拟openjiuwen的输入格式
        inputs = {
            "query": message,
            "user_id": user_id,
            "context": context,
        }

        # 1. 意图识别
        intent_result = await self._intent_node._do_invoke(inputs, None, None)
        intent = intent_result.get("intent", IntentType.UNKNOWN.value)
        target_agent = intent_result.get("target_agent", AgentType.COMMANDER.value)

        # 2. 返回路由信息（由工作流或上层处理实际执行）
        return {
            "response": f"[需要路由到 {target_agent}]",
            "intent": intent,
            "routed_to": target_agent,
            "routing_reason": intent_result.get("routing_reason"),
            "needs_routing": True,
        }

    def _load_llm_config_from_env(self) -> Optional[Dict[str, Any]]:
        """从环境变量和配置文件加载LLM配置.

        Returns:
            LLM配置字典，如果配置不完整则返回None
        """
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

    async def identify_intent(self, message: str) -> IntentType:
        """识别用户意图.

        Args:
            message: 用户消息

        Returns:
            意图类型
        """
        inputs = {"query": message, "user_id": "temp", "context": {}}
        result = await self._intent_node._do_invoke(inputs, None, None)
        intent_str = result.get("intent", "unknown")
        for intent in IntentType:
            if intent.value == intent_str:
                return intent
        return IntentType.UNKNOWN

    async def route_task(self, intent: IntentType) -> AgentType:
        """根据意图路由到目标Agent.

        Args:
            intent: 意图类型

        Returns:
            目标Agent类型
        """
        routing_map = {
            IntentType.LEARNING: AgentType.MENTOR,
            IntentType.STORY: AgentType.ARTIST,
            IntentType.GAME: AgentType.ARTIST,
            IntentType.CREATIVE: AgentType.ARTIST,
            IntentType.EMOTION: AgentType.COMMANDER,
            IntentType.HABIT: AgentType.COMMANDER,
            IntentType.UNKNOWN: AgentType.COMMANDER,
        }
        return routing_map.get(intent, AgentType.COMMANDER)

