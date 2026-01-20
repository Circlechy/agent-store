#!/usr/bin/env python
# coding: utf-8
"""
文本匹配工具 - Mock实现

本工具用于模拟文本匹配功能，实际应用中可以实现文本相似度计算、关键词匹配等功能。
"""

from openjiuwen.core.component.base import WorkflowComponent
from openjiuwen.core.runtime.base import ComponentExecutable
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.common.utlis.dict_utils import extract_leaf_nodes, format_path
from openjiuwen.core.common.logging import logger
from typing import AsyncIterator, TypedDict, Union, AsyncGenerator, Any
from openjiuwen.core.runtime.constants import (
    END_COMP_TEMPLATE_RENDER_POSITION_TIMEOUT_KEY,
    END_COMP_TEMPLATE_BATCH_READER_TIMEOUT_KEY,
)
from openjiuwen.core.graph.executable import Input, Output
from openjiuwen.core.runtime.runtime import Runtime

from tools.element_matcher import ElementMatcher
from main_thread_timing import MainThreadTimingManager


class TextMatchingComponent(WorkflowComponent, ComponentExecutable):
    """文本匹配组件"""
    
    def to_executable(self) -> ComponentExecutable:
        return self

    # async def collect(
    #     self, inputs: Input, runtime: Runtime, context: Context
    # ) -> Output:
    #     print("🔍 [文本匹配工具] 正在进行文本匹配...")
    #     print("🔍 [文本匹配工具] 功能描述：负责文本相似度计算、关键词匹配和文本分类")

    #     chunks = []
    #     for path, value in extract_leaf_nodes(inputs):
    #         if isinstance(value, AsyncGenerator):
    #             async for frame in value:
    #                 chunks.append({format_path(path): frame})
    #         else:
    #             chunks.append({format_path(path): value})
    #     logger.debug(f"collect chunks: {chunks}")
    #     return {"collect_output": chunks}

    async def transform(
        self, inputs: Input, runtime: Runtime, context: Context
    ) -> Output:
        print("🔍 [文本匹配工具] 正在进行文本匹配...")
        print("🔍 [文本匹配工具] 功能描述：负责文本相似度计算、关键词匹配和文本分类")
        self.element_matcher = ElementMatcher.get_instance()
        
        # 获取MainThreadTimingManager实例
        self.timing_manager = MainThreadTimingManager.get_instance()
        
        for path, value in extract_leaf_nodes(inputs):
            if isinstance(value, AsyncGenerator):
                async for frame in value:
                    print(f"中转数据：{frame}")
                    # 提取recog_sentence字段
                    recog_sentence = None
                    if isinstance(frame, dict):
                        recog_sentence = frame.get("recog_sentence")
                    elif isinstance(frame, str):
                        # 如果frame是字符串，直接使用
                        recog_sentence = frame
                    else:
                        print(f"未知类型的frame：{type(frame)}")
                    
                    if recog_sentence:
                        print(f"提取到语音识别结果：{recog_sentence}")
                        matched_elements = self.element_matcher.match(recog_sentence)
                        print(f"匹配结果：{matched_elements}")
                    else:
                        print("未找到recog_sentence字段")
                        matched_elements = None
                    
                    # 提取匹配的element_id
                    if matched_elements and isinstance(matched_elements, dict):
                        text_idx = matched_elements.get("text_idx")
                        if text_idx is not None:
                            print(f"匹配到Element: {text_idx}")
                            # 更新当前Element并开始计时
                            print(f"⏰ 更新当前Element并开始计时: {text_idx}")
                            self.timing_manager.update_current_element(text_idx)
                            # 检查计时
                            self.timing_manager.check_timing()
                    
                    yield {"matched_elements": matched_elements}
            else:
                yield {"matched_results": value}

    async def invoke(self, inputs, runtime, context):
        """执行文本匹配"""
        print("🔍 [文本匹配工具] 正在进行文本匹配...")
        print("🔍 [文本匹配工具] 功能描述：负责文本相似度计算、关键词匹配和文本分类")
        for content in inputs["recog_sentence"]:
            print(content)

        # Mock实现：返回模拟的文本匹配结果
        return {
            "result": {
                "matching_id": "match_101",
                "similarity_score": 0.85,
                "matched_keywords": ["关键词1", "关键词2"],
                "matching_result": "匹配成功",
            },
            "data": {"match_score": 0.85},
        }


# 导出组件
__all__ = ["TextMatchingComponent"]
