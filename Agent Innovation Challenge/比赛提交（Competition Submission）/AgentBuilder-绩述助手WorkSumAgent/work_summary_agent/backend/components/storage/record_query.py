# -*- coding: utf-8 -*-
"""
记录查询组件

查询指定日期范围内的所有工作记录
"""

import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime, timedelta
from openjiuwen.core.component.base import ComponentExecutable, WorkflowComponent
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.common.logging import logger

# 工作记录存储目录
_current_file = Path(__file__).resolve()
WORK_RECORDS_DIR = _current_file.parent.parent.parent.parent / "work_records"
WORK_RECORDS_DIR.mkdir(exist_ok=True)


class RecordQueryComponent(ComponentExecutable, WorkflowComponent):
    """记录查询组件 - 查询指定日期范围的记录"""
    
    def __init__(self, work_records_dir: Optional[Path] = None):
        """
        初始化记录查询组件
        
        Args:
            work_records_dir: 工作记录目录，如果为None则使用默认目录
        """
        self.work_records_dir = work_records_dir or WORK_RECORDS_DIR
    
    async def invoke(self, inputs: Dict[str, Any], runtime: Runtime, context: Context) -> Dict[str, Any]:
        """
        查询工作记录
        
        Args:
            inputs: 输入数据，包含：
                - start_date: 开始日期（格式: YYYY-MM-DD）
                - end_date: 结束日期（格式: YYYY-MM-DD）
            runtime: 运行时上下文
            context: 上下文引擎
            
        Returns:
            查询结果字典：
                - records: 记录列表
                - start_date: 开始日期
                - end_date: 结束日期
                - record_count: 记录数量
        """
        start_date = inputs.get("start_date")
        end_date = inputs.get("end_date")
        
        if not start_date or not end_date:
            logger.warning("记录查询组件：未提供日期范围")
            return {
                "records": [],
                "start_date": start_date,
                "end_date": end_date,
                "record_count": 0,
                "error": "未提供日期范围"
            }
        
        try:
            all_records: List[Dict[str, Any]] = []
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            
            current = start
            while current <= end:
                date_str = current.strftime("%Y-%m-%d")
                record_file = self.work_records_dir / f"{date_str}.json"
                
                if record_file.exists():
                    try:
                        with open(record_file, "r", encoding="utf-8") as f:
                            day_records = json.load(f)
                            all_records.extend(day_records)
                    except Exception as e:
                        logger.warning(f"读取 {date_str} 的记录失败: {e}")
                
                current += timedelta(days=1)
            
            logger.info(f"记录查询完成: {start_date} 到 {end_date}，共 {len(all_records)} 条记录")
            
            return {
                "records": all_records,
                "start_date": start_date,
                "end_date": end_date,
                "record_count": len(all_records)
            }
        except Exception as e:
            logger.error(f"记录查询失败: {e}", exc_info=True)
            return {
                "records": [],
                "start_date": start_date,
                "end_date": end_date,
                "record_count": 0,
                "error": str(e)
            }
