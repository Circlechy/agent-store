# -*- coding: utf-8 -*-
"""
记录格式化组件

将记录格式化为LLM可理解的文本，用于报告生成
"""

from typing import Dict, Any, List
from datetime import datetime
from openjiuwen.core.component.base import ComponentExecutable, WorkflowComponent
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.common.logging import logger


class RecordFormatterComponent(ComponentExecutable, WorkflowComponent):
    """记录格式化组件 - 将记录格式化为LLM可理解的文本"""
    
    async def invoke(self, inputs: Dict[str, Any], runtime: Runtime, context: Context) -> Dict[str, Any]:
        """
        格式化记录
        
        Args:
            inputs: 输入数据，包含：
                - records: 记录列表（来自RecordQuery组件）
                - start_date: 开始日期
                - end_date: 结束日期
            runtime: 运行时上下文
            context: 上下文引擎
            
        Returns:
            格式化结果字典：
                - formatted_text: 格式化后的文本
                - record_count: 记录数量
                - start_date: 开始日期
                - end_date: 结束日期
        """
        records = inputs.get("records", [])
        start_date = inputs.get("start_date")
        end_date = inputs.get("end_date")
        
        if not records:
            logger.warning("记录格式化组件：记录列表为空")
            return {
                "formatted_text": "",
                "record_count": 0,
                "start_date": start_date,
                "end_date": end_date
            }
        
        try:
            formatted_text = self._format_records(records, start_date, end_date)
            
            logger.info(f"记录格式化完成：{len(records)} 条记录")
            
            return {
                "formatted_text": formatted_text,
                "record_count": len(records),
                "start_date": start_date,
                "end_date": end_date
            }
        except Exception as e:
            logger.error(f"记录格式化失败: {e}", exc_info=True)
            return {
                "formatted_text": "",
                "record_count": len(records),
                "start_date": start_date,
                "end_date": end_date,
                "error": str(e)
            }
    
    def _format_records(self, records: List[Dict[str, Any]], start_date: str = None, end_date: str = None) -> str:
        """
        格式化记录为文本
        
        Args:
            records: 记录列表
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
        """
        if not records:
            return ""
        
        # 按日期分组记录
        records_by_date: Dict[str, List[Dict[str, Any]]] = {}
        for record in records:
            timestamp = record.get("timestamp", "")
            if timestamp:
                try:
                    # 从时间戳中提取日期
                    record_date = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime("%Y-%m-%d")
                    if record_date not in records_by_date:
                        records_by_date[record_date] = []
                    records_by_date[record_date].append(record)
                except:
                    # 如果解析失败，使用默认日期
                    record_date = start_date or datetime.now().strftime("%Y-%m-%d")
                    if record_date not in records_by_date:
                        records_by_date[record_date] = []
                    records_by_date[record_date].append(record)
        
        # 构建格式化文本
        parts = []
        
        if start_date and end_date:
            parts.append(f"日期范围：{start_date} 至 {end_date}\n")
        elif start_date:
            parts.append(f"日期：{start_date}\n")
        
        parts.append(f"共 {len(records)} 条工作记录\n")
        parts.append("=" * 60 + "\n\n")
        
        # 按日期分组显示
        for date_str in sorted(records_by_date.keys()):
            day_records = records_by_date[date_str]
            parts.append(f"## {date_str} ({len(day_records)} 条记录)\n\n")
            
            for i, record in enumerate(day_records, 1):
                content = record.get("content", {})
                timestamp = record.get("timestamp", "")
                
                parts.append(f"### 记录 {i} ({timestamp})\n\n")
                
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
                            elif desc:
                                parts.append(f"- {desc}\n")
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
