"""
统一生成服务

协调主协调器完成智能体生成任务，提供 SSE 流式响应
"""
from typing import Dict, Any, AsyncIterator, Optional
from pathlib import Path
from loguru import logger

from openjiuwen.core.context_engine.engine import ContextEngine
from openjiuwen.agent.config.base import AgentConfig
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo

from app.config.settings import get_settings
from app.context.context_manager import ContextManager
from app.session.session_manager import SessionManager
from app.skills.skill_manager import SkillManager
from app.wisdom.wisdom_manager import WisdomManager
from app.orchestrator.master_orchestrator import MasterOrchestrator
from app.models.events import SSEEvent, EventType
from app.models.task import AgentMode
from app.utils import normalize_agent_mode


class UnifiedGenerationService:
    """统一生成服务"""
    
    def __init__(self):
        """初始化服务"""
        self.settings = get_settings()
        
        # 创建基础设施组件
        self.context_engine = ContextEngine(agent_id="master_orchestrator")
        self.context_manager = ContextManager(
            context_engine=self.context_engine,
            session_id="default"
        )
        self.session_manager = SessionManager(context_engine=self.context_engine)
        self.skill_manager = SkillManager()
        self.wisdom_manager = WisdomManager()
        
        logger.info("初始化 UnifiedGenerationService")
    
    async def generate(
        self,
        user_input: str,
        agent_mode: str = "workflow",
        workflow_name: str = "default",
        max_iterations: int = 3

    ) -> AsyncIterator[str]:
        """
        生成智能体（SSE 流式响应）
        
        Args:
            user_input: 用户输入
            agent_mode: Agent 模式（react/workflow/multi_agent）
            workflow_name: 工作流名称
            max_iterations: 最大迭代次数
        
        Yields:
            SSE 事件字符串（格式：data: {json}\n\n）
        """
        import json
        import time
        
        try:
            # 规范化 agent_mode（向后兼容：将 "agent" 映射到 "react"）
            agent_mode = normalize_agent_mode(agent_mode)
            
            # 创建主协调器
            master_orchestrator = self._create_master_orchestrator()
            
            # 调用主协调器的流式接口
            inputs = {
                "user_input": user_input,
                "agent_mode": agent_mode,
                "workflow_name": workflow_name
            }
            
            # 创建 Runtime（使用具体实现 AgentRuntime）
            from openjiuwen.core.runtime.agent import AgentRuntime
            session_id = self.session_manager.create_session(title="Main Session")
            runtime = AgentRuntime(session_id=session_id)
            
            # 使用 stream() 方法获取流式事件
            async for event in master_orchestrator.stream(inputs, runtime):
                # 确保事件格式正确
                if isinstance(event, dict):
                    # 确保包含所有必需的字段
                    event_dict = {
                        "type": event.get("type", "unknown"),
                        "message": event.get("message", ""),
                        "data": event.get("data", {}),
                        "timestamp": event.get("timestamp", time.time())
                    }
                    
                    # 添加可选字段（如果存在）
                    if "step_id" in event:
                        event_dict["step_id"] = event["step_id"]
                    if "step_name" in event:
                        event_dict["step_name"] = event["step_name"]
                    
                    # 转换为 SSE 格式
                    yield f"data: {json.dumps(event_dict, ensure_ascii=False)}\n\n"
                else:
                    # 如果不是字典，尝试转换为字符串
                    logger.warning(f"收到非字典类型事件: {type(event)}")
                    yield f"data: {json.dumps({'type': 'unknown', 'message': str(event)}, ensure_ascii=False)}\n\n"
        
        except Exception as e:
            logger.error(f"生成过程发生错误: {e}", exc_info=True)
            error_event = {
                "type": "error",
                "message": str(e),
                "data": {"error": str(e)},
                "timestamp": time.time()
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
    
    async def modify(
        self,
        workflow_dir: str,
        modification_request: str,
        conversation_id: Optional[str] = None,
        max_iterations: int = 3
    ) -> AsyncIterator[str]:
        """
        修改工作流（SSE 流式响应）
        
        Args:
            workflow_dir: 工作流目录路径（相对或绝对路径）
            modification_request: 当前修改需求（自然语言）
            conversation_id: 会话ID（用于获取历史需求）
            max_iterations: 最大迭代次数
        
        Yields:
            SSE 事件字符串（格式：data: {json}\n\n）
        """
        import json
        import time
        
        try:
            # 创建主协调器
            master_orchestrator = self._create_master_orchestrator()
            
            # 将相对路径转换为绝对路径
            workflow_path = Path(workflow_dir)
            if not workflow_path.is_absolute():
                project_root = Path(__file__).parent.parent.parent.parent
                workflow_dir = str(project_root / workflow_dir)
            
            # 调用主协调器的流式接口
            inputs = {
                "is_modification": True,
                "workflow_dir": workflow_dir,
                "modification_request": modification_request,
                "conversation_id": conversation_id,
                "max_iterations": max_iterations
            }
            
            # 创建 Runtime（使用具体实现 AgentRuntime）
            from openjiuwen.core.runtime.agent import AgentRuntime
            # 使用提供的 conversation_id 或创建新的会话
            if conversation_id:
                session_id = self.session_manager.create_session(
                    session_id=conversation_id,
                    title="Modify Session"
                )
            else:
                session_id = self.session_manager.create_session(title="Modify Session")
            
            runtime = AgentRuntime(session_id=session_id)
            
            # 使用 stream() 方法获取流式事件
            async for event in master_orchestrator.stream(inputs, runtime):
                # 确保事件格式正确
                if isinstance(event, dict):
                    # 确保包含所有必需的字段
                    event_dict = {
                        "type": event.get("type", "unknown"),
                        "message": event.get("message", ""),
                        "data": event.get("data", {}),
                        "timestamp": event.get("timestamp", time.time())
                    }
                    
                    # 添加可选字段（如果存在）
                    if "step_id" in event:
                        event_dict["step_id"] = event["step_id"]
                    if "step_name" in event:
                        event_dict["step_name"] = event["step_name"]
                    
                    # 转换为 SSE 格式
                    yield f"data: {json.dumps(event_dict, ensure_ascii=False)}\n\n"
                else:
                    # 如果不是字典，尝试转换为字符串
                    logger.warning(f"收到非字典类型事件: {type(event)}")
                    yield f"data: {json.dumps({'type': 'unknown', 'message': str(event)}, ensure_ascii=False)}\n\n"
        
        except Exception as e:
            logger.error(f"修改过程发生错误: {e}", exc_info=True)
            error_event = {
                "type": "error",
                "message": str(e),
                "data": {"error": str(e)},
                "timestamp": time.time()
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
    
    def _create_master_orchestrator(self) -> MasterOrchestrator:
        """创建主协调器"""
        settings = self.settings
        
        # 创建模型配置
        logger.info(f"📦 创建模型配置: provider={settings.model.provider}, model={settings.model.model_name}")
        model_config = ModelConfig(
            model_provider=settings.model.provider,
            model_info=BaseModelInfo(
                api_key=settings.model.api_key,
                api_base=settings.model.api_base,
                model=settings.model.model_name,  # 使用别名 'model' 而非 'model_name'
                temperature=0.1,  # 主协调器使用低温度
                top_p=0.9,
                timeout=settings.model.timeout
            )
        )
        
        # 创建 Agent 配置
        agent_config = AgentConfig(
            id="master_orchestrator",
            version="1.0.0",
            description="主协调器，负责任务协调和委托",
            model=model_config
        )
        
        return MasterOrchestrator(
            agent_config=agent_config,
            context_manager=self.context_manager,
            session_manager=self.session_manager,
            skill_manager=self.skill_manager,
            wisdom_manager=self.wisdom_manager
        )
    
    def _ensure_workflow_dir(self, workflow_name: str) -> Path:
        """确保工作流目录存在"""
        project_root = Path(__file__).parent.parent.parent.parent
        workflow_dir = project_root / self.settings.experiments_dir / workflow_name
        workflow_dir.mkdir(parents=True, exist_ok=True)
        return workflow_dir
