"""Star-Artist: 创意Agent的简化API封装（仅故事生成）。"""

from typing import Any, Dict, List, Optional

from novastar.nodes.artist_node import ArtistNode
from novastar.core.llm_wrapper import LLMWrapper, create_llm_from_config
from novastar.utils.config import get_config

class StarArtist:
    """创意Agent的简化API封装.

    仅提供故事生成方法。

    Example:
        >>> artist = StarArtist()
        >>> result = await artist.generate_image(
        ...     user_id="child_001",
        ...     prompt="一只可爱的小恐龙",
        ...     context={"age": 6}
        ... )
        >>> print(result["content"])
    """

    def __init__(
        self,
        name: str = "Star-Artist",
        model: Optional[str] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        mcp_config: Optional[Dict[str, Any]] = None,
        auto_load_llm: bool = True,
        **kwargs: Any,
    ):
        """初始化创意Agent.

        Args:
            name: Agent名称
            model: 使用的模型名称
            llm_config: LLM配置
            mcp_config: MCP工具配置
            **kwargs: 其他配置参数
        """
        self.name = name
        self.model = model
        self.config = kwargs

        # 初始化LLM（如果没有提供llm_config，且允许自动加载则尝试从环境变量加载）
        self._llm: Optional[LLMWrapper] = None
        if llm_config:
            self._llm = create_llm_from_config(llm_config)
            LLMWrapper.register("artist", self._llm)
        elif auto_load_llm:
            # 尝试从环境变量和配置文件自动加载LLM配置
            auto_llm_config = self._load_llm_config_from_env()
            if auto_llm_config:
                self._llm = create_llm_from_config(auto_llm_config)
                LLMWrapper.register("artist", self._llm)

        # 初始化节点
        node_config = {
            "mcp": mcp_config or {},
            **kwargs,
        }
        self._artist_node = ArtistNode(config=node_config)

        # 设置LLM
        if self._llm:
            self._artist_node.set_llm(self._llm)

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
        
        # 统一读取所有模型名称
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

    async def generate_story(
        self,
        user_id: str,
        request: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """生成故事.

        Args:
            user_id: 用户ID
            request: 故事请求
            context: 上下文信息

        Returns:
            生成结果，包含content（标题和内容）等字段
        """
        context = context or {}
        age = context.get("age", 6)
        interests = context.get("interests", [])

        result = await self._artist_node._generate_story(request, age, interests)

        return {
            "content": result.get("content", {}),
            "description": result.get("description", ""),
            "metadata": result.get("metadata", {}),
        }

    async def generate_idiom_story(
        self,
        user_id: str,
        idiom: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """生成成语故事.

        Args:
            user_id: 用户ID
            idiom: 成语
            context: 上下文信息

        Returns:
            生成结果，包含content（标题和内容）等字段
        """
        context = context or {}
        age = context.get("age", 6)

        result = await self._artist_node._generate_idiom_story(idiom, age)

        return {
            "content": result.get("content", {}),
            "description": result.get("description", ""),
            "metadata": result.get("metadata", {}),
        }