# -*- coding: utf-8 -*-
"""
文本提取组件

直接返回用户输入的文本内容，无需额外处理
"""

from typing import Dict, Any
from openjiuwen.core.component.base import ComponentExecutable, WorkflowComponent
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.common.logging import logger


class TextExtractorComponent(ComponentExecutable, WorkflowComponent):
    """文本提取组件 - 直接返回文本内容"""
    
    async def invoke(self, inputs: Dict[str, Any], runtime: Runtime, context: Context) -> Dict[str, Any]:
        """
        提取文本内容
        
        Args:
            inputs: 输入数据，包含：
                - content: 文本内容（字符串）
            runtime: 运行时上下文
            context: 上下文引擎
            
        Returns:
            包含提取的文本和元数据的字典：
                - text: 提取的文本内容
                - metadata: 元数据（包含input_type等）
        """
        content = inputs.get("content", "")
        
        if not content:
            logger.warning("文本提取组件：输入内容为空")
            return {
                "text": "",
                "metadata": {
                    "input_type": "text",
                    "extracted": False
                }
            }
        
        logger.info(f"文本提取组件：成功提取文本，长度={len(content)}")
        
        return {
            "text": content,
            "metadata": {
                "input_type": "text",
                "extracted": True,
                "text_length": len(content)
            }
        }
