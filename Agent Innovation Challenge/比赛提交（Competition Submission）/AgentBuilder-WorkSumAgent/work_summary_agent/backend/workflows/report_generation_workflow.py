# -*- coding: utf-8 -*-
"""
报告生成工作流

查询指定日期范围的记录，格式化，汇总分析，生成报告
"""

from pathlib import Path
from openjiuwen.core.workflow.base import Workflow
from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata, WorkflowInputsSchema
from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.component.llm_comp import LLMComponent, LLMCompConfig
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo
from openjiuwen.core.common.logging import logger
import os

# 导入自定义组件
import sys
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent
sys.path.insert(0, str(_backend_dir))

from backend.components.storage.record_query import RecordQueryComponent
from backend.components.formatters.record_formatter import RecordFormatterComponent
from backend.components.formatters.report_formatter import ReportFormatterComponent
from backend.prompts.prompt_loader import load_combined_prompt

# 工作记录目录
WORK_RECORDS_DIR = _backend_dir.parent / "work_records"


def create_report_generation_workflow(model_config: ModelConfig = None) -> Workflow:
    """
    创建报告生成工作流
    
    Args:
        model_config: LLM模型配置
        
    Returns:
        Workflow实例
    """
    # 创建工作流配置
    workflow_config = WorkflowConfig(
        metadata=WorkflowMetadata(
            id="report_generation_workflow",
            name="report_generation_workflow",
            version="1.0.0",
            description="报告生成工作流：查询记录，格式化，汇总分析，生成报告"
        ),
        workflow_inputs_schema=WorkflowInputsSchema(
            type="object",
            properties={
                "start_date": {"type": "string", "description": "开始日期（格式: YYYY-MM-DD）", "required": True},
                "end_date": {"type": "string", "description": "结束日期（格式: YYYY-MM-DD）", "required": True},
            },
            required=['start_date', 'end_date']
        )
    )
    
    # 初始化工作流
    flow = Workflow(workflow_config=workflow_config)
    
    # 创建组件
    start = Start({
        "inputs": [
            {"id": "start_date", "type": "String", "required": True, "sourceType": "ref"},
            {"id": "end_date", "type": "String", "required": True, "sourceType": "ref"},
        ]
    })
    
    # 记录查询组件
    record_query = RecordQueryComponent(work_records_dir=WORK_RECORDS_DIR)
    
    # 记录格式化组件
    record_formatter = RecordFormatterComponent()
    
    # 内容汇总组件（LLMComponent）
    if not model_config:
        # 创建默认模型配置
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
    
    # 创建汇总LLM组件配置（从文件加载 prompt）
    system_prompt, user_prompt = load_combined_prompt("report_generation/summarize.txt")
    
    summarizer_config = LLMCompConfig(
        model=model_config,
        template_content=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
            response_format={"type": "json"},
        output_config={
            "tasks": {
                "type": "array",
                "description": "主要任务/项目列表（需进行智能聚类和去重，只保留主要项目，控制在10条以内）",
                "required": True,
                "items": {"type": "string"},
                "maxItems": 10
            },
            "work_content": {
                "type": "array",
                "description": "完成的工作内容列表，每条内容是一个独立的工作项描述",
                "required": True,
                "items": {"type": "string"}
            },
            "achievements": {
                "type": "array",
                "description": "取得的成果列表，每个成果是一个字符串描述（格式：'标题: 描述'）",
                "required": False,
                "items": {"type": "string"}
            },
            "issues": {
                "type": "array",
                "description": "遇到的问题列表",
                "required": False,
                "items": {"type": "string"}
            },
            "next_steps": {
                "type": "array",
                "description": "下一步计划列表",
                "required": False,
                "items": {"type": "string"}
            }
        },
    )
    
    content_summarizer = LLMComponent(summarizer_config)
    
    # 报告格式化组件
    report_formatter = ReportFormatterComponent()
    
    # 结束组件
    # 不使用 responseTemplate，直接传递 report_formatter 的输出
    end = End()
    
    # 注册组件到工作流
    flow.set_start_comp("start", start, inputs_schema={
        "start_date": "${start_date}",
        "end_date": "${end_date}",
    })
    
    # 记录查询组件
    flow.add_workflow_comp("record_query", record_query, inputs_schema={
        "start_date": "${start.start_date}",
        "end_date": "${start.end_date}",
    })
    
    # 记录格式化组件
    flow.add_workflow_comp("record_formatter", record_formatter, inputs_schema={
        "records": "${record_query.records}",
        "start_date": "${record_query.start_date}",
        "end_date": "${record_query.end_date}",
    })
    
    # 内容汇总组件
    flow.add_workflow_comp("content_summarizer", content_summarizer, inputs_schema={
        "formatted_text": "${record_formatter.formatted_text}",
    })
    
    # 报告格式化组件
    flow.add_workflow_comp("report_formatter", report_formatter, inputs_schema={
        "summary": "${content_summarizer}",
        "start_date": "${start.start_date}",
        "end_date": "${start.end_date}",
        "record_count": "${record_formatter.record_count}",
    })
    
    # 结束组件
    flow.set_end_comp("end", end, inputs_schema={
        "output": "${report_formatter}",
    })
    
    # 连接工作流拓扑
    flow.add_connection("start", "record_query")
    flow.add_connection("record_query", "record_formatter")
    flow.add_connection("record_formatter", "content_summarizer")
    flow.add_connection("content_summarizer", "report_formatter")
    flow.add_connection("report_formatter", "end")
    
    logger.info("报告生成工作流创建完成")
    
    return flow
