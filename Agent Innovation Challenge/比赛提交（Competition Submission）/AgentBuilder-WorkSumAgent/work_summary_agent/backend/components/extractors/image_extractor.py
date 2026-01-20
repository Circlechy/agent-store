# -*- coding: utf-8 -*-
"""
图片提取组件

封装InputProcessor的图片处理功能，支持OCR和多模态LLM识别
支持自动截屏模式（is_auto_screenshot）
"""

from typing import Dict, Any, Optional
from pathlib import Path
from openjiuwen.core.component.base import ComponentExecutable, WorkflowComponent
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.common.logging import logger

# 导入InputProcessor
import sys
from pathlib import Path as PathLib
_current_file = PathLib(__file__).resolve()
_backend_dir = _current_file.parent.parent.parent
sys.path.insert(0, str(_backend_dir))
from backend.input_processor import InputProcessor, InputType


class ImageExtractorComponent(ComponentExecutable, WorkflowComponent):
    """图片提取组件 - 封装InputProcessor的图片处理功能"""
    
    def __init__(self, image_processing_mode: str = "ocr"):
        """
        初始化图片提取组件
        
        Args:
            image_processing_mode: 图片处理模式 ("ocr", "multimodal", "both", 默认"ocr")
        """
        self.input_processor = InputProcessor()
        self.image_processing_mode = image_processing_mode
    
    async def invoke(self, inputs: Dict[str, Any], runtime: Runtime, context: Context) -> Dict[str, Any]:
        """
        提取图片内容
        
        Args:
            inputs: 输入数据，包含：
                - file_path: 图片文件路径（字符串）
                - is_auto_screenshot: 是否是自动截图（默认False），影响多模态模型的prompt
                - image_processing_mode: 可选，覆盖默认处理模式
            runtime: 运行时上下文
            context: 上下文引擎
            
        Returns:
            包含提取的文本和元数据的字典：
                - text: 提取的文本内容
                - metadata: 元数据（包含input_type、file_path、is_auto_screenshot等）
        """
        file_path = inputs.get("file_path")
        if not file_path:
            logger.warning("图片提取组件：未提供文件路径")
            return {
                "text": "",
                "metadata": {
                    "input_type": "image",
                    "extracted": False,
                    "error": "未提供文件路径"
                }
            }
        
        file_path = Path(file_path)
        if not file_path.exists():
            logger.warning(f"图片提取组件：文件不存在: {file_path}")
            return {
                "text": "",
                "metadata": {
                    "input_type": "image",
                    "extracted": False,
                    "error": f"文件不存在: {file_path}"
                }
            }
        
        # 获取is_auto_screenshot参数（关键参数）
        is_auto_screenshot = inputs.get("is_auto_screenshot", False)
        
        # 获取处理模式（优先使用输入中的，否则使用默认值）
        processing_mode = inputs.get("image_processing_mode", self.image_processing_mode)
        
        try:
            logger.info(f"图片提取组件：开始提取图片内容: {file_path.name}, "
                       f"is_auto_screenshot={is_auto_screenshot}, mode={processing_mode}")
            
            # 调用InputProcessor处理图片
            # 传递is_auto_screenshot参数，这会影响多模态模型的prompt
            result = await self.input_processor.process_input(
                InputType.IMAGE,
                str(file_path),
                file_path=str(file_path),
                image_processing_mode=processing_mode,
                is_auto_screenshot=is_auto_screenshot  # 关键参数
            )
            
            text = result.get("text", "")
            metadata = result.get("metadata", {})
            
            logger.info(f"图片提取组件：成功提取图片，文本长度={len(text)}")
            
            return {
                "text": text,
                "metadata": {
                    "input_type": "image",
                    "extracted": True,
                    "text_length": len(text),
                    "file_path": str(file_path),
                    "file_name": file_path.name,
                    "is_auto_screenshot": is_auto_screenshot,  # 传递到下游组件
                    "image_processing_mode": processing_mode,
                    **metadata
                }
            }
        except Exception as e:
            logger.error(f"图片提取组件：提取失败: {e}", exc_info=True)
            return {
                "text": "",
                "metadata": {
                    "input_type": "image",
                    "extracted": False,
                    "error": str(e),
                    "file_path": str(file_path),
                    "is_auto_screenshot": is_auto_screenshot
                }
            }
