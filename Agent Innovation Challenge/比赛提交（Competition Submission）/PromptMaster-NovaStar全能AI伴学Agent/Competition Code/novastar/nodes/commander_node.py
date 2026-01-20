"""Commander节点模块 - 基于openjiuwen的主控Agent节点.

负责意图识别、任务路由等核心功能。
"""

import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.graph.executable import Input, Output
from openjiuwen.core.runtime.runtime import Runtime

from novastar.core.base_node import NovaStarBaseNode

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """意图类型枚举."""
    LEARNING = "learning"  # 语言学习（汉字）
    STORY = "story"  # 故事绘本
    QA = "qa"  # 十万个为什么
    CHAT = "chat"  # 陪伴闲聊
    UNKNOWN = "unknown"  # 未知意图


class AgentType(str, Enum):
    """Agent类型枚举."""
    MENTOR = "mentor"  # 智教Agent
    ARTIST = "artist"  # 创意Agent
    COMPANION = "companion"  # 闲聊陪伴Agent
    COMMANDER = "commander"  # 主控Agent


class IntentRouterNode(NovaStarBaseNode):
    """意图路由节点.

    负责识别用户意图并路由到合适的Agent节点。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化意图路由节点.

        Args:
            config: 节点配置
        """
        super().__init__(name="IntentRouterNode", config=config)
        self._system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """加载系统提示词."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "commander.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "你是启明星（NovaStar）的主控Agent，负责识别用户意图并路由到合适的处理模块。"

    async def _do_invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        """执行意图识别和路由.

        Args:
            inputs: 输入数据
            runtime: 运行时环境
            context: 上下文

        Returns:
            路由结果
        """
        query = self.get_input_value(inputs, "query", "")
        user_id = self.get_input_value(inputs, "user_id", "")

        logger.info(f"[IntentRouterNode] 开始意图识别: query={query[:50]}...")

        # 识别意图（支持前端覆盖）
        intent = self._get_intent_override(inputs)
        if intent is None:
            intent = await self._identify_intent(query)

        # 确定路由目标
        target_agent, routing_reason = self._route_task(intent)

        result = {
            "query": query,
            "user_id": user_id,
            "intent": intent.value,
            "target_agent": target_agent.value,
            "routing_reason": routing_reason,
            "next_node": self._get_next_node(target_agent),
        }

        logger.info(f"[IntentRouterNode] 意图识别完成: intent={intent.value}, target={target_agent.value}")
        return result

    async def _identify_intent(self, message: str) -> IntentType:
        """识别用户意图.

        Args:
            message: 用户消息

        Returns:
            意图类型
        """
        # 使用LLM进行意图识别
        intent_prompt = f"""分析以下儿童输入，识别其意图类型。

输入：{message}

意图类型选项：
- learning: 语言学习（汉字）
- story: 睡前故事
- qa: 十万个为什么问答
- chat: 陪伴闲聊
- unknown: 无法确定

只返回意图类型，不要其他内容。"""

        try:
            response = await self.chat(intent_prompt, system_prompt=self._system_prompt)
            intent_str = response.strip().lower()

            for intent in IntentType:
                if intent.value == intent_str:
                    return intent
            return IntentType.UNKNOWN
        except Exception as e:
            logger.warning(f"[IntentRouterNode] LLM意图识别失败: {e}，使用关键词匹配")
            return self._keyword_intent_match(message)

    def _get_intent_override(self, inputs: Input) -> Optional[IntentType]:
        """从输入中读取前端指定的意图（可选）."""
        raw_intent = self.get_input_value(inputs, "intent", "")
        if not raw_intent:
            return None

        intent_str = str(raw_intent).strip().lower()
        for intent in IntentType:
            if intent.value == intent_str:
                logger.info("[IntentRouterNode] 使用前端指定意图: %s", intent.value)
                return intent

        logger.warning("[IntentRouterNode] 无效意图覆盖: %s", raw_intent)
        return None

    def _keyword_intent_match(self, message: str) -> IntentType:
        """使用关键词匹配识别意图（后备方案）.

        Args:
            message: 用户消息

        Returns:
            意图类型
        """
        message_lower = message.lower()

        if any(word in message_lower for word in ["汉字", "拼音", "笔画", "部首"]):
            return IntentType.LEARNING
        elif any(word in message_lower for word in ["故事", "绘本", "睡前", "讲个故事"]):
            return IntentType.STORY
        elif any(word in message_lower for word in ["为什么", "怎么", "是什么", "原因", "原理", "为什么会"]):
            return IntentType.QA
        elif any(word in message_lower for word in ["聊天", "聊聊", "陪我", "一起聊"]):
            return IntentType.CHAT
        else:
            return IntentType.CHAT

    def _route_task(self, intent: IntentType) -> tuple:
        """根据意图路由到目标Agent.

        Args:
            intent: 意图类型

        Returns:
            (目标Agent类型, 路由原因)
        """
        routing_map = {
            IntentType.LEARNING: (AgentType.MENTOR, "语言学习路由到智教Agent"),
            IntentType.STORY: (AgentType.ARTIST, "故事请求路由到创意Agent"),
            IntentType.QA: (AgentType.MENTOR, "问答请求路由到智教Agent"),
            IntentType.CHAT: (AgentType.COMPANION, "闲聊由陪伴Agent处理"),
            IntentType.UNKNOWN: (AgentType.COMPANION, "未知意图交由陪伴Agent"),
        }
        return routing_map.get(intent, (AgentType.COMPANION, "默认由陪伴Agent处理"))

    def _get_next_node(self, target_agent: AgentType) -> str:
        """获取下一个节点ID.

        Args:
            target_agent: 目标Agent类型

        Returns:
            下一个节点ID
        """
        node_map = {
            AgentType.MENTOR: "mentor",
            AgentType.ARTIST: "artist",
            AgentType.COMPANION: "companion",
            AgentType.COMMANDER: "commander",  # 使用工作流中定义的节点ID
        }
        return node_map.get(target_agent, "commander")  # 默认路由到commander


class CommanderNode(NovaStarBaseNode):
    """主控Commander节点.

    负责直接处理情感陪伴、习惯养成等请求，以及协调其他Agent。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化Commander节点.

        Args:
            config: 节点配置
        """
        super().__init__(name="CommanderNode", config=config)
        self._system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """加载系统提示词."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "commander.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return """你是启明星（NovaStar）的主控Agent——Novy。

你是一个温暖、有耐心的AI伙伴，专门陪伴3-12岁的儿童。

你的职责：
1. 理解孩子的需求和情感
2. 提供温暖的情感支持
3. 帮助孩子养成好习惯
4. 用简单易懂的语言交流
5. 保持积极、鼓励的态度

请用温和、鼓励的语气与孩子交流。"""

    async def _do_invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        """执行Commander处理逻辑.

        Args:
            inputs: 输入数据
            runtime: 运行时环境
            context: 上下文

        Returns:
            处理结果
        """
        query = self.get_input_value(inputs, "query", "")
        user_id = self.get_input_value(inputs, "user_id", "")
        intent = self.get_input_value(inputs, "intent", IntentType.UNKNOWN.value)
        user_context = self.get_input_value(inputs, "context", {})

        logger.info(f"[CommanderNode] 处理请求: intent={intent}")

        # 构建提示词
        context_prompt = self._build_context_prompt(query, intent, user_context)

        # 调用LLM生成响应
        try:
            response = await self.chat(context_prompt, system_prompt=self._system_prompt)
        except Exception as e:
            logger.error(f"[CommanderNode] LLM调用失败: {e}")
            response = "抱歉，我暂时无法处理这个问题。让我们换个话题吧！"

        result = {
            "query": query,
            "user_id": user_id,
            "intent": intent,
            "response": response,
            "handled_by": "commander",
        }

        logger.info(f"[CommanderNode] 处理完成: response_length={len(response)}")
        return result

    async def stream_response(
        self, query: str, user_id: str, user_context: Dict[str, Any], intent: Optional[str] = None
    ):
        """流式生成主控回复."""
        intent_value = intent or IntentType.UNKNOWN.value
        context_prompt = self._build_context_prompt(query, intent_value, user_context)

        yield {
            "query": query,
            "user_id": user_id,
            "intent": intent_value,
            "handled_by": "commander",
            "agents": ["commander"],
        }

        async for chunk in self.stream_chat(context_prompt, system_prompt=self._system_prompt):
            if chunk:
                yield {"response": chunk}

    def _build_context_prompt(
        self,
        query: str,
        intent: str,
        user_context: Dict[str, Any],
    ) -> str:
        """构建包含上下文的提示词.

        Args:
            query: 用户查询
            intent: 意图类型
            user_context: 用户上下文

        Returns:
            完整提示词
        """
        age = user_context.get("age", 6)

        context_parts = [f"用户年龄：{age}岁"]

        context_text = "\n".join(context_parts)

        prompt = f"""用户信息：
{context_text}

用户输入：{query}
意图类型：{intent}

请以Novy（启明星）的身份，用温和、鼓励的语气回应。"""

        return prompt
