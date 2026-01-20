"""
图片存储API路由
提供图片上传、下载、管理接口
"""

import asyncio
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import Response

from ..models import (
    BaseResponse,
    ResponseStatus,
    ImageUploadResponse,
    ImageInfo,
    ImageListResponse,
    ImageMetadata,
)
from ..services import (
    get_storage_service,
    StorageService,
    get_search_service,
    SearchService,
    get_vector_db_service,
    VectorDBService
)

router = APIRouter(prefix="/storage", tags=["Storage"])


def get_services():
    """获取服务依赖"""
    storage_svc = get_storage_service()
    search_svc = get_search_service()
    vector_db_svc = get_vector_db_service()

    if not storage_svc.is_initialized:
        raise HTTPException(status_code=503, detail="存储服务未初始化")

    return storage_svc, search_svc, vector_db_svc


def _background_index_image(
    image_id: str,
    image_path: str,
    metadata: dict,
    search_svc: SearchService
):
    """
    后台异步索引图片
    在后台线程中生成Embedding并存入向量数据库

    注意：索引失败不会影响图片存储，但会导致该图片无法被搜索到
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"开始异步索引图片: {image_id}")

        success = search_svc.index_image(
            image_id=image_id,
            image_path=image_path,
            metadata=metadata
        )

        if success:
            logger.info(f"✅ 异步索引成功: {image_id}")
        else:
            logger.error(f"❌ 异步索引失败: {image_id} - index_image返回False")

    except Exception as e:
        # 关键改进：记录详细的错误信息
        logger.error(f"❌ 异步索引异常: {image_id}", exc_info=True)
        logger.error(f"   错误详情: {str(e)}")
        logger.error(f"   图片路径: {image_path}")
        logger.error(f"   元数据: {metadata}")
        # 注意：异步索引失败不影响图片存储，图片文件已成功保存


@router.post(
    "/upload",
    response_model=ImageUploadResponse,
    summary="上传图片",
    description="""
    上传单张图片并可选择自动索引到向量数据库。
    - 支持jpg、jpeg、png、gif、webp、bmp格式
    - 最大文件大小50MB
    - 可选自动生成Embedding并存入向量库（异步执行）
    """
)
async def upload_image(
    file: UploadFile = File(..., description="图片文件"),
    auto_index: bool = Form(True, description="是否自动索引到向量库"),
    async_index: bool = Form(True, description="是否异步索引（推荐）"),
    tags: Optional[str] = Form(None, description="标签，逗号分隔"),
    description: Optional[str] = Form(None, description="图片描述"),
    background_tasks: BackgroundTasks = None,
    services: tuple = Depends(get_services)
):
    """上传图片"""
    storage_svc, search_svc, vector_db_svc = services

    # 读取文件内容
    content = await file.read()

    # 保存图片
    image_info = storage_svc.save_image(content, file.filename)

    # 处理标签
    tag_list = []
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    # 自动索引
    if auto_index and search_svc.is_initialized:
        metadata = ImageMetadata(
            filename=image_info["filename"],
            file_path=image_info["file_path"],
            file_size=image_info["file_size"],
            width=image_info["width"],
            height=image_info["height"],
            format=image_info["format"],
            created_at=image_info["created_at"],
            tags=tag_list,
            description=description or ""
        )

        if async_index and background_tasks is not None:
            # 异步后台索引（推荐）
            background_tasks.add_task(
                _background_index_image,
                image_id=image_info["id"],
                image_path=image_info["full_path"],
                metadata=metadata.model_dump(),
                search_svc=search_svc
            )
            image_info["indexed"] = "processing"  # 索引处理中
            image_info["index_mode"] = "async"  # 新增：标识异步模式
        else:
            # 同步索引 - 增强错误处理
            try:
                success = search_svc.index_image(
                    image_id=image_info["id"],
                    image_path=image_info["full_path"],
                    metadata=metadata.model_dump()
                )
                image_info["indexed"] = success  # 根据实际结果设置
                image_info["index_mode"] = "sync"

                if not success:
                    # 索引失败但不影响图片存储
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"同步索引失败但图片已保存: {image_info['id']}")

            except Exception as e:
                # 捕获索引异常，但不影响图片存储流程
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"同步索引异常: {image_info['id']}", exc_info=True)

                image_info["indexed"] = False
                image_info["index_mode"] = "sync"
                image_info["index_error"] = str(e)
    else:
        image_info["indexed"] = False
        image_info["index_mode"] = "none"

    return ImageUploadResponse(
        status=ResponseStatus.SUCCESS,
        message="图片上传成功",
        data=image_info
    )


@router.post(
    "/upload/batch",
    response_model=BaseResponse,
    summary="批量上传图片",
    description="批量上传多张图片"
)
async def upload_images_batch(
    files: List[UploadFile] = File(..., description="图片文件列表"),
    auto_index: bool = Form(True, description="是否自动索引"),
    services: tuple = Depends(get_services)
):
    """批量上传图片"""
    storage_svc, search_svc, vector_db_svc = services

    results = []
    errors = []

    for file in files:
        content = await file.read()
        image_info = storage_svc.save_image(content, file.filename)

        if auto_index and search_svc.is_initialized:
            metadata = ImageMetadata(
                filename=image_info["filename"],
                file_path=image_info["file_path"],
                file_size=image_info["file_size"],
                width=image_info["width"],
                height=image_info["height"],
                format=image_info["format"],
                created_at=image_info["created_at"],
                tags=[],
                description=""
            )

            search_svc.index_image(
                image_id=image_info["id"],
                image_path=image_info["full_path"],
                metadata=metadata.model_dump()
            )
            image_info["indexed"] = True

        results.append(image_info)

    return BaseResponse(
        status=ResponseStatus.SUCCESS,
        message=f"成功上传 {len(results)} 张图片",
        data={
            "uploaded": results,
            "errors": errors
        }
    )


@router.get(
    "/images/{image_id}",
    summary="获取图片",
    description="根据ID获取图片文件",
    responses={
        200: {
            "content": {"image/*": {}},
            "description": "图片文件"
        }
    }
)
async def get_image(
    image_id: str,
    services: tuple = Depends(get_services)
):
    """获取图片文件"""
    storage_svc, _, _ = services

    result = storage_svc.get_image(image_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"图片不存在: {image_id}")

    content, media_type = result

    return Response(
        content=content,
        media_type=media_type
    )


@router.get(
    "/images/{image_id}/info",
    response_model=BaseResponse,
    summary="获取图片信息",
    description="获取图片的详细信息"
)
async def get_image_info(
    image_id: str,
    services: tuple = Depends(get_services)
):
    """获取图片信息"""
    storage_svc, _, _ = services

    info = storage_svc.get_image_info(image_id)

    if not info:
        raise HTTPException(status_code=404, detail=f"图片不存在: {image_id}")

    return BaseResponse(
        status=ResponseStatus.SUCCESS,
        message="获取成功",
        data=info
    )


@router.delete(
    "/images/{image_id}",
    response_model=BaseResponse,
    summary="删除图片",
    description="删除图片文件及其向量索引"
)
async def delete_image(
    image_id: str,
    delete_vector: bool = Query(True, description="是否同时删除向量索引"),
    services: tuple = Depends(get_services)
):
    """删除图片"""
    storage_svc, search_svc, vector_db_svc = services

    # 删除文件
    success = storage_svc.delete_image(image_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"图片不存在: {image_id}")

    # 删除向量索引
    if delete_vector and vector_db_svc.is_initialized:
        vector_db_svc.delete(image_id)

    return BaseResponse(
        status=ResponseStatus.SUCCESS,
        message="图片已删除"
    )


@router.get(
    "/images",
    response_model=ImageListResponse,
    summary="列出图片",
    description="分页获取图片列表"
)
async def list_images(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向"),
    services: tuple = Depends(get_services)
):
    """列出图片"""
    storage_svc, _, _ = services

    images, total = storage_svc.list_images(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order
    )

    image_infos = [
        ImageInfo(
            id=img["id"],
            filename=img["filename"],
            file_path=img["file_path"],
            file_size=img["file_size"],
            width=img["width"],
            height=img["height"],
            format=img["format"],
            created_at=img["created_at"],
            url=img["url"]
        )
        for img in images
    ]

    return ImageListResponse(
        status=ResponseStatus.SUCCESS,
        message="获取成功",
        data=image_infos,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get(
    "/stats",
    summary="获取存储统计",
    description="获取存储空间使用统计"
)
async def get_storage_stats(
    services: tuple = Depends(get_services)
):
    """获取存储统计"""
    storage_svc, _, _ = services

    stats = storage_svc.get_storage_stats()

    return {
        "status": "success",
        "data": stats
    }


@router.post(
    "/index/{image_id}",
    response_model=BaseResponse,
    summary="索引单张图片",
    description="将已存储的图片索引到向量数据库"
)
async def index_image(
    image_id: str,
    tags: Optional[List[str]] = Query(None, description="标签列表"),
    description: Optional[str] = Query(None, description="图片描述"),
    services: tuple = Depends(get_services)
):
    """索引单张图片"""
    storage_svc, search_svc, _ = services

    if not search_svc.is_initialized:
        raise HTTPException(status_code=503, detail="搜索服务未初始化")

    # 获取图片信息
    image_info = storage_svc.get_image_info(image_id)
    if not image_info:
        raise HTTPException(status_code=404, detail=f"图片不存在: {image_id}")

    # 构建元数据
    metadata = ImageMetadata(
        filename=image_info["filename"],
        file_path=image_info["file_path"],
        file_size=image_info["file_size"],
        width=image_info["width"],
        height=image_info["height"],
        format=image_info["format"],
        created_at=image_info["created_at"],
        tags=tags or [],
        description=description or ""
    )

    # 索引
    success = search_svc.index_image(
        image_id=image_id,
        image_path=image_info["full_path"],
        metadata=metadata.model_dump()
    )

    if success:
        return BaseResponse(
            status=ResponseStatus.SUCCESS,
            message="图片索引成功"
        )
    else:
        raise HTTPException(status_code=500, detail="索引失败")


@router.post(
    "/index/all",
    response_model=BaseResponse,
    summary="索引所有图片",
    description="将存储中所有未索引的图片添加到向量数据库"
)
async def index_all_images(
    services: tuple = Depends(get_services)
):
    """索引所有图片"""
    storage_svc, search_svc, vector_db_svc = services

    if not search_svc.is_initialized:
        raise HTTPException(status_code=503, detail="搜索服务未初始化")

    # 获取所有图片
    images, total = storage_svc.list_images(page=1, page_size=10000)

    indexed_count = 0
    for img in images:
        # 检查是否已索引
        existing = vector_db_svc.get(img["id"])
        if existing:
            continue

        metadata = ImageMetadata(
            filename=img["filename"],
            file_path=img["file_path"],
            file_size=img["file_size"],
            width=img["width"],
            height=img["height"],
            format=img["format"],
            created_at=img["created_at"],
            tags=[],
            description=""
        )

        search_svc.index_image(
            image_id=img["id"],
            image_path=img["full_path"],
            metadata=metadata.model_dump()
        )
        indexed_count += 1

    return BaseResponse(
        status=ResponseStatus.SUCCESS,
        message=f"成功索引 {indexed_count} 张图片",
        data={
            "indexed": indexed_count,
            "total": total
        }
    )
