# coding: utf-8
"""
自定义 WorkflowController - 优先使用 workflow_id 来选择工作流
"""
from typing import Optional
from openjiuwen.agent.workflow_agent.workflow_controller import WorkflowController
from openjiuwen.agent.common.schema import WorkflowSchema
from openjiuwen.core.agent.message.message import Message
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.agent.controller.intent_detection_controller import Intent, IntentType
from openjiuwen.core.common.logging import logger


class CustomWorkflowController(WorkflowController):
    """
    自定义 WorkflowController，优先使用 workflow_id 来选择工作流
    
    如果 inputs 中包含 workflow_id，直接使用它来选择工作流，而不是使用 LLM 检测
    """
    
    async def intent_detection(
        self,
        message: Message,
        runtime: Runtime
    ) -> Intent:
        """Intent detection: 优先使用 workflow_id，否则使用父类逻辑"""
        workflows = self.agent_config.workflows or []
        
        if not workflows:
            raise ValueError("No workflows configured for agent")
        
        # 检查 extensions 中是否有 workflow_id
        workflow_id = None
        if message.content.extensions:
            workflow_id = message.content.extensions.get("workflow_id")
        
        # 如果指定了 workflow_id，直接使用它
        if workflow_id:
            # 查找匹配的工作流
            # workflow_id 可能是 "workflow_name" 或 "{id}_{version}" 格式
            detected_workflow = None
            
            # 先尝试按 name 匹配
            for workflow in workflows:
                if workflow.name == workflow_id or workflow.id == workflow_id:
                    detected_workflow = workflow
                    break
            
            # 如果按 name 没找到，尝试按 "{id}_{version}" 格式匹配
            if not detected_workflow:
                for workflow in workflows:
                    workflow_full_id = f"{workflow.id}_{workflow.version}"
                    if workflow_full_id == workflow_id:
                        detected_workflow = workflow
                        break
            
            if detected_workflow:
                logger.info(
                    f"Using workflow_id '{workflow_id}' to select workflow: {detected_workflow.name}"
                )
                # 检查是否有中断的任务
                interrupted_task = self._find_interrupted_task(
                    detected_workflow, runtime
                )
                
                if interrupted_task:
                    should_resume = self._should_resume_interrupted_task(
                        interrupted_task, message, runtime
                    )
                    if should_resume:
                        logger.info(
                            f"Found interrupted task for workflow {detected_workflow.name}, resuming"
                        )
                        return Intent(
                            intent_type=IntentType.ResumeTask,
                            task=interrupted_task,
                            workflow=detected_workflow
                        )
                    else:
                        logger.info(
                            f"Found interrupted task with dict-type interruption, "
                            f"returning interruption again for workflow {detected_workflow.name}"
                        )
                        return Intent(
                            intent_type=IntentType.ResumeTask,
                            task=interrupted_task,
                            workflow=detected_workflow,
                            metadata={"return_interruption": True}
                        )
                else:
                    # 创建新任务
                    logger.info(
                        f"No interrupted task for workflow {detected_workflow.name}, creating new task"
                    )
                    new_task = self._create_new_task(message, detected_workflow)
                    return Intent(
                        intent_type=IntentType.ExecNewTask,
                        task=new_task,
                        workflow=detected_workflow
                    )
            else:
                logger.warning(
                    f"Workflow_id '{workflow_id}' not found in available workflows, "
                    f"falling back to LLM detection"
                )
        
        # 如果没有 workflow_id 或找不到匹配的工作流，使用父类的逻辑
        return await super().intent_detection(message, runtime)
