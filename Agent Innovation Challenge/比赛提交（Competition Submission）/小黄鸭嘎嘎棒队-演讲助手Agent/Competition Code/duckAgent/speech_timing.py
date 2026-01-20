#!/usr/bin/env python
# coding: utf-8
"""
演讲计时器模块 - 实现Element级演讲节奏管控
包含三个子节点：
1. 前置 - PPT Element 理论时长分配（离线执行）
2. 实时 - Element 计时与低干扰偏差提醒
3. 后置 - 演讲后耗时复盘
"""

import time
import threading
import tkinter as tk
from tkinter import ttk
import re
from typing import Dict, List, Optional, Tuple, Any
import json

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


class ElementTimingManager:
    """子节点1：PPT Element 理论时长分配管理器"""
    
    def __init__(self):
        """初始化"""
        # 默认Element权重字典
        self.default_element_weights = {
            "title": 0.5,
            "core_argument": 1.5,
            "case": 1.0,
            "chart": 0.8,
            "summary": 1.2
        }
        # 默认权重
        self.default_weight = 1.0
        
    def calculate_element_timings(self, elements: List[Dict], total_seconds: int) -> Tuple[List[Dict], Dict]:
        """
        计算PPT Element理论时长
        
        Args:
            elements: PPT Element列表
            total_seconds: 总演讲时长（秒）
            
        Returns:
            Tuple[更新后的Element列表, element_timing_map]
        """
        print(f"⏰ [子节点1] 开始计算Element理论时长，总演讲时长：{total_seconds}秒")
        
        # 计算总加权文字长度
        total_weighted_length = 0
        element_details = []
        
        for element in elements:
            element_id = element.get("element_id")
            element_type = element.get("element_type", "unknown")
            content = element.get("content", "")
            script_paragraph = element.get("script_paragraph", "")
            
            # 获取Element权重
            weight = self.default_element_weights.get(element_type, self.default_weight)
            
            # 统计有效文字长度（过滤标点/空格）
            effective_length = self._count_effective_words(content + " " + script_paragraph)
            
            # 计算加权文字长度
            weighted_length = effective_length * weight
            
            element_detail = {
                "element_id": element_id,
                "element_type": element_type,
                "effective_length": effective_length,
                "weight": weight,
                "weighted_length": weighted_length
            }
            
            element_details.append(element_detail)
            total_weighted_length += weighted_length
        
        # 分配理论时长
        updated_elements = []
        element_timing_map = {}

        
        if total_weighted_length > 0:
            # 按加权文字长度分配
            for element, detail in zip(elements, element_details):
                element_id = detail["element_id"]
                weighted_length = detail["weighted_length"]
                
                # 计算理论时长
                theoretical_seconds = (weighted_length / total_weighted_length) * total_seconds
                theoretical_seconds = max(5, min(300, int(theoretical_seconds)))  # 限制在5-300秒之间
                
                # 更新Element
                updated_element = element.copy()
                updated_element.update({
                    "theoretical_seconds": theoretical_seconds,
                    "theoretical_minutes": round(theoretical_seconds / 60, 2),
                    "weight": detail["weight"],
                    "weighted_length": detail["weighted_length"]
                })
                updated_elements.append(updated_element)
                
                # 更新element_timing_map
                element_timing_map[element_id] = {
                    "theoretical_seconds": theoretical_seconds,
                    "page_num": element.get("page_num", 1),
                    "element_type": detail["element_type"]
                }
        else:
            # 平均分配
            element_count = len(elements)
            if element_count > 0:
                avg_seconds = max(5, int(total_seconds / element_count))
                
                for element in elements:
                    element_id = element.get("element_id")
                    
                    # 更新Element
                    updated_element = element.copy()
                    updated_element.update({
                        "theoretical_seconds": avg_seconds,
                        "theoretical_minutes": round(avg_seconds / 60, 2),
                        "weight": self.default_weight,
                        "weighted_length": 0
                    })
                    updated_elements.append(updated_element)
                    
                    # 更新element_timing_map
                    element_timing_map[element_id] = {
                        "theoretical_seconds": avg_seconds,
                        "page_num": element.get("page_num", 1),
                        "element_type": element.get("element_type", "unknown")
                    }
        
        print(f"⏰ [子节点1] 完成Element理论时长计算，共{len(updated_elements)}个Element")
        for element in updated_elements:  # 只打印前5个
            print(f"  Element {element.get('element_id')}: {element.get('theoretical_seconds')}秒 ({element.get('element_type')})")
        
        return updated_elements, element_timing_map
    
    def _count_effective_words(self, text: str) -> int:
        """
        统计有效文字长度
        
        Args:
            text: 文本内容
            
        Returns:
            有效文字长度
        """
        # 过滤标点、空格和换行符
        filtered_text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', text)
        return len(filtered_text)


class SpeechTimingManager:
    """子节点2：实时Element计时与偏差提醒管理器"""
    
    def __init__(self, element_timing_map: Dict):
        """
        初始化
        
        Args:
            element_timing_map: Element理论时长映射
        """
        self.element_timing_map = element_timing_map
        self.current_element = None
        self.element_start_time = 0
        self.element_actual_time = 0
        self.global_start_time = 0
        self.global_actual_time = 0
        self.is_running = False
        self.is_paused = False
        self.pause_start_time = 0
        self.pause_duration = 0
        self.timing_history = []
        self.last_remind_time = 0
        self.reminder_cooldown = 30  # 30秒内同一Element仅提醒1次
        self.reminder_window = None
        
        # 默认提醒规则
        self.remind_rules = {
            "deviation_threshold": 0.2,  # 20%偏差
            "key_element_types": ["core_argument", "summary"],
            "global_deviation_threshold": 60,  # 60秒全局偏差
            "remind_method": "status_bar",  # 默认状态栏提醒
            "duplicate_remind_interval": 30  # 重复提醒间隔
        }
    
    def start_global_timer(self):
        """开始全局计时器"""
        if not self.is_running:
            self.is_running = True
            self.global_start_time = time.time()
            print("⏰ [子节点2] 全局计时器已启动")
    
    def start_element_timing(self, element_id: str):
        """
        开始Element计时
        
        Args:
            element_id: Element ID
        """
        if not self.is_running:
            self.start_global_timer()
        
        # 停止当前Element计时
        if self.current_element:
            self.stop_element_timing()
        
        self.current_element = element_id
        self.element_start_time = time.time() - self.pause_duration
        print(f"⏰ [子节点2] 开始计时 Element: {element_id}")
    
    def stop_element_timing(self):
        """停止Element计时并记录历史"""
        if not self.current_element:
            return
        
        actual_time = self._get_current_element_time()
        theoretical_time = self.element_timing_map.get(self.current_element, {}).get("theoretical_seconds", 0)
        
        # 计算偏差
        deviation = actual_time - theoretical_time
        deviation_rate = deviation / theoretical_time if theoretical_time > 0 else 0
        
        # 记录历史
        history_record = {
            "element_id": self.current_element,
            "start_time": self.element_start_time,
            "end_time": time.time() - self.pause_duration,
            "actual_seconds": actual_time,
            "theoretical_seconds": theoretical_time,
            "deviation": deviation,
            "deviation_rate": deviation_rate,
            "element_type": self.element_timing_map.get(self.current_element, {}).get("element_type", "unknown"),
            "page_num": self.element_timing_map.get(self.current_element, {}).get("page_num", 1)
        }
        
        self.timing_history.append(history_record)
        print(f"⏰ [子节点2] 停止计时 Element: {self.current_element}, 实际用时: {actual_time:.2f}秒, 理论用时: {theoretical_time}秒, 偏差: {deviation:.2f}秒 ({deviation_rate:.1%})")
        
        # 分析偏差并提醒
        self.analyze_and_remind(self.current_element, actual_time, theoretical_time, deviation_rate)
        
        self.current_element = None
    
    def pause(self):
        """暂停计时"""
        if self.is_running and not self.is_paused:
            self.is_paused = True
            self.pause_start_time = time.time()
            print("⏰ [子节点2] 计时器已暂停")
    
    def resume(self):
        """恢复计时"""
        if self.is_running and self.is_paused:
            self.is_paused = False
            self.pause_duration += time.time() - self.pause_start_time
            print("⏰ [子节点2] 计时器已恢复")
    
    def stop(self):
        """停止计时"""
        self.stop_element_timing()
        self.is_running = False
        self.global_actual_time = time.time() - self.global_start_time - self.pause_duration
        print(f"⏰ [子节点2] 计时器已停止，总用时: {self.global_actual_time:.2f}秒")
    
    def analyze_and_remind(self, element_id: str, actual_time: float, theoretical_time: float, deviation_rate: float):
        """
        分析偏差并提醒
        
        Args:
            element_id: Element ID
            actual_time: 实际用时
            theoretical_time: 理论用时
            deviation_rate: 偏差率
        """
        current_time = time.time()
        
        # 检查是否在冷却期
        if current_time - self.last_remind_time < self.reminder_cooldown:
            return
        
        # 检查提醒条件
        should_remind = False
        reminder_type = "normal"
        
        # 条件1：偏差率 ≥ 20%
        if abs(deviation_rate) >= self.remind_rules["deviation_threshold"]:
            should_remind = True
        
        # 条件2：关键Element偏差率 ≥ 10%
        element_type = self.element_timing_map.get(element_id, {}).get("element_type", "unknown")
        if element_type in self.remind_rules["key_element_types"] and abs(deviation_rate) >= 0.1:
            should_remind = True
        
        # 条件3：全局累计偏差 ≥ 60秒
        global_deviation = self._calculate_global_deviation()
        if abs(global_deviation) >= self.remind_rules["global_deviation_threshold"]:
            should_remind = True
        
        if should_remind:
            self.last_remind_time = current_time
            self._show_reminder(element_id, actual_time, theoretical_time, deviation_rate, global_deviation)
    
    def _get_current_element_time(self) -> float:
        """获取当前Element已用时间"""
        if not self.current_element or not self.element_start_time:
            return 0
        
        if self.is_paused:
            return self.element_start_time - (time.time() - self.pause_start_time)
        
        return time.time() - self.element_start_time - self.pause_duration
    
    def _calculate_global_deviation(self) -> float:
        """计算全局累计偏差"""
        total_deviation = 0
        for record in self.timing_history:
            total_deviation += record["deviation"]
        return total_deviation
    
    def _show_reminder(self, element_id: str, actual_time: float, theoretical_time: float, deviation_rate: float, global_deviation: float):
        """显示提醒"""
        element_info = self.element_timing_map.get(element_id, {})
        page_num = element_info.get("page_num", 1)
        element_type = element_info.get("element_type", "unknown")
        
        # 构建提醒消息
        if deviation_rate > 0:
            message = f"⚠️ 节奏过快\n第{page_num}页 Element {element_id}\n实际: {actual_time:.0f}秒\n理论: {theoretical_time:.0f}秒\n建议: 适当展开内容"
            color = "orange"
        else:
            message = f"⚠️ 节奏过慢\n第{page_num}页 Element {element_id}\n实际: {actual_time:.0f}秒\n理论: {theoretical_time:.0f}秒\n建议: 精简内容"
            color = "blue"
        
        # 显示提醒
        print(f"⏰ [提醒] {message}")
        
        # 偏差率 ≥ 30% 时弹出半透明悬浮窗
        if abs(deviation_rate) >= 0.3:
            self._show_floating_reminder(message, color)
    
    def _show_floating_reminder(self, message: str, color: str):
        """显示浮动提醒窗口"""
        try:
            # 创建独立的提醒窗口
            if self.reminder_window and self.reminder_window.winfo_exists():
                self.reminder_window.destroy()
                
            self.reminder_window = tk.Toplevel()
            self.reminder_window.title("节奏提醒")
            self.reminder_window.geometry("350x180")
            self.reminder_window.attributes("-topmost", True)
            self.reminder_window.attributes("-alpha", 0.8)  # 半透明
            
            # 计算位置（右下角）
            screen_width = self.reminder_window.winfo_screenwidth()
            screen_height = self.reminder_window.winfo_screenheight()
            window_width = 350
            window_height = 180
            x = screen_width - window_width - 20
            y = screen_height - window_height - 20
            self.reminder_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
            # 设置样式
            style = ttk.Style()
            style.configure("TLabel", font=("Arial", 12))
            
            # 添加标签
            label = ttk.Label(self.reminder_window, text=message, font=("Arial", 12))
            label.pack(pady=20)
            label.configure(foreground=color)
            
            # 设置自动关闭
            self.reminder_window.after(3000, lambda: self._close_reminder())
            
        except Exception as e:
            print(f"显示提醒失败: {e}")
    
    def _close_reminder(self):
        """关闭提醒窗口"""
        if self.reminder_window and self.reminder_window.winfo_exists():
            try:
                self.reminder_window.destroy()
            except:
                pass
    
    def get_timing_history(self) -> List[Dict]:
        """获取计时历史"""
        return self.timing_history
    
    def get_current_status(self) -> Dict:
        """获取当前状态"""
        return {
            "current_element": self.current_element,
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "global_actual_time": self.global_actual_time,
            "element_actual_time": self._get_current_element_time(),
            "timing_history_count": len(self.timing_history)
        }


class SpeechReviewManager:
    """子节点3：演讲后耗时复盘管理器"""
    
    def __init__(self, element_timing_map: Dict):
        """
        初始化
        
        Args:
            element_timing_map: Element理论时长映射
        """
        self.element_timing_map = element_timing_map
    
    def generate_review_report(self, timing_history: List[Dict], global_actual_time: float, global_theoretical_time: float) -> Dict:
        """
        生成复盘报告
        
        Args:
            timing_history: 计时历史
            global_actual_time: 全局实际总时长
            global_theoretical_time: 全局理论总时长
            
        Returns:
            复盘报告
        """
        print("⏰ [子节点3] 开始生成演讲耗时复盘报告")
        
        # 统计数据
        slow_count = 0
        fast_count = 0
        normal_count = 0
        core_argument_issues = []
        
        for record in timing_history:
            deviation_rate = record["deviation_rate"]
            
            if abs(deviation_rate) < 0.1:
                normal_count += 1
            elif deviation_rate > 0:
                fast_count += 1
            else:
                slow_count += 1
            
            # 记录核心论点偏差问题
            if record["element_type"] == "core_argument" and abs(deviation_rate) >= 0.2:
                core_argument_issues.append({
                    "element_id": record["element_id"],
                    "page_num": record["page_num"],
                    "deviation_rate": deviation_rate,
                    "actual_seconds": record["actual_seconds"],
                    "theoretical_seconds": record["theoretical_seconds"]
                })
        
        # 计算全局偏差率
        global_deviation = global_actual_time - global_theoretical_time
        global_deviation_rate = global_deviation / global_theoretical_time if global_theoretical_time > 0 else 0
        
        # 生成报告
        report = {
            "summary": {
                "total_elements": len(timing_history),
                "slow_count": slow_count,
                "fast_count": fast_count,
                "normal_count": normal_count,
                "global_actual_time": global_actual_time,
                "global_theoretical_time": global_theoretical_time,
                "global_deviation": global_deviation,
                "global_deviation_rate": global_deviation_rate,
                "core_argument_issues_count": len(core_argument_issues)
            },
            "element_timing_details": timing_history,
            "core_argument_issues": core_argument_issues,
            "optimization_suggestions": self._generate_suggestions(slow_count, fast_count, core_argument_issues),
            "visualization_data": self._generate_visualization_data(timing_history)
        }
        
        # 打印报告摘要
        print("⏰ [子节点3] 复盘报告生成完成")
        print(f"  总Element数: {len(timing_history)}")
        print(f"  节奏正常: {normal_count}, 过快: {fast_count}, 过慢: {slow_count}")
        print(f"  全局实际用时: {global_actual_time:.2f}秒")
        print(f"  全局理论用时: {global_theoretical_time:.2f}秒")
        print(f"  全局偏差: {global_deviation:.2f}秒 ({global_deviation_rate:.1%})")
        print(f"  核心论点问题: {len(core_argument_issues)}个")
        
        return report
    
    def _generate_suggestions(self, slow_count: int, fast_count: int, core_argument_issues: List[Dict]) -> List[str]:
        """生成优化建议"""
        suggestions = []
        
        if slow_count > fast_count:
            suggestions.append("整体节奏偏慢，建议：1. 精简次要内容 2. 提高语速 3. 减少口头禅")
        elif fast_count > slow_count:
            suggestions.append("整体节奏偏快，建议：1. 适当展开核心内容 2. 增加停顿 3. 观察听众反应")
        
        if core_argument_issues:
            suggestions.append("核心论点讲解时间偏差较大，建议：1. 提前准备核心论点内容 2. 练习核心论点的时间控制 3. 使用提示卡辅助")
        
        if not suggestions:
            suggestions.append("整体节奏控制良好，建议：1. 保持当前演讲风格 2. 注意与听众互动 3. 灵活调整语速")
        
        return suggestions
    
    def _generate_visualization_data(self, timing_history: List[Dict]) -> Dict:
        """生成可视化数据"""
        element_ids = []
        actual_times = []
        theoretical_times = []
        deviations = []
        
        for record in timing_history:
            element_ids.append(record["element_id"])
            actual_times.append(record["actual_seconds"])
            theoretical_times.append(record["theoretical_seconds"])
            deviations.append(record["deviation"])
        
        return {
            "element_ids": element_ids,
            "actual_times": actual_times,
            "theoretical_times": theoretical_times,
            "deviations": deviations
        }


class SpeechTimingComponent(WorkflowComponent, ComponentExecutable):
    """演讲计时器组件 - 标准OpenJiuwen工作流组件"""
    
    def to_executable(self) -> ComponentExecutable:
        return self

    async def collect(
        self, inputs: Input, runtime: Runtime, context: Context
    ) -> Output:
        print("⏰ [计时器] 执行收集操作...")
        print("⏰ [计时器] 功能描述：负责管理演讲过程中的计时和节奏分析")

        chunks = []

        for path, value in extract_leaf_nodes(inputs):
            if isinstance(value, AsyncGenerator):
                async for frame in value:
                    print(f"⏰ 收到计时器更新: {frame}")
                    chunks.append({format_path(path): frame})
            else:
                chunks.append({format_path(path): value})
        logger.debug(f"collect chunks: {chunks}")
        print(chunks)
        return {"collect_output": chunks}

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        """执行计时器操作"""
        print("⏰ [计时器] 执行操作...")
        
        # 解析输入参数
        input_data = inputs if isinstance(inputs, dict) else {}
        action = input_data.get("action", "init")
        
        print(f"⏰ [计时器] 收到操作: {action}")
        
        # 初始化组件
        if not hasattr(self, 'element_timing_manager'):
            self.element_timing_manager = ElementTimingManager()
            self.speech_timing_manager = None
            self.speech_review_manager = None
        
        # 执行操作
        if action == "init":
            # 初始化 - 计算Element理论时长
            elements = input_data.get("elements", [])
            total_seconds = input_data.get("total_seconds", 300)  # 默认5分钟（300秒）
            
            updated_elements, element_timing_map = self.element_timing_manager.calculate_element_timings(elements, total_seconds)
            
            # 初始化实时计时器和复盘管理器
            self.speech_timing_manager = SpeechTimingManager(element_timing_map)
            self.speech_review_manager = SpeechReviewManager(element_timing_map)
            
            return {
                "updated_elements": updated_elements,
                "element_timing_map": element_timing_map,
                "status": "initialized"
            }
            
        elif action == "start_element":
            # 开始Element计时
            element_id = input_data.get("element_id")
            if self.speech_timing_manager:
                self.speech_timing_manager.start_element_timing(element_id)
                status = self.speech_timing_manager.get_current_status()
                return {
                    "status": "element_started",
                    "current_status": status
                }
            
        elif action == "stop_element":
            # 停止Element计时
            if self.speech_timing_manager:
                self.speech_timing_manager.stop_element_timing()
                status = self.speech_timing_manager.get_current_status()
                return {
                    "status": "element_stopped",
                    "current_status": status
                }
            
        elif action == "pause":
            # 暂停计时
            if self.speech_timing_manager:
                self.speech_timing_manager.pause()
                status = self.speech_timing_manager.get_current_status()
                return {
                    "status": "paused",
                    "current_status": status
                }
            
        elif action == "resume":
            # 恢复计时
            if self.speech_timing_manager:
                self.speech_timing_manager.resume()
                status = self.speech_timing_manager.get_current_status()
                return {
                    "status": "resumed",
                    "current_status": status
                }
            
        elif action == "stop":
            # 停止计时
            if self.speech_timing_manager:
                self.speech_timing_manager.stop()
                status = self.speech_timing_manager.get_current_status()
                return {
                    "status": "stopped",
                    "current_status": status
                }
            
        elif action == "generate_review":
            # 生成复盘报告
            if self.speech_timing_manager and self.speech_review_manager:
                timing_history = self.speech_timing_manager.get_timing_history()
                global_actual_time = self.speech_timing_manager.global_actual_time
                
                # 计算全局理论总时长
                global_theoretical_time = sum(info.get("theoretical_seconds", 0) for info in self.speech_timing_manager.element_timing_map.values())
                
                review_report = self.speech_review_manager.generate_review_report(
                    timing_history, global_actual_time, global_theoretical_time
                )
                
                return {
                    "status": "review_generated",
                    "review_report": review_report
                }
        
        # 返回默认状态
        return {
            "status": "idle"
        }
        
    async def transform(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        """流式处理接口"""
        print("⏰ [计时器] 启动流式处理...")
        
        # 解析输入
        input_data = inputs if isinstance(inputs, dict) else {}
        action = input_data.get("action", "start")
        
        # 流式返回时间更新
        if hasattr(self, 'speech_timing_manager') and self.speech_timing_manager and self.speech_timing_manager.is_running:
            while self.speech_timing_manager.is_running:
                status = self.speech_timing_manager.get_current_status()
                yield {
                    "status": "running",
                    "current_status": status
                }
                await asyncio.sleep(1.0)  # 每秒更新一次
        
        # 返回最终状态
        yield {
            "status": "completed"
        }

    def __init__(self):
        """初始化计时器组件"""
        super().__init__()
        self.element_timing_manager = ElementTimingManager()
        self.speech_timing_manager = None
        self.speech_review_manager = None


# 导出组件
__all__ = [
    "ElementTimingManager",
    "SpeechTimingManager",
    "SpeechReviewManager",
    "SpeechTimingComponent"
]