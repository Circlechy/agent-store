# -*- coding: utf-8 -*-
"""
文档提取组件

封装InputProcessor的文档处理功能，支持Word、PDF、TXT、MD等格式
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


class DocumentExtractorComponent(ComponentExecutable, WorkflowComponent):
    """文档提取组件 - 封装InputProcessor的文档处理功能"""
    
    def __init__(self):
        """初始化文档提取组件"""
        self.input_processor = InputProcessor()
    
    async def invoke(self, inputs: Dict[str, Any], runtime: Runtime, context: Context) -> Dict[str, Any]:
        """
        提取文档内容
        
        Args:
            inputs: 输入数据，包含：
                - file_path: 文档文件路径（字符串）
                - content: 可选，如果提供则作为备用
            runtime: 运行时上下文
            context: 上下文引擎
            
        Returns:
            包含提取的文本和元数据的字典：
                - text: 提取的文本内容
                - metadata: 元数据（包含input_type、file_path等）
        """
        file_path = inputs.get("file_path")
        if not file_path:
            logger.warning("文档提取组件：未提供文件路径")
            return {
                "text": "",
                "metadata": {
                    "input_type": "document",
                    "extracted": False,
                    "error": "未提供文件路径"
                }
            }
        
        file_path = Path(file_path)
        if not file_path.exists():
            logger.warning(f"文档提取组件：文件不存在: {file_path}")
            return {
                "text": "",
                "metadata": {
                    "input_type": "document",
                    "extracted": False,
                    "error": f"文件不存在: {file_path}"
                }
            }
        
        # 检查文件类型：如果是图片文件，直接返回空结果（不报错）
        # 因为工作流中 doc_extractor 和 image_extractor 并行执行
        file_ext = file_path.suffix.lower()
        image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}
        if file_ext in image_extensions:
            logger.debug(f"文档提取组件：跳过图片文件 {file_path.name}（应由 image_extractor 处理）")
            return {
                "text": "",
                "metadata": {
                    "input_type": "document",
                    "extracted": False,
                    "skipped": True,
                    "reason": "图片文件应由 image_extractor 处理",
                    "file_path": str(file_path)
                }
            }
        
        try:
            logger.info(f"文档提取组件：开始提取文档内容: {file_path.name}")
            
            # 调用InputProcessor处理文档
            result = await self.input_processor.process_input(
                InputType.DOCUMENT,
                str(file_path),
                file_path=str(file_path)
            )
            
            text = result.get("text", "")
            metadata = result.get("metadata", {})
            
            logger.info(f"文档提取组件：成功提取文档，文本长度={len(text)}")
            
            return {
                "text": text,
                "metadata": {
                    "input_type": "document",
                    "extracted": True,
                    "text_length": len(text),
                    "file_path": str(file_path),
                    "file_name": file_path.name,
                    **metadata
                }
            }
        except Exception as e:
            logger.error(f"文档提取组件：提取失败: {e}", exc_info=True)
            return {
                "text": "",
                "metadata": {
                    "input_type": "document",
                    "extracted": False,
                    "error": str(e),
                    "file_path": str(file_path)
                }
            }
