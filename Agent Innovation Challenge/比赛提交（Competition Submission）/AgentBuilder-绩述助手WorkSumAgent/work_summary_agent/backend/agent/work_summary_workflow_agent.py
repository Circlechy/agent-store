# -*- coding: utf-8 -*-
"""
工作总结 WorkflowAgent

基于openjiuwen的WorkflowAgent，绑定内容录入和报告生成两个工作流
"""

from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import hashlib
from openjiuwen.agent.workflow_agent.workflow_agent import WorkflowAgent
from openjiuwen.agent.config.workflow_config import WorkflowAgentConfig
from openjiuwen.agent.common.schema import WorkflowSchema
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.common.logging import logger
from openjiuwen.core.agent.agent import workflow_provider

# 导入工作流工厂函数
import sys
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent
sys.path.insert(0, str(_backend_dir))

from backend.workflows.record_input_workflow import create_record_input_workflow
from backend.workflows.report_generation_workflow import create_report_generation_workflow
from backend.agent.custom_workflow_controller import CustomWorkflowController


class WorkSummaryWorkflowAgent:
    """
    工作总结 WorkflowAgent 包装器
    
    封装WorkflowAgent，提供统一的调用接口
    """
    
    def __init__(
        self,
        model_config: Optional[ModelConfig] = None,
        image_processing_mode: str = "ocr"
    ):
        """
        初始化WorkflowAgent
        
        Args:
            model_config: LLM模型配置
            image_processing_mode: 图片处理模式
        """
        self.model_config = model_config
        self.image_processing_mode = image_processing_mode
        
        # 创建Agent配置
        # 注意：WorkflowSchema的inputs字段用于定义工作流的输入参数
        # 这些参数会从message.content.extensions中过滤出来，然后传递给工作流
        agent_config = WorkflowAgentConfig(
            id="work_summary_agent",
            version="1.0.0",
            description="工作总结Agent - 基于WorkflowAgent实现",
            workflows=[
                WorkflowSchema(
                    id="record_input_workflow",
                    name="record_input_workflow",
                    version="1.0.0",
                    description="内容录入工作流",
                    inputs={
                        "content": {"type": "string"},
                        "input_type": {"type": "string"},
                        "file_path": {"type": "string"},
                        "date": {"type": "string"},
                        "timestamp": {"type": "string"},
                        "is_auto_screenshot": {"type": "boolean"},
                        "image_processing_mode": {"type": "string"},
                        "merge_similar": {"type": "boolean"},
                        "additional_text": {"type": "string"}
                    }
                ),
                WorkflowSchema(
                    id="report_generation_workflow",
                    name="report_generation_workflow",
                    version="1.0.0",
                    description="报告生成工作流",
                    inputs={
                        "start_date": {"type": "string"},
                        "end_date": {"type": "string"}
                    }
                )
            ]
        )
        
        # 创建WorkflowAgent
        self.workflow_agent = WorkflowAgent(agent_config)
        
        # 替换为自定义的 WorkflowController，优先使用 workflow_id
        # 使用 controller 属性会自动调用 _setup_controller() 进行配置
        custom_controller = CustomWorkflowController()
        self.workflow_agent.controller = custom_controller
        
        # 使用@workflow_provider装饰器创建工作流工厂函数
        @workflow_provider(
            workflow_id="record_input_workflow",
            workflow_version="1.0.0",
            workflow_name="record_input_workflow",
            workflow_description="内容录入工作流"
        )
        def create_record_input():
            return create_record_input_workflow(
                model_config=self.model_config,
                image_processing_mode=self.image_processing_mode
            )
        
        @workflow_provider(
            workflow_id="report_generation_workflow",
            workflow_version="1.0.0",
            workflow_name="report_generation_workflow",
            workflow_description="报告生成工作流"
        )
        def create_report_generation():
            return create_report_generation_workflow(
                model_config=self.model_config
            )
        
        # 绑定工作流（使用add_workflows方法）
        self.workflow_agent.add_workflows([
            create_record_input,
            create_report_generation
        ])
        
        logger.info("WorkSummaryWorkflowAgent初始化完成")
    
    async def invoke_record_input(
        self,
        content: str = None,
        input_type: str = "text",
        file_path: str = None,
        date: str = None,
        timestamp: str = None,
        is_auto_screenshot: bool = False,
        image_processing_mode: str = None,
        merge_similar: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用内容录入工作流
        
        Args:
            content: 文本内容（当input_type为text时必填）
            input_type: 输入类型（text/document/image）
            file_path: 文件路径（当input_type为document或image时必填）
            date: 日期（格式: YYYY-MM-DD，可选）
            timestamp: 时间戳（ISO格式，可选）
            is_auto_screenshot: 是否是自动截图（默认False）
            image_processing_mode: 图片处理模式（可选）
            merge_similar: 是否合并相似记录（默认True）
            **kwargs: 其他参数
            
        Returns:
            工作流执行结果
        """
        # WorkflowAgent期望的输入格式：
        # - query: 用户查询（可选，用于意图识别）
        # - workflow_id: 工作流ID（用于直接指定工作流）
        # - 其他参数放在顶层，会被放入extensions中，然后传递给工作流
        # 工作流期望的输入格式是直接的参数字典，不需要user_inputs包装
        # 确保所有字段都被传递，即使是None也包含在extensions中
        # WorkflowController._filter_workflow_inputs 会根据 workflow.inputs schema 过滤字段
        # 如果字段不在extensions中，它不会被传递给工作流
        inputs = {
            "query": f"添加{input_type}类型的工作记录",  # 用于意图识别
            "workflow_id": "record_input_workflow",  # 直接指定工作流
            # 这些参数会被放入extensions，然后传递给工作流作为输入
            # 注意：即使值是None，也要包含这些字段，确保它们被传递给工作流
            "content": content or "",
            "input_type": input_type,
            "file_path": file_path or "",
            "date": date or "",  # 如果None，使用空字符串
            "timestamp": timestamp or "",
            "is_auto_screenshot": is_auto_screenshot,
            "image_processing_mode": image_processing_mode or self.image_processing_mode,
            "merge_similar": merge_similar,
            "additional_text": kwargs.get("additional_text") or "",
            **{k: v for k, v in kwargs.items() if k != "additional_text"}
        }
        
        # 对于自动截图，使用独立的session，避免相互取消
        # 使用文件路径的hash作为session ID，确保每个截图有独立的session
        if is_auto_screenshot and file_path:
            # 使用文件路径和时间戳生成唯一的session ID
            session_id = f"auto_screenshot_{hashlib.md5(f'{file_path}_{timestamp or datetime.now().isoformat()}'.encode()).hexdigest()[:16]}"
            inputs["conversation_id"] = session_id
            logger.info(f"自动截图使用独立session: {session_id}")
        
        result = await self.workflow_agent.invoke(inputs)
        return result
    
    async def invoke_report_generation(
        self,
        start_date: str,
        end_date: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用报告生成工作流
        
        Args:
            start_date: 开始日期（格式: YYYY-MM-DD）
            end_date: 结束日期（格式: YYYY-MM-DD）
            **kwargs: 其他参数
            
        Returns:
            工作流执行结果
        """
        # WorkflowAgent期望的输入格式：
        # - query: 用户查询（可选，用于意图识别）
        # - workflow_id: 工作流ID（用于直接指定工作流）
        # - 其他参数放在顶层，会被放入extensions中
        inputs = {
            "query": f"生成{start_date}到{end_date}的工作报告",  # 用于意图识别
            "workflow_id": "report_generation_workflow",  # 直接指定工作流
            "start_date": start_date,
            "end_date": end_date,
            **kwargs
        }
        
        result = await self.workflow_agent.invoke(inputs)
        return result
