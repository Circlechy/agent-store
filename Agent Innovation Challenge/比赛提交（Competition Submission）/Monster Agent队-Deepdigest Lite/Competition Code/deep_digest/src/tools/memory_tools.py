"""
Memory 工具模块 - JSON 长期记忆管理
负责管理知识卡片（长期记忆）

功能：
1. 加载记忆索引（轻量级，用于 LLM 上下文）
2. 保存知识卡片（LLM 生成的结构化知识）
3. 查询卡片
"""

import json
import random
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from ..config import MEMORY_JSON_PATH


def _ensure_memory_file():
    """
    确保 memory_cards.json 文件存在
    如果不存在，创建初始结构
    """
    if not MEMORY_JSON_PATH.exists():
        MEMORY_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        initial_data = {"cards": []}
        with open(MEMORY_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, ensure_ascii=False, indent=2)
        print(f"✅ 创建长期记忆文件: {MEMORY_JSON_PATH}")


def get_random_card() -> Optional[str]:
    """
    随机抽取一张知识卡片（用于“灵感漫游”功能）
    
    Returns:
        Optional[str]: 卡片的完整 JSON 字符串，如果知识库为空则返回 None
    
    Example:
        >>> card_json = get_random_card()
        >>> if card_json:
        ...     card = json.loads(card_json)
        ...     print(f"随机抽到: {card['title']}")
    """
    _ensure_memory_file()
    
    try:
        with open(MEMORY_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cards = data.get("cards", [])
        
        if not cards:
            print("🎲 知识库为空，无法随机抽取")
            return None
        
        # 随机选择一张卡片
        random_card = random.choice(cards)
        print(f"🎲 随机抽取卡片: {random_card.get('title', 'Unknown')}")
        
        # 返回精简版卡片（排除 embedding 等大字段）
        slim_card = {k: v for k, v in random_card.items() if k != "embedding"}
        
        return json.dumps(slim_card, ensure_ascii=False, indent=2)
    
    except Exception as e:
        print(f"❌ 随机抽取卡片失败: {e}")
        return None


def load_memory_index() -> Dict:
    """
    加载记忆索引（轻量级）
    
    **核心设计**: 只返回 id, title, tags，不返回完整内容
    这是为了给 LLM 做上下文时节省 Token
    
    Returns:
        Dict: 包含记忆索引JSON字符串的字典
            {"memory_index": "[{\"id\": \"uuid1\", ...}]"}
    
    Example:
        >>> result = load_memory_index()
        >>> print(f"现有 {len(json.loads(result['memory_index']))} 条记忆")
    """
    _ensure_memory_file()
    
    try:
        with open(MEMORY_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cards = data.get("cards", [])
        
        # 只提取轻量级信息
        index = [
            {
                "id": card.get("id"),
                "title": card.get("title"),
                "tags": card.get("tags", [])
            }
            for card in cards
        ]
        
        print(f"📚 加载记忆索引: {len(index)} 条")
        # 转为JSON字符串
        return {"memory_index": json.dumps(index, ensure_ascii=False, indent=2)}
    
    except Exception as e:
        print(f"❌ 加载记忆索引失败: {e}")
        return {"memory_index": "[]"}


def save_knowledge_cards(cards: List[Dict]) -> str:
    """
    保存知识卡片到长期记忆
    
    **用途**: Night Agent 生成卡片后调用此函数归档
    **新增**: 自动为每张卡片生成 Embedding 向量
    
    Args:
        cards: 卡片列表，每张卡片应包含以下字段：
            - id (str): 唯一标识
            - type (str): 类型 (tech/todo/idea)
            - title (str): 标题
            - tags (List[str]): 标签
            - summary (str): 摘要
            - snippet (Dict): 代码片段
            - created_at (str): 创建时间
            - related_card_ids (List[str]): 关联的旧记忆ID
            - source_fragment_ids (List[int]): 来源碎片ID
    
    Returns:
        str: 操作结果消息
    
    Example:
        >>> cards = [
        ...     {
        ...         "id": "uuid-123",
        ...         "type": "tech",
        ...         "title": "FastAPI Pydantic v2 适配",
        ...         "tags": ["Python", "FastAPI"],
        ...         "summary": "Pydantic v2 废弃了 .dict() 方法...",
        ...         "snippet": {},
        ...         "created_at": "2026-01-07T10:30:00",
        ...         "related_card_ids": [],
        ...         "source_fragment_ids": [1, 2]
        ...     }
        ... ]
        >>> result = save_knowledge_cards(cards)
        >>> print(result)
        ✅ 已归档 1 张卡片 (含向量)
    """
    _ensure_memory_file()
    
    if not cards:
        return "⚠️ 没有卡片需要保存"
    
    try:
        # 1. 自动生成 Embedding（在保存前）
        from .embedding_tools import get_embedding
        
        embedding_success_count = 0
        embedding_fail_count = 0
        
        for card in cards:
            # 如果卡片已有 embedding，跳过
            if card.get("embedding"):
                continue
            
            # 拼接 title 和 summary 作为输入文本
            title = card.get("title", "")
            summary = card.get("summary", "")
            text = f"{title}\n{summary}".strip()
            
            if not text:
                # 如果没有文本内容，设置为空列表
                card["embedding"] = []
                continue
            
            try:
                # 调用 Embedding API
                embedding = get_embedding(text)
                
                if embedding:
                    card["embedding"] = embedding
                    embedding_success_count += 1
                else:
                    # API 返回空向量，设置为空列表
                    card["embedding"] = []
                    embedding_fail_count += 1
                    
            except Exception as e:
                # Embedding 生成失败，不阻塞保存流程
                print(f"⚠️ 卡片 {card.get('id')} 的 Embedding 生成失败: {e}")
                card["embedding"] = []
                embedding_fail_count += 1
        
        # 2. 读取现有数据
        with open(MEMORY_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        existing_cards = data.get("cards", [])
        
        # 3. 追加新卡片
        existing_cards.extend(cards)
        data["cards"] = existing_cards
        
        # 4. 写回文件
        with open(MEMORY_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 5. 生成结果消息
        msg = f"✅ 已归档 {len(cards)} 张卡片"
        if embedding_success_count > 0:
            msg += f" (含向量: {embedding_success_count})"
        if embedding_fail_count > 0:
            msg += f" (向量失败: {embedding_fail_count})"
        
        print(msg)
        return msg
    
    except Exception as e:
        error_msg = f"❌ 保存卡片失败: {e}"
        print(error_msg)
        return error_msg


def get_cards_from_last_days(days: int = 7) -> List[Dict]:
    """
    获取最近 N 天的知识卡片（精简版，不含 embedding）
    
    Args:
        days: 天数，默认 7 天
    
    Returns:
        List[Dict]: 精简的卡片列表（不含 embedding）
    
    Example:
        >>> cards = get_cards_from_last_days(7)
        >>> print(f"过去7天有 {len(cards)} 张卡片")
    """
    from datetime import datetime, timedelta
    
    _ensure_memory_file()
    
    try:
        with open(MEMORY_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cards = data.get("cards", [])
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")
        
        recent_cards = []
        for card in cards:
            card_date = card.get("created_at", "")[:10]  # 取日期部分
            if card_date >= cutoff_str:
                # 返回精简版卡片（排除 embedding）
                slim_card = {k: v for k, v in card.items() if k != "embedding"}
                recent_cards.append(slim_card)
        
        print(f"📅 获取最近 {days} 天卡片: {len(recent_cards)} 条")
        return recent_cards
    
    except Exception as e:
        print(f"❌ 获取最近卡片失败: {e}")
        return []


def get_all_cards() -> List[Dict]:
    """
    获取所有知识卡片（包含完整内容）
    
    Returns:
        List[Dict]: 完整的卡片列表
    
    Example:
        >>> cards = get_all_cards()
        >>> for card in cards:
        ...     print(f"{card['title']} - {card['type']}")
    """
    _ensure_memory_file()
    
    try:
        with open(MEMORY_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cards = data.get("cards", [])
        print(f"📚 加载完整卡片: {len(cards)} 条")
        return cards
    
    except Exception as e:
        print(f"❌ 加载卡片失败: {e}")
        return []


def get_cards_by_type(card_type: str) -> List[Dict]:
    """
    按类型获取卡片
    
    Args:
        card_type: 卡片类型 (tech/todo/idea)
    
    Returns:
        List[Dict]: 指定类型的卡片列表
    
    Example:
        >>> tech_cards = get_cards_by_type("tech")
        >>> print(f"技术卡片: {len(tech_cards)} 条")
    """
    all_cards = get_all_cards()
    filtered = [card for card in all_cards if card.get("type") == card_type]
    return filtered


def search_cards_by_tag(tag: str) -> List[Dict]:
    """
    按标签搜索卡片
    
    Args:
        tag: 标签名称
    
    Returns:
        List[Dict]: 包含该标签的卡片列表
    
    Example:
        >>> python_cards = search_cards_by_tag("Python")
        >>> print(f"Python 相关: {len(python_cards)} 条")
    """
    all_cards = get_all_cards()
    filtered = [
        card for card in all_cards 
        if tag in card.get("tags", [])
    ]
    return filtered


def get_card_by_id(card_id: str) -> Optional[Dict]:
    """
    根据 ID 获取单张卡片
    
    Args:
        card_id: 卡片唯一标识
    
    Returns:
        Dict: 卡片对象，不存在返回 None
    
    Example:
        >>> card = get_card_by_id("uuid-123")
        >>> if card:
        ...     print(card['title'])
    """
    all_cards = get_all_cards()
    for card in all_cards:
        if card.get("id") == card_id:
            return card
    return None


def count_cards() -> Dict[str, int]:
    """
    统计卡片数量
    
    Returns:
        Dict: 统计信息
            {
                "total": 10,
                "tech": 5,
                "todo": 3,
                "idea": 2
            }
    
    Example:
        >>> stats = count_cards()
        >>> print(f"总计: {stats['total']} 张")
    """
    all_cards = get_all_cards()
    
    stats = {
        "total": len(all_cards),
        "tech": 0,
        "todo": 0,
        "idea": 0
    }
    
    for card in all_cards:
        card_type = card.get("type", "")
        if card_type in stats:
            stats[card_type] += 1
    
    return stats


# ===================== 测试代码 =====================
if __name__ == "__main__":
    import uuid
    
    print("=" * 50)
    print("Memory Tools 测试")
    print("=" * 50)
    
    # 1. 测试索引加载
    print("\n[测试] 加载记忆索引...")
    index = load_memory_index()
    print(f"索引数量: {len(index)}")
    
    # 2. 测试保存卡片
    print("\n[测试] 保存知识卡片...")
    test_cards = [
        {
            "id": str(uuid.uuid4()),
            "type": "tech",
            "title": "FastAPI Pydantic v2 适配指南",
            "tags": ["Python", "FastAPI"],
            "summary": "Pydantic v2 废弃了 .dict() 方法，需要使用 model_dump()",
            "snippet": {
                "before": "user.dict()",
                "after": "user.model_dump()"
            },
            "created_at": datetime.now().isoformat(),
            "related_card_ids": [],
            "source_fragment_ids": [1, 2]
        },
        {
            "id": str(uuid.uuid4()),
            "type": "todo",
            "title": "明天下午3点技术评审会",
            "tags": ["会议"],
            "summary": "讨论新架构设计方案",
            "snippet": {},
            "created_at": datetime.now().isoformat(),
            "related_card_ids": [],
            "source_fragment_ids": [3]
        }
    ]
    
    result = save_knowledge_cards(test_cards)
    print(f"结果: {result}")
    
    # 3. 测试查询
    print("\n[测试] 查询所有卡片...")
    all_cards = get_all_cards()
    print(f"总卡片数: {len(all_cards)}")
    
    # 4. 测试统计
    print("\n[测试] 统计卡片...")
    stats = count_cards()
    print(f"统计信息: {stats}")
    
    # 5. 测试按类型查询
    print("\n[测试] 按类型查询...")
    tech_cards = get_cards_by_type("tech")
    print(f"技术卡片: {len(tech_cards)} 条")
    
    # 6. 测试按标签搜索
    print("\n[测试] 按标签搜索...")
    python_cards = search_cards_by_tag("Python")
    print(f"Python 相关: {len(python_cards)} 条")


def delete_card_by_id(card_id: str) -> bool:
    """
    根据 ID 删除知识卡片
    
    Args:
        card_id: 卡片的唯一标识符
    
    Returns:
        bool: 删除成功返回 True，未找到卡片返回 False
    
    Example:
        >>> success = delete_card_by_id("uuid-123")
        >>> print(f"删除结果: {'成功' if success else '未找到'}")
    """
    _ensure_memory_file()
    
    try:
        # 读取当前所有卡片
        with open(MEMORY_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cards = data.get("cards", [])
        original_count = len(cards)
        
        # 过滤掉指定 ID 的卡片
        filtered_cards = [card for card in cards if card.get("id") != card_id]
        
        # 检查是否有卡片被删除
        if len(filtered_cards) == original_count:
            print(f"⚠️ 未找到 ID 为 {card_id} 的卡片")
            return False
        
        # 写回文件
        data["cards"] = filtered_cards
        with open(MEMORY_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 成功删除卡片: {card_id}")
        return True
    
    except Exception as e:
        print(f"❌ 删除卡片失败: {e}")
        return False


def update_card(card_id: str, updates: Dict) -> bool:
    """
    更新知识卡片
    
    Args:
        card_id: 卡片的唯一标识符
        updates: 要更新的字段字典
            可更新字段: title, tags, summary, snippet, type
    
    Returns:
        bool: 更新成功返回 True，失败返回 False
    
    Example:
        >>> updates = {
        ...     "title": "新标题",
        ...     "tags": ["Python", "FastAPI"],
        ...     "summary": "更新后的摘要"
        ... }
        >>> success = update_card("uuid-123", updates)
    """
    _ensure_memory_file()
    
    try:
        # 读取当前所有卡片
        with open(MEMORY_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cards = data.get("cards", [])
        card_found = False
        
        # 查找并更新卡片
        for card in cards:
            if card.get("id") == card_id:
                card_found = True
                
                # 允许更新的字段
                allowed_fields = ["title", "tags", "summary", "snippet", "type", "deadline"]
                
                for field, value in updates.items():
                    if field in allowed_fields:
                        card[field] = value
                    else:
                        print(f"⚠️ 忽略不允许更新的字段: {field}")
                
                # 更新修改时间
                card["updated_at"] = datetime.now().isoformat()
                
                break
        
        if not card_found:
            print(f"⚠️ 未找到 ID 为 {card_id} 的卡片")
            return False
        
        # 写回文件
        with open(MEMORY_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 成功更新卡片: {card_id}")
        return True
    
    except Exception as e:
        print(f"❌ 更新卡片失败: {e}")
        return False


def search_cards(query: str, use_semantic: bool = True, similarity_threshold: float = 0.3) -> str:
    """
    搜索知识卡片（用于 RAG 问答）
    优先使用语义搜索，失败时降级到关键词搜索
    支持按类型过滤（当查询包含 todo/待办/tech/技术/idea/想法 等关键词时）
    
    Args:
        query: 搜索关键词
        use_semantic: 是否使用语义搜索（默认 True）
        similarity_threshold: 语义搜索相似度阈值（默认 0.3）
    
    Returns:
        str: 格式化的 JSON 字符串，包含匹配卡片的详细信息
    
    Example:
        >>> result = search_cards("Python")
        >>> print(result)  # 返回包含 "Python" 的所有卡片
    """
    _ensure_memory_file()
    
    matched_cards = []
    matched_card_ids = set()  # 用于去重
    search_method = "关键词搜索"
    
    # 检测是否包含类型关键词
    query_lower = query.lower()
    type_filter = None
    type_keywords = {
        "todo": ["todo", "待办", "任务", "要做"],
        "tech": ["tech", "技术", "代码", "编程"],
        "idea": ["idea", "想法", "灵感", "点子"]
    }
    
    for card_type, keywords in type_keywords.items():
        if any(kw in query_lower for kw in keywords):
            type_filter = card_type
            break
    
    # 尝试语义搜索
    if use_semantic:
        try:
            # 动态导入 embedding_tools（避免循环依赖）
            from .embedding_tools import search_cards_semantic, _openai_client
            
            # 检查 embedding 客户端是否已初始化
            if _openai_client is not None:
                # 使用语义搜索
                results = search_cards_semantic(query, top_k=10, similarity_threshold=similarity_threshold)
                
                if results:
                    search_method = "语义搜索"
                    for card, similarity in results:
                        card_id = card.get("id", "")
                        if card_id not in matched_card_ids:
                            matched_card = {
                                "id": card_id,
                                "type": card.get("type", ""),
                                "title": card.get("title", ""),
                                "summary": card.get("summary", ""),
                                "tags": card.get("tags", []),
                                "snippet": card.get("snippet", {}),
                                "created_at": card.get("created_at", ""),
                                "deadline": card.get("deadline", ""),  # 待办截止日期
                                "similarity": f"{similarity:.2%}"  # 添加相似度信息
                            }
                            matched_cards.append(matched_card)
                            matched_card_ids.add(card_id)
        except Exception as e:
            print(f"⚠️ 语义搜索失败，降级到关键词搜索: {e}")
    
    # 如果检测到类型关键词，补充按类型过滤的结果
    if type_filter:
        try:
            with open(MEMORY_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            cards = data.get("cards", [])
            
            for card in cards:
                card_id = card.get("id", "")
                # 跳过已匹配的卡片
                if card_id in matched_card_ids:
                    continue
                
                # 按类型过滤
                if card.get("type") == type_filter:
                    matched_card = {
                        "id": card_id,
                        "type": card.get("type", ""),
                        "title": card.get("title", ""),
                        "summary": card.get("summary", ""),
                        "tags": card.get("tags", []),
                        "snippet": card.get("snippet", {}),
                        "created_at": card.get("created_at", ""),
                        "deadline": card.get("deadline", ""),  # 待办截止日期
                        "match_reason": f"类型匹配: {type_filter}"
                    }
                    matched_cards.append(matched_card)
                    matched_card_ids.add(card_id)
            
            if matched_cards:
                search_method = "语义搜索 + 类型过滤" if search_method == "语义搜索" else "类型过滤"
        except Exception as e:
            print(f"⚠️ 类型过滤失败: {e}")
    
    # 如果有结果，直接返回
    if matched_cards:
        print(f"🔍 {search_method} '{query}': 找到 {len(matched_cards)} 张相关卡片")
        return json.dumps({
            "found": True, 
            "cards": matched_cards, 
            "count": len(matched_cards),
            "search_method": search_method
        }, ensure_ascii=False, indent=2)
    
    # 降级到关键词搜索
    try:
        with open(MEMORY_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cards = data.get("cards", [])
        
        # 将查询拆分为多个关键词（OR 搜索）
        keywords = [kw.strip().lower() for kw in query.split() if kw.strip()]
        
        # 搜索匹配的卡片（部分匹配）
        for card in cards:
            title = card.get("title", "").lower()
            summary = card.get("summary", "").lower()
            tags = [tag.lower() for tag in card.get("tags", [])]
            
            # 检查是否匹配任意一个关键词（OR 逻辑）
            match_found = False
            for keyword in keywords:
                if (keyword in title or 
                    keyword in summary or 
                    any(keyword in tag for tag in tags)):
                    match_found = True
                    break
            
            if match_found:
                # 构建简化的卡片信息（适合 LLM 阅读）
                matched_card = {
                    "id": card.get("id", ""),
                    "type": card.get("type", ""),
                    "title": card.get("title", ""),
                    "summary": card.get("summary", ""),
                    "tags": card.get("tags", []),
                    "snippet": card.get("snippet", {}),
                    "created_at": card.get("created_at", "")
                }
                matched_cards.append(matched_card)
        
        # 返回结果
        if not matched_cards:
            print(f"🔍 {search_method} '{query}': 未找到匹配的卡片")
            return json.dumps({
                "found": False, 
                "message": "未找到相关卡片",
                "search_method": search_method
            }, ensure_ascii=False)
        
        print(f"🔍 {search_method} '{query}': 找到 {len(matched_cards)} 张卡片")
        return json.dumps({
            "found": True, 
            "cards": matched_cards, 
            "count": len(matched_cards),
            "search_method": search_method
        }, ensure_ascii=False, indent=2)
    
    except Exception as e:
        print(f"❌ 搜索失败: {e}")
        return f"搜索出错: {str(e)}"


def export_to_markdown() -> str:
    """
    导出所有知识卡片为 Markdown 格式
    
    Returns:
        Markdown 格式的字符串
    
    Example:
        >>> md_content = export_to_markdown()
        >>> with open("knowledge.md", "w") as f:
        ...     f.write(md_content)
    """
    _ensure_memory_file()
    
    try:
        cards = get_all_cards()
        
        if not cards:
            return "# DeepDigest 知识库导出\n\n暂无卡片\n"
        
        # 生成标题
        md_content = "# DeepDigest 知识库导出\n\n"
        md_content += f"**导出时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n"
        md_content += f"**卡片总数**: {len(cards)}  \n\n"
        md_content += "---\n\n"
        
        # 按类型分组
        cards_by_type = {"tech": [], "todo": [], "idea": []}
        for card in cards:
            card_type = card.get("type", "tech")
            if card_type in cards_by_type:
                cards_by_type[card_type].append(card)
        
        # 导出各类型卡片
        type_labels = {"tech": "💻 技术笔记", "todo": "✅ 待办事项", "idea": "💡 想法灵感"}
        
        for card_type, label in type_labels.items():
            type_cards = cards_by_type[card_type]
            if not type_cards:
                continue
            
            md_content += f"## {label}\n\n"
            
            for i, card in enumerate(type_cards, 1):
                # 卡片标题
                md_content += f"### {i}. {card.get('title', '无标题')}\n\n"
                
                # 元数据
                md_content += f"**类型**: {card_type.upper()}  \n"
                
                tags = card.get("tags", [])
                if tags:
                    tags_str = " ".join([f"`#{tag}`" for tag in tags])
                    md_content += f"**标签**: {tags_str}  \n"
                
                created_at = card.get("created_at", "")
                if created_at:
                    date_str = created_at[:10] if len(created_at) >= 10 else created_at
                    md_content += f"**创建时间**: {date_str}  \n"
                
                card_id = card.get("id", "")
                if card_id:
                    md_content += f"**卡片ID**: `{card_id[:16]}...`  \n"
                
                md_content += "\n"
                
                # 摘要
                summary = card.get("summary", "")
                if summary:
                    md_content += f"**摘要**:  \n{summary}\n\n"
                
                # 代码片段
                snippet = card.get("snippet", {})
                if snippet:
                    if snippet.get("before") or snippet.get("after"):
                        # Before/After 对比
                        md_content += "**代码对比**:\n\n"
                        
                        if snippet.get("before"):
                            md_content += "❌ Before:\n```python\n"
                            md_content += snippet.get("before", "")
                            md_content += "\n```\n\n"
                        
                        if snippet.get("after"):
                            md_content += "✅ After:\n```python\n"
                            md_content += snippet.get("after", "")
                            md_content += "\n```\n\n"
                    
                    elif snippet.get("code"):
                        # 单一代码
                        language = snippet.get("language", "python")
                        md_content += f"**代码片段**:\n```{language}\n"
                        md_content += snippet.get("code", "")
                        md_content += "\n```\n\n"
                    
                    elif snippet.get("command"):
                        # 命令
                        md_content += "**命令**:\n```bash\n"
                        md_content += snippet.get("command", "")
                        md_content += "\n```\n\n"
                
                # 关联记忆
                related_ids = card.get("related_card_ids", [])
                if related_ids:
                    md_content += f"**关联记忆**: {len(related_ids)} 张相关卡片  \n"
                
                md_content += "\n---\n\n"
        
        # 页脚
        md_content += f"\n**导出完成** - 共 {len(cards)} 张卡片  \n"
        md_content += "*由 DeepDigest Lite 生成*\n"
        
        print(f"✅ 成功导出 {len(cards)} 张卡片为 Markdown 格式")
        return md_content
    
    except Exception as e:
        print(f"❌ 导出失败: {e}")
        return f"# 导出失败\n\n错误: {str(e)}\n"


def export_cards_to_markdown(card_ids: List[str]) -> str:
    """
    导出指定的知识卡片为 Markdown 格式
    
    Args:
        card_ids: 要导出的卡片 ID 列表
    
    Returns:
        Markdown 格式的字符串
    
    Example:
        >>> md_content = export_cards_to_markdown(["id1", "id2", "id3"])
        >>> with open("selected_cards.md", "w") as f:
        ...     f.write(md_content)
    """
    _ensure_memory_file()
    
    if not card_ids:
        return "# DeepDigest 知识库导出\n\n未选择任何卡片\n"
    
    try:
        all_cards = get_all_cards()
        
        # 按 ID 筛选卡片
        selected_cards = [c for c in all_cards if c.get("id") in card_ids]
        
        if not selected_cards:
            return "# DeepDigest 知识库导出\n\n未找到选中的卡片\n"
        
        # 生成标题
        md_content = "# DeepDigest 知识库导出（批量选择）\n\n"
        md_content += f"**导出时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n"
        md_content += f"**导出卡片数**: {len(selected_cards)} / {len(all_cards)} 张  \n\n"
        md_content += "---\n\n"
        
        # 按类型分组
        cards_by_type = {"tech": [], "todo": [], "idea": []}
        for card in selected_cards:
            card_type = card.get("type", "tech")
            if card_type in cards_by_type:
                cards_by_type[card_type].append(card)
        
        # 导出各类型卡片
        type_labels = {"tech": "💻 技术笔记", "todo": "✅ 待办事项", "idea": "💡 想法灵感"}
        
        for card_type, label in type_labels.items():
            type_cards = cards_by_type[card_type]
            if not type_cards:
                continue
            
            md_content += f"## {label}\n\n"
            
            for i, card in enumerate(type_cards, 1):
                # 卡片标题
                md_content += f"### {i}. {card.get('title', '无标题')}\n\n"
                
                # 元数据
                md_content += f"**类型**: {card_type.upper()}  \n"
                
                tags = card.get("tags", [])
                if tags:
                    tags_str = " ".join([f"`#{tag}`" for tag in tags])
                    md_content += f"**标签**: {tags_str}  \n"
                
                created_at = card.get("created_at", "")
                if created_at:
                    date_str = created_at[:10] if len(created_at) >= 10 else created_at
                    md_content += f"**创建时间**: {date_str}  \n"
                
                card_id = card.get("id", "")
                if card_id:
                    md_content += f"**卡片ID**: `{card_id[:16]}...`  \n"
                
                md_content += "\n"
                
                # 摘要
                summary = card.get("summary", "")
                if summary:
                    md_content += f"**摘要**:  \n{summary}\n\n"
                
                # 代码片段
                snippet = card.get("snippet", {})
                if snippet:
                    if snippet.get("before") or snippet.get("after"):
                        md_content += "**代码对比**:\n\n"
                        if snippet.get("before"):
                            md_content += "❌ Before:\n```python\n"
                            md_content += snippet.get("before", "")
                            md_content += "\n```\n\n"
                        if snippet.get("after"):
                            md_content += "✅ After:\n```python\n"
                            md_content += snippet.get("after", "")
                            md_content += "\n```\n\n"
                    elif snippet.get("code"):
                        language = snippet.get("language", "python")
                        md_content += f"**代码片段**:\n```{language}\n"
                        md_content += snippet.get("code", "")
                        md_content += "\n```\n\n"
                    elif snippet.get("command"):
                        md_content += "**命令**:\n```bash\n"
                        md_content += snippet.get("command", "")
                        md_content += "\n```\n\n"
                
                # 关联记忆
                related_ids = card.get("related_card_ids", [])
                if related_ids:
                    md_content += f"**关联记忆**: {len(related_ids)} 张相关卡片  \n"
                
                md_content += "\n---\n\n"
        
        # 页脚
        md_content += f"\n**导出完成** - 共 {len(selected_cards)} 张卡片  \n"
        md_content += "*由 DeepDigest Lite 生成*\n"
        
        print(f"✅ 成功导出 {len(selected_cards)} 张卡片为 Markdown 格式")
        return md_content
    
    except Exception as e:
        print(f"❌ 导出失败: {e}")
        return f"# 导出失败\n\n错误: {str(e)}\n"


def find_similar_card_ids(
    card_id: str, 
    top_k: int = 3,
    threshold_with_tag_overlap: float = 0.4,
    threshold_no_tag_overlap: float = 0.75
) -> List[str]:
    """
    基于 Embedding 向量相似度查找相似卡片（带动态阈值和标签加权）
    
    **用途**: 混合召回策略中的语义关联路径
    
    **动态阈值机制**:
    - 如果两张卡片有共同标签：阈值较低 (threshold_with_tag_overlap)
    - 如果没有共同标签：阈值较高 (threshold_no_tag_overlap)
    - 只有超过阈值的卡片才会被推荐，避免低质量关联
    
    Args:
        card_id: 当前卡片的 ID
        top_k: 返回前 K 个最相似的卡片（最多）
        threshold_with_tag_overlap: 有共同标签时的相似度阈值 (默认 0.4)
        threshold_no_tag_overlap: 无共同标签时的相似度阈值 (默认 0.75)
    
    Returns:
        List[str]: 相似卡片的 ID 列表（按相似度降序），可能为空
    
    Example:
        >>> similar_ids = find_similar_card_ids("abc123", top_k=3)
        >>> print(f"找到 {len(similar_ids)} 个相似卡片")
    """
    _ensure_memory_file()
    
    try:
        with open(MEMORY_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cards = data.get("cards", [])
        
        # 找到当前卡片
        current_card = None
        for card in cards:
            if card.get("id") == card_id:
                current_card = card
                break
        
        # 如果找不到当前卡片或没有 embedding，返回空列表
        if not current_card:
            print(f"⚠️ 未找到卡片: {card_id}")
            return []
        
        current_embedding = current_card.get("embedding")
        if not current_embedding or len(current_embedding) == 0:
            print(f"⚠️ 卡片没有 embedding: {card_id}")
            return []
        
        # 获取当前卡片的标签集合（转小写以忽略大小写）
        current_tags = set(tag.lower() for tag in current_card.get("tags", []))
        
        # 转换为 numpy 数组
        current_vec = np.array(current_embedding)
        current_norm = np.linalg.norm(current_vec)
        
        if current_norm == 0:
            return []
        
        # 计算与其他卡片的相似度（带动态阈值过滤）
        candidates = []
        
        for card in cards:
            # 排除自己
            if card.get("id") == card_id:
                continue
            
            # 检查是否有 embedding
            other_embedding = card.get("embedding")
            if not other_embedding or len(other_embedding) == 0:
                continue
            
            # 计算余弦相似度
            other_vec = np.array(other_embedding)
            other_norm = np.linalg.norm(other_vec)
            
            if other_norm == 0:
                continue
            
            # cosine_similarity = dot(a, b) / (norm(a) * norm(b))
            similarity = float(np.dot(current_vec, other_vec) / (current_norm * other_norm))
            
            # === 动态阈值判断 ===
            other_tags = set(tag.lower() for tag in card.get("tags", []))
            has_tag_overlap = bool(current_tags & other_tags)  # 是否有共同标签
            
            # 根据是否有共同标签选择阈值
            if has_tag_overlap:
                threshold = threshold_with_tag_overlap
            else:
                threshold = threshold_no_tag_overlap
            
            # 只有超过阈值的才加入候选
            if similarity > threshold:
                candidates.append((card.get("id"), similarity, has_tag_overlap))
        
        # 按相似度降序排序
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # 返回前 top_k 个卡片的 ID（如果没有通过阈值的，返回空列表）
        result = [cid for cid, _, _ in candidates[:top_k]]
        
        if result:
            print(f"🔍 找到 {len(result)} 个相似卡片 (动态阈值过滤)")
        else:
            print(f"ℹ️ 没有找到满足阈值的相似卡片")
        
        return result
    
    except Exception as e:
        print(f"❌ 查找相似卡片失败: {e}")
        return []
