"""
向量嵌入工具 - 支持语义搜索
使用 Embedding API 生成向量，并计算余弦相似度
"""

import sys
from pathlib import Path

# 当作为脚本直接运行时，添加父目录到 Python 路径
if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

import json
import numpy as np
import os
from typing import List, Dict, Tuple, Optional
from openai import OpenAI

# 根据运行方式选择导入方式
try:
    from ..config import MEMORY_JSON_PATH
    from .memory_tools import get_all_cards, save_knowledge_cards
except ImportError:
    from deep_digest.src.config import MEMORY_JSON_PATH
    from deep_digest.src.tools.memory_tools import get_all_cards, save_knowledge_cards


# 全局 OpenAI 客户端
_openai_client: Optional[OpenAI] = None


def init_openai_client(api_key: str, api_base: str = "https://api.openai.com/v1"):
    """
    初始化 OpenAI 客户端
    
    Args:
        api_key: OpenAI API Key
        api_base: API Base URL
    """
    global _openai_client
    _openai_client = OpenAI(
        api_key=api_key,
        base_url=api_base
    )
    print(f"✅ Embedding 客户端已初始化: {api_base}")


def get_embedding(text: str, model: str = None) -> List[float]:
    """
    生成文本的向量嵌入
    
    Args:
        text: 输入文本
        model: 嵌入模型名称（默认从环境变量 EMBEDDING_MODEL 读取，或使用 BAAI/bge-m3）
    
    Returns:
        向量列表
    
    Example:
        >>> embedding = get_embedding("这是一段测试文本")
        >>> len(embedding)
        1024
    """
    if _openai_client is None:
        raise RuntimeError("OpenAI 客户端未初始化，请先调用 init_openai_client()")
    
    # 从环境变量读取模型名称，默认使用 BAAI/bge-m3
    if model is None:
        model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    
    # 清理文本
    text = text.replace("\n", " ").strip()
    
    if not text:
        return []
    
    try:
        response = _openai_client.embeddings.create(
            model=model,
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"❌ 生成 embedding 失败 (模型: {model}): {e}")
        return []


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    计算两个向量的余弦相似度
    
    Args:
        vec1: 向量1
        vec2: 向量2
    
    Returns:
        相似度分数 (0-1)
    
    Example:
        >>> sim = cosine_similarity([1, 0, 0], [1, 0, 0])
        >>> sim
        1.0
    """
    if not vec1 or not vec2:
        return 0.0
    
    # 转换为 numpy 数组
    a = np.array(vec1)
    b = np.array(vec2)
    
    # 计算余弦相似度
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return float(dot_product / (norm_a * norm_b))


def generate_card_embeddings(force_regenerate: bool = False) -> int:
    """
    为所有卡片生成 embedding（如果尚未生成）
    
    Args:
        force_regenerate: 是否强制重新生成所有 embedding
    
    Returns:
        生成的 embedding 数量
    
    Example:
        >>> count = generate_card_embeddings()
        >>> print(f"生成了 {count} 个 embedding")
    """
    cards = get_all_cards()
    
    generated_count = 0
    
    for card in cards:
        # 跳过已有 embedding 的卡片（除非强制重新生成）
        if not force_regenerate and "embedding" in card and card["embedding"]:
            continue
        
        # 生成卡片文本（标题 + 摘要 + 标签）
        card_text = f"{card['title']} {card['summary']} {' '.join(card.get('tags', []))}"
        
        # 生成 embedding
        embedding = get_embedding(card_text)
        
        if embedding:
            card["embedding"] = embedding
            generated_count += 1
            print(f"✅ 已生成 embedding [{generated_count}]: {card['title'][:30]}... (ID: {card.get('id', 'N/A')[:8]}...)")
        else:
            print(f"⚠️ 跳过卡片 (embedding 生成失败): {card['title'][:30]}... (ID: {card.get('id', 'N/A')[:8]}...)")
    
    # 保存更新后的卡片（直接写入文件，不使用 save_knowledge_cards 避免重复追加）
    if generated_count > 0:
        try:
            with open(MEMORY_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 更新卡片列表
            data["cards"] = cards
            
            # 写回文件
            with open(MEMORY_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"\n✅ 共生成 {generated_count} 个 embedding")
        except Exception as e:
            print(f"❌ 保存 embedding 失败: {e}")
            return 0
    else:
        print("ℹ️  所有卡片已有 embedding，无需生成")
    
    return generated_count


def search_cards_semantic(
    query: str,
    top_k: int = 5,
    similarity_threshold: float = 0.7
) -> List[Tuple[Dict, float]]:
    """
    基于语义相似度搜索卡片
    
    Args:
        query: 搜索查询
        top_k: 返回前 K 个结果
        similarity_threshold: 相似度阈值（0-1）
    
    Returns:
        (卡片, 相似度分数) 列表
    
    Example:
        >>> results = search_cards_semantic("Python 编程", top_k=3)
        >>> for card, score in results:
        ...     print(f"{card['title']}: {score:.2f}")
    """
    # 生成查询的 embedding
    query_embedding = get_embedding(query)
    
    if not query_embedding:
        print("❌ 无法生成查询的 embedding")
        return []
    
    # 获取所有卡片
    cards = get_all_cards()
    
    # 计算相似度
    cards_with_scores = []
    
    for card in cards:
        # 如果卡片没有 embedding，跳过
        if "embedding" not in card or not card["embedding"]:
            continue
        
        # 计算余弦相似度
        similarity = cosine_similarity(query_embedding, card["embedding"])
        
        # 只保留超过阈值的结果
        if similarity >= similarity_threshold:
            cards_with_scores.append((card, similarity))
    
    # 按相似度降序排序
    cards_with_scores.sort(key=lambda x: x[1], reverse=True)
    
    # 返回 Top-K
    return cards_with_scores[:top_k]


def search_cards_hybrid(
    query: str,
    top_k: int = 5,
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3
) -> List[Tuple[Dict, float]]:
    """
    混合搜索：语义搜索 + 关键词搜索
    
    Args:
        query: 搜索查询
        top_k: 返回前 K 个结果
        semantic_weight: 语义搜索权重
        keyword_weight: 关键词搜索权重
    
    Returns:
        (卡片, 综合分数) 列表
    """
    # 1. 语义搜索
    semantic_results = search_cards_semantic(query, top_k=top_k * 2, similarity_threshold=0.5)
    semantic_scores = {card["id"]: score for card, score in semantic_results}
    
    # 2. 关键词搜索
    cards = get_all_cards()
    keyword_scores = {}
    
    query_lower = query.lower()
    
    for card in cards:
        score = 0.0
        
        # 标题匹配（权重最高）
        if query_lower in card["title"].lower():
            score += 0.5
        
        # 摘要匹配
        if query_lower in card["summary"].lower():
            score += 0.3
        
        # 标签匹配
        for tag in card.get("tags", []):
            if query_lower in tag.lower():
                score += 0.2
                break
        
        if score > 0:
            keyword_scores[card["id"]] = score
    
    # 3. 合并分数
    all_card_ids = set(semantic_scores.keys()) | set(keyword_scores.keys())
    
    combined_results = []
    
    for card_id in all_card_ids:
        # 归一化分数
        semantic_score = semantic_scores.get(card_id, 0.0)
        keyword_score = keyword_scores.get(card_id, 0.0)
        
        # 加权合并
        combined_score = (
            semantic_weight * semantic_score +
            keyword_weight * keyword_score
        )
        
        # 找到对应的卡片
        card = next((c for c in cards if c["id"] == card_id), None)
        
        if card:
            combined_results.append((card, combined_score))
    
    # 排序并返回 Top-K
    combined_results.sort(key=lambda x: x[1], reverse=True)
    
    return combined_results[:top_k]


def recommend_related_cards(
    card_id: str,
    top_k: int = 5,
    exclude_existing_relations: bool = True
) -> List[Tuple[Dict, float]]:
    """
    基于相似度推荐相关卡片
    
    Args:
        card_id: 当前卡片 ID
        top_k: 推荐数量
        exclude_existing_relations: 是否排除已关联的卡片
    
    Returns:
        (推荐卡片, 相似度分数) 列表
    
    Example:
        >>> recommendations = recommend_related_cards("card_123", top_k=3)
        >>> for card, score in recommendations:
        ...     print(f"{card['title']}: {score:.2f}")
    """
    # 获取当前卡片
    cards = get_all_cards()
    current_card = next((c for c in cards if c["id"] == card_id), None)
    
    if not current_card:
        print(f"❌ 未找到卡片: {card_id}")
        return []
    
    if "embedding" not in current_card or not current_card["embedding"]:
        print(f"❌ 卡片没有 embedding: {card_id}")
        return []
    
    # 获取已关联的卡片 ID
    existing_relations = set(current_card.get("related_card_ids", []))
    
    # 计算与其他卡片的相似度
    similarities = []
    
    for card in cards:
        # 跳过自己
        if card["id"] == card_id:
            continue
        
        # 跳过已关联的卡片
        if exclude_existing_relations and card["id"] in existing_relations:
            continue
        
        # 跳过没有 embedding 的卡片
        if "embedding" not in card or not card["embedding"]:
            continue
        
        # 计算相似度
        similarity = cosine_similarity(current_card["embedding"], card["embedding"])
        
        similarities.append((card, similarity))
    
    # 排序并返回 Top-K
    similarities.sort(key=lambda x: x[1], reverse=True)
    
    return similarities[:top_k]


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    # 加载环境变量
    load_dotenv()
    
    # 初始化 OpenAI 客户端
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
    
    if not api_key:
        print("❌ 请设置 LLM_API_KEY 环境变量")
        exit(1)
    
    init_openai_client(api_key, api_base)
    
    print("=" * 70)
    print("向量嵌入工具测试")
    print("=" * 70)
    
    # 测试 1: 生成 embedding
    print("\n[测试 1] 生成卡片 embedding...")
    count = generate_card_embeddings()
    
    # 测试 2: 语义搜索
    print("\n[测试 2] 语义搜索...")
    results = search_cards_semantic("Python 编程技巧", top_k=3)
    
    print(f"\n找到 {len(results)} 个相关卡片:")
    for card, score in results:
        print(f"  • {card['title'][:40]:<40} 相似度: {score:.3f}")
    
    # 测试 3: 混合搜索
    print("\n[测试 3] 混合搜索...")
    results = search_cards_hybrid("Docker 容器", top_k=3)
    
    print(f"\n找到 {len(results)} 个相关卡片:")
    for card, score in results:
        print(f"  • {card['title'][:40]:<40} 综合分数: {score:.3f}")
    
    # 测试 4: 智能推荐
    if results:
        print("\n[测试 4] 智能推荐...")
        card_id = results[0][0]["id"]
        recommendations = recommend_related_cards(card_id, top_k=3)
        
        print(f"\n基于卡片 '{results[0][0]['title'][:30]}' 的推荐:")
        for card, score in recommendations:
            print(f"  • {card['title'][:40]:<40} 相似度: {score:.3f}")
    
    print("\n✅ 测试完成")
