"""
会话管理器

管理会话的创建和生命周期，底层使用 Runtime 的 session_id
"""
from typing import Dict, Optional, List
import uuid
import time
from loguru import logger

from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.context_engine.engine import ContextEngine
from app.context.context_manager import ContextManager


class SessionManager:
    """会话管理器 - 管理会话的创建和生命周期"""
    
    def __init__(self, context_engine: ContextEngine):
        """
        初始化会话管理器
        
        Args:
            context_engine: openJiuwen 的 ContextEngine（来自 BaseAgent）
        """
        self._context_engine = context_engine
        self._sessions: Dict[str, Dict[str, any]] = {}  # session_id -> {context_manager, parent_runtime, title, created_at}
    
    def create_session(
        self,
        parent_runtime: Optional[Runtime] = None,
        session_id: Optional[str] = None,
        title: Optional[str] = None
    ) -> str:
        """
        创建会话
        
        Args:
            parent_runtime: 父 Runtime（可选）
            session_id: 会话 ID（可选，如果不提供则自动生成）
            title: 会话标题（可选）
            
        Returns:
            会话 ID
        """
        if session_id is None:
            session_id = uuid.uuid4().hex
        
        # 创建 ContextManager（使用共享的 context_engine）
        context_manager = ContextManager(
            context_engine=self._context_engine,
            session_id=session_id
        )
        
        # 注册会话
        self._sessions[session_id] = {
            "context_manager": context_manager,
            "parent_runtime": parent_runtime,
            "title": title,
            "created_at": time.time()
        }
        
        logger.debug(f"创建会话: {session_id}, 标题: {title}")
        return session_id
    
    def get_context_manager(self, session_id: str) -> Optional[ContextManager]:
        """获取会话的 ContextManager"""
        session = self._sessions.get(session_id)
        return session.get("context_manager") if session else None
    
    def get_session(self, session_id: str) -> Optional[Dict[str, any]]:
        """获取会话信息"""
        return self._sessions.get(session_id)
    
    def close_session(self, session_id: str):
        """关闭会话"""
        if session_id in self._sessions:
            context_manager = self._sessions[session_id].get("context_manager")
            if context_manager:
                context_manager.clear_context()
            del self._sessions[session_id]
            logger.debug(f"关闭会话: {session_id}")
    
    def list_sessions(self) -> List[str]:
        """列出所有会话 ID"""
        return list(self._sessions.keys())
    
    def get_conversation_history(self, session_id: str) -> List[str]:
        """
        获取会话历史（所有用户消息）
        
        Args:
            session_id: 会话ID
        
        Returns:
            用户消息列表（初始需求 + 各轮修改需求）
        """
        context_manager = self.get_context_manager(session_id)
        if not context_manager:
            logger.warning(f"会话不存在: {session_id}")
            return []
        
        # 从 ContextManager 获取完整对话历史
        history = context_manager.get_conversation_history(num=-1)
        
        # 提取所有用户消息（role == "user" 或 "human"）
        user_messages = []
        for msg in history:
            role = msg.get("role", "").lower()
            content = msg.get("content", "")
            if role in ["user", "human"] and content:
                user_messages.append(content)
        
        return user_messages