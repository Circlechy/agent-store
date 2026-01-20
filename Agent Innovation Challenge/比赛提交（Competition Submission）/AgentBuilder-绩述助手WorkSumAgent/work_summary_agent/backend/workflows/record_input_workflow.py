# -*- coding: utf-8 -*-
"""
内容录入工作流

处理文字/文档/图片输入，提取文本，分析内容，保存记录
"""

from pathlib import Path
from openjiuwen.core.workflow.base import Workflow
from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata, WorkflowInputsSchema
from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.component.branch_comp import BranchComponent
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.common.logging import logger

# 导入自定义组件
import sys
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent
sys.path.insert(0, str(_backend_dir))

from backend.components.extractors.text_extractor import TextExtractorComponent
from backend.components.extractors.document_extractor import DocumentExtractorComponent
from backend.components.extractors.image_extractor import ImageExtractorComponent
from backend.components.extractors.text_merger import TextMergerComponent
from backend.components.analyzers.content_analyzer_comp import ContentAnalyzerComponent
from backend.components.storage.record_saver import RecordSaverComponent

# 工作记录目录
WORK_RECORDS_DIR = _backend_dir.parent / "work_records"


def create_record_input_workflow(model_config: ModelConfig = None, image_processing_mode: str = "ocr") -> Workflow:
    """
    创建内容录入工作流
    
    Args:
        model_config: LLM模型配置
        image_processing_mode: 图片处理模式
        
    Returns:
        Workflow实例
    """
    # 创建工作流配置
    workflow_config = WorkflowConfig(
        metadata=WorkflowMetadata(
            id="record_input_workflow",
            name="record_input_workflow",
            version="1.0.0",
            description="内容录入工作流：处理文字/文档/图片输入，提取文本，分析内容，保存记录"
        ),
        workflow_inputs_schema=WorkflowInputsSchema(
            type="object",
            properties={
                "content": {"type": "string", "description": "文本内容（当input_type为text时必填）"},
                "input_type": {"type": "string", "description": "输入类型：text/document/image", "required": True},
                "file_path": {"type": "string", "description": "文件路径（当input_type为document或image时必填）"},
                "date": {"type": "string", "description": "日期（格式: YYYY-MM-DD，可选）"},
                "timestamp": {"type": "string", "description": "时间戳（ISO格式，可选）"},
                "is_auto_screenshot": {"type": "boolean", "description": "是否是自动截图（默认false）"},
                "image_processing_mode": {"type": "string", "description": "图片处理模式（可选）"},
                "merge_similar": {"type": "boolean", "description": "是否合并相似记录（默认true）"},
                "additional_text": {"type": "string", "description": "用户输入的额外文本内容（可选），会与文档/图片内容整合"}
            },
            required=['input_type']
        )
    )
    
    # 初始化工作流
    flow = Workflow(workflow_config=workflow_config)
    
    # 创建组件
    # 注意：所有字段都应该设置为 required: false，因为它们可能是可选的
    # Start 组件的 _validate_inputs 只会检查 required: true 的字段
    start = Start({
        "inputs": [
            {"id": "content", "type": "String", "required": False, "sourceType": "ref"},
            {"id": "input_type", "type": "String", "required": True, "sourceType": "ref"},
            {"id": "file_path", "type": "String", "required": False, "sourceType": "ref"},
            {"id": "date", "type": "String", "required": False, "sourceType": "ref"},
            {"id": "timestamp", "type": "String", "required": False, "sourceType": "ref"},
            {"id": "is_auto_screenshot", "type": "Boolean", "required": False, "sourceType": "ref"},
            {"id": "image_processing_mode", "type": "String", "required": False, "sourceType": "ref"},
            {"id": "merge_similar", "type": "Boolean", "required": False, "sourceType": "ref"},
            {"id": "additional_text", "type": "String", "required": False, "sourceType": "ref"},
        ]
    })
    
    # 三个提取器组件（支持并行执行，处理混合输入）
    text_extractor = TextExtractorComponent()
    doc_extractor = DocumentExtractorComponent()
    image_extractor = ImageExtractorComponent(image_processing_mode=image_processing_mode)
    
    # 文本合并组件（合并三个提取器的输出和additional_text）
    text_merger = TextMergerComponent()
    
    # 内容分析组件
    content_analyzer = ContentAnalyzerComponent(model_config=model_config)
    
    # 记录保存组件
    record_saver = RecordSaverComponent(work_records_dir=WORK_RECORDS_DIR)
    
    # 结束组件
    end = End({"responseTemplate": "{{record_saver}}"})
    
    # 注册组件到工作流
    # 注意：Start组件的inputs_schema使用${variable_name}格式引用全局变量
    # 这些变量来自工作流的输入（通过commit_user_inputs设置到global_state）
    # 对于可选字段，如果它们在全局变量中不存在，get_by_schema会返回None
    # 但Start组件的_validate_inputs只会检查required=True的字段
    # 所以即使这些字段是None，只要required=False，就不会报错
    flow.set_start_comp("start", start, inputs_schema={
        "content": "${content}",
        "input_type": "${input_type}",
        "file_path": "${file_path}",
        "date": "${date}",
        "timestamp": "${timestamp}",
        "is_auto_screenshot": "${is_auto_screenshot}",
        "image_processing_mode": "${image_processing_mode}",
        "merge_similar": "${merge_similar}",
        "additional_text": "${additional_text}",
    })
    
    # 文本提取器（处理content字段，支持与文档/图片混合）
    flow.add_workflow_comp("text_extractor", text_extractor, inputs_schema={
        "content": "${start.content}",
    })
    
    # 文档提取器（处理file_path，当input_type为document时）
    flow.add_workflow_comp("doc_extractor", doc_extractor, inputs_schema={
        "file_path": "${start.file_path}",
    })
    
    # 图片提取器（处理file_path，当input_type为image时）
    flow.add_workflow_comp("image_extractor", image_extractor, inputs_schema={
        "file_path": "${start.file_path}",
        "is_auto_screenshot": "${start.is_auto_screenshot}",
        "image_processing_mode": "${start.image_processing_mode}",
    })
    
    # 文本合并组件（合并三个提取器的输出和additional_text）
    # 支持混合输入：文本+文档、文本+图片、文档+文本等组合
    flow.add_workflow_comp("text_merger", text_merger, inputs_schema={
        "text_extractor": "${text_extractor}",
        "doc_extractor": "${doc_extractor}",
        "image_extractor": "${image_extractor}",
        "additional_text": "${start.additional_text}",  # 传递additional_text
    })
    
    # 内容分析组件（接收来自合并组件的输出）
    flow.add_workflow_comp("content_analyzer", content_analyzer, inputs_schema={
        "text": "${text_merger.text}",
        "extracted_text": "${text_merger.text}",  # 兼容性支持
        "metadata": "${text_merger.metadata}",
        "is_auto_screenshot": "${text_merger.metadata.is_auto_screenshot}",  # 传递is_auto_screenshot
    })
    
    # 记录保存组件
    # 注意：content_analyzer的输出是一个字典，包含tasks、work_content等字段
    # 但record_saver期望的content字段应该是一个包含这些字段的字典
    flow.add_workflow_comp("record_saver", record_saver, inputs_schema={
        "content": "${content_analyzer}",  # 整个分析结果作为content
        "date": "${start.date}",
        "timestamp": "${start.timestamp}",
        "merge_similar": "${start.merge_similar}",
    })
    
    # 结束组件
    flow.set_end_comp("end", end, inputs_schema={
        "output": "${record_saver}",
    })
    
    # 连接工作流拓扑
    # 支持混合输入：所有提取器并行执行，由text_merger合并结果
    # start -> 三个提取器（并行执行）
    flow.add_connection("start", "text_extractor")
    flow.add_connection("start", "doc_extractor")
    flow.add_connection("start", "image_extractor")
    
    # 三个提取器 -> 文本合并器（并行输入）
    flow.add_connection("text_extractor", "text_merger")
    flow.add_connection("doc_extractor", "text_merger")
    flow.add_connection("image_extractor", "text_merger")
    
    # 文本合并器 -> 内容分析器
    flow.add_connection("text_merger", "content_analyzer")
    
    # 内容分析器 -> 记录保存器
    flow.add_connection("content_analyzer", "record_saver")
    
    # 记录保存器 -> 结束
    flow.add_connection("record_saver", "end")
    
    logger.info("内容录入工作流创建完成")
    
    return flow
