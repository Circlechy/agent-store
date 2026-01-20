# -*- coding: utf-8 -*-
"""
工作总结Agent适配器

将旧的WorkSummaryAgent接口适配到新的WorkSummaryWorkflowAgent
保持向后兼容
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pathlib import Path
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo
from openjiuwen.core.common.logging import logger
import os
import json
import asyncio
import threading
from dataclasses import dataclass

# 导入新的WorkflowAgent
from backend.agent.work_summary_workflow_agent import WorkSummaryWorkflowAgent
from backend.input_processor import InputType
from backend.screen_capture import ScreenCapture, get_screen_capture

# 工作记录存储目录
_current_file = Path(__file__).resolve()
WORK_RECORDS_DIR = _current_file.parent.parent / "work_records"
WORK_RECORDS_DIR.mkdir(exist_ok=True)


@dataclass
class ScreenshotTask:
    """截图处理任务"""
    file_path: str
    timestamp: str
    captured_at: datetime


class WorkSummaryAgentAdapter:
    """
    工作总结Agent适配器
    
    实现与旧WorkSummaryAgent相同的接口，但内部使用新的WorkSummaryWorkflowAgent
    """
    
    def __init__(self, 
                 model_config: Optional[ModelConfig] = None,
                 image_processing_mode: str = "ocr",
                 enable_auto_screenshot: bool = False,
                 screenshot_interval: int = 5):
        """
        初始化适配器
        
        Args:
            model_config: LLM模型配置（可选）
            image_processing_mode: 图片处理模式 ("ocr", "multimodal", "both", 默认"ocr")
            enable_auto_screenshot: 是否启用自动截图（默认False）
            screenshot_interval: 自动截图间隔（秒，默认5秒）
        """
        # 如果没有提供model_config，创建默认配置
        if not model_config:
            api_key = os.getenv("API_KEY", "")
            api_base = os.getenv("API_BASE", "https://api.modelarts-maas.com/openai/v1")
            model = os.getenv("MODEL_NAME", "deepseek-v3.2-exp")
            
            model_config = ModelConfig(
                model_provider="openai",
                model_info=BaseModelInfo(
                    model=model,
                    api_base=api_base,
                    api_key=api_key,
                    temperature=0.7,
                    top_p=0.9,
                    timeout=120,
                ),
            )
        
        # 创建新的WorkflowAgent
        self.workflow_agent = WorkSummaryWorkflowAgent(
            model_config=model_config,
            image_processing_mode=image_processing_mode
        )
        
        self.screen_capture = get_screen_capture()
        self._auto_screenshot_enabled = False
        self._processing_screenshots = 0  # 正在处理的截图数量
        self._processed_screenshots = 0  # 已处理完成的截图数量
        
        # 截图处理队列
        self._screenshot_queue: Optional[asyncio.Queue] = None
        self._queue_processor_thread: Optional[threading.Thread] = None  # 队列处理线程
        self._queue_processor_loop: Optional[asyncio.AbstractEventLoop] = None  # 队列处理事件循环
        self._queue_processor_running = False  # 队列处理是否在运行
        self._current_processing_task: Optional[ScreenshotTask] = None  # 当前正在处理的任务
        
        # 如果启用自动截图，设置回调函数
        if enable_auto_screenshot:
            self.start_auto_screenshot(screenshot_interval)
    
    def save_work_record(self, date: str, content: Dict[str, Any], timestamp: Optional[str] = None, merge_similar: bool = True, time_window_seconds: int = 30) -> bool:
        """
        保存工作记录（兼容旧接口）
        
        Args:
            date: 日期
            content: 内容
            timestamp: 时间戳（可选）
            merge_similar: 是否合并相似记录（默认True）
            time_window_seconds: 时间窗口（秒），在此时间内的记录会自动合并（默认60秒）
        """
        record_file = WORK_RECORDS_DIR / f"{date}.json"
        
        # 读取现有记录
        records = []
        if record_file.exists():
            try:
                with open(record_file, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except:
                records = []
        
        # 获取时间戳，统一使用带 'Z' 的 UTC 时间戳格式（与前端保持一致）
        if timestamp:
            new_timestamp = timestamp
        else:
            # 生成带 'Z' 的 UTC 时间戳（与前端 toISOString() 格式一致）
            new_timestamp = datetime.utcnow().isoformat() + 'Z'
        
        # 如果启用合并，尝试合并
        if merge_similar and records:
            # 优先检查时间窗口：1分钟内的记录直接合并
            merged = self._try_merge_by_time_window(records, content, new_timestamp, time_window_seconds)
            if merged:
                logger.info(f"检测到时间窗口内的记录（{time_window_seconds}秒内），已合并到现有记录中（日期: {date}）")
                records = merged
            else:
                # 时间窗口内没有记录，再检查内容相似度
                merged = self._try_merge_similar_record(records, content, new_timestamp)
                if merged:
                    logger.info(f"检测到相似内容，已合并到现有记录中（日期: {date}）")
                    records = merged
                else:
                    new_record = {
                        "timestamp": new_timestamp,
                        "content": content
                    }
                    records.append(new_record)
        else:
            new_record = {
                "timestamp": new_timestamp,
                "content": content
            }
            records.append(new_record)
        
        # 保存到文件
        with open(record_file, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        
        return True
    
    def delete_work_record(self, date: str, timestamp: str) -> bool:
        """删除工作记录（兼容旧接口）"""
        record_file = WORK_RECORDS_DIR / f"{date}.json"
        
        if not record_file.exists():
            return False
        
        try:
            with open(record_file, "r", encoding="utf-8") as f:
                records = json.load(f)
            
            original_count = len(records)
            records = [r for r in records if r.get("timestamp") != timestamp]
            
            if len(records) == original_count:
                return False
            
            with open(record_file, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已删除记录（日期: {date}, 时间戳: {timestamp}）")
            return True
        except Exception as e:
            logger.error(f"删除记录失败: {e}", exc_info=True)
            return False
    
    def clear_day_records(self, date: str) -> bool:
        """
        清空指定日期的所有工作记录
        
        Args:
            date: 日期（格式: YYYY-MM-DD）
            
        Returns:
            是否成功清空（如果文件不存在也返回True）
        """
        record_file = WORK_RECORDS_DIR / f"{date}.json"
        
        if not record_file.exists():
            logger.info(f"[清空] 记录文件不存在: {record_file}，无需清空")
            return True
        
        try:
            # 删除文件
            record_file.unlink()
            logger.info(f"[清空] 成功清空日期 {date} 的所有记录")
            return True
        except Exception as e:
            logger.error(f"[清空] 清空记录失败: {e}", exc_info=True)
            return False
    
    def update_work_record(self, date: str, timestamp: str, content: Dict[str, Any]) -> bool:
        """更新工作记录（兼容旧接口）"""
        record_file = WORK_RECORDS_DIR / f"{date}.json"
        
        if not record_file.exists():
            return False
        
        try:
            with open(record_file, "r", encoding="utf-8") as f:
                records = json.load(f)
            
            found = False
            for record in records:
                if record.get("timestamp") == timestamp:
                    record["content"] = content
                    found = True
                    break
            
            if not found:
                return False
            
            with open(record_file, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已更新记录（日期: {date}, 时间戳: {timestamp}）")
            return True
        except Exception as e:
            logger.error(f"更新记录失败: {e}", exc_info=True)
            return False
    
    def get_work_records(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """获取工作记录（兼容旧接口）"""
        from datetime import timedelta
        all_records = []
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        current = start
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            record_file = WORK_RECORDS_DIR / f"{date_str}.json"
            
            if record_file.exists():
                try:
                    with open(record_file, "r", encoding="utf-8") as f:
                        day_records = json.load(f)
                        all_records.extend(day_records)
                except Exception as e:
                    print(f"读取 {date_str} 的记录失败: {e}")
            
            current += timedelta(days=1)
        
        return all_records
    
    async def add_text_record(self, text: str, date: Optional[str] = None, timestamp: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """添加文字工作记录（使用新的工作流）"""
        result = await self.workflow_agent.invoke_record_input(
            content=text,
            input_type="text",
            date=date,
            timestamp=timestamp,
            **kwargs
        )
        
        # 转换结果格式以兼容旧接口
        return self._convert_workflow_result(result)
    
    async def add_document_record(self, file_path: str, date: Optional[str] = None, timestamp: Optional[str] = None, additional_text: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """添加文档工作记录（使用新的工作流）"""
        result = await self.workflow_agent.invoke_record_input(
            input_type="document",
            file_path=file_path,
            date=date,
            timestamp=timestamp,
            additional_text=additional_text or "",
            **kwargs
        )
        
        return self._convert_workflow_result(result)
    
    async def add_image_record(self, file_path: str, date: Optional[str] = None, timestamp: Optional[str] = None, image_processing_mode: Optional[str] = None, is_auto_screenshot: bool = False, additional_text: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """添加图片工作记录（使用新的工作流）"""
        result = await self.workflow_agent.invoke_record_input(
            input_type="image",
            file_path=file_path,
            date=date,
            timestamp=timestamp,
            image_processing_mode=image_processing_mode,
            is_auto_screenshot=is_auto_screenshot,
            additional_text=additional_text or "",
            **kwargs
        )
        
        return self._convert_workflow_result(result)
    
    async def add_work_record(self, input_type: InputType, content: str, file_path: Optional[str] = None, date: Optional[str] = None, timestamp: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """添加工作记录（通用方法，使用新的工作流）"""
        input_type_str = input_type.value if hasattr(input_type, 'value') else str(input_type)
        
        if input_type_str == "text":
            return await self.add_text_record(content, date=date, timestamp=timestamp, **kwargs)
        elif input_type_str == "document":
            return await self.add_document_record(file_path or content, date=date, timestamp=timestamp, **kwargs)
        elif input_type_str == "image":
            return await self.add_image_record(file_path or content, date=date, timestamp=timestamp, **kwargs)
        else:
            raise ValueError(f"不支持的输入类型: {input_type_str}")
    
    async def summarize_day_records(self, date: Optional[str] = None, use_llm: bool = True) -> Dict[str, Any]:
        """汇总一天的所有记录（使用新的工作流）"""
        date_str = date or datetime.now().strftime("%Y-%m-%d")
        result = await self.workflow_agent.invoke_report_generation(
            start_date=date_str,
            end_date=date_str
        )
        
        return self._convert_report_result(result)
    
    async def summarize_date_range(self, start_date: str, end_date: str, use_llm: bool = True) -> Dict[str, Any]:
        """汇总指定日期范围内的所有记录（使用新的工作流）"""
        result = await self.workflow_agent.invoke_report_generation(
            start_date=start_date,
            end_date=end_date
        )
        
        return self._convert_report_result(result)
    
    async def capture_and_analyze(self, date: Optional[str] = None, timestamp: Optional[str] = None, check_diff: bool = False, **kwargs) -> Dict[str, Any]:
        """截取屏幕并自动分析记录（使用新的工作流）"""
        from backend.screen_capture import get_screen_capture
        
        screen_capture = get_screen_capture()
        screenshot_path = screen_capture.capture_screen()
        
        if not screenshot_path or not Path(screenshot_path).exists():
            return {
                "success": False,
                "error": "截图失败"
            }
        
        # 使用新的工作流处理截图
        result = await self.workflow_agent.invoke_record_input(
            input_type="image",
            file_path=screenshot_path,
            date=date,
            timestamp=timestamp,
            is_auto_screenshot=True,
            **kwargs
        )
        
        return {
            "success": True,
            "screenshot_path": screenshot_path,
            **self._convert_workflow_result(result)
        }
    
    def start_auto_screenshot(self, interval: int = 5):
        """启动自动截图"""
        if self._auto_screenshot_enabled:
            logger.warning("自动截图已在运行中")
            return
        
        # 初始化队列和启动队列处理线程
        if self._screenshot_queue is None:
            self._screenshot_queue = asyncio.Queue()
            self._start_queue_processor()
            logger.info("截图处理队列已初始化")
        
        self._auto_screenshot_enabled = True
        self.screen_capture.start_auto_capture(
            interval=interval,
            callback=self._on_screenshot_captured
        )
    
    def stop_auto_screenshot(self):
        """停止自动截图"""
        self._auto_screenshot_enabled = False
        self.screen_capture.stop_auto_capture()
        
        # 注意：不停止队列处理线程，让它继续处理队列中剩余的截图
        # 队列处理线程会在队列为空且没有新截图时自动停止（通过超时机制）
        logger.info("自动截图已停止，队列处理将继续运行直到队列为空")
    
    def is_auto_screenshot_running(self) -> bool:
        """检查自动截图是否正在运行"""
        return self.screen_capture.is_auto_capture_running()
    
    def get_screenshot_interval(self) -> Optional[int]:
        """获取截图间隔"""
        return self.screen_capture.get_auto_capture_interval()
    
    def get_screenshot_stats(self) -> Dict[str, Any]:
        """
        获取截图统计信息
        
        Returns:
            统计信息字典：
                - total_captured: 本次会话已截图总数
                - processing: 正在处理的截图数量
                - processed: 已处理完成的截图数量
                - session_duration: 本次会话持续时间（秒）
        """
        screen_stats = self.screen_capture.get_screenshot_stats()
        queue_size = self._screenshot_queue.qsize() if self._screenshot_queue else 0
        current_processing = None
        if self._current_processing_task:
            current_processing = Path(self._current_processing_task.file_path).name
        
        return {
            "total_captured": screen_stats["total_count"],
            "processing": self._processing_screenshots,
            "processed": self._processed_screenshots,
            "queue_size": queue_size,
            "current_processing": current_processing,
            "session_duration": screen_stats["session_duration"]
        }
    
    async def consolidate_day_records(self, date: str, similarity_threshold: float = 0.2) -> int:
        """
        整合指定日期的相似记录（使用LLM分析）
        
        Args:
            date: 日期（格式: YYYY-MM-DD）
            similarity_threshold: 相似度阈值（暂未使用，保留兼容性）
            
        Returns:
            减少的记录数量
        """
        logger.info(f"[整合] 开始整合日期 {date} 的记录")
        record_file = WORK_RECORDS_DIR / f"{date}.json"
        
        if not record_file.exists():
            logger.info(f"[整合] 记录文件不存在: {record_file}")
            return 0
        
        try:
            # 读取记录
            with open(record_file, "r", encoding="utf-8") as f:
                records = json.load(f)
            
            if len(records) <= 1:
                logger.info(f"[整合] 日期 {date} 只有 {len(records)} 条记录，无需整合")
                return 0
            
            original_count = len(records)
            logger.info(f"[整合] 开始整合日期 {date} 的记录，共 {original_count} 条")
            
            # 格式化记录供LLM分析
            formatted_text = self._format_records_for_consolidation(records)
            logger.info(f"[整合] 格式化完成，文本长度: {len(formatted_text)}")
            
            # 使用LLM分析并生成合并方案
            logger.info(f"[整合] 开始调用LLM分析...")
            consolidation_plan = await self._analyze_consolidation_with_llm(formatted_text)
            logger.info(f"[整合] LLM分析完成，结果: {consolidation_plan}")
            
            if not consolidation_plan or not consolidation_plan.get("groups"):
                logger.info(f"[整合] LLM分析结果：无需合并记录")
                return 0
            
            # 执行合并
            logger.info(f"[整合] 开始执行合并方案...")
            merged_records = self._apply_consolidation_plan(records, consolidation_plan)
            
            # 保存合并后的记录
            with open(record_file, "w", encoding="utf-8") as f:
                json.dump(merged_records, f, ensure_ascii=False, indent=2)
            
            reduced_count = original_count - len(merged_records)
            logger.info(f"[整合] 整合完成：从 {original_count} 条记录减少到 {len(merged_records)} 条，减少了 {reduced_count} 条")
            
            return reduced_count
            
        except Exception as e:
            logger.error(f"[整合] 整合记录失败: {e}", exc_info=True)
            raise  # 重新抛出异常，让上层处理
    
    def _format_records_for_consolidation(self, records: List[Dict[str, Any]]) -> str:
        """格式化记录供LLM分析"""
        parts = []
        parts.append(f"共 {len(records)} 条工作记录\n")
        parts.append("=" * 60 + "\n\n")
        
        for i, record in enumerate(records):
            content = record.get("content", {})
            timestamp = record.get("timestamp", "")
            
            parts.append(f"## 记录 {i}\n")
            parts.append(f"时间戳: {timestamp}\n\n")
            
            parts.append(f"**内容类型:** {content.get('content_type', 'own_work')}\n\n")
            
            if content.get("tasks"):
                parts.append(f"**任务/项目：**\n")
                for task in content["tasks"]:
                    parts.append(f"- {task}\n")
                parts.append("\n")
            
            if content.get("work_content"):
                parts.append(f"**工作内容：**\n{content['work_content']}\n\n")
            
            if content.get("achievements"):
                parts.append(f"**成果：**\n")
                for ach in content["achievements"]:
                    if isinstance(ach, dict):
                        title = ach.get("title", "")
                        desc = ach.get("description", "")
                        if title and desc:
                            parts.append(f"- {title}: {desc}\n")
                        elif title:
                            parts.append(f"- {title}\n")
                    else:
                        parts.append(f"- {ach}\n")
                parts.append("\n")
            
            if content.get("issues"):
                parts.append(f"**问题：**\n")
                for issue in content["issues"]:
                    parts.append(f"- {issue}\n")
                parts.append("\n")
            
            if content.get("next_steps"):
                parts.append(f"**下一步：**\n")
                for step in content["next_steps"]:
                    parts.append(f"- {step}\n")
                parts.append("\n")
            
            parts.append("-" * 40 + "\n\n")
        
        return "".join(parts)
    
    async def _analyze_consolidation_with_llm(self, formatted_records: str) -> Optional[Dict[str, Any]]:
        """使用LLM分析记录并生成合并方案"""
        try:
            from openjiuwen.core.component.llm_comp import LLMComponent, LLMCompConfig
            from backend.prompts.prompt_loader import load_combined_prompt
            
            # 加载prompt
            system_prompt, user_prompt_template = load_combined_prompt("consolidation/merge.txt")
            user_prompt = user_prompt_template.replace("{{formatted_records}}", formatted_records)
            
            # 创建LLM配置
            llm_config = LLMCompConfig(
                model=self.workflow_agent.model_config,
                template_content=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json"},
                output_config={
                    "groups": {
                        "type": "array",
                        "description": "合并组列表",
                        "items": {
                            "type": "object",
                            "properties": {
                                "record_indices": {
                                    "type": "array",
                                    "description": "要合并的记录索引（从0开始）",
                                    "items": {"type": "integer"}
                                },
                                "merged_content": {
                                    "type": "object",
                                    "description": "合并后的内容",
                                    "properties": {
                                        "content_type": {"type": "string"},
                                        "tasks": {"type": "array", "items": {"type": "string"}},
                                        "work_content": {"type": "string"},
                                        "achievements": {"type": "array"},
                                        "issues": {"type": "array", "items": {"type": "string"}},
                                        "next_steps": {"type": "array", "items": {"type": "string"}}
                                    }
                                }
                            },
                            "required": ["record_indices", "merged_content"]
                        }
                    },
                    "unmerged_indices": {
                        "type": "array",
                        "description": "不需要合并的记录索引",
                        "items": {"type": "integer"}
                    }
                }
            )
            
            # 调用LLM
            llm_component = LLMComponent(llm_config)
            
            # 需要创建runtime和context（简化版，直接调用executable）
            from openjiuwen.core.runtime.runtime import Runtime
            from openjiuwen.core.context_engine.base import Context
            
            runtime = Runtime()
            context = Context()
            
            # LLMComponent 可能需要输入数据，即使模板已经替换了变量
            # 传递空字典应该可以，因为变量已经在 user_prompt 中替换了
            # 但为了保险，我们传递 formatted_records 作为输入
            llm_inputs = {
                "formatted_records": formatted_records
            }
            
            result = await llm_component.executable.invoke(
                llm_inputs,
                runtime.base(),
                context
            )
            
            # 解析结果
            if isinstance(result, dict):
                return result
            elif isinstance(result, str):
                import json
                return json.loads(result)
            else:
                logger.warning(f"LLM返回了意外的格式: {type(result)}")
                return None
                
        except Exception as e:
            logger.error(f"LLM分析失败: {e}", exc_info=True)
            return None
    
    def _apply_consolidation_plan(
        self, 
        records: List[Dict[str, Any]], 
        plan: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """应用合并方案"""
        groups = plan.get("groups", [])
        unmerged_indices = set(plan.get("unmerged_indices", []))
        
        # 收集所有需要合并的索引
        merged_indices = set()
        merged_records = []
        
        # 处理合并组
        for group in groups:
            indices = group.get("record_indices", [])
            merged_content = group.get("merged_content", {})
            
            if not indices or len(indices) < 2:
                # 单个记录不需要合并
                continue
            
            # 验证索引有效性
            valid_indices = [i for i in indices if 0 <= i < len(records)]
            if len(valid_indices) < 2:
                continue
            
            # 使用第一个记录的时间戳
            first_record = records[valid_indices[0]]
            merged_record = {
                "timestamp": first_record.get("timestamp", datetime.utcnow().isoformat() + 'Z'),
                "content": merged_content
            }
            
            # 保留metadata（如果有）
            if "metadata" in first_record.get("content", {}):
                merged_record["content"]["metadata"] = first_record["content"]["metadata"]
            
            merged_records.append(merged_record)
            merged_indices.update(valid_indices)
        
        # 添加未合并的记录
        for i, record in enumerate(records):
            if i not in merged_indices:
                merged_records.append(record)
        
        # 按时间戳排序
        merged_records.sort(key=lambda r: r.get("timestamp", ""))
        
        return merged_records
    
    def _try_merge_by_time_window(
        self, 
        existing_records: List[Dict[str, Any]], 
        new_content: Dict[str, Any], 
        new_timestamp: str,
        time_window_seconds: int = 60
    ) -> Optional[List[Dict[str, Any]]]:
        """
        尝试将新内容合并到时间窗口内的记录中
        
        Args:
            existing_records: 现有记录列表
            new_content: 新内容
            new_timestamp: 新记录的时间戳（ISO格式字符串）
            time_window_seconds: 时间窗口（秒）
            
        Returns:
            如果成功合并，返回更新后的记录列表；否则返回None
        """
        if not existing_records or not new_content:
            return None
        
        try:
            # 解析新记录的时间戳
            timestamp_str = new_timestamp.replace('Z', '+00:00') if new_timestamp.endswith('Z') else new_timestamp
            new_time = datetime.fromisoformat(timestamp_str)
            if new_time.tzinfo is not None:
                new_time = new_time.replace(tzinfo=None)
        except Exception:
            try:
                new_time = datetime.fromisoformat(new_timestamp)
            except Exception as e:
                logger.warning(f"解析新时间戳失败: {new_timestamp}, 错误: {e}，跳过时间窗口检查")
                return None
        
        # 检查最近的记录（最多检查最近10条）
        check_count = min(10, len(existing_records))
        recent_records = existing_records[-check_count:] if len(existing_records) >= check_count else existing_records
        
        # 从最新到最旧查找时间窗口内的记录
        for record in reversed(recent_records):
            record_timestamp = record.get("timestamp")
            if not record_timestamp:
                continue
            
            try:
                # 解析记录的时间戳
                timestamp_str = record_timestamp.replace('Z', '+00:00') if record_timestamp.endswith('Z') else record_timestamp
                record_time = datetime.fromisoformat(timestamp_str)
                if record_time.tzinfo is not None:
                    record_time = record_time.replace(tzinfo=None)
                
                # 计算时间差（秒）
                time_diff = abs((new_time - record_time).total_seconds())
                
                # 如果在时间窗口内，检查内容类型是否相同
                if time_diff <= time_window_seconds:
                    existing_content = record.get("content", {})
                    
                    # 检查内容类型：如果类型不同，不合并
                    existing_type = existing_content.get("content_type", "own_work")
                    new_type = new_content.get("content_type", "own_work")
                    
                    # 如果内容类型不同，不合并（即使在一分钟内）
                    if existing_type != new_type and existing_type != "mixed" and new_type != "mixed":
                        logger.debug(
                            f"时间窗口内的记录但内容类型不同（时间差: {time_diff:.1f}秒，"
                            f"现有类型: {existing_type}，新类型: {new_type}），不合并"
                        )
                        continue  # 继续检查下一条记录
                    
                    # 检查任务主题相似度：如果任务完全不同，不合并
                    task_similarity = self._calculate_task_similarity(
                        existing_content.get("tasks", []),
                        new_content.get("tasks", [])
                    )
                    
                    # 如果任务相似度太低（没有共同任务），不合并
                    TASK_SIMILARITY_THRESHOLD = 0.5  # 至少要有50%的任务相似度（提高阈值，避免不同事情混在一起）
                    if task_similarity < TASK_SIMILARITY_THRESHOLD:
                        logger.debug(
                            f"时间窗口内的记录但任务主题不同（时间差: {time_diff:.1f}秒，"
                            f"任务相似度: {task_similarity:.2%}），不合并"
                        )
                        continue  # 继续检查下一条记录
                    
                    # 内容类型相同且任务主题相似，可以合并
                    merged_content = self._merge_content(existing_content, new_content)
                    record["content"] = merged_content
                    record["timestamp"] = new_timestamp
                    logger.info(
                        f"检测到时间窗口内的记录（时间差: {time_diff:.1f}秒，"
                        f"内容类型: {existing_type}，任务相似度: {task_similarity:.2%}），已合并"
                    )
                    return existing_records
            except Exception as e:
                logger.warning(f"解析记录时间戳失败: {record_timestamp}, 错误: {e}，跳过此记录")
                continue
        
        return None
    
    def _try_merge_similar_record(
        self, 
        existing_records: List[Dict[str, Any]], 
        new_content: Dict[str, Any],
        new_timestamp: str
    ) -> Optional[List[Dict[str, Any]]]:
        """尝试合并相似记录（基于内容相似度，简化版）"""
        # 这里可以添加基于内容相似度的合并逻辑
        # 目前返回 None，表示不进行相似度合并
        return None
    
    def _calculate_task_similarity(self, tasks1: List[str], tasks2: List[str]) -> float:
        """
        计算任务列表的相似度
        
        Args:
            tasks1: 第一个任务列表
            tasks2: 第二个任务列表
            
        Returns:
            相似度分数（0-1之间），0表示完全不同，1表示完全相同
        """
        if not tasks1 and not tasks2:
            # 都没有任务，认为相似
            return 1.0
        
        if not tasks1 or not tasks2:
            # 一个有空任务，另一个有任务，认为不相似
            return 0.0
        
        # 将任务转换为小写并去除空白，用于比较
        tasks1_normalized = [t.lower().strip() for t in tasks1 if t and t.strip()]
        tasks2_normalized = [t.lower().strip() for t in tasks2 if t and t.strip()]
        
        if not tasks1_normalized or not tasks2_normalized:
            return 0.0
        
        # 计算集合相似度（Jaccard相似度）
        set1 = set(tasks1_normalized)
        set2 = set(tasks2_normalized)
        
        # 交集大小
        intersection = len(set1 & set2)
        # 并集大小
        union = len(set1 | set2)
        
        if union == 0:
            return 0.0
        
        # Jaccard相似度 = 交集 / 并集
        similarity = intersection / union
        
        return similarity
    
    def _merge_content(self, existing_content: Dict[str, Any], new_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        合并两个内容记录（简化版）
        
        Args:
            existing_content: 现有内容
            new_content: 新内容
            
        Returns:
            合并后的内容
        """
        # 合并 tasks（去重）
        existing_tasks = set([t.lower().strip() for t in existing_content.get("tasks", []) if t])
        new_tasks = set([t.lower().strip() for t in new_content.get("tasks", []) if t])
        merged_tasks = list(existing_tasks | new_tasks)
        
        # 合并 work_content（用换行分隔，如果内容差异大则用分隔符区分）
        existing_work = existing_content.get("work_content", "").strip()
        new_work = new_content.get("work_content", "").strip()
        if existing_work and new_work:
            # 如果两个工作内容差异很大，用分隔符明确区分，避免不同事情混在一起
            # 简单检查：如果内容长度差异很大，可能是不同的事情
            len_diff_ratio = abs(len(existing_work) - len(new_work)) / max(len(existing_work), len(new_work)) if max(len(existing_work), len(new_work)) > 0 else 0
            if len_diff_ratio > 0.5:
                # 内容长度差异大（>50%），可能是不同的事情，用分隔符区分
                merged_work_content = f"{existing_work}\n\n---\n\n{new_work}"
            else:
                merged_work_content = f"{existing_work}\n{new_work}"
        elif existing_work:
            merged_work_content = existing_work
        else:
            merged_work_content = new_work
        
        # 合并 achievements（去重，基于 title）
        existing_achievements = existing_content.get("achievements", [])
        new_achievements = new_content.get("achievements", [])
        achievement_titles = set()
        merged_achievements = []
        
        for ach in existing_achievements:
            if isinstance(ach, dict):
                title = ach.get("title", "").strip()
                if title and title not in achievement_titles:
                    achievement_titles.add(title)
                    merged_achievements.append(ach)
            elif ach:
                merged_achievements.append(ach)
        
        for ach in new_achievements:
            if isinstance(ach, dict):
                title = ach.get("title", "").strip()
                if title and title not in achievement_titles:
                    achievement_titles.add(title)
                    merged_achievements.append(ach)
            elif ach:
                merged_achievements.append(ach)
        
        # 合并 issues 和 next_steps（去重）
        existing_issues = [i.strip() for i in existing_content.get("issues", []) if i and i.strip()]
        new_issues = [i.strip() for i in new_content.get("issues", []) if i and i.strip()]
        merged_issues = list(set(existing_issues + new_issues))
        
        existing_steps = [s.strip() for s in existing_content.get("next_steps", []) if s and s.strip()]
        new_steps = [s.strip() for s in new_content.get("next_steps", []) if s and s.strip()]
        merged_steps = list(set(existing_steps + new_steps))
        
        # 保留 content_type
        existing_type = existing_content.get("content_type", "own_work")
        new_type = new_content.get("content_type", "own_work")
        if existing_type == "mixed" or new_type == "mixed":
            merged_type = "mixed"
        elif existing_type != new_type:
            merged_type = "mixed"
        else:
            merged_type = existing_type
        
        merged = {
            "content_type": merged_type,
            "tasks": merged_tasks,
            "work_content": merged_work_content,
            "achievements": merged_achievements,
            "issues": merged_issues,
            "next_steps": merged_steps,
        }
        
        # 保留 metadata
        if "metadata" in new_content:
            merged["metadata"] = new_content["metadata"]
        elif "metadata" in existing_content:
            merged["metadata"] = existing_content["metadata"]
        
        return merged
    
    def _convert_workflow_result(self, result: Any) -> Dict[str, Any]:
        """转换工作流结果为旧格式"""
        # WorkflowAgent.invoke可能返回多种格式：
        # 1. {"output": WorkflowOutput, "result_type": "answer"}
        # 2. WorkflowOutput对象
        # 3. 字典
        
        # 处理WorkflowOutput对象
        if hasattr(result, 'result'):
            result = result.result
        
        # 处理字典格式
        if isinstance(result, dict):
            # 如果result包含output字段，提取它
            if "output" in result:
                output = result["output"]
                # 如果output是WorkflowOutput对象，提取其result
                if hasattr(output, 'result'):
                    output = output.result
                if isinstance(output, dict):
                    # 如果output是record_saver的结果，直接返回
                    if "saved" in output or "record_file" in output:
                        return output
                    # 否则返回整个output
                    return output
                return output
            # 如果result直接包含saved或record_file，说明是record_saver的结果
            if "saved" in result or "record_file" in result:
                return result
            return result
        
        return result if isinstance(result, dict) else {}
    
    def _convert_report_result(self, result: Any) -> Dict[str, Any]:
        """转换报告结果为旧格式"""
        # WorkflowAgent.invoke可能返回多种格式：
        # 1. {"output": WorkflowOutput, "result_type": "answer"}
        # 2. WorkflowOutput对象
        # 3. 字典
        
        # 处理WorkflowOutput对象
        if hasattr(result, 'result'):
            result = result.result
        
        # 处理字典格式
        if isinstance(result, dict):
            if "output" in result:
                output = result["output"]
                # 如果output是WorkflowOutput对象，提取其result
                if hasattr(output, 'result'):
                    output = output.result
                
                if isinstance(output, dict):
                    # 处理多层嵌套的情况
                    # 可能的结构：
                    # 1. {"output": {实际报告数据}}
                    # 2. {"output": {"output": {实际报告数据}}}
                    # 3. 直接包含报告字段
                    
                    current = output
                    depth = 0
                    max_depth = 3  # 最多处理3层嵌套
                    
                    while depth < max_depth:
                        # 如果当前层级直接包含报告字段，返回它
                        if "tasks" in current or "work_content" in current:
                            return current
                        
                        # 如果当前层级包含"output"字段，继续深入
                        if "output" in current and isinstance(current["output"], dict):
                            current = current["output"]
                            depth += 1
                        else:
                            # 没有更多嵌套，返回当前层级
                            break
                    
                    # 如果遍历完所有层级都没找到报告字段，返回最深层的数据
                    return current
                return output
            
            # 如果result直接包含tasks或work_content，说明是报告结果
            if "tasks" in result or "work_content" in result:
                return result
            
            return result
        
        return result if isinstance(result, dict) else {}
    
    async def _on_screenshot_captured(self, screenshot_path: str):
        """自动截图回调函数 - 将截图加入队列"""
        if not self._auto_screenshot_enabled:
            return
        
        if self._screenshot_queue is None:
            logger.error("截图队列未初始化，无法处理截图")
            return
        
        # 确保队列处理线程在运行
        if not self._queue_processor_running:
            self._start_queue_processor()
        
        # 创建任务并加入队列
        # 注意：由于队列处理在另一个线程的事件循环中，我们需要使用 call_soon_threadsafe
        task = ScreenshotTask(
            file_path=screenshot_path,
            timestamp=datetime.utcnow().isoformat() + 'Z',
            captured_at=datetime.now()
        )
        
        try:
            # 如果队列处理循环在运行，使用 call_soon_threadsafe 将任务加入队列
            if self._queue_processor_loop and self._queue_processor_loop.is_running():
                # 在队列处理线程的事件循环中执行 put 操作
                # 不等待结果，避免阻塞（队列是线程安全的，put 操作会立即完成或排队）
                future = asyncio.run_coroutine_threadsafe(
                    self._screenshot_queue.put(task),
                    self._queue_processor_loop
                )
                # 不等待 future 完成，避免超时
                # 队列的 put 操作是线程安全的，即使处理循环正在处理其他任务，put 也能成功
                # 使用 add_done_callback 来记录结果，但不阻塞
                def log_result(fut):
                    try:
                        fut.result()  # 检查是否有异常
                        queue_size = self._screenshot_queue.qsize()
                        logger.info(f"截图已加入队列: {Path(screenshot_path).name} (队列长度: {queue_size})")
                    except Exception as e:
                        logger.error(f"将截图加入队列失败: {e}", exc_info=True)
                
                future.add_done_callback(log_result)
            else:
                logger.warning("队列处理循环未运行，无法加入队列")
        except Exception as e:
            logger.error(f"将截图加入队列失败: {e}", exc_info=True)
    
    def _start_queue_processor(self):
        """启动队列处理线程"""
        if self._queue_processor_running:
            return
        
        if self._screenshot_queue is None:
            self._screenshot_queue = asyncio.Queue()
        
        self._queue_processor_running = True
        
        def run_queue_processor():
            """在后台线程中运行队列处理循环"""
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._queue_processor_loop = loop
            
            try:
                # 运行队列处理协程
                loop.run_until_complete(self._process_screenshot_queue())
            except Exception as e:
                logger.error(f"队列处理线程出错: {e}", exc_info=True)
            finally:
                loop.close()
                self._queue_processor_running = False
                self._queue_processor_loop = None
        
        self._queue_processor_thread = threading.Thread(target=run_queue_processor, daemon=True)
        self._queue_processor_thread.start()
        logger.info("截图队列处理线程已启动")
    
    def _stop_queue_processor(self):
        """停止队列处理线程"""
        if not self._queue_processor_running:
            return
        
        self._queue_processor_running = False
        
        # 停止事件循环
        if self._queue_processor_loop and self._queue_processor_loop.is_running():
            self._queue_processor_loop.call_soon_threadsafe(self._queue_processor_loop.stop)
        
        # 等待线程结束
        if self._queue_processor_thread and self._queue_processor_thread.is_alive():
            self._queue_processor_thread.join(timeout=5)
        
        logger.info("截图队列处理线程已停止")
    
    async def _process_screenshot_queue(self):
        """队列处理任务 - 按顺序处理队列中的截图"""
        logger.info("截图队列处理任务已启动")
        
        # 连续超时次数（用于判断队列是否真的为空）
        consecutive_timeouts = 0
        max_consecutive_timeouts = 10  # 连续10次超时（10秒）且自动截图已停止，才真正停止
        
        while self._queue_processor_running:
            try:
                # 从队列中获取任务（阻塞等待，但设置超时以便检查运行状态）
                try:
                    task = await asyncio.wait_for(
                        self._screenshot_queue.get(),
                        timeout=1.0
                    )
                    # 成功获取任务，重置超时计数
                    consecutive_timeouts = 0
                except asyncio.TimeoutError:
                    # 超时，检查是否应该停止
                    consecutive_timeouts += 1
                    
                    # 如果自动截图已停止，且队列为空，且连续超时多次，才真正停止
                    if not self._auto_screenshot_enabled:
                        queue_size = self._screenshot_queue.qsize()
                        if queue_size == 0 and consecutive_timeouts >= max_consecutive_timeouts:
                            logger.info(f"自动截图已停止，队列为空，连续超时{consecutive_timeouts}次，停止队列处理")
                            break
                        elif queue_size > 0:
                            # 队列中还有任务，重置超时计数
                            consecutive_timeouts = 0
                            logger.debug(f"队列中还有{queue_size}个任务，继续处理")
                    
                    # 继续循环
                    continue
                
                # 更新当前处理的任务
                self._current_processing_task = task
                self._processing_screenshots += 1
                
                logger.info(f"开始处理截图: {Path(task.file_path).name} (队列剩余: {self._screenshot_queue.qsize()})")
                
                screenshot_file = Path(task.file_path)
                try:
                    # 使用新的工作流处理截图
                    await self.workflow_agent.invoke_record_input(
                        input_type="image",
                        file_path=task.file_path,
                        is_auto_screenshot=True,
                        incremental=True
                    )
                    # 处理完成，更新计数
                    self._processing_screenshots -= 1
                    self._processed_screenshots += 1
                    logger.info(f"截图处理完成: {Path(task.file_path).name} (已处理: {self._processed_screenshots} 张，队列剩余: {self._screenshot_queue.qsize()})")
                    
                    # 处理成功后，删除截图文件以节省空间
                    try:
                        if screenshot_file.exists():
                            screenshot_file.unlink()
                            logger.info(f"已删除截图文件: {task.file_path}")
                        else:
                            logger.warning(f"截图文件不存在，无法删除: {task.file_path}")
                    except Exception as delete_error:
                        # 删除失败不影响主流程，只记录警告
                        logger.warning(f"删除截图文件失败: {task.file_path}, 错误: {delete_error}")
                except Exception as e:
                    # 处理失败，也要更新计数
                    self._processing_screenshots -= 1
                    logger.error(f"自动截图处理失败: {e}", exc_info=True)
                    # 处理失败时不删除文件，保留以便调试
                finally:
                    # 清除当前处理的任务
                    self._current_processing_task = None
                    # 标记任务完成
                    self._screenshot_queue.task_done()
                    
            except asyncio.CancelledError:
                logger.info("截图队列处理任务已取消")
                break
            except Exception as e:
                logger.error(f"队列处理任务出错: {e}", exc_info=True)
                # 继续处理下一个任务
                if self._current_processing_task:
                    self._current_processing_task = None
                    self._processing_screenshots -= 1
        
        logger.info("截图队列处理任务已结束")