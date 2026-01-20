"""
数据备份与恢复工具
提供自动备份和手动恢复功能
"""

import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict
from ..config import DATA_DIR, DB_PATH, MEMORY_JSON_PATH


# 备份目录
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)


def create_backup(backup_name: Optional[str] = None) -> str:
    """
    创建数据备份
    
    Args:
        backup_name: 备份名称（可选），默认使用时间戳
    
    Returns:
        备份目录路径
    
    Example:
        >>> backup_path = create_backup()
        >>> print(f"备份已创建: {backup_path}")
    """
    # 生成备份名称
    if backup_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}"
    
    # 创建备份目录
    backup_path = BACKUP_DIR / backup_name
    backup_path.mkdir(parents=True, exist_ok=True)
    
    # 备份 SQLite 数据库
    if DB_PATH.exists():
        shutil.copy2(DB_PATH, backup_path / "deep_digest.db")
        print(f"✅ 已备份 SQLite 数据库")
    else:
        print(f"⚠️ SQLite 数据库不存在，跳过备份")
    
    # 备份 JSON 记忆文件
    if MEMORY_JSON_PATH.exists():
        shutil.copy2(MEMORY_JSON_PATH, backup_path / "memory_cards.json")
        print(f"✅ 已备份 JSON 记忆文件")
    else:
        print(f"⚠️ JSON 记忆文件不存在，跳过备份")
    
    # 创建备份元数据
    metadata = {
        "backup_name": backup_name,
        "created_at": datetime.now().isoformat(),
        "db_exists": DB_PATH.exists(),
        "json_exists": MEMORY_JSON_PATH.exists()
    }
    
    with open(backup_path / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 备份完成: {backup_path}")
    return str(backup_path)


def list_backups() -> List[Dict]:
    """
    列出所有备份
    
    Returns:
        备份列表，每个备份包含名称、时间和大小信息
    
    Example:
        >>> backups = list_backups()
        >>> for backup in backups:
        ...     print(f"{backup['name']} - {backup['created_at']}")
    """
    backups = []
    
    if not BACKUP_DIR.exists():
        return backups
    
    for backup_path in BACKUP_DIR.iterdir():
        if not backup_path.is_dir():
            continue
        
        # 读取元数据
        metadata_file = backup_path / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        else:
            # 如果没有元数据，从目录名推断
            metadata = {
                "backup_name": backup_path.name,
                "created_at": datetime.fromtimestamp(backup_path.stat().st_ctime).isoformat(),
                "db_exists": (backup_path / "deep_digest.db").exists(),
                "json_exists": (backup_path / "memory_cards.json").exists()
            }
        
        # 计算备份大小
        total_size = sum(f.stat().st_size for f in backup_path.rglob('*') if f.is_file())
        metadata["size_mb"] = round(total_size / 1024 / 1024, 2)
        metadata["path"] = str(backup_path)
        
        backups.append(metadata)
    
    # 按时间倒序排序
    backups.sort(key=lambda x: x["created_at"], reverse=True)
    
    return backups


def restore_backup(backup_name: str, restore_db: bool = True, restore_json: bool = True) -> bool:
    """
    恢复备份
    
    Args:
        backup_name: 备份名称或路径
        restore_db: 是否恢复 SQLite 数据库
        restore_json: 是否恢复 JSON 记忆文件
    
    Returns:
        恢复是否成功
    
    Example:
        >>> success = restore_backup("backup_20260107_100000")
        >>> if success:
        ...     print("恢复成功")
    """
    # 查找备份路径
    if Path(backup_name).exists():
        backup_path = Path(backup_name)
    else:
        backup_path = BACKUP_DIR / backup_name
    
    if not backup_path.exists():
        print(f"❌ 备份不存在: {backup_name}")
        return False
    
    try:
        # 恢复 SQLite 数据库
        if restore_db:
            db_backup = backup_path / "deep_digest.db"
            if db_backup.exists():
                # 先备份当前数据库（安全措施）
                if DB_PATH.exists():
                    safety_backup = DB_PATH.parent / f"deep_digest.db.before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    shutil.copy2(DB_PATH, safety_backup)
                    print(f"⚠️ 已创建安全备份: {safety_backup.name}")
                
                shutil.copy2(db_backup, DB_PATH)
                print(f"✅ 已恢复 SQLite 数据库")
            else:
                print(f"⚠️ 备份中没有 SQLite 数据库")
        
        # 恢复 JSON 记忆文件
        if restore_json:
            json_backup = backup_path / "memory_cards.json"
            if json_backup.exists():
                # 先备份当前文件（安全措施）
                if MEMORY_JSON_PATH.exists():
                    safety_backup = MEMORY_JSON_PATH.parent / f"memory_cards.json.before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    shutil.copy2(MEMORY_JSON_PATH, safety_backup)
                    print(f"⚠️ 已创建安全备份: {safety_backup.name}")
                
                shutil.copy2(json_backup, MEMORY_JSON_PATH)
                print(f"✅ 已恢复 JSON 记忆文件")
            else:
                print(f"⚠️ 备份中没有 JSON 记忆文件")
        
        print(f"✅ 备份恢复完成: {backup_name}")
        return True
    
    except Exception as e:
        print(f"❌ 恢复备份失败: {e}")
        return False


def delete_backup(backup_name: str) -> bool:
    """
    删除备份
    
    Args:
        backup_name: 备份名称或路径
    
    Returns:
        删除是否成功
    
    Example:
        >>> success = delete_backup("backup_20260107_100000")
    """
    # 查找备份路径
    if Path(backup_name).exists():
        backup_path = Path(backup_name)
    else:
        backup_path = BACKUP_DIR / backup_name
    
    if not backup_path.exists():
        print(f"❌ 备份不存在: {backup_name}")
        return False
    
    try:
        shutil.rmtree(backup_path)
        print(f"✅ 已删除备份: {backup_name}")
        return True
    except Exception as e:
        print(f"❌ 删除备份失败: {e}")
        return False


def auto_backup(max_backups: int = 10) -> Optional[str]:
    """
    自动备份（清理旧备份）
    
    Args:
        max_backups: 保留的最大备份数量
    
    Returns:
        新创建的备份路径，失败返回 None
    
    Example:
        >>> backup_path = auto_backup(max_backups=5)
    """
    # 创建新备份
    backup_path = create_backup()
    
    # 清理旧备份
    backups = list_backups()
    
    if len(backups) > max_backups:
        # 删除最旧的备份
        old_backups = backups[max_backups:]
        for backup in old_backups:
            print(f"🗑️ 清理旧备份: {backup['backup_name']}")
            delete_backup(backup['backup_name'])
    
    return backup_path

