# -*- coding: utf-8 -*-
"""
报告格式化组件

格式化最终报告输出，添加元数据
"""

from typing import Dict, Any
from openjiuwen.core.component.base import ComponentExecutable, WorkflowComponent
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.common.logging import logger


class ReportFormatterComponent(ComponentExecutable, WorkflowComponent):
    """报告格式化组件 - 格式化最终报告输出"""
    
    async def invoke(self, inputs: Dict[str, Any], runtime: Runtime, context: Context) -> Dict[str, Any]:
        """
        格式化报告
        
        Args:
            inputs: 输入数据，包含：
                - summary: 汇总结果（来自ContentSummarizer LLMComponent）
                - start_date: 开始日期
                - end_date: 结束日期
                - record_count: 记录数量（来自RecordFormatter）
            runtime: 运行时上下文
            context: 上下文引擎
            
        Returns:
            格式化后的报告字典
        """
        summary = inputs.get("summary", {})
        start_date = inputs.get("start_date")
        end_date = inputs.get("end_date")
        record_count = inputs.get("record_count", 0)
        
        if not summary:
            logger.warning("报告格式化组件：汇总结果为空")
            return {
                "tasks": [],
                "work_content": [],
                "achievements": [],
                "issues": [],
                "next_steps": [],
                "metadata": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "record_count": record_count,
                    "summary_method": "none"
                }
            }
        
        try:
            # 确保metadata存在
            if "metadata" not in summary:
                summary["metadata"] = {}
            
            # 更新元数据
            summary["metadata"].update({
                "start_date": start_date,
                "end_date": end_date,
                "record_count": record_count,
                "summary_method": summary.get("metadata", {}).get("summary_method", "llm_summary")
            })
            
            logger.info(f"报告格式化完成：{start_date} 至 {end_date}，{record_count} 条记录")
            
            return summary
        except Exception as e:
            logger.error(f"报告格式化失败: {e}", exc_info=True)
            return {
                "tasks": [],
                "work_content": [],
                "achievements": [],
                "issues": [],
                "next_steps": [],
                "metadata": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "record_count": record_count,
                    "summary_method": "error",
                    "error": str(e)
                }
            }
