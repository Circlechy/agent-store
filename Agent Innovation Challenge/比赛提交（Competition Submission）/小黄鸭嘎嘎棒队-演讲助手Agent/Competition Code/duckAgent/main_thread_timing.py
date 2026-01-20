#!/usr/bin/env python
# coding: utf-8
"""
Main-thread controlled timing module - 实现Element级演讲节奏管控
由主线程控制计时，定期检查当前Element耗时与期望耗时的比较，给出节奏提醒
"""

import time
import threading
import tkinter as tk
from typing import Dict, List, Optional, Tuple, Any

from openjiuwen.core.component.base import WorkflowComponent
from openjiuwen.core.runtime.base import ComponentExecutable
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.common.utlis.dict_utils import extract_leaf_nodes, format_path
from openjiuwen.core.common.logging import logger
from typing import AsyncIterator, TypedDict, Union, AsyncGenerator
from openjiuwen.core.runtime.constants import (
    END_COMP_TEMPLATE_RENDER_POSITION_TIMEOUT_KEY,
    END_COMP_TEMPLATE_BATCH_READER_TIMEOUT_KEY,
)
from openjiuwen.core.graph.executable import Input, Output
from openjiuwen.core.runtime.runtime import Runtime


class MainThreadTimingManager:
    """主线程控制的计时管理器"""
    
    _instance = None
    _instance_lock = threading.Lock()
    
    @classmethod
    def get_instance(cls) -> "MainThreadTimingManager":
        """获取单例实例"""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance
    
    def __init__(self):
        """初始化计时管理器"""
        self.start_time = 0
        self.is_running = False
        self.current_element = None
        self.element_start_time = 0
        self.element_timing_map = {}
        self.element_matcher = None
        self.highlight_renderer = None
        self.check_interval = 2  # 检查间隔（秒）
        self.last_check_time = 0
        
        # 默认提醒规则
        self.remind_rules = {
            "deviation_threshold": 0.2,  # 20%偏差
            "key_element_types": ["core_argument", "summary"],
            "remind_cooldown": 30  # 30秒内同一Element仅提醒1次
        }
        
        self.last_remind_time = 0
        self.reminder_window = None
    
    def initialize(self, element_timing_map: Dict, highlight_renderer):
        """初始化管理器"""
        self.element_timing_map = element_timing_map
        self.highlight_renderer = highlight_renderer
        print("⏰ [MainThreadTimingManager] 已初始化")
    
    def start_timing(self):
        """开始全局计时"""
        if not self.is_running:
            self.start_time = time.time()
            self.is_running = True
            self.last_check_time = self.start_time
            print("⏰ [MainThreadTimingManager] 全局计时已启动")
    
    def update_current_element(self, element_id: str):
        """更新当前Element并开始计时"""
        if not self.is_running:
            self.start_timing()
        
        # 检查当前Element的时间
        if self.current_element:
            self._check_element_timing()
        
        # 更新为新Element
        self.current_element = element_id
        self.element_start_time = time.time()
        print(f"⏰ [MainThreadTimingManager] 当前Element更新为: {element_id}")
        
        # 获取Element的理论时长
        element_info = self.element_timing_map.get(element_id, {})
        theoretical_time = element_info.get("theoretical_seconds", 0)
        if theoretical_time > 0:
            print(f"⏰ [MainThreadTimingManager] 理论时长: {theoretical_time}秒")
    
    def _check_element_timing(self):
        """检查当前Element的计时"""
        if not self.current_element:
            return
        
        current_time = time.time()
        element_elapsed = current_time - self.element_start_time
        total_elapsed = current_time - self.start_time
        
        # 获取Element的理论时长
        element_info = self.element_timing_map.get(self.current_element, {})
        theoretical_time = element_info.get("theoretical_seconds", 0)
        element_type = element_info.get("element_type", "unknown")
        
        if theoretical_time > 0:
            # 计算偏差
            deviation = element_elapsed - theoretical_time
            deviation_rate = deviation / theoretical_time
            
            print(f"⏰ [MainThreadTimingManager] Element {self.current_element}:")
            print(f"   实际用时: {element_elapsed:.2f}秒")
            print(f"   理论用时: {theoretical_time}秒")
            print(f"   偏差: {deviation:.2f}秒 ({deviation_rate:.1%})")
            
            # 检查是否需要提醒
            self._check_and_remind(self.current_element, element_elapsed, 
                                  theoretical_time, deviation_rate, element_type)
        
        # 更新显示
        if self.highlight_renderer:
            self._update_timing_display(total_elapsed, element_elapsed, 
                                      theoretical_time if theoretical_time > 0 else None)
    
    def _check_and_remind(self, element_id: str, actual_time: float, 
                         theoretical_time: float, deviation_rate: float, 
                         element_type: str):
        """检查并生成提醒"""
        current_time = time.time()
        
        # 检查冷却期
        if current_time - self.last_remind_time < self.remind_rules["remind_cooldown"]:
            return
        
        # 检查提醒条件
        should_remind = False
        reminder_message = ""
        
        # 条件1：偏差率 ≥ 20%
        if abs(deviation_rate) >= self.remind_rules["deviation_threshold"]:
            should_remind = True
        
        # 条件2：关键Element偏差率 ≥ 10%
        if element_type in self.remind_rules["key_element_types"] and abs(deviation_rate) >= 0.1:
            should_remind = True
        
        if should_remind:
            self.last_remind_time = current_time
            
            if deviation_rate < 0:
                reminder_message = f"⚠️ 节奏过快\nElement {element_id}\n实际: {actual_time:.0f}秒\n理论: {theoretical_time:.0f}秒\n建议: 适当展开内容"
            else:
                reminder_message = f"⚠️ 节奏过慢\nElement {element_id}\n实际: {actual_time:.0f}秒\n理论: {theoretical_time:.0f}秒\n建议: 精简内容"
            
            print(f"⏰ [提醒] {reminder_message}")
            
            # 显示提醒
            if self.highlight_renderer:
                self._show_reminder(reminder_message)
    
    def _update_timing_display(self, total_elapsed: float, element_elapsed: float, 
                              theoretical_time: Optional[float]):
        """更新计时显示"""
        if not self.highlight_renderer:
            return
        
        # 格式化时间
        total_str = self._format_time(total_elapsed)
        element_str = self._format_time(element_elapsed)
        
        display_text = f"总用时: {total_str}"
        # if theoretical_time is not None:
        #     theoretical_str = self._format_time(theoretical_time)
        #     display_text += f"\n当前Element: {element_str}/{theoretical_str}"
        
        # 通过队列发送到渲染器
        try:
            self.highlight_renderer.ui_queue.put(("update_timing", (display_text,)), timeout=0.01)
        except Exception as e:
            print(f"⏰ [MainThreadTimingManager] 更新计时显示失败: {e}")
    
    def _show_reminder(self, message: str):
        """显示提醒窗口"""
        if not self.highlight_renderer:
            return
        
        try:
            self.highlight_renderer.ui_queue.put(("show_reminder", (message,)), timeout=0.01)
        except Exception as e:
            print(f"⏰ [MainThreadTimingManager] 显示提醒失败: {e}")
    
    def _format_time(self, seconds: float) -> str:
        """格式化时间为 mm:ss"""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"
    
    def get_elapsed_time(self) -> float:
        """获取已用时间"""
        if not self.is_running:
            return 0.0
        return time.time() - self.start_time
    
    def stop_timing(self):
        """停止计时"""
        if self.is_running:
            self.is_running = False
            print("⏰ [MainThreadTimingManager] 计时已停止")
    
    def check_timing(self):
        """手动检查计时（由主线程定期调用）"""
        if not self.is_running:
            return
        
        current_time = time.time()
        if current_time - self.last_check_time >= self.check_interval:
            self._check_element_timing()
            self.last_check_time = current_time


class TimingDisplayComponent(WorkflowComponent, ComponentExecutable):
    """计时显示组件"""
    
    def to_executable(self) -> ComponentExecutable:
        return self
    
    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        """执行计时显示"""
        print("⏰ [计时显示组件] 执行操作...")
        
        # 解析输入参数
        input_data = inputs if isinstance(inputs, dict) else {}
        action = input_data.get("action", "update")
        
        # 获取MainThreadTimingManager实例
        timing_manager = MainThreadTimingManager.get_instance()
        
        if action == "update":
            # 更新计时
            element_id = input_data.get("element_id")
            if element_id:
                timing_manager.update_current_element(element_id)
        
        elif action == "check":
            # 检查计时
            timing_manager.check_timing()
        
        elif action == "start":
            # 开始计时
            timing_manager.start_timing()
        
        elif action == "stop":
            # 停止计时
            timing_manager.stop_timing()
        
        # 返回当前状态
        return {
            "status": "running" if timing_manager.is_running else "stopped",
            "elapsed_time": timing_manager.get_elapsed_time()
        }