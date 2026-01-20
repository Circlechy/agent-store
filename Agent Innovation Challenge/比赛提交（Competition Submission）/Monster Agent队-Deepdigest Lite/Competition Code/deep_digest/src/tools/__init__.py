"""
工具层模块
提供 SQLite 和 JSON 操作工具
"""

from .inbox_tools import (
    init_inbox_db,
    add_fragment,
    get_all_fragments,
    get_pending_fragments,
    delete_fragments,
    count_pending_fragments
)

from .memory_tools import (
    load_memory_index,
    save_knowledge_cards,
    get_all_cards,
    get_cards_by_type,
    search_cards_by_tag,
    get_card_by_id,
    count_cards,
    delete_card_by_id,
    update_card,
    search_cards,
    export_to_markdown,
    export_cards_to_markdown,
    get_random_card,
    get_cards_from_last_days
)

from .backup_tools import (
    create_backup,
    list_backups,
    restore_backup,
    delete_backup,
    auto_backup
)

__all__ = [
    # Inbox Tools (短期记忆 - SQLite)
    "init_inbox_db",
    "add_fragment",
    "get_all_fragments",
    "get_pending_fragments",
    "delete_fragments",
    "count_pending_fragments",
    
    # Memory Tools (长期记忆 - JSON)
    "load_memory_index",
    "save_knowledge_cards",
    "get_all_cards",
    "get_cards_by_type",
    "search_cards_by_tag",
    "get_card_by_id",
    "count_cards",
    "delete_card_by_id",
    "update_card",
    "search_cards",
    "export_to_markdown",
    "export_cards_to_markdown",
    "get_random_card",
    "get_cards_from_last_days",
    
    # Backup Tools (备份恢复)
    "create_backup",
    "list_backups",
    "restore_backup",
    "delete_backup",
    "auto_backup"
]
