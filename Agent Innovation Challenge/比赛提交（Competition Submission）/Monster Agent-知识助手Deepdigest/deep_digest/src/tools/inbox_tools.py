"""
Inbox 工具模块 - SQLite 数据库操作
负责管理用户输入的碎片信息（短期记忆）

功能：
1. 初始化数据库
2. 添加碎片
3. 查询碎片（全部/待处理）
4. 删除碎片（熵减清理）
5. 统计待处理数量
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from ..config import DB_PATH, INBOX_SCHEMA


def get_connection():
    """
    获取数据库连接
    
    Returns:
        sqlite3.Connection: 数据库连接对象
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 使查询结果可以像字典一样访问
    return conn


def init_inbox_db() -> bool:
    """
    初始化 Inbox 数据库，创建 fragments 表和索引
    
    Returns:
        bool: 成功返回 True
    """
    try:
        conn = get_connection()
        
        # 创建表
        conn.execute(INBOX_SCHEMA)
        
        # 创建索引（提升查询性能）
        # 索引 1: status 字段（用于查询待处理碎片）
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON fragments(status)")
        
        # 索引 2: created_at 字段（用于按时间排序）
        conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON fragments(created_at)")
        
        # 索引 3: source 字段（用于按来源筛选）
        conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON fragments(source)")
        
        # 组合索引：status + created_at（优化待处理碎片的按时间查询）
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status_created ON fragments(status, created_at)")
        
        conn.commit()
        conn.close()
        print(f"✅ 数据库初始化成功（含索引优化）: {DB_PATH}")
        return True
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        return False


def add_fragment(content: str, source: str = "user") -> Optional[int]:
    """
    添加一条碎片记录（用户输入）
    
    Args:
        content: 碎片内容
        source: 来源标识，默认 "user"
    
    Returns:
        int: 插入记录的 ID，失败返回 None
    
    Example:
        >>> fragment_id = add_fragment("学习 FastAPI 的 Pydantic v2 适配")
        >>> print(f"碎片ID: {fragment_id}")
    """
    if not content.strip():
        print("⚠️ 警告: 碎片内容为空，跳过插入")
        return None
    
    try:
        conn = get_connection()
        cursor = conn.execute(
            "INSERT INTO fragments (content, source, status) VALUES (?, ?, ?)",
            (content.strip(), source, "pending")
        )
        fragment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"✅ 碎片已保存 (ID: {fragment_id})")
        return fragment_id
    except Exception as e:
        print(f"❌ 保存碎片失败: {e}")
        return None


def get_all_fragments() -> List[Dict]:
    """
    获取所有碎片记录（包括已处理和待处理）
    
    Returns:
        List[Dict]: 碎片列表，每个碎片是一个字典
    
    Example:
        >>> fragments = get_all_fragments()
        >>> for frag in fragments:
        ...     print(f"{frag['id']}: {frag['content']}")
    """
    try:
        conn = get_connection()
        cursor = conn.execute(
            "SELECT id, content, source, created_at, status FROM fragments ORDER BY created_at DESC"
        )
        rows = cursor.fetchall()
        conn.close()
        
        fragments = [dict(row) for row in rows]
        return fragments
    except Exception as e:
        print(f"❌ 查询碎片失败: {e}")
        return []


def get_pending_fragments() -> Dict:
    """
    获取所有待处理的碎片（status = 'pending'）
    
    Returns:
        Dict: 包含碎片JSON字符串的字典
            {"fragments": "[{\"id\": 1, ...}]"}
    
    Example:
        >>> result = get_pending_fragments()
        >>> print(f"待处理碎片数量: {len(json.loads(result['fragments']))}")
    """
    try:
        conn = get_connection()
        cursor = conn.execute(
            "SELECT id, content, source, created_at, status FROM fragments WHERE status = 'pending' ORDER BY created_at ASC"
        )
        rows = cursor.fetchall()
        conn.close()
        
        fragments = [dict(row) for row in rows]
        print(f"📥 提取待处理碎片: {len(fragments)} 条")
        # 转为JSON字符串
        import json
        return {"fragments": json.dumps(fragments, ensure_ascii=False, indent=2)}
    except Exception as e:
        print(f"❌ 查询待处理碎片失败: {e}")
        return {"fragments": "[]"}


def delete_fragments(fragment_ids: List[int]) -> int:
    """
    删除指定的碎片记录（熵减清理核心功能）
    
    Args:
        fragment_ids: 要删除的碎片 ID 列表
    
    Returns:
        int: 成功删除的记录数
    
    Example:
        >>> deleted_count = delete_fragments([1, 2, 3])
        >>> print(f"已删除 {deleted_count} 条碎片")
    """
    if not fragment_ids:
        print("⚠️ 警告: 删除列表为空")
        return 0
    
    try:
        conn = get_connection()
        placeholders = ",".join("?" * len(fragment_ids))
        cursor = conn.execute(
            f"DELETE FROM fragments WHERE id IN ({placeholders})",
            fragment_ids
        )
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        print(f"🗑️ 已删除 {deleted_count} 条碎片 (IDs: {fragment_ids})")
        return deleted_count
    except Exception as e:
        print(f"❌ 删除碎片失败: {e}")
        return 0


def count_pending_fragments() -> int:
    """
    统计待处理碎片数量（用于 UI 显示计数器）
    
    Returns:
        int: 待处理碎片数量
    
    Example:
        >>> count = count_pending_fragments()
        >>> print(f"待处理: {count} 条")
    """
    try:
        conn = get_connection()
        cursor = conn.execute("SELECT COUNT(*) as count FROM fragments WHERE status = 'pending'")
        result = cursor.fetchone()
        conn.close()
        
        return result["count"]
    except Exception as e:
        print(f"❌ 统计碎片失败: {e}")
        return 0


def mark_fragments_processed(fragment_ids: List[int]) -> int:
    """
    将碎片标记为已处理（可选功能，如果不想立即删除）
    
    Args:
        fragment_ids: 要标记的碎片 ID 列表
    
    Returns:
        int: 成功标记的记录数
    """
    if not fragment_ids:
        return 0
    
    try:
        conn = get_connection()
        placeholders = ",".join("?" * len(fragment_ids))
        cursor = conn.execute(
            f"UPDATE fragments SET status = 'processed' WHERE id IN ({placeholders})",
            fragment_ids
        )
        updated_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        print(f"✅ 已标记 {updated_count} 条碎片为已处理")
        return updated_count
    except Exception as e:
        print(f"❌ 标记碎片失败: {e}")
        return 0
