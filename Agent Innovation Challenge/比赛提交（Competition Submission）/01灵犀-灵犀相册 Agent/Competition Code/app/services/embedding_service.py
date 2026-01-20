"""
Embedding服务模块
封装Qwen3-VL多模态Embedding模型的调用
"""

import sys
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, TYPE_CHECKING
from PIL import Image

# 先添加模型脚本路径到sys.path（必须在最前面）
SCRIPTS_PATH = Path(__file__).parent.parent.parent / \
    "qwen3-vl-embedding-2B" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

# 延迟导入：只在类型检查时导入，运行时不导入
if TYPE_CHECKING:
    from qwen3_vl_embedding import Qwen3VLEmbedder

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Embedding服务类
    负责管理Qwen3-VL模型实例并提供向量生成接口
    """

    _instance: Optional["EmbeddingService"] = None
    _embedder: Optional[Any] = None  # 使用Any避免类型错误

    def __new__(cls):
        """单例模式确保只有一个模型实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._initialized = getattr(self, '_initialized', False)

    def initialize(
        self,
        model_path: str,
        max_length: int = 8192,
        min_pixels: int = 4096,
        max_pixels: int = 1843200,
        default_instruction: str = "Represent the user's input.",
        device: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        初始化Embedding模型

        Args:
            model_path: 模型路径或HuggingFace模型ID
            max_length: 最大序列长度
            min_pixels: 图像最小像素数
            max_pixels: 图像最大像素数
            default_instruction: 默认指令提示
            device: 显式指定设备（如 'cuda:1', 'mps', 'cpu'）
            **kwargs: 传递给模型的其他参数
        """
        if self._initialized and self._embedder is not None:
            logger.info("Embedding模型已初始化，跳过重复初始化")
            return

        logger.info(
            f"正在初始化Embedding模型: {model_path} (Device: {device or 'Auto'})")

        # 在这里动态导入模块（sys.path已在模块顶部设置好）
        from qwen3_vl_embedding import Qwen3VLEmbedder

        self._embedder = Qwen3VLEmbedder(
            model_name_or_path=model_path,
            max_length=max_length,
            min_pixels=min_pixels,
            max_pixels=max_pixels,
            default_instruction=default_instruction,
            device=device,
            **kwargs
        )
        self._initialized = True
        logger.info("Embedding模型初始化完成")

    @property
    def is_initialized(self) -> bool:
        """检查模型是否已初始化"""
        return self._initialized and self._embedder is not None

    @property
    def vector_dimension(self) -> int:
        """获取向量维度"""
        if not self.is_initialized:
            raise RuntimeError("Embedding服务未初始化")
        # Qwen3-VL的embedding维度
        return self._embedder.model.config.hidden_size

    def generate_embedding(
        self,
        text: Optional[str] = None,
        image: Optional[Union[str, Image.Image]] = None,
        instruction: Optional[str] = None,
        normalize: bool = True
    ) -> List[float]:
        """
        生成单个输入的Embedding向量

        Args:
            text: 文本内容
            image: 图片路径或PIL Image对象
            instruction: 指令提示词
            normalize: 是否归一化向量

        Returns:
            向量列表
        """
        if not self.is_initialized:
            raise RuntimeError("Embedding服务未初始化，请先调用initialize()")

        input_data = {
            "text": text,
            "image": image,
            "instruction": instruction
        }

        embeddings = self._embedder.process([input_data], normalize=normalize)
        return embeddings[0].cpu().tolist()

    def generate_embeddings_batch(
        self,
        inputs: List[Dict[str, Any]],
        normalize: bool = True
    ) -> List[List[float]]:
        """
        批量生成Embedding向量

        Args:
            inputs: 输入列表，每个元素包含text、image、instruction等字段
            normalize: 是否归一化向量

        Returns:
            向量列表的列表
        """
        if not self.is_initialized:
            raise RuntimeError("Embedding服务未初始化，请先调用initialize()")

        embeddings = self._embedder.process(inputs, normalize=normalize)
        return embeddings.cpu().tolist()

    def generate_text_embedding(
        self,
        text: str,
        instruction: Optional[str] = None,
        normalize: bool = True
    ) -> List[float]:
        """
        生成纯文本的Embedding向量

        Args:
            text: 文本内容
            instruction: 指令提示词
            normalize: 是否归一化向量

        Returns:
            向量列表
        """
        return self.generate_embedding(
            text=text,
            instruction=instruction,
            normalize=normalize
        )

    def generate_image_embedding(
        self,
        image: Union[str, Image.Image],
        instruction: Optional[str] = None,
        normalize: bool = True
    ) -> List[float]:
        """
        生成图片的Embedding向量

        Args:
            image: 图片路径或PIL Image对象
            instruction: 指令提示词
            normalize: 是否归一化向量

        Returns:
            向量列表
        """
        return self.generate_embedding(
            image=image,
            instruction=instruction,
            normalize=normalize
        )

    def generate_multimodal_embedding(
        self,
        text: str,
        image: Union[str, Image.Image],
        instruction: Optional[str] = None,
        normalize: bool = True
    ) -> List[float]:
        """
        生成图文混合的Embedding向量

        Args:
            text: 文本内容
            image: 图片路径或PIL Image对象
            instruction: 指令提示词
            normalize: 是否归一化向量

        Returns:
            向量列表
        """
        return self.generate_embedding(
            text=text,
            image=image,
            instruction=instruction,
            normalize=normalize
        )


# 全局服务实例
embedding_service = EmbeddingService()


def get_embedding_service() -> EmbeddingService:
    """获取Embedding服务实例"""
    return embedding_service
