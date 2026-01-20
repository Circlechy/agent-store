# -*- coding: utf-8 -*-
"""
文本合并组件

合并来自三个提取器（text/document/image）的输出，统一传递给内容分析组件
"""

from typing import Dict, Any
from openjiuwen.core.component.base import ComponentExecutable, WorkflowComponent
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.common.logging import logger


class TextMergerComponent(ComponentExecutable, WorkflowComponent):
    """文本合并组件 - 合并来自不同提取器的输出"""
    
    async def invoke(self, inputs: Dict[str, Any], runtime: Runtime, context: Context) -> Dict[str, Any]:
        """
        合并文本输出
        
        支持混合输入：可以同时合并文本、文档、图片的内容
        例如：用户输入的文本 + 上传的文档，或 用户输入的文本 + 上传的图片
        
        Args:
            inputs: 输入数据，可能包含：
                - text_extractor: 文本提取器的输出
                - doc_extractor: 文档提取器的输出
                - image_extractor: 图片提取器的输出
                - additional_text: 用户输入的额外文本（可选）
            runtime: 运行时上下文
            context: 上下文引擎
            
        Returns:
            合并后的输出：
                - text: 合并后的文本内容
                - metadata: 元数据（包含所有输入源的信息）
        """
        # 从三个提取器中获取输出（支持多个同时有值）
        text_extractor_output = inputs.get("text_extractor", {})
        doc_extractor_output = inputs.get("doc_extractor", {})
        image_extractor_output = inputs.get("image_extractor", {})
        
        # 收集所有有效的文本片段
        text_parts = []
        sources = []
        all_metadata = {}
        
        # 收集文本提取器的输出
        if text_extractor_output and text_extractor_output.get("text"):
            text = text_extractor_output.get("text", "").strip()
            if text:
                text_parts.append(f"[用户输入文本]\n{text}")
                sources.append("text")
                all_metadata["text_source"] = text_extractor_output.get("metadata", {})
        
        # 收集文档提取器的输出
        if doc_extractor_output and doc_extractor_output.get("text"):
            text = doc_extractor_output.get("text", "").strip()
            if text:
                text_parts.append(f"[文档内容]\n{text}")
                sources.append("document")
                all_metadata["document_source"] = doc_extractor_output.get("metadata", {})
        
        # 收集图片提取器的输出
        if image_extractor_output and image_extractor_output.get("text"):
            text = image_extractor_output.get("text", "").strip()
            if text:
                text_parts.append(f"[图片内容]\n{text}")
                sources.append("image")
                all_metadata["image_source"] = image_extractor_output.get("metadata", {})
        
        # 获取additional_text（如果有，这是用户输入的额外文本）
        additional_text = inputs.get("additional_text", "").strip()
        if additional_text:
            text_parts.append(f"[用户补充说明]\n{additional_text}")
            sources.append("additional_text")
        
        # 合并所有文本
        if not text_parts:
            logger.warning("文本合并组件：所有提取器都未返回有效输出")
            return {
                "text": "",
                "metadata": {
                    "merged": False,
                    "error": "所有提取器都未返回有效输出",
                    "sources": []
                }
            }
        
        # 合并文本，使用双换行分隔不同来源的内容
        merged_text = "\n\n".join(text_parts)
        
        # 合并元数据
        merged_metadata = {
            "merged": True,
            "sources": sources,
            "source_count": len(sources),
            "has_text": "text" in sources,
            "has_document": "document" in sources,
            "has_image": "image" in sources,
            "has_additional_text": "additional_text" in sources,
            **all_metadata
        }
        
        # 从主要输入源获取is_auto_screenshot（优先从image_source获取）
        if "image_source" in all_metadata:
            merged_metadata["is_auto_screenshot"] = all_metadata["image_source"].get("is_auto_screenshot", False)
        elif "document_source" in all_metadata:
            merged_metadata["is_auto_screenshot"] = False
        elif "text_source" in all_metadata:
            merged_metadata["is_auto_screenshot"] = False
        else:
            merged_metadata["is_auto_screenshot"] = False
        
        logger.info(
            f"文本合并组件：成功合并来自 {', '.join(sources)} 的内容，"
            f"总长度={len(merged_text)}"
        )
        
        return {
            "text": merged_text,
            "metadata": merged_metadata
        }
