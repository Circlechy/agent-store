#!/usr/bin/env python
# coding: utf-8
"""
视窗绘制工具 - Mock实现

本工具用于模拟视窗绘制功能，实际应用中可以实现绘制图形、图表等功能。
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


class WindowDrawingComponent(WorkflowComponent, ComponentExecutable):
    """视窗绘制组件"""
    
    def to_executable(self) -> ComponentExecutable:
        return self

    async def collect(
        self, inputs: Input, runtime: Runtime, context: Context
    ) -> Output:
        print("🎨 [视窗绘制工具] 正在绘制视窗内容...")
        print("🎨 [视窗绘制工具] 功能描述：负责在视窗中绘制图形、图表和用户界面元素")

        # 运行时导入，避免模块加载时触发 Tkinter
        from tools.highlight_renderer import HighlightRenderer

        self.window_renderer = HighlightRenderer.get_instance()
        chunks = []

        for path, value in extract_leaf_nodes(inputs):
            print(f"📥 收到路径: {path}, 值类型: {type(value)}")
            
            if isinstance(value, AsyncGenerator):
                async for frame in value:
                    print(f"🔍 收到匹配结果: {frame}")

                    # 处理输入数据格式
                    processed_data = frame
                    
                    # 处理输入数据的多层嵌套格式
                    if isinstance(frame, dict):
                        # 处理从工作流配置来的input_data字段（当前实际收到的格式）
                        if 'input_data' in frame:
                            input_data = frame['input_data']
                            print(f"📦 提取input_data: {input_data}")
                            
                            # 处理input_data内部的text_matching（当前实际格式）
                            if isinstance(input_data, dict) and 'text_matching' in input_data:
                                text_matching_data = input_data['text_matching']
                                print(f"📦 提取input_data中的text_matching: {text_matching_data}")
                                processed_data = text_matching_data
                            else:
                                processed_data = input_data
                        
                        # 处理直接的text_matching字段（当前实际收到的格式）
                        elif 'text_matching' in frame:
                            text_matching_data = frame['text_matching']
                            print(f"📦 提取text_matching: {text_matching_data}")
                            processed_data = text_matching_data
                        
                        # 处理其他格式
                        else:
                            processed_data = frame
                            print(f"📦 直接使用frame: {frame}")

                    # 从字典中提取正确的索引
                    if isinstance(processed_data, dict):
                        text_idx = processed_data.get("text_idx")
                        img_indices = processed_data.get("img_indices", [])
                        img_coords_map = processed_data.get("img_coords_map", {})
                        match_type = processed_data.get("match_type", "none")

                        # 只在有匹配时显示新高亮
                        if match_type != "none":
                            # 总是先清除旧的高亮
                            print("🧹 清除之前的高亮")
                            self.window_renderer.clear_all()
                            # 高亮文本元素
                            if text_idx is not None:
                                print(f"✅ 高亮文本索引: {text_idx}")
                                self.window_renderer.show_highlight(
                                    text_idx, elem_type="text"
                                )

                            # 高亮图片元素
                            for img_idx in img_indices:
                                if img_idx in img_coords_map:
                                    coords = img_coords_map[img_idx]
                                    print(f"✅ 高亮图片索引: {img_idx}, 坐标: {coords}")
                                    self.window_renderer.show_highlight(
                                        img_idx, elem_type="image", coords=coords
                                    )
                        else:
                            print("❌ 无匹配内容")
                    else:
                        # 兼容旧格式：直接传索引
                        self.window_renderer.clear_all()
                        self.window_renderer.show_highlight(processed_data)

                    chunks.append({format_path(path): frame})
            else:
                chunks.append({format_path(path): value})
        logger.debug(f"collect chunks: {chunks}")
        print(chunks)
        return {"collect_output": chunks}

    async def transform(
        self, inputs: Input, runtime: Runtime, context: Context
    ) -> Output:
        """流式处理接口 - 支持流式数据"""
        print("🎨 [视窗绘制工具] 启动流式处理...")
        
        # 运行时导入，避免模块加载时触发 Tkinter
        from tools.highlight_renderer import HighlightRenderer
        self.window_renderer = HighlightRenderer.get_instance()
        
        for path, value in extract_leaf_nodes(inputs):
            print(f"📥 收到路径: {path}, 值类型: {type(value)}")
            
            if isinstance(value, AsyncGenerator):
                async for frame in value:
                    print(f"🔍 流式收到匹配结果: {frame}")
                    
                    # 处理输入数据格式
                    processed_data = frame
                    
                    # 处理输入数据的多层嵌套格式
                    if isinstance(frame, dict):
                        # 处理从工作流配置来的input_data字段（当前实际收到的格式）
                        if 'input_data' in frame:
                            input_data = frame['input_data']
                            print(f"📦 提取input_data: {input_data}")
                            
                            # 处理input_data内部的text_matching（当前实际格式）
                            if isinstance(input_data, dict) and 'text_matching' in input_data:
                                text_matching_data = input_data['text_matching']
                                print(f"📦 提取input_data中的text_matching: {text_matching_data}")
                                processed_data = text_matching_data
                            else:
                                processed_data = input_data
                        
                        # 处理直接的text_matching字段（当前实际收到的格式）
                        elif 'text_matching' in frame:
                            text_matching_data = frame['text_matching']
                            print(f"📦 提取text_matching: {text_matching_data}")
                            processed_data = text_matching_data
                        
                        # 处理其他格式
                        else:
                            processed_data = frame
                            print(f"📦 直接使用frame: {frame}")
                    
                    # 从字典中提取正确的索引
                    if isinstance(processed_data, dict):
                        text_idx = processed_data.get("text_idx")
                        img_indices = processed_data.get("img_indices", [])
                        img_coords_map = processed_data.get("img_coords_map", {})
                        match_type = processed_data.get("match_type", "none")

                        # 总是先清除旧的高亮
                        print("🧹 清除之前的高亮")
                        self.window_renderer.clear_all()

                        # 只在有匹配时显示新高亮
                        if match_type != "none":
                            # 高亮文本元素
                            if text_idx is not None:
                                print(f"✅ 高亮文本索引: {text_idx}")
                                self.window_renderer.show_highlight(
                                    text_idx, elem_type="text"
                                )

                            # 高亮图片元素
                            for img_idx in img_indices:
                                if img_idx in img_coords_map:
                                    coords = img_coords_map[img_idx]
                                    print(f"✅ 高亮图片索引: {img_idx}, 坐标: {coords}")
                                    self.window_renderer.show_highlight(
                                        img_idx, elem_type="image", coords=coords
                                    )
                        else:
                            print("❌ 无匹配内容，保持清空状态")
                    else:
                        # 兼容旧格式：直接传索引
                        self.window_renderer.clear_all()
                        self.window_renderer.show_highlight(processed_data)
                    
                    yield {"rendered": True, "matched_data": processed_data}
            else:
                yield {"rendered": True, "data": value}

    async def invoke(self, inputs, runtime, context):
        """执行视窗绘制"""
        print("🎨 [视窗绘制工具] 正在绘制视窗内容...")
        print("🎨 [视窗绘制工具] 功能描述：负责在视窗中绘制图形、图表和用户界面元素")

        # Mock实现：返回模拟的视窗绘制结果
        return {
            "result": {
                "drawing_id": "drawing_202",
                "elements_drawn": ["chart", "text_box", "button"],
                "status": "drawn",
                "render_time_ms": 150,
            },
            "data": {"drawing_result": "模拟的视窗绘制内容"},
        }


# 导出组件
__all__ = ["WindowDrawingComponent"]