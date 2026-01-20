"""
Qdrant向量数据库服务模块
支持本地模式和Docker部署模式的灵活切换
"""

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    HasIdCondition,
    FieldCondition,
    MatchValue,
    MatchAny,
    DatetimeRange,
    UpdateResult,
    ScoredPoint,
)

logger = logging.getLogger(__name__)


class VectorDBService:
    """
    Qdrant向量数据库服务类
    提供向量存储、检索、更新、删除等CRUD操作
    支持本地模式和Docker部署模式
    """

    _instance: Optional["VectorDBService"] = None
    _client: Optional[QdrantClient] = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._initialized = getattr(self, '_initialized', False)
        self._collection_name: Optional[str] = None
        self._vector_dimension: int = 2048

    def initialize(
        self,
        mode: str = "local",
        path: Optional[str] = None,
        host: str = "localhost",
        port: int = 6333,
        api_key: Optional[str] = None,
        collection_name: str = "smart_album",
        vector_dimension: int = 2048,
        **kwargs
    ) -> None:
        """
        初始化向量数据库连接

        Args:
            mode: 部署模式 - "local"(本地文件) | "docker"(Docker部署) | "cloud"(云服务)
            path: 本地模式下的存储路径
            host: Docker/云服务模式下的主机地址
            port: Docker/云服务模式下的端口
            api_key: 云服务API密钥
            collection_name: 集合名称
            vector_dimension: 向量维度
        """
        if self._initialized and self._client is not None:
            logger.info("向量数据库已初始化，跳过重复初始化")
            return

        self._collection_name = collection_name
        self._vector_dimension = vector_dimension

        logger.info(f"正在初始化Qdrant向量数据库，模式: {mode}")

        if mode == "local":
            # 本地文件模式
            storage_path = Path(path) if path else Path("./qdrant_data")
            storage_path.mkdir(parents=True, exist_ok=True)
            self._client = QdrantClient(path=str(storage_path))
            logger.info(f"Qdrant本地模式初始化完成，存储路径: {storage_path}")

        elif mode == "docker":
            # Docker部署模式
            self._client = QdrantClient(host=host, port=port)
            logger.info(f"Qdrant Docker模式初始化完成，连接: {host}:{port}")

        elif mode == "cloud":
            # 云服务模式
            self._client = QdrantClient(
                host=host,
                port=port,
                api_key=api_key,
                https=True
            )
            logger.info(f"Qdrant云服务模式初始化完成")
        else:
            raise ValueError(f"不支持的Qdrant模式: {mode}")

        # 确保集合存在
        self._ensure_collection()
        self._initialized = True

    def _ensure_collection(self) -> None:
        """确保集合存在，不存在则创建"""
        collections = self._client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self._collection_name not in collection_names:
            logger.info(f"创建集合: {self._collection_name}")
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(
                    size=self._vector_dimension,
                    distance=Distance.COSINE
                )
            )
            # 创建payload索引以支持过滤
            self._client.create_payload_index(
                collection_name=self._collection_name,
                field_name="tags",
                field_schema=qdrant_models.PayloadSchemaType.KEYWORD
            )
            self._client.create_payload_index(
                collection_name=self._collection_name,
                field_name="created_at",
                field_schema=qdrant_models.PayloadSchemaType.DATETIME
            )

    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized and self._client is not None

    @property
    def collection_name(self) -> str:
        """获取集合名称"""
        return self._collection_name

    def get_collection_info(self) -> Dict[str, Any]:
        """获取集合信息"""
        if not self.is_initialized:
            raise RuntimeError("向量数据库未初始化")

        info = self._client.get_collection(self._collection_name)
        return {
            "name": self._collection_name,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": info.status.value,
            "vector_dimension": self._vector_dimension
        }

    def upsert(
        self,
        id: str,
        vector: List[float],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        插入或更新单个向量记录

        Args:
            id: 唯一标识符
            vector: 向量数据
            metadata: 元数据

        Returns:
            操作是否成功
        """
        if not self.is_initialized:
            raise RuntimeError("向量数据库未初始化")

        # 处理datetime字段
        payload = self._prepare_payload(metadata)

        point = PointStruct(
            id=id,
            vector=vector,
            payload=payload
        )

        result = self._client.upsert(
            collection_name=self._collection_name,
            points=[point],
            wait=True
        )
        return result.status == qdrant_models.UpdateStatus.COMPLETED

    def upsert_batch(
        self,
        records: List[Dict[str, Any]]
    ) -> bool:
        """
        批量插入或更新向量记录

        Args:
            records: 记录列表，每个记录包含id、vector、metadata

        Returns:
            操作是否成功
        """
        if not self.is_initialized:
            raise RuntimeError("向量数据库未初始化")

        points = []
        for record in records:
            payload = self._prepare_payload(record.get("metadata", {}))
            point = PointStruct(
                id=record["id"],
                vector=record["vector"],
                payload=payload
            )
            points.append(point)

        result = self._client.upsert(
            collection_name=self._collection_name,
            points=points,
            wait=True
        )
        return result.status == qdrant_models.UpdateStatus.COMPLETED

    def _prepare_payload(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """准备payload，处理特殊类型"""
        payload = {}
        for key, value in metadata.items():
            if isinstance(value, datetime):
                payload[key] = value.isoformat()
            else:
                payload[key] = value
        return payload

    def get(self, id: str) -> Optional[Dict[str, Any]]:
        """
        根据ID获取向量记录

        Args:
            id: 记录ID

        Returns:
            记录数据或None
        """
        if not self.is_initialized:
            raise RuntimeError("向量数据库未初始化")

        results = self._client.retrieve(
            collection_name=self._collection_name,
            ids=[id],
            with_vectors=True,
            with_payload=True
        )

        if not results:
            return None

        point = results[0]
        return {
            "id": point.id,
            "vector": point.vector,
            "metadata": point.payload
        }

    def get_batch(self, ids: List[str]) -> List[Dict[str, Any]]:
        """
        批量获取向量记录

        Args:
            ids: ID列表

        Returns:
            记录列表
        """
        if not self.is_initialized:
            raise RuntimeError("向量数据库未初始化")

        results = self._client.retrieve(
            collection_name=self._collection_name,
            ids=ids,
            with_vectors=True,
            with_payload=True
        )

        return [
            {
                "id": point.id,
                "vector": point.vector,
                "metadata": point.payload
            }
            for point in results
        ]

    def update_metadata(
        self,
        id: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        更新记录的元数据

        Args:
            id: 记录ID
            metadata: 新的元数据（仅更新提供的字段）

        Returns:
            操作是否成功
        """
        if not self.is_initialized:
            raise RuntimeError("向量数据库未初始化")

        payload = self._prepare_payload(metadata)

        result = self._client.set_payload(
            collection_name=self._collection_name,
            payload=payload,
            points=[id],
            wait=True
        )
        return result.status == qdrant_models.UpdateStatus.COMPLETED

    def delete(self, id: str) -> bool:
        """
        删除单个向量记录

        Args:
            id: 记录ID

        Returns:
            操作是否成功
        """
        if not self.is_initialized:
            raise RuntimeError("向量数据库未初始化")

        result = self._client.delete(
            collection_name=self._collection_name,
            points_selector=qdrant_models.PointIdsList(points=[id]),
            wait=True
        )
        return result.status == qdrant_models.UpdateStatus.COMPLETED

    def delete_batch(self, ids: List[str]) -> bool:
        """
        批量删除向量记录

        Args:
            ids: ID列表

        Returns:
            操作是否成功
        """
        if not self.is_initialized:
            raise RuntimeError("向量数据库未初始化")

        result = self._client.delete(
            collection_name=self._collection_name,
            points_selector=qdrant_models.PointIdsList(points=ids),
            wait=True
        )
        return result.status == qdrant_models.UpdateStatus.COMPLETED

    def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        score_threshold: Optional[float] = None,
        filter_tags: Optional[List[str]] = None,
        filter_conditions: Optional[Dict[str, Any]] = None,
        filter_created_at_from: Optional[datetime] = None,
        filter_created_at_to: Optional[datetime] = None,
        filter_ids: Optional[List[Union[int, str]]] = None
    ) -> List[Dict[str, Any]]:
        """
        向量相似度搜索

        使用 qdrant-client >= 1.7.0 推荐的 query_points() 方法
        替代已废弃的 search() 方法

        Args:
            query_vector: 查询向量
            top_k: 返回结果数量
            score_threshold: 相似度阈值
            filter_tags: 标签过滤
            filter_conditions: 其他过滤条件

        Returns:
            搜索结果列表
        """
        if not self.is_initialized:
            raise RuntimeError("向量数据库未初始化")

        # 诊断检查：确保客户端对象正确初始化
        if self._client is None:
            raise RuntimeError("Qdrant 客户端未正确初始化，_client 为 None")

        # 构建过滤条件
        query_filter = None
        conditions = []

        if filter_ids:
            conditions.append(HasIdCondition(has_id=filter_ids))

        if filter_tags:
            conditions.append(
                FieldCondition(
                    key="tags",
                    match=MatchAny(any=filter_tags)
                )
            )

        if filter_conditions:
            for key, value in filter_conditions.items():
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                )

        if filter_created_at_from or filter_created_at_to:
            conditions.append(
                FieldCondition(
                    key="created_at",
                    range=DatetimeRange(
                        gte=filter_created_at_from,
                        lt=filter_created_at_to,
                    ),
                )
            )

        if conditions:
            query_filter = Filter(must=conditions)

        # 使用新版 API: query_points() 替代已废弃的 search()
        # 关键变化:
        #   1. 参数名: query_vector -> query
        #   2. 返回值: List[ScoredPoint] -> QueryResponse (需要 .points 获取列表)
        try:
            response = self._client.query_points(
                collection_name=self._collection_name,
                query=query_vector,  # 新版 API 使用 query 而非 query_vector
                limit=top_k,
                score_threshold=score_threshold,
                query_filter=query_filter,
                with_payload=True
            )
            # query_points 返回 QueryResponse 对象，通过 .points 获取结果列表
            results = response.points
        except Exception as e:
            logger.error(f"Qdrant query_points 查询失败: {e}")
            logger.error(f"参数: collection={self._collection_name}, limit={top_k}, "
                         f"score_threshold={score_threshold}, filter={query_filter}")
            raise

        return [
            {
                "id": point.id,
                "score": point.score,
                "metadata": point.payload
            }
            for point in results
        ]

    def scroll(
        self,
        limit: int = 100,
        offset: Optional[str] = None,
        filter_tags: Optional[List[str]] = None,
        filter_created_at_from: Optional[datetime] = None,
        filter_created_at_to: Optional[datetime] = None
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """
        分页遍历所有记录

        Args:
            limit: 每页数量
            offset: 偏移量（上次返回的next_offset）
            filter_tags: 标签过滤

        Returns:
            (记录列表, 下一页偏移量)
        """
        if not self.is_initialized:
            raise RuntimeError("向量数据库未初始化")

        query_filter = None
        conditions = []
        if filter_tags:
            conditions.append(
                FieldCondition(
                    key="tags",
                    match=MatchAny(any=filter_tags)
                )
            )

        if filter_created_at_from or filter_created_at_to:
            conditions.append(
                FieldCondition(
                    key="created_at",
                    range=DatetimeRange(
                        gte=filter_created_at_from,
                        lt=filter_created_at_to,
                    ),
                )
            )

        if conditions:
            query_filter = Filter(must=conditions)

        results, next_offset = self._client.scroll(
            collection_name=self._collection_name,
            limit=limit,
            offset=offset,
            scroll_filter=query_filter,
            with_payload=True,
            with_vectors=False
        )

        records = [
            {
                "id": point.id,
                "metadata": point.payload
            }
            for point in results
        ]

        return records, next_offset

    def count(self, filter_tags: Optional[List[str]] = None) -> int:
        """
        统计记录数量

        Args:
            filter_tags: 标签过滤

        Returns:
            记录数量
        """
        if not self.is_initialized:
            raise RuntimeError("向量数据库未初始化")

        query_filter = None
        if filter_tags:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="tags",
                        match=MatchAny(any=filter_tags)
                    )
                ]
            )

        result = self._client.count(
            collection_name=self._collection_name,
            count_filter=query_filter,
            exact=True
        )
        return result.count

    def delete_collection(self) -> bool:
        """删除整个集合"""
        if not self.is_initialized:
            raise RuntimeError("向量数据库未初始化")

        return self._client.delete_collection(self._collection_name)

    def recreate_collection(self) -> None:
        """重建集合"""
        if not self.is_initialized:
            raise RuntimeError("向量数据库未初始化")

        self._client.recreate_collection(
            collection_name=self._collection_name,
            vectors_config=VectorParams(
                size=self._vector_dimension,
                distance=Distance.COSINE
            )
        )


# 全局服务实例
vector_db_service = VectorDBService()


def get_vector_db_service() -> VectorDBService:
    """获取向量数据库服务实例"""
    return vector_db_service
