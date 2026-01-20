"""
智能图像检索服务模块
整合Embedding服务和向量数据库实现语义搜索
"""

import logging
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta
import re

from PIL import Image

from .embedding_service import get_embedding_service, EmbeddingService
from .vector_db_service import get_vector_db_service, VectorDBService
from .storage_service import get_storage_service, StorageService

logger = logging.getLogger(__name__)


class SearchService:
    """
    智能图像检索服务类
    提供基于语义的图像搜索功能
    """

    _instance: Optional["SearchService"] = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._embedding_service: Optional[EmbeddingService] = None
        self._vector_db_service: Optional[VectorDBService] = None
        self._storage_service: Optional[StorageService] = None

    def initialize(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        vector_db_service: Optional[VectorDBService] = None,
        storage_service: Optional[StorageService] = None
    ) -> None:
        """
        初始化搜索服务

        Args:
            embedding_service: Embedding服务实例
            vector_db_service: 向量数据库服务实例
            storage_service: 存储服务实例
        """
        self._embedding_service = embedding_service or get_embedding_service()
        self._vector_db_service = vector_db_service or get_vector_db_service()
        self._storage_service = storage_service or get_storage_service()

        logger.info("搜索服务初始化完成")

    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return (
            self._embedding_service is not None and
            self._vector_db_service is not None and
            self._storage_service is not None and
            self._embedding_service.is_initialized and
            self._vector_db_service.is_initialized
        )

    def _get_query_type(
        self,
        query_text: Optional[str],
        query_image: Optional[Union[str, Image.Image]]
    ) -> str:
        """确定查询类型"""
        if query_text and query_image:
            return "hybrid"
        elif query_image:
            return "image"
        elif query_text:
            return "text"
        else:
            raise ValueError("必须提供query_text或query_image")

    def search_by_text(
        self,
        query_text: str,
        instruction: Optional[str] = None,
        top_k: int = 10,
        score_threshold: Optional[float] = None,
        filter_tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        文本语义搜索

        Args:
            query_text: 查询文本
            instruction: 查询指令
            top_k: 返回结果数量
            score_threshold: 相似度阈值
            filter_tags: 标签过滤

        Returns:
            搜索结果列表
        """
        if not self.is_initialized:
            raise RuntimeError("搜索服务未初始化")

        logger.info(
            f"开始文本搜索: query='{query_text}', top_k={top_k}, score_threshold={score_threshold}, tags={filter_tags}")

        # 关键修复：使用与索引时相同的 instruction
        # 索引时用的是: "Represent this image for retrieval."
        # 搜索时也应该使用相同的语义空间
        query_vector = self._embedding_service.generate_text_embedding(
            text=query_text,
            instruction=instruction or "Represent this text for retrieval."
        )

        logger.info(
            f"查询向量生成完成: dimension={len(query_vector)}, first_3_values={query_vector[:3]}")

        # 向量搜索
        results = self._vector_db_service.search(
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=score_threshold,
            filter_tags=filter_tags
        )

        logger.info(f"向量搜索完成: 返回 {len(results)} 条结果")
        if len(results) > 0:
            for i, result in enumerate(results):
                logger.info(f"第{i+1}条结果: id={result['id']}, score={result['score']}")

        # 添加预览URL
        for result in results:
            result["preview_url"] = f"/api/v1/storage/images/{result['id']}"

        return results

    def search_by_date_text(
        self,
        date_text: str,
        top_k: int = 10,
        filter_tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        if not self.is_initialized:
            raise RuntimeError("搜索服务未初始化")

        parsed = self._parse_date_text(date_text)
        if not parsed:
            return []

        year, month, day = parsed
        logger.info(f"开始日期检索: date_text='{date_text}', parsed={(year, month, day)}, top_k={top_k}, tags={filter_tags}")

        if year is not None:
            start = datetime(year, month, day)
            end = start + timedelta(days=1)
            records, _ = self._vector_db_service.scroll(
                limit=max(top_k * 5, 50),
                offset=None,
                filter_tags=filter_tags,
                filter_created_at_from=start,
                filter_created_at_to=end,
            )
            results = [{"id": r["id"], "score": None, "metadata": r.get("metadata", {})} for r in records]
        else:
            results = []
            offset = None
            fetched = 0
            fetch_limit = 256
            max_fetch = 5000
            while fetched < max_fetch:
                records, offset = self._vector_db_service.scroll(
                    limit=fetch_limit,
                    offset=offset,
                    filter_tags=filter_tags,
                )
                if not records:
                    break
                fetched += len(records)
                for r in records:
                    created = (r.get("metadata") or {}).get("created_at")
                    if not isinstance(created, str):
                        continue
                    dt = self._try_parse_iso_datetime(created)
                    if dt and dt.month == month and dt.day == day:
                        results.append({"id": r["id"], "score": None, "metadata": r.get("metadata", {})})
                if offset is None:
                    break

        def sort_key(item: Dict[str, Any]):
            created = (item.get("metadata") or {}).get("created_at")
            dt = self._try_parse_iso_datetime(created) if isinstance(created, str) else None
            return dt or datetime.min

        results.sort(key=sort_key, reverse=True)
        results = results[:top_k]

        for result in results:
            result["preview_url"] = f"/api/v1/storage/images/{result['id']}"

        return results

    def search_by_meta(
        self,
        date_text: Optional[str] = None,
        tags: Optional[List[str]] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        if not self.is_initialized:
            raise RuntimeError("搜索服务未初始化")

        tags = tags or None
        if date_text:
            results = self.search_by_date_text(date_text=date_text, top_k=top_k, filter_tags=tags)
            return results

        records, _ = self._vector_db_service.scroll(
            limit=5000,
            offset=None,
            filter_tags=tags,
        )

        def sort_key(item: Dict[str, Any]):
            created = (item.get("metadata") or {}).get("created_at")
            dt = self._try_parse_iso_datetime(created) if isinstance(created, str) else None
            return dt or datetime.min

        records.sort(key=sort_key, reverse=True)
        records = records[:top_k]

        results = [{"id": r["id"], "score": None, "metadata": r.get("metadata", {})} for r in records]
        for result in results:
            result["preview_url"] = f"/api/v1/storage/images/{result['id']}"
        return results

    def search_by_text_with_meta(
        self,
        query_text: str,
        date_text: Optional[str] = None,
        tags: Optional[List[str]] = None,
        top_k: int = 10,
        score_threshold: Optional[float] = None,
        instruction: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self.is_initialized:
            raise RuntimeError("搜索服务未初始化")

        tags = tags or None
        filter_ids = None
        filter_created_at_from = None
        filter_created_at_to = None

        if date_text:
            parsed = self._parse_date_text(date_text)
            if parsed:
                year, month, day = parsed
                if year is not None:
                    start = datetime(year, month, day)
                    end = start + timedelta(days=1)
                    filter_created_at_from = start
                    filter_created_at_to = end
                else:
                    filter_ids = self._list_ids_by_month_day(month=month, day=day, tags=tags)

        query_vector = self._embedding_service.generate_text_embedding(
            text=query_text,
            instruction=instruction or "Represent this text for retrieval."
        )

        results = self._vector_db_service.search(
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=score_threshold,
            filter_tags=tags,
            filter_created_at_from=filter_created_at_from,
            filter_created_at_to=filter_created_at_to,
            filter_ids=filter_ids,
        )

        for result in results:
            result["preview_url"] = f"/api/v1/storage/images/{result['id']}"

        return results

    @staticmethod
    def split_date_and_query(text: str) -> tuple[Optional[str], str]:
        s = (text or "").strip()
        patterns = [
            r"(\d{4}[./-]\d{1,2}[./-]\d{1,2})",
            r"(\d{1,2}[./-]\d{1,2})",
            r"(\d{1,2}月\d{1,2}日?)",
        ]

        for pat in patterns:
            m = re.search(pat, s)
            if not m:
                continue
            date_text = m.group(1)
            rest = (s[:m.start()] + " " + s[m.end():]).strip()
            rest = re.sub(r"\s+", " ", rest)
            return date_text, rest

        return None, s

    def _list_ids_by_month_day(self, month: int, day: int, tags: Optional[List[str]] = None) -> List[str]:
        ids: List[str] = []
        offset = None
        fetched = 0
        fetch_limit = 256
        max_fetch = 20000
        max_ids = 5000

        while fetched < max_fetch and len(ids) < max_ids:
            records, offset = self._vector_db_service.scroll(
                limit=fetch_limit,
                offset=offset,
                filter_tags=tags,
            )
            if not records:
                break
            fetched += len(records)
            for r in records:
                created = (r.get("metadata") or {}).get("created_at")
                if not isinstance(created, str):
                    continue
                dt = self._try_parse_iso_datetime(created)
                if dt and dt.month == month and dt.day == day:
                    ids.append(str(r["id"]))
                    if len(ids) >= max_ids:
                        break
            if offset is None:
                break

        return ids

    @staticmethod
    def _try_parse_iso_datetime(value: str) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None

    @staticmethod
    def _parse_date_text(date_text: str) -> Optional[tuple[Optional[int], int, int]]:
        text = (date_text or "").strip()

        m = re.fullmatch(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", text)
        if m:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= month <= 12 and 1 <= day <= 31:
                return year, month, day

        m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})", text)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
            if 1 <= month <= 12 and 1 <= day <= 31:
                return None, month, day

        m = re.fullmatch(r"(\d{1,2})月(\d{1,2})日?", text)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
            if 1 <= month <= 12 and 1 <= day <= 31:
                return None, month, day

        return None

    def search_by_image(
        self,
        image: Union[str, Image.Image],
        instruction: Optional[str] = None,
        top_k: int = 10,
        score_threshold: Optional[float] = None,
        filter_tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        图像相似度搜索

        Args:
            image: 图片路径或PIL Image对象
            instruction: 查询指令
            top_k: 返回结果数量
            score_threshold: 相似度阈值
            filter_tags: 标签过滤

        Returns:
            搜索结果列表
        """
        if not self.is_initialized:
            raise RuntimeError("搜索服务未初始化")

        # 生成查询向量
        query_vector = self._embedding_service.generate_image_embedding(
            image=image,
            instruction=instruction or "Find similar images."
        )

        # 向量搜索
        results = self._vector_db_service.search(
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=score_threshold,
            filter_tags=filter_tags
        )

        # 添加预览URL
        for result in results:
            result["preview_url"] = f"/api/v1/storage/images/{result['id']}"

        return results

    def search_by_image_id(
        self,
        image_id: str,
        instruction: Optional[str] = None,
        top_k: int = 10,
        score_threshold: Optional[float] = None,
        filter_tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        根据图片ID搜索相似图片

        Args:
            image_id: 图片ID
            instruction: 查询指令
            top_k: 返回结果数量
            score_threshold: 相似度阈值
            filter_tags: 标签过滤

        Returns:
            搜索结果列表
        """
        # 获取图片路径
        image_path = self._storage_service.get_image_path(image_id)
        if not image_path:
            raise ValueError(f"图片不存在: {image_id}")

        return self.search_by_image(
            image=str(image_path),
            instruction=instruction,
            top_k=top_k,
            score_threshold=score_threshold,
            filter_tags=filter_tags
        )

    def search_hybrid(
        self,
        query_text: str,
        image: Union[str, Image.Image],
        instruction: Optional[str] = None,
        top_k: int = 10,
        score_threshold: Optional[float] = None,
        filter_tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        图文混合语义搜索

        Args:
            query_text: 查询文本
            image: 图片路径或PIL Image对象
            instruction: 查询指令
            top_k: 返回结果数量
            score_threshold: 相似度阈值
            filter_tags: 标签过滤

        Returns:
            搜索结果列表
        """
        if not self.is_initialized:
            raise RuntimeError("搜索服务未初始化")

        # 生成多模态查询向量
        query_vector = self._embedding_service.generate_multimodal_embedding(
            text=query_text,
            image=image,
            instruction=instruction or "Find images matching both the text description and visual content."
        )

        # 向量搜索
        results = self._vector_db_service.search(
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=score_threshold,
            filter_tags=filter_tags
        )

        # 添加预览URL
        for result in results:
            result["preview_url"] = f"/api/v1/storage/images/{result['id']}"

        return results

    def search(
        self,
        query_text: Optional[str] = None,
        query_image_id: Optional[str] = None,
        query_image_url: Optional[str] = None,
        instruction: Optional[str] = None,
        top_k: int = 10,
        score_threshold: Optional[float] = None,
        filter_tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        统一搜索接口

        Args:
            query_text: 查询文本
            query_image_id: 查询图片ID
            query_image_url: 查询图片URL/路径
            instruction: 查询指令
            top_k: 返回结果数量
            score_threshold: 相似度阈值
            filter_tags: 标签过滤

        Returns:
            包含查询类型和结果的字典
        """
        # 确定查询图片
        query_image = None
        if query_image_id:
            image_path = self._storage_service.get_image_path(query_image_id)
            if image_path:
                query_image = str(image_path)
        elif query_image_url:
            query_image = query_image_url

        # 确定查询类型
        query_type = self._get_query_type(query_text, query_image)

        # 执行搜索
        if query_type == "hybrid":
            results = self.search_hybrid(
                query_text=query_text,
                image=query_image,
                instruction=instruction,
                top_k=top_k,
                score_threshold=score_threshold,
                filter_tags=filter_tags
            )
        elif query_type == "image":
            results = self.search_by_image(
                image=query_image,
                instruction=instruction,
                top_k=top_k,
                score_threshold=score_threshold,
                filter_tags=filter_tags
            )
        else:  # text
            results = self.search_by_text(
                query_text=query_text,
                instruction=instruction,
                top_k=top_k,
                score_threshold=score_threshold,
                filter_tags=filter_tags
            )

        return {
            "query_type": query_type,
            "results": results,
            "total": len(results)
        }

    def index_image(
        self,
        image_id: str,
        image_path: str,
        metadata: Dict[str, Any],
        instruction: Optional[str] = None
    ) -> bool:
        """
        索引单张图片到向量数据库

        Args:
            image_id: 图片ID
            image_path: 图片路径
            metadata: 元数据
            instruction: 索引指令

        Returns:
            是否成功
        """
        if not self.is_initialized:
            raise RuntimeError("搜索服务未初始化")

        logger.info(f"开始索引图片: id={image_id}, path={image_path}")

        # 生成图片向量
        vector = self._embedding_service.generate_image_embedding(
            image=image_path,
            instruction=instruction or "Represent this image for retrieval."
        )

        logger.info(
            f"图片向量生成完成: dimension={len(vector)}, first_3_values={vector[:3]}")

        # 存入向量数据库
        success = self._vector_db_service.upsert(
            id=image_id,
            vector=vector,
            metadata=metadata
        )

        if success:
            logger.info(f"图片索引成功: {image_id}")
        else:
            logger.error(f"图片索引失败: {image_id}")

        return success

    def index_images_batch(
        self,
        images: List[Dict[str, Any]],
        instruction: Optional[str] = None
    ) -> bool:
        """
        批量索引图片

        Args:
            images: 图片信息列表，每个包含id、path、metadata
            instruction: 索引指令

        Returns:
            是否成功
        """
        if not self.is_initialized:
            raise RuntimeError("搜索服务未初始化")

        # 批量生成向量
        inputs = [
            {
                "image": img["path"],
                "instruction": instruction or "Represent this image for retrieval."
            }
            for img in images
        ]

        vectors = self._embedding_service.generate_embeddings_batch(inputs)

        # 准备记录
        records = [
            {
                "id": img["id"],
                "vector": vec,
                "metadata": img["metadata"]
            }
            for img, vec in zip(images, vectors)
        ]

        return self._vector_db_service.upsert_batch(records)

    def remove_from_index(self, image_id: str) -> bool:
        """
        从索引中删除图片

        Args:
            image_id: 图片ID

        Returns:
            是否成功
        """
        return self._vector_db_service.delete(image_id)


# 全局服务实例
search_service = SearchService()


def get_search_service() -> SearchService:
    """获取搜索服务实例"""
    return search_service
