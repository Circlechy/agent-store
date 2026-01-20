"""
Embedding API路由
提供多模态Embedding生成接口
"""

import logging
from typing import List
from fastapi import APIRouter, HTTPException, Depends

from ..models import (
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingResult,
    ResponseStatus,
)
from ..services import get_embedding_service, EmbeddingService, get_storage_service, StorageService

router = APIRouter(prefix="/embedding", tags=["Embedding"])
logger = logging.getLogger(__name__)


def get_services():
    """获取服务依赖"""
    embedding_svc = get_embedding_service()
    storage_svc = get_storage_service()

    if not embedding_svc.is_initialized:
        raise HTTPException(status_code=503, detail="Embedding服务未初始化")

    return embedding_svc, storage_svc


@router.post(
    "/generate",
    response_model=EmbeddingResponse,
    summary="生成Embedding向量",
    description="""
    支持多种输入类型的Embedding向量生成：
    - 纯文本输入
    - 图片输入（通过图片ID或URL）
    - 图文混合输入
    
    返回归一化的向量表示，可用于后续的相似度计算和检索。
    """
)
async def generate_embedding(
    request: EmbeddingRequest,
    services: tuple = Depends(get_services)
):
    """
    生成Embedding向量

    - **inputs**: 输入列表，支持批量处理
    - **normalize**: 是否对向量进行L2归一化（默认True）
    """
    embedding_svc, storage_svc = services

    # 准备输入数据
    processed_inputs = []
    for inp in request.inputs:
        data = {}

        # 处理文本
        if inp.text:
            data["text"] = inp.text

        # 处理图片
        image_path = None
        if inp.image_id:
            path = storage_svc.get_image_path(inp.image_id)
            if path:
                image_path = str(path)
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"图片不存在: {inp.image_id}"
                )
        elif inp.image_url:
            image_path = inp.image_url

        if image_path:
            data["image"] = image_path

        # 处理指令
        if inp.instruction:
            data["instruction"] = inp.instruction

        if not data:
            raise HTTPException(
                status_code=400,
                detail="输入不能为空，必须提供text、image_id或image_url"
            )

        processed_inputs.append(data)

    # 生成Embedding
    embeddings = embedding_svc.generate_embeddings_batch(
        processed_inputs,
        normalize=request.normalize
    )

    # 构建响应
    results = [
        EmbeddingResult(
            index=i,
            embedding=emb,
            dimension=len(emb)
        )
        for i, emb in enumerate(embeddings)
    ]

    return EmbeddingResponse(
        status=ResponseStatus.SUCCESS,
        message="Embedding生成成功",
        data=results
    )


@router.post(
    "/text",
    response_model=EmbeddingResponse,
    summary="生成文本Embedding",
    description="快捷接口：仅处理文本输入"
)
async def generate_text_embedding(
    text: str,
    instruction: str = None,
    normalize: bool = True,
    services: tuple = Depends(get_services)
):
    """生成纯文本的Embedding向量"""
    embedding_svc, _ = services

    embedding = embedding_svc.generate_text_embedding(
        text=text,
        instruction=instruction,
        normalize=normalize
    )

    return EmbeddingResponse(
        status=ResponseStatus.SUCCESS,
        message="文本Embedding生成成功",
        data=[EmbeddingResult(
            index=0,
            embedding=embedding,
            dimension=len(embedding)
        )]
    )


@router.post(
    "/image",
    response_model=EmbeddingResponse,
    summary="生成图片Embedding",
    description="快捷接口：仅处理图片输入，支持自动存储和索引"
)
async def generate_image_embedding(
    image_id: str = None,
    image_url: str = None,
    instruction: str = None,
    normalize: bool = True,
    auto_store: bool = False,  # 新增：是否自动存储
    auto_index: bool = False,  # 新增：是否自动索引
    tags: str = None,  # 新增：标签
    services: tuple = Depends(get_services)
):
    """
    生成图片的Embedding向量

    Args:
        image_id: 已存储图片的ID
        image_url: 图片URL（如果auto_store=True，会下载并存储）
        auto_store: 是否自动下载并存储图片（仅对image_url有效）
        auto_index: 是否自动索引到向量数据库（需要auto_store=True）
        tags: 图片标签，逗号分隔
    """
    embedding_svc, storage_svc = services

    # 确定图片路径
    image_path = None
    stored_image_id = None

    if image_id:
        # 使用已存储的图片
        path = storage_svc.get_image_path(image_id)
        if path:
            image_path = str(path)
            stored_image_id = image_id
        else:
            raise HTTPException(status_code=404, detail=f"图片不存在: {image_id}")

    elif image_url:
        if auto_store:
            # 下载并存储图片
            import requests
            import tempfile
            from pathlib import Path

            try:
                # 下载图片
                img_response = requests.get(image_url, timeout=10)
                img_response.raise_for_status()

                # 提取文件名
                filename = Path(image_url).name or "downloaded_image.jpg"

                # 存储图片
                image_info = storage_svc.save_image(
                    content=img_response.content,
                    filename=filename
                )

                image_path = image_info["full_path"]
                stored_image_id = image_info["id"]

                logger.info(f"从 URL 下载并存储图片: {stored_image_id}")

            except Exception as e:
                logger.error(f"下载图片失败: {e}")
                raise HTTPException(
                    status_code=400, detail=f"下载图片失败: {str(e)}")
        else:
            # 直接使用URL（不存储）
            image_path = image_url

    else:
        raise HTTPException(status_code=400, detail="必须提供image_id或image_url")

    # 生成Embedding
    embedding = embedding_svc.generate_image_embedding(
        image=image_path,
        instruction=instruction,
        normalize=normalize
    )

    # 如果需要索引
    if auto_index and stored_image_id:
        try:
            from ..services import get_search_service
            from ..models import ImageMetadata

            search_svc = get_search_service()

            # 获取图片信息
            img_info = storage_svc.get_image_info(stored_image_id)

            # 构建元数据
            metadata = ImageMetadata(
                filename=img_info["filename"],
                file_path=img_info["file_path"],
                file_size=img_info["file_size"],
                width=img_info.get("width", 0),
                height=img_info.get("height", 0),
                format=img_info.get("format", ""),
                created_at=img_info["created_at"],
                tags=tags.split(",") if tags else [],
                description=f"从LRL下载: {image_url}" if image_url else ""
            )

            # 索引到向量数据库
            search_svc.index_image(
                image_id=stored_image_id,
                image_path=image_path,
                metadata=metadata.model_dump()
            )

            logger.info(f"图片已索引: {stored_image_id}")

        except Exception as e:
            logger.error(f"索引图片失败: {e}")

    response_data = EmbeddingResult(
        index=0,
        embedding=embedding,
        dimension=len(embedding)
    )

    # 如果存储了图片，返回image_id
    extra_info = {}
    if stored_image_id:
        extra_info["stored_image_id"] = stored_image_id
        extra_info["indexed"] = auto_index

    return EmbeddingResponse(
        status=ResponseStatus.SUCCESS,
        message="图片Embedding生成成功" + (
            f"，已存储为 {stored_image_id}" if stored_image_id else ""
        ),
        data=[response_data],
        **extra_info
    )


@router.get(
    "/dimension",
    summary="获取向量维度",
    description="返回当前模型的向量维度"
)
async def get_vector_dimension(
    services: tuple = Depends(get_services)
):
    """获取Embedding向量维度"""
    embedding_svc, _ = services

    return {
        "status": "success",
        "dimension": embedding_svc.vector_dimension
    }
