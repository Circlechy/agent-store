"""
长期记忆管理器

简化版实现，直接使用SQLite存储对话历史，确保可靠性。
"""
import os
import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class LongTermMemoryManager:
    """
    长期记忆管理器（简化版）
    
    直接使用SQLite存储对话历史，不依赖复杂的向量检索。
    """
    
    _instance: Optional['LongTermMemoryManager'] = None
    _initialized: bool = False
    
    def __init__(self, persist_dir: str = "./memory_data"):
        """初始化"""
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.persist_dir / "memory.db"
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 创建消息表（如果不存在）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        
        # 创建用户偏好表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                UNIQUE(user_id, key)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"数据库初始化完成: {self.db_path}")
    
    @classmethod
    async def get_instance(cls, **kwargs) -> 'LongTermMemoryManager':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls(**kwargs)
            cls._initialized = True
            logger.info("长期记忆管理器初始化完成")
        return cls._instance
    
    async def add_conversation(
        self,
        user_id: str,
        messages: List[Dict[str, str]],
        session_id: Optional[str] = None
    ):
        """
        添加对话到长期记忆
        
        Args:
            user_id: 用户ID
            messages: 对话消息列表 [{"role": "user/assistant", "content": "..."}]
            session_id: 会话ID (暂不使用)
        """
        if not messages:
            return
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            timestamp = datetime.now().isoformat()
            
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role and content:
                    cursor.execute(
                        "INSERT INTO conversation_history (user_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                        (user_id, role, content, timestamp)
                    )
            
            conn.commit()
            conn.close()
            logger.info(f"已添加 {len(messages)} 条消息到长期记忆")
            
        except Exception as e:
            logger.error(f"添加对话到长期记忆失败: {e}")
    
    async def get_recent_messages(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[Dict[str, str]]:
        """
        获取用户最近的消息（合并新旧两个表的数据）
        
        Args:
            user_id: 用户ID
            limit: 返回消息数量
            
        Returns:
            消息列表 [{"role": "user/assistant", "content": "...", "timestamp": "..."}]
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            all_rows = []
            
            # 从新表获取数据
            try:
                cursor.execute(
                    """SELECT role, content, timestamp FROM conversation_history 
                       WHERE user_id = ? 
                       ORDER BY timestamp DESC""",
                    (user_id,)
                )
                all_rows.extend(cursor.fetchall())
            except:
                pass
            
            # 从旧表获取数据 (openjiuwen 创建的)
            try:
                cursor.execute(
                    """SELECT role, content, timestamp FROM user_message 
                       WHERE user_id = ? 
                       ORDER BY timestamp DESC""",
                    (user_id,)
                )
                all_rows.extend(cursor.fetchall())
            except:
                pass
            
            conn.close()
            
            # 按时间排序并去重（基于内容）
            seen_contents = set()
            unique_rows = []
            # 先按时间排序（最新的在前）
            all_rows.sort(key=lambda x: x[2] if x[2] else "", reverse=True)
            
            for row in all_rows:
                content = row[1]
                if content not in seen_contents:
                    seen_contents.add(content)
                    unique_rows.append(row)
                    if len(unique_rows) >= limit:
                        break
            
            # 返回时间正序（最早的在前）
            messages = [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in reversed(unique_rows)]
            return messages
            
        except Exception as e:
            logger.error(f"获取最近消息失败: {e}")
            return []
    
    async def get_relevant_memories(
        self,
        user_id: str,
        query: str,
        top_k: int = 10
    ) -> str:
        """
        获取与当前查询相关的记忆（格式化为提示词）
        
        直接返回最近的对话历史，让LLM自己判断相关性。
        
        Args:
            user_id: 用户ID
            query: 当前用户查询
            top_k: 返回记忆数量
            
        Returns:
            格式化的记忆字符串
        """
        recent_messages = await self.get_recent_messages(user_id, limit=top_k)
        
        if not recent_messages:
            logger.debug(f"用户 {user_id} 没有历史对话记录")
            return ""
        
        memory_text = "# 用户历史对话记录（请参考这些信息回答用户问题）\n"
        for msg in recent_messages:
            role = "用户" if msg.get("role") == "user" else "助手"
            content = msg.get("content", "")
            # 截断过长的内容
            if len(content) > 150:
                content = content[:150] + "..."
            memory_text += f"- {role}: {content}\n"
        
        logger.info(f"检索到 {len(recent_messages)} 条历史记录")
        return memory_text
    
    async def set_user_preference(
        self,
        user_id: str,
        key: str,
        value: str
    ):
        """设置用户偏好"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            timestamp = datetime.now().isoformat()
            
            cursor.execute(
                """INSERT OR REPLACE INTO user_preferences (user_id, key, value, timestamp) 
                   VALUES (?, ?, ?, ?)""",
                (user_id, key, value, timestamp)
            )
            
            conn.commit()
            conn.close()
            logger.info(f"已设置用户偏好 {key}={value}")
            
        except Exception as e:
            logger.error(f"设置用户偏好失败: {e}")
    
    async def get_user_preference(
        self,
        user_id: str,
        key: str
    ) -> Optional[str]:
        """获取用户偏好"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT value FROM user_preferences WHERE user_id = ? AND key = ?",
                (user_id, key)
            )
            row = cursor.fetchone()
            conn.close()
            
            return row[0] if row else None
            
        except Exception as e:
            logger.error(f"获取用户偏好失败: {e}")
            return None
    
    async def list_user_preferences(
        self,
        user_id: str
    ) -> Dict[str, str]:
        """列出用户所有偏好"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT key, value FROM user_preferences WHERE user_id = ?",
                (user_id,)
            )
            rows = cursor.fetchall()
            conn.close()
            
            return {r[0]: r[1] for r in rows}
            
        except Exception as e:
            logger.error(f"列出用户偏好失败: {e}")
            return {}

    async def clear_conversation_history(
        self,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """清空对话历史（可按用户清理）"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            result = {"conversation_history": 0, "user_message": 0}

            if user_id:
                cursor.execute(
                    "DELETE FROM conversation_history WHERE user_id = ?",
                    (user_id,)
                )
                result["conversation_history"] = max(cursor.rowcount, 0)

                try:
                    cursor.execute(
                        "DELETE FROM user_message WHERE user_id = ?",
                        (user_id,)
                    )
                    result["user_message"] = max(cursor.rowcount, 0)
                except Exception:
                    result["user_message"] = 0
            else:
                cursor.execute("DELETE FROM conversation_history")
                result["conversation_history"] = max(cursor.rowcount, 0)

                try:
                    cursor.execute("DELETE FROM user_message")
                    result["user_message"] = max(cursor.rowcount, 0)
                except Exception:
                    result["user_message"] = 0

            conn.commit()
            conn.close()
            logger.info(
                f"已清空对话历史{f'（用户: {user_id}）' if user_id else '（全部）'}"
            )
            return result
        except Exception as e:
            logger.error(f"清空对话历史失败: {e}")
            return {"conversation_history": 0, "user_message": 0, "error": str(e)}


# 便捷函数
async def get_memory_manager(**kwargs) -> LongTermMemoryManager:
    """获取长期记忆管理器实例"""
    return await LongTermMemoryManager.get_instance(**kwargs)
