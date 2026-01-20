#!/usr/bin/env python
# coding: utf-8
"""
视窗初始化工具 - 最终修复版
"""

from openjiuwen.core.component.base import WorkflowComponent
from openjiuwen.core.runtime.base import ComponentExecutable
from openjiuwen.core.runtime.base import Input
from openjiuwen.core.runtime.base import Output as OutputType
from openjiuwen.core.context_engine.base import Context

# 延迟导入：避免在子线程触发 Tkinter
# from tools.highlight_renderer import HighlightRenderer
from tools.element_matcher import ElementMatcher
import threading
import queue


class WindowInitComponent(WorkflowComponent, ComponentExecutable):
    """视窗初始化组件 - 最终修复版"""

    async def invoke(self, inputs, runtime, context):
        """执行视窗初始化（完全无阻塞）"""
        print("🔧 [视窗初始化工具] 正在初始化应用视窗...")
        print("🔧 [视窗初始化工具] 功能描述：负责创建应用主窗口、设置布局和窗口属性")

        # 运行时导入，避免模块加载时触发 Tkinter
        from tools.highlight_renderer import HighlightRenderer

        ppt_parsed_elements = inputs["input_data"]
        elem_coords = ppt_parsed_elements.get_elem_coords()
        elem_texts = ppt_parsed_elements.get_elem_texts()

        # 核心修复：统一通过get_instance初始化，自动处理线程问题
        try:
            self.renderer = HighlightRenderer.get_instance()
            self.renderer.set_elem_coords(elem_coords)
            ElementMatcher.init_data(elem_texts=elem_texts, match_threshold=0.3)
            print("🔧 [视窗初始化工具] Renderer参数初始化成功")
        except Exception as e:
            print(f"🔧 [视窗初始化工具] Renderer参数初始化失败：{e}")
            raise

        # Mock实现：立即返回，不阻塞
        return {}


# 导出组件
__all__ = ["WindowInitComponent"]
