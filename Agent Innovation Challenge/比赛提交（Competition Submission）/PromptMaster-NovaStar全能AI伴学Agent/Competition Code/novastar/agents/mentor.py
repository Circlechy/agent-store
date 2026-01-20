"""Star-Mentor: 智教Agent的简化API封装.

这个模块提供对底层MentorNode的简化封装，
保持向后兼容的同时使用openjiuwen框架。
"""

from typing import Any, Dict, Optional

from novastar.nodes.mentor_node import MentorNode
from novastar.core.llm_wrapper import LLMWrapper, create_llm_from_config
from novastar.utils.config import get_config

class StarMentor:
    """智教Agent的简化API封装.

    提供两种能力：
    1. 汉字学习（字形、字音、字义、字源、字网）
    2. 十万个为什么（回答儿童问题）

    Example:
        >>> mentor = StarMentor()
        >>> result = await mentor.process(
        ...     user_id="child_001",
        ...     message="为什么天空是蓝色的？",
        ...     context={"age": 6}
        ... )
        >>> print(result["response"])
    """

    def __init__(
        self,
        name: str = "Star-Mentor",
        model: Optional[str] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ):
        """初始化智教Agent.

        Args:
            name: Agent名称
            model: 使用的模型名称
            llm_config: LLM配置
            **kwargs: 其他配置参数
        """
        self.name = name
        self.model = model
        self.config = kwargs

        # 初始化LLM（如果没有提供llm_config，尝试从环境变量加载）
        self._llm: Optional[LLMWrapper] = None
        if llm_config:
            self._llm = create_llm_from_config(llm_config)
            LLMWrapper.register("mentor", self._llm)
        else:
            # 尝试从环境变量和配置文件自动加载LLM配置
            auto_llm_config = self._load_llm_config_from_env()
            if auto_llm_config:
                self._llm = create_llm_from_config(auto_llm_config)
                LLMWrapper.register("mentor", self._llm)

        # 初始化节点
        node_config = kwargs
        self._mentor_node = MentorNode(config=node_config)

        # 设置LLM
        if self._llm:
            self._mentor_node.set_llm(self._llm)

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

    async def process(
        self,
        user_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """处理学习问题.

        Args:
            user_id: 用户ID
            message: 用户消息
            context: 上下文信息（包含age等）

        Returns:
            处理结果，包含response、lesson_type等字段
        """
        context = context or {}

        # 模拟openjiuwen的输入格式
        inputs = {
            "query": message,
            "user_id": user_id,
            "context": context,
        }

        # 调用节点处理
        result = await self._mentor_node._do_invoke(inputs, None, None)

        return {
            "response": result.get("response", ""),
            "lesson_type": result.get("lesson_type", "chinese"),
            "lesson": result.get("lesson", {}),
        }

    async def teach_character(
        self,
        user_id: str,
        character: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """汉字立体学习.

        Args:
            user_id: 用户ID
            character: 要学习的汉字
            context: 上下文信息

        Returns:
            学习结果，包含character、teaching_content、dimensions等字段
        """
        context = context or {}
        age = context.get("age", 6)

        # 调用节点的汉字教学方法
        result = await self._mentor_node.teach_character(character, age)

        return {
            "character": result.get("character", character),
            "teaching_content": result.get("teaching_content", ""),
            "dimensions": result.get("dimensions", ["字形", "字音", "字义", "字源", "字网"]),
        }

    async def answer_question(
        self,
        user_id: str,
        question: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """十万个为什么：回答儿童问题.
        
        Args:
            user_id: 用户ID
            question: 问题内容
            context: 上下文信息
            
        Returns:
            回答结果，包含question、answer_content等字段
        """
        context = context or {}
        age = context.get("age", 6)
        
        result = await self._mentor_node.answer_question(question, age)
        return {
            "question": result.get("question", question),
            "answer_content": result.get("answer_content", ""),
            "lesson_type": "qa",
            "image": result.get("image", ""),
            "audio": result.get("audio", ""),
        }