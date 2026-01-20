"""
向量数据库CRUD API路由
提供向量记录的增删改查操作
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from ..models import (
    BaseResponse,
    ResponseStatus,
    VectorUpsertRequest,
    VectorBatchUpsertRequest,
    VectorUpdateMetadataRequest,
    VectorQueryResult,
    VectorSearchResponse,
    ImageMetadata,
)
from ..services import (
    get_vector_db_service,
    VectorDBService,
    get_embedding_service,
    EmbeddingService,
    get_storage_service,
    StorageService
)

router = APIRouter(prefix="/vectors", tags=["Vector Database"])


def get_services():
    """获取服务依赖"""
    vector_db_svc = get_vector_db_service()
    embedding_svc = get_embedding_service()
    storage_svc = get_storage_service()

    if not vector_db_svc.is_initialized:
        raise HTTPException(status_code=503, detail="向量数据库未初始化")

    return vector_db_svc, embedding_svc, storage_svc


@router.post(
    "/upsert",
    response_model=BaseResponse,
    summary="插入或更新向量记录",
    description="""
    插入或更新单条向量记录。
    - 如果提供了vector，直接使用
    - 如果未提供vector，将根据metadata中的file_path自动生成
    """
)
async def upsert_vector(
    request: VectorUpsertRequest,
    services: tuple = Depends(get_services)
):
    """插入或更新向量记录"""
    vector_db_svc, embedding_svc, storage_svc = services

    vector = request.vector

    # 如果未提供向量，自动生成
    if vector is None:
        if not embedding_svc.is_initialized:
            raise HTTPException(
                status_code=503, detail="Embedding服务未初始化，无法自动生成向量")

        # 获取图片路径
        image_path = storage_svc.get_image_path(request.id)
        if not image_path:
            raise HTTPException(status_code=404, detail=f"图片不存在: {request.id}")

        vector = embedding_svc.generate_image_embedding(str(image_path))

    success = vector_db_svc.upsert(
        id=request.id,
        vector=vector,
        metadata=request.metadata.model_dump()
    )

    if success:
        return BaseResponse(
            status=ResponseStatus.SUCCESS,
            message="向量记录已保存"
        )
    else:
        raise HTTPException(status_code=500, detail="保存向量记录失败")


@router.post(
    "/upsert/batch",
    response_model=BaseResponse,
    summary="批量插入或更新向量记录",
    description="批量操作，提高写入效率"
)
async def upsert_vectors_batch(
    request: VectorBatchUpsertRequest,
    services: tuple = Depends(get_services)
):
    """批量插入或更新向量记录"""
    vector_db_svc, embedding_svc, storage_svc = services

    # 准备记录，需要自动生成向量的单独处理
    records_to_embed = []
    final_records = []

    for record in request.records:
        if record.vector is not None:
            final_records.append({
                "id": record.id,
                "vector": record.vector,
                "metadata": record.metadata.model_dump()
            })
        else:
            image_path = storage_svc.get_image_path(record.id)
            if image_path:
                records_to_embed.append({
                    "id": record.id,
                    "path": str(image_path),
                    "metadata": record.metadata.model_dump()
                })

    # 批量生成向量
    if records_to_embed:
        if not embedding_svc.is_initialized:
            raise HTTPException(status_code=503, detail="Embedding服务未初始化")

        inputs = [{"image": r["path"]} for r in records_to_embed]
        vectors = embedding_svc.generate_embeddings_batch(inputs)

        for record, vector in zip(records_to_embed, vectors):
            final_records.append({
                "id": record["id"],
                "vector": vector,
                "metadata": record["metadata"]
            })

    success = vector_db_svc.upsert_batch(final_records)

    if success:
        return BaseResponse(
            status=ResponseStatus.SUCCESS,
            message=f"成功保存 {len(final_records)} 条向量记录"
        )
    else:
        raise HTTPException(status_code=500, detail="批量保存失败")


@router.get(
    "/{vector_id}",
    summary="获取向量记录",
    description="根据ID获取向量记录详情"
)
async def get_vector(
    vector_id: str,
    services: tuple = Depends(get_services)
):
    """获取向量记录"""
    vector_db_svc, _, _ = services

    record = vector_db_svc.get(vector_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"记录不存在: {vector_id}")

    return {
        "status": "success",
        "data": record
    }


@router.get(
    "/batch/get",
    summary="批量获取向量记录",
    description="根据ID列表批量获取记录"
)
async def get_vectors_batch(
    ids: List[str] = Query(..., description="ID列表"),
    services: tuple = Depends(get_services)
):
    """批量获取向量记录"""
    vector_db_svc, _, _ = services

    records = vector_db_svc.get_batch(ids)

    return {
        "status": "success",
        "data": records,
        "total": len(records)
    }


@router.patch(
    "/{vector_id}/metadata",
    response_model=BaseResponse,
    summary="更新元数据",
    description="仅更新向量记录的元数据，不影响向量本身"
)
async def update_vector_metadata(
    vector_id: str,
    request: VectorUpdateMetadataRequest,
    services: tuple = Depends(get_services)
):
    """更新向量记录的元数据"""
    vector_db_svc, _, _ = services

    # 构建更新数据
    update_data = {}
    if request.tags is not None:
        update_data["tags"] = request.tags
    if request.description is not None:
        update_data["description"] = request.description
    if request.extra is not None:
        update_data["extra"] = request.extra

    if not update_data:
        raise HTTPException(status_code=400, detail="未提供任何更新内容")

    success = vector_db_svc.update_metadata(vector_id, update_data)

    if success:
        return BaseResponse(
            status=ResponseStatus.SUCCESS,
            message="元数据更新成功"
        )
    else:
        raise HTTPException(status_code=500, detail="更新失败")


@router.delete(
    "/{vector_id}",
    response_model=BaseResponse,
    summary="删除向量记录",
    description="删除指定ID的向量记录"
)
async def delete_vector(
    vector_id: str,
    services: tuple = Depends(get_services)
):
    """删除向量记录"""
    vector_db_svc, _, _ = services

    success = vector_db_svc.delete(vector_id)

    if success:
        return BaseResponse(
            status=ResponseStatus.SUCCESS,
            message="记录已删除"
        )
    else:
        raise HTTPException(status_code=500, detail="删除失败")


@router.delete(
    "/batch/delete",
    response_model=BaseResponse,
    summary="批量删除向量记录",
    description="批量删除指定ID的向量记录"
)
async def delete_vectors_batch(
    ids: List[str] = Query(..., description="要删除的ID列表"),
    services: tuple = Depends(get_services)
):
    """批量删除向量记录"""
    vector_db_svc, _, _ = services

    success = vector_db_svc.delete_batch(ids)

    if success:
        return BaseResponse(
            status=ResponseStatus.SUCCESS,
            message=f"成功删除 {len(ids)} 条记录"
        )
    else:
        raise HTTPException(status_code=500, detail="批量删除失败")


@router.get(
    "/",
    response_model=VectorSearchResponse,
    summary="列出向量记录",
    description="分页获取向量记录列表"
)
async def list_vectors(
    limit: int = Query(100, ge=1, le=1000, description="每页数量"),
    offset: Optional[str] = Query(None, description="分页偏移量"),
    tags: Optional[List[str]] = Query(None, description="标签过滤"),
    services: tuple = Depends(get_services)
):
    """列出向量记录"""
    vector_db_svc, _, _ = services

    records, next_offset = vector_db_svc.scroll(
        limit=limit,
        offset=offset,
        filter_tags=tags
    )

    results = [
        VectorQueryResult(
            id=r["id"],
            score=1.0,  # scroll不返回分数
            metadata=ImageMetadata(
                **r["metadata"]) if r.get("metadata") else None
        )
        for r in records
    ]

    return VectorSearchResponse(
        status=ResponseStatus.SUCCESS,
        message="查询成功",
        data=results,
        total=len(results)
    )


@router.get(
    "/stats/info",
    summary="获取集合统计信息",
    description="获取向量数据库集合的统计信息"
)
async def get_collection_stats(
    services: tuple = Depends(get_services)
):
    """获取集合统计信息"""
    vector_db_svc, _, _ = services

    info = vector_db_svc.get_collection_info()

    return {
        "status": "success",
        "data": info
    }


@router.get(
    "/stats/count",
    summary="统计记录数量",
    description="统计向量记录数量，支持标签过滤"
)
async def count_vectors(
    tags: Optional[List[str]] = Query(None, description="标签过滤"),
    services: tuple = Depends(get_services)
):
    """统计记录数量"""
    vector_db_svc, _, _ = services

    count = vector_db_svc.count(filter_tags=tags)

    return {
        "status": "success",
        "count": count
    }
