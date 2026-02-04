"""
上下文管理器

基于 openJiuwen ContextEngine 的适配层，添加业务逻辑
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger

from openjiuwen.core.context_engine.engine import ContextEngine
from openjiuwen.core.context_engine.context import AgentContext
from openjiuwen.core.utils.llm.messages import HumanMessage, AIMessage, SystemMessage


class ContextManager:
    """
    上下文管理器 - 基于 openJiuwen ContextEngine 的适配层
    
    职责分层：
    1. 对话历史管理 → 使用 openJiuwen 的 ContextEngine（委托）
    2. 文件上下文管理 → 自定义实现（业务逻辑）
    3. 执行状态管理 → 自定义实现（业务逻辑）
    4. 元数据管理 → 自定义实现（业务逻辑）
    """
    
    def __init__(self, context_engine: ContextEngine, session_id: str = "default"):
        """
        初始化上下文管理器
        
        Args:
            context_engine: openJiuwen 的 ContextEngine 实例（来自 BaseAgent）
            session_id: 会话 ID
        """
        # 使用 BaseAgent 的 context_engine（不要创建新的）
        self._context_engine = context_engine
        self._session_id = session_id
        
        # 业务逻辑：文件上下文、执行状态、元数据
        self.generated_files: Dict[str, str] = {}
        self.execution_state: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}
    
    @property
    def context_engine(self) -> ContextEngine:
        """获取 openJiuwen 的 ContextEngine 实例"""
        return self._context_engine
    
    @property
    def agent_context(self) -> AgentContext:
        """获取当前会话的 AgentContext"""
        return self._context_engine.get_agent_context(self._session_id)
    
    def add_conversation(self, role: str, content: str, metadata: Optional[Dict] = None):
        """
        添加对话记录（使用 ContextEngine）
        
        Args:
            role: 角色（user/assistant/system）
            content: 内容
            metadata: 元数据（作为 tags）
        """
        # 使用 ContextEngine 管理对话历史
        if role == "user":
            message = HumanMessage(content=content)
        elif role == "assistant":
            message = AIMessage(content=content)
        else:
            message = SystemMessage(content=content)
        
        # 添加消息（metadata 作为 tags）
        self.agent_context.add_message(message, tags=metadata or {})
    
    def get_conversation_history(self, num: int = -1) -> List[Dict[str, Any]]:
        """
        获取对话历史（从 ContextEngine）
        
        Args:
            num: 消息数量（-1 表示全部）
            
        Returns:
            对话历史列表
        """
        messages = self.agent_context.get_messages(num=num)
        
        # 转换为字典格式（兼容现有接口）
        history = []
        for msg in messages:
            history.append({
                "role": getattr(msg, 'role', 'assistant'),
                "content": getattr(msg, 'content', str(msg)),
                "timestamp": getattr(msg, 'timestamp', None)
            })
        
        return history
    
    def update_generated_files(self, files: Dict[str, str]):
        """更新生成的文件（业务逻辑）"""
        self.generated_files.update(files)
        logger.debug(f"更新生成文件: {len(files)} 个文件")
    
    def add_test_result(self, result: Dict[str, Any]):
        """添加测试结果（业务逻辑）"""
        if "test_results" not in self.execution_state:
            self.execution_state["test_results"] = []
        self.execution_state["test_results"].append(result)
    
    def get_context(self, max_tokens: int = 4000) -> Dict[str, Any]:
        """
        获取完整上下文（组合 ContextEngine 和业务逻辑）
        
        Args:
            max_tokens: 最大 token 数（用于压缩）
            
        Returns:
            压缩后的上下文
        """
        # 从 ContextEngine 获取对话历史
        conversation_history = self.get_conversation_history(num=20)  # 获取最近20条
        
        # 压缩生成的文件（业务逻辑）
        compressed_files = self._compress_files(max_tokens // 4)
        
        return {
            "conversation_history": conversation_history,  # 来自 ContextEngine
            "generated_files": compressed_files,  # 业务逻辑
            "test_results": self.execution_state.get("test_results", [])[-5:],  # 业务逻辑
            "metadata": self.metadata,  # 业务逻辑
        }
    
    def _compress_files(self, max_tokens: int) -> Dict[str, str]:
        """压缩文件内容（业务逻辑）"""
        # 简单实现：只保留关键文件
        important_files = ["main.py", "workflow_builder.py", "components.py", "config.py", "local_agent.py", "leader_agent.py", "worker_agent.py"]
        return {
            name: content
            for name, content in self.generated_files.items()
            if name in important_files
        }
    
    def clear_context(self):
        """清除上下文"""
        self.generated_files.clear()
        self.execution_state.clear()
        self.metadata.clear()
        self._context_engine.clear_context(self._session_id)
        logger.debug(f"清除上下文: {self._session_id}")
